# TROP — overnight build status (morning report)

> Updated at every gate by the lead session. Times are Europe/Warsaw.

## Timeline
- 21:44 start (earlier than the 22:15 plan). Brief read.
- 22:20 **Contracts gate**: `backend/` uv project (`trop` package, Python 3.12), `trop/schema.py` (all API shapes), `docs/contracts/schema.json`, CLI registry, `deploy/compose.yml` + `compose.coolify.yml`, `.env.example`, `docs/CONTRACTS.md`. Branch `integration`.
- Coolify check: the Solvro GitHub App (`solvro-coolify`) can read `Solvro/web-hacknation-trop` → deploy is unblocked.

- 22:05 **WS4 media merged** (integration): model gateway (OpenRouter Qwen3.6 → Gemini Flash → EasyOCR → cache; sha256 cache, offline replay, spend log), faces 9 TP/0 FP/2 FN reproduced, Gemini video passes for DANE 5/14/47 (d5 now has transcript content: fake-doctor back-pain ointment, "Program Państwowy"), voice ids (WeSpeaker ONNX; no two DANE videos share a voice), **adjudicator on Gemini Flash: 105 pairs, accuracy 1.00, 0 FP / 0 FN** → trusted for veto. Spend $0.24.
- BigQuery ADC set up by Dawid (separate gcloud config `~/.config/gcloud-trop`) → Google Ads Transparency in scope.
- 22:00 TechTree stopped on Dawid's request (session + 12 containers stopped, not removed).

- 22:10 **Incident: data/ wiped.** ws/2-api had committed its worktree `data` symlink (root .gitignore `data/` doesn't match a symlink); merging it let git replace the ignored dir. Fixed (`/data` anchored, symlink untracked). Restored: DANE from WCSS (sha OK), data/experiments from WS1's pre-wipe copy, raw/sample_v1 + face gallery + models from Dawid's laptop. Lost: captures/ (5.1 GB, re-capturable), WS4's Gemini outputs (≈$0.24, re-runnable). Backups now in ~/hacknation/backup/.
- 22:20 **WS2 API merged**: 77 endpoints, mock universe (BRIEF), SSE + `?replay=demo`, arq worker, Dockerfile (1.2 GB). Mock API live on 127.0.0.1:18000.
- 22:25 **WS1 engine merged — G-ENGINE PASS** (re-run by lead after restore): sample_v1 B³/ARI 1.00, LOCO 1.00/1.00, 0 wrong links, perturbations 0 wrong (502 0.867); DANE 9/9 open-set, 0 wrong, incremental + joint B³/ARI 1.00. `trop batch` on DANE: 10 items in 2.3 s, campaigns + operation column match labels. 56 tests pass. **Merged to main.**

- 22:24 **WS1 complete & merged**: isotonic calibration (276 pairs; p=0.54 at score 5, 0.99 at ~8), all ingest shapes (zip, capture-tool dir, file, URL, video-only), `trop analyze|ingest|batch|engine|db|export`, migration 0013 applied to dev DB (backup in data/backup/), judge seed `data/seed/trop_seed.dump`. 58 tests pass. WS2 resumed for G2 real-mode wiring.

- 22:36 **WS5 merged**: enrich (FS cache, replays offline; cache rebuilt from DB after the wipe), capture sandbox image `trop-capture` (read-only, caps dropped, no forms), Hunter Meta run pulled 67 real PL ads → 6 snapshots → 1 landing captured; CERT PL diff; Google ATC enabled (queries scan 6–35 GB, capped). **Oracle is weak** (backtest AUC 0.54 by time split, 0.78 random split; precision@20 0.55) — present honestly.
- 22:38 **WS6 merged**: White Rabbit live run from a kit-A domain found **50 sibling domains (23 new to our data)** in 9 steps for $0.07; fictional velmoria demo replay; Act: DSA art. 16 PDF/JSON (Polish notice by Gemini Flash), CERT PL draft, STIX 2.1, MISP, CSV, rules with dataset test (campaign A: precision 1.0, 0/42 benign). Nothing is ever sent.
- 22:45 **G2 core met (WS2)**: real-mode API on :18001 (offline, no keys): DANE folder 1 zip → six bots → `assign` KMP-001 p 0.99 in ~2 s. Mock API on :18000. Postgres image now pg17 (seed dump made with pg17). 111 tests pass. WS7 (extension + /sprawdz) started.

- 23:05 **WS3 web merged** (Next.js: Sprawdź → six bots over SSE → Raport → Graf, Kampanie, Zgłoszenie, Scal, Śledztwa, Lab + "Importuj zbiór"; follows the light zgrai-style boards; detective bots run from three.js r128). integration → **main**.
- 23:08 **Coolify**: created environment `hacknation-2026-trop` in project "Hackatony" and ONE compose application `trop` (uuid ss4xttwzy13a9ufyvslnpujo, branch main, `deploy/compose.coolify.yml`, domain https://trop.b.solvro.pl). First deploy queued.
  - **Decision: the public URL runs in MOCK mode (fictional universe only).** Real mode would serve organizer-derived identifiers (domains, pixel/tenant ids, captions) on a public URL, which the data rule forbids. Real data runs on the home PC (http://10.8.0.3:13000 once bound) and via `docker compose` for judges. See "Needs Dawid".

- 23:40 trop.b.solvro.pl answers (mock build; 502 was Traefik picking the image's EXPOSE 13000 → fixed, web listens on 3000). **Dawid decided: production = real data, no mocks, jury clicks through; login optional.** WS2 is bundling the derived data (seed dump, corpus, models, caches ≈ 120 MB) into the image; WS3 removes every fixture from real-mode paths and adds env-gated basic auth (off). Coolify env now has GEMINI/OPENROUTER/URLSCAN keys + LLM_BUDGET_USD=10 (live LLM features; capture off on the server). WS7 (extension + /sprawdz) merged. docs/INSTALL.md written. QA agent running G-E2E on a clean clone.

- 23:00 **Production build merged & redeploying** (WS2): data bundle in the image (127 MB: seed dump, corpus, models, caches, real replays), entrypoint seeding, no mock defaults; Coolify env: live LLM with LLM_BUDGET_USD=10, capture `local` in the new Chromium worker image (WS5: example.com 13.6 s / 222 MiB, real scam landing 15 s / 800 MiB within the 1.5 GB limit; Meta Hunter runs inside the image).
- 23:00 **QA G-E2E (clean clone)**: API PASS (seed → DANE 1 → assign KMP-001 p 0.99 in 0.6 s); **G-BATCH PASS** (10 folders 2.0 s, 10 zips 3.8 s, 13 columns). Web: blocking bug (prefilled demo URL overrides an uploaded zip), file-attach drop, /operators 404, investigation start race → fixture fallback, graph focus 404 → fixture fallback, /lab shape mismatch, SSE not closing after job.done. All assigned (WS2 API side, WS3 web side).
- Organizer materials through the real API (each folder zipped): DANE 1, 2 → KMP-001; 3 → KMP-003; 10, 36 → new; 48, 61 → confirm toward A/C (batch: one new campaign K, same operation); 14 → confirm on a degenerate ad-name `x` (weak); 47 → confirm KMP-007 (should be new); 5 → insufficient (video not wired yet). WS1 is wiring the adjudicator veto (confirm band only) + video/ASR evidence.

## Needs Dawid
- Deadline assumed 22.11 ~11:00.
