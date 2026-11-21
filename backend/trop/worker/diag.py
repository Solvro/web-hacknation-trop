"""Worker diagnostics: every task is wrapped so its start / end / exception lands in Redis (no logs needed), read by GET /api/v1/debug/worker.

Keys: `trop:tasks:running` (hash job_id -> json, removed at the end), `trop:tasks:log` (list, newest first, max 100),
`trop:worker:info` (hash written at worker startup: uid, writable data dirs, mode, which keys are present -- never their values).
"""
from __future__ import annotations

import functools
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trop.config import settings

RUNNING, LOG, INFO = "trop:tasks:running", "trop:tasks:log", "trop:worker:info"
LOG_MAX = 100


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _r():
    import redis
    return redis.Redis.from_url(settings.redis_url, socket_timeout=3, socket_connect_timeout=3)


def dir_checks() -> dict[str, Any]:
    """Can THIS process create + write + delete inside the data dirs the tasks need?"""
    out: dict[str, Any] = {}
    data = Path(settings.data_dir)
    for name, p in (("data", data), ("investigations", data / "investigations"), ("cache", Path(settings.cache_dir)),
                    ("logs", data / "logs"), ("artifacts", Path(settings.artifact_dir))):
        try:
            p.mkdir(parents=True, exist_ok=True)
            f = p / f".probe-{os.getpid()}"
            f.write_text("x")
            f.unlink()
            out[name] = {"writable": True}
        except Exception as e:  # noqa: BLE001
            out[name] = {"writable": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}
    return out


def env_info() -> dict[str, Any]:
    return {"uid": os.getuid(), "mode": settings.trop_mode, "no_live": os.environ.get("TROP_NO_LIVE"), "capture": os.environ.get("TROP_CAPTURE"),
            "has_gemini_key": bool(settings.gemini_api_key), "has_openrouter_key": bool(settings.openrouter_api_key),
            "llm_budget_usd": settings.llm_budget_usd, "data_dir": str(settings.data_dir), "pid": os.getpid()}


def write_info(extra: dict | None = None) -> None:
    try:
        r = _r()
        r.hset(INFO, mapping={"at": _now(), "env": json.dumps(env_info()), "dirs": json.dumps(dir_checks()), **{k: json.dumps(v) for k, v in (extra or {}).items()}})
    except Exception:  # noqa: BLE001
        pass


def _record(entry: dict) -> None:
    try:
        r = _r()
        r.lpush(LOG, json.dumps(entry, ensure_ascii=False))
        r.ltrim(LOG, 0, LOG_MAX - 1)
    except Exception:  # noqa: BLE001
        pass


def recorded(fn):
    """Decorator for arq task coroutines. Exceptions are recorded and re-raised; an `{"error": ...}` result (tasks that swallow their own
    errors to emit a Polish event) is recorded as an error too."""
    @functools.wraps(fn)
    async def wrapper(ctx: dict, *args: Any, **kw: Any):
        jid = ctx.get("job_id") or (args[0] if args and isinstance(args[0], str) else "?")
        t0, started = time.monotonic(), _now()
        try:
            _r().hset(RUNNING, str(jid), json.dumps({"function": fn.__name__, "started": started}))
        except Exception:  # noqa: BLE001
            pass
        status, etype, emsg = "ok", None, None
        try:
            res = await fn(ctx, *args, **kw)
            if isinstance(res, dict) and res.get("error"):
                status, emsg = "error", str(res["error"])[:300]
            return res
        except BaseException as e:  # noqa: BLE001 -- includes CancelledError (arq job_timeout)
            status, etype, emsg = "exception", type(e).__name__, str(e)[:300]
            raise
        finally:
            _record({"job_id": str(jid), "function": fn.__name__, "status": status, "started": started, "duration_s": round(time.monotonic() - t0, 2),
                     "exception_type": etype, "message": emsg})
            try:
                _r().hdel(RUNNING, str(jid))
            except Exception:  # noqa: BLE001
                pass
    return wrapper


def snapshot() -> dict[str, Any]:
    """Everything GET /debug/worker returns that lives in Redis (sync; call from a thread)."""
    r = _r()
    out: dict[str, Any] = {}
    try:
        out["queue_length"] = r.zcard("arq:queue")
        out["queued_jobs"] = [(k.decode() if isinstance(k, bytes) else k) for k in r.zrange("arq:queue", 0, 19)]
        ip = [k.decode() if isinstance(k, bytes) else k for k in r.scan_iter("arq:in-progress:*", count=200)]
        out["arq_in_progress"] = [k.rsplit(":", 1)[-1] for k in ip]
        run = r.hgetall(RUNNING)
        now = datetime.now(timezone.utc)
        rows = []
        for k, v in run.items():
            d = json.loads(v)
            try:
                d["running_s"] = round((now - datetime.fromisoformat(d["started"])).total_seconds())
            except Exception:  # noqa: BLE001
                pass
            rows.append({"job_id": k.decode(), **d})
        out["running"] = rows
        hb = r.get("arq:queue:health-check")
        out["heartbeat"] = {"alive": hb is not None, "info": hb.decode() if hb else None, "ttl_s": r.ttl("arq:queue:health-check")}
        out["recent"] = [json.loads(x) for x in r.lrange(LOG, 0, 19)]
        info = r.hgetall(INFO)
        out["worker"] = {k.decode(): (json.loads(v) if v[:1] in (b"{", b"[") else v.decode()) for k, v in info.items()}
    except Exception as e:  # noqa: BLE001
        out["redis_error"] = f"{type(e).__name__}: {str(e)[:150]}"
    return out
