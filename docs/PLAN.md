# TROP (ex RED PILL) — scam-campaign intelligence platform · Plan v2

> **Superseded for building by [`docs/IMPLEMENTATION.md`](IMPLEMENTATION.md)** (final implementation plan). This file stays as the product vision. Where it disagrees with `experiments/RESULTS.md` (method, thresholds, models) or `docs/design/README.md` (screens), those win.

> HackNation 2026 · "Kolekcjoner fejków / Follow the Fake" (NASK PIB, AI Safety Research Center) · 30k PLN · ~2k participants
> v2 (2026-11-21): bigger scope, our own product + dashboard (no Streamlit/Gradio/Neo4j by default), Matrix-themed.
> Task text re-checked after the organizers' "updated description" announcement (Drive file of 2026-11-21 11:04): word-for-word identical to the description PDF + teaser we planned from. Nothing changed; copies are in `data/raw/task/`.
> ⚠️ Organizer data must **not** be published. `data/` is git-ignored; the repo is public. Keep this plan private too (it quotes dataset IDs).

---

## 0. The pitch (what we are building)

Everyone else will ship *"upload ads → clusters → graph in Streamlit"*. We ship an **operations platform for NASK's analysts** that follows a scam from a single ad to the **operator behind it**, finds the campaign's **future domains before the ads go live**, and produces **ready-to-send takedown packages for whole campaigns** instead of single ads.

**Hunt → Capture → Understand → Attribute → Predict → Act**, in one product:

| Pillar | What it does | Why it wins |
|---|---|---|
| 🧬 **Attribution engine** (core) | Turns any material into a normalized incident with ~40 features and links it to others through typed, weighted, explainable evidence. Groups at four levels: duplicate → variant → campaign → operator. Decides openly between "joins campaign X" and "new campaign". | Covers the 60% of the score on method and features, with measured metrics |
| 🕵️ **Autonomous Investigator ("Agent Smith")** | An LLM agent with OSINT tools (crt.sh, DNS, RDAP, urlscan, Ad Library, CERT PL, Wayback, our own index). From one seed it pivots step by step, writes a case file, and the graph grows live on screen | The "wow" moment of the live demo, and it shows reasoning step by step |
| 🔮 **Oracle — early warning** | Learns each campaign's *domain DNA* (naming grammar, TLD, registrar, cert issuer and timing, hosting) and watches the Certificate Transparency firehose and new urlscan submissions. It flags campaign domains as their TLS certificates are issued, **often before the ad is even live** | Prediction instead of after-the-fact analysis; the Matrix theme fits |
| ⚖️ **Act** | One click builds a **campaign-level DSA Art. 16 notice** (all ads, advertisers and domains, with evidence), a CERT PL warning-list submission, STIX 2.1/MISP export, and detection rules (urlscan queries, URL regex, HTML signatures) | Fixes the gap NASK itself reported: platforms remove single ads, not campaigns |
| 🛰️ **Hunter / scheduler** | Continuously ingests the Meta Ad Library (lure phrases, celebrity names, known advertiser pages), the Google Ads Transparency BigQuery data, the CERT PL list and urlscan feeds. New items are captured and attributed automatically, with alerts | Explicit bonus in the brief, run continuously |
| 👁️ **Citizen layer** | A browser extension marks sponsored posts on Facebook that match known campaigns, plus a "Sprawdź reklamę" (check this ad) page. Reports from users come back as new incidents | Public-impact story for the pitch, and a data flywheel |
| 🎭 **Impersonation radar** | Shows who is being impersonated this week (face plus name): trends, the campaigns behind them, sample ads, and deepfake and synthetic-voice scores | Media-friendly, and useful to NASK's communications |
| 🌳 **Kit phylogeny** | An evolution tree of landing-page templates and kits across campaigns (DOM and asset lineage) | Unusual scientific angle for the methodology slide |

Demo storyline (3 min): *a judge hands us a new ad URL or screenshot → 20 s later it is attributed to campaign A, with "why" evidence chips → the agent pivots and finds 14 more domains, 3 of which got TLS certificates **tonight** and are not yet on the CERT PL list → the Oracle had already flagged 2 of them → one click produces the DSA package for the whole campaign.*

---

## 1. Scoring → how each criterion is covered

| Criterion | W | Covered by |
|---|---|---|
| Correlation & clustering method | 30% | Attribution engine: rarity-weighted evidence (IDF / Fellegi-Sunter) + multi-level community detection + calibrated open-set assignment. We report B-cubed F1/ARI, leave-one-campaign-out results, and ablations. |
| Features & data sources | 30% | 5 feature layers / ~40 features. High-precision operator fingerprints (pixel IDs, kit API paths, CAPI gateways, asset hashes, certificate batches) + multimodal content (faces, voice, deepfake, OCR, ASR) + 8 external sources. |
| End-to-end demonstrator | 15% | Our own dashboard, `docker compose up`, a scripted live demo plus a cached offline mode. |
| Interpretability | 15% | Evidence chips with weight and rarity, campaign cards, template diff, the agent's case file, a "why not linked" view. |
| Deployability / scale / portability | 10% | Service architecture (API, workers, Postgres+pgvector, object store), incremental indexing, LSH/ANN blocking, STIX/MISP, DSA export, extension. |

The hidden test set holds new variants of known campaigns **and** unrelated campaigns. Refusing a wrong link counts as much as making a right one, so we tune for precision on "new campaign" decisions.

---

## 2. What the data tells us (sample_v1, 15 incidents)

Source: `___BACKUP.zip` from the teaser CTF (password `WSTAWAJSAMURAJU`), copied to `data/raw/sample_v1/`. The official `DANE.zip` (510 MB, MEGA) is still to be downloaded (MEGA quota). **Its format may differ, so ingestion is adapter-based.**

Each incident has a **screenshot of the ad in Meta Ad Library**, a **HAR** of the landing visit (12/15), and a **saved landing HTML**. p1 also has a structured **archive bundle** (`archive_info.json`, `dns_ssl.json`, `metadata.json`, `page_text.txt`, `rendered/source.html`, screenshots, storage, `sha256.json`, pdf, mhtml), which looks like the organizer's own capture format, so we support it natively.

Findings that drive the design:
1. **The ad creatives are cloaked decoys.** The images show a bird and a game landscape; the text is generic clickbait ("🚨 PILNE! Ta wiadomość wywołała burzliwą dyskusję…", "Temat, o którym mówi cała Polska"); the display link is fake (`AMAZON.COM`); advertiser names are random. Comparing creative images gives a weak signal. Clickbait templates, advertiser behaviour and the landing page carry it, and the decoy pattern is itself a feature.
2. **Fake Gazeta.pl pre-landers with the person swapped out.** "«Wiem, kto strzelał»: zamach na Rafała Brzoskę…" (p1, p2, p7, p15); "PILNE: Brutalna napaść na {Krzysztofa Stanowskiego | Tomasza Sekielskiego}…" (p3, p4). Headline templates with the names masked out mark variants.
3. **Shared kit:** `/api/v1/trigger/field/{uuidv7}/` and `/api/v1/agent/persist-session-record/…` appear on dorquesio.click, falmurek.live, grentavo.click, wernulio.live and lundevra.live, **and on sfuxd.com (p11, a health lure)**. So one operator runs several narratives, which is our operator-family level.
4. **Shared Meta CAPI gateway** `xd-f1cf3d4f….ecs.us-east-1.on.aws/events?cee=no` on p1–p4 and p7. Other operators use `dv-c3e594c6….on.aws` (p10) and `mpc-prod-24-….run.app` (p8).
5. **Tracking IDs:** FB pixels `2420768028414250` (p10), `1550629110431763` (p9) and `959278079792247` (p8); Google `AW-16725023086` + `G-S9K3K2XFQK` (p14).
6. **URL grammars:** random utm_* values + `utm_visit` UUIDv7 (kit A); `clickid/key/pixel_fb` (Keitaro-like, p5); `click?key&sid=pl&pixel&ad_id` (p8); `ad_name=FARM/PL/MUDr. Štěpán Kovář/…` (p10), which leaks the operator's naming convention (vertical/geo/persona).
7. **Cloudflare noise:** p4, p5, p9, p10 and p15 share `188.114.96.11` without being one campaign. IP links must therefore be weighted by rarity and be CDN-aware. Real origins show up as DigitalOcean IPs, certificate batches, TLD choice (`.click/.live` with random words) and third-party assets (pandavideo `vz-b2d5546a-081`, `static.joxi.pro`, `vstats.io`).
8. **Incomplete data is normal:** the p1 archive caught a Cloudflare 502; p6, p12 and p14 have no HAR; p10 says "video deleted". **A missing value is not evidence of difference.**
9. **Certificate batches:** Let's Encrypt `YE1`, notBefore 2026-10-07 18:53 (p1). The teaser's fake reviews hint "5 domen, ten sam favicon, certyfikaty z tego samego dnia".
10. **CTF hints from the organizers:** **facetorch** (face deepfake/attributes) and **SpeechBrain** (voice). We use both and say so in the pitch.

Rough manual grouping (to verify, becomes `eval/labels.yaml`): **A** fake-Gazeta attack/assassination: p1, p2, p3, p4, p7, p15 (p11 shares the kit, same operator). **B** health/supplements: p5, p6, p9, p10, p12, p13, p14, likely several sub-campaigns. **C** p8 "Trudna odpowiedź" (same title as p11!). CTF bonus: 3 Google-Ads URLs (caepertss.com, tlbjyhce.com share `/products/{id}` + Shopline params; zzvn.info).

---

## 3. Architecture & stack (chosen on merit)

```
          ┌───────────── Web app (our dashboard) ─────────────┐     Browser extension (MV3)
          │ Next.js + TS + Tailwind + shadcn/ui                │◄──── "Sprawdź reklamę" overlay
          │ Sigma.js/graphology (WebGL graph, 10k+ nodes)      │
          │ React Flow (investigation canvas) · deck.gl/MapLibre (infra map) · visx timelines
          └──────────────▲───────────── SSE/WebSocket (live events) ─────────┘
                         │ REST/OpenAPI
                 ┌───────┴────────┐
                 │ FastAPI (Py3.12)│── Agent service (LLM + tool calling, streamed steps)
                 └───────┬────────┘
       Redis (queue + pub/sub) ── workers (arq): capture · extract · enrich · link · hunt · oracle
                         │
   Postgres 16 (+pgvector, pg_trgm) — incidents, features, evidence edges, campaigns, vectors
   MinIO (S3) — HAR, HTML, screenshots, video, audio                 Model worker — OCR/ASR/faces/voice/embeddings
   Playwright capture worker (sandboxed, no form submission)          Oracle worker — CT-log stream consumer
                         │
   Model gateway (OpenAI-compatible router): WCSS vLLM (VLM, PLLuM/Bielik) · Claude API · local ONNX fallbacks
   Training jobs on WCSS (SLURM): M1–M5 → artifacts pulled into the repo's model registry (versioned)
```

Why this and not the defaults from the brief:
- A **custom web app** gives a real-time investigation UX (a live agent, a growing graph, alerts) and a product that NASK could actually deploy. Streamlit can't do live graph canvases, websockets or extension integration well.
- **Postgres + pgvector** instead of Neo4j: one store for relational data, vectors and edges. Graph analytics run in Python (igraph/networkx Louvain). We still offer a Cypher/GraphML export.
- **Workers plus a queue** let the hunter, the oracle and live captures run continuously while the UI streams progress.
- The **LLM is optional at every step**: structured extraction, campaign summaries and the agent need an API key, and the core pipeline is fully deterministic without one (so judges can run it with no key).

ML/OSINT libraries (CPU-friendly; no local GPU):
- **Text:** Polish embeddings (`sdadas/mmlw-roberta-base` or `bge-m3`), spaCy `pl_core_news` for NER, MinHash (datasketch).
- **Visual:** SigLIP/CLIP-small + pHash.
- **Faces:** InsightFace or AuraFace, plus facetorch.
- **Voice and speech:** SpeechBrain ECAPA (voice), faster-whisper int8 (speech-to-text), Tesseract/EasyOCR `pol` (OCR).
- **OSINT:** tldextract, dnspython, whoisit (RDAP), mmh3 (favicon), certstream/CT-log client, httpx.
- **Clustering and scheduling:** igraph/networkx, scikit-learn (HDBSCAN, metrics), APScheduler.
- Licenses are tracked in `docs/DATA_SOURCES.md` (InsightFace models are non-commercial; urlscan and VirusTotal free tiers are non-commercial; Leiden is GPL, so we use Louvain).

### Repo layout
```
web/                 Next.js dashboard
extension/           MV3 browser extension
api/                 FastAPI app (routers: incidents, campaigns, graph, ingest, agent, hunt, oracle, export)
core/
  schema.py          Incident / Evidence / Campaign models (THE contract)
  ingest/            adapters: url, har, html, screenshot, video, archive_bundle, sample_dir, adlibrary, csv
  capture/           playwright crawler (HAR, DOM, redirects, favicon, TLS cert)
  extract/           text, ocr, asr, visual, faces, deepfake, voice, dom, infra, tracking, adlayer
  enrich/            rdap, dns, crtsh, urlscan, certpl, ipinfo, wayback (cached, offline-tolerant)
  link/              blocking, evidence, weights
  cluster/           levels, assign, phylogeny
  agent/             tools + loop + case-file writer
  oracle/            domain-DNA models + CT stream matcher
  act/               dsa_notice, certpl_submission, stix, rules
eval/                labels, metrics, robustness, ablation
refdb/               celebrity gallery, brand logos, lexicons
deploy/              docker compose (web, api, workers, postgres, redis, minio)
docs/                PLAN, METHODOLOGY, DATA_SOURCES, DEMO, ATLAS (campaign patterns report)
data/                (git-ignored)
```

---

## 4. Core contract: the `Incident` schema (defined in hour 1, frozen early)

```jsonc
{
  "id": "inc_…", "source": {"type": "sample_dir|url|har|screenshot|adlibrary|extension|hunter", "captured_at": "..."},
  "ad":      {"platform": "meta", "library_id": "...", "advertiser": "...", "text": "...", "display_link": "AMAZON.COM",
              "cta": "...", "creative_phash": "...", "creative_is_decoy": true, "delivery": {"start": "...", "reach": 0}},
  "landing": {"entry_url": "...", "final_url": "...", "redirect_chain": [], "status": 200, "title": "...", "text": "...",
              "lang": "pl", "dom_minhash": [], "screenshot_phash": "...", "favicon_mmh3": 0, "forms": [], "outlinks": []},
  "tracking":{"fb_pixels": [], "capi_gateways": [], "google_ads": [], "ga4": [], "url_param_schema": "utm5+uuidv7",
              "kit_endpoints": ["/api/v1/trigger/field/{uuid}/"], "third_party": [], "asset_hashes": []},
  "infra":   {"domains": [{"fqdn": "...", "etld1": "...", "tld": "...", "registrar": "...", "created": "...", "ns": [],
              "ips": [], "asn": "...", "cdn": "cloudflare", "cert": {"issuer": "...", "not_before": "...", "san": []}}],
              "on_certpl_list": false},
  "content": {"headline_template": "PILNE: Brutalna napaść na {PER} …", "persons": [], "brands": [], "narrative": "...",
              "products": [], "keywords": [], "contacts": {"phones": [], "ibans": [], "telegram": []}},
  "media":   {"faces": [{"identity": "...", "score": 0.0, "deepfake": 0.0}], "asr_text": "...", "voice_id": "..."},
  "quality": {"available": [], "missing": [], "errors": []}
}
```

---

## 5. Feature catalogue (scored 30%)

Strength = how strongly a match implies "same campaign": H = near-proof, M = supportive, L = context only.

| Layer | Feature | Compare | Str. |
|---|---|---|---|
| Tracking | FB pixel / Google Ads AW / GA4 / GTM / TikTok pixel IDs | exact | **H** |
| Tracking | CAPI gateway host (`*.on.aws`, `*.run.app` + `/events?cee=no`) | exact | **H** |
| Kit | API path templates (ids → `{uuid}`) | exact template | **H/M** |
| Kit | URL parameter grammar (names + value shapes) | exact / Jaccard | M |
| Kit | Asset body hashes (JS/CSS/img) from HAR and saved files | rare-hash overlap | **H** |
| Kit | DOM tag-path shingles (MinHash) · favicon mmh3 · third-party stack/IDs | Jaccard / exact | M–H |
| Infra | eTLD+1 / FQDN | exact | **H** |
| Infra | Domain DNA (lexical grammar, TLD, length, dictionary-ness) | similarity | L/M |
| Infra | Certificate batch (issuer + issuance within N hours, SAN overlap) · RDAP registrar/creation/NS | window / exact | M |
| Infra | Origin IP/ASN (CDN-aware, rarity-weighted) | exact | M (CDN ≈ 0) |
| Content | Headline template with names masked · products · contacts (phone/IBAN/Telegram) | exact / fuzzy | **H** |
| Content | Semantic embedding (landing + ad + OCR + ASR) · near-duplicate MinHash | cosine / Jaccard | M / H (dup) |
| Content | Narrative/vertical · impersonated brand (logo + text) | category / set | L–M |
| Persons | Celebrity identity from face (small gallery, ~25 people) and from name (NER + gazetteer) | identity | M |
| Visual | Landing screenshot pHash + SigLIP · ad creative pHash + decoy detector | Hamming / cosine | M / L |
| Ad | Advertiser page/ID · clickbait template · delivery window | exact / Jaccard / window | M |
| Media | Synthetic-voice speaker embedding (SpeechBrain) · deepfake score / face-swap template (facetorch) | cosine / context | M/H · L |

---

## 6. Attribution method (scored 30%)

1. **Blocking:** candidate pairs come from inverted indexes on exact IDs/templates/domains/rare hashes, pgvector kNN (text/visual/face/voice) and MinHash-LSH. Scales well below O(n²).
2. **Typed evidence:** `weight = strength(type) × rarity(value)`, where `rarity = log(N/df)`. Values shared by everyone (Cloudflare, facebook.net, jquery, cdnjs, gstatic) get weight 0.
   - Strengths are Fellegi-Sunter `log(m/u)`, calibrated on labeled pairs; with few labels we start from priors and run a grid search.
   - A missing field contributes 0, and every score carries a **coverage** value.
   - Negative evidence counts only when a high-strength field is present on both sides and conflicts.
3. **Levels:**
   - **L0 duplicate:** hash/URL match, or text MinHash ≥ 0.9 and pHash ≤ 6.
   - **L1 variant:** same template/product/DOM, different entity or domain.
   - **L2 campaign:** at least one high-strength evidence item, or Σ ≥ τ from at least 2 independent layers; communities found with Louvain.
   - **L3 operator family:** shared kit/gateway/pixel across narratives.
4. **Open-set assignment:** score a new item against each campaign as max-linkage plus the mean of the top 3. Assign it when the score ≥ τ and the margin over the runner-up ≥ δ; otherwise mark it as a **new campaign candidate**. Updates are incremental (a local re-run of community detection).
5. **"Why NOT linked" view:** shows the nearest campaign and what was missing or conflicting. Useful for interpretability and for checking false merges.
6. **Evaluation:**
   - B-cubed P/R/F1, ARI and pairwise precision.
   - Open-set accuracy, plus precision of "new campaign" decisions.
   - Leave-one-campaign-out.
   - Robustness: drop HAR, drop screenshot, swap domain, 502 page, duplicates, format variants.
   - Ablation per layer.
   - HDBSCAN-on-embeddings baseline, to show how much better evidence-based linking is than "pure ML".

---

## 6b. Models & learning strategy (cloud LLM + local GPU on WCSS + our own models)

Principle: **hand-set evidence is the baseline; learned models improve on it, but every decision still breaks down into human-readable evidence.**

### Compute topology
| Where | What runs there | Why |
|---|---|---|
| **WCSS GPU cluster** (SLURM; serve via vLLM with an OpenAI-compatible endpoint, reached through an SSH tunnel or gateway) | An open-weights VLM for reading screenshots and ads; a Polish LLM; training and fine-tuning our models; batch embedding of the whole corpus | Organizer data never leaves Poland or our control. Fits NASK's deployment model ("sovereign" stack). Fast batch work. |
| **Cloud LLM** (Claude API) | Agent Smith orchestration (tool use), case-file writing, DSA notice drafting, teacher labels for distillation, adjudicator for uncertain pairs | Best reasoning and tool use; fewer calls since it only runs at the top of the cascade |
| **Laptop / judge machine (CPU)** | The distilled small models (GBM, small encoders, int8 ONNX), with everything precomputed | `docker compose up` works without GPUs or API keys |

Local LLM candidates:
- **PLLuM**, the Polish LLM family co-developed with NASK. Using the organizer's own model is a strong nod to the jury.
- **Bielik** (SpeakLeash), Polish-native.
- **Qwen-VL / InternVL-class VLMs** for screenshots.

Pick the newest versions that fit WCSS GPUs; benchmark on 20 labeled screenshots in hour 1–2.

> ⚠️ Data rule check: sending organizer materials to a cloud API could count as "distribution". Default to **WCSS/local for raw materials**. The cloud LLM sees only extracted features or public OSINT, unless the organizers confirm on Discord that it's fine.

### Our own models (each one is a methodology slide)
| # | Model | Type | Trained on | Role |
|---|---|---|---|---|
| M1 | **Linkage decision model:** P(same campaign \| pair) | Gradient boosting (LightGBM) over the evidence vector, with **monotonic constraints** + isotonic calibration | Labeled pairs + weak labels + synthetic perturbations | Replaces hand weights. **SHAP per link** gives the evidence chips with learned contributions |
| M2 | **Infrastructure-supervised content encoder** | Contrastive/triplet fine-tune of a small multimodal encoder (SigLIP + Polish text encoder) | *Distant supervision:* pairs linked by near-certain infra evidence (same pixel, kit, gateway) are positives; different operators are negatives | Learns which *look and story* mean "same operator", so it can **link variants after infra fully rotates**, which is exactly the hidden-test case |
| M3 | **Domain DNA model** (Oracle) | Char-CNN or char n-gram LR per campaign plus a global "scam-kit domain" classifier | Campaign domains (ours + CERT PL list + crt.sh pivots) vs. benign CT-log sample | Scores live CT-stream domains and predicts future campaign domains |
| M4 | **Narrative / vertical classifier** | Fine-tuned Polish encoder (e.g. mmlw/HerBERT) | **Distilled** from PLLuM/Bielik/Claude labels on the corpus | Cheap, consistent narrative tags at scale |
| M5 | **Page-role & decoy detectors** | Small heads on SigLIP embeddings | LLM/VLM-labeled ad creatives and landings (pre-lander, order form, cloaked decoy, error/parked) | Feature + routing (e.g. a 502 or parked page drops visual weight) |
| M6 | **Celebrity matcher** | Face embeddings + gallery kNN (no training), plus a voice gallery (SpeechBrain) | ~25 most-impersonated people, a few photos and clips each | Persons layer and Impersonation radar |

Weak supervision: Snorkel-style labelling functions such as "same pixel → same", "same kit + same gateway → same", "different narrative and no shared infra → different". These multiply labels from 15 samples to thousands of pairs once DANE, CERT PL captures and pivots arrive.

### Decision cascade (open-set, calibrated, explainable)
1. **Rules:** L0 duplicates and high-strength exact IDs decide immediately (fast, certain).
2. **M1 linkage model** gives a calibrated probability per candidate pair, and per-campaign aggregation scores the new item.
3. **Conformal open-set decision:** a split-conformal threshold on campaign scores gives a **controlled error rate for "assigned to an existing campaign"**. Anything outside the conformal set becomes a **new campaign candidate**. This is a statistically grounded answer to "zdolność identyfikowania materiałów, które nie powinny zostać połączone".
4. **LLM adjudicator**, only for the uncertain band (say 0.35–0.65). The cloud LLM or local PLLuM gets *both evidence dossiers* and writes a verdict with a rationale, which is stored as evidence and is reviewable.
5. **Analyst feedback** (accept/reject in Triage) feeds active learning; M1 retrains in seconds.

### Evaluation of the models
- **M1:** compare against hand weights and an HDBSCAN-only baseline (B-cubed F1, ARI).
- **M2:** an "infra-blind" test where all infra features are masked: can content alone re-find campaigns?
- **M3:** precision@k on held-out campaign domains in the CT stream.
- **Conformal:** report achieved vs. target error.
- Everything goes on the **Lab** screen.

---

## 7. Dashboard (our own) — screens

1. **Command center:** live feed (hunter/oracle/extension), new incidents, campaigns heating up, alerts, KPIs.
2. **Analyze:** drop a URL, screenshot, HAR, video or zip. A live pipeline view (capture → extract → match) with step timings, then the verdict card.
3. **Incident view:** all extracted features by layer, captured artifacts, top matches with evidence chips.
4. **Campaign view:** fingerprint ("DNA"), members, timeline, domains, persons/brands, tracking IDs, kit-phylogeny branch, generated summary, Act buttons.
5. **Graph explorer:** WebGL graph with campaign coloring and evidence-type filters (infra only / content only / persons). Lets us show live that content alone over-merges while infra splits correctly.
6. **Investigation canvas:** the agent's pivots appear as nodes in real time, with a case file streamed alongside.
7. **Oracle:** domain-DNA per campaign, a live CT stream with matches, and "predicted vs. confirmed" results.
8. **Impersonation radar:** persons × time heatmap, deepfake/voice evidence.
9. **Act center:** DSA notice package, CERT PL submission draft, STIX/MISP, rules with a "test on dataset" button.
10. **Lab:** metrics, ablations, robustness stress test (perturb and re-score with one click), methodology.

Visual identity: Matrix-inspired (dark, green glyph accents, "Follow the fake" copy) but readable. The jury doesn't score looks, while 2k participants and a stage demo reward them.

---

## 8. Scope tiers (so we win even if time runs out)

| Tier | Contents | Done when |
|---|---|---|
| **T1 — Winning core** (must) | Schema, adapters (sample_dir, archive bundle, HAR, HTML, screenshot+OCR/VLM, URL capture), all tracking/kit/infra/content features, evidence engine, **M1 linkage GBM + calibration + conformal open-set**, eval suite, dashboard screens 2–5 + 10, docker compose, METHODOLOGY.md | End-to-end on sample + DANE with metrics, beating the hand-weight baseline |
| **T2 — Differentiators** | Agent Smith (investigator), LLM adjudicator, Act center (DSA/STIX/rules), Hunter (Meta Ad Library + CERT PL + urlscan), faces + celebrity gallery (M6), M4/M5 distilled classifiers, Command center | Live demo storyline works |
| **T3 — Moonshots** | **M2 infra-supervised content encoder**, Oracle (CT stream + M3 domain DNA), voice/deepfake layer (SpeechBrain/facetorch), browser extension, kit phylogeny, Impersonation radar, ATLAS report | Any 2–3 of these = big stage moments |

---

## 9. Team & timeline (≈24–30 h; fill in names and the end time)

| Stream | Owner | T1 | T2/T3 |
|---|---|---|---|
| Frontend (dashboard, graph, canvas) | ? | screens 2–5, 10 | 1, 6–9, extension |
| Ingest & capture & infra/OSINT | ? | adapters, Playwright, DNS/RDAP/crt.sh | hunter, oracle |
| Features & ML (text/visual/faces/media) | ? | OCR/VLM extraction, NER templates, embeddings, pHash | faces, voice, deepfake, M4/M5 |
| Models & WCSS (training + serving) | ? | vLLM on WCSS + model gateway, batch embeddings | M2 contrastive encoder, M3 domain DNA |
| Attribution & eval (method owner) | ? | evidence, M1 GBM, conformal open-set, metrics | adjudicator, phylogeny, ablation story |
| Agent & Act & pitch | ? | API, docker, docs | agent, DSA/STIX/rules, slides, demo video |

| Phase | h | Milestone |
|---|---|---|
| P0 | 0–2 | Schema frozen, repo skeleton, compose with Postgres/Redis/MinIO, labels for sample_v1, DANE downloaded |
| P1 | 2–10 | Adapters + T1 features → incidents in DB; API endpoints; dashboard shell against mocked API |
| P2 | 8–14 | Evidence engine + clustering + open-set + first metrics; **E2E demo-able by h14** |
| P3 | 14–22 | T2: agent, Act center, hunter, faces; graph explorer polish |
| P4 | 18–26 | T3 picks; robustness/ablation numbers; ATLAS report |
| P5 | last 4–6 | Clean-machine docker test, README/METHODOLOGY/DATA_SOURCES, recorded backup video, pitch rehearsal |

Rule: **the frontend works against a mocked API from hour 2** (OpenAPI contract), so UI and pipeline progress in parallel.

---

## 10. Risks / open items

- **DANE.zip** is not downloaded yet (MEGA quota resets ~16:50) and its format is unknown. Re-plan the adapters after opening it, and ask on Discord about the test-set format.
- **Meta Ad Library API** needs identity verification (can take days). Apply **now**; meanwhile use a Playwright fallback against the public UI (demo only).
- **Scope creep:** T1 must be finished and measured before T3 starts. The method owner has veto power over moonshots.
- **Live demo fragility:** keep a cached and seeded demo dataset, an offline mode and a recorded video.
- **WCSS:** confirm the account, GPU type and quota, SLURM queue wait times, and whether we can expose a vLLM endpoint (tunnel). Book GPUs early. The judges' run must not depend on WCSS: ship distilled CPU models and precomputed embeddings.
- **Training data is tiny** (15 samples until DANE arrives): rely on weak supervision, distant supervision (M2) and synthetic perturbations; always report the hand-weight baseline next to the learned results.
- **LLM cost/keys:** the agent and adjudicator are optional with deterministic fallbacks; document how to get keys. Raw organizer material goes to WCSS/local only (see 6b).
- **Licenses and data rules:** document everything in DATA_SOURCES.md; never commit organizer data.

## 11. Next actions (now)
1. Fill in the team table and the hackathon end time.
2. Get DANE.zip (a teammate's browser or retry after the quota resets).
3. Apply for Meta Ad Library API access; get urlscan.io and ipinfo keys; Claude API key; WCSS: reserve GPUs, stand up vLLM with a VLM + PLLuM/Bielik and benchmark them on 20 screenshots.
4. Hour-1 tasks: `core/schema.py`, OpenAPI contract + mock server, compose skeleton, `eval/labels.yaml` for sample_v1.

## Appendix: sources
Task PDFs (Drive); teaser https://science.nask.pl/hacknation (hints: facetorch, SpeechBrain, favicon/SSL); CSIRT KNF "Masowa kampania wyłudzeń finansowych" (domain grammar `finance<NN>-<lorem><NN>.sbs`, manual CSS/DOM linking); NASK 2025 platform-response report (deepfake doctor template; single-ad removals); CERT PL warning list; Gen Digital "Scam Ad Machine" (2026); Bitdefender Meta scam network (2026); Infoblox/Confiant Keitaro research; RTR/ÖIAT Ad Library study (2025); Meta `ads_archive` API (DSA: all EU ads); Google Ads Transparency BigQuery; arXiv 2005.14440.
