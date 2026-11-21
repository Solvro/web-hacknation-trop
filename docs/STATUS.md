# TROP: morning report

> Kept current by the lead session. Times are Europe/Warsaw. Last update: 22.11 00:10.

## TL;DR
- **Live:** https://trop.b.solvro.pl runs the **real product on real data**, with no mock data. It does live URL capture (sandboxed Chromium worker) and live LLM features (Gemini, capped at $10). Coolify: project "Hackatony" → environment `hacknation-2026-trop` → application `trop`.
- **Engine gate (G-ENGINE) passes:**
  - sample_v1 B³/ARI 1.00, LOCO 1.00/1.00, 0 wrong links, 0 wrong links under perturbation;
  - held-out DANE 9/9 with 0 wrong links;
  - 174 backend tests pass.
- **Every DANE folder works as a single upload on production.**
  - 1, 2 → KMP-001; 3 → KMP-003; 5, 10, 14, 36, 47, 48, 61 → new campaign.
  - 47, 48 and 61 used to be "confirm"; the adjudicator's veto turns them into new campaigns.
  - Batch mode (`trop batch`, Lab → "Importuj zbiór") on the whole DANE.zip, 509 MB, takes about 7 s. `results.csv` has both the campaign and the operation column.
- **API spend:** about $0.61 of the $30 cap.

## What works end to end
| Area | State |
|---|---|
| **Sprawdź** | Link, file, ZIP, folder (drag-and-drop) or trace → six bots over SSE → Raport → Graf. Built-in sample buttons. Real page screenshots with evidence outlines. Uploads over 20 MB go in 8 MiB chunks, because the Coolify proxy has a ~60 s limit. |
| **Engine (Déjà Vu)** | The ported RESULTS evidence engine, plus isotonic "pewność". The adjudicator (Gemini Flash, Polish rationale) works in the confirm band only and can only veto, never link. Video evidence uses the Gemini transcript and on-screen text, plus voice IDs; faces come from the gallery only. |
| **Kampanie** | KMP-001…009 with Polish names and descriptions, the campaign page, merge view and Zgłoszenie. **Act** builds a DSA art. 16 PDF/JSON, a CERT PL draft, STIX 2.1, MISP and CSV; nothing is ever sent. |
| **Śledztwa (White Rabbit)** | Starts from any material ("Śledź dalej"). A live run from a kit-A domain found 50 sibling domains, 23 of them new, for $0.07. **On production the live run currently hangs at 0 steps; being fixed (see below).** |
| **Hunter** | Meta Ad Library live (67 real PL ads → captured landing pages), the CERT PL list, urlscan pivots and Google Ads Transparency (BigQuery, advertiser stats only). **The scheduler is off on the server (manual runs only).** |
| **Oracle** | Domain-DNA scorer and urlscan CT polling. Weak: time-split backtest AUC 0.54, random split 0.78. Present it honestly. |
| **Extension** | MV3: badge, "Dlaczego?" and "Zgłoś". Verified headlessly against production. Demo feed: https://trop.b.solvro.pl/demo/feed-real.html. Laptop install: download `extension/dist/trop-extension.zip`, then "Load unpacked". |
| **Docs** | METHODOLOGY, DATA_SOURCES (licences, biometric note), ATLAS (campaign patterns), INSTALL, README. |

## Demo steps (jury path)
1. https://trop.b.solvro.pl → **Sprawdź** → click a sample (e.g. "DANE 1"), or drop a DANE folder or ZIP. The bots run, then the Raport shows „Dołącza do kampanii KMP-001 · pewność 0.99” with the evidence (pixel, kit tenant, lander).
2. **Graf:** click the domain, Zestaw strony and person nodes.
3. Sample **DANE 36** → „Nowa kampania (kandydat)” with the Sędzia rationale.
4. **Kampanie** → KMP-001 → **Zgłoś całą kampanię** → download the PDF/STIX.
5. **Śledź dalej** from a Raport (White Rabbit).
6. Paste a live link → captured in the sandbox → verdict.
7. **Lab:** the engine numbers.
8. Extension on the demo feed.

## Timeline (abridged)
- **21.11, 21:44** start. **21:49** contracts committed.
- **22:10** **Incident:** `data/` was wiped. A workstream branch committed its worktree `data` symlink, and merging it replaced the ignored directory. Restored from WCSS (DANE), from the engine workstream's copy (experiments) and from Dawid's laptop (sample_v1 + gallery). Lost: 5.1 GB of captures (re-capturable). Guard: `/data` is anchored in `.gitignore`, and every merge checks that no `data` symlink is tracked.
- **22:25** G-ENGINE passes on the ported engine and is merged to `main`.
- **22:45** G2: the real-mode API runs end to end offline.
- **23:00** production switched to real data (Dawid's decision).
- **23:00–00:10** fixes found while clicking through: streams that lost events, uploads through the proxy, files vs URL, graph focus ids, real screenshots, Polish texts, chunked uploads, veto → new.

## Cut or not done
- Real Facebook feed for the extension: untested (obfuscated DOM); the fixture page is the demo.
- Certstream live server: not run; the Oracle uses urlscan polling plus the backtest.
- SpeechBrain voice: replaced by a WeSpeaker ONNX model on CPU. Deepfake score: skipped.
- Google Ads Transparency: advertiser rows only; each query scans 6–35 GB.

## Known bugs / in progress
- **Production investigations hang at 0 steps in live mode**; they work locally. A diagnostics endpoint and a fix are in progress.
- Production QA click-through in progress (results below when done).

## Needs Dawid
- **Final video:** a demo video session is rendering 2–4 versions (≤ 2 min) to choose from.
- **Pitch deck:** canvas with 4 style variants (publishes after 01:00).
- **Hunter scheduler:** turn it on on the server? Meta every 2 h, CERT PL hourly, urlscan/Oracle every 6 h.
