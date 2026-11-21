"""Meta ad snapshot → landing URL (the Ad Library API never returns where an ad leads).

    python -m scrapers.hunter.meta_snapshot --limit 30            # pick ads, render snapshots, store link_url
    python -m scrapers.hunter.meta_snapshot --limit 30 --targets data/captures/meta_run/targets.txt

For each selected ad we open facebook.com/ads/archive/render_ad/?id=<id>&access_token=<token> headless (one ad at a
time — Meta's terms allow snapshot use "for analysis of individual ads"), read the outbound links
(l.facebook.com/l.php?u=<landing> or direct), and store:
  ads.link_url (first non-Facebook link) · ads.raw.snapshot {links, caption, rendered_at} · the rendered creative
  as an artifact (role ad_creative_image) · observables etld1/fqdn/url_param_schema/meta ids from the link.
The token only exists in memory: no HAR is recorded and every stored URL is redacted.
The landing itself is captured afterwards by the sandboxed capture worker (scrapers.capture) and attached to the ad.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from psycopg.types.json import Jsonb

from ..ingest.extract import domain_hits, url_observables
from ..ingest.model import ArtifactDraft
from ..store import artifacts
from ..store.db import Loader, connect
from ..util.urls import host_of
from .meta_adlib import redact_token

RENDER = "https://www.facebook.com/ads/archive/render_ad/"
FB_HOSTS = ("facebook.com", "fb.com", "fb.me", "instagram.com", "messenger.com", "fbcdn.net", "whatsapp.com")

SELECT_SQL = """
WITH grp AS (   -- coordinated texts: the same clickbait template on many pages first
  SELECT io.incident_id, max(o.df_incidents) AS template_df
  FROM incident_observables io JOIN observables o ON o.id = io.observable_id AND o.type = 'clickbait_template'
  GROUP BY io.incident_id)
SELECT DISTINCT ON (coalesce(tpl.value, a.library_id)) i.id, a.id, a.library_id, coalesce(g.template_df, 0) AS df
FROM ads a JOIN incidents i ON i.ad_id = a.id
LEFT JOIN grp g ON g.incident_id = i.id
LEFT JOIN LATERAL (SELECT o.value FROM incident_observables io JOIN observables o ON o.id = io.observable_id
                   WHERE io.incident_id = i.id AND o.type = 'clickbait_template' LIMIT 1) tpl ON true
WHERE a.platform = 'meta' AND a.library_id IS NOT NULL AND a.link_url IS NULL
  AND NOT (a.raw ? 'snapshot')
ORDER BY coalesce(tpl.value, a.library_id), a.delivery_start DESC NULLS LAST
"""


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


async def render(ad_ids: list[str], token: str, shots_dir: Path) -> dict[str, dict]:
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
                landings = [l for l in (landing_from_href(h) for h in hrefs) if l]
                rec["links"] = list(dict.fromkeys(redact_token(l) for l in landings))[:10]
                rec["text"] = (await page.evaluate("() => document.body ? document.body.innerText : ''"))[:2000]
                shot = shots_dir / f"{ad_id}.png"
                await page.screenshot(path=str(shot), full_page=True)
                rec["screenshot"] = str(shot)
            except Exception as e:  # deleted ads, rate limits, layout changes
                rec["error"] = redact_token(f"{type(e).__name__}: {str(e)[:200]}")
            finally:
                await page.close()
            out[ad_id] = rec
            await asyncio.sleep(1.5)   # gentle: one ad at a time
        await browser.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--targets", type=Path, default=None, help="write landing URLs here for scrapers.capture --file")
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    token = os.environ.get("META_ACCESS_TOKEN")
    if not token:
        print("META_ACCESS_TOKEN not set", file=sys.stderr)
        return 2
    shots_dir = Path("data/captures/meta_snapshots")
    shots_dir.mkdir(parents=True, exist_ok=True)
    with connect(args.db) as conn:
        loader = Loader(conn, artifacts.from_env(), sensitivity="internal")
        picks = conn.execute(SELECT_SQL).fetchall()
        picks.sort(key=lambda r: -r[3])                       # most coordinated templates first
        picks = picks[: args.limit]
        run_id = loader.start_run("meta_adlib_api", trigger="manual", params={"cmd": "snapshots", "n": len(picks)})
        conn.commit()
        rendered = asyncio.run(render([r[2] for r in picks], token, shots_dir))
        targets, n_links = [], 0
        for iid, ad_pk, lib, _df in picks:
            rec = rendered.get(lib, {})
            link = rec["links"][0] if rec.get("links") else None
            conn.execute("UPDATE ads SET link_url = coalesce(%s, link_url), raw = raw || %s WHERE id = %s",
                         (link, Jsonb({"snapshot": {k: v for k, v in rec.items() if k != "screenshot"}}), ad_pk))
            if rec.get("screenshot") and Path(rec["screenshot"]).is_file():
                a = ArtifactDraft(role="ad_creative_image", path=Path(rec["screenshot"]), rel_path=f"snapshot/{lib}.png",
                                  mime="image/png")
                loader.ref_artifact(loader.put_artifact(a), a, incident_id=iid, ad_id=ad_pk)
            if link:
                n_links += 1
                targets.append(link)
                from ..ingest.model import ObsHit
                ctx = {"ad_archive_id": lib, "via": "snapshot"}
                for h in domain_hits(host_of(link), "ad.snapshot_link", ctx) + url_observables(link, "ad.snapshot_link", ctx):
                    loader.link(iid, ObsHit(h.type, h.value, h.field, h.display, h.confidence, h.context,
                                            "snapshot@1", h.noise_reason, h.attrs))
                conn.execute("UPDATE incidents SET entry_url = coalesce(entry_url, %s), needs_relink = true WHERE id = %s",
                             (link, iid))
            conn.commit()
            print(f"  {lib}  → {redact_token(link) if link else '(no outbound link)'}  {rec.get('error') or ''}", flush=True)
        loader.finish_run(run_id, "ok", {"rendered": len(picks), "with_link": n_links})
        conn.commit()
    if args.targets and targets:
        args.targets.parent.mkdir(parents=True, exist_ok=True)
        args.targets.write_text("\n".join(dict.fromkeys(targets)) + "\n", encoding="utf-8")
        print(f"{len(set(targets))} landing URL(s) → {args.targets}")
    print({"rendered": len(picks), "with_link": n_links})
    return 0


if __name__ == "__main__":
    sys.exit(main())
