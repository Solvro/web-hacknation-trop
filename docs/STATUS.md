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

## Needs Dawid
- (optional) BigQuery ADC (`gcloud auth application-default login`) for Google Ads Transparency — skipped for now.
- Deadline assumed 22.11 ~11:00.
