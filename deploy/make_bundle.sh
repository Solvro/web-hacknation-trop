#!/usr/bin/env bash
# Build deploy/bundle/ = everything the REAL product reads at runtime, copied from data/ (organizer-derived: private repo only).
# The image bakes it at /bundle; deploy/entrypoint.sh seeds the /data volume from it (never overwriting newer files) and
# deploy/seed.sh restores bundle/seed/trop_seed.dump into an empty Postgres.
#   deploy/make_bundle.sh [DATA_DIR]      (default: <repo>/data)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-$ROOT/data}"
OUT="$ROOT/deploy/bundle"
[ -d "$SRC" ] || { echo "no data dir: $SRC" >&2; exit 1; }

copy() {  # copy <relative path> [find-expr...]  -- keeps the tree layout under $OUT
  local rel="$1"; shift
  [ -e "$SRC/$rel" ] || { echo "skip (missing): $rel"; return 0; }
  mkdir -p "$OUT/$(dirname "$rel")"
  cp -r "$SRC/$rel" "$OUT/$rel"
}

rm -rf "$OUT"
mkdir -p "$OUT"
copy seed/trop_seed.dump                  # Postgres snapshot (engine corpus, campaigns, operations, ...)
copy corpus                               # JSON corpus (fallback when the DB is empty)
copy models                               # face/voice index + ONNX (loaded at runtime, not baked into the python layer)
copy oracle                               # trained domain-DNA model + predictions
copy cache/models                         # model-output cache (offline replay of VLM/LLM tasks)
copy cache/enrich                         # DNS/RDAP/crt.sh cache
for f in lab_eval lab_eval_dane lab_eval_ablation; do copy "cache/$f.json"; done   # `trop eval` numbers for /lab (sample, DANE open-set, layer ablation)
copy cache/screenshot_index.json
for d in sample_v1 dane joint; do         # precomputed extractor outputs the ingest layers fall back to (offline analysis)
  [ -d "$SRC/experiments/$d" ] || continue
  mkdir -p "$OUT/experiments/$d"
  find "$SRC/experiments/$d" -maxdepth 2 -type f \( -name '*.json' -o -name '*.jsonl' -o -name '*.npy' -o -name '*.npz' \) -size -5M \
    -exec sh -c 'for f; do rel="${f#'"$SRC"'/}"; mkdir -p "'"$OUT"'/$(dirname "$rel")"; cp "$f" "'"$OUT"'/$rel"; done' _ {} +
done
# real runs only (no fictional demo data): White Rabbit runs, the KMP-001 Act package, real SSE recordings
copy investigations
mkdir -p "$OUT/act"; [ -d "$SRC/act/ACT-105" ] && cp -r "$SRC/act/ACT-105" "$OUT/act/ACT-105" || true
mkdir -p "$OUT/replay"
for f in live-analyze.jsonl investigation_live.jsonl; do [ -f "$SRC/replay/$f" ] && cp "$SRC/replay/$f" "$OUT/replay/$f" || echo "skip (missing): replay/$f"; done

du -sh "$OUT"; find "$OUT" -type f -size +90M -print | sed 's/^/WARNING >90MB: /'
