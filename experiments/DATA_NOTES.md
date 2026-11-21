# Data notes — formats the ingest adapters must handle

> ⚠️ **Do not publish.** This file quotes organizer-derived identifiers (domains, pixel/tenant IDs, ad captions). The repo is public — keep it out of commits or redact it first (same rule as docs/PLAN.md).

Organizer data stays in `data/` (git-ignored) and on WCSS Lustre only. Never open the landing URLs in a normal browser.

## 1. sample_v1 (teaser CTF backup, `data/raw/sample_v1/p1..p15`)

One directory per incident (`pN/`), produced by an analyst by hand (Chrome "Save page as… complete" + DevTools HAR
export + a Windows screenshot):

| File | Present | Notes |
|---|---|---|
| `Zrzut ekranu <date> <time>.png` | 14/15 (not p6) | the **ad**, two kinds: feed-style post capture (11) or Meta Ad Library "Szczegóły reklamy" modal (3: p3, p4, p13 — has library ID, status, start date) |
| `<page title>.html` + `<page title>_files/` | 15/15 | Chrome save; first line `<!-- saved from url=(NNNN)<entry URL> -->` gives the **full entry URL** (query string = param grammar, ad_name, pixel ids). `_files/` holds assets with `.pobrane` suffix; Chrome names FB pixel config files by the **pixel ID** (e.g. `_files/1396608265958754`) |
| `<domain>.har` | 12/15 (not p6, p12, p14) | DevTools HAR 1.2 (`creator: WebInspector`), **with response bodies** (`content.text`, base64 for binary), POST bodies, `serverIPAddress`. Sizes 1.6–37 MB (p9 contains a whole HLS video) |
| `archive_<domain>_<YYYYMMDD_HHMMSS>/` (+ `.zip`, `.zip.sha256`) | p1 only | **organizer-style capture bundle**: `archive_info.json` {url, timestamp_utc, title, user_agent (HeadlessChrome/154)}, `dns_ssl.json` {hostname, ip, all_addresses, ssl{subject, issuer, notBefore, notAfter, serialNumber, subjectAltName, caIssuers, crlDistributionPoints}}, `metadata.json` {title, meta_tags, links, scripts, images}, `network.har`, `html/{rendered,source}.html`, `page_text.txt`, `page.pdf`, `page.mhtml`, `screenshots/{full_page,viewport}.png` (landing), `storage/{cookies,localStorage,sessionStorage}.json`, `sha256.json` (per-file hashes, Windows paths) |
| `video_deleted.txt` | p10 | empty marker: the ad video was removed |

Quirks: p2 is a byte-identical copy of p1 without the bundle (L0 duplicate test); the p1 bundle captured a
**Cloudflare 502** (landing content absent → real "error page" case); file names contain Polish characters in mixed
encodings (cp852 mojibake for some) — always open by listing, never by reconstructing names.

Adapter: `rp/extract.py` — `find_files()` for `pN/` dirs, `find_bundle_files()`/`is_bundle()` for capture bundles
(the visited URL comes from `archive_info.json`; `screenshots/` are landing screenshots, not ads).

## 2. DANE.zip (official dataset)

* Source: MEGA link from the task (`DANE.zip`, 509,743,633 B, sha256 `9582ac56…49d0`), not encrypted. Downloaded on the
  WCSS login node (MEGA's bandwidth quota is per IP; `wcss/mega_dl.mjs`), copied to `data/raw/dane/DANE.zip`,
  unpacked with `safe_unzip.py` to `data/raw/dane/unpacked/do_udostępnienia/` (329 files, 557 MB; a copy stays in
  `$RP_PD/redpill/data/dane/` on WCSS).
* **Only 10 incidents**, folders numbered `1, 2, 3, 5, 10, 14, 36, 47, 48, 61` — a sample from a larger numbered pool
  (the hidden test set is probably the rest of that pool → expect the same heterogeneity).
* **No labels, no manifest.** Same hand-made capture style as sample_v1 (Chrome "save complete" HTML + `_files/`,
  DevTools HAR with bodies, Windows screenshots), plus new shapes:

| Folder | Shape | Content |
|---|---|---|
| 1 | screenshot + HAR + HTML | fake Gazeta "«Wiem, kto strzelał»" (campaign A, new domain civicdaybook.live) |
| 2 | **2 HARs** + HTML, no screenshot | A pre-lander (acrosscommunities.live) **and its click-through** to healthlinkq.pro (lander) |
| 3 | screenshot + HTML (no HAR) | fake TVN24, Monika Olejnik (campaign C narrative) on healthlinkq.pro |
| 5 | **MP4 + yt-dlp `.info.json`** only | Ad Library ad 1982065065827084 (page "TreeKollo", id 1183383648198728, 3 creatives), 198 s 500×500 AI video, back-pain story; no landing |
| 10 | **6 iPhone screenshots `IMG_*.PNG`** + HAR (16 MB) + HTML | fake "App Store – Słodka Bonanza" (gambling) |
| 14 | 10 iPhone screenshots + **339 MB screen recording** + HTML + **capture-tool bundle** `ineptsolidoval_top/ineptsolidoval_top/{manifest.json, dom.html, page.har, page.mhtml, resources/}` | Metabo RX (health) |
| 36 | screenshot + HAR + HTML | "Poland Invest Summit 2026" (investment event) |
| 47 | **screen recording `Nagrywanie ekranu….mp4`** + HAR + HTML | Uromexil Forte (prostate) |
| 48 | screenshot + HAR (13 MB) + HTML | "37 minut po emisji wyprowadzono go w kajdankach…" pre-lander |
| 61 | `reklama_1.png` (Google display ad) + **`strona_1/2/3/`** (3-step funnel, each with HAR + HTML; one HAR is named just `.har`) | same "37 minut…" pre-lander → "Trwały Działunek" → glowpixel.org |

Adapter changes (`rp/extract.py`): merge all HARs of an incident and record each HAR's first document as
`landing.chain_urls`; treat sub-directories that are not `_files` as chain pages (`strona_N`, nested capture-tool
dirs) and pull their HAR/HTML; ad screenshots sorted `reklama|zrzut|screenshot` first, phone screenshots after;
`.info.json` → `ad.library_id / advertiser / page_id / video_title / n_creatives`; videos kept as `ad.video_path`
(not analysed yet: frames → VLM and ASR are the next step for folder 5/14/47).
Extraction of all 10: 27 s on CPU (the 339 MB recording is not read).

Labels written by hand in `labels_dane.yaml`: of the 9 labelled items, 3 are new variants of known sample_v1
campaigns (A, A, C) and 6 belong to 5 new campaigns (K×2, L, M, N, O); folder 5 is unlabelled. New "operation" level:
A + C + K share one investment funnel (A's pre-lander clicks through to C's lander domain healthlinkq.pro).
