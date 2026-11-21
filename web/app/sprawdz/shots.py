"""Screenshots of /sprawdz against the API behind the web proxy (production when API_INTERNAL_URL points there). Run: python shots.py [base_url]  (default http://127.0.0.1:13160)"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:13160"
OUT = Path(os.environ.get("TROP_SHOTS", "/home/dawid-home-pc/hacknation/trop/data/screens/ws7"))
OUT.mkdir(parents=True, exist_ok=True)
CHROME = os.environ.get("CHROME", str(Path.home() / ".cache/ms-playwright/chromium-1243/chrome-linux64/chrome"))

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, args=["--headless=new"])
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    pg.goto(f"{BASE}/sprawdz")
    pg.get_by_text("Schematy tego tygodnia").wait_for()
    pg.get_by_role("heading", name="Znana kampania oszustwa reklamowego").wait_for(timeout=10000)
    pg.get_by_label("Link do reklamy lub tekst reklamy").fill("Wydarzenie, które wstrząsnęło całą Polską")
    pg.get_by_role("button", name="Sprawdź").click()
    pg.get_by_text("To wygląda na znane oszustwo").wait_for(timeout=10000)
    pg.screenshot(path=str(OUT / "10-sprawdz-scam.png"), full_page=True)
    pg.get_by_role("button", name="Zgłoś tę reklamę").click()
    pg.get_by_text("zgłoszenie przyjęte").wait_for(timeout=10000)
    pg.screenshot(path=str(OUT / "10b-sprawdz-reported.png"), full_page=True)
    pg.get_by_label("Link do reklamy lub tekst reklamy").fill("https://przyklad.example/abc")
    pg.get_by_role("button", name="Sprawdź").click()
    pg.get_by_text("Nie znamy tego materiału").wait_for(timeout=10000)
    assert "bezpiecz" not in pg.get_by_role("heading", level=2, name="Nie znamy tego materiału").inner_text().lower()
    pg.screenshot(path=str(OUT / "11-sprawdz-unknown.png"), full_page=True)
    pg.set_viewport_size({"width": 390, "height": 800})
    pg.screenshot(path=str(OUT / "12-sprawdz-mobile.png"), full_page=True)
    assert pg.evaluate("document.documentElement.scrollWidth <= 390 && [...document.querySelectorAll('main *')].every(e => e.getBoundingClientRect().right <= 391)"), "horizontal overflow"
    b.close()
print("OK")
