"""Headless Playwright capture that writes the organizer archive-bundle layout (archive_info.json, network.har with
embedded bodies, html/rendered.html, screenshots/, dns_ssl.json, ...) so our captures and the organizer's go through
the same ingest path.

Runs standalone inside the sandbox container (`python -m trop.capture.worker <url> --out /out`) or locally.
Safety policy (enforced here): headless only; downloads refused; executables/archives aborted at the network layer;
no clicks, no typing, no form submission, never logs in; challenge pages are recorded as blocked, never solved;
optional egress proxy. The per-domain politeness budget is enforced by the caller (trop.capture.politeness).
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import re
import shutil
import socket
import ssl
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import Request, Response, async_playwright

from ._util import etld1_of, favicon_mmh3, host_of
from .profiles import BLOCKED_EXT, INIT_SCRIPT, PROFILES, Profile

TOOL = "trop-playwright"
CHALLENGE_RE = re.compile(r"just a moment|attention required|verify you are human|cf-chl|turnstile|h-captcha|g-recaptcha"
                          r"|checking your browser|ddos-guard", re.I)
META_REFRESH_RE = re.compile(r"<meta[^>]+http-equiv=[\"']?refresh[\"']?[^>]*content=[\"']?\s*\d+\s*;\s*url=([^\"'>\s]+)", re.I)
MAX_MEDIA = 60 * 1024 * 1024
MEDIA_EXT = (".mp4", ".webm", ".m3u8", ".ts", ".m4s", ".mov", ".mkv", ".mp3", ".aac")   # skipped in fast/local mode (memory)


def tls_info(host: str, port: int = 443, timeout: float = 8.0) -> dict:
    """Organizer-compatible dns_ssl.json: python ssl getpeercert() dict + DER sha256."""
    out: dict = {"hostname": host}
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        addrs = sorted({i[4][0] for i in infos})
        out["ip"], out["all_addresses"] = (addrs[0] if addrs else None), addrs
    except OSError as e:
        out["dns_error"] = str(e)
        return out
    try:
        import certifi
        cafile = certifi.where()
    except ImportError:
        cafile = None
    for verify in (True, False):
        ctx = ssl.create_default_context(cafile=cafile)
        if not verify:
            ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        try:
            with socket.create_connection((host, port), timeout=timeout) as s, ctx.wrap_socket(s, server_hostname=host) as t:
                der = t.getpeercert(binary_form=True)
                out["ssl"] = t.getpeercert() if verify else _decode_der(der)
                out["ssl_der_sha256"] = hashlib.sha256(der).hexdigest() if der else None
                out["ssl_verified"] = verify
                out["tls_version"] = t.version()
                return out
        except (ssl.SSLError, OSError) as e:
            out["ssl_error" if verify else "ssl_error_unverified"] = str(e)
    return out


def _decode_der(der: bytes | None) -> dict:
    """Same dict shape as getpeercert() for a certificate we could not verify (self-signed, expired,
    missing chain) — scam infrastructure is exactly where that happens."""
    if not der:
        return {}
    import os
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".pem")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(ssl.DER_cert_to_PEM_cert(der))
        return ssl._ssl._test_decode_cert(path)  # stdlib helper used by getpeercert itself
    except Exception:
        return {}
    finally:
        os.unlink(path)


class Recorder:
    """Collects navigation hops, console, media and the main-document source while the page runs."""

    def __init__(self) -> None:
        self.hops: list[dict] = []
        self.console: list[dict] = []
        self.media: list[dict] = []
        self.main_docs: list[Response] = []
        self.blocked: list[str] = []
        self._media_tasks: list[asyncio.Task] = []

    def on_response(self, resp: Response) -> None:
        req = resp.request
        if req.resource_type == "document" and req.frame == req.frame.page.main_frame:
            self.main_docs.append(resp)
            chain = []
            r: Request | None = req
            while r is not None:
                chain.append(r)
                r = r.redirected_from
            for i, rr in enumerate(reversed(chain)):
                kind = "entry" if not self.hops and i == 0 else ("http_redirect" if i > 0 else "js_navigation")
                if self.hops and self.hops[-1]["url"] == rr.url:
                    continue
                self.hops.append({"url": rr.url, "kind": kind, "at": datetime.now(timezone.utc).isoformat()})
            self.hops[-1]["status"] = resp.status
        ct = (resp.headers.get("content-type") or "").lower()
        if ct.startswith(("video/", "audio/")) or "mpegurl" in ct or req.url.split("?")[0].endswith((".m3u8", ".mp4", ".mp3")):
            self._media_tasks.append(asyncio.ensure_future(self._grab_media(resp, ct)))

    async def _grab_media(self, resp: Response, ct: str) -> None:
        item = {"url": resp.url, "content_type": ct, "status": resp.status}
        try:
            cl = int(resp.headers.get("content-length") or 0)
            if cl and cl > MAX_MEDIA:
                item["skipped"] = "too_large"
            else:
                body = await asyncio.wait_for(resp.body(), timeout=15)   # live streams never finish
                if len(body) <= MAX_MEDIA:
                    item["body"] = body
        except Exception as e:  # streamed / aborted responses
            item["error"] = type(e).__name__
        self.media.append(item)

    async def finish(self) -> None:
        if self._media_tasks:
            await asyncio.gather(*self._media_tasks, return_exceptions=True)


def _write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)


def _json(path: Path, obj) -> None:
    _write(path, json.dumps(obj, ensure_ascii=False, indent=2, default=str))


async def capture(url: str, out_root: Path, profile: Profile, *, referer: str | None = None, timeout_s: int = 45,
                  settle_s: float = 5.0, proxy: str | None = None, pdf: bool = True, zip_bundle: bool = True,
                  mhtml: bool = True, idle_ms: int = 15000, skip_media: bool = False) -> Path:
    started = datetime.now(timezone.utc)
    host = host_of(url)
    bundle = out_root / f"archive_{host}_{started:%Y%m%d_%H%M%S}_{profile.name}"
    tmp_har = bundle / "network.har"
    bundle.mkdir(parents=True, exist_ok=True)
    rec = Recorder()
    challenge = False
    status = None
    t0 = time.monotonic()
    # Playwright disables Chromium's own sandbox by default. On a host we turn it ON; inside our container the
    # container is the isolation layer (non-root, read-only rootfs, no capabilities) and Docker's seccomp
    # profile does not allow the namespaces Chromium's sandbox needs.
    in_container = Path("/.dockerenv").exists()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True, proxy={"server": proxy} if proxy else None, chromium_sandbox=not in_container,
            args=["--disable-blink-features=AutomationControlled", "--no-first-run", "--no-default-browser-check", "--disable-dev-shm-usage", "--disable-gpu", "--disable-extensions",
                  "--disable-background-networking", "--renderer-process-limit=1", "--js-flags=--max-old-space-size=384",
                  "--disable-features=Translate,OptimizationHints,MediaRouter", "--mute-audio"])
        ctx_kwargs = dict(
            viewport={"width": profile.viewport[0], "height": profile.viewport[1]},
            device_scale_factor=profile.device_scale_factor, is_mobile=profile.is_mobile, has_touch=profile.has_touch,
            locale=profile.locale, timezone_id=profile.timezone, accept_downloads=False, service_workers="block",
            extra_http_headers={"Accept-Language": profile.accept_language, **profile.extra_headers},
            record_har_path=str(tmp_har), record_har_content="embed", record_har_mode="full", ignore_https_errors=True)
        if profile.user_agent:
            ctx_kwargs["user_agent"] = profile.user_agent
        context = await browser.new_context(**ctx_kwargs)
        await context.add_init_script(INIT_SCRIPT)

        async def guard(route):
            u = route.request.url.lower().split("?")[0]
            if u.endswith(BLOCKED_EXT) or (skip_media and (route.request.resource_type == "media" or u.endswith(MEDIA_EXT))):
                rec.blocked.append(route.request.url)
                await route.abort()
            else:
                await route.continue_()
        await context.route("**/*", guard)

        page = await context.new_page()
        page.on("response", rec.on_response)
        page.on("console", lambda m: rec.console.append({"type": m.type, "text": m.text[:500]}))
        page.on("pageerror", lambda e: rec.console.append({"type": "pageerror", "text": str(e)[:500]}))
        page.on("download", lambda d: asyncio.ensure_future(d.cancel()))
        error = None
        try:
            try:
                resp = await page.goto(url, referer=referer or profile.referer, wait_until="domcontentloaded",
                                       timeout=timeout_s * 1000)
            except Exception as e:
                # dead/parked domains often have no working TLS: try plain http once, and say so
                if url.startswith("https://") and re.search(r"ERR_SSL|ERR_CERT|ERR_CONNECTION_(REFUSED|RESET|CLOSED)", str(e)):
                    rec.console.append({"type": "capture", "text": f"https failed ({str(e)[:120]}); retrying over http"})
                    error = f"https_failed: {str(e)[:200]}"
                    resp = await page.goto("http://" + url[len("https://"):], referer=referer or profile.referer,
                                           wait_until="domcontentloaded", timeout=timeout_s * 1000)
                else:
                    raise
            status = resp.status if resp else None
            try:
                await page.wait_for_load_state("networkidle", timeout=idle_ms)
            except Exception:
                pass
            for _ in range(4):  # lazy content, scroll-triggered scripts — no clicks
                await page.mouse.wheel(0, profile.viewport[1])
                await page.wait_for_timeout(600)
            await page.wait_for_timeout(int(settle_s * 1000))
        except Exception as e:
            error = f"{type(e).__name__}: {str(e)[:300]}"

        async def safe(coro, default):
            """Hostile pages throw from anywhere (sandboxed origins, navigations mid-read); a capture never dies on them."""
            try:
                return await coro
            except Exception as e:
                rec.console.append({"type": "capture", "text": f"{type(e).__name__}: {str(e)[:200]}"})
                return default

        final_url = page.url
        title = await safe(page.title(), None)
        rendered = await safe(page.content(), "")
        text = await safe(page.evaluate("() => document.body ? document.body.innerText : ''"), "")
        challenge = bool(CHALLENGE_RE.search((title or "") + " " + rendered[:20000]))
        meta = await safe(page.evaluate("""() => ({
            title: document.title,
            meta_tags: [...document.querySelectorAll('meta')].map(m => Object.fromEntries([...m.attributes].map(a => [a.name, a.value]))),
            links: [...document.querySelectorAll('a[href]')].slice(0, 500).map(a => ({href: a.href, text: (a.innerText||'').trim().slice(0, 200)})),
            scripts: [...document.querySelectorAll('script')].map(s => s.src || null),
            images: [...document.querySelectorAll('img')].slice(0, 300).map(i => i.currentSrc || i.src),
            icons: [...document.querySelectorAll('link[rel*=icon]')].map(l => l.href),
            iframes: [...document.querySelectorAll('iframe')].map(f => f.src),
        })"""), {})
        forms = await safe(page.evaluate("""() => [...document.forms].map(f => ({
            action: f.action, method: (f.method || 'get').toLowerCase(),
            fields: [...f.elements].filter(e => e.name || e.id).map(e => ({name: e.name || e.id, type: e.type || e.tagName.toLowerCase()}))
        }))"""), [])
        storage = await safe(page.evaluate("""() => {
            const dump = get => { try { const s = get(); return Object.fromEntries(Object.keys(s).map(k => [k, s.getItem(k)])); } catch (e) { return {}; } };
            return {local: dump(() => window.localStorage), session: dump(() => window.sessionStorage)};
        }"""), {})
        # meta-refresh tagging: a later main-frame navigation whose predecessor document carried <meta refresh>
        for prev_resp, next_resp in zip(rec.main_docs, rec.main_docs[1:]):
            try:
                body = (await prev_resp.body()).decode("utf-8", errors="ignore")
            except Exception:
                continue
            if META_REFRESH_RE.search(body):
                for h in rec.hops:
                    if h["url"] == next_resp.url and h["kind"] == "js_navigation":
                        h["kind"] = "meta_refresh"
        # client-side hop that did not produce a new main-frame response (history API / SPA routing)
        if rec.hops and rec.hops[-1]["url"] != final_url:
            rec.hops.append({"url": final_url, "kind": "js_navigation", "at": datetime.now(timezone.utc).isoformat()})

        source_html = None
        if rec.main_docs:
            try:
                source_html = await rec.main_docs[-1].body()
            except Exception:
                source_html = None
        _write(bundle / "html" / "rendered.html", rendered)
        if source_html is not None:
            _write(bundle / "html" / "source.html", source_html)
        _write(bundle / "page_text.txt", text or "")
        await safe(page.screenshot(path=str(bundle / "screenshots" / "viewport.png")), None)
        await safe(page.screenshot(path=str(bundle / "screenshots" / "full_page.png"), full_page=True), None)
        try:
            if not mhtml:
                raise RuntimeError("mhtml skipped (fast mode)")
            cdp = await context.new_cdp_session(page)
            snap = await cdp.send("Page.captureSnapshot", {"format": "mhtml"})
            _write(bundle / "page.mhtml", snap["data"])
        except Exception as e:
            rec.console.append({"type": "capture", "text": f"mhtml failed: {e}"})
        if pdf:
            try:
                await page.pdf(path=str(bundle / "page.pdf"), print_background=True)
            except Exception as e:
                rec.console.append({"type": "capture", "text": f"pdf failed: {e}"})

        # favicon via the same browser context (same UA / cookies / referer)
        fav_urls = [u for u in (meta.get("icons") or []) if u] + [f"{final_url.split('/', 3)[0]}//{host_of(final_url)}/favicon.ico"]
        for fu in fav_urls[:3]:
            try:
                r = await context.request.get(fu, timeout=10000)
                if r.ok:
                    body = await r.body()
                    if body and len(body) < 2_000_000:
                        ext = Path(fu.split("?")[0]).suffix.lower() or ".ico"
                        _write(bundle / f"favicon{ext if len(ext) <= 5 else '.ico'}", body)
                        _json(bundle / "favicon.json", {"url": fu, "mmh3": favicon_mmh3(body),
                                                        "sha256": hashlib.sha256(body).hexdigest(), "size": len(body)})
                        break
            except Exception:
                continue
        cookies = await context.cookies()
        try:
            await asyncio.wait_for(rec.finish(), timeout=20)
        except asyncio.TimeoutError:
            rec.console.append({"type": "capture", "text": "media drain timed out"})
        await context.close()  # flushes network.har
        await browser.close()

    final_host = host_of(final_url) if final_url.startswith("http") else host
    dns_ssl = await asyncio.to_thread(tls_info, final_host)   # DNS + TLS even when the page itself failed
    for h in rec.hops:
        if host_of(h["url"]) == final_host and dns_ssl.get("ip"):
            h["ip"] = dns_ssl["ip"]

    media_manifest = []
    for i, m in enumerate(rec.media):
        entry = {k: v for k, v in m.items() if k != "body"}
        if m.get("body"):
            ext = ".m3u8" if "mpegurl" in m["content_type"] else (Path(m["url"].split("?")[0]).suffix or ".bin")[:6]
            name = f"media/{i:03d}{ext}"
            _write(bundle / name, m["body"])
            entry.update(file=name, sha256=hashlib.sha256(m["body"]).hexdigest(), size=len(m["body"]))
        media_manifest.append(entry)
    if media_manifest:
        _json(bundle / "media" / "manifest.json", {"items": media_manifest,
              "note": "HLS playlists are saved as text; segments are fetched by the media worker (ffmpeg) under the same profile"})

    finished = datetime.now(timezone.utc)
    dead = final_url.startswith(("chrome-error://", "about:blank")) or status is None
    page_role = "blocked" if challenge else ("error" if dead or (status and status >= 500) else None)
    _json(bundle / "archive_info.json", {
        "url": url, "timestamp_utc": started.isoformat(), "title": title, "user_agent": profile.user_agent or "default",
        # RED PILL extensions (ignored by organizer tooling)
        "tool": TOOL, "tool_version": "0.1", "profile": profile.name, "referer": referer or profile.referer,
        "final_url": final_url, "status": status, "duration_ms": int((time.monotonic() - t0) * 1000),
        "finished_utc": finished.isoformat(), "challenge_detected": challenge, "page_role_hint": page_role,
        "blocked_requests": rec.blocked[:50], "error": error, "viewport": list(profile.viewport),
        "locale": profile.locale, "timezone": profile.timezone})
    _json(bundle / "dns_ssl.json", dns_ssl)
    _json(bundle / "metadata.json", {k: meta.get(k) for k in ("title", "meta_tags", "links", "scripts", "images")})
    _json(bundle / "storage" / "cookies.json", cookies)
    _json(bundle / "storage" / "localStorage.json", storage.get("local", {}))
    _json(bundle / "storage" / "sessionStorage.json", storage.get("session", {}))
    _json(bundle / "redirects.json", [{k: v for k, v in h.items() if k != "html"} for h in rec.hops])
    _json(bundle / "forms.json", forms)
    _json(bundle / "outlinks.json", sorted({l["href"] for l in meta.get("links") or []}))
    _json(bundle / "console.json", rec.console[:500])

    manifest = {}
    for p in sorted(bundle.rglob("*")):
        if p.is_file() and p.name != "sha256.json":
            manifest[p.relative_to(bundle).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    _json(bundle / "sha256.json", manifest)
    if zip_bundle:
        zpath = bundle.parent / (bundle.name + ".zip")   # not with_suffix(): domain dots look like suffixes
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(bundle.rglob("*")):
                if p.is_file():
                    z.write(p, f"{bundle.name}/{p.relative_to(bundle).as_posix()}")
        zpath.with_name(zpath.name + ".sha256").write_text(hashlib.sha256(zpath.read_bytes()).hexdigest())
    return bundle


async def run(urls: list[str], out: Path, profiles: list[str], referer: str | None = None, proxy: str | None = None,
              concurrency: int = 1, gap_s: float = 20.0, fast: bool = False, nav_timeout: int = 45, hard_timeout: int = 240) -> list[Path]:
    """Parallel across different sites (<= concurrency), one at a time per eTLD+1 with gap_s between profiles."""
    from collections import defaultdict
    sem = asyncio.Semaphore(max(1, concurrency))
    site_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
    done: list[Path] = []

    async def one_site(url: str) -> None:
        site = etld1_of(host_of(url))
        async with site_locks[site]:
            for i, pname in enumerate(profiles):
                if i:
                    await asyncio.sleep(gap_s)
                async with sem:
                    try:
                        b = await asyncio.wait_for(
                            capture(url, out, PROFILES[pname], referer=referer, proxy=proxy,
                                    timeout_s=nav_timeout,
                                    **({"pdf": False, "mhtml": False, "zip_bundle": False, "settle_s": 2.0, "idle_ms": 6000, "skip_media": True} if fast else {})),
                            timeout=hard_timeout)
                    except Exception as e:  # one hostile page must not kill the batch
                        print(f"  {pname:<20} FAILED {url[:80]}: {type(e).__name__}: {str(e)[:150]}", flush=True)
                        continue
                info = json.loads((b / "archive_info.json").read_text(encoding="utf-8"))
                print(f"  {pname:<20} {info['status']} {site:<28} final={info['final_url'][:60]} "
                      f"title={str(info['title'])[:50]!r} challenge={info['challenge_detected']}", flush=True)
                done.append(b)

    await asyncio.gather(*(one_site(u) for u in urls))
    return done


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="trop.capture.worker")
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--file", type=Path, help="one URL per line ('#' comments allowed)")
    ap.add_argument("--out", type=Path, default=Path("/out"))
    ap.add_argument("--profile", action="append", choices=sorted(PROFILES), help="repeatable; default fb_inapp_android_pl")
    ap.add_argument("--referer", default=None)
    ap.add_argument("--proxy", default=None)
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--gap", type=float, default=20.0, help="seconds between two profiles on the same site")
    ap.add_argument("--fast", action="store_true", help="no PDF/MHTML, shorter settle")
    ap.add_argument("--nav-timeout", type=int, default=45, help="seconds for the navigation itself")
    ap.add_argument("--hard-timeout", type=int, default=240, help="hard cap per capture (seconds)")
    args = ap.parse_args(argv)
    urls = list(args.urls)
    if args.file:
        urls += [l.split()[0] for l in args.file.read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.lstrip().startswith("#")]
    if not urls:
        ap.error("no URLs")
    bundles = asyncio.run(run(urls, args.out, args.profile or ["fb_inapp_android_pl"], args.referer, args.proxy,
                              args.concurrency, args.gap, args.fast, args.nav_timeout, args.hard_timeout))
    print(json.dumps({"bundles": [b.name for b in bundles]}))
    return 0 if bundles else 1


if __name__ == "__main__":
    sys.exit(main())


def capture_url(url: str, out_dir: str | None = None, **kw):
    """Sync entry point used by trop.ingest.pipeline (`capture_url(url, out_dir=...)` -> bundle dir path)."""
    from pathlib import Path as _P

    from .cli import capture_url as _cap
    kw.setdefault("fast", True)
    r = _cap(url, out=_P(out_dir) if out_dir else None, **kw)
    return r.get("bundle")
