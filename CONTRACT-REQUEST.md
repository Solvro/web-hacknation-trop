# Contract notes / requests from WS6 (White Rabbit + Act)

No blocking schema change needed; everything fits `schema.py` as is. Notes for the lead:

1. `graph.node_added` is an **upsert**: when a node's status/level changes (e.g. `in_progress` → `new`, analyst
   "Pomiń" → `skipped`, promote → `in_campaign`) the same node id is re-sent. The web should replace by id.
2. Node ids: domains are `d-<fqdn>`; trace/query nodes `n-…` (stable sha1-based suffixes, so replays are deterministic).
   `InvestigationNode.status` also uses `skipped` (already allowed by the schema).
3. `investigation.decision.options` is `["Dołącz", "Pomiń"]`; the answer comes back through
   `POST /investigations/{id}/steer` with `{node_id, choice}` (WS2's `SteerRequest` already has both fields).
4. New agent tool `oracle_lookup` (reads `oracle_candidates`), branch `db`, bot `notariusz`.
5. `ActPackage.contents` carries an extra key `certpl_new` (domains not yet on the CERT PL list). `ActPackage.formats`
   is `["pdf","json","stix","misp","csv"]`; `download()` also accepts `certpl` (the e-mail draft as text).
6. Suggest adding `"certpl"` to the `format` pattern of `GET /act/packages/{id}/download` (WS2 route).
