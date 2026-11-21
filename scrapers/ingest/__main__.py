"""Ingest CLI: auto-detects the layout of each path and loads it through the single Loader.

    python -m scrapers.ingest data/raw/sample_v1                       # sample_v1 folders (p1..p15)
    python -m scrapers.ingest path/to/archive_x_2026… --source redpill_capture   # one bundle dir/zip
    python -m scrapers.ingest data/raw/dane --source dane --dry-run     # inspect a new dataset
"""
from __future__ import annotations

import argparse
import collections
import sys
import time
from pathlib import Path

from ..store import artifacts
from ..store.db import Loader, connect
from .bundle import bundle_incident, is_bundle
from .sample_dir import discover, load_incident


def _is_incident_folder(p: Path) -> bool:
    return p.is_dir() and any(f.suffix.lower() in (".har", ".html", ".htm", ".png") for f in p.iterdir() if f.is_file())


def iter_drafts(path: Path, source: str, ref_prefix: str):
    if is_bundle(path):
        yield path, lambda p=path: bundle_incident(p, source)
        return
    if _is_incident_folder(path):  # e.g. data/raw/sample_v1/p1 (its inner bundle belongs to it)
        yield path, lambda: load_incident(path, source, ref_prefix)
        return
    # a folder of bundles?
    bundles = [c for c in sorted(path.iterdir()) if is_bundle(c)] if path.is_dir() else []
    dirs = {b.name for b in bundles if b.is_dir()}
    bundles = [b for b in bundles if b.is_dir() or b.stem not in dirs]  # dir + same-name zip = one bundle
    folders = discover(path) if path.is_dir() else []
    if folders:
        for d in folders:
            yield d, lambda d=d: load_incident(d, source, ref_prefix)
    elif bundles:
        for b in bundles:
            yield b, lambda b=b: bundle_incident(b, source)
    elif path.is_dir():  # a single incident folder
        yield path, lambda: load_incident(path, source, ref_prefix)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    ap.add_argument("--source", default="sample_v1")
    ap.add_argument("--ref-prefix", default=None)
    ap.add_argument("--dry-run", action="store_true", help="parse only, print what would be loaded")
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    ref_prefix = args.ref_prefix or args.source

    if args.dry_run:
        for p, make in iter_drafts(args.path, args.source, ref_prefix):
            inc = make()
            c = collections.Counter(o.type for o in {(o.type, o.value): o for o in inc.observables}.values())
            print(f"{p.name}: {inc.kind} captures={len(inc.captures)} obs={dict(c)}")
        return 0

    store = artifacts.from_env()
    with connect(args.db) as conn:
        loader = Loader(conn, store)
        run_id = loader.start_run(args.source, trigger="seed" if args.source == "sample_v1" else "manual",
                                  params={"path": str(args.path)})
        conn.commit()
        t0 = time.time()
        n = 0
        errors = []
        for p, make in iter_drafts(args.path, args.source, ref_prefix):
            t = time.time()
            try:
                inc = make()
                iid = loader.ingest(inc, run_id)
                conn.commit()
                n += 1
                print(f"  {inc.source_ref:<24} → incident {iid:<4} {inc.kind:<12} "
                      f"{len(inc.captures)} capture(s)  {time.time() - t:4.1f}s", flush=True)
            except Exception as e:  # keep going: one broken folder must not stop a batch
                conn.rollback()
                errors.append(f"{p.name}: {e!r}")
                print(f"  ERROR {p.name}: {e!r}", file=sys.stderr, flush=True)
        updated = conn.execute("SELECT refresh_observable_stats()").fetchone()[0]
        loader.finish_run(run_id, "ok" if not errors else "partial", {**loader.stats, "errors": errors, "observables_refreshed": updated})
        conn.commit()
        print(f"loaded {n} incident(s) in {time.time() - t0:.1f}s; stats={loader.stats}; df refreshed for {updated} observables")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
