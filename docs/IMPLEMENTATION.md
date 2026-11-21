# TROP — final implementation plan

> Status: 2026-11-21 afternoon. The build plan that turns the exploration (PLAN.md v2, `experiments/RESULTS.md`, `docs/db/`, `docs/design/`) into the submitted product.
> Decisions in force: the repo is **private**; **cloud LLMs are allowed** (the task and terms only forbid *public* distribution of organizer data); the organizers did not answer our questions, so we act on the assumptions in §9; **in scope: core + extras + stretch** (browser extension, video/speech analysis, live Meta Ad Library Hunter).
> Name: **TROP — follow the fake**. Modules: **Déjà Vu** (matching engine), **White Rabbit** (investigator agent), **Oracle** (early warning), **Hunter** (sources), **Act** (takedown packages).

---

## 0. Blockers to clear before anyone writes code

| # | Blocker | Owner | Why it matters |
|---|---|---|---|
| B1 | **C: has 1.5 GB free** (953 GB disk). The face-photo fetch already failed on it. | Dawid | Docker images (torch, Playwright), `node_modules`, models and Postgres need roughly 30–40 GB. Free space, move Docker/WSL storage to another drive, or develop on the home PC / WCSS. `data/captures` (5.1 GB) and `data/artifacts` (2.3 GB) can move to another drive or be pruned. |
| B2 | **Meta Ad Library identity verification** (facebook.com/ID). Steps: `docs/db/META_AD_LIBRARY_ACCESS.md`. | Dawid | Critical path for the live Hunter. Until it passes, the Hunter runs on the public-UI fallback and fixtures. |
| B3 | Keys in `.env` (git-ignored): `ANTHROPIC_API_KEY`, `URLSCAN_API_KEY` (exists), `IPINFO_TOKEN` (exists), `gcloud auth application-default login` for BigQuery, `WIKIMEDIA_UA`. | Dawid | Agent, adjudicator, notices, Google Ads Transparency, gallery refresh. |
| B4 | **Submission deadline and demo slot length.** | Dawid | Sets the clock times of the gates in §7. The plan below is written relative to T0 (start of implementation). |
| B5 | **WCSS GPU for the demo window**: our own `serve_vllm.sbatch` reservation (Qwen3.6-35B-A3B), not someone else's server. | Models stream | The ad-screenshot reader and Polish LLM run there. The judge build must still work without it (cache + EasyOCR + Claude fallback). |

---

## 1. Architecture (final)

```
web/  Next.js 15 + TS + Tailwind + shadcn/ui · Sigma.js/graphology · zgrai jelly bots (three.js)
      routes: /  (Sprawdź) · /kampanie · /kampanie/[id] · /kampanie/[id]/zgloszenie · /sledztwa/[id]
              /slad/[type]/[value] · /lab (hidden, metrics) · /sprawdz (public, no auth)
extension/  MV3 (content script on facebook.com + popup) → /api/v1/public/*
            │ REST + SSE (/api/v1, OpenAPI generated from FastAPI, contract = docs/design/README.md §7)
backend/  Python 3.12, uv, one package `trop`
  api/      FastAPI routers (analyze, jobs, incidents, links, evidence, campaigns, operators, graph,
            investigations, oracle, persons, act, hunter, lab, public, events SSE)
  worker/   arq on Redis: analyze · capture · enrich · media · link · hunt · oracle · agent · act · eval
  ingest/   adapters → IncidentDraft:  sample_dir · organizer bundle · capture-tool dir (manifest.json) ·
            multi-HAR click chain · strona_N funnel · phone screenshots · video + yt-dlp info.json ·
            single URL · upload (file/zip) · urlscan result · Ad Library ad · extension report
  capture/  Playwright victim-context profiles → organizer-compatible bundle (+ video download via yt-dlp)
  extract/  tracking · kit · content · infra · ad   (deterministic, CPU, ~1–3 s/incident)
  media/    model gateway (WCSS vLLM → Claude → EasyOCR) · faces (YuNet+SFace, 6.3k gallery) · pHash ·
            video keyframes (ffmpeg) · ASR (faster-whisper) · voice (SpeechBrain ECAPA) · deepfake (facetorch)
  enrich/   CERT PL · crt.sh/Cert Spotter · RDAP · DNS/NS · ASN · ipinfo · urlscan · Wayback (cached, replayable)
  engine/   Déjà Vu: blocking → typed rarity-weighted evidence → score_campaign / score_operator →
            decide (5 states) → clusters (campaign / variant / operator / operation) → explain
  agent/    White Rabbit: Claude tool-use loop over enrich/capture/db tools, budgeted, streamed
  oracle/   domain-DNA scorer + CT stream consumer (+ crt.sh polling fallback)
  hunter/   Meta Ad Library API (+ public-UI fallback) · Google Ads Transparency (BigQuery) · CERT PL diff ·
            urlscan pivots (expand) · scheduler (APScheduler inside the worker)
  act/      DSA Art. 16 package (PDF+JSON) · CERT PL submission draft · STIX 2.1 · rules + rule test
  store/    psycopg 3 · migrations (from db/) · artifact store (local FS volume; S3 interface optional)
  eval/     labels, B³/ARI, LOCO, held-out DANE, perturbation stress, ablation → Lab
deploy/   docker compose: postgres(+pgvector) · redis · api · worker · web  (+ profile `full`: capture, oracle)
docs/     METHODOLOGY · DATA_SOURCES (+licenses) · INSTALL · DEMO · ATLAS (campaign patterns) · this file
experiments/  frozen, reproduces RESULTS.md (cited by METHODOLOGY)
```

Fixed choices and why:
- **Déjà Vu = the approach (a) evidence engine from `experiments/rp/evidence.py` + `cluster.py`, ported as is.** It's the only approach with 0 wrong links on sample LOCO, all perturbations and held-out DANE (9/9). Embeddings, the GBM and the LLM adjudicator are support or veto only (RESULTS §0).
- **Artifacts on a local FS volume**, with an S3 interface kept behind a flag. MinIO community images are no longer pullable (docs/db §8.3).
- **No MinIO, no Neo4j, no login.** Graph views come from Postgres (`incident_neighborhood()`, recursive CTEs), with a GraphML/Cypher export for NASK.
- **Model gateway order:** WCSS vLLM (Qwen3.6-35B-A3B; raw material allowed) → Claude (cloud now allowed) → EasyOCR/offline cache. **Never take person identity from a VLM**; faces come only from SFace + gallery (VLMs renamed politicians in tests).
- **Claude models:** `claude-opus-5-5` for White Rabbit (long tool loops), `claude-sonnet-5-5` for notices and campaign summaries, `claude-haiku-5-5` for the adjudicator. Whoever writes this code loads the `claude-api` skill first.

---

## 2. Code consolidation (today there are three codebases)

| Today | Becomes | Notes |
|---|---|---|
| `experiments/rp/evidence.py`, `cluster.py`, `metrics.py`, `perturb.py`, `harness.py` | `trop/engine/*`, `trop/eval/*` | Port with tests that **reproduce RESULTS §2a/§2b exactly** (regression gate G-ENGINE). |
| `experiments/rp/extract.py` (handles DANE shapes) vs `scrapers/ingest/extract.py` | **one** `trop/ingest/*` + `trop/extract/*` | Keep rp's feature logic (it has the NEW features: kit tenants, lander ids, comment names, chain domains, path shapes). Keep the scrapers' `IncidentDraft` + `Loader` + DB provenance. Field names follow RESULTS §4. |
| `experiments/rp/media.py`, `gallery.py`, `emb.py`, `wcss/*` | `trop/media/*` | The gallery index (6,305 people) is built by a CLI; its artifacts go in `data/models/` (not git). |
| `scrapers/enrich/*`, `capture/*`, `hunter/*`, `expand.py`, `store/*` | `trop/enrich`, `trop/capture`, `trop/hunter`, `trop/store` | Already modular; move and rename the imports. |
| `db/migrations/0001–0012`, `migrate.py`, `seed_sample.py` | `backend/migrations/` + `trop db migrate/seed` | Add 0013: `investigations`, `investigation_steps`, `rules`, `rule_tests` (docs/db §9). |
| `experiments/` scripts | stay frozen | Referenced by METHODOLOGY for reproducibility. |

CLI (`trop …`): `db migrate|seed`, `ingest <path> [--source]`, `analyze <url|file>`, `batch <dir|zip> --out results.csv`, `enrich`, `capture <url>`, `gallery build`, `eval [--dane]`, `hunter run <source>`, `oracle run`, `demo record|replay`.

---

## 3. Feature work per pillar (definition of done)

### 3.1 Core — Déjà Vu (must, 60% of the score)
- Ingest every format in `experiments/DATA_NOTES.md` (sample_v1, bundle, DANE's 10 shapes) plus URL, upload and zip.
- Decision states exactly as RESULTS §4:
  - **assign:** max-linkage `score_campaign` ≥ 5 and margin ≥ 1;
  - **ambiguous:** two campaigns ≥ 5 within the margin;
  - **confirm:** best score between 1 and 5, the adjudicator may veto or annotate;
  - **new:** best score < 1, plus a "same operator as X" flag when `score_operator` ≥ 3;
  - **insufficient:** no landing content and no ad layer.
- **The confidence shown in the UI ("pewność 0.94")** is a Platt/isotonic fit of `score_campaign` → P(same campaign) on the labelled pairs, stored per model version. The design's α/conformal wording stays out of the UI (the canvas already removed it); the conformal τ(α) appears only in `/lab`.
- Levels: campaign → variant (Louvain inside) → operator (`score_operator` ≥ 3) → **operation** (shared funnel, the DANE finding).
- Explain: evidence chips `{type, layer, level, value, weight, df/N}`, "why linked", "why not linked" (best candidate + missing/conflicting), template diff.
- **Batch mode for the hidden test:** `trop batch` and a UI "Importuj zbiór" (folder or zip) → per-item decision → `results.csv` + a JSON with evidence, at **both campaign and operation granularity** (hedge for the unknown label definition).
- DoD: G-ENGINE passes (sample B³ = 1.00, DANE 9/9, 0 wrong links); a batch of all 25 items runs end to end in < 2 min on CPU with caches.

### 3.2 Media: video and speech (stretch, now in scope)
- Video sources: DANE 5 (yt-dlp mp4 + info.json), 14 and 47 (screen recordings, 339 MB), sample p9 (HLS in HAR), and Ad Library videos from the Hunter.
- Pipeline:
  1. `ffmpeg` scene-change keyframes (≤ 12 per video), each going to the ad VLM and to faces.
  2. faster-whisper (`large-v3-turbo` on WCSS, `small` int8 on CPU as fallback) → transcript, then into the content layer (templates, persons, products, MinHash).
  3. SpeechBrain ECAPA speaker embedding → new **`voice_id` evidence** (same synthetic voice across ads; strength 4, rarity-weighted).
  4. facetorch deepfake score → context only (shown, never linking).
- DoD: DANE 5 goes from "unattributable" to a decision with transcript-based evidence; the voice match is demonstrated on ≥ 2 videos, or reported honestly if none share a voice.

### 3.3 Hunter: live sources (stretch, now in scope)
- **Meta Ad Library API:** `ads_archive` with `ad_reached_countries=PL`, lure phrases from our templates and campaign DNA (e.g. "PILNE", "Temat, o którym mówi cała Polska", celebrity names), known `page_id`s.
  - `ad_snapshot_url` is rendered with Playwright to get the creative and the CTA link, then the landing is captured, then analyzed.
  - Fallback while B2 is pending: the public Ad Library UI via Playwright (demo only, ToS caveat in the docs), plus manual library IDs.
- **Google Ads Transparency:** BigQuery `creative_stats` for advertisers seen in our data (enrichment, not creatives).
- **CERT PL list diff** every hour, and **urlscan pivots** (`expand.py`, already finds new kit domains) daily.
- Scheduler: APScheduler in the worker; `jobs`/`job_runs` tables; the UI shows growth in Kampanie ("dołączyło 3 z Huntera").
- DoD: one scheduled run pulls real PL ads, captures ≥ 1 landing, and auto-attributes it, visible live in the UI.

### 3.4 Browser extension (stretch, now in scope)
- MV3:
  - A content script on `facebook.com` finds sponsored posts (the "Sponsorowane" marker) and extracts advertiser, caption, CTA link and a creative pHash computed in the browser.
  - It sends them to `POST /public/extension/match` and gets back an overlay badge: "Pasuje do znanej kampanii oszustwa", plus "Dlaczego?" with coarse reasons only and "Zgłoś".
  - A report becomes an incident with `source=extension`.
- Popup: the same "Sprawdź" field as the web app (E1/E2 designs).
- **Demo on a local fixture page** that mimics a feed with a fictional sponsored post (reliable and safe), plus a live run on a real feed if the network allows.
- DoD: install unpacked, open the fixture, see the badge, report it, and watch the incident appear in TROP.

### 3.5 White Rabbit (agent investigation)
- A Claude tool-use loop. Tools: `db_search`, `incident_neighborhood`, `crtsh`, `rdap`, `dns_ns`, `urlscan_search`, `certpl_check`, `wayback`, `adlib_search`, `capture` (budgeted, headless), `propose_link`.
- Budget (steps and cost), a steer/stop API, and a streamed `agent.step` / `graph.node_added` / `casefile.delta`.
- The result is a set of candidate domains and incidents with their evidence, then **promote** into the campaign (board 10 "Dodaj do kampanii").
- DoD: from a kit-A domain it finds ≥ 10 sibling domains (urlscan already gave 137 candidates), live in the UI, with a recorded replay for the demo.

### 3.6 Oracle
- **Domain DNA per campaign:** TLD set, lexical grammar (char n-gram LR), NS pair / Cloudflare account, registrar batch window, cert issuer.
- Input: the CT stream (self-hosted certstream-server-go container, or the public certstream). Fallback: crt.sh / Cert Spotter polling for the campaign's TLDs.
- A match becomes a prediction, which becomes confirmed when an ad or landing later shows up. Metric: precision@k on held-out kit-A domains.
- DoD: the Oracle strip in Kampanie shows live predictions; at least one historical backtest ("would have flagged X N hours before its first ad").

### 3.7 Act
- **DSA Art. 16 notice package for a whole campaign:** all ad library IDs, advertisers, domains and evidence, as PDF + JSON. The text is drafted by Sonnet and editable.
- **CERT PL submission draft:** the domains not yet on the list.
- STIX 2.1 bundle (MISP-importable); rules (urlscan query, URL regex, HTML signature) with "test on dataset".
- **Nothing is ever actually sent.** "Wyślij" marks the package as prepared, exports it and logs it, and the UI says so.
- DoD: board 7 flow works end to end on campaign A.

### 3.8 Web app (TROP · Sprawdź direction, `docs/design/README.md` §1 boards 1–14, 4a–4d, Kampanie 5–8)
- Tabs **Sprawdź · Kampanie · Śledztwa**, no login, no chat.
- The Sprawdź field → the six bots wake (Zwiadowca, Tropiciel, Czytelnik, Notariusz, Archiwista, Sędzia), **one per `job.step` SSE event**.
- Then three columns (captured page with outlined findings, evidence filling in live, campaign ranking with a forming graph), then Raport (verdict), then Graf (clickable nodes 4a–4d).
- Kampanie: list by operator with the Oracle strip, the campaign page, the takedown package, the merge view. Śledztwa: boards 9–10. Other outcomes: boards 11 (new), 12 (uncertain), 13 (page down), 14 (trace).
- `/lab` (hidden) holds metrics, ablation and stress test for the methodology part of the pitch. `/sprawdz` is the public page.
- **Frontend starts against a mock API** seeded with the canvas's fictional universe (`docs/design/canvas/BRIEF.md`) and switches to the real API at gate G2.
- `?replay=demo` on every SSE stream for the offline demo.

### 3.9 Docs and submission (required by the task)
- **`docs/METHODOLOGY.md`:**
  - feature acquisition per layer;
  - the evidence model (strengths, rarity, levels, conjunction rule, negatives);
  - the decision states and calibration;
  - evaluation tables from RESULTS;
  - what failed (embeddings and GBM over-linking) and why.
- `docs/DATA_SOURCES.md`: every source, model and library with its license and limits.
  - The InsightFace models aren't used; YuNet/SFace are Apache-2.0 (OpenCV Zoo).
  - Note the Wikidata/Commons photo licenses and that face embeddings are biometric data, kept local.
- `docs/INSTALL.md`: `docker compose up` (judge build, no keys needed: cached VLM fields and enrichment); how to obtain each optional key; how to load the organizer data (`trop db seed --path …`).
- `docs/ATLAS.md`: the campaign patterns we found (kit A tenants, registration batches, the funnel A→C→K, decoys, fake-commenter rosters). The organizers explicitly value this.
- **Enriched dataset export** (`trop export dataset`): the incidents, features and labels as JSONL/CSV for NASK.
- Demo video recorded as a fallback.

---

## 4. Workstreams (run as parallel sessions, each owning its folders)

| WS | Owns | Depends on | First deliverable |
|---|---|---|---|
| **WS1 Engine & ingest** | `backend/trop/{ingest,extract,engine,eval,store}`, `backend/migrations` | — | Port + G-ENGINE regression tests; `trop batch` |
| **WS2 API, worker, deploy** | `backend/trop/{api,worker}`, `deploy/` | WS1 schema | FastAPI from design §7 + SSE + compose, mock mode |
| **WS3 Web** | `web/` | contract (WS2 mock) | Sprawdź → analysis → verdict on the mock |
| **WS4 Media & models** | `backend/trop/media`, `experiments/wcss` → `deploy/wcss/` | WS1 schema | Model gateway, video/ASR/voice, gallery CLI |
| **WS5 Sources** | `backend/trop/{capture,enrich,hunter,oracle}` | WS1 store | Hunter scheduler + Meta API + Oracle stream |
| **WS6 Agent & Act** | `backend/trop/{agent,act}` | WS1, WS5 tools | White Rabbit loop + DSA/STIX package |
| **WS7 Extension & public** | `extension/`, `web/app/sprawdz` (coordinate with WS3) | WS2 public endpoints | Fixture-page badge + report |
| **Integrator (this session)** | `docs/`, contracts, gates, merges | all | Contract files at T0+1h, gate reviews |

Rules: each WS works in its own git worktree/branch and touches only its folders. Contracts (`backend/trop/schema.py`, `openapi.json`, SSE catalogue) change only through the integrator. Organizer data stays in `data/` (git-ignored) even though the repo is private: it's too big for git, and it must never be public.

---

## 5. Contracts (written first, T0 → T0+1h, by the integrator)
1. **`backend/trop/schema.py`** (pydantic):
   - `IncidentDraft` / `Incident` (PLAN §4 plus the RESULTS §4 NEW fields: `kit_tenants`, `lander_ids`, `landing_type_ids`, `chain_urls`, `comment_names`, `path_shapes`, `video`, `asr_text`, `voice_id`);
   - `Evidence {type, layer, level: campaign|operator_only|platform, value, weight, strength, df, N}`;
   - `Decision {state: assign|confirm|ambiguous|new|insufficient, campaign_id?, score, margin, confidence, operator_id?, operation_id?, evidence[]}`;
   - `Campaign`, `Operator`, `Operation`, `Job`/`JobStep` (six bot steps), `Investigation`, `ActPackage`, `OraclePrediction`.
2. **`openapi.json`** generated from FastAPI stubs that match design §7.1, plus the SSE catalogue §7.2 (adding `job.step.bot`, one of the six bot names).
3. **The mock server** serves BRIEF.md's fictional data with the same shapes.
4. **`.env.example`** lists every key with how to get it and "optional" flags.

---

## 6. Quality gates (nothing merges past a red gate)

| Gate | Check |
|---|---|
| **G-ENGINE** | `trop eval` reproduces the RESULTS numbers: sample_v1 B³ 1.00 / ARI 1.00 / LOCO 1.00 / 0 wrong; DANE open-set 9/9, 0 wrong links; perturbation table 0 wrong links. |
| **G-E2E** | `docker compose up` on a clean machine → seed → paste a sample URL/upload a DANE folder → verdict with evidence in the UI in < 60 s (offline mode, no keys). |
| **G-BATCH** | `trop batch data/raw/dane/unpacked` → `results.csv` with campaign + operation columns, no crashes on any of the 10 shapes. |
| **G-DEMO** | The 3-minute script (§8) runs twice in a row live and once fully offline (`?replay=demo`). |
| **G-DOCS** | METHODOLOGY, DATA_SOURCES (licenses), INSTALL, ATLAS present; the repo builds from README alone. |

---

## 7. Timeline (relative to T0 = start of implementation; map to clock time once B4 is known)

| Window | Milestone |
|---|---|
| T0 → +1 h | Blockers B1/B3 cleared; contracts (§5) committed; worktrees and sessions started |
| +1 → +6 h | **G1**: WS1 port passes G-ENGINE; WS2 API in mock mode; WS3 Sprawdź flow on the mock; WS4 gateway + keyframes/ASR on DANE 5; WS5 scheduler + CERT PL/urlscan jobs; WS6 agent loop on cached tools; WS7 fixture badge |
| +6 → +10 h | **G2 integration**: web on the real API; analyze job runs the six bot steps end to end; batch mode; Kampanie list/page from the DB |
| +10 → +16 h | Extras: White Rabbit live in Śledztwa, Act package, Oracle strip, voice evidence, Meta API Hunter (if B2 passed), extension → incident |
| +16 → +20 h | Hardening: G-E2E on a clean machine, G-BATCH, demo recording, offline replay, METHODOLOGY/ATLAS |
| last 3–4 h | Freeze features; rehearse the demo; video backup; submission packaging (repo access for organizers, INSTALL check) |

Cut order if late (last cut first): extension live-on-Facebook (keep the fixture) → Oracle live stream (keep the backtest) → Google BigQuery → voice evidence → Meta API Hunter (keep the public-UI fallback) → White Rabbit live (keep the replay). **Never cut:** G-ENGINE, batch mode, explain views, METHODOLOGY.

---

## 8. Demo script (3 min, every step has an offline fallback)
1. **0:00 Sprawdź.** A judge's URL or file goes in, the bots wake, evidence fills in live, and the verdict is "Dołącza do KMP-A · pewność 0.9x", with chips (pixel, kit tenant, registration batch).
2. **0:40 Raport → Graf.** Click the domain node: same night batch, same Cloudflare account. Click the person node: who is being impersonated.
3. **1:10 New-campaign case.** A DANE item the engine correctly does *not* link: "Nowa kampania (kandydat)", plus "ten sam operator co …" where true.
4. **1:30 White Rabbit** from a kit domain: siblings appear live, N of them not on the CERT PL list.
5. **2:00 Oracle strip.** Domains with certificates before any ad.
6. **2:15 Act.** One package for the whole campaign (DSA + CERT PL + STIX).
7. **2:35 Hunter and the extension.** A sponsored post gets the badge; the report lands in TROP.
8. **2:50 Lab.** 0 wrong links, 9/9 held-out, the ablation, and the methods we rejected and why.

---

## 9. Assumptions we act on (no organizer answers)
- **The hidden test set looks like DANE** (same pool, heterogeneous shapes) and may be run by the organizers themselves → batch mode, a robust ingest, and no keys required.
- **"Kampania" = same operator and same narrative** (persona swaps are the same campaign; a shared funnel is the same *operation*). We report both levels.
- **Cloud processing is allowed.** Raw material may go to Claude. We still prefer WCSS for bulk VLM work (cost, speed), and we log which model saw what.
- **Nothing is sent to platforms or CERT PL** during the hackathon: packages are prepared and exported only.
- **The zgrai bots** (three.js jelly scripts) are our own work and can be shipped in the private repo; check their license before any public release.
