# TROP: wtyczka "Sprawdź reklamę" (MV3)

Plain JS, no build step. Content script (`content.js`, `phash.js`) finds sponsored posts ("Sponsorowane" / "Sponsored"),
extracts advertiser, caption, CTA link and a creative pHash (32x32 DCT, 64 bit, computed in the browser), and asks
`POST /api/v1/public/extension/match` (via the service worker `background.js`). On a match it shows an overlay
"Pasuje do znanej kampanii oszustwa" with "Dlaczego?" (coarse reasons only), "Zgłoś" (`POST /public/report`) and "Ukryj".
No match means no overlay: the extension never says an ad is safe. Popup = the same "Sprawdź" field as the web page
(`POST /public/check`). Options: API base URL (default `http://127.0.0.1:18000`, preset `https://trop.b.solvro.pl`),
anonymous random install id (stored in `chrome.storage.local`, sent as `install_id`).

Only advertiser name, caption, target link and the pHash leave the browser; no image, no account data.
Cross-origin creatives with a tainted canvas send `creative_phash: null` (text and link still match).

## Install unpacked
1. `chrome://extensions` -> Developer mode -> Load unpacked -> select this `extension/` folder.
2. (Optional) Details -> Allow access to file URLs if you open the fixture via `file://`.

## Demo (no Facebook needed)
```bash
# terminal 1: API in mock mode on :18000 (see repo docs)
# terminal 2: fixture feed
cd extension/fixture && python -m http.server 13150 --bind 127.0.0.1
```
Open `http://127.0.0.1:13150/feed.html`: three fictional posts, only the sponsored "Puzzle Mania PL" post
(fictional «Kurier Dnia» lure, morvanta.click-style link) gets the badge. Click "Dlaczego?", then "Zgłoś"
(status shows the report id `REP-…`). Click the toolbar icon, paste `https://morvanta.click/?utm_source=fb`
-> "To wygląda na znane oszustwo"; paste any other link -> "Nie znamy tego materiału".

## Headless test
```bash
backend/.venv/bin/python extension/test/e2e.py   # needs playwright + chromium, API on :18000
```
Loads the extension in a persistent Chromium context (`--headless=new --load-extension`), asserts badge, report ack
and popup verdicts, writes screenshots to `data/screens/ws7/` (override with `TROP_SHOTS`, Chrome binary with `CHROME`).
Never point it at real facebook.com.

Facebook note: its DOM is obfuscated and changes often; the sponsored detector (`isSponsored`/`extract` in `content.js`)
is best effort and the fixture is the supported demo surface.
