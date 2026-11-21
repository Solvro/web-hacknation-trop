"""Enrich every landing domain in the DB (DNS + ASN, RDAP, crt.sh), cached and rate-limited.

    python -m scrapers.enrich                      # all etld1/fqdn observables not enriched in the last day
    python -m scrapers.enrich --providers dns,rdap --limit 20
    REDPILL_OFFLINE=1 python -m scrapers.enrich    # replay from enrichment_cache only

Talks to resolvers, RDAP registries and crt.sh only — never to the scam hosts.
"""
from __future__ import annotations

import argparse
import sys
import time

from ..store import artifacts
from ..store.db import Loader, connect
from . import crtsh, dns, rdap


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--providers", default="dns,rdap,crtsh")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--all", action="store_true", help="ignore enriched_at freshness")
    ap.add_argument("--pivot", action="store_true", help="also enrich domains discovered via relations (SANs, redirects)")
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    providers = set(args.providers.split(","))
    with connect(args.db) as conn:
        loader = Loader(conn, artifacts.from_env(), sensitivity="public")
        run_id = loader.start_run("dns", trigger="manual", params={"providers": sorted(providers)}, job_key="enrich_refresh")
        conn.commit()
        # default scope: landing-chain domains of incidents; --pivot also enriches domains discovered through
        # relations (cert SANs, redirects, CNAMEs) — the agent's pivot step, bounded by --limit
        rows = conn.execute(
            """SELECT DISTINCT d.fqdn, d.etld1 FROM obs_domains d
               JOIN observables o ON o.id = d.observable_id
               WHERE o.type IN ('fqdn','etld1') AND NOT o.noise
                 AND (%s OR EXISTS (SELECT 1 FROM incident_observables io
                                    WHERE io.observable_id = o.id AND io.field LIKE 'landing.%%'))
                 AND (%s OR d.enriched_at IS NULL OR d.enriched_at < now() - interval '1 day')
               ORDER BY d.etld1, d.fqdn LIMIT %s""", (args.pivot, args.all, args.limit)).fetchall()
        fqdns = sorted({r[0] for r in rows})
        etld1s = sorted({r[1] for r in rows})
        stats = {"fqdn": len(fqdns), "etld1": len(etld1s), "nxdomain": 0, "rdap_ok": 0, "certs": 0}
        t0 = time.time()
        if "dns" in providers:
            for n in fqdns:
                r = dns.enrich_name(loader, n)
                stats["nxdomain"] += bool(r.get("nxdomain"))
                print(f"  dns   {n:<40} {('NXDOMAIN' if r.get('nxdomain') else ','.join(r.get('A', [])[:3]))}", flush=True)
        if "rdap" in providers:
            for d in etld1s:
                r = rdap.enrich_domain(loader, d)
                stats["rdap_ok"] += r.get("status") == "ok"
                print(f"  rdap  {d:<40} {r.get('registrar')} created={r.get('created')} ns={r.get('nameservers')} {r.get('error') or ''}", flush=True)
        if "crtsh" in providers:
            for d in etld1s:
                r = crtsh.enrich_domain(loader, d)
                stats["certs"] += r["certs"]
                print(f"  crtsh {d:<40} certs={r['certs']} first={r['first_cert']} issuers={r['issuers']}", flush=True)
        conn.execute("SELECT refresh_observable_stats()")
        stats["seconds"] = round(time.time() - t0, 1)
        loader.finish_run(run_id, "ok", stats)
        conn.commit()
        print(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
