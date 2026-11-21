# TROP — data sources, models, libraries and licences

> Contains identifiers derived from organizer data — do not publish outside the private repository.

Status: 2026-11-21. Facts come from `docs/db/SOURCES_FACTSHEET.md` (read 2026-11-21), `docs/db/DB_AND_SCRAPING.md` §3,
`docs/IMPLEMENTATION.md` §1, `experiments/RESULTS.md` and the `pyproject.toml` files. Anything not confirmed by one of
those is marked **to verify**. This is an engineering summary, not legal advice.

## 1. Rules that apply to everything

- **Organizer data is never published.** `sample_v1` and `DANE.zip` stay in `data/` (git-ignored) and on the WCSS
  Lustre volume. The repo is private; the task and terms forbid only public distribution.
- **No keys needed to run.** Without keys TROP starts in offline mode: cached VLM/LLM/enrichment outputs and recorded
  streams (`TROP_MODE`, `TROP_REPLAY`). Keys live in a git-ignored `.env` (`.env.example` lists them, all optional).
- **We never contact scam hosts from analyst machines in the enrichment path.** Enrichment queries third-party
  registries (RDAP, CT, DNS, urlscan). Captures of landing pages run only in the sandboxed Playwright worker, which
  never submits forms and never solves captchas.
- **Every external response is cached** (per eTLD+1 for enrichment, per input sha256 for model calls) so a judge build
  replays without network.

## 2. Data sources

### 2.1 Datasets

| Source | Access | Auth | Terms / licence | What we store |
|---|---|---|---|---|
| **Organizer `sample_v1`** (15 incidents p1–p15, teaser CTF backup) | Local folder `data/raw/sample_v1/` | none | Organizer data, **never published** | Extracted features (`incidents.json`), hashes of assets, screenshots and HAR/HTML only in git-ignored `data/` |
| **Organizer `DANE.zip`** (10 incidents d1…d61 from a larger numbered pool; 509,743,633 B) | MEGA link from the task, downloaded on WCSS (per-IP quota), unpacked with `safe_unzip.py` | none | Organizer data, **never published**; sha256 `9582ac56…49d0` | As above; videos kept as paths, not analysed offline |

Neither dataset is committed, uploaded to a public host or used for training any published model. Hand-made labels
(`experiments/labels*.yaml`) quote organizer identifiers and stay in the private repo.

### 2.2 Live and enrichment sources

| Source | Access method | Auth | Rate limits (as measured / documented) | Terms / licence | What we store |
|---|---|---|---|---|---|
| **Meta Ad Library API** (`ads_archive`, Graph v27.0) | REST, Hunter job every 2 h (`ad_reached_countries=["PL"]`, Polish lure phrases, known `page_id`s) | Identity-confirmed user token (60-day long-lived), `META_ACCESS_TOKEN` | Unpublished; error 613 = back off; our budget 200 calls/run | Platform terms: API is the only allowed programmatic access; snapshots only for analysis of individual ads. **No scraping of the web UI** (manual lookups only). Free | Ad text, link title/caption, page id/name, delivery dates, EU reach, targeting, `ad_snapshot_url`; our own copy because EU ads vanish 1 year after last impression. The API returns **no landing URL and no media URLs** |
| **urlscan.io** | REST search pivots (`page.domain`, `hash:`, `page.ip`, `page.asn`, `page.tlsIssuer`, `domainAgeDays`) | `URLSCAN_API_KEY` (search is keyless but 30 req/min, 30 days back; `/result`, `/dom`, `/responses` need a key since 2026-05-04) | Free account: 1,000 searches/day, 10,000 result fetches/day; we throttle to 120/min | **Commercial use needs written permission** (terms) | Pivot results as relations/candidates (domain, IP, hash, timestamp), not page bodies |
| **crt.sh** (primary) and **Cert Spotter** (fallback) | crt.sh JSON `?q=%25.<domain>&output=json`; Cert Spotter `/v1/issuances` | none (Cert Spotter optional `CERTSPOTTER_API_KEY`) | crt.sh 5 req/min/IP, frequent 502s, Sectigo rebuild announced 2026-05-28 (replicas freeze); Cert Spotter keyless 100 queries/h | CT logs are public. Cert Spotter keyless use is **personal/evaluation only** (to verify for a production deployment) | Issuer, serial, SANs, validity per domain (e.g. 257 certs for 14 domains) |
| **RDAP** (IANA bootstrap `dns.json`, per-TLD servers) | HTTPS GET straight to the registry | none | Unpublished per registry; honour 429/`Retry-After`; rdap.org redirector 10 req/10 s (not used) | GDPR-redacted registrant data; gTLD WHOIS optional since 2025-01-28 | Registrar, created/expiry/updated, nameservers, status → `registrar`, `ns_set`, `registration_batch` evidence. 14/14 sample domains resolved |
| **DNS** (+ Team Cymru IP→ASN) | `dnspython` against public resolvers; ASN via `origin.asn.cymru.com` TXT | none | Resolver-bound | — | A/AAAA/NS/MX/TXT, ASN/prefix; our own passive-DNS history in `observable_relations` |
| **IPinfo Lite** | REST `api.ipinfo.io/lite/{ip}` | `IPINFO_TOKEN` (free) | Unlimited | **CC BY-SA 4.0 — attribute IPinfo in the UI** | Country, ASN, AS name/domain per IP (cached 30 days) |
| **CERT Polska warning list** (`hole.cert.pl/domains/v2/`) | Conditional GET (ETag), poll ≥ every 5 min (we use 10 min) | none | 126,597 records (22.5 MB) measured; v2 keeps the last 6 months | Any use incl. commercial; must not imply endorsement; statutory basis in the 2023 anti-abuse act | `domains.json` snapshots and diffs (insert/delete dates) as labels and early-warning signal |
| **Wayback Machine CDX** | `web.archive.org/cdx/search/cdx` on demand (agent pivot) | none | Anti-automation 429 blocking since 2026-09-15; low volume only | Internet Archive terms | First/last capture, digests — enrichment only |
| **Google Ads Transparency Center** (BigQuery `bigquery-public-data.google_ads_transparency_center`, **optional**) | BigQuery SQL: `creative_stats`, `removed_creative_stats` | Google account via Application Default Credentials (`gcloud auth application-default login`) + `GOOGLE_CLOUD_PROJECT`; sandbox project needs no billing | 1 TiB/month free; always select explicit columns and set `maximum_bytes_billed` | Google ToS + Ads Transparency Center terms; no official API | Advertiser id/name/verification, creative id and page URL, PL first/last shown, Google's removal reasons (weak labels). **No ad text, no landing URL, no media.** Loaded as a registry, not as incidents. Without ADC the Hunter skips this source |
| **Wikidata** (SPARQL) | One query for Polish citizens with a portrait, ≥ 5 Wikipedia editions, alive or died after 2000; international figures by en-wiki title | none; descriptive User-Agent with a contact address in `WIKIMEDIA_UA` (kept out of the repo) | Serial requests (parallel Commons calls were rate-limited) | Wikidata data are CC0 | QID, label, image file name → local gallery metadata |
| **Wikimedia Commons** | Portraits (P18) and up to 6 category photos for 534 people (top 500 + 25 international + 25 curated) | none; same User-Agent rule | Fetch ≈ 20 min / 484 MB + extras 12 min / 167 MB | **Each image carries its own licence (CC BY, CC BY-SA, public domain, …)** — attribution/share-alike obligations apply if images were ever redistributed. We do not redistribute them | Local files in `data/` only (git-ignored); only the SFace embeddings (see §5) are used at runtime |
| **User / extension reports** | `POST /api/v1/public/*` | none (pseudonymous) | Our API rate limit | User-submitted; salted reporter hash only | URL, library id, screenshot, note |

Evaluated, **not used** in the shipped path: TikTok Commercial Content API (needs approval; commercial eligibility
unclear), Shodan InternetDB (non-commercial), OpenPhish feed (non-commercial, no redistribution; off by default),
mnemonic passive DNS (10 req/min; agent pivot only), PhishTank (registration closed), URLhaus (ToS of 2026-10-21 forbids
AI training without consent), VirusTotal / Safe Browsing (non-commercial), Meta Ad Library web UI (ToS), live
CaliDog certstream (dead; a self-hosted certstream-server-go would be needed for the Oracle stream).

## 3. Models

All model calls go through one gateway (`media/gateway.py`), which caches responses by input sha256.
Provider order per task (IMPLEMENTATION §1):

| Task | Order |
|---|---|
| Ad screenshots (advertiser, library id, caption, decoy, vertical) | OpenRouter `qwen/qwen3.6-35b-a3b` → Gemini flash → EasyOCR + offline cache |
| Video ads | Gemini (`gemini-flash-latest` bulk, `gemini-pro-latest` hard cases) → ffmpeg keyframes + VLM + ASR |
| Speech-to-text | `gemini-3.5-transcribe` → faster-whisper |
| LLM tasks (White Rabbit agent, notices, summaries, adjudicator) | Gemini `-latest` aliases → OpenRouter `qwen/qwen3.8-27b`; Claude optional when `ANTHROPIC_API_KEY` is set |

### 3.1 Shipped

| Model | Role | Where it runs | Licence / terms |
|---|---|---|---|
| **Qwen3.6-35B-A3B** (OpenRouter `qwen/qwen3.6-35b-a3b`) | Ad-screenshot VLM; 14/14 advertiser, library id and caption on sample_v1 (2.7 s/img on WCSS) | OpenRouter (cloud); also WCSS vLLM for bulk re-runs | Open weights; licence **to verify** (Qwen releases are usually Apache-2.0). OpenRouter terms and the upstream provider's data policy apply |
| **Qwen3.8-27B** (`qwen/qwen3.8-27b`) | LLM fallback and benchmarked adjudicator (0 false links on 105 pairs); also VLM fallback (14/14, 9.6 s/img) | OpenRouter / WCSS | Licence **to verify** |
| **Gemini flash / pro** (`gemini-flash-latest`, `gemini-pro-latest`) | Video pass, adjudicator, summaries, White Rabbit function calling | Gemini API (AI Studio endpoint, `GEMINI_API_KEY`) | Google Gemini API terms. Whether the key's tier lets Google train on prompts: **to verify** (free-tier terms differ from paid) |
| **gemini-3.5-transcribe** | Speech-to-text for video ads | Gemini API | As above |
| **YuNet** (`face_detection_yunet_2023mar.onnx`) | Face detection | Local CPU (OpenCV DNN) | OpenCV Zoo; per-model licence file in the zoo — **to verify** (YuNet is believed MIT, the task brief lists Apache-2.0) |
| **SFace** (`face_recognition_sface_2021dec.onnx`) | 128-d face embeddings for the public-figure gallery | Local CPU | OpenCV Zoo, Apache-2.0 (as stated in the brief; confirm in the zoo's LICENSE) |
| **EasyOCR** (pl + en) | Offline fallback for ad fields (64–86 % on sample_v1) | Local CPU | Apache-2.0 (code); model weights follow the project's release — to verify |
| **faster-whisper** (optional extra `ml`) | ASR fallback (`large-v3-turbo` on GPU, `small` int8 on CPU) | Local | MIT (code); Whisper weights MIT (to verify) |
| pHash (`imagehash`), MinHash (`datasketch`) | Creative and text near-duplicate detection | Local | BSD / MIT |

### 3.2 Evaluated and rejected (not shipped as decision makers)

Per `experiments/RESULTS.md` §0, §2: the typed evidence engine is the backbone; the models below were tested on the
same data and rejected or demoted to supporting signal.

| Model | Why not shipped |
|---|---|
| **Qwen3-Embedding-0.6B** | Adds nothing on top of typed content features on sample_v1 (its τ had to be tuned on the evaluation items and swung 0.52–0.92 across models); over-links held-out: 6/9 open-set, 3 wrong links on DANE |
| **mmlw (sdadas), bge-m3** + HDBSCAN | B³-F1 0.78 / ARI 0.37 on sample_v1; 5/9 open-set and 3–4 wrong links on DANE |
| **SigLIP** (screenshot embedding) | 7/9 open-set, joint ARI 0.26 on DANE: visual look alone is not operator evidence |
| **LightGBM** on the evidence vector (and on layer sums) | LOCO: 7 and 4 wrong links; held-out DANE: 3 wrong links (d47→G, d48→A, d61→C). Weak labels from labelling functions are 100 % accurate on 98/105 gold pairs, so retrain only when there are many campaigns |
| **PaddleOCR-VL / GLM-OCR / Qwen3.5-9B** | Advertiser 2/14 and 12/14, or kind 3/14; worse than Qwen3.6-35B-A3B |
| **InsightFace / AuraFace** | Considered in PLAN; InsightFace pretrained models are non-commercial — replaced by SFace |
| **LLM adjudicator as a decider** | Never links wrongly but splits persona-swap variants (A1/A2); kept as veto/annotation only |
| **VLM / LLM person identification** | Both Qwen models renamed Morawiecki to Tusk/Duda; precision 0.38–0.50 vs 1.0 for the face gallery. Never used |

## 4. Libraries (main dependencies)

Versions are as pinned in `backend/pyproject.toml` / `experiments/pyproject.toml`; the licences below are what we
believe each project uses — re-check with `pip-licenses` / `license-checker` before release.

| Library | Use | Licence |
|---|---|---|
| FastAPI, Starlette (uvicorn is BSD) | API | MIT |
| pydantic, pydantic-settings | Contracts, settings | MIT |
| psycopg 3 | Postgres driver | LGPL-3.0 (dynamic use; `psycopg[binary]` ships the C library) |
| networkx | Louvain / components | BSD-3-Clause |
| datasketch | MinHash-LSH | MIT |
| scikit-learn, numpy, scipy | Metrics, clustering helpers | BSD-3-Clause |
| arq | Redis job queue | MIT |
| APScheduler (3.x) | Hunter scheduler | MIT |
| Playwright (Python) | Sandboxed capture | Apache-2.0 (browser binaries have their own licences) |
| httpx, dnspython, tldextract, rapidfuzz, beautifulsoup4, lxml, pillow, imagehash, typer, orjson | Fetching, parsing | BSD / MIT / Apache-2.0 / MPL-2.0 (lxml: BSD; dnspython: ISC; tldextract: BSD-3; rapidfuzz: MIT) — **to verify** per package |
| opencv-python-headless | Face models, image I/O | Apache-2.0 (wheel bundles FFmpeg under LGPL) |
| google-genai, openai | Gemini / OpenRouter clients | Apache-2.0 |
| Next.js, React | Web UI | MIT |
| Tailwind CSS, shadcn/ui | Styling, components | MIT |
| Sigma.js, graphology | WebGL graph | MIT |
| three.js | Decorative 3D (zgrai bots) | MIT |
| PostgreSQL 16 + **pgvector** (`pgvector/pgvector:pg16`) | Store + vectors | PostgreSQL licence (permissive) for both |
| **Redis** (`redis:7-alpine` in `deploy/compose.yml`) | Queue and pub/sub | **Check:** Redis 7.2 and earlier are BSD-3; **7.4+ is RSALv2/SSPL** (source-available, not OSI-open), 8.x adds an AGPLv3 option. The `7-alpine` tag floats to the newest 7.x, so it is probably under RSALv2/SSPL — to verify. Using it for our own service is allowed; offering Redis as a managed service is not. **Alternative: Valkey** (BSD-3, Linux Foundation fork, wire-compatible; `valkey/valkey:7-alpine`) or pin `redis:7.2` |
| uv, ruff, pytest | Tooling | MIT / Apache-2.0 |

Leiden would be GPL, so only Louvain (networkx) is used. Optional heavy libraries (torch, sentence-transformers,
LightGBM, shap) live only in `experiments/` (frozen, BSD/Apache/MIT; shap is MIT, LightGBM MIT).

## 5. Biometric data note

- **Face embeddings of real public figures are biometric data** (GDPR Art. 9 category when used to identify a person).
  The gallery holds 6,305 people / 7,364 photos built from Wikidata and Wikimedia Commons: Polish public figures
  (≥ 5 Wikipedia editions) plus 25 international and 25 curated people. Index file: `index_sface.npz` (128-d SFace
  vectors).
- **The gallery stays local**: `data/` is git-ignored, the gallery is rebuilt by the CLI (`trop gallery build`) and is
  never committed, uploaded or served. The deployed image carries only the precomputed index.
- **Purpose limitation.** It is used only to flag *impersonation of public figures in scam ads* (persons layer with
  weight about 2, the cross-modal check "face in ad = person in the story", the Impersonation radar). It is **never used
  to identify private persons**. Faces that match nobody stay anonymous; only the face-vs-face cosine between ads is
  stored (a face alone weighs 2.5 < τ = 5, so a face never links two incidents by itself).
- **Identity never comes from a VLM or LLM.** A person is named only if **cosine ≥ 0.45 and the lead over the
  runner-up ≥ 0.10** (precision 1.0, recall 0.82 on 11 named faces in sample + DANE ads).
- Gallery coverage stops at the Wikidata cut; fake personas, local influencers and doctors are outside it.
- Persons named in scam text are public figures abused without consent; the UI states "likeness used in the ad",
  never "this person endorsed it".

## 6. Cloud processing note

- **What leaves the machine, by model:**
  - OpenRouter (`qwen/qwen3.6-35b-a3b`, fallback `qwen/qwen3.8-27b`): **raw ad screenshots** (and video keyframes).
  - Gemini API: **raw ad screenshots, video files and audio** (Files API) and LLM prompts with extracted features
    (IDs, templates, fake-commenter names, evidence JSON).
  - Local only: YuNet/SFace, EasyOCR, pHash, faster-whisper, the whole evidence engine.
  - WCSS (batch only, outside the live path): raw organizer material may go there; it is the sovereign option.
- Decision in force (IMPLEMENTATION §0/§9): the repo is private and cloud LLMs are allowed because the terms forbid only
  public distribution. The organizers did not answer; **if they object, switch to WCSS-only adjudication and
  offline VLM fields** (offline mode, see `TROP_MODE` in `.env.example`).
- **Caching:** every gateway response is stored under the sha256 of its input, so each image/video is sent at most
  once per model and the judge build replays from cache. **Offline mode needs no keys** (precomputed VLM fields +
  EasyOCR fallback + cached enrichment); the cost is about 0.13–0.2 recall on dead landings.
- Cloud providers' retention and training policies for the keys we use: **to verify** before processing any
  non-sample organizer data. Do not send faces or voices of private persons to any cloud model.
