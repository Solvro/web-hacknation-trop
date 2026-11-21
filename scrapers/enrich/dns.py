"""Active DNS resolution + IP→ASN (Team Cymru DNS, no key) → passive-DNS style relations.

    python -m scrapers.enrich.dns example.com

Writes: resolves_to (fqdn→ip, first/last seen kept on the relation = our own passive DNS), uses_ns,
uses_mx, cname_to, in_asn (ip→asn); obs_ips.asn/as_org/country/cdn; CDN edges flagged noise.
Only resolvers are contacted — never the scam host itself.
"""
from __future__ import annotations

import argparse
import sys

import dns.exception
import dns.resolver
import dns.reversename

from ..ingest.extract import cdn_of
from ..ingest.model import RelationDraft
from ..store import artifacts
from ..store.db import Loader, connect
from .http import CachedClient

# Shared *edge* networks only (weight 0). Cloud compute ASNs (AWS 16509/14618, GCP 396982, Azure 8075) are NOT here:
# kit backends and CAPI gateways live there, so those IPs are real origin evidence. CloudFront edges are caught by range.
CDN_ASNS = {13335: "cloudflare", 209242: "cloudflare", 54113: "fastly", 20940: "akamai", 16625: "akamai",
            32934: "meta", 15169: "google"}
HOSTING_ASNS = {14061: "digitalocean", 24940: "hetzner", 16276: "ovh", 63949: "linode", 20473: "vultr",
                51167: "contabo", 9009: "m247", 47583: "hostinger", 212238: "datacamp", 200651: "flokinet"}


def _resolver() -> dns.resolver.Resolver:
    r = dns.resolver.Resolver()
    r.lifetime = 8.0
    r.timeout = 4.0
    return r


def resolve(name: str, rtype: str) -> tuple[str, list[str]]:
    try:
        ans = _resolver().resolve(name, rtype)
        return "ok", sorted({a.to_text().rstrip(".").lower() for a in ans})
    except dns.resolver.NXDOMAIN:
        return "nxdomain", []
    except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return "noanswer", []
    except dns.exception.Timeout:
        return "timeout", []


def lookup_cached(client: CachedClient, name: str) -> dict:
    hit = client.cached(f"all:{name}")
    if hit and hit.status in ("ok", "not_found"):
        return hit.data or {}
    out: dict = {"name": name}
    for rtype in ("A", "AAAA", "CNAME", "NS", "MX", "TXT"):
        st, vals = resolve(name, rtype)
        out[rtype] = vals
        if st == "nxdomain":
            out["nxdomain"] = True
            break
    from .http import Result
    client.store(f"all:{name}", Result("not_found" if out.get("nxdomain") else "ok", out))
    return out


def asn_of(client: CachedClient, ip: str) -> dict:
    """Team Cymru: <rev-ip>.origin.asn.cymru.com TXT → 'ASN | prefix | CC | rir | date'."""
    hit = client.cached(f"asn:{ip}")
    if hit and hit.status == "ok":
        return hit.data
    from .http import Result
    try:
        rev = dns.reversename.from_address(ip).to_text().replace(".in-addr.arpa.", "").replace(".ip6.arpa.", "")
        zone = "origin6.asn.cymru.com" if ":" in ip else "origin.asn.cymru.com"
        st, txt = resolve(f"{rev}.{zone}", "TXT")
        if st != "ok" or not txt:
            client.store(f"asn:{ip}", Result("not_found", {}))
            return {}
        parts = [p.strip().strip('"') for p in txt[0].strip('"').split("|")]
        asn = int(parts[0].split()[0])
        st2, txt2 = resolve(f"AS{asn}.asn.cymru.com", "TXT")
        name = txt2[0].strip('"').split("|")[-1].strip() if st2 == "ok" and txt2 else None
        data = {"asn": asn, "prefix": parts[1], "country": parts[2], "as_org": name}
        client.store(f"asn:{ip}", Result("ok", data))
        return data
    except (ValueError, IndexError, dns.exception.DNSException):
        return {}


def enrich_name(loader: Loader, name: str) -> dict:
    client = CachedClient(loader.conn, "dns")
    rec = lookup_cached(client, name)
    if rec.get("nxdomain"):
        loader.conn.execute("UPDATE obs_domains SET enriched_at = now() WHERE fqdn = %s", (name,))
        loader.conn.commit()
        return {"name": name, "nxdomain": True}
    for ip in rec.get("A", []) + rec.get("AAAA", []):
        cdn = cdn_of(ip)
        asn = asn_of(client, ip)
        cdn = cdn or CDN_ASNS.get(asn.get("asn"))
        loader.observable_id("ip", ip, noise_reason=f"cdn:{cdn}" if cdn else None, attrs={"cdn": cdn})
        loader.relate(RelationDraft(("fqdn", name), "resolves_to", ("ip", ip), "dns"))
        loader.propagate(name, "ip", ip, "enrich.dns", "dns@1", noise_reason=f"cdn:{cdn}" if cdn else None)
        if asn and not cdn:
            loader.propagate(name, "asn", f"AS{asn['asn']}", "enrich.dns", "cymru@1", display=asn.get("as_org"))
        if asn:
            loader.conn.execute(
                "UPDATE obs_ips SET asn = %s, as_org = %s, country = %s, cdn = coalesce(cdn, %s), is_cdn = %s, "
                "hosting = %s, enriched_at = now() WHERE ip = %s",
                (asn["asn"], asn.get("as_org"), asn.get("country"), cdn, cdn is not None,
                 HOSTING_ASNS.get(asn["asn"]), ip))
            loader.relate(RelationDraft(("ip", ip), "in_asn", ("asn", f"AS{asn['asn']}"), "cymru",
                                        {"prefix": asn.get("prefix")}))
    for c in rec.get("CNAME", []):
        loader.relate(RelationDraft(("fqdn", name), "cname_to", ("fqdn", c), "dns"))
    for ns in rec.get("NS", []):
        loader.relate(RelationDraft(("fqdn", name), "uses_ns", ("nameserver", ns), "dns"))
    for mx in rec.get("MX", []):
        host = mx.split()[-1]
        loader.relate(RelationDraft(("fqdn", name), "uses_mx", ("fqdn", host), "dns"))
    loader.conn.execute("UPDATE obs_domains SET enriched_at = now() WHERE fqdn = %s", (name,))
    loader.conn.commit()
    return {k: v for k, v in rec.items() if v}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    with connect(args.db) as conn:
        print(enrich_name(Loader(conn, artifacts.from_env(), sensitivity="public"), args.name.lower()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
