# Research 2: data sources, metadata services, building blocks, prior work

> Research subagent report, 2026-11-21 morning. Use it for `docs/DATA_SOURCES.md` (licenses and limits) and the related-work section of METHODOLOGY.
> Items marked **[uncertain]** weren't confirmed from official pages. Later verification on 21.11: the Meta Ad Library API **works** with our token for PL; the urlscan and IPinfo keys work; BigQuery works from the laptop (gcloud ADC, project `gen-lang-client-0264807540`), not yet on the home PC.

Short version: Meta's official Ad Library API is the source to build the scheduler on, with its public web UI as a fallback for creatives and landing links. For infrastructure, crt.sh, RDAP, DNS, ipinfo Lite and Shodan InternetDB are cheap and solid, plus the CERT Polska warning list, the most useful single feed for Polish domains.

## A. Ad library access

**Meta Ad Library API (`ads_archive`)**, the one realistically usable for the Hunter:
- **What it gives:** under the DSA, any ad that reached an EU country is returned whatever its topic (outside the EU only political/issue ads).
  - Filters: `search_terms` (≤ 100 chars), `search_type` (keyword or exact phrase), `ad_reached_countries=['PL']`, `ad_active_status`, delivery-date min/max, `languages`, `media_type`, `publisher_platforms`, `search_page_ids` (≤ 10).
  - Fields for all ads: `id`, `ad_creation_time`, `ad_creative_bodies`, `ad_creative_link_captions`, `ad_creative_link_titles`, `ad_creative_link_descriptions`, `ad_delivery_start_time`, `ad_delivery_stop_time`, `ad_snapshot_url`, `languages`, `page_id`, `page_name`, `publisher_platforms`.
  - EU-only fields: `eu_total_reach`, `beneficiary_payers`, `target_ages`, `target_gender`, `target_locations`, `age_country_gender_reach_breakdown`.
  - Docs: https://developers.facebook.com/docs/graph-api/reference/ads_archive/ and https://developers.facebook.com/docs/marketing-api/reference/archived-ad/
- **Gaps:**
  - No landing URL, image or video field; link captions are text (often the displayed domain).
  - `ad_snapshot_url` is a rendered page that needs the token: fetch it with Playwright to get the creative and the outbound link.
  - Spend and impressions are only returned for political ads.
- **Auth:** a Meta developer app plus a user token after identity verification. Long-lived tokens last ~60 days. Rate limits are the standard Graph API ones (error 613 = throttled; ~200 calls/h/token **[uncertain]**).
- **No-auth alternatives:** the public web UI's GraphQL (Playwright scrapers such as https://github.com/NiksHacks/meta-ads-library-scraper) is against the ToS and brittle. Apify actors are paid (~$5 per 1k results).
- **Domain caveat** (RTR/ÖIAT, Dec 2025): celebrity-bait ads are often **not findable by the celebrity's name**, and the payer field is unverified free text. Search by lure phrases, known `page_id`s and `media_type=VIDEO` instead. https://www.rtr.at/medien/aktuelles/publikationen/Publikationen/Publikationen_2026/Betrugsoekosystem_Werbung_KommAustria_final_EN.pdf
- **Landing pages** use cloakers: crawl with a PL IP, a mobile UA, a Facebook referrer and the original params, or you get a harmless decoy page.

**Google Ads Transparency Center:** no official API, but a free BigQuery public dataset `bigquery-public-data.google_ads_transparency_center` (`creative_stats`, `removed_creative_stats`). It covers EEA/Turkey advertisers, lags, and has no creative text or images (only advertiser, region, format, dates, creative URL). The BigQuery sandbox gives 1 TB of queries a month free. Good for advertiser-level enrichment and removal reasons as weak labels, not for creatives.

**TikTok Commercial Content Library:** the web UI (library.tiktok.com) needs no login; the API needs an approved project, too slow for a hackathon. https://developers.tiktok.com/products/commercial-content-api

**LinkedIn Ad Library:** an API only after it's granted to the app. Not relevant for this kind of scam.

**X Ads Repository:** a UI and/or CSV downloads **[uncertain]**. Low value.

**Realistic plan:** Meta API (with a Playwright fallback) for the scheduler; optional Google BigQuery; TikTok, LinkedIn and X out of scope.

## B. Infrastructure metadata

| Source | What it gives | Auth / limits | License / terms |
|---|---|---|---|
| RDAP/WHOIS (`whoisit` MIT, `asyncwhois`, `python-whois`) | registrar, creation date, nameservers; `.pl` (NASK) WHOIS is heavily redacted | free; registries throttle | data belongs to the registry |
| `dnspython` | A/AAAA/NS/MX/TXT, which lead to hosting pivots | none | ISC |
| crt.sh (JSON or its public Postgres) | SANs → sibling domains; issuance times → campaign timeline | none, but often slow or 502; cache and retry | free |
| urlscan.io | search (`page.domain`, `hash:`, `page.asn`), submit scans, screenshot, DOM, redirect chain | API key mandatory since May 2026; free quotas ~1k searches/day **[uncertain]**; free scans are public | free tier non-commercial |
| VirusTotal public API | URL/domain reputation, relations | 4 requests/min, 500/day | non-commercial |
| Shodan InternetDB (`internetdb.shodan.io/{ip}`) | ports, hostnames, CPEs | no key | non-commercial |
| Shodan / Censys free | favicon-hash and host search | Censys 100 credits/month | non-commercial |
| ipinfo Lite | ASN + country | token; unlimited | attribution required |
| ip-api.com | ASN, org, city | 45 requests/min, HTTP only | non-commercial |
| Wayback CDX | historical snapshots of short-lived pages | no key; ~1 request/s politeness | free |
| Favicon hash `mmh3(base64(favicon))` | a strong kit-clustering signal | local | `mmh3` MIT |
| Google Safe Browsing v4/v5 | known-bad flag | API key | non-commercial (commercial use means Web Risk) |
| **CERT Polska list** `hole.cert.pl/domains/v2/domains.txt` | active PL scam domains; ground truth and seed list | none | no explicit license; NASK disclaims liability |
| PhishTank / OpenPhish community feed | phishing URLs | PhishTank registration closed; OpenPhish updates every 6–12 h | restrictive / free community tier |

## C. Building blocks (with licenses)

- **Capture:** Playwright (Apache-2.0). Record the redirect chain (`request.redirected_from`, `framenavigated`, plus JS and meta-refresh hops), a HAR (`record_har_path`), screenshot, final DOM, favicon, outbound links and form `action` targets.
- **HTML similarity:** DOM tag-path 5-gram shingles → MinHash + LSH (`datasketch`, MIT); sets of external script/CSS paths and form endpoints (kit fingerprints).
- **Image similarity:** `imagehash` (BSD-2), near-duplicate at Hamming ≤ 10. `open_clip` (MIT code, LAION weights MIT); SigLIP/SigLIP2 (Apache-2.0); multilingual `xlm-roberta-large-ViT-H-14` (MIT).
- **Faces:** InsightFace code is MIT, but **its models are non-commercial research only**. Alternatives: facenet-pytorch (MIT code; VGGFace2 weights carry research caveats), DeepFace (MIT wrapper), **YuNet + SFace (OpenCV Zoo, Apache-2.0; the experiments chose these)**, AuraFace (Apache-2.0).
- **OCR:** EasyOCR (Apache-2.0, `pl`), PaddleOCR (Apache-2.0), Tesseract `pol` (Apache-2.0).
- **ASR:** faster-whisper (MIT) with Whisper large-v3-turbo weights (MIT).
- **Polish text embeddings:** `BAAI/bge-m3` (MIT), `intfloat/multilingual-e5-large` (MIT), `sdadas/mmlw-roberta-large` (Apache-2.0, PL-MTEB 63.2), Qwen3-Embedding (Apache-2.0). Paper: https://arxiv.org/pdf/2405.10138
- **Keywords:** KeyBERT (MIT); YAKE (believed LGPL-3.0, verify). Regexes for phones, IBANs, Telegram handles, wallets and PL brands are cheap and very discriminative.
- **Vector store:** FAISS (MIT), Qdrant (Apache-2.0), pgvector (PostgreSQL license; chosen).
- **Clustering:** a typed similarity graph → high-precision connected components + Louvain (`networkx`, BSD-3). Leiden (`leidenalg`) is GPL-3.0, so avoid it. HDBSCAN (`sklearn`, BSD-3) for the purely semantic view.
- **Explainable scoring:** Fellegi-Sunter log-likelihood weights (m/u) per feature ("+4.2 same favicon hash"); Splink (MIT) implements it.
- **Graph store/visualisation:** Neo4j Community is GPLv3 with operational overhead. NetworkX + Cytoscape.js (MIT) / Sigma.js.
- **Evaluation:** ARI, NMI, Fowlkes-Mallows (sklearn); B-cubed P/R/F1 (a few lines). Open-set: assign if best ≥ τ else new; calibrate τ on held-out campaigns; report known-campaign accuracy plus new-campaign AUROC/F1.

## D. Prior work

- **Gen Digital, "Scam Ad Machine" (Feb 2026):** 14.57M Meta ads (EU+UK); 31% led to scam/phishing/malware; advertisers grouped by shared domains, URL patterns and payer/infrastructure; the top 10 advertisers ran 56% of scam ads. https://www.gendigital.com/blog/insights/research/scam-ad-machine-meta
- **Bitdefender (Mar 2026):** 310 coordinated Meta scam campaigns, 26k+ ad sightings, celebrity "will/testament" lures. The closest to our use case. https://www.bitdefender.com/en-us/blog/labs/global-investment-scam-network-using-meta-ads
- **RTR/ÖIAT (Dec 2025):** the Ad Library's limits for auditing fraud ads (link above).
- **Investigate Europe (Oct 2025):** DSA gaps around investment scam ads. https://www.investigate-europe.eu/posts/investment-scammers-slip-through-cracks-in-eu-big-tech-law
- **"Tracing Cryptocurrency Scams: Clustering Replicated Advance-Fee and Phishing Websites":** HTML-similarity clustering of scam sites into campaigns. https://arxiv.org/pdf/2005.14440
- **Reference-based phishing detection** (brand/visual matching, not clustering):
  - Phishpedia (USENIX Sec 2021), PhishIntention (USENIX Sec 2022): https://github.com/lindsey98/PhishIntention
  - VisualPhishNet (CCS 2020): https://github.com/S-Abdelnabi/VisualPhishNet
  - KnowPhish (USENIX Sec 2024): https://arxiv.org/html/2403.02253v2
  - Check each repo's license before reuse.
- **Meta's own celeb-bait face matching** (tested from Oct 2024, later EU/UK). https://about.fb.com/news/2024/10/testing-new-ways-to-combat-scams-help-restore-access-to-compromised-accounts/
- **Gap:** no peer-reviewed 2025–26 paper specifically on clustering celebrity-bait ads was found. Most work is industry or regulator reports, which is a point for our methodology write-up.

## Things still to verify
- urlscan free daily quotas (`/user/quotas` with our key).
- YAKE's license (we don't plan to use it).
- Whether the CERT PL list may be redistributed (no explicit license; we only use it for lookups).
