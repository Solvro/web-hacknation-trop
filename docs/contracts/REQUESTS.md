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

# WS2 answers to the QA round (API)

- **Graph node ids** (`GET /graph?focus=&origin=`): incidents `INC-…`/`p1`, campaigns `KMP-…`, operators `OP-…`, domains `d:<host>` (a bare
  domain is accepted), people `person:<name>`, traces `trace:<field>:<value>` (`meta.field/value/layer`; CDN = `trace:cdn:<name>`, `meta.weak`).
  Chip aliases resolve server-side: `trace:kit`, `trace:capi`, `trace:cdn`, `trace:pixel:<v>`, `trace:content:<v>`, `trace:<field>:<v>`. An unknown
  focus id with a known `origin` is shown as a synthetic node (`meta.synthetic`) next to the origin; without origin it is 404. A freshly analysed
  `origin` (INC-U…, not in the corpus) is loaded from the job result and its own traces are included.
- **`/lab/metrics`** summary keys: `bcubed_f1, ari, pairwise_precision, pair_auc, open_set_accuracy, dane_open_set{correct,n,wrong_links},
  new_campaign_precision, wrong_links, loco_link, loco_not_link, operator_f1, m2_infra_blind_f1, raw{sample,dane,ablation}`; `view=baselines` → `rows[{model,bcubed_f1}]`;
  `/lab/ablation` → `[{layer, delta_f1, b3_F1, ari, pair_auc, loco_link, wrong}]` (drop-one-layer, from `trop eval --ablation`).
- **`Decision.duplicate_of`** is set (L0) when the analysed material has the same entry URL / landing hash as a corpus incident.
- `GET /operators[?ids=]` lists operators; `POST /analyze` with `files` ignores a prefilled `url`.

# WS2 round 3 (prod fixes)

- **Durable streams:** every job / investigation event is appended to Redis list `trop:job:<id>:events` / `trop:inv:<id>:events` (TTL 24 h);
  `/jobs/{id}/stream` and `/investigations/{id}/stream` replay the list, then follow it by index (no pub/sub loss, no idle cut-off while the job runs)
  and close after `job.done` / `job.error` / `investigation.done`.
- `GET /act/packages?campaign_id=&status=`, `GET /oracle/predictions?status=&campaign=` filter; real mode never returns campaigns outside the corpus.
- Real campaigns: Polish `name`, `narrative` (= headline) and `description` = `"headline\nlead"` from `backend/trop/api/campaigns_pl.json`.
- `side:'right'` is set only on incident focus nodes.
- **Samples:** `GET /api/v1/samples` → `[{id,title,description,expected,size}]` (dane-1, dane-3, dane-36, dane-5, p13, p14; zips live in the image bundle,
  `deploy/make_samples.py`); `POST /api/v1/samples/{id}/analyze` → `AnalyzeAccepted` (a normal job, stream `/jobs/{id}/stream`).
  Offline outcomes: dane-1 → assign KMP-001, dane-3 → assign KMP-003, dane-36 → new, dane-5 → insufficient, p13 → assign KMP-008, p14 → assign KMP-009 (duplicate_of p14).

# WS2 round 4

- `POST /api/v1/investigations {seed: "incident:<id>"}` (any analysed incident, corpus or fresh upload/URL result): the API derives the pivots
  (landing etld1 + redirect/chain domains, ad display_link / CTA domain, domains named in the video, advertiser + page_id / library_id, kit tenant / pixel / CAPI / Google Ads)
  and answers `{id, seed, pivots, hints}`. White Rabbit is seeded with the best domain; the rest is passed as analyst notes (`steer` channel, <= 300 chars each, Polish),
  same budget cap (`budget_steps`, usd cap 1.0). No domain at all -> seed = advertiser / `page:<id>` with a note to start from `adlib_search` + `db_search`;
  neither -> 422. The investigation's `campaign_id` defaults to the incident's campaign. (The offline/heuristic planner ignores notes; the LLM planner follows them.)
- dane-5 (video only) now analyses to `new` with media evidence: zips are unpacked by the adapter (ingest's `single_item` treats a zip as a generic "upload" and loses
  the video layer; WS1 may want `classify(root)` there) and the bundle carries the d5 mp4 at its recorded path so the (name, size) media lookup hits.
