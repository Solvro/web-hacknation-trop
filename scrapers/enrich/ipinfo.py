"""IPinfo Lite: IP → ASN, AS name, AS domain, country (free, unlimited with token; CC BY-SA 4.0 — attribute IPinfo).

    python -m scrapers.enrich.ipinfo                 # every IP in obs_ips not enriched in 30 days
    python -m scrapers.enrich.ipinfo 1.2.3.4 …       # specific IPs
"""
from __future__ import annotations

import argparse
import os
import sys

from ..ingest.extract import cdn_of
from ..ingest.model import RelationDraft
from ..store import artifacts
from ..store.db import Loader, connect
from .dns import CDN_ASNS, HOSTING_ASNS
from .http import CachedClient


def lookup(conn, ip: str) -> dict:
    token = os.environ.get("IPINFO_TOKEN")
    if not token:
        return {"error": "IPINFO_TOKEN not set"}
    res = CachedClient(conn, "ipinfo").get_json(f"lite:{ip}", f"https://api.ipinfo.io/lite/{ip}", params={"token": token})
    return res.data if res.status == "ok" else {"error": res.error or res.status}


def enrich_ip(loader: Loader, ip: str) -> dict:
    d = lookup(loader.conn, ip)
    if d.get("error"):
        return {"ip": ip, **d}
    asn = int(str(d.get("asn", "")).upper().replace("AS", "") or 0) or None
    cdn = cdn_of(ip) or CDN_ASNS.get(asn)
    loader.observable_id("ip", ip, noise_reason=f"cdn:{cdn}" if cdn else None, attrs={"cdn": cdn})
    loader.conn.execute(
        """UPDATE obs_ips SET asn = %s, as_org = %s, country = %s, cdn = coalesce(cdn, %s), is_cdn = %s,
               hosting = coalesce(%s, hosting), enriched_at = now() WHERE ip = %s""",
        (asn, d.get("as_name"), d.get("country_code"), cdn, cdn is not None,
         HOSTING_ASNS.get(asn) or d.get("as_domain"), ip))
    if asn:
        loader.relate(RelationDraft(("ip", ip), "in_asn", ("asn", f"AS{asn}"), "ipinfo",
                                    {"name": d.get("as_name"), "as_domain": d.get("as_domain")}))
    loader.conn.commit()
    return {"ip": ip, "asn": asn, "as_name": d.get("as_name"), "as_domain": d.get("as_domain"),
            "country": d.get("country_code"), "cdn": cdn}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ips", nargs="*")
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    with connect(args.db) as conn:
        loader = Loader(conn, artifacts.from_env(), sensitivity="public")
        ips = args.ips or [r[0] for r in conn.execute(
            "SELECT host(ip) FROM obs_ips WHERE enriched_at IS NULL OR enriched_at < now() - interval '30 days' ORDER BY 1")]
        for ip in ips:
            r = enrich_ip(loader, ip)
            print(f"  {ip:<40} {r.get('asn')} {str(r.get('as_name'))[:40]:<40} {r.get('country')} cdn={r.get('cdn')} {r.get('error') or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
