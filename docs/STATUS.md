# TROP — overnight build status (morning report)

> Updated at every gate by the lead session. Times are Europe/Warsaw.

## Timeline
- 21:44 start (earlier than the 22:15 plan). Brief read.
- 22:20 **Contracts gate**: `backend/` uv project (`trop` package, Python 3.12), `trop/schema.py` (all API shapes), `docs/contracts/schema.json`, CLI registry, `deploy/compose.yml` + `compose.coolify.yml`, `.env.example`, `docs/CONTRACTS.md`. Branch `integration`.
- Coolify check: the Solvro GitHub App (`solvro-coolify`) can read `Solvro/web-hacknation-trop` → deploy is unblocked.

- 22:05 **WS4 media merged** (integration): model gateway (OpenRouter Qwen3.6 → Gemini Flash → EasyOCR → cache; sha256 cache, offline replay, spend log), faces 9 TP/0 FP/2 FN reproduced, Gemini video passes for DANE 5/14/47 (d5 now has transcript content: fake-doctor back-pain ointment, "Program Państwowy"), voice ids (WeSpeaker ONNX; no two DANE videos share a voice), **adjudicator on Gemini Flash: 105 pairs, accuracy 1.00, 0 FP / 0 FN** → trusted for veto. Spend $0.24.
- BigQuery ADC set up by Dawid (separate gcloud config `~/.config/gcloud-trop`) → Google Ads Transparency in scope.
- 22:00 TechTree stopped on Dawid's request (session + 12 containers stopped, not removed).

## Needs Dawid
- (optional) BigQuery ADC (`gcloud auth application-default login`) for Google Ads Transparency — skipped for now.
- Deadline assumed 22.11 ~11:00.
