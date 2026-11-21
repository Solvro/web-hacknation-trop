"""`HunterSource` / `HunterRun` objects for the API (GET /hunter/sources, /hunter/runs), derived from run records on disk."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from trop.config import settings
from trop.schema import HunterRun, HunterSource

from . import gazetteer, google_atc, sink

DEFS = [
    ("meta_adlibrary", "meta_adlibrary", "Meta Ad Library (PL)", "every 6 h", "meta"),
    ("certpl", "certpl", "CERT Polska warning list diff", "hourly", "certpl"),
    ("urlscan", "urlscan", "urlscan.io pivots (search only)", "daily", "urlscan"),
    ("google_ads_transparency", "google_ads_transparency", "Google Ads Transparency (BigQuery)", "daily", "google"),
]


def _cred(kind: str) -> str:
    if kind == "meta_adlibrary":
        return "set" if settings.meta_access_token else "missing"
    if kind == "google_ads_transparency":
        return google_atc.credentials_status()
    return "not_needed"


def list_sources() -> list[HunterSource]:
    runs = sink.list_runs(limit=200)
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    out = []
    for sid, kind, label, sched, _ in DEFS:
        mine = [r for r in runs if r.source_id == sid]
        recent = [r for r in mine if datetime.fromisoformat(r.started_at) >= day_ago]
        cred = _cred(sid)
        last = mine[0] if mine else None
        status = "disabled" if cred == "missing" else ("error" if last and last.status == "error" else
                                                      ("degraded" if any(r.status == "error" for r in recent) else "ok"))
        cfg = {"country": "PL"}
        if sid == "meta_adlibrary":
            cfg |= {"phrases": gazetteer.LURE_PHRASES, "persons": list(gazetteer.PERSONS)[:12], "advertisers": []}
        out.append(HunterSource(id=sid, kind=kind, label=label, schedule=sched, status=status,
                                last_run_at=last.started_at if last else None, new_24h=sum(r.found for r in recent),
                                errors_24h=sum(1 for r in recent if r.status == "error"), enabled=cred != "missing",
                                credentials_status=cred, config=cfg))
    return out


def list_runs(source_id: str | None = None, limit: int = 50) -> list[HunterRun]:
    return sink.list_runs(source_id, limit)
