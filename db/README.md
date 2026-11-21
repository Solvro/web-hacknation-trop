# db/: Postgres 16 + pgvector + pg_trgm

Design and rationale: [docs/db/DB_AND_SCRAPING.md](../docs/db/DB_AND_SCRAPING.md).

```bash
docker compose -f db/docker-compose.yml up -d     # 127.0.0.1:55432, user/db redpill, password redpill_dev (dev only)
python db/migrate.py --status                     # migrations also auto-run on the first boot of an empty volume
python db/seed_sample.py                          # migrations + data/raw/sample_v1 + experiments labels + summary
```

| File | Contents |
|---|---|
| `migrations/0001_extensions.sql` | `vector`, `pg_trgm`, `btree_gin`, `pgcrypto`, `schema_migrations`, `hamming64()` |
| `0002_provenance.sql` | `sources`, `jobs`, `job_runs`, `artifacts` (content-addressed, pHash bands) |
| `0003_core.sql` | `advertisers`, `ads`, `ad_observations`, `incidents`, `captures`, `capture_hops`, `capture_requests` (partitioned), `artifact_refs` |
| `0004_observables.sql` | `observable_types`, `observables`, `incident_observables` (inverted index), `obs_domains/ips/certs/persons`, `observable_relations` |
| `0005_vectors_media.sql` | `model_versions`, `embedding_spaces`, `embeddings` (halfvec), `media_texts`, `faces`, `voice_segments` |
| `0006_analysis.sql` | `evidence_types`, `clustering_runs`, `pair_links`, `evidence`, `operator_families`, `campaigns`, `variants`, `campaign_memberships` (SCD2), `campaign_events`, `label_sets`, `labels`, `pair_labels`, `feedback` |
| `0007_operations.sql` | `enrichment_providers`, `enrichment_cache`, `certpl_*`, `capture_tasks`, `domain_budgets`, `oracle_candidates` (partitioned), `act_packages`, `reports`, `audit_log` (append-only) |
| `0008_functions.sql` | `corpus_stats`, `idf_of()`, `refresh_observable_stats()`, `blocking_candidates()`, `infra_pivot()`, `incident_neighborhood()`, `set_membership()`, `ensure_month_partition()`, views `v_current_membership`, `v_campaign_dna`, `v_incident_coverage`, `v_graph_edges` |
| `0009_reference_data.sql` | Source catalogue, observable and evidence types with priors, embedding spaces + HNSW indexes, provider TTLs and limits, default jobs, `rules v0`, label sets |

Every migration records itself in `schema_migrations`, so the same files work both through `docker-entrypoint-initdb.d` and through `migrate.py`. Add new changes as `0010_*.sql` and never edit an applied migration on a shared database.
