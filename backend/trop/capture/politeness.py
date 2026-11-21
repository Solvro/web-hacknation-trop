"""Per-registrable-domain politeness budget (filesystem token bucket) + circuit breaker.

Defaults: 6 captures/hour per eTLD+1 and, after 3 consecutive failures, a cooldown of 1 h doubling up to 24 h.
Scam hosts are short-lived and ban aggressive visitors (and burn the cloaker's "good visitor" decision), so being
gentle also keeps captures representative. State: <cache_dir>/capture/budget.json (flock-protected).
"""
from __future__ import annotations

import fcntl
import json
import time
from contextlib import contextmanager
from pathlib import Path

from trop.config import settings

MAX_PER_HOUR = 6.0


def _path() -> Path:
    p = Path(settings.cache_dir) / "capture" / "budget.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@contextmanager
def _locked():
    p = _path()
    with open(str(p) + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        state = json.loads(p.read_text()) if p.exists() else {}
        yield state
        p.write_text(json.dumps(state))


def acquire(etld1: str, cost: float = 1.0, max_per_hour: float = MAX_PER_HOUR) -> tuple[bool, float]:
    """-> (allowed, seconds_to_wait)."""
    now = time.time()
    with _locked() as st:
        b = st.setdefault(etld1, {"tokens": max_per_hour, "t": now, "errors": 0, "cooldown_until": 0})
        if b["cooldown_until"] > now:
            return False, b["cooldown_until"] - now
        b["tokens"] = min(max_per_hour, b["tokens"] + (now - b["t"]) / 3600.0 * max_per_hour)
        b["t"] = now
        if b["tokens"] >= cost:
            b["tokens"] -= cost
            return True, 0.0
        return False, (cost - b["tokens"]) / max_per_hour * 3600.0


def report(etld1: str, ok: bool) -> None:
    with _locked() as st:
        b = st.setdefault(etld1, {"tokens": MAX_PER_HOUR, "t": time.time(), "errors": 0, "cooldown_until": 0})
        if ok:
            b["errors"], b["cooldown_until"] = 0, 0
            return
        b["errors"] += 1
        if b["errors"] >= 3:
            b["cooldown_until"] = time.time() + min(24, 2 ** (b["errors"] - 3)) * 3600
