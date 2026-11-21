"""Rule-based observable extraction from a capture (HAR entries + HTML + URLs).

Everything here is deterministic and explainable: every ObsHit carries the field it came from
and a context pointer (request seq / URL), which becomes the evidence chip in the UI.
"""
from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable
from urllib.parse import unquote, urlsplit

from ..util.hashing import favicon_mmh3, sha256_bytes
from ..util.urls import (etld1_of, host_of, is_ip, param_schema, query_params, split_host,
                         templatize_path)
from .har import Har, HarEntry
from .html import ParsedHtml, tracking_ids
from .model import ObsHit, RelationDraft, RequestDraft

EXTRACTOR = "rules@1"

# Third-party hosts that every site loads: weight 0 as hosts, and asset hashes from them are noise.
PLATFORM_HOSTS = (
    "facebook.net", "facebook.com", "fbcdn.net", "instagram.com", "google-analytics.com",
    "googletagmanager.com", "gstatic.com", "googleapis.com", "google.com", "doubleclick.net",
    "googlesyndication.com", "googleadservices.com", "youtube.com", "ytimg.com", "jquery.com",
    "cloudflare.com", "cloudflareinsights.com", "jsdelivr.net", "unpkg.com", "bootstrapcdn.com",
    "fontawesome.com", "hotjar.com", "clarity.ms", "tiktok.com", "tiktokcdn.com", "yandex.ru",
    "gravatar.com", "wp.com", "polyfill.io", "recaptcha.net",
)
PUBLIC_LIB_HOSTS = ("code.jquery.com", "cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com",
                    "ajax.googleapis.com", "fonts.googleapis.com", "fonts.gstatic.com",
                    "stackpath.bootstrapcdn.com", "maxcdn.bootstrapcdn.com", "use.fontawesome.com",
                    "connect.facebook.net", "www.googletagmanager.com", "www.google-analytics.com")

# Serverless / PaaS hosts used as Conversions-API gateways or kit backends.
CLOUD_GATEWAY = re.compile(
    r"(\.on\.aws|\.run\.app|\.lambda-url\.[a-z0-9-]+\.on\.aws|\.execute-api\.[a-z0-9-]+\.amazonaws\.com|"
    r"\.cloudfunctions\.net|\.workers\.dev|\.vercel\.app|\.netlify\.app|\.herokuapp\.com|\.azurewebsites\.net|"
    r"\.appspot\.com|\.supabase\.co|\.firebaseio\.com|\.onrender\.com|\.fly\.dev|\.railway\.app)$")

# Accounts/libraries on third-party services: (name, host regex, url regex → group(1) = account id)
THIRD_PARTY_ACCOUNTS = [
    ("pandavideo", re.compile(r"(vz-[0-9a-f]{8}-[0-9a-f]{3})")),
    ("converteai", re.compile(r"converteai\.net/([0-9a-f-]{20,})/")),
    ("vturb", re.compile(r"vturb\.com\.br/([0-9a-f-]{20,})/")),
    ("cloudinary", re.compile(r"res\.cloudinary\.com/([a-z0-9_-]+)/")),
    ("firebase", re.compile(r"([a-z0-9-]+)\.(?:firebaseapp\.com|firebaseio\.com|web\.app)")),
    ("supabase", re.compile(r"([a-z0-9]{20})\.supabase\.co")),
    ("s3", re.compile(r"([a-z0-9.\-]{3,63})\.s3[.-](?:[a-z0-9-]+\.)?amazonaws\.com")),
    ("cloudfront", re.compile(r"(d[a-z0-9]{12,14})\.cloudfront\.net")),
    ("wistia", re.compile(r"fast\.wistia\.(?:com|net)/embed/(?:medias|iframe)/([a-z0-9]{10})")),
    ("vimeo", re.compile(r"player\.vimeo\.com/video/(\d{6,12})")),
    ("youtube", re.compile(r"youtube(?:-nocookie)?\.com/embed/([A-Za-z0-9_-]{11})")),
    ("joxi", re.compile(r"static\.joxi\.pro/([a-z0-9_-]{3,40})/")),
    ("bunny", re.compile(r"([a-z0-9-]+)\.b-cdn\.net")),
]

# CDN edge ranges: IPs here are shared infrastructure, never campaign evidence.
CDN_RANGES = {
    "cloudflare": ["173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22", "141.101.64.0/18",
                   "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20", "197.234.240.0/22", "198.41.128.0/17",
                   "162.158.0.0/15", "104.16.0.0/13", "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
                   "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32", "2405:8100::/32",
                   "2a06:98c0::/29", "2c0f:f248::/32"],
    "fastly": ["151.101.0.0/16", "199.232.0.0/16", "146.75.0.0/17", "2a04:4e42::/32"],
    "meta": ["157.240.0.0/16", "31.13.24.0/21", "31.13.64.0/18", "129.134.0.0/16", "2a03:2880::/32"],
    "google": ["142.250.0.0/15", "172.217.0.0/16", "216.58.192.0/19", "172.253.0.0/16", "74.125.0.0/16",
               "64.233.160.0/19", "209.85.128.0/17", "2a00:1450::/32", "2607:f8b0::/32"],
    "akamai": ["23.32.0.0/11", "23.192.0.0/11", "2.16.0.0/13", "104.64.0.0/10"],
    "cloudfront": ["13.32.0.0/15", "13.224.0.0/14", "18.64.0.0/14", "52.84.0.0/15", "54.230.0.0/16",
                   "54.239.128.0/18", "99.84.0.0/16", "143.204.0.0/16", "205.251.192.0/19", "3.160.0.0/14"],
}
_CDN_NETS = [(name, ipaddress.ip_network(n)) for name, nets in CDN_RANGES.items() for n in nets]


def cdn_of(ip: str) -> str | None:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return None
    for name, net in _CDN_NETS:
        if a.version == net.version and a in net:
            return name
    return None


def _under(host: str, suffixes: Iterable[str]) -> bool:
    return any(host == s or host.endswith("." + s) for s in suffixes)


META_ID_PARAMS = {
    "campaign_id": "meta_campaign_id", "utm_campaign": "meta_campaign_id", "utm_id": "meta_campaign_id",
    "adset_id": "meta_adset_id", "utm_term": "meta_adset_id",
    "ad_id": "meta_ad_id", "utm_content": "meta_ad_id",
}
NAMING_PARAMS = ("ad_name", "adset_name", "campaign_name")
TDS_KEY_PARAMS = ("key", "campaign_key", "cmp", "_token")
PIXEL_PARAMS = ("pixel", "fbpx", "fb_pixel", "pixel_id", "px")


def url_observables(url: str, field_prefix: str, ctx: dict) -> list[ObsHit]:
    """Campaign-level ids and grammar leaked in an ad click URL."""
    hits: list[ObsHit] = []
    q = query_params(url)
    schema = param_schema(url)
    if schema:
        hits.append(ObsHit("url_param_schema", schema, f"{field_prefix}.query", context=ctx))
    for k, v in q.items():
        kl = k.lower()
        vv = unquote(v).strip()
        if kl in META_ID_PARAMS and re.fullmatch(r"12\d{15,17}", vv):
            hits.append(ObsHit(META_ID_PARAMS[kl], vv, f"{field_prefix}.param:{kl}", context=ctx))
        elif kl in NAMING_PARAMS and len(vv) >= 6 and not vv.isdigit():
            tpl = re.sub(r"\d+", "#", vv)
            hits.append(ObsHit("ad_naming", tpl, f"{field_prefix}.param:{kl}", display=vv, context=ctx))
        elif kl in TDS_KEY_PARAMS and re.fullmatch(r"[A-Za-z0-9]{16,64}", vv):
            hits.append(ObsHit("tds_key", vv.lower(), f"{field_prefix}.param:{kl}", context=ctx))
        elif kl in PIXEL_PARAMS and re.fullmatch(r"\d{14,17}", vv):
            hits.append(ObsHit("fb_pixel", vv, f"{field_prefix}.param:{kl}", context=ctx))
        elif kl == "utm_campaign" and vv and not vv.isdigit() and ("|" in vv or "[" in vv):
            # agency-style naming ('DS-CVE-ABO | [FLEX] [ID] …|1202…') leaks the operator's conventions
            tpl = re.sub(r"\d+", "#", vv.split("|")[0]).strip()
            if len(tpl) >= 4:
                hits.append(ObsHit("ad_naming", tpl, f"{field_prefix}.param:{kl}", display=vv, context=ctx))
    return hits


def domain_hits(host: str, field: str, ctx: dict) -> list[ObsHit]:
    if not host:
        return []
    if is_ip(host):
        return [ObsHit("ip", host, field, context=ctx)]
    etld1, sld, suffix = split_host(host)
    out = [ObsHit("fqdn", host, field, context=ctx, attrs={"etld1": etld1, "sld": sld, "tld": suffix})]
    out.append(ObsHit("etld1", etld1, field, context=ctx, attrs={"etld1": etld1, "sld": sld, "tld": suffix}))
    pat = domain_pattern(etld1)
    if pat:
        out.append(ObsHit("domain_pattern", pat, field, display=etld1, context=ctx))
    return out


VOWELS = set("aeiouy")


def domain_pattern(etld1: str) -> str | None:
    """Lexical grammar of the registrable domain: digits→N, letter runs → shape class.
    'qwertyuio.click' → 'wM.click', 'finance12-lorem34.sbs' → 'finance{N2}-wS{N2}.sbs'."""
    _, sld, suffix = split_host(etld1)
    if not sld or not suffix:
        return None
    parts = re.findall(r"[a-z]+|\d+|-", sld)
    out = []
    for p in parts:
        if p.isdigit():
            out.append(f"{{N{len(p)}}}")
        elif p == "-":
            out.append("-")
        elif len(p) <= 3 or p in ("finance", "invest", "crypto", "news", "info", "shop", "health", "bank"):
            out.append(p)
        else:  # length bucket, not exact length: kit A uses 8–9 letter pseudo-words on .click/.live
            out.append("wS" if len(p) <= 5 else "wM" if len(p) <= 10 else "wL")
    return "".join(out) + "." + suffix


_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
KIT_ID_PATTERNS = [
    # multi-tenant landing SaaS (kit A): /_cdn/production/landing-cdn/{TENANT}/{LANDER}/…
    (re.compile(rf"/landing-cdn/({_UUID})/({_UUID})/", re.I), ("kit_tenant", "lander_id")),
    (re.compile(rf"/landing-cdn/({_UUID})/", re.I), ("kit_tenant",)),
    # single-tenant lander folders: /l/{uuid}/ (p10), /lander/{uuid}_{ts}/ (p9)
    (re.compile(rf"/l/({_UUID})/", re.I), ("lander_id",)),
    (re.compile(rf"/landers?/({_UUID})(?:_\d+)?/", re.I), ("lander_id",)),
]


def kit_ids(path: str) -> list[tuple[str, str]]:
    for pat, types in KIT_ID_PATTERNS:
        m = pat.search(path)
        if m:
            return [(t, m.group(i + 1).lower()) for i, t in enumerate(types)]
    return []


def kit_ids_all(text: str) -> set[tuple[str, str]]:
    """Every tenant/lander id referenced anywhere in a document (saved pages keep absolute URLs in
    inline JS, srcset and data-* attributes even after the browser rewrote resource links)."""
    out: set[tuple[str, str]] = set()
    for pat, types in KIT_ID_PATTERNS:
        for m in pat.finditer(text):
            out.update((t, m.group(i + 1).lower()) for i, t in enumerate(types))
    return out


def extract_from_har(har: Har, landing_etld1s: set[str], cap_ref: str) -> tuple[list[ObsHit], list[RelationDraft], list[RequestDraft]]:
    hits: list[ObsHit] = []
    rels: list[RelationDraft] = []
    reqs: list[RequestDraft] = []
    seen_hosts: set[str] = set()
    for e in har.entries:
        if not e.url.startswith(("http://", "https://")):
            continue
        host = e.host
        h_etld1 = etld1_of(host) if host else ""
        third = h_etld1 not in landing_etld1s
        body_sha = sha256_bytes(e.body) if e.body else None
        path = urlsplit(e.url).path or "/"
        tpl = templatize_path(path)
        reqs.append(RequestDraft(
            seq=e.seq, started_at=e.started, method=e.method, url=e.url, host=host, path_template=tpl,
            status=e.status, mime=e.mime, resource_type=e.resource_type, server_ip=e.server_ip,
            body_sha256=body_sha, body_size=e.body_size, is_third_party=third,
            initiator=(e.initiator_url or e.initiator_type)))
        ctx = {"capture": cap_ref, "seq": e.seq, "url": e.url[:300]}

        # --- hosts and IPs ---
        if host and host not in seen_hosts:
            seen_hosts.add(host)
            if not third:
                hits += domain_hits(host, "har.request_host", ctx)
            else:
                noise = "platform_host" if _under(host, PLATFORM_HOSTS) else None
                hits.append(ObsHit("third_party_host", host, "har.request_host", context=ctx, noise_reason=noise))
                if not noise:
                    rels.append(RelationDraft(("etld1", next(iter(sorted(landing_etld1s)), "")), "loads_from",
                                              ("third_party_host", host), "har"))
        if e.server_ip and host:
            cdn = cdn_of(e.server_ip)
            if not third or not _under(host, PLATFORM_HOSTS):
                hits.append(ObsHit("ip", e.server_ip, "har.server_ip", context={**ctx, "host": host},
                                   noise_reason=f"cdn:{cdn}" if cdn else None, attrs={"cdn": cdn}))
                src_type = "fqdn" if not third else "third_party_host"
                rels.append(RelationDraft((src_type, host), "resolves_to", ("ip", e.server_ip), "har",
                                          {"at": e.started.isoformat() if e.started else None}))

        # --- CAPI / serverless gateways ---
        if host and CLOUD_GATEWAY.search(host):
            hits.append(ObsHit("capi_gateway", host, "har.request_host", display=f"{host}{path}", context=ctx))
            rels.append(RelationDraft(("etld1", next(iter(sorted(landing_etld1s)), "")), "posts_to",
                                      ("capi_gateway", host), "har"))

        # --- kit endpoints & lander paths (same-site only) ---
        if not third:
            if e.resource_type in ("xhr", "fetch", "ping", "beacon", "eventsource", "websocket", "other") \
                    or e.method == "POST" or "/api/" in path:
                if tpl not in ("/", "") and not tpl.endswith((".js", ".css", ".png", ".jpg", ".webp", ".svg", ".ico", ".woff2")):
                    hits.append(ObsHit("kit_endpoint", tpl, "har.same_site_api", display=path, context=ctx))
            for typ, val in kit_ids(path):
                hits.append(ObsHit(typ, val, "har.static_asset_path", display=path[:200], context=ctx))
            if e.resource_type in ("script", "stylesheet", "image", "font", "media"):
                d = tpl.rsplit("/", 1)[0]
                segs = [s for s in d.split("/") if s]
                if segs:
                    lp = "/" + "/".join(segs[:3]) + "/"
                    noise = "cdn_injected" if lp.startswith(("/cdn-cgi/", "/wp-includes/", "/wp-content/plugins/")) else None
                    hits.append(ObsHit("lander_path", lp, "har.static_asset_dir", context=ctx, noise_reason=noise))

        # --- tracking ids in URLs ---
        for typ, val in tracking_ids(e.url):
            hits.append(ObsHit(typ, val, "har.request_url", context=ctx))
        if e.post_data and len(e.post_data) < 200_000:
            for typ, val in tracking_ids(e.post_data):
                hits.append(ObsHit(typ, val, "har.post_body", context=ctx))

        # --- third-party accounts ---
        for name, pat in THIRD_PARTY_ACCOUNTS:
            m = pat.search(e.url)
            if m:
                hits.append(ObsHit("third_party_account", f"{name}:{m.group(1).lower()}", "har.request_url", context=ctx))

        # --- bodies: tracking ids inside JS/HTML, asset hashes, favicon ---
        if e.body:
            mime = (e.mime or "").lower()
            if ("javascript" in mime or "html" in mime or "json" in mime) and len(e.body) < 3_000_000 \
                    and not _under(host, PUBLIC_LIB_HOSTS):
                txt = e.body.decode("utf-8", errors="ignore")
                for typ, val in tracking_ids(txt):
                    hits.append(ObsHit(typ, val, "har.response_body", context=ctx))
            is_doc = e.resource_type in ("document", "frame")
            if not is_doc and (e.body_size or 0) >= 256 and e.status and e.status < 300 \
                    and e.resource_type in ("script", "stylesheet", "image", "font", "media", "fetch", "xhr", "other"):
                noise = "public_cdn_library" if _under(host, PUBLIC_LIB_HOSTS) else None
                if e.resource_type != "media":  # video segments are per-viewer chunks, not kit assets
                    hits.append(ObsHit("asset_sha256", body_sha, f"har.asset:{e.resource_type}",
                                       display=f"{host}{path}"[:200], context=ctx, noise_reason=noise))
            if path.lower().endswith("favicon.ico") or "icon" in (e.mime or "") and e.resource_type == "image" and "favicon" in path.lower():
                hits.append(ObsHit("favicon_mmh3", str(favicon_mmh3(e.body)), "har.favicon", context=ctx))
    return hits, rels, reqs


def extract_from_html(doc: ParsedHtml, field: str, ctx: dict, landing_etld1s: set[str]) -> list[ObsHit]:
    hits: list[ObsHit] = []
    for typ, val in tracking_ids(doc.inline_scripts + "\n" + "\n".join(doc.script_srcs)):
        hits.append(ObsHit(typ, val, f"{field}.script", context=ctx))
    for sig in doc.signatures:
        hits.append(ObsHit("html_signature", sig, f"{field}.signature", context=ctx))
    for url in doc.script_srcs + doc.resource_srcs + doc.iframes:
        if url.startswith(("http://", "https://")):
            host = host_of(url)
            if host and etld1_of(host) not in landing_etld1s:
                noise = "platform_host" if _under(host, PLATFORM_HOSTS) else None
                hits.append(ObsHit("third_party_host", host, f"{field}.resource", context={**ctx, "url": url[:300]},
                                   noise_reason=noise))
            for name, pat in THIRD_PARTY_ACCOUNTS:
                m = pat.search(url)
                if m:
                    hits.append(ObsHit("third_party_account", f"{name}:{m.group(1).lower()}", f"{field}.resource",
                                       context={**ctx, "url": url[:300]}))
            if host and CLOUD_GATEWAY.search(host):
                hits.append(ObsHit("capi_gateway", host, f"{field}.resource", context=ctx))
    for f in doc.forms:
        if f["fields"]:
            act = f["action"]
            act_tpl = templatize_path(urlsplit(act).path) if act.startswith("http") else act
            hits.append(ObsHit("form_schema", f"{f['method']} {act_tpl} [{','.join(f['fields'])}]", f"{field}.form", context=ctx))
    # gateway hosts / pixels only referenced inside inline JS strings
    for m in re.finditer(r"https?://([a-z0-9.-]+\.(?:on\.aws|run\.app|workers\.dev|vercel\.app))", doc.inline_scripts, re.I):
        hits.append(ObsHit("capi_gateway", m.group(1).lower(), f"{field}.inline_js", context=ctx))
    return hits


def tls_hits(tls: dict, host: str, ctx: dict, field: str) -> tuple[list[ObsHit], list[RelationDraft]]:
    """From a python-ssl getpeercert() dict (organizer dns_ssl.json format)."""
    hits, rels = [], []
    if not tls:
        return hits, rels
    issuer = {k: v for part in tls.get("issuer", []) for k, v in part}
    serial = (tls.get("serialNumber") or "").lstrip("0").lower()
    icn = issuer.get("commonName", "?")
    sans = [v for t, v in tls.get("subjectAltName", []) if t == "DNS"]
    if serial:
        cert_id = f"{icn.lower()}/{serial}"
        attrs = {"issuer_cn": icn, "issuer_org": issuer.get("organizationName"), "serial": serial,
                 "not_before": tls.get("notBefore"), "not_after": tls.get("notAfter"), "sans": sans,
                 "subject_cn": {k: v for part in tls.get("subject", []) for k, v in part}.get("commonName")}
        hits.append(ObsHit("cert", cert_id, field, context=ctx, attrs=attrs))
        nb = tls.get("notBefore")
        if nb:
            from datetime import datetime
            try:
                t = datetime.strptime(nb.replace("  ", " "), "%b %d %H:%M:%S %Y %Z")
                hits.append(ObsHit("cert_batch", f"{icn.lower()}|{t:%Y-%m-%dT%H}", field, context=ctx))
            except ValueError:
                pass
        for s in sans:
            rels.append(RelationDraft(("cert", cert_id), "cert_covers", ("fqdn", s.lstrip("*.").lower()), "tls"))
        if host:
            rels.append(RelationDraft(("fqdn", host), "has_cert", ("cert", cert_id), "tls"))
    return hits, rels
