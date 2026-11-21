"""Headless end-to-end test: fixture feed -> badge -> "Zgłoś" -> API ack.

Needs: mock API on 127.0.0.1:18000, Playwright chromium (backend/.venv has playwright).
Run: backend/.venv/bin/python extension/test/e2e.py
Screenshots go to $TROP_SHOTS or data/screens/ws7/.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
API = os.environ.get("TROP_API", "https://trop.b.solvro.pl")
FIXTURE = os.environ.get("TROP_FIXTURE", "feed-real.html")
REAL = FIXTURE == "feed-real.html"
SCAM_ADV = "Formal Favorable" if REAL else "Puzzle Mania PL"
PORT = 13150
SHOTS = Path(os.environ.get("TROP_SHOTS", "/home/dawid-home-pc/hacknation/trop/data/screens/ws7"))
SHOTS.mkdir(parents=True, exist_ok=True)


def mine():
    try:
        return json.load(urllib.request.urlopen(f"{API}/api/v1/public/reports/mine"))["submitted"]
    except Exception:
        return None


def main():
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
                           cwd=ROOT / "fixture", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    before = mine()
    reqs = []
    try:
        with sync_playwright() as p, tempfile.TemporaryDirectory() as ud:
            ctx = p.chromium.launch_persistent_context(
                ud, executable_path=os.environ.get("CHROME", str(Path.home() / ".cache/ms-playwright/chromium-1243/chrome-linux64/chrome")), headless=False,
                args=["--headless=new", f"--disable-extensions-except={ROOT}", f"--load-extension={ROOT}"],
                viewport={"width": 720, "height": 1100})
            bodies = {}
            def on_req(r):
                if "/public/" in r.url:
                    reqs.append((r.method, r.url))
                    bodies.setdefault(r.url.split("/api/v1")[1], []).append(r.post_data)
            ctx.on("request", on_req)
            page = ctx.new_page()
            page.goto(f"http://127.0.0.1:{PORT}/{FIXTURE}")
            host = page.locator("[data-trop-overlay]")
            host.first.wait_for(timeout=15000)
            n = host.count()
            assert n == 1, f"expected exactly 1 overlay (scam post only), got {n}"
            assert page.locator("#post-scam [data-trop-overlay]").count() == 1
            assert page.locator("#post-benign-ad [data-trop-overlay]").count() == 0
            assert page.locator("#post-friend [data-trop-overlay]").count() == 0
            body = page.locator("#post-scam [data-trop-overlay]").evaluate("h => h.shadowRoot.textContent")
            assert "Pasuje do znanej kampanii oszustwa" in body, body
            print("overlay:", body.strip()[:300])
            assert "bezpiecz" not in page.content().lower()
            page.screenshot(path=str(SHOTS / "01-badge.png"), full_page=True)

            page.get_by_role("button", name="Dlaczego?").click()
            why_txt = page.locator("#post-scam [data-trop-overlay]").evaluate("h => h.shadowRoot.querySelector('.why ol').textContent")
            assert why_txt.strip(), "no reasons"
            print("reasons:", why_txt)
            page.screenshot(path=str(SHOTS / "02-why.png"), full_page=True)

            page.get_by_role("button", name="Zgłoś").click()
            page.get_by_text("Zgłoszono, dziękujemy").wait_for(timeout=10000)
            page.screenshot(path=str(SHOTS / "03-reported.png"), full_page=True)
            ack = page.locator("#post-scam [data-trop-overlay]").get_attribute("data-reported")
            assert ack and ack.startswith("REP-"), ack

            # popup: same check field as the web
            sw = ctx.service_workers[0] if ctx.service_workers else ctx.wait_for_event("serviceworker")
            ext_id = sw.url.split("/")[2]
            pop = ctx.new_page()
            pop.set_viewport_size({"width": 380, "height": 520})
            pop.goto(f"chrome-extension://{ext_id}/popup.html")
            q = pop.get_by_label("Link do reklamy lub tekst reklamy")
            q.fill("https://civicdaybook.live/" if REAL else "https://morvanta.click/?utm_source=fb")
            pop.get_by_role("button", name="Sprawdź").click()
            pop.locator("h2").first.wait_for(timeout=15000)
            print("popup verdict for known domain:", pop.locator("h2").first.inner_text())
            pop.screenshot(path=str(SHOTS / "04-popup-scam.png"))
            pop.get_by_label("Link do reklamy lub tekst reklamy").fill("https://przyklad.example/abc")
            pop.get_by_role("button", name="Sprawdź").click()
            pop.get_by_text("Nie znamy tego materiału").wait_for(timeout=10000)
            pop.screenshot(path=str(SHOTS / "05-popup-unknown.png"))
            m = next(x for x in map(json.loads, bodies["/public/extension/match"]) if x["advertiser"] == SCAM_ADV)
            import re
            assert re.fullmatch(r"[0-9a-f]{16}", m.get("creative_phash") or ""), m
            assert m["install_id"] and m["advertiser"] == SCAM_ADV and ("civicdaybook.live" if REAL else "morvanta.click") in m["cta_url"], m
            print("match payload:", {k: (v[:40] if isinstance(v, str) else v) for k, v in m.items()})
            ctx.close()
    finally:
        srv.terminate()
    after = mine()
    if before is not None and after is not None:
        assert after == before + 1, f"report counter {before} -> {after}"
    kinds = {(m, u.split("/api/v1")[1]) for m, u in reqs}
    print("API calls seen:", sorted(kinds))
    print("PASS: badge shown on scam post only, report acked, popup verdicts OK; reports", before, "->", after)


if __name__ == "__main__":
    main()
