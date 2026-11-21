# TROP — overnight build status (morning report)

> Updated at every gate by the lead session. Times are Europe/Warsaw.

## Timeline
- 21:44 start (earlier than the 22:15 plan). Brief read.
- 22:20 **Contracts gate**: `backend/` uv project (`trop` package, Python 3.12), `trop/schema.py` (all API shapes), `docs/contracts/schema.json`, CLI registry, `deploy/compose.yml` + `compose.coolify.yml`, `.env.example`, `docs/CONTRACTS.md`. Branch `integration`.
- Coolify check: the Solvro GitHub App (`solvro-coolify`) can read `Solvro/web-hacknation-trop` → deploy is unblocked.

## Needs Dawid
- (optional) BigQuery ADC (`gcloud auth application-default login`) for Google Ads Transparency — skipped for now.
- Deadline assumed 22.11 ~11:00.
