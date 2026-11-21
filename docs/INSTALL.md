# TROP — install and run

TROP runs fully **offline without any API key**. In that mode it uses:
- cached VLM fields for the screenshots,
- cached enrichment,
- recorded demo streams.

Keys only add live capture, live model calls and live sources.

Requirements:
- Docker 24+ with compose v2;
- about 4 GB RAM for the stack (each container has a `mem_limit`, about 5 GB in total);
- for the CLI without Docker: [uv](https://docs.astral.sh/uv/) (Python 3.12 is installed by uv) and Node 20+ for the web app.

Organizer data is **not** in this repository. Copy it into `data/` (git-ignored) as described in §3.

## 1. Quick look: fictional demo universe (no data, no keys)

```bash
docker compose -f deploy/compose.yml --profile mock up -d --build api-mock web
# web:  http://127.0.0.1:13000   (shows the "demo · dane fikcyjne" pill)
# API:  http://127.0.0.1:18002/api/v1/health
```

Every live stream also has a recorded replay: open `http://127.0.0.1:13000/analiza/demo?replay=demo`.

## 2. Full stack on the organizer data (offline mode)

```bash
cp .env.example .env                         # every key is optional; TROP_MODE=offline
# put the data in place (see §3), then:
docker compose -f deploy/compose.yml up -d --build
```

- **web:** http://127.0.0.1:13000
- **API:** http://127.0.0.1:18000/api/v1/health
- **Postgres:** 127.0.0.1:55433 (user/db `trop`)
- **Redis:** 127.0.0.1:56379

On first start, the one-shot `seed` service restores `data/seed/trop_seed.dump` into Postgres. When there is no dump, the engine falls back to the JSON corpus in `data/corpus/`. `data/` is mounted read-only.

Then, in the web app: **Sprawdź** → drop a DANE folder as a `.zip` (or a screenshot / HAR / video) → the six bots run → verdict with evidence. To analyse a whole folder set, use **Lab → Importuj zbiór**.

To publish the ports on another interface, set `TROP_BIND=10.8.0.3` (or similar).

## 3. Loading the organizer data

```
data/raw/sample_v1/p1 … p15        # teaser / CTF sample (one folder per incident)
data/raw/dane/DANE.zip             # official dataset; unpack safely:
cd experiments && uv run python -I safe_unzip.py ../data/raw/dane/DANE.zip ../data/raw/dane/unpacked
```

Build the engine corpus, calibration and DB seed from it:

```bash
cd backend
uv sync
uv run trop engine build-corpus          # labelled known corpus -> data/corpus/known.json
uv run trop engine calibrate             # isotonic p(score) -> trop/engine/calibration/
uv run trop db migrate && uv run trop db seed   # into $DATABASE_URL
uv run trop db snapshot                  # -> data/seed/trop_seed.dump (for the compose seed)
```

Optional extras:
- **Face gallery (6,305 public figures).** It is biometric data, so we keep it local and don't distribute it. Rebuild it with:

  ```bash
  WIKIMEDIA_UA="name/version (contact: you@example.org)" uv run python -m rp.gallery fetch --min-sitelinks 5   # in experiments/
  uv run trop gallery build && uv run trop gallery install
  ```

  Without the gallery, the persons layer only uses names found in the text.
- **Model cache.** `uv run trop media seed-cache` imports the precomputed VLM outputs, so screenshots get ad fields offline.

## 4. Batch mode (hidden test set)

The input is one sub-folder per incident, in any of the formats from `experiments/DATA_NOTES.md`: a folder or a `.zip`.

```bash
cd backend
uv run trop batch /path/to/folders --out results.csv      # also writes results.json with the evidence
```

`results.csv` has one row per item. Key columns:
- `decision`: `assign`, `confirm`, `ambiguous`, `new` or `insufficient`;
- `campaign` (known `KMP-…` or a new cluster id) with `campaign_score` and `campaign_p`;
- `operator`, `operation`, `variant`, `same_operator_as`, `duplicate_of`;
- `coverage` and `top_evidence`.

Both granularities are there because the label definition is not known: campaign (same operator and narrative) and operation (shared funnel).

The same mode is in the web app under **Lab → Importuj zbiór**, which ends with a download of `results.csv`.

## 5. Reproducing the evaluation (G-ENGINE)

```bash
cd backend
uv run trop eval          # sample_v1: B³ 1.00, ARI 1.00, LOCO 1.00 / 1.00, 0 wrong links, perturbations 0 wrong
uv run trop eval --dane   # held-out DANE: 9/9 open-set, 0 wrong links, incremental + joint B³ 1.00
uv run pytest
```

The research code behind `experiments/RESULTS.md` is frozen in `experiments/` (`uv run python run_a_evidence.py …`, see RESULTS §7).

## 6. Optional keys (live mode, `TROP_MODE=live`)

| Key | Enables | How to get it |
|---|---|---|
| `GEMINI_API_KEY` | video pass, ASR, LLM (White Rabbit, notices, adjudicator) | https://aistudio.google.com/apikey |
| `OPENROUTER_API_KEY` | ad-screenshot VLM (`qwen/qwen3.6-35b-a3b`), LLM fallback | https://openrouter.ai/keys |
| `META_ACCESS_TOKEN` (+ app id/secret) | Hunter: Meta Ad Library `ads_archive` | identity verification + developer app, see `docs/db/META_AD_LIBRARY_ACCESS.md` |
| `URLSCAN_API_KEY` | urlscan results/DOM (search works without a key) | https://urlscan.io/user/profile/ |
| `IPINFO_TOKEN`, `CERTSPOTTER_API_KEY` | ASN enrichment, CT polling | ipinfo.io, sslmate.com |
| `GOOGLE_APPLICATION_CREDENTIALS` + `GOOGLE_CLOUD_PROJECT` | Google Ads Transparency (BigQuery) | `gcloud auth application-default login` |

Every paid call is logged in `data/logs/spend.jsonl`, and a hard cap is set by `LLM_BUDGET_USD`.

Live URL capture runs headless Chromium in the `trop-capture` sandbox image: read-only, no forms, no logins, politeness budget. Build it with:

```bash
docker build -t trop-capture -f backend/trop/capture/Dockerfile backend
```

## 7. Browser extension

See `extension/README.md`. In short:
1. Load `extension/` unpacked in Chrome.
2. Open `extension/fixture/feed.html`. The demo feed is served with `python -m http.server 13150 --bind 127.0.0.1`.
3. The fictional sponsored post gets the badge, and "Zgłoś" creates an incident.
