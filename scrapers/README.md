# scrapers/: ingest, enrichment, capture, hunters

Design: [docs/db/DB_AND_SCRAPING.md](../docs/db/DB_AND_SCRAPING.md). Source facts: [docs/db/SOURCES_FACTSHEET.md](../docs/db/SOURCES_FACTSHEET.md).

When the app skeleton lands, these map onto PLAN §3's `core/ingest`, `core/capture` and `core/enrich`. Until then the package is importable as `scrapers.*`.

```bash
python -m venv .venv && .venv/Scripts/pip install -r scrapers/requirements.txt
.venv/Scripts/python -m playwright install chromium
```

| Command | Does |
|---|---|
| `python -m scrapers.ingest <path> [--source sample_v1] [--dry-run]` | Auto-detects a bundle, an incident folder or a folder of either, and loads it through the single `Loader` |
| `python -m scrapers.enrich.certpl [--force]` | CERT PL v2 list → `certpl_domains` (+ history), conditional GET |
| `python -m scrapers.enrich [--providers dns,rdap,crtsh] [--all] [--pivot]` | Enriches every landing domain and propagates registrar, NS set, registration batch, certs and IP/ASN to incidents |
| `python -m scrapers.enrich.{dns,rdap,crtsh} <domain>` | A single lookup |
| `python -m scrapers.capture <url> [--profile fb_inapp_android_pl] [--profile plain_headless] [--ingest] [--proxy …]` | Headless capture → organizer-compatible bundle in `data/captures/` |
| `python -m scrapers.hunter.meta_adlib --terms "…" --dry-run` / `--job hunter:meta:lures_pl --ingest` / `--fixture …` | Meta Ad Library hunter (needs `META_ACCESS_TOKEN` for live runs) |
| `python -m scrapers.hunter.google_atc --advertisers --days 7 --ingest` / `--removed --days 30 --ingest` | Google Ads Transparency (BigQuery sandbox): advertiser registry / removal labels |
| `python -m scrapers.enrich.urlscan pivots --budget 40` | Search-only pivots from campaign values → `oracle_candidates` |
| `python -m scrapers.enrich.urlscan results --limit 100` | Each candidate's latest public urlscan scan → full incident (no visit by us) |
| `python -m scrapers.hunter.meta_snapshot --limit 30 --targets <file>` | Render Meta ad snapshots → landing URLs (token kept in memory only) |
| `python -m scrapers.expand [--steps …] [--capture docker\|local]` | The whole expansion loop (pivots → scan results → snapshots → sandboxed captures → enrich → stats); job `expand_daily` |

**Environment variables**
- `DATABASE_URL`: default `postgresql://redpill:redpill_dev@127.0.0.1:55432/redpill`.
- `ARTIFACT_STORE`: `file://…` (default `data/artifacts`) or `s3://bucket`, with `S3_ENDPOINT`, `S3_ACCESS_KEY` and `S3_SECRET_KEY`.
- `REDPILL_OFFLINE=1`: enrichment serves from cache only.
- `META_ACCESS_TOKEN`: Meta Ad Library API token.

**Sandboxed capture** (recommended for live scam domains):
```bash
docker build -t redpill-capture -f scrapers/capture/Dockerfile .
docker run --rm --read-only --tmpfs /tmp --tmpfs /home/pwuser --cap-drop ALL --security-opt no-new-privileges   --memory 2g --pids-limit 512 --shm-size 512m -v "$PWD/data/captures/run1:/out"   redpill-capture --file /out/targets.txt --out /out --profile fb_inapp_android_pl --profile plain_headless --concurrency 4 --no-db
python -m scrapers.capture --ingest-dir data/captures/run1     # on the host: attach + cloaking pairs
```
During development, add `-v "$PWD/scrapers:/app/scrapers:ro"` to run the working tree instead of the code baked into the image.

**Safety**
- Captures are headless only: no clicks, no form submission, downloads blocked, and challenges recorded as blocked, never solved.
- Run captures of live scam domains from the sandbox container (`scrapers/capture/Dockerfile`) behind an egress proxy, never from an analyst's own machine or IP.
