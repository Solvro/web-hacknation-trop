"""Meta ad snapshot -> creative screenshot + CTA landing link (the Ad Library API never returns where an ad leads).

Opens facebook.com/ads/archive/render_ad/?id=<id>&access_token=<token> headless, one ad at a time (Meta's terms allow
snapshot use for analysis of individual ads), reads the outbound links (l.facebook.com/l.php?u=<landing> or direct).
The token exists only in memory: no HAR is recorded and every stored URL is redacted. Only facebook.com is contacted;
the landing itself is captured afterwards by the sandboxed capture worker.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from trop.capture._util import host_of
from trop.config import settings

from .meta import redact

RENDER = "https://www.facebook.com/ads/archive/render_ad/"
FB_HOSTS = ("facebook.com", "fb.com", "fb.me", "instagram.com", "messenger.com", "fbcdn.net", "whatsapp.com", "facebook.net")


def landing_from_href(href: str) -> str | None:
    if not href or not href.startswith("http"):
        return None
    host = host_of(href)
    if host.endswith(("l.facebook.com", "lm.facebook.com", "l.instagram.com")):
        u = parse_qs(urlsplit(href).query).get("u", [None])[0]
        return unquote(u) if u else None
    if any(host == h or host.endswith("." + h) for h in FB_HOSTS):
        return None
    return href


async def _render(ad_ids: list[str], token: str, shots_dir: Path, gap_s: float) -> dict[str, dict]:
    from playwright.async_api import async_playwright
    out: dict[str, dict] = {}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, chromium_sandbox=True)
        ctx = await browser.new_context(locale="pl-PL", viewport={"width": 600, "height": 1000})
        for ad_id in ad_ids:
            page = await ctx.new_page()
            rec: dict = {"rendered_at": datetime.now(timezone.utc).isoformat(), "links": []}
            try:
                await page.goto(f"{RENDER}?id={ad_id}&access_token={token}", wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2500)
                hrefs = await page.evaluate("() => [...document.querySelectorAll('a[href]')].map(a => a.href)")
                rec["links"] = list(dict.fromkeys(redact(x) for x in (landing_from_href(h) for h in hrefs) if x))[:10]
                rec["text"] = (await page.evaluate("() => document.body ? document.body.innerText : ''"))[:2000]
                shot = shots_dir / f"{ad_id}.png"
                await page.screenshot(path=str(shot), full_page=True)
                rec["screenshot"] = str(shot)
            except Exception as e:  # deleted ads, rate limits, layout changes
                rec["error"] = redact(f"{type(e).__name__}: {str(e)[:200]}")
            finally:
                await page.close()
            out[ad_id] = rec
            await asyncio.sleep(gap_s)
        await browser.close()
    return out


def render_snapshots(ad_ids: list[str], shots_dir: Path, gap_s: float = 1.5) -> dict[str, dict]:
    """-> {ad_id: {links, text, screenshot, error?}}. Empty when offline / no token."""
    from trop.enrich import cache
    token = settings.meta_access_token
    if not ad_ids or not token or cache.is_offline():
        return {}
    shots_dir.mkdir(parents=True, exist_ok=True)
    return asyncio.run(_render(ad_ids, token, shots_dir, gap_s))
