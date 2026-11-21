# The three exploration sessions (21.11): briefs, outputs and decisions they fixed

> All three ran on the laptop in parallel, sharing the repo folder, from ~12:00 to ~22:00 on 21.11. Their outputs are in the repo and in `data/`. This file keeps what each was asked to do and the decisions that exist only in their conversations.
> The product was renamed RED PILL → **TROP** mid-day, so older docs still say RED PILL.

## Shared background given to all three
- **Task:** NASK's "Kolekcjoner fejków / Follow the Fake" (HackNation 2026, ~2k participants, 30k PLN). Cluster scam ads (celebrity/deepfake, fake-news pre-landers, fake investment and health products on Meta ads → short-lived landing domains) into campaigns using text, visual, semantic and infrastructure signals. Assign new material to a known campaign or flag a new one, explain every link, and ship a GUI, Docker and methodology docs.
- **Jury weights:** method 30%, features/data sources 30%, end-to-end demo 15%, interpretability 15%, deployability 10%. The hidden test set holds new variants of known campaigns plus unrelated campaigns, so refusing wrong links matters as much as making right ones.
- **User preferences:** aim big to win. Do not default to the tech the brief suggests (Streamlit/Gradio/Neo4j): a custom Next.js dashboard + FastAPI + Postgres/pgvector + workers.
- **Hard rules:**
  - organizer data never public (`data/` git-ignored);
  - commit nothing, switch no branch (exploration only);
  - real scam sites: headless only, never submit forms;
  - don't apply for accounts or keys on the user's behalf.
  - (Later lifted: cloud LLMs are allowed; the repo is private.)

## Session 1 — Approach bake-off (WCSS + laptop) → `experiments/`
**Brief.** Try the approaches on this PC and WCSS and decide the analysis flow, combining as many signals as possible and measuring what each adds:
1. Label sample_v1 into campaigns and operator families, with evidence.
2. Write throwaway loaders and extractors (tracking IDs, kit endpoints, URL grammar, asset hashes, DOM MinHash, templates with names masked, OCR/VLM, pHash, embeddings, infra).
3. Compare, with B³-F1 / ARI / LOCO "should not link" / robustness / cost:
   - a) the rarity-weighted evidence graph;
   - b) embeddings + HDBSCAN;
   - c) a LightGBM linkage model with SHAP;
   - d) a VLM on WCSS vs OCR for screenshots;
   - e) faces against a gallery of impersonated people;
   - f) RDAP/DNS/crt.sh enrichment;
   - g) conformal open-set;
   - h) an LLM adjudicator for the uncertain band.
4. Set up WCSS (PBR grant, sbatch, vLLM tunnel).
5. Download and unpack DANE.zip and rerun everything on it.

**Outputs:**
- `experiments/RESULTS.md`: the decision. The evidence engine won, with 0 wrong links and DANE 9/9.
- `experiments/DATA_NOTES.md`; `labels.yaml`, `labels_dane.yaml`, `ad_truth.yaml`.
- Code in `experiments/rp/` and `run_*.py`; `experiments/wcss/README.md` with the sbatch scripts.
- Data: `data/experiments/` (incidents JSON, VLM outputs) and `data/experiments/face_gallery/`: 6,305 people / 7,364 photos, built from Wikidata + Commons with `WIKIMEDIA_UA`, 0 wrong names, 9/11 found.

## Session 2 — App and flow design (Claude Design canvas) → `docs/design/`
**Brief.** Design the whole app in Claude's design canvas: IA and navigation; every screen; explainability components (evidence chips with weight and rarity, why linked / why not, template diff, coverage, new-campaign display); key flows (new material → verdict; campaign → Act → DSA; agent investigation; hunter/oracle alert → triage; extension + public "Sprawdź reklamę"; the 3-minute judge demo); visual identity; Polish copy. Fictional data only. Deliver `docs/design/README.md` with screens, flows, a component inventory and the data/API each screen needs.

**Outputs:**
- Canvas https://claude.ai/artifact/9ZdsnJ3Mo4Z3KFGJy4QG6W (private to Dawid's account).
- `docs/design/README.md` (canvas map, IA, screens, explainability, component inventory, **API contract §7**: endpoints, SSE events, TS shapes, flows).
- `docs/design/canvas/BRIEF.md` (fictional demo universe), board sources `canvas/project/*.dc.html`, CSS tokens, bot scripts (`jelly-overlay-detective.js`).

**UI decisions fixed with Dawid during that session** (they override older parts of the design README):
- **Current direction = canvas page "TROP · Sprawdź"** (boards `Sprawdz`, `Sprawdz-2-Analiza`, `-3-Raport`, `-4-Graf`, 4a–4d, Kampanie 5–8, Śledztwa 9–10, outcomes 11–14).
  - **Light zgrai look:** Geist font, black on white, top tabs (Sprawdź · Kampanie · Śledztwa), no sidebar.
  - **No login, no avatar, never a chat UI.**
  - Only the first screen is zgrai-like: one field ("Link, plik albo ślad") with sleeping jelly bots and a "Sprawdź" button. Everything after it grows out of the analysis view: six detective bots, one per pipeline step (Zwiadowca, Tropiciel, Czytelnik, Notariusz, Archiwista, Sędzia), each with its own costume. The view shows live evidence, the captured page with findings outlined, and a live campaign ranking.
- Oracle, operators and people live **inside Kampanie**, not in their own tabs. Reports (Zgłoszenia) live inside each campaign. The separate queue (Kolejka) was dropped: confident items from Hunter, Oracle or the extension join campaigns on their own.
- Search **is** the Sprawdź field: a link, a file, or a single trace (domain, pixel, name).
- **Copy style:**
  - plain descriptive headlines, not IDs;
  - **no conformal/α jargon and no "why not" lines in the UI**, so the verdict reads "KMP-017 · pewność 0.94";
  - one primary action plus a text link, never rows of buttons.
- **8 evidence layers** in the UI: tracking, kit, infra, content, persons, visual, ad, media. **Five decision states:** assign, confirm, ambiguous, new, insufficient.
- The zgrai-style chat/queue screens were rejected and parked on the page "Odłożone".

## Session 3 — DB schema + data acquisition and scraping → `docs/db/`, `db/`, `scrapers/`
**Brief.** Design the database and the data-acquisition layer, and prove it with prototypes:
1. A normalized Postgres 16 + pgvector + pg_trgm schema from the Incident model: provenance, incidents/ads/landings/captures/artifacts, observables as typed entities (the inverted index for blocking and IDF), vectors, evidence edges, campaigns/operators with membership history, labels/feedback, enrichment cache, hunter jobs, oracle candidates, audit; plus dedupe, incomplete data, incremental re-clustering and scale.
2. A source matrix for every source (what it gives, auth, limits, cost, ToS, cadence, tables filled, feasibility).
3. Landing-capture design (Playwright anti-cloaking profiles, HAR, full redirect chain, organizer-compatible bundle layout, sandbox, politeness).
4. Prototypes: migrations + docker-compose + seed loader; scrapers for the CERT PL list, crt.sh, RDAP+DNS, Playwright capture; Meta Ad Library access steps for the user.

**Outputs:**
- `docs/db/DB_AND_SCRAPING.md` (57 tables, ER diagrams, source matrix, capture design, scheduling, open questions, hand-off notes), `SOURCES_FACTSHEET.md`, `META_AD_LIBRARY_ACCESS.md`.
- `db/migrations/0001–0012`, `db/docker-compose.yml`, `db/seed_sample.py`.
- `scrapers/` (ingest adapters, enrich, capture, hunter: Meta API + Google ATC + urlscan expansion).
- **The live database** (now restored on the home PC): 1,752 incidents, including 1,588 Meta ads pulled by the Hunter prototype and 137 urlscan candidate domains (most not on the CERT PL list).
- Findings in `data/notes/DB_FINDINGS_sample_v1.md`: kit-A domains came from two registration batches seconds apart, behind one Cloudflare account, certified 30 minutes after registration. The kit-A "operator" CAPI gateway turned out to be a shared service, so it should get lower weight.
