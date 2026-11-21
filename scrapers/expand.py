"""Corpus expansion loop — one command (and the `expand_daily` job) that turns candidates into full incidents.

    python -m scrapers.expand                       # all steps, budgets from jobs.budget of 'expand_daily'
    python -m scrapers.expand --steps urlscan_results,meta_snapshots --capture local

Steps (each recorded as its own job_runs row):
  urlscan_pivots   campaign assets / gateways / origin IPs → new domains → oracle_candidates    (search quota)
  urlscan_results  each new candidate's latest public scan → full incident, no visit by us      (result quota)
  meta_snapshots   Meta ads without a known landing → render snapshot → ads.link_url + targets
  sandbox_capture  capture those landings (victim + bot profile) in the hardened container
                   (or locally with --capture local), attach to the ad incidents, mark cloaking pairs
  enrich           DNS/ASN + RDAP + crt.sh (+ IPinfo) for every new landing domain
  relink           refresh df/idf/noise statistics; flags new incidents for the linker
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .store import artifacts
from .store.db import Loader, connect

ROOT = Path(__file__).resolve().parents[1]
ALL_STEPS = ["urlscan_pivots", "urlscan_results", "meta_snapshots", "sandbox_capture", "enrich", "relink"]


def _py(*args: str) -> int:
    print(f"\n$ python {' '.join(args)}", flush=True)
    return subprocess.run([sys.executable, "-W", "ignore", *args], cwd=ROOT).returncode


def sandbox_capture(targets: Path, out: Path, mode: str) -> int:
    common = ["--file", f"/out/{targets.name}" if mode == "docker" else str(targets), "--out", "/out" if mode == "docker" else str(out),
              "--profile", "fb_inapp_android_pl", "--profile", "plain_headless", "--concurrency", "6", "--no-db", "--fast"]
    if mode == "docker":
        cmd = ["docker", "run", "--rm", "--read-only", "--tmpfs", "/tmp", "--tmpfs", "/home/pwuser", "--cap-drop", "ALL",
               "--security-opt", "no-new-privileges", "--memory", "3g", "--pids-limit", "1024", "--shm-size", "1g",
               "-v", f"{(ROOT / 'scrapers').as_posix()}:/app/scrapers:ro", "-v", f"{out.resolve().as_posix()}:/out",
               "redpill-capture", *common]
        print("\n$ " + " ".join(cmd[:12]) + " … redpill-capture …", flush=True)
        rc = subprocess.run(cmd, cwd=ROOT).returncode
    else:
        rc = _py("-m", "scrapers.capture", *common)
    if rc == 0:
        rc = _py("-m", "scrapers.capture", "--ingest-dir", str(out))
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", default=",".join(ALL_STEPS))
    ap.add_argument("--capture", choices=["docker", "local"], default="docker")
    args = ap.parse_args()
    steps = [s for s in args.steps.split(",") if s]
    with connect() as conn:
        row = conn.execute("SELECT budget FROM jobs WHERE key = 'expand_daily'").fetchone()
        budget = (row[0] if row else {}) or {}
        loader = Loader(conn, artifacts.from_env(), sensitivity="internal")
        run_id = loader.start_run("urlscan_scan", trigger="manual", params={"steps": steps, "budget": budget},
                                  job_key="expand_daily")
        conn.commit()
        before = conn.execute("SELECT count(*) FROM incidents").fetchone()[0]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    out = ROOT / "data" / "captures" / f"expand_{stamp}"
    targets = out / "targets.txt"
    rcs: dict[str, int] = {}
    if "urlscan_pivots" in steps:
        rcs["urlscan_pivots"] = _py("-m", "scrapers.enrich.urlscan", "pivots", "--budget", str(budget.get("urlscan_searches", 40)))
    if "urlscan_results" in steps:
        rcs["urlscan_results"] = _py("-m", "scrapers.enrich.urlscan", "results", "--limit", str(budget.get("urlscan_results", 100)))
    if "meta_snapshots" in steps:
        out.mkdir(parents=True, exist_ok=True)
        rcs["meta_snapshots"] = _py("-m", "scrapers.hunter.meta_snapshot", "--limit", str(budget.get("meta_snapshots", 30)),
                                    "--targets", str(targets))
    if "sandbox_capture" in steps and targets.is_file():
        rcs["sandbox_capture"] = sandbox_capture(targets, out, args.capture)
    if "enrich" in steps:
        rcs["enrich"] = _py("-m", "scrapers.enrich", "--providers", "dns,rdap,crtsh")
        _py("-m", "scrapers.enrich.ipinfo")
    with connect() as conn:
        if "relink" in steps:
            conn.execute("SELECT mark_platform_values(3)")      # multi-tenant kit values → platform-level
            conn.execute("SELECT refresh_observable_stats()")
        after = conn.execute("SELECT count(*) FROM incidents").fetchone()[0]
        loader = Loader(conn, artifacts.from_env())
        stats = {"incidents_before": before, "incidents_after": after, "step_exit_codes": rcs}
        loader.finish_run(run_id, "ok" if all(v == 0 for v in rcs.values()) else "partial", stats)
        conn.commit()
    print("\n" + json.dumps(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
