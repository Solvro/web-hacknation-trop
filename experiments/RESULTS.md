# RED PILL — approach experiments: results & decided analysis flow

> ⚠️ **Do not publish.** This file quotes organizer-derived identifiers (domains, pixel/tenant IDs, ad captions). The repo is public — keep it out of commits or redact it first (same rule as docs/PLAN.md).

*Experiments session, 2026-11-21. Data: sample_v1 (15 incidents, CTF backup) + DANE.zip (10 incidents, official).
Feature names follow PLAN.md §5; new ones are marked **NEW**. Labels: `labels.yaml`, `labels_dane.yaml`.*

**Evidence strength caveat.** 25 incidents, 14 campaigns. DANE is the only held-out test (9 labelled queries), and
two rules (§0.3) were added after seeing it — they are re-validated on sample_v1 LOCO but not on unseen data.
Read the numbers as "which approach fails how", not as final accuracy.

---

## 0. Decisions (TL;DR)

1. **Backbone = typed, rarity-weighted evidence engine (approach a), two scores per pair**:
   `score_campaign` (ad-account, lander, content, ad-layer evidence) and `score_operator` (+ account-level hosting
   evidence: kit tenant, Cloudflare NS pair, registrar batch, third parties, lander-tool path shape, downstream funnel
   domains). It is the only approach with **0 wrong links** on sample LOCO, all perturbations, and held-out DANE.
2. **Clustering** = average-linkage on `score_campaign`, τ = 5 (stable for τ ∈ [2, 10]); Louvain only inside a
   campaign for L1 variants. **Assignment** = max-linkage ≥ 5 with margin ≥ 1, else "new campaign"
   (PLAN's max + mean-top-3 dilutes strong links: 502-page recovery 0.53 → 0.80).
3. **Two rules DANE forced** (both follow from the label definition "campaign = same operator AND same narrative"):
   * *chain domains are operator-level*: a lander reached by click-through (d2 → healthlinkq.pro) is shared by several
     pre-lander campaigns; counting it as campaign evidence produced the only wrong link on DANE (C variant → A);
   * *conjunction*: operator-level evidence (capped at +4) counts toward the campaign score only when content/ad
     evidence agrees (≥ 2.5). Recovers the C variant (d3 ↔ p5: same Cloudflare account + same Olejnik/NBP persona),
     keeps "same operator, different product" (p6↔p12, p9↔p10) apart.
4. **Ad screenshots → Qwen3.6-35B-A3B VLM on WCSS** (100% advertiser/library-ID/caption, 2.7 s/img unbatched;
   Qwen3.8-27B same accuracy at 9.6 s; EasyOCR on CPU 64–86% as offline fallback). **Never take person identity
   from a VLM** (both Qwen models renamed Morawiecki to Tusk/Duda). Faces = SFace embeddings against a
   **6,305-person gallery** (every Polish public figure on Wikidata with ≥ 5 Wikipedia editions + 25 international
   + 25 curated; 7,364 photos, 1–4 per person from Wikimedia Commons): precision 1.0 / recall 0.82 on the
   sample+DANE ads with the rule cos ≥ 0.45 and lead over runner-up ≥ 0.10, vs 0.38–0.50 for the VLMs. The
   automatic Commons photos alone reach the same 1.0 / 0.82 without any hand-picked photo (Wikidata portrait only: 0.64).
5. **Embeddings (b), learned GBM (c), LLM adjudicator (h) = supporting / veto only.** On held-out DANE, b and c make
   3–4 wrong links each; the LLM never links wrongly but splits persona-swap variants. Train M1 again when there are
   many campaigns (labelling functions: 100% accurate on 98/105 gold pairs → cheap weak labels).
6. **Conformal threshold (g)**: implemented; not reliable at n ≤ 25 (tied scores; achieved 5–6% vs 1% target).
   Ship a-priori τ = 5 and show conformal τ(α) in the Lab once a few hundred labelled incidents exist.
7. **Capture & enrichment must keep**: full entry URL (L0 visit id, param grammar, `ad_name` leaks), every HAR in a
   click chain, HAR bodies (asset hashes), NS records + RDAP + crt.sh (Cloudflare account, registration batches 6 s–2 min
   apart in campaign A). Infra never decides alone but confirms every operator link, including across rotation.
8. **New label level "operation"**: DANE shows A (Brzoska pre-landers), C (Olejnik lander network) and K (new
   "kajdanki" pre-lander) are one investment funnel. The product should show campaign → operator → operation.

## 1. Labels — what changed vs PLAN §2

* "Kit A" (`/_cdn/production/landing-cdn/{TENANT}/{LANDER}/`, `/api/v1/trigger/field/{visit}`, `aio-static/sdk`) is a
  **multi-tenant SaaS**; tenant UUID = operator account (f141c307 = A, 0660ffe3 = p6+p12, 007e0023 = p11); endpoints =
  platform evidence. Kit POST bodies leak lander + landing-type UUIDs even without saved HTML.
* p5 is investment (Olejnik vs NBP), p6/p12 are on kit A, p8+p11 share one lander build on two stacks, p2 = byte copy of p1,
  the p1 capture bundle is a real Cloudflare 502. Only 4/14 ad creatives are decoys.
* DANE (10 folders, numbered from a larger pool): d1, d2 = A; d3 = C; d48, d61 = new campaign K (same pre-lander,
  FB vs **Google Ads**); d10 gambling (fake App Store), d14 Metabo RX, d36 "Poland Invest Summit", d47 Uromexil = new;
  d5 = video-only ad (unlabelled). Formats: multi-HAR click chains, 3-page funnels, iPhone screenshots, screen
  recordings, yt-dlp Ad Library downloads, a capture-tool bundle — see `DATA_NOTES.md`.

## 2. Comparison of approaches

### 2a. sample_v1 (15 incidents; LOCO = leave-one-campaign-out open set, n_link = 8, n_not-link = 15)

| Approach | B³-F1 | ARI | hn viol | LOCO link | LOCO not-link | wrong | 502 page | full infra rotation |
|---|---|---|---|---|---|---|---|---|
| **a. evidence engine, final** (campaign/operator split, max-linkage, conjunction, τ=5) | **1.00** | **1.00** | 0/9 | **1.00** | **1.00** | **0** | 0.87 (0 wrong) | 1.00 (0) |
| a. without conjunction / with PLAN aggregation | 1.00 | 1.00 | 0/9 | 1.00 | 1.00 | 0 | 0.80 / 0.53 | 1.00 |
| a. single score (no split), Louvain | 0.87 | 0.60 | 1/9 | 1.00 | 0.87 | 2 | — | 0.93 (1) |
| b. Qwen3-Embedding landing text (τ tuned on these items*) | 1.00* | 1.00* | 0/9 | 1.00* | 1.00* | 0* | n/a | 1.00 |
| b. mmlw / bge-m3 + HDBSCAN | 0.78 | 0.37 | 1–2/9 | — | — | — | n/a | — |
| c1. LightGBM on 40-dim evidence vector (LOCO) | 0.83–0.86 | 0.51–0.57 | 0/9 | 0.50 | 0.53 | 7 | 0.67 (3) | 0.67 (3) |
| c2. LightGBM on layer sums + hand scores (LOCO) | 0.93–0.97 | 0.93–0.96 | 1–2/9 | 1.00 | 0.73 | 4 | 0.87 (2) | 0.93 (1) |
| h. adjudicator alone — Haiku 5.5, features only | pair acc 0.943, 0 FP, 6 FN | | | | | | | |
| h. adjudicator alone — Qwen3.8-27B on WCSS, features / + raw text | pair acc 0.924 / 0.952, 0 FP | | | | | | | |

\* tuned on the evaluation items; the best τ swings 0.52–0.92 across models, separation margin is negative.

### 2b. Held-out DANE (known = sample_v1; 9 labelled queries: 3 should link, 6 should be "new")

| Approach (fixed before scoring DANE unless noted) | open-set correct | **wrong links** | incremental B³-F1 / ARI | joint batch (24 items) B³-F1 / ARI |
|---|---|---|---|---|
| **a. evidence engine, final** (chain-domain + conjunction rules, added after first DANE run) | **9/9** | **0** | **1.00 / 1.00** | **1.00 / 1.00** |
| a. as frozen before DANE | 8/9 (d3 → new) | 0 | 0.94 / 0.85 (d3 → A via d2's chain) | 0.98 / 0.98 |
| a. chain-domain rule only | 8/9 | 0 | 0.98 / 0.98 | 0.98 / 0.98 |
| b. Qwen3-Embedding, τ tuned on sample | 6/9 | 3 | — | 0.88 / 0.66 |
| b. mmlw / bge-m3, τ tuned on sample | 5/9 | 3–4 | — | 0.78 / 0.50–0.52 |
| b. SigLIP screenshot | 7/9 | 0 | — | 0.78 / 0.26 |
| c. LightGBM (layer sums) trained on all sample pairs | 5/9 | 3 (d47→G, d48→A, d61→C) | — | 0.93 / 0.93 |

Operator/operation level on the 24 items: B³-F1 0.93 (components, τ_op = 3) / 0.86 (avg-link), all errors are
missing weak links inside the "operation" (K ↔ A/C only share a fake byline and a kit platform).

### 2c. Approach (d) — ad-screenshot extraction (14 sample screenshots vs hand transcription `ad_truth.yaml`)

| Extractor | where | kind | advertiser | library ID | caption | decoy | persons named P/R | s/img |
|---|---|---|---|---|---|---|---|---|
| EasyOCR pl+en + heuristics | PC CPU | 14/14 | 9/14 | 3/3 | 10/12 | — | — | 10 |
| PaddleOCR-VL / GLM-OCR (+ same heuristics) | WCSS | 14/14 | 2/14 / 12/14 | 2/3 / 3/3 | 2/12 / 3/12 | — | — | 0.5–0.6 |
| Qwen3.5-9B | WCSS | 3/14 | 12/14 | 3/3 | 11/12 | 11/14 | 0.44/0.50 | 4.9 |
| Qwen3.8-27B-FP8 | WCSS | 14/14 | 14/14 | 3/3 | 12/12 | 14/14 | 0.38/0.38 | 9.6 |
| **Qwen3.6-35B-A3B (MoE)** | WCSS | **14/14** | **14/14** | **3/3** | **12/12** | 12/14 | 0.50/0.50 | **2.7** |

(e) Faces (YuNet + SFace, CPU): cross-ad re-identification 6/6 true pairs, 0/39 false pairs (cos 0.965–1.0 vs ≤ 0.31),
72 ms/screenshot; on sample+DANE the only cross-ad face clusters are the A1 Morawiecki inset and one unexplained
d3↔d10 match (not inspected; it caused no link — a face alone weighs 2.5 < τ, which is the intended safety margin).

**Face gallery at scale** (`rp/gallery.py`, `run_faces_id.py`): Wikidata query for every Polish citizen with a
portrait, ≥ 5 Wikipedia language editions, alive or died after 2000 → 6,516 people, + 25 international figures abused
in PL scam ads (Musk, Gates, Buffett, Zuckerberg, von der Leyen, Zełenski, Lagarde, the Pope …, resolved by en-wiki
title) + the 25 curated photos kept as extra templates → **6,305 people / 6,362 photos** with a detectable face (203
portraits had none). Fetch ≈ 20 min / 484 MB (needs a contact address in `WIKIMEDIA_UA`, kept out of the repo); index
build ≈ 5 min CPU; matching = one 6,362×128 matrix product per face, person score = max over that person's photos.

Truth = 11 named faces in 7 screenshots (sample + DANE d1, d3):

| gallery | rule | TP | FP | FN | precision | recall |
|---|---|---|---|---|---|---|
| 1,849 people (≥ 12 editions), 1 photo each | cos ≥ 0.363 (SFace default) | 9 | 4 | 2 | 0.69 | 0.82 |
| 1,849 people, 1 photo each | cos ≥ 0.45 | 9 | 0 | 2 | 1.00 | 0.82 |
| 6,344 people (≥ 5 editions), 1 photo each | cos ≥ 0.45 | 8 | 2 | 3 | 0.80 | 0.73 |
| 6,344 people, 1 photo each | cos ≥ 0.50 | 8 | 0 | 3 | 1.00 | 0.73 |
| **6,305 people, curated + Wikidata photos** | **cos ≥ 0.45 and lead ≥ 0.10** (also cos ≥ 0.50 alone) | **9** | **0** | **2** | **1.00** | **0.82** |

What scale taught us: a 3.4× bigger gallery brings more lookalikes (impostor scores rise from ≤ 0.44 to 0.48 on p5's
blurry studio faces), so a single photo per person forces a higher threshold and loses recall; **a second photo per
person restores it** (Glapiński 0.52 → 0.62, Olejnik back at 0.56). Hits: Morawiecki ×4 (0.71–0.73), Zełenski 0.79,
Sikorski 0.69, Brzoska 0.57 (d1), Olejnik 0.56 and Glapiński 0.62 (d3); true matches lead the runner-up by ≥ 0.13.
Misses: both faces in p5's studio still (profile view). **Rule: name a person only if cos ≥ 0.45 and top-1 − top-2
≥ 0.10** (perfect anywhere in 0.40–0.55 here).

**Extra Commons photos** (`rp.gallery fetch-extra` + `build --per 3`): for the 500 living Polish figures with the most
Wikipedia editions in scam-prone occupations (politicians, journalists, presenters, economists, entrepreneurs, doctors,
clergy, actors, athletes, singers …) + the 25 international + 25 curated people (534 in total), up to 6 photos from each
person's Commons category (signatures, coats of arms, graves, logos and .svg filtered by file name). An extra photo is
kept only if its best face matches the person's own portrait at 0.45 ≤ cos ≤ 0.97 (same person, not a duplicate).
2,363 downloaded → **1,002 kept, 616 rejected** (group photos, other people in the category, no face) → 7,364 photos.
Fetch 12 min / 167 MB (serial Commons API calls; parallel ones got rate-limited), build 4.6 min CPU.

Ablation (same 11 truth faces, rule cos ≥ 0.45 and lead ≥ 0.10, without the 25 hand-picked photos):

| gallery (6,299 people) | photos | TP | FP | FN | precision | recall |
|---|---|---|---|---|---|---|
| Wikidata portrait only | 6,338 | 7 | 0 | 4 | 1.00 | 0.64 |
| **Wikidata portrait + Commons extras** | **7,340** | **9** | **0** | **2** | **1.00** | **0.82** |
| + hand-picked photos (shipped index) | 7,364 | 9 | 0 | 2 | 1.00 | 0.82 |

So the automatic extras replace manual photo curation: Olejnik 0.42 (lost) → 0.53, Glapiński 0.52 with a 0.04 lead
(rejected) → 0.65 with 0.17. Impostor scores barely move (max 0.48 on p5, its lead 0.09 stays below 0.10), so the
rule is unchanged. Caveat: Olejnik and Glapiński are ranks 509 and 526 by editions; they got extras only because the
curated list forces them in. **Next: extend `--top` to ~2,000 people (≈ 45 min, ≈ 0.6 GB)** so that people at
their level of fame are covered without curation. The 2 misses (p5's profile-view studio still) are a face-quality
limit, not a gallery gap.
Use: persons layer (named identity, weight ~2: celebrities are reused across operators), cross-modal check "face in
the ad = person in the landing story", and the Impersonation radar.

(g) Conformal (120 novel / 64 known queries, 200 splits): target α 0.01/0.05/0.10 → achieved 0.060/0.051/0.059 at
power 0.97; a-priori τ = 5: 0 false links, power 0.92.

## 3. What each signal contributes (approach a, sample_v1, avg-link τ = 5)

| Setting | B³-F1 | ARI | pair AUC | LOCO link | LOCO not-link |
|---|---|---|---|---|---|
| all layers | 1.00 | 1.00 | 1.000 | 1.00 | 1.00 |
| drop **tracking** (pixel, CAPI, AW/GA4) | 0.90 | 0.63 | 1.000 | 1.00 | 1.00 |
| drop **content** (templates, text MinHash, persons, comment names) | 0.97 | 0.96 | 0.999 | 0.75 | 1.00 |
| drop kit / infra / ad / persons / visual / negatives | 1.00 | 1.00 | ≥ 0.997 | 1.00 | 1.00 |
| only content | 0.90 | 0.63 | 0.989 | 1.00 | 1.00 |
| only tracking | 0.90 | 0.74 | 0.812 | 0.63 | 1.00 |
| only kit | 0.86 | 0.57 | 0.994 | 0.75 | 1.00 |
| only infra / ad / visual / persons | 0.75–0.78 | 0–0.20 | 0.53–0.69 | 0 | 1.00 |

Robustness by input layer (accuracy of perturbed queries; wrong links are 0 in every cell):

| Incident variant | dup | −screenshot | −HAR | −HTML | swap domain | new pixel+domain | 502 page | full rotation |
|---|---|---|---|---|---|---|---|---|
| landing only | 1.0 | 1.0 | 1.0 | 0.87 | 1.0 | 1.0 | 0.47 | 1.0 |
| + EasyOCR ad fields + faces | 1.0 | 1.0 | 1.0 | 0.87 | 1.0 | 1.0 | 0.67 | 1.0 |
| + VLM ad fields + faces (max-linkage) | 1.0 | 1.0 | 1.0 | 0.87 | 1.0 | 1.0 | 0.80 | 1.0 |
| + embeddings + conjunction (final) | 1.0 | 1.0 | 1.0 | 0.87 | 1.0 | 1.0 | 0.87 | 1.0 |

What carries what — **tracking IDs** join persona-swap variants (A1↔A2 only via pixel+CAPI); **content** carries
variants across full infra rotation (templates, text, fake-commenter roster); **kit IDs** (tenant, lander UUID, asset
hashes) give near-proof links and the operator level; **the ad layer** rescues dead landings (502) — VLM > OCR;
**infra enrichment** (NS pair, registration batch) confirms operators and, via the conjunction rule, recovers variants
whose landing stack was rebuilt (d3); **embeddings** add nothing on top of typed content here and over-link held-out.
Real-data checks the synthetic tests missed: an English 502 page created a spurious language-conflict (fixed: error
pages produce no content negatives); the p1 capture bundle is the same visit as p1 (fixed: L0 `entry_url` with a
visit/click id).

## 4. Recommended end-to-end flow

```
INGEST (PC/API worker)   adapters: sample_dir · capture bundle (archive_info.json) · capture-tool dir (manifest.json+dom.html)
                         · multi-HAR click chains · strona_N funnels · phone screenshots · video + yt-dlp info.json
EXTRACT (CPU, ~0.3–3 s/incident)
  tracking  fb_pixels, capi_gateways, google_ads, ga4, gtm, tiktok/snap
  kit       kit_tenants NEW, lander_ids NEW, landing_type_ids NEW, asset_hashes (minus brand_asset_hashes NEW),
            DOM MinHash, video_hosts NEW, url_param_schema, entry_path_template, path_shapes NEW, kit_endpoints (platform)
  content   headline/h1 template (names masked), persons (public-figure gazetteer), comment_names NEW, brands, vertical,
            products, ad_name grammar, text MinHash
  infra     landing etld1 (campaign-level), chain/tracker domains (operator-level) NEW, origin IPs (CDN-aware), cert
ENRICH (PC worker, cached; never contacts scam hosts)   NS pair NEW · RDAP registrar+created → registrar_batch NEW · crt.sh · ASN
MEDIA     WCSS: Qwen3.6-35B-A3B → ad.{advertiser, caption, overlay, library_id, display_link, cta, is_decoy, vertical}
          PC:   creative pHash; YuNet+SFace face embeddings (link at cos ≥ 0.45); EasyOCR fallback when WCSS is down
          TODO: video keyframes → VLM, ASR (faster-whisper) for video-only ads (DANE folder 5)
EMBED     optional: Qwen3-Embedding-0.6B text_emb (pgvector) — kNN blocking + weak supporting evidence only
LINK      blocking (inverted index on IDs/templates/hashes, MinHash-LSH, kNN) → typed evidence per candidate pair:
          {type, layer, level: campaign|operator_only|platform, value, weight = strength × rarity, df, N}
          score_campaign = Σ campaign-level + min(Σ operator-only, 4) if content/ad agreement ≥ 2.5 ; negatives
          score_operator = Σ all
DECIDE    L0 duplicate: same entry URL with visit/click id, or text MinHash ≥ 0.9 & pHash ≤ 6         → merge
          assign:    max-linkage score_campaign ≥ 5 and margin ≥ 1                                      → campaign X
          ambiguous: two campaigns ≥ 5 within margin 1                                                  → analyst
          confirm:   1 ≤ best < 5  → LLM adjudicator may VETO/annotate (Haiku on features; Qwen/PLLuM on WCSS with raw)
          new:       < 1;  plus flag "same operator as X" when score_operator ≥ 3
          insufficient: no landing content and no ad layer (e.g. 502 without screenshot)
          batch view: avg-linkage components on score_campaign (campaigns), Louvain inside (variants),
                      score_operator ≥ 3 components (operators / operations)
EXPLAIN   evidence chips per link; "why not linked" = best candidate + missing/conflicting items (e.g. tenant f141c307 ≠ 007e0023)
```

Strengths (a-priori, one near-proof ID ≈ 6): entry_url 8 · lander_id 7 · pixel/CAPI/AW/GA4/tenant/landing etld1 6 ·
asset_hash 5 (rarity-weighted) · text MinHash 5 · headline template 4 · NS pair 4 · chain domain 4 (op) · ad caption
(exact, > 25 chars) 3.5 · registrar batch 3 · path shape 3 (op) · face 2.5 · comment names 2 · brand assets 0.5 ·
kit endpoints 1 (platform). Negatives: tenant conflict −5, language conflict −2, vertical conflict −1 (never on error pages).

| Component | Where | Why |
|---|---|---|
| ingest, extract, enrich, evidence, decisions, faces, pHash, explanations | PC / docker CPU | deterministic, < 1 s per incident, judges need no GPU or key |
| ad VLM, OCR-VLMs, Polish LLMs, batch embeddings, future M1/M2 training | WCSS (PBR grant) | raw organizer material may go there; H100s |
| adjudicator rationale / agent | Claude API on features only, or WCSS for raw | data rule |
| judge / offline mode | precomputed VLM fields + EasyOCR fallback + cached enrichment | `docker compose up` without WCSS or keys |

## 5. Costs (measured)

| Item | Measured | Projection |
|---|---|---|
| extraction | sample 15 in 3.6 s (56 s cold, 36 MB HAR); DANE 10 in 27 s | ~1–3 s/incident CPU |
| evidence scoring | 105 pairs in 40–80 ms | blocking keeps it linear |
| enrichment | 23 domains in ~6 min (crt.sh dominates) | cache per eTLD+1 |
| ad VLM | Qwen3.6-35B-A3B 2.7 s/img, Qwen3.8-27B 9.6 s/img (unbatched, shared H100) | batched ≫ 1k img/h → 10k ads ≈ 1–3 GPU-h |
| embeddings (WCSS CPU 32 cores, 25 items) | mmlw 7 s, bge-m3 16 s, Qwen3-Emb 32 s, SigLIP 9 s (incl. load) | minutes per 10k on GPU |
| faces | 72 ms/screenshot CPU; gallery fetch ≈ 20 min / 484 MB + extras 12 min / 167 MB, index build ≈ 5 min CPU (6,305 people / 7,364 photos) | gallery refresh weekly |
| **WCSS GPU-hours charged to us** | **0** (all GPU inference ran inside the other session's live allocation via `srun --overlap`) | ~4976 GPU-h left on PBR |
| WCSS CPU-hours | ~2 (4 short CPU jobs) | — |
| Claude adjudicator via `claude -p` | $0.48 / 105 pairs (CLI overhead ~90k cached tokens per call) | direct API ≈ 1.2k in / 150 out per pair: Haiku 5.5 ≈ $0.0002, Sonnet 5.5 ≈ $0.004; Batch −50%; only the uncertain band |
| Qwen3.8 adjudicator on WCSS | 105 pairs / 51 s (8 workers), 1.15k in / 64 out tokens | marginal cost 0 while the server is up |

## 6. Open risks

1. **25 incidents.** The two DANE-driven rules are principled but post-hoc; thresholds are a-priori. The hidden set will
   contain DANE-like shapes (videos, phone screenshots, funnels, Google Ads) — expect lower coverage there.
2. **Max-linkage + conjunction can over-merge** if one operator runs many narratives with shared fake personas (K ↔ C
   already share the fake author "Natalia Pacholczyk"). Watch wrong-link counts; the operation level absorbs most of it.
3. **Label granularity is a choice** (persona swap = same campaign; shared funnel = same operation, different campaign).
   Both LLMs split A1/A2. If the organizers label by funnel, report the operation level as "campaign".
4. **Video-only ads** (DANE 5) are unattributable without keyframe VLM + ASR — next extractor to build.
5. **Face gallery**: coverage stops at the Wikidata cut (≥ 5 language editions, 6.3k people) — local influencers,
   doctors and fake personas are outside it; bigger galleries need more photos per person to stay precise (§2c);
   extra photos currently cover only 534 people (the top 500 + forced-in lists).
   Recall on profile/low-res
   faces is limited (p5). Face embeddings of real people are biometric data: keep the gallery local, use it only to flag
   impersonation, document it in DATA_SOURCES.md.
6. **WCSS**: SSH is rate-limited per IP (use the home-PC ControlMaster, `wcss/README.md`); the vLLM server belongs to
   another session and its model list changes (Qwen3.8 → Qwen3.6 mid-run); offline fallback costs ~0.13–0.2 recall on
   dead landings.
7. **Cloud data rule**: cloud dossiers contain IDs, templates and fake-commenter names extracted from organizer data —
   confirm with the organizers, or adjudicate on WCSS only.

## 7. Reproduce

```bash
cd experiments
uv run python run_extract.py ../data/raw/sample_v1 ../data/experiments/sample_v1/incidents.json
uv run python run_infra.py ../data/experiments/sample_v1/incidents.json        # f
uv run python run_media.py ../data/experiments/sample_v1/incidents.json        # EasyOCR + pHash
uv run python run_faces.py ../data/experiments/sample_v1/incidents.json        # e
#  WCSS (wcss/README.md): vlm_extract.py (d), embed_batch.sbatch (b), adjudicate.py (h), mega_dl.mjs (DANE)
uv run python score_vlm.py ../data/experiments/sample_v1                       # d
uv run python merge_enrich.py ../data/experiments/sample_v1 incidents_all.json --ad qwen38-27b-fp8 --faces --emb qwen3emb
uv run python run_a_evidence.py ../data/experiments/sample_v1/incidents_all.json   # a + ablation + operator level
uv run python run_b_embed.py ../data/experiments/sample_v1                     # b
C_VARIANT=layers uv run python run_c_gbm.py ../data/experiments/sample_v1/incidents_full.json   # c (LOCO)
uv run python run_g_conformal.py ../data/experiments/sample_v1/incidents_all.json  # g
uv run python run_h_adjudicator.py ../data/experiments/sample_v1/incidents_full.json claude haiku 6   # h
# DANE
python -I safe_unzip.py ../data/raw/dane/DANE.zip ../data/raw/dane/unpacked
uv run python merge_enrich.py ../data/experiments/dane incidents_q36.json --ad qwen36-35b-a3b
uv run python run_dane_eval.py incidents_q36.json      # a: open-set, incremental, joint
uv run python run_b_joint.py                           # b held-out
uv run python run_c_dane.py                            # c held-out
# face gallery (needs WIKIMEDIA_UA="name/version (contact: <address>)" in the shell; never commit the address)
uv run python -m rp.gallery fetch --min-sitelinks 5     # Wikidata portraits
uv run python -m rp.gallery fetch-extra --top 500       # Commons extras (resumable)
uv run python -m rp.gallery build --per 3               # offline: detect + SFace -> index_sface.npz
uv run python run_faces_id.py                           # truth test; FACES_NO_CURATED=1 / FACES_INDEX=... for ablations
```
Logs/JSON: `data/experiments/{sample_v1,dane,joint}/` (git-ignored).
