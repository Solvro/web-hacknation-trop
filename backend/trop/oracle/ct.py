"""Certificate-issuance inputs for the Oracle. Each source yields {"domain", "issuer", "not_before", "source"} dicts.

* certstream_collect: self-hosted certstream-server-go (/domains-only or /full-stream, ORACLE_CERTSTREAM_URL) for N seconds
  (the public CaliDog server is dead). Optional: returns [] when nothing listens.
* urlscan_recent: newly scanned domains on the campaign TLDs with their TLS cert time (free search; polling fallback,
  because crt.sh / Cert Spotter cannot enumerate a whole TLD).
* crtsh_domain / file replay for targeted checks and tests.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from trop.enrich import urlscan
from trop.enrich.util import etld1

DEFAULT_STREAM = "ws://127.0.0.1:18101/full-stream"


def certstream_collect(tlds: Iterable[str], seconds: float = 30.0, url: str | None = None, max_items: int = 5000) -> list[dict]:
    url = url or os.environ.get("ORACLE_CERTSTREAM_URL", DEFAULT_STREAM)
    tl = {"." + t.lstrip(".") for t in tlds}
    out: list[dict] = []
    try:
        from websockets.sync.client import connect
        with connect(url, open_timeout=5, ping_interval=20) as ws:
            end = time.time() + seconds
            while time.time() < end and len(out) < max_items:
                try:
                    msg = json.loads(ws.recv(timeout=max(0.1, end - time.time())))
                except TimeoutError:
                    break
                d = msg.get("data")
                if msg.get("message_type") == "dns_entries":
                    names, nb, iss = d, time.time(), None
                else:
                    leaf = (d or {}).get("leaf_cert", {})
                    names, nb = leaf.get("all_domains", []), leaf.get("not_before", time.time())
                    iss = ((leaf.get("issuer") or {}).get("aggregated")) or ((leaf.get("issuer") or {}).get("CN"))
                for n in names or []:
                    n = n.lstrip("*.").lower()
                    if any(n.endswith(t) for t in tl):
                        out.append({"domain": etld1(n), "issuer": iss, "source": "certstream",
                                    "not_before": datetime.fromtimestamp(float(nb), timezone.utc).isoformat()})
    except Exception:           # no server / handshake failure: optional source
        return out
    return out


def urlscan_recent(tlds: Iterable[str], hours: int = 24, size: int = 100) -> list[dict]:
    out = []
    for t in tlds:
        span = f"{hours // 24}d" if hours % 24 == 0 else f"{hours}h"
        r = urlscan.search(f"page.domain:*.{t.lstrip('.')} AND date:>now-{span}", size)
        for s in r.get("results", []):
            d = s.get("apex") or etld1(s.get("domain") or "")
            if d and not s.get("umbrella_rank"):
                out.append({"domain": d, "issuer": s.get("tls_issuer"), "not_before": s.get("tls_valid_from") or s.get("time"),
                            "source": "urlscan", "first_seen": s.get("time"), "ip": s.get("ip"), "title": s.get("title")})
    seen, uniq = set(), []
    for o in out:
        if o["domain"] not in seen:
            seen.add(o["domain"])
            uniq.append(o)
    return uniq


def from_file(path: str | Path) -> list[dict]:
    """Replay: JSON list of {"domain","issuer","not_before"} (e.g. a recorded CT sample)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
