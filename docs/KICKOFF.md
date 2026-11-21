# TROP — overnight build kickoff (home PC)

> Written 2026-11-21 ~22:15 (Europe/Warsaw) by the planning session on the laptop, which is now closed.
> You are the **lead/integrator** that builds TROP overnight on this machine. Dawid (the user) is **asleep** until the morning, so work autonomously within the permissions below and leave a clear morning report.
> Everything that was decided is in the docs listed in §1. Don't re-litigate those decisions; build.

---

## 0. Mission and clock
- **Goal:** ship TROP ("follow the fake"), the HackNation 2026 entry for NASK's task "Kolekcjoner fejków". It clusters scam ads into campaigns, operators and operations with explainable evidence. It needs a custom dashboard, a working end-to-end demo and methodology docs.
- **Deadline (assumed; not confirmed):** submission **2026-11-22 ~11:00**.
  - **Feature freeze 10:00.**
  - **Morning report ready by 08:00** (§6).
- **Gates, mapped to clock time** (check `TZ=Europe/Warsaw date`):

  | Gate | By | Contents |
  |---|---|---|
  | **Contracts** | ~23:15 | schema, compose, `.env.example`, `docs/CONTRACTS.md` |
  | **G1** | ~03:00 | each workstream's first deliverable, G-ENGINE green |
  | **G2** | ~06:00 | integrated E2E + first deploy to `trop.b.solvro.pl` + G-BATCH |
  | **Extras** | ~08:30 | White Rabbit live, Act package, Oracle strip, voice, extension, Hunter |
  | **Hardening** | 08:30–10:00 | G-E2E clean-machine test, docs, offline replay, demo recording |

  If time is short, use the **cut order** in `docs/IMPLEMENTATION.md` §7. **Never cut:** G-ENGINE, batch mode, explain views, METHODOLOGY.

## 1. Read first (in this order)
1. `docs/IMPLEMENTATION.md`: **the build plan (authoritative)**. Architecture, hosting (§1a), code consolidation (§2), per-pillar definitions of done (§3), workstreams (§4), contracts (§5), gates (§6), timeline and cut order (§7), demo script (§8), assumptions (§9).
2. `experiments/RESULTS.md`: the chosen method, with numbers.
   - **Port the evidence engine (`experiments/rp/evidence.py`, `cluster.py`) as is.**
   - §4 is the end-to-end flow, strengths, thresholds and decision states.
3. `experiments/DATA_NOTES.md`: every input format the ingest must handle (sample_v1, organizer bundle, the 10 DANE shapes).
4. `docs/design/README.md` and `docs/design/canvas/BRIEF.md`: screens, flows, component inventory, **API contract (§7)**, the fictional demo universe.
   - The **current UI direction** is the "TROP · Sprawdź" boards:
     - tabs **Sprawdź · Kampanie · Śledztwa**, no login, no chat;
     - six detective bots, one per pipeline step;
     - verdict → Raport → Graf (clickable nodes 4a–4d);
     - Kampanie (by operator, Oracle strip, campaign page, takedown package, merge);
     - Śledztwa (White Rabbit tree);
     - other outcomes: new / uncertain / page down / trace.
   - Canvas sources: `docs/design/canvas/project/*.dc.html`; tokens in `docs/design/canvas/assets/rp.css`; bots in `jelly-overlay-detective.js`.
5. `docs/db/DB_AND_SCRAPING.md` (plus `SOURCES_FACTSHEET.md`, `META_AD_LIBRARY_ACCESS.md`): the 57-table schema, ingest/enrich/capture/hunter prototypes, source matrix.
6. `docs/PLAN.md`: the product vision (pillars, wow features). Where it disagrees with 1–5, those win.

## 2. State of this machine
- **Repo:** `~/hacknation/trop`, branch `plan/trop-foundation` (2 commits on top of `main`).
  - Remote: `origin` = `https://github.com/Solvro/web-hacknation-trop` (**private**). `gh` is logged in as `dawidlinek`.
- **`.env`** (git-ignored, verified working 21.11):
  - `GEMINI_API_KEY`: AI Studio endpoint, not Vertex. Models `gemini-flash-latest`, `gemini-pro-latest`, `gemini-3.5-transcribe`.
  - `OPENROUTER_API_KEY`: $100 limit. Screenshot model `qwen/qwen3.6-35b-a3b`; adjudicator fallback `qwen/qwen3.8-27b`.
  - `META_*`: Meta Ad Library `ads_archive` works for PL.
  - `URLSCAN_API_KEY`, `IPINFO_TOKEN`, `CERTSPOTTER_API_KEY`, `WIKIMEDIA_UA`.
  - `COOLIFY_URL` / `COOLIFY_API_TOKEN`: Solvro Coolify admin token, so be careful.
  - `GOOGLE_CLOUD_PROJECT=gen-lang-client-0264807540`. **BigQuery credentials (gcloud ADC) are NOT set up on this machine**, so the Google Ads Transparency source is optional; skip it and note that in STATUS.
  - `ANTHROPIC_API_KEY` is intentionally absent: **Gemini is the default LLM**.
- **Database:** Postgres 16 + pgvector at `127.0.0.1:55432`, container `redpill-db-postgres-1`, started from `db/docker-compose.yml` (user/db `redpill`, dev password `redpill_dev`).
  - It already holds **1,752 incidents** (1,588 Meta ads from the Hunter prototype, 137 urlscan, 15 sample_v1, 10 DANE, 2 own captures) with enrichment.
  - A dump is at `~/hacknation/redpill.dump`.
- **`data/`** (git-ignored, 13,666 files):
  - `raw/sample_v1` (15 incidents), `raw/dane/unpacked` (10 incidents), `raw/task` (task PDFs);
  - `experiments/` (incidents JSON, VLM outputs, `face_gallery/` with **6,305 people / 7,364 photos**, SFace index);
  - `captures/` (5.1 GB), `artifacts/`.
- **Tools:** uv 0.12 (`~/.local/bin`) — use **Python 3.12 via uv**; the system Python is 3.14. Node 26 LTS via fnm (`eval "$(~/.local/share/fnm/fnm env --shell bash)"`). Docker 29.6, git, gh. **No sudo**, so ffmpeg comes from Debian packages inside Docker images, or `imageio-ffmpeg` from PyPI.
- **Shared machine.** Other projects run here: tt-iso staging, techtree, riskminer (often running heavy pytest), obsidian, coolify-proxy (80/443/8080), several Postgres containers on 5432–5434, and ports 1025, 3000, 3128, 4000–4002, 5173, 7000–7003, 8000, 8025, 8102. The GPU (4 GB) is already full.
  - **TROP ports: Postgres 55432 · Redis 56379 · API 18000 · web 13000**, compose project `trop`, bound to `127.0.0.1` / `10.8.0.3`.
  - **Never stop, modify or reuse other projects' containers, volumes or ports.**
- **WCSS** (`ssh ui`, SLURM, PBR grant): optional, batch only (bulk VLM, embeddings, training). It's unstable for live use. See `experiments/wcss/README.md`. Skip it if unreachable.

## 3. Decisions in force (do not re-open)
- **Name and modules:** TROP — Déjà Vu (matching engine), White Rabbit (investigator agent), Oracle (early warning), Hunter (sources), Act (takedown packages).
- **Method:** the RESULTS.md evidence engine, ported unchanged.
  - Every pair gets two scores, `score_campaign` and `score_operator`.
  - Assign when max-linkage ≥ 5 with a margin ≥ 1; `confirm` covers 1–5; `new` is < 1; `ambiguous` and `insufficient` as defined there.
  - The chain-domain and conjunction rules apply. The levels are campaign / variant / operator / operation.
  - Embeddings, the GBM and the LLM adjudicator are support or veto only.
  - The UI's "pewność" is a Platt/isotonic calibration of `score_campaign`. Conformal τ(α) appears in /lab only.
- **Models:**
  - **Screenshots:** OpenRouter `qwen/qwen3.6-35b-a3b` → Gemini Flash → EasyOCR/cache.
  - **Video:** Gemini first (whole video and audio in one call), with ffmpeg keyframes + ASR as fallback.
  - **ASR:** `gemini-3.5-transcribe` → faster-whisper on CPU.
  - **LLM tasks:** Gemini (Pro for White Rabbit with function calling; Flash for notices, summaries and the adjudicator) → OpenRouter fallback.
  - Every model response is cached by input sha256, so the judge build runs without keys.
  - **Person identity only from the SFace face gallery, never from a VLM/LLM.**
  - Re-run the 105-pair adjudicator benchmark on Gemini before trusting it (0 false links required).
- **Stack:**
  - **Frontend:** Next.js + TS + Tailwind + shadcn/ui, Sigma.js/graphology, the zgrai three.js bots. **Our own dashboard, no Streamlit/Gradio.**
  - **Backend:** FastAPI + arq/Redis workers, Postgres + pgvector, artifacts on a local FS volume (MinIO images are no longer pullable).
  - Graph analytics in Python, with a GraphML/Cypher export.
- **Deploy target:**
  - **Where:** Solvro Coolify `devops.solvro.pl` (v4.7.6), server **`solvro-stacja-web`** (uuid `qwokkw440cgks8oswwc8o8ks`), project **"Hackatony"**, Traefik wildcard `*.b.solvro.pl`, so **`trop.b.solvro.pl`** with the API under `/api`.
  - **Memory budget ≤ 5 GiB total** with `mem_limit` on every container: Postgres 1.5 G · Redis 256 M · API 1 G · worker 1.5 G · web 512 M. The server has only ~9 GiB RAM free and runs 97 other containers.
  - No local ML models in the deployed image.
  - Deployment works only if the Coolify GitHub App can read `Solvro/web-hacknation-trop`. Check the sources via the API. If it can't, write that in STATUS and keep the demo on this machine.
- **Hidden test hedge:** `trop batch <dir|zip>` plus UI "Importuj zbiór" → `results.csv`, at both **campaign and operation** granularity.

## 4. Standing permissions from Dawid (valid for this overnight run)
**Allowed:**
- Create branches and worktrees; commit; **merge into `main` after a gate passes**; **push to `origin`**.
- **Create and redeploy one TROP resource** in Coolify project "Hackatony" on solvro-stacja-web.
- Run headless live captures of scam landing pages from this machine:
  - never submit forms, never log in anywhere, keep the politeness budget in `scrapers/capture/`;
  - never open them in a desktop browser.
- Spend on the Gemini and OpenRouter APIs, **≤ $30 total overnight**. Log spend in STATUS.
- Use WCSS batch jobs if helpful.

**Not allowed:**
- Touch other projects on this machine or other resources and settings in Solvro Coolify (no enabling metrics, no other servers, no deleting anything).
- Publish organizer data publicly (`data/` stays git-ignored; the private repo is fine for docs).
- Send real takedown notices or CERT PL reports: Act only prepares and exports.
- Create accounts or apply for API access.

**Commits and PRs must never mention Claude:** no `Co-Authored-By: Claude…` trailer, no "Generated with Claude Code", no mention in the body.

## 5. How to run the night
1. **Contracts (you, first, ~45 min).**
   - `backend/` uv project (Python 3.12, package `trop`).
   - `backend/trop/schema.py`: pydantic models for:
     - `IncidentDraft` / `Incident` (PLAN §4 plus the RESULTS §4 NEW fields: `kit_tenants`, `lander_ids`, `landing_type_ids`, `chain_urls`, `comment_names`, `path_shapes`, video/asr/voice);
     - `EvidenceItem`, `Decision` (states `assign|confirm|ambiguous|new|insufficient`), `LinkExplanation`, `Campaign*`, `Operator`, `Operation`, `Job`/`JobStep` (six bot steps: Zwiadowca, Tropiciel, Czytelnik, Notariusz, Archiwista, Sędzia), `Investigation`, `ActPackage`, `OraclePrediction`, `TriageItem`, `HunterSource`, `CheckResult`;
     - all mirroring `docs/design/README.md` §7.3.
   - `deploy/compose.yml` (project `trop`, ports above, `mem_limit`s) and `deploy/compose.coolify.yml`.
   - `.env.example` (every key with how to obtain it and optional flags).
   - `docs/CONTRACTS.md`: folder ownership per workstream, branch naming `ws/<n>-<name>`, how contracts change (only through you), the SSE event catalogue (design §7.2), the port map.
   - Commit, then push.
2. **Workstreams** (`docs/IMPLEMENTATION.md` §4).
   - Run them as **parallel subagents, each in its own git worktree** (`isolation: worktree`).
   - At most ~5 running at once; this machine is shared.
   - Each brief: the owned folders, that workstream's definition of done from §3, its gate, the commit rules (no Claude), and "don't touch other folders; contracts change only via the lead".
   - Suggested first wave: **WS1 engine+ingest**, **WS2 API+worker+deploy (mock mode first)**, **WS3 web**, **WS4 media (Gemini video/ASR, faces)**, **WS5 sources (capture/enrich/hunter/oracle)**.
   - Second wave as capacity frees up: **WS6 White Rabbit + Act**, **WS7 extension + public `/sprawdz`**.
3. **Integrate at each gate.**
   - Merge the workstream branches into an integration branch.
   - Run **G-ENGINE**: `trop eval` reproduces RESULTS (sample B³ 1.00 / 0 wrong links; DANE 9/9 open-set, 0 wrong links).
   - Fix, merge into `main`, push.
   - From G2 on, redeploy `trop.b.solvro.pl` and smoke-test it (curl the API health check and one analysis).
4. **Keep it demo-safe:**
   - a seeded DB snapshot;
   - `?replay=demo` recorded SSE streams;
   - cached model outputs;
   - a 3-minute script that runs offline (`docs/IMPLEMENTATION.md` §8);
   - record a demo video if you can (e.g. a Playwright screen capture of the flow).
5. **Docs required by the task:**
   - `docs/METHODOLOGY.md` (features, evidence model, decisions, evaluation with numbers, what failed);
   - `docs/DATA_SOURCES.md` (every source, model and library with its license; biometric note for faces);
   - `docs/INSTALL.md` (`docker compose up`, no keys needed in offline mode);
   - `docs/ATLAS.md` (campaign patterns found);
   - `README.md` (pitch, quickstart, links).

## 6. Morning report (Dawid reads this first)
Keep **`docs/STATUS.md`** updated at every gate and committed. By 08:00 it must have:
- what works end to end;
- the URLs (`trop.b.solvro.pl`, local `http://10.8.0.3:13000`);
- the exact demo steps;
- gate results with numbers;
- what was cut and why;
- known bugs;
- API spend;
- anything that needs Dawid: decisions, keys, a Coolify GitHub App grant, the BigQuery login.

End your run with a short summary pointing to STATUS.md.

## 7. Gotchas
- **Line endings:** files made on Windows may show as modified only because of CRLF. Use `git diff --ignore-cr-at-eol` before trusting a diff.
- **WCSS SSH** is rate-limited per IP. Reuse the ControlMaster described in `experiments/wcss/README.md`.
- **The DANE 14 screen recording is 339 MB:** trim it with ffmpeg before uploading to Gemini.
- **Real scam data:** never follow `gclid`/`fbclid` links outside the capture container.
- **Biometrics:** the face gallery is real people's biometric data. Keep it local (`data/`), and use it only to flag impersonation.
- **Data rule:** organizer files (`data/raw/sample_v1`, `data/raw/dane`) must never be made public.
