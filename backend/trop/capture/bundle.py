"""Light bundle -> incident sections (landing / tracking / infra / quality) used by the Hunter before the full ingest
(WS1 `trop.ingest`) re-extracts everything from the same bundle. Deterministic, no ML, never contacts the network."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ._util import etld1_of, host_of

FB_PIXEL = re.compile(r"""fbq\(\s*['"]init['"]\s*,\s*['"]?(\d{8,17})""")
FB_ID_URL = re.compile(r"facebook\.com/tr/?\?[^\"' ]*?\bid=(\d{8,17})")
GTM = re.compile(r"\b(GTM-[A-Z0-9]{4,9})\b")
GA4 = re.compile(r"\b(G-[A-Z0-9]{8,12})\b")
GADS = re.compile(r"\b(AW-\d{8,12})\b")
TT = re.compile(r"ttq\.load\(\s*['\"]([A-Z0-9]{10,24})")
SOCIAL_CDN = ("facebook.net", "facebook.com", "fbcdn.net", "googletagmanager.com", "google-analytics.com", "google.com",
              "gstatic.com", "googleapis.com", "doubleclick.net", "tiktok.com", "cloudflare.com", "cdnjs.cloudflare.com")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore") if p.is_file() else ""


def _json(p: Path, default: Any):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def bundle_sections(bundle: str | Path) -> dict[str, Any]:
    b = Path(bundle)
    info = _json(b / "archive_info.json", {})
    dns_ssl = _json(b / "dns_ssl.json", {})
    redirects = _json(b / "redirects.json", [])
    forms = _json(b / "forms.json", [])
    outlinks = _json(b / "outlinks.json", [])
    text = _read(b / "page_text.txt")
    html = _read(b / "html" / "rendered.html")
    final = info.get("final_url") or info.get("url") or ""
    host = host_of(final)
    src = html + " " + _read(b / "html" / "source.html")
    hosts: set[str] = set()
    har = _json(b / "network.har", {})
    for e in (har.get("log") or {}).get("entries", []):
        h = host_of(e.get("request", {}).get("url", ""))
        if h:
            hosts.add(h)
    third = sorted({etld1_of(h) for h in hosts if etld1_of(h) != etld1_of(host)} - set(SOCIAL_CDN))[:60]
    land = {"entry_url": info.get("url"), "final_url": final, "host": host, "etld1": etld1_of(host), "status": info.get("status"),
            "title": info.get("title"), "text": text[:20000] or None,
            "redirect_chain": [h["url"] for h in redirects], "n_hars": 1, "n_pages": 1,
            "screenshot_path": str(b / "screenshots" / "viewport.png") if (b / "screenshots" / "viewport.png").is_file() else None,
            "forms": forms, "outlinks": outlinks[:200],
            "page_role": info.get("page_role_hint") or ("content" if text else "unknown")}
    tracking = {"fb_pixels": sorted(set(FB_PIXEL.findall(src)) | set(FB_ID_URL.findall("\n".join(hosts) + src))),
                "gtm": sorted(set(GTM.findall(src))), "ga4": sorted(set(GA4.findall(src))),
                "google_ads": sorted(set(GADS.findall(src))), "tiktok_pixels": sorted(set(TT.findall(src))),
                "third_party": third}
    ips = [dns_ssl["ip"]] if dns_ssl.get("ip") else []
    cert = dns_ssl.get("ssl") or None
    infra = {"domains": [{"fqdn": host, "etld1": etld1_of(host), "tld": etld1_of(host).split(".", 1)[-1] if "." in etld1_of(host) else None,
                          "sld_label": etld1_of(host).split(".")[0], "ips": ips, "cert": cert, "enrich": {}}] if host else [],
             "ips": ips}
    return {"landing": land, "tracking": tracking, "infra": infra,
            "quality": {"available": ["capture"] + (["har"] if har else []), "missing": [], "errors": [info["error"]] if info.get("error") else []},
            "captured_at": info.get("timestamp_utc"), "challenge": bool(info.get("challenge_detected"))}
