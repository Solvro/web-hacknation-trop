"""Adapter: a urlscan.io scan result (someone else's capture) → IncidentDraft, without visiting the site.

Inputs per scan uuid: /api/v1/result/<uuid>/ (requests with body sha256, IPs, TLS, redirects, links, form
input names), /dom/<uuid>/ (rendered DOM) and /screenshots/<uuid>.png. The request list is mapped onto our
Har model so the very same extractor (rules@1) produces the same observable types as for HAR captures; body
hashes come from urlscan's `response.hash` instead of the body itself.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..util.urls import host_of
from .capture_builder import build_capture
from .extract import PUBLIC_LIB_HOSTS, _under
from .har import Har, HarEntry
from .model import ArtifactDraft, IncidentDraft, ObsHit

TYPE_MAP = {"document": "document", "script": "script", "stylesheet": "stylesheet", "image": "image", "font": "font",
            "media": "media", "xhr": "xhr", "fetch": "fetch", "ping": "ping", "websocket": "websocket",
            "eventsource": "eventsource", "manifest": "manifest", "other": "other"}


def _ts(v) -> datetime | None:
    if v is None:
        return None
    try:
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v, timezone.utc)
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (ValueError, OSError):
        return None


def to_har(result: dict) -> Har:
    reqs = result.get("data", {}).get("requests", [])
    main_frame = next((r["request"].get("frameId") for r in reqs if r.get("request", {}).get("primaryRequest")), None)
    entries = []
    for i, r in enumerate(reqs):
        rq, rs = r.get("request", {}), r.get("response", {})
        inner_rq, inner_rs = rq.get("request", {}), rs.get("response", {})
        url = inner_rq.get("url") or inner_rs.get("url") or ""
        rtype = TYPE_MAP.get(str(rq.get("type") or rs.get("type") or "other").lower(), "other")
        if rtype == "document" and main_frame and rq.get("frameId") != main_frame:
            rtype = "frame"
        ip = (inner_rs.get("remoteIPAddress") or "").strip("[]") or None
        entries.append(HarEntry(
            seq=i, started=_ts(rq.get("wallTime")), method=inner_rq.get("method", "GET"), url=url, host=host_of(url),
            status=inner_rs.get("status"), status_text=inner_rs.get("statusText", ""), mime=inner_rs.get("mimeType"),
            resource_type=rtype, server_ip=ip, body=None, body_size=rs.get("dataLength") or rs.get("size"),
            redirect_url=None, initiator_type=(rq.get("initiator") or {}).get("type"),
            initiator_url=(rq.get("initiator") or {}).get("url"), pageref=None,
            req_headers={k.lower(): str(v) for k, v in (inner_rq.get("headers") or {}).items()},
            resp_headers={k.lower(): str(v) for k, v in (inner_rs.get("headers") or {}).items()}))
        entries[-1].urlscan_hash = rs.get("hash")          # body sha256 computed by urlscan
        entries[-1].security = inner_rs.get("securityDetails")
    entries.sort(key=lambda e: (e.started or datetime.min.replace(tzinfo=timezone.utc), e.seq))
    return Har(creator="urlscan.io", creator_version=(result.get("scanner") or {}).get("country"),
               browser=None, pages=[], entries=entries)


def to_incident(result: dict, dom: bytes | None, screenshot: bytes | None, source_key: str = "urlscan_scan") -> IncidentDraft:
    task, page = result.get("task", {}), result.get("page", {})
    uuid = task.get("uuid")
    har = to_har(result)
    cap, hits, rels = build_capture(
        har=har, har_artifact=None, html=dom, html_role="landing_html_rendered", html_rel="dom.html",
        files_dir=None, fallback_url=task.get("url"), fallback_time=_ts(task.get("time")), cap_ref=f"urlscan:{uuid}",
        tool="urlscan")
    cap.captured_at = _ts(task.get("time")) or cap.captured_at
    cap.meta["captured_at_source"] = "urlscan_task"
    cap.final_url = page.get("url") or cap.final_url
    cap.title = cap.title or page.get("title")
    cap.meta["urlscan"] = {"uuid": uuid, "visibility": task.get("visibility"), "source": task.get("source"),
                           "country": page.get("country"), "verdict": (result.get("verdicts") or {}).get("overall"),
                           "input_names": (result.get("data") or {}).get("inputNames", [])[:50],
                           "tags": task.get("tags")}
    # asset hashes from urlscan (we never had the bodies)
    by_seq = {r.seq: r for r in cap.requests}
    for e in har.entries:
        h = getattr(e, "urlscan_hash", None)
        if not h:
            continue
        if e.seq in by_seq:
            by_seq[e.seq].body_sha256 = h
        if e.resource_type in ("script", "stylesheet", "image", "font", "xhr", "fetch", "other") and (e.body_size or 0) >= 256 \
                and e.status and e.status < 300:
            noise = "public_cdn_library" if _under(e.host, PUBLIC_LIB_HOSTS) else None
            hits.append(ObsHit("asset_sha256", h, f"urlscan.asset:{e.resource_type}", display=(f"{e.host}{e.url.split(e.host, 1)[-1][:150]}" if e.host else e.url[:150]),
                               context={"capture": cap_ref_of(uuid), "seq": e.seq, "url": e.url[:300]}, noise_reason=noise))
    # TLS of the main document → certificate batch (urlscan gives issuer + validity, not the serial)
    main = next((e for e in har.entries if e.resource_type == "document" and getattr(e, "security", None)), None)
    if main and main.security:
        sec = main.security
        nb = _ts(sec.get("validFrom"))
        cap.tls = {"issuer": sec.get("issuer"), "subjectName": sec.get("subjectName"), "sanList": sec.get("sanList"),
                   "validFrom": str(nb) if nb else None, "validTo": str(_ts(sec.get("validTo")))}
        if nb and sec.get("issuer"):
            hits.append(ObsHit("cert_batch", f"{str(sec['issuer']).lower()}|{nb:%Y-%m-%dT%H}", "urlscan.tls",
                               context={"capture": cap_ref_of(uuid)}))
    if screenshot:
        cap.artifacts.append(ArtifactDraft(role="landing_screenshot_full", data=screenshot, rel_path=f"{uuid}.png", mime="image/png"))

    inc = IncidentDraft(source_key=source_key, source_ref=f"urlscan:{uuid}", kind="landing_only",
                        observed_at=cap.captured_at, entry_url=task.get("url"), captures=[cap], observables=hits,
                        relations=rels, sensitivity="internal",
                        quality={"available": ["urlscan_result"] + (["dom"] if dom else []) + (["screenshot"] if screenshot else []),
                                 "missing": ["ad", "response_bodies"], "errors": []})
    from .sample_dir import finalize_content
    finalize_content(inc)
    return inc


def cap_ref_of(uuid: str | None) -> str:
    return f"urlscan:{uuid}"
