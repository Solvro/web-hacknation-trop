"""Render a SAVED landing page (Chrome "save complete" .html + _files/, a capture bundle's html/rendered.html, a dom.html)
to a full-page screenshot plus bounding boxes, with ALL network blocked.

Safety: the page is opened from file:// with JavaScript disabled, every request except file:// / data: / blob: is aborted
by a route handler, the browser resolves no hostnames (`--host-resolver-rules`) and the context is offline: nothing ever
reaches a scam host. The browser runs in a child process (own memory, hard timeout, safe to call from an asyncio worker).

    render_saved(html_or_dir, out_png, width=1280, max_height=4000) -> {png, w, h, boxes, markers, ...}
    render_corpus()                          -> data/artifacts/rendered/<incident_id>.webp + .boxes.json
    ensure_landing_screenshot(src, inc_id)   -> hook for the worker (never raises, <= 8 s)
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from ._boxes import BOXES_JS, MARKERS

ALLOWED_SCHEMES = ("file:", "data:", "blob:", "about:")
HTML_EXT = (".html", ".htm")
BACKEND = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------------------------- locating the HTML
def find_html(src: str | Path) -> Path | None:
    """File -> itself; directory -> the saved page (sibling *_files dir wins), then bundle html/rendered.html, dom.html,
    then any .html below it that is not inside a *_files resource folder."""
    p = Path(src)
    if p.is_file():
        return p if p.suffix.lower() in HTML_EXT else None
    if not p.is_dir():
        return None
    top = sorted(x for x in p.iterdir() if x.is_file() and x.suffix.lower() in HTML_EXT)
    saved = [x for x in top if (x.parent / (x.stem + "_files")).is_dir()]
    if saved or top:
        return (saved or top)[0]
    for name in ("html/rendered.html", "rendered.html", "dom.html", "html/source.html"):
        if (p / name).is_file():
            return p / name
    for b in sorted(p.glob("archive_*")):
        if (b / "html" / "rendered.html").is_file():
            return b / "html" / "rendered.html"
    cands = [x for x in sorted(p.rglob("*")) if x.suffix.lower() in HTML_EXT and x.is_file()
             and not any(part.endswith("_files") for part in x.relative_to(p).parts[:-1])]
    for x in cands:
        if (x.parent / (x.stem + "_files")).is_dir():
            return x
    return cands[0] if cands else None


def _repair_resources(html: Path, tmpdir: Path) -> Path:
    """Browser "save complete" folders often lose their encoding (zip names in cp437: `napaÿå..._files`) so the HTML's
    `<name>_files/x` references no longer resolve. If the referenced folder is missing and exactly one `*_files` sibling
    exists, write a patched copy (with <base> -> the original folder) that points at the real folder."""
    import re
    from urllib.parse import quote
    dirs = [d for d in html.parent.iterdir() if d.is_dir() and d.name.endswith("_files")]
    if len(dirs) != 1:
        return html
    text = html.read_text(encoding="utf-8", errors="replace")
    real = dirs[0].name
    if (real + "/") in text or quote(real) in text:
        return html
    pat = re.compile(r"""(["'(=]\s*)(?:\./)?[^"'()<>]*?_files/""")
    new, n = pat.subn(lambda m: m.group(1) + quote(real) + "/", text)
    if not n:
        return html
    base = f'<base href="{html.parent.resolve().as_uri()}/">'
    new = re.sub(r"(<head[^>]*>)", lambda m: m.group(1) + base, new, count=1, flags=re.I) if re.search(r"<head", new, re.I) else base + new
    out = tmpdir / "patched.html"
    out.write_text(new, encoding="utf-8")
    return out


# --------------------------------------------------------------------------------------------- browser side
async def _render_one(browser, html: Path, png: Path, width: int, max_height: int, nav_timeout_ms: int) -> dict[str, Any]:
    ctx = await browser.new_context(viewport={"width": width, "height": 900}, java_script_enabled=False, offline=True,
                                    service_workers="block", locale="pl-PL", accept_downloads=False)
    blocked = {"n": 0}

    async def guard(route):
        u = route.request.url.lower()
        if u.startswith(ALLOWED_SCHEMES):
            await route.continue_()
        else:
            blocked["n"] += 1
            await route.abort()
    await ctx.route("**/*", guard)
    page = await ctx.new_page()
    fixdir = tempfile.TemporaryDirectory(prefix="trop-fix-")
    try:
        await page.goto(_repair_resources(html, Path(fixdir.name)).resolve().as_uri(), wait_until="load", timeout=nav_timeout_ms)
        await page.wait_for_timeout(150)
        info = await page.evaluate(BOXES_JS, MARKERS)
        full_h = int(info["page"]["h"])
        clip_h = min(full_h or 900, max_height)
        png.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(png), full_page=True, clip={"x": 0, "y": 0, "width": width, "height": clip_h}, type="png")
        boxes = []
        for b in info["boxes"]:
            if b["y"] >= clip_h or b["x"] >= width:
                continue
            b["w"], b["h"] = min(b["w"], width - b["x"]), min(b["h"], clip_h - b["y"])
            boxes.append(b)
        return {"w": width, "h": clip_h, "page_h": full_h, "truncated": full_h > clip_h, "boxes": boxes,
                "markers": info["markers"], "inline_markers": info["inline_markers"], "blocked_requests": blocked["n"]}
    finally:
        await ctx.close()
        fixdir.cleanup()


async def _run_jobs(jobs: list[dict], width: int, max_height: int, nav_timeout_ms: int) -> list[dict]:
    from playwright.async_api import async_playwright
    out: list[dict] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True, chromium_sandbox=not Path("/.dockerenv").exists(),
            args=["--disable-dev-shm-usage", "--disable-gpu", "--disable-extensions", "--disable-background-networking",
                  "--host-resolver-rules=MAP * ~NOTFOUND", "--proxy-server=127.0.0.1:9", "--mute-audio"])
        try:
            for j in jobs:
                t0 = time.monotonic()
                try:
                    r = await asyncio.wait_for(_render_one(browser, Path(j["html"]), Path(j["png"]), width, max_height, nav_timeout_ms),
                                               timeout=nav_timeout_ms / 1000 + 6)
                    r.update(ok=True, png=j["png"], html=j["html"], id=j.get("id"))
                except Exception as e:                       # one hostile/broken page never kills the batch
                    r = {"ok": False, "id": j.get("id"), "html": j["html"], "error": f"{type(e).__name__}: {str(e)[:160]}"}
                r["seconds"] = round(time.monotonic() - t0, 2)
                out.append(r)
        finally:
            await browser.close()
    return out


def _main() -> int:                                          # python -m trop.capture.render <jobs.json> <result.json> ...
    jobs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    width, max_h, nav_ms = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
    res = asyncio.run(_run_jobs(jobs, width, max_h, nav_ms))
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    return 0


def _spawn(jobs: list[dict], width: int, max_height: int, nav_timeout_s: float, hard_s: float) -> list[dict]:
    """Run the jobs in a child process (own process group, killed at `hard_s`)."""
    with tempfile.TemporaryDirectory(prefix="trop-render-") as td:
        jf, rf = Path(td) / "jobs.json", Path(td) / "result.json"
        jf.write_text(json.dumps(jobs), encoding="utf-8")
        p = subprocess.Popen([sys.executable, "-m", "trop.capture.render", str(jf), str(rf), str(width), str(max_height),
                              str(int(nav_timeout_s * 1000))], cwd=BACKEND, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            p.wait(timeout=hard_s)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
            return [{"ok": False, "html": j["html"], "id": j.get("id"), "error": f"timeout after {hard_s:.0f}s"} for j in jobs]
        if not rf.is_file():
            return [{"ok": False, "html": j["html"], "id": j.get("id"), "error": f"renderer exited {p.returncode}"} for j in jobs]
        return json.loads(rf.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------------- public API
def render_saved(html_path_or_dir: str | Path, out_png: str | Path, *, width: int = 1280, max_height: int = 4000,
                 timeout_s: float = 8.0) -> dict[str, Any]:
    """Full-page screenshot of a saved page, network blocked. -> {png, w, h, boxes, markers, ...} or {ok: False, error}.
    Box: {kind, selector, x, y, w, h, text?}, px of the PNG (device scale 1)."""
    html = find_html(html_path_or_dir)
    if html is None:
        return {"ok": False, "error": f"no saved HTML found in {html_path_or_dir}"}
    r = _spawn([{"html": str(html), "png": str(out_png)}], width, max_height, max(2.0, timeout_s - 3.0), timeout_s + 4.0)[0]
    return r


def _to_webp(png: Path, webp: Path, max_w: int = 1200, quality: int = 75) -> tuple[int, int, float]:
    from PIL import Image
    with Image.open(png) as im:
        im = im.convert("RGB")
        scale = min(1.0, max_w / im.width)
        if scale < 1:
            im = im.resize((max_w, max(1, round(im.height * scale))), Image.LANCZOS)
        webp.parent.mkdir(parents=True, exist_ok=True)
        im.save(webp, "WEBP", quality=quality, method=4)
        return im.width, im.height, scale


def _write_boxes(path: Path, r: dict, w: int, h: int, scale: float, html: str | None) -> None:
    boxes = [{**b, "x": round(b["x"] * scale), "y": round(b["y"] * scale), "w": max(1, round(b["w"] * scale)), "h": max(1, round(b["h"] * scale))}
             for b in r.get("boxes", [])]
    path.write_text(json.dumps({"image": {"w": w, "h": h}, "scale_from_page": round(scale, 4), "page_h": r.get("page_h"),
                                "truncated": r.get("truncated"), "boxes": boxes, "markers": r.get("markers", []),
                                "inline_markers": r.get("inline_markers", []), "source": html}, ensure_ascii=False, indent=1), encoding="utf-8")


def artifacts_dir() -> Path:
    from trop.config import settings
    return Path(settings.data_dir) / "artifacts" / "rendered"


def ensure_landing_screenshot(src: str | Path, incident_id: str, out_dir: str | Path | None = None, *, force: bool = False,
                              timeout_s: float = 8.0) -> dict[str, Any] | None:
    """Worker hook: for an upload that has HTML but no landing screenshot. Writes <out_dir>/<id>.webp + <id>.boxes.json
    (default data/artifacts/rendered). Idempotent, <= ~8 s, never raises; returns {webp, boxes, w, h} or None."""
    try:
        out = Path(out_dir) if out_dir else artifacts_dir()
        webp, bj = out / f"{incident_id}.webp", out / f"{incident_id}.boxes.json"
        if webp.is_file() and bj.is_file() and not force:
            d = json.loads(bj.read_text(encoding="utf-8"))
            return {"webp": str(webp), "boxes": str(bj), "w": d["image"]["w"], "h": d["image"]["h"], "cached": True}
        with tempfile.TemporaryDirectory(prefix="trop-shot-") as td:
            png = Path(td) / "page.png"
            r = render_saved(src, png, timeout_s=timeout_s)
            if not r.get("ok") or not png.is_file():
                return None
            w, h, scale = _to_webp(png, webp)
            _write_boxes(bj, r, w, h, scale, r.get("html"))
        return {"webp": str(webp), "boxes": str(bj), "w": w, "h": h, "cached": False}
    except Exception:
        return None


def render_for_upload(src: str | Path, *, timeout_s: float = 8.0) -> dict[str, Any] | None:
    """Worker hook: upload dir/file that has saved HTML -> {png: bytes-path, boxes: [...], w, h} (PNG in a temp file the
    caller moves/deletes) or None (no HTML / render failed). Never raises."""
    try:
        td = tempfile.mkdtemp(prefix="trop-up-")
        png = Path(td) / "landing.png"
        r = render_saved(src, png, timeout_s=timeout_s)
        if not r.get("ok") or not png.is_file():
            return None
        return {"png": str(png), "boxes": r["boxes"], "w": r["w"], "h": r["h"], "markers": r.get("markers", [])}
    except Exception:
        return None


def corpus_items() -> list[tuple[str, Path]]:
    """(incident_id, source dir): data/raw/sample_v1/p<N> -> p<N>, DANE .../do_udostępnienia/<N> -> d<N> (ids as in the engine corpus)."""
    from trop.config import settings
    raw = Path(settings.data_dir) / "raw"
    items: list[tuple[str, Path]] = []
    for base, prefix, pat in ((raw / "sample_v1", "", "p*"), (raw / "dane" / "unpacked" / "do_udostępnienia", "d", "*")):
        for d in base.glob(pat) if base.is_dir() else []:
            n = d.name[1:] if prefix == "" else d.name
            if d.is_dir() and n.isdigit():
                items.append(((d.name if prefix == "" else f"d{n}"), d))
    return sorted(items, key=lambda t: (t[0][0], int(t[0][1:])))


def render_corpus(out_dir: str | Path | None = None, ids: list[str] | None = None, width: int = 1280, max_height: int = 4000,
                  progress=print) -> dict[str, Any]:
    out = Path(out_dir) if out_dir else artifacts_dir()
    out.mkdir(parents=True, exist_ok=True)
    items = [(i, d) for i, d in corpus_items() if not ids or i in ids]
    jobs, missing = [], []
    tmp = Path(tempfile.mkdtemp(prefix="trop-corpus-"))
    for iid, d in items:
        h = find_html(d)
        if h is None:
            missing.append(iid)
            continue
        jobs.append({"id": iid, "html": str(h), "png": str(tmp / f"{iid}.png")})
    progress(f"rendering {len(jobs)} incidents ({len(missing)} without saved HTML: {missing})")
    res = _spawn(jobs, width, max_height, 15.0, 30.0 * len(jobs) + 30)
    summary = {"rendered": 0, "failed": [], "missing_html": missing, "bytes": 0, "items": []}
    for r in res:
        iid = r["id"]
        if not r.get("ok"):
            summary["failed"].append({"id": iid, "error": r.get("error")})
            continue
        webp, bj = out / f"{iid}.webp", out / f"{iid}.boxes.json"
        w, h, scale = _to_webp(Path(r["png"]), webp)
        _write_boxes(bj, r, w, h, scale, r["html"])
        Path(r["png"]).unlink(missing_ok=True)
        sz = webp.stat().st_size
        summary["rendered"] += 1
        summary["bytes"] += sz + bj.stat().st_size
        summary["items"].append({"id": iid, "w": w, "h": h, "webp_kb": round(sz / 1024), "boxes": len(r["boxes"]),
                                 "blocked_requests": r["blocked_requests"], "seconds": r["seconds"]})
        progress(f"  {iid:<6} {w}x{h} {sz / 1024:6.0f} KB  boxes={len(r['boxes']):<3} blocked={r['blocked_requests']} {r['seconds']}s")
    try:
        tmp.rmdir()
    except OSError:
        pass
    return summary


if __name__ == "__main__":
    sys.exit(_main())
