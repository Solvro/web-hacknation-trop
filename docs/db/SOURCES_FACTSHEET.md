# External data sources: verified fact sheet (2026-11-21)

Companion to [DB_AND_SCRAPING.md](DB_AND_SCRAPING.md) §3.

These facts come from the official docs, read on 2026-11-21. A few unauthenticated GET/HEAD probes against harmless endpoints (cert.pl, 1.1.1.1, nic.click, crt.sh, urlscan search) confirmed the live behaviour.
- **[CHG]** marks a change made in 2025–2026.
- *unverified* means no official source confirmed the fact.

We did not sign up for anything.

## Two corrections to earlier assumptions
- **urlscan.io search still works without a key.** Since 2026-05-04 only `/result`, `/dom` and `/responses` require one. Anonymous search allows 30 req/min per IP and only reaches 30 days back.
- **OpenPhish has moved.** `openphish.com/feed.txt` now 302-redirects to `raw.githubusercontent.com/openphish/public_feed/refs/heads/main/feed.txt`.

---

## 1. Meta Ad Library API (`ads_archive`)

**Endpoint**
- `GET https://graph.facebook.com/v27.0/ads_archive`. The reference page shows v27.0, and v26.0 also works.
- Docs: [ads_archive ref](https://developers.facebook.com/docs/marketing-api/reference/ads_archive/)

**Search parameters**

| Parameter | Values / notes |
|---|---|
| `search_terms` | ≤ 100 chars, not translated, so query in Polish |
| `search_type` | `KEYWORD_UNORDERED` or `KEYWORD_EXACT_PHRASE` |
| `search_page_ids` | ≤ 10 |
| `ad_reached_countries` | `["PL"]` |
| `ad_active_status` | `ACTIVE`, `ALL` or `INACTIVE` |
| `ad_delivery_date_min` / `ad_delivery_date_max` | date range |
| `media_type` | — |
| `languages` | — |
| `publisher_platforms` | — |
| `ad_type` | `ALL` |

**Coverage**
- All ads delivered in the EU are included under the DSA.
- Non-EU ads appear only if they are about social issues, elections or politics.

**Fields**
- All ads:
  - creative text: `ad_creative_bodies`, `ad_creative_link_titles`, `ad_creative_link_captions`, `ad_creative_link_descriptions`
  - `ad_snapshot_url`, `page_id`, `page_name`
  - `ad_creation_time`, `ad_delivery_start_time`, `ad_delivery_stop_time`
  - `languages`, `publisher_platforms`, `total_reach_by_location`
- EU ads also return `eu_total_reach` and `beneficiary_payers`.
- EU and UK ads also return `target_ages`, `target_gender`, `target_locations` and `age_country_gender_reach_breakdown`.
- **There is no landing URL and no media URLs.**

**Access**
1. Identity confirmation at facebook.com/ID (can take days).
2. Create a developer app and accept the Ad Library API terms (no App Review needed).
3. Get a user token and exchange it for a long-lived one (about 60 days).

Step-by-step: [META_AD_LIBRARY_ACCESS.md](META_AD_LIBRARY_ACCESS.md).

**Limits and cost**
- Error 613 means "rate limited". There is no `ads_archive`-specific quota.
- App-level limit is 200 × users per hour (*unverified for this endpoint*).
- Free.

**ToS**
- "Platform APIs are the only allowable means to access data programmatically, unless you have our prior written permission" ([automated data collection](https://developers.facebook.com/docs/development/terms-and-policies/automated-data-collection/)).
- The web UI's internal GraphQL (`AdLibrarySearchPaginationQuery`) is undocumented, rotates its `doc_id`, and breaches the ToS: **do not automate it**.
- **[CHG]** The Automated Data Collection Terms were reportedly tightened on 2026-07-29 (*unverified*).

**Retention**
- EU ads stay visible for 1 year after their last impression, so archive your own snapshots.

**[CHG] Political ads**
- Since 2025-10-06 Meta no longer runs political ads in the EU, so the political-ads report is irrelevant for us.

## 2. Google Ads Transparency Center (BigQuery)

**Dataset**
- `bigquery-public-data.google_ads_transparency_center`, with tables `creative_stats` and `removed_creative_stats`.
- The same data is available as free JSON bulk downloads ([README](https://storage.googleapis.com/ads-transparency-center/api-data/README.txt)).

**`creative_stats` columns**
- Advertiser: `advertiser_id`, `advertiser_disclosed_name`, `advertiser_legal_name`, `advertiser_location`, `advertiser_verification_status`
- Creative: `creative_id`, `creative_page_url`, `ad_format_type`, `topic`
- Funding: `is_funded_by_google_ad_grants`, `ad_funded_by`
- `region_stats[]` (repeated):
  - `region_code`, `first_shown`, `last_shown`
  - `times_shown_start_date`, `times_shown_end_date`
  - `times_shown_lower_bound` / `times_shown_upper_bound`
  - `times_shown_availability_date`
- `audience_selection_approach_info.*`

**`removed_creative_stats` columns**
- `creative_page_url`, `region_stats`
- `disapproval.{removal_reason, violation_category, use_of_automated_means, removal_location, decision_type}`
- These are Google's own removal decisions, useful as weak labels.

**Limitations and coverage**
- No ad text, no landing URL and no media.
- Region stats cover the EEA (including PL) and Turkey. Impression data starts 2023-03-01.

**Cost**
- BigQuery free tier: 1 TiB of queries per month.
- Sandbox: no card needed, 10 GiB storage, tables expire after 60 days ([sandbox](https://docs.cloud.google.com/bigquery/docs/sandbox)).
- The dataset is about 150 GB (*unverified*), so always select explicit columns and set `maximum_bytes_billed`.

**Freshness and terms**
- "Updates periodically and may be delayed" (cadence *unverified*).
- Licence: Google ToS plus the [Ads Transparency Center terms](https://adstransparency.google.com/terms).
- There is no official API.

## 3. TikTok Commercial Content API

**Endpoint and fields**
- `POST https://open.tiktokapis.com/v2/research/adlib/ad/query/`, scope `research.adlib.basic`, client-credentials token ([query ads](https://developers.tiktok.com/doc/commercial-content-api-query-ads)).
- Fields: `ad.id`, `first_shown_date`, `last_shown_date`, `status`, `status_statement`, `videos`, `image_urls`, `reach`, `advertiser.business_id`, `business_name`, `paid_for_by`.

**Filters and paging**
- `ad_published_date_range` is required, with a minimum of 1 year back.
- `search_term` ≤ 50 chars.
- `max_count` ≤ 10 per page; paginate with `search_id` / `has_more`.

**Coverage**
- EU-27 plus NO, IS, LI, GB and CH.
- Data is kept while the ad runs and for 1 year after.

**Access**
- Developer account, official e-mail and an application. The answer comes in about 2 working days ([product page](https://developers.tiktok.com/products/commercial-content-api)).
- A third-party guide says commercial users are ineligible (*unverified*).

**Limits and cost**
- Nothing is published for this API. The Research API FAQ gives 1,000 req and 100,000 records per day (*unverified for CCAPI*).
- Free.

## 4. CERT Polska warning list (*Lista ostrzeżeń*)

**Files**
- Base URL: `https://hole.cert.pl/domains/v2/`. Available files:
  - `domains.txt` (active domains only)
  - `domains.json`, `domains.csv` (TSV), `domains.xml`
  - `domains_hosts.txt`, `domains_adblock.txt`, `domains_ublock.txt`, `domains_rpz.db`, `domains_mikrotik.rsc`
- JSON records: `RegisterPositionId`, `DomainAddress`, `InsertDate`, `DeleteDate`. A non-null `DeleteDate` means the domain was delisted.
- `actions_<year>.log` (NDJSON, 2020–2026) holds the full block/unblock history, which makes ideal labels.
- **[CHG]** The v1 URLs have been frozen since 2025-06-01 and now 301 to v2. v2 keeps only the last 6 months.

**Freshness**
- Updates 24/7, and CERT asks integrators to poll every 5 min.
- Measured today: 126,597 records in `domains.json` (22.5 MB), parsed and loaded in 12 s. A conditional GET returns 304 when nothing changed.

**Terms**
- Any use, including commercial.
- Attribution is optional but must not imply endorsement.
- The list has a statutory basis in the 2023 *ustawa o zwalczaniu nadużyć w komunikacji elektronicznej* ([cert.pl](https://www.cert.pl/en/warning-list/)).

**Reporting a domain**
- Use https://incydent.cert.pl/phishing (or SMS 8080).
- The Act center only drafts reports. A human submits them.

## 5. urlscan.io

**[CHG] Authentication**
- Since 2026-05-04, `/api/v1/result/{uuid}/`, `/dom/{uuid}/` and `/responses/{hash}/` need an `API-Key` ([blog](https://urlscan.io/blog/2026/03/18/api-auth-required/)).
- Search does not.

**Search quotas**
- Anonymous: 30 req/min per IP, and **[CHG]** history is limited to 30 days (`search_date_limit_days: 30`).
- Free account, per day: 50 private scans, 1,000 unlisted, 5,000 public, 1,000 searches, 10,000 result fetches ([pricing](https://urlscan.io/pricing/)). Check them with `GET /api/v1/quotas`.

**Useful pivots** (Elasticsearch syntax, [search docs](https://urlscan.io/docs/search/))
- `page.domain:`, `page.apexDomain:`, `page.ip:`, `page.asn:`, `hash:`, `page.title:`, `page.tlsIssuer:`
- `page.domainAgeDays:`, `date:>now-7d`
- Leading wildcards and regex need a login. `dom.*`, `brand.*` and `content.*` need Pro.

**Terms and paid tiers**
- Commercial use needs written permission ([terms](https://urlscan.io/terms/)).
- The feeds start at Pro ($1,250/month).

## 6. crt.sh and alternatives

**crt.sh**
- JSON: `https://crt.sh/?q=%25.<domain>&output=json`. A probe took 18 s.
- Postgres: `psql -h crt.sh -p 5432 -U guest certwatch`.
- Limits: 5 req/min per IP (HTTPS) and 5 connections per IP (Postgres). 502s are frequent.
- **[CHG]** Sectigo announced a rebuild on 2026-05-28, and replicas "freeze almost daily". Full-text search is being replaced, which will break 5432 queries ([group](https://groups.google.com/g/crtsh/c/PsNhy2WVXhg)).
- In our run, 14 domains returned 257 certificates in 6.5 min with a 4/min client limit.

**Cert Spotter (SSLMate)** (fallback, implemented)
- `GET https://api.certspotter.com/v1/issuances?domain=X&include_subdomains=true&expand=dns_names&expand=issuer`
- Keyless use allows 100 single-hostname queries/hour and is for personal or evaluation use only ([pricing](https://sslmate.com/ct_search_api/)).

**Censys**
- Free tier, quota not stated (*unverified*).

## 7. Live CT stream

**CaliDog certstream**
- The public server is effectively dead: today the WebSocket handshake succeeded but no data arrived in 10 s, and the repos are archived.

**certstream-server-go (self-hosted)**
- Docker image `0rickyy0/certstream-server-go`, endpoints `/full-stream` and `/domains-only`; clients must ping ≤ 60 s.
- Handles about 250–300 certs/s.
- **[CHG]** v1.9.0 adds static-CT (tiled) log support via `additional_tiled_logs`.

**[CHG] Let's Encrypt logs**
- LE's RFC 6962 logs went read-only on 2025-11-30 and shut down on 2026-02-28.
- LE now issues about 10 M certs/day and logs them only to **Static CT** (tiled) logs.

**What a 2026 consumer must handle** ([C2SP static-ct-api](https://github.com/C2SP/C2SP/blob/main/static-ct-api.md))
- Signed checkpoints.
- `tile/data/<N>` with gzip, partial tiles `.p/<W>`, and `TileLeaf` parsing.
- `/issuer/<sha256>`.
- RFC 6962 `get-entries` for logs that have not migrated.

## 8. RDAP

**Bootstrap**
- https://data.iana.org/rdap/dns.json

| TLD | RDAP base |
|---|---|
| `.click` | `rdap.registry.click/rdap/` |
| `.live`, `.pro`, `.info` | `rdap.identitydigital.services/rdap/` |
| `.top` | `rdap.zdnsgtld.com/top/` |
| `.ink` | `rdap.nic.ink/` |
| `.com` | `rdap.verisign.com/com/v1/` |
| `.sbs`, `.xyz`, `.icu`, `.cfd` | `rdap.centralnic.com/<tld>/` |
| `.org` | `rdap.publicinterestregistry.org/rdap/` |
| `.shop` | `rdap.gmoregistry.net/rdap/` |
| `.online`, `.site` | `rdap.radix.host/rdap/` |
| `.pl` | `rdap.dns.pl/` |

**rdap.org**
- The redirector is limited to 10 req per 10 s, so use the bootstrap file directly.
- Registry limits are unpublished: honour 429 and `Retry-After`.

**[CHG] WHOIS sunset**
- Since 2025-01-28 gTLDs no longer have to run WHOIS (except .com/.name/.post), and RDAP is mandatory ([ICANN](https://www.icann.org/rdap)).
- Registrant data is redacted, but the registrar, event dates, nameservers and status are not, and those are the pivots we use.
- Measured: 14/14 sample domains resolved via the bootstrap.

## 9. DNS and passive DNS

**Public DoH resolvers**
- Cloudflare DoH JSON: `cloudflare-dns.com/dns-query?name=&type=` with `accept: application/dns-json` (no stated limits).
- Google DoH JSON: `dns.google/resolve` (1,500 QPS per IP, no SLA).

**Passive DNS**
- mnemonic: `https://api.mnemonic.no/pdns/v3/<q>`. No auth, TLP:WHITE data, 10 req/min and 1,000/day ([docs](https://docs.mnemonic.no/api/services/pdns/01-public_api.html)).
- CIRCL: trusted partners only.
- Validin Community: account needed, 10 queries/day.
- SecurityTrails: free quota unpublished.

**IP → ASN**
- Team Cymru DNS: `<rev-ip>.origin.asn.cymru.com TXT`. No key; used in our prototype.

## 10. IPinfo Lite

- Endpoint: `https://api.ipinfo.io/lite/{ip}?token=…`. Returns country, continent, ASN, AS name and AS domain.
- Free and **unlimited**, but a token is required.
- Also offered as daily MMDB/CSV/Parquet downloads.
- Licence: **CC BY-SA 4.0**, attribution required ([ipinfo.io/lite](https://ipinfo.io/lite)).

## 11. Shodan InternetDB

- Endpoint: `https://internetdb.shodan.io/{ip}`. Returns `ports`, `cpes`, `hostnames`, `tags`, `vulns`.
- No key; limits unstated; updated weekly.
- **Non-commercial** use only; making money from it needs an enterprise licence.

## 12. Wayback Machine

**CDX API**
- `https://web.archive.org/cdx/search/cdx?url=X&matchType=domain&output=json&fl=timestamp,original,statuscode,digest&collapse=digest&showResumeKey=true`
- Maximum 150k rows per query.
- **[CHG]** Since 2026-09-15 there is anti-automation 429 blocking ([blog](https://blog.archive.org/2026/09/15/an-update-on-wayback-machine-access/)).

**Save Page Now 2**

| | Authenticated | Anonymous |
|---|---|---|
| Captures per minute | 7 | 3 |
| Captures per day | 30,000 | 200 |
| Data per day | 5 GB | 2 GB |
| Same URL per day | 5 | 5 |

## 13. OpenPhish

- **[CHG]** Now on GitHub raw (see top).
- Updated every 12 h.
- **Non-commercial only, no redistribution** ([terms](https://openphish.com/terms.html)).

## 14. Others (not planned)

- **PhishTank**: registration is closed, so no new API keys.
- **URLhaus / abuse.ch**:
  - **[CHG]** An Auth-Key has been mandatory since 2025-06-30.
  - **[CHG]** The ToS were updated on 2026-10-21: free use is not-for-profit only, and **using the data for AI training needs consent**.
- **Google Safe Browsing**: non-commercial.
- **Web Risk**: 100k lookups/month free, then $0.50 per 1,000.
- **VirusTotal public API**: 4 req/min, 500/day, and must not be used in commercial products.
