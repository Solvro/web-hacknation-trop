# Contract requests from WS2 (api/worker/deploy)

1. `schema.AnalyzeAccepted.job_id` should be `str | None` (CONTRACTS §5: a `trace` input returns `{job_id: null}`).
   Workaround: `trop.api.models.AnalyzeResponse` (identical but nullable) is the response model of `POST /analyze`.
2. API-only resources without a model in `schema.py` live in `trop/api/models.py` (Alert, Artifact, Match, Person, Brand,
   TraceView, TriageList, FeedbackStats, StressRun, CapturePolicy, PublicScheme, ...). Promote them to `schema.py` if the
   web types should be generated from them (they are all in the OpenAPI document already: `backend/trop/api/openapi.json`).
3. SSE replay file naming: `?replay=<name>` resolves to `data/replay/<name>-<kind>.jsonl` with kind in
   analyze | investigation | events | oracle (fallback `<name>.jsonl`). Canned `demo-*` recordings ship in `trop/api/replay/`.

# Contract notes / requests from WS6 (White Rabbit + Act)

No blocking schema change needed; everything fits `schema.py` as is. Notes for the lead:

1. `graph.node_added` is an **upsert**: when a node's status/level changes (e.g. `in_progress` → `new`, analyst
   "Pomiń" → `skipped`, promote → `in_campaign`) the same node id is re-sent. The web should replace by id.
2. Node ids: domains are `d-<fqdn>`; trace/query nodes `n-…` (stable sha1-based suffixes, so replays are deterministic).
   `InvestigationNode.status` also uses `skipped` (already allowed by the schema).
3. `investigation.decision.options` is `["Dołącz", "Pomiń"]`; the answer comes back through
   `POST /investigations/{id}/steer` with `{node_id, choice}` (WS2's `SteerRequest` already has both fields).
4. New agent tool `oracle_lookup` (reads `oracle_candidates`), branch `db`, bot `notariusz`.
5. `ActPackage.contents` carries an extra key `certpl_new` (domains not yet on the CERT PL list). `ActPackage.formats`
   is `["pdf","json","stix","misp","csv"]`; `download()` also accepts `certpl` (the e-mail draft as text).
6. Suggest adding `"certpl"` to the `format` pattern of `GET /act/packages/{id}/download` (WS2 route).

## WS7 (extension / public /sprawdz)
- `POST /public/check` should accept an optional multipart file field `image` (screenshot). The public page already sends it; the server currently ignores it, so a screenshot-only check returns "unknown".
- `PublicReport` has no `source` field; the extension sends `note: "extension"` and `post{...}`. Please set incident `source=extension` when `post` is present.
- Web shell (WS3): root layout renders Header/Footer for every route. `/sprawdz` covers it with a fixed full-screen wrapper; cleaner: move `/sprawdz` into a route group `(public)` with its own layout, or hide the shell for that path.
