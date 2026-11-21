# Contract requests from WS2 (api/worker/deploy)

1. `schema.AnalyzeAccepted.job_id` should be `str | None` (CONTRACTS §5: a `trace` input returns `{job_id: null}`).
   Workaround: `trop.api.models.AnalyzeResponse` (identical but nullable) is the response model of `POST /analyze`.
2. API-only resources without a model in `schema.py` live in `trop/api/models.py` (Alert, Artifact, Match, Person, Brand,
   TraceView, TriageList, FeedbackStats, StressRun, CapturePolicy, PublicScheme, ...). Promote them to `schema.py` if the
   web types should be generated from them (they are all in the OpenAPI document already: `backend/trop/api/openapi.json`).
3. SSE replay file naming: `?replay=<name>` resolves to `data/replay/<name>-<kind>.jsonl` with kind in
   analyze | investigation | events | oracle (fallback `<name>.jsonl`). Canned `demo-*` recordings ship in `trop/api/replay/`.
