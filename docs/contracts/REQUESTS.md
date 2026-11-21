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

# WS3 (web) contract requests

**Round 2 (real mode, 21.11 late):** the fixture fallback in point 2 is gone — fixtures only with `?offline=1` /
`NEXT_PUBLIC_MOCK=1`. Focus ids: the web sends `ev:<field>:<value>` for an evidence chip and resolves it itself
against `GET /graph` (exact id → `trace:<field>s:<value>` / any id ending in `:<value>` → `person:<lower name>` →
`d:<domain>` for URL/cert fields), then calls `/graph?focus=<real node id>`; unresolved → intentional empty state.
`trace:<type>:<value>` with the engine field name (plural or singular) works with this. Please: (a) `side:'right'` only on
incident centres (the web ignores it elsewhere), (b) a freshly analysed incident as a graph node (today `focus=INC-…`
404s, the web shows it as the origin card without edges), (c) Polish `narrative`/`description` in real mode (the web hides
English narratives and uses `name` as the headline), (d) `GET /act/packages?campaign_id=` should filter (the web filters
client-side meanwhile), (e) `oracle/predictions?campaign=` should filter (same).

The web works against today's API with local adapters (web/lib/graph.ts, web/lib/mock/*). These would remove them.

1. **`GET /graph?focus=<id>` returns the neighbourhood, not the whole graph** (focus node + origin + ≤ 6 direct
   neighbours), and answers for `INC-…` and `person:<name>` ids (today: empty `nodes`). The web trims a whole-graph
   answer itself (`neighbourhood()`), but cannot invent missing neighbours.
2. **`GraphPayload.panel` shape** (open dict in the schema). The web reads (all optional):
   `{kind_label, badge:{text,tone:g|amber|red|cyan|violet}, tags[], title, description, facts:[{k,v}], bot, bot_text,
   action:{label, href?, kind?:'investigate'|'trace'|'incident'|'campaign', seed?}, link:{label, href}}`.
   Today's `{kind, facts:["K: V"], bot_sentence:"Bot: …", primary_action}` is also accepted. Board copy for the four
   demo focus views (4a–4d) is in `web/lib/mock/graph.ts`; when the API panel has no `description` and a fixture exists
   the web shows the fixture (remove once the API serves these).
3. **Node `meta` for focus cards**: `sub` (second line), `count`, `thumb` (material/campaign thumbnail), `weak`
   (dashed, e.g. Cloudflare), `relation:'operator'|'oracle'` (violet dashed edge), `bot`, and for the bridge view 4d
   `side:'right'` on the centre plus `only:'origin'|'focus'` on traces present on one side.
4. **`JobStep.detail` convention**: first line = short summary shown in the bot strip / Raport row; following lines
   (`\n`) = the bot's sentences shown when the step is expanded.
5. **`Campaign.description`**: if it contains `\n`, line 1 is the Raport headline (board 3 h1) and the rest the lead
   paragraph; otherwise the web uses `narrative` as the headline. `name` may be `Zamach` or `«Zamach»`; the web wraps it.
6. Mock scenarios for the other outcomes from `POST /analyze`: `kelvaro.live` / HAR → `ambiguous` (board 12),
   `selqueno.live` → `job.error` at capture + `insufficient` (board 13). The web simulates these offline already.
7. `GET /traces/{type}/{value}`: the web uses Polish path types `domena|osoba|piksel|kit` in its own routes and sends
   the same strings to the API; please accept `domena→domain`, `osoba→person`, `piksel→pixel` aliases.

# WS7 (extension + /sprawdz) contract requests

1. POST /public/check: accept an optional `image` file (the page sends it; ignored today).
2. PublicReport with `post` present → incident source = extension (no source field in the schema).
3. WS3: root layout wraps every route in Header/Footer; /sprawdz covers it with a fixed wrapper — a (public) route group would be cleaner.
