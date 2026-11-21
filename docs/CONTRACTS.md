# TROP — contracts for the overnight build

> Owner: the integrator (lead session). **Contracts change only through the lead.** If a workstream needs a change,
> write it in its report (or a `CONTRACT-REQUEST.md` at the root of its branch) and work around it with a local adapter until merged.

## 1. Source of truth

| Contract | File | Consumers |
|---|---|---|
| Data model (pydantic) | `backend/trop/schema.py` | all backend WS |
| JSON schema (generated) | `docs/contracts/schema.json` (`cd backend && uv run trop schema --out ../docs/contracts/schema.json`) | web (TS types via `json-schema-to-typescript`), extension |
| REST endpoints | `docs/design/README.md` §7.1 (base `/api/v1`) + §3 below | WS2 implements, WS3/WS7 consume |
| SSE catalogue | §4 below (extends design §7.2) | WS2 emits, WS3 consumes |
| Engine interface | `backend/trop/engine/contract.py` | WS2 worker, WS6, WS7 |
| Model gateway interface | `backend/trop/media/gateway_contract.py` | WS1, WS5, WS6 |
| CLI registry | `backend/trop/cli.py` (each WS adds `trop/<pkg>/cli.py` with `app`/functions listed there) | everyone |
| Settings | `backend/trop/config.py` (env / `.env`) | everyone |
| Decision thresholds | `experiments/RESULTS.md` §4: τ = 5, margin δ = 1, confirm [1, 5), new < 1, operator flag ≥ 3, operator-only cap +4 with content/ad agreement ≥ 2.5 | WS1 |

## 2. Folder ownership, branches, worktrees

| WS | Branch | Owns (write) | Reads |
|---|---|---|---|
| WS1 Engine & ingest | `ws/1-engine` | `backend/trop/{ingest,extract,engine,eval,store}`, `backend/migrations/`, `backend/tests/{engine,ingest,eval,store}/` | experiments/, scrapers/, db/ |
| WS2 API, worker, deploy | `ws/2-api` | `backend/trop/{api,worker}`, `deploy/`, `backend/tests/{api,worker}/`, `data/replay/` (recorded streams) | schema, engine contract |
| WS3 Web | `ws/3-web` | `web/` (except `web/app/sprawdz/`, WS7) | schema.json, docs/design |
| WS4 Media & models | `ws/4-media` | `backend/trop/media`, `deploy/wcss/`, `backend/tests/media/` | experiments/rp/{media,gallery,emb}.py |
| WS5 Sources | `ws/5-sources` | `backend/trop/{capture,enrich,hunter,oracle}`, `backend/tests/{capture,enrich,hunter,oracle}/` | scrapers/ |
| WS6 White Rabbit & Act | `ws/6-agent` | `backend/trop/{agent,act}`, `backend/tests/{agent,act}/` | enrich/hunter (WS5), gateway (WS4) |
| WS7 Extension & public | `ws/7-ext` | `extension/`, `web/app/sprawdz/` | public endpoints |
| Lead | `integration` → `main` | `docs/`, `README.md`, `backend/trop/{schema,config,cli,__init__}.py`, `backend/pyproject.toml`*, `.env.example` | all |

\* `backend/pyproject.toml`: a WS **may add** dependencies (append lines inside the list, one per line) — the lead resolves merge conflicts. No other edits.

Worktrees live under `~/hacknation/trop-wt/<ws>` (or the harness's own worktree dir). Every worktree needs the data: **`data/` is git-ignored, so use the absolute path `/home/dawid-home-pc/hacknation/trop/data`** (set `DATA_DIR`, or symlink `data -> /home/dawid-home-pc/hacknation/trop/data` in the worktree; the symlink is git-ignored too). Same for `.env`: symlink or read `/home/dawid-home-pc/hacknation/trop/.env`.

Rules:
- Touch only your folders. Do not edit `experiments/` (frozen; RESULTS reproductions) or `scrapers/` (source of the port; copy code into your package, don't import from `scrapers`/`experiments` at runtime).
- Commit early and often on your branch. Messages: imperative, English, scoped (`engine: port evidence scoring`). **Never mention Claude/AI assistants**: no `Co-Authored-By` trailer, no "Generated with …".
- Never commit anything from `data/` or organizer identifiers in fixtures. Tests that need organizer data read it from `DATA_DIR` and `skip` when it is absent.
- Never push `main`; the lead merges. Push your branch (`git push -u origin ws/…`) when you reach a deliverable.
- Machine is shared: TROP ports only (below). Never stop/modify other containers. Heavy jobs: `nice -n 10`. Python via `uv` (3.12), Node via fnm: `eval "$(~/.local/share/fnm/fnm env --shell bash)"`.

## 3. Ports, hosts, data paths

| What | Home PC (dev) | `deploy/compose.yml` | Coolify |
|---|---|---|---|
| Postgres | **55432** = existing `redpill-db-postgres-1` (user/db `redpill`, pw `redpill_dev`, 1 752 incidents) | 55433 (`trop`/`trop`) | internal |
| Redis | 56379 (start with compose `redis` service: `docker compose -f deploy/compose.yml up -d redis`) | 56379 | internal |
| API | 18000 (`uv run trop serve --port 18000`) | 18000 | `trop.b.solvro.pl/api` (proxied by web) |
| Web | 13000 (`npm run dev -- -p 13000`) | 13000 | `trop.b.solvro.pl` |

Bind to `127.0.0.1` or `10.8.0.3` (WireGuard, Dawid's laptop). Never 0.0.0.0 on the host.

Data (all under `DATA_DIR`, git-ignored): `raw/sample_v1/p1..p15`, `raw/dane/unpacked/do_udostępnienia/{1,2,3,5,10,14,36,47,48,61}`, `experiments/{sample_v1,dane,joint}/` (incidents JSON, VLM outputs, enrichment), `experiments/face_gallery/` (+ SFace index), `captures/`, `artifacts/`. New: `cache/` (model + enrichment cache, sha256 keys), `models/` (face index copy), `replay/` (recorded SSE), `seed/` (DB snapshot for judges), `out/` (batch results).

Labels: `experiments/labels.yaml` (sample_v1), `experiments/labels_dane.yaml` (DANE).

## 4. SSE event catalogue

Envelope (`schema.Event`): `event: <type>` + `data: {"type","at","data"}`. Every SSE endpoint accepts `?replay=demo` (recorded stream from `data/replay/<name>.jsonl`, same timing) and sends a `: ping` comment every 15 s.

### 4.1 `GET /api/v1/jobs/{id}/stream` (Sprawdź, the six bots)

Order for one analysis: for each bot step `job.step(run)` → zero or more `job.evidence` / `job.finding` → `job.step(done|warn|skip|error)`; `job.ranking` whenever candidate scores change (from Archiwista on); finally `job.done`.

| type | data | Notes |
|---|---|---|
| `job.step` | `{job_id, step: JobStep}` | `step.key` ∈ capture, tracking, content, infra, compare, verdict; `step.bot` ∈ zwiadowca, tropiciel, czytelnik, notariusz, archiwista, sedzia (one bot per step, fixed order `schema.BOT_STEPS`). |
| `job.evidence` | `{job_id, bot, item: EvidenceItem}` | A finding about the material itself (value + rarity) during steps 1–4; `weight` is the prior strength until Archiwista scores pairs. |
| `job.finding` | `{job_id, finding: Finding}` | Where on the captured page it was found (outline box). Optional. |
| `job.ranking` | `{job_id, scores: CampaignScore[], graph?: GraphPayload}` | Live campaign ranking + small forming graph. |
| `job.done` | `{job_id, incident_id, decision: Decision}` | Then the UI shows Raport. `GET /incidents/{id}/decision` returns the same Decision. |
| `job.error` | `{job_id, step, message}` | Page down etc. → board 13 (still emit what was established). |

### 4.2 Global `GET /api/v1/events`
`incident.created {incident_id, source}` · `incident.attributed {incident_id, decision, campaign_id?, p}` · `campaign.updated {campaign_id, counts, heat}` · `alert.created Alert` · `triage.created {item_id, type}` · `triage.updated {item_id, status}` · `oracle.match OraclePrediction` · `hunter.capture {source_id, incident_id}` · `extension.report {incident_id}` · `act.submitted {package_id, kind, campaign_id}` · `model.updated {model, version, metrics_delta}`.

### 4.3 `GET /api/v1/investigations/{id}/stream` (White Rabbit, Śledztwa)
`agent.step {investigation_id, step: InvestigationStep}` · `graph.node_added {investigation_id, node: InvestigationNode, parent?}` · `graph.edge_added {investigation_id, edge}` · `casefile.delta {investigation_id, step_n, text_delta}` · `investigation.decision {investigation_id, node_id, question, options}` (Sędzia card) · `investigation.done {investigation_id, summary}`.

### 4.4 `GET /api/v1/oracle/stream`
`oracle.match OraclePrediction`.

## 5. REST additions to design §7.1

- `POST /api/v1/analyze` multipart: `url` | `files[]` (screenshot, video, HAR, zip, folder as zip) | `trace` → `AnalyzeAccepted`. A `trace` (domain, pixel, name) returns `{job_id: null}` and the UI opens `/slad/{type}/{value}`.
- `GET /api/v1/traces/{type}/{value}` → board 14 data `{value, type, campaigns[], weekly[], latest: IncidentSummary[], usage[], co_traces[]}`.
- `POST /api/v1/batch` (zip or folder upload, "Importuj zbiór") → `{job_id}`; `GET /api/v1/batch/{job_id}` → `BatchResult`; `GET /api/v1/batch/{job_id}/results.csv`.
- `GET /api/v1/operations` · `GET /api/v1/operations/{id}` → `Operation`.
- `GET /api/v1/graph?focus=<node id>` → `GraphPayload` with `focus` + `panel` (boards 4a–4d).
- `GET /api/v1/health` → `{ok, mode, db, redis, version, counts}`.
- `GET /api/v1/campaigns/{id}/merge-preview?other=` → `MergePreview`; `POST /api/v1/campaigns/{id}/merge` body `MergeRequest`.

Mock mode (`TROP_MODE=mock` or `trop serve --mock`): every endpoint serves the fictional universe of `docs/design/canvas/BRIEF.md` (KMP-017 «Zamach», INC-24817, OP-03 «Kestrel», velmoria.click investigation …) with exactly these shapes. Real mode serves the DB (organizer + Hunter data). The web app shows a "demo/fikcyjne" pill in mock mode.

## 6. Gates

| Gate | Check | Command |
|---|---|---|
| G-ENGINE | sample_v1 B³ 1.00 / ARI 1.00 / LOCO 1.00 / 0 wrong; DANE open-set 9/9, 0 wrong links; perturbation 0 wrong | `cd backend && uv run trop eval && uv run trop eval --dane` + `uv run pytest tests/engine` |
| G-BATCH | `results.csv` with campaign + operation columns, no crash on any DANE shape | `uv run trop batch $DATA_DIR/raw/dane/unpacked --out $DATA_DIR/out/results.csv` |
| G-E2E | clean `docker compose up` → seed → analyse → verdict with evidence < 60 s, offline | `docker compose -f deploy/compose.yml up -d --build` |
| G-DEMO | 3-min script twice live + once `?replay=demo` | docs/DEMO.md |
| G-DOCS | METHODOLOGY, DATA_SOURCES, INSTALL, ATLAS, README | — |
