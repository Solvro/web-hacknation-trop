# TROP — methodology

> TROP ("follow the fake") groups scam advertisements into **campaigns**, **operators** and **operations**, and explains every link with typed, rarity-weighted evidence.
> This document covers how features are acquired, the evidence model, the decision states, the evaluation with numbers, and what we tried that failed.
> Reproduction: `experiments/` (frozen research code, `experiments/RESULTS.md`) and the product port (`backend/trop/engine`, `trop eval`).
> Contains identifiers derived from organizer data — private repository only.

## 1. Problem and label definition

An *incident* is one observed scam ad plus whatever we could capture behind it: the ad creative (screenshot, video, Ad Library record), the landing page (HTML, HAR, screenshots, click chain) and enrichment of the domains.

We label at four levels; the product reports all of them because the organizers' label definition is unknown:

| Level | Meaning | How we recognise it |
|---|---|---|
| **L0 duplicate** | the same visit captured twice | identical entry URL with a high-entropy visit/click id, or text MinHash ≥ 0.9 and pHash ≤ 6 |
| **L1 variant** | same campaign, different persona/headline/domain | Louvain communities inside a campaign |
| **L2 campaign** (primary) | same operator **and** same narrative/offer family | `score_campaign` (max-linkage ≥ 5) |
| **L3 operator** | same operator account across narratives | `score_operator` ≥ 3 components |
| **operation** | campaigns that share one funnel (pre-lander → lander network) | operator-level components including chain domains |

"Persona swap = same campaign" (e.g. the same fake-portal lure with Brzoska or Morawiecki) and "shared funnel = same operation, different campaign" are deliberate choices, backed by the DANE data (§5).

## 2. Feature acquisition (per layer)

All extraction is deterministic, CPU-only and takes ~0.3–3 s per incident. Models are used only where pixels or audio must become text, and every model response is cached by input hash, so the judge build runs offline without keys.

| Layer | Features | Source in the material |
|---|---|---|
| **Tracking** | Facebook pixel ids, CAPI gateway hosts, Google Ads AW ids, GA4, GTM, TikTok/Snap pixels | HAR requests, saved HTML, Chrome's pixel-named `_files/` |
| **Kit** | kit tenant UUID, lander UUID, landing-type UUID (leaked in kit POST bodies), asset body hashes (minus brand assets such as outlet logos), DOM tag-path MinHash, URL parameter grammar, entry path template, lander path shape, kit endpoint templates, third-party stack, video hosts | HAR bodies, URLs, saved assets |
| **Infra** | landing eTLD+1 (campaign-level), click-chain and tracker domains (operator-level), origin IPs (CDN-aware: Cloudflare IPs weigh 0), NS pair (= Cloudflare account), RDAP registrar + creation time → registration batch, crt.sh certificate batches | URLs, HAR `serverIPAddress`, cached enrichment |
| **Content** | headline / h1 template with person names masked (`{PER}`), text MinHash (5-shingles), persons (gazetteer), fake-commenter roster, brands, products, vertical, language, ad-name grammar | landing text and DOM |
| **Ad** | advertiser, caption (exact, > 25 chars), overlay text, display link, library id, decoy flag | ad screenshot → VLM (Qwen3.6-35B-A3B; Gemini Flash fallback; EasyOCR offline), Ad Library API, yt-dlp `info.json` |
| **Persons** | face identity (YuNet + SFace against a 6,305-person gallery of Polish public figures + abused international figures) | ad screenshots, video keyframes |
| **Visual** | creative pHash, landing screenshot pHash | images |
| **Media** | transcript and on-screen text of video ads (Gemini video pass; ASR fallback), voice id | video files |

Rules that came from real data:
- An error page (e.g. a Cloudflare 502) produces **no content evidence and no content negatives** (an English 502 page once created a spurious language conflict).
- The full entry URL is kept (visit id, parameter grammar, `ad_name` leaks); it is what detects L0 duplicates.
- Every HAR of a click chain is merged; the first document of each HAR is recorded as `landing.chain_urls`.
- **Person identity is never taken from a VLM or LLM.** Both Qwen VLMs renamed one politician as another in tests. Names come only from the face gallery with the rule cos ≥ 0.45 and lead over the runner-up ≥ 0.10 (precision 1.00, recall 0.82 on the 11 truth faces).

## 3. Evidence model

For every candidate pair (blocked by inverted indexes on identifiers, templates and rare hashes, so it stays near-linear), each shared value becomes one evidence item:

```
weight = strength(type) × rarity(value)        rarity = 1 for identifiers; IDF-normalised for shape-like values
item   = {type, layer, level: campaign | operator_only | platform, value, weight, df, N}
```

A-priori strengths (one near-proof id ≈ 6): entry URL 8 · lander id 7 · pixel / CAPI / AW / GA4 / tenant / landing eTLD+1 6 · asset hash 5 (rarity-weighted) · text MinHash 5 · headline template 4 · NS pair 4 · chain domain 4 (operator) · ad caption 3.5 · registrar batch 3 · path shape 3 (operator) · face 2.5 · comment names 2 · brand assets 0.5 · kit endpoints 1 (platform).
Negatives, only when a high-strength field is present on both sides and conflicts: tenant conflict −5, language conflict −2, vertical conflict −1. **A missing value is never evidence of difference**; it lowers coverage instead.

Two scores per pair:

```
score_operator = Σ all evidence
score_campaign = Σ campaign-level evidence
               + min(Σ operator-only evidence, 4)   only if content/ad agreement ≥ 2.5      (conjunction rule)
```

- **Operator-only evidence** (kit tenant, NS pair, registrar batch, chain domains, path shape, third parties, landing-type id, origin IP, cert batch, …) identifies the operator's account, not a specific campaign: one operator runs several campaigns from one Cloudflare account or kit tenant.
- **Chain-domain rule:** a lander reached by click-through is shared by several pre-lander campaigns, so chain domains are operator-level. Counting them as campaign evidence produced the only wrong link on DANE.
- **Conjunction rule:** same operator AND same narrative ⇒ same campaign. It recovers a variant whose landing stack was rebuilt (d3 ↔ p5: same Cloudflare account and same persona) while keeping "same operator, different product" apart (p6 vs p12, p9 vs p10).

## 4. Decisions

Open-set assignment of a new incident against the known campaigns uses **max-linkage** (the best single member link): the PLAN's "max + mean of top 3" diluted strong links (502-page recovery 0.53 → 0.80 with max).

| State | Rule | UI |
|---|---|---|
| **assign** | best `score_campaign` ≥ 5 and margin over the runner-up ≥ 1 | „Dołącza do kampanii KMP-… · pewność p” |
| **ambiguous** | two campaigns ≥ 5 within the margin | „Niepewne → triage” (both candidates side by side) |
| **confirm** | 1 ≤ best < 5 | analyst confirms; the LLM adjudicator may veto or annotate |
| **new** | best < 1 | „Nowa kampania (kandydat)”, plus „ten sam operator co …” when `score_operator` ≥ 3 |
| **insufficient** | no landing content and no ad layer | ask for a screenshot / archive copy / agent run |

**Confidence ("pewność")** is an isotonic/Platt fit of `score_campaign` → P(same campaign) on the labelled pairs, stored per engine version. The conformal threshold τ(α) is implemented but shown only in `/lab`: at n ≤ 25 it is unreliable (tied scores; achieved 5–6 % error against a 1 % target), so the a-priori τ = 5 ships.

Batch view (the hidden-test mode, `trop batch` / „Importuj zbiór”): average-linkage on `score_campaign` (τ = 5; stable for τ ∈ [2, 10]) for campaigns, Louvain inside each campaign for variants, `score_operator` ≥ 3 components for operators and operations. `results.csv` carries both the campaign and the operation column.

Explanations: every link shows its evidence chips (type, value, strength, weight, rarity df/N), what was missing on either side, conflicts, values zeroed for being too common (Cloudflare, facebook.net, jQuery CDNs), and a "why not" view against the best other candidate (e.g. tenant f141c307 ≠ 007e0023).

## 5. Evaluation

Data: sample_v1 (15 incidents, 9 campaigns) and DANE (10 official incidents, held out; 9 labelled queries: 3 should link to a sample campaign, 6 are new). 25 incidents, 14 campaigns. Labels: `experiments/labels.yaml`, `experiments/labels_dane.yaml`.

### 5.1 sample_v1 (LOCO = leave-one-campaign-out open set; 8 link, 15 not-link queries)

| Approach | B³-F1 | ARI | LOCO link | LOCO not-link | wrong links | 502 page | full infra rotation |
|---|---|---|---|---|---|---|---|
| **Evidence engine, final** | **1.00** | **1.00** | **1.00** | **1.00** | **0** | 0.87 (0 wrong) | 1.00 (0 wrong) |
| single score (no campaign/operator split), Louvain | 0.87 | 0.60 | 1.00 | 0.87 | 2 | — | 0.93 (1) |
| Qwen3-Embedding text, τ tuned on these items | 1.00* | 1.00* | 1.00* | 1.00* | 0* | n/a | 1.00 |
| mmlw / bge-m3 + HDBSCAN | 0.78 | 0.37 | — | — | — | n/a | — |
| LightGBM on the 40-dim evidence vector (LOCO) | 0.83–0.86 | 0.51–0.57 | 0.50 | 0.53 | 7 | 0.67 (3) | 0.67 (3) |
| LightGBM on layer sums + hand scores (LOCO) | 0.93–0.97 | 0.93–0.96 | 1.00 | 0.73 | 4 | 0.87 (2) | 0.93 (1) |
| LLM adjudicator alone (features), pair accuracy | 0.92–0.95, 0 false positives | | | | | | |

\* tuned on the evaluation items; the best τ swings 0.52–0.92 across models.

### 5.2 Held-out DANE (known = sample_v1)

| Approach | open-set correct | wrong links | incremental B³ / ARI | joint batch (24 items) B³ / ARI |
|---|---|---|---|---|
| **Evidence engine, final** | **9/9** | **0** | **1.00 / 1.00** | **1.00 / 1.00** |
| engine as frozen before DANE | 8/9 | 0 | 0.94 / 0.85 | 0.98 / 0.98 |
| Qwen3-Embedding, τ tuned on sample | 6/9 | 3 | — | 0.88 / 0.66 |
| mmlw / bge-m3 | 5/9 | 3–4 | — | 0.78 / 0.50 |
| SigLIP screenshot embedding | 7/9 | 0 | — | 0.78 / 0.26 |
| LightGBM trained on all sample pairs | 5/9 | 3 | — | 0.93 / 0.93 |

Operator/operation level on the 24 items: B³-F1 0.93 (components, τ_op = 3); all errors are missing weak links inside the operation (K ↔ A/C share only a fake byline and a kit platform).

Honesty note: the chain-domain and conjunction rules were added after the first DANE run. Both follow from the label definition and were re-validated on sample_v1 LOCO, but not on unseen data.

### 5.3 Robustness (perturbed queries; wrong links are 0 in every cell)

| Input | dup | −screenshot | −HAR | −HTML | swap domain | new pixel+domain | 502 page | full rotation |
|---|---|---|---|---|---|---|---|---|
| landing only | 1.0 | 1.0 | 1.0 | 0.87 | 1.0 | 1.0 | 0.47 | 1.0 |
| + VLM ad fields + faces (final) | 1.0 | 1.0 | 1.0 | 0.87 | 1.0 | 1.0 | 0.87 | 1.0 |

### 5.4 Ablation (sample_v1)

Dropping tracking: B³ 1.00 → 0.90 (tracking joins persona-swap variants). Dropping content: LOCO link 1.00 → 0.75 (content carries variants across full infra rotation). Kit ids give near-proof links and the operator level; the ad layer rescues dead landings; infra enrichment confirms operators and, through the conjunction rule, recovers rebuilt variants.

### 5.5 Ad screenshots and faces

| Extractor | advertiser | library id | caption | s/img |
|---|---|---|---|---|
| EasyOCR + heuristics (CPU, offline fallback) | 9/14 | 3/3 | 10/12 | 10 |
| **Qwen3.6-35B-A3B** (shipped) | **14/14** | **3/3** | **12/12** | **2.7** |

Faces (YuNet + SFace, 6,305 people / 7,364 photos): 9 TP / 0 FP / 2 FN on 11 truth faces; a second Commons photo per person replaces manual curation.

## 6. What failed, and why

- **Embedding clustering over-links held-out data** (3–4 wrong links on DANE): semantic similarity of scam stories is high across unrelated operators, and the best threshold depends on the model.
- **A learned GBM over the evidence vector** trained on 15 incidents learns the training campaigns (7 wrong links in LOCO). It is kept as a future M1 once there are many labelled campaigns; labelling functions are 100 % accurate on 98 of 105 gold pairs, so weak labels are cheap.
- **One score instead of two** merges different products of the same operator (2 wrong links).
- **Mean-of-top-3 aggregation** dilutes the single strong link that rescues degraded captures.
- **VLMs for person identity**: renamed politicians; replaced by the face gallery.
- **Conformal open-set thresholds** at n ≤ 25: ties make the achieved error miss the target; shown in the Lab only.

LLMs and embeddings therefore act only as support or veto: the adjudicator may veto a `confirm` link, never create one.

## 7. Limits

25 labelled incidents; the hidden set probably contains more DANE-like shapes (videos, phone screenshots, funnels, Google Ads). Coverage on video-only ads depends on the Gemini video pass. The face gallery stops at Wikidata's ≥ 5-language-edition cut; local influencers and invented personas are outside it. Max-linkage plus conjunction can over-merge an operator that reuses fake personas across narratives; the operation level absorbs most of that, and wrong-link counts are monitored in the Lab.
