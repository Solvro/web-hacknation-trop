"""Domain / incident enrichment in the shape experiments/run_infra.py + merge_enrich.py produced:

    infra.domains[].enrich = {"ns": [...], "registrar", "created", "asn": [...], "certs": [{"issuer", "not_before"}],
                              "certpl": {...}, "ips": [...]}

which is exactly what the engine's `ns_pair`, `registrar_batch` and `cert_batch` evidence read. Everything is cached on
the FS (see cache.py) and replays in offline mode.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from . import certpl as certpl_mod
from . import crtsh, dns, rdap
from .util import etld1

ALL = ("dns", "rdap", "crtsh", "certpl")


def enrich_domain(domain: str, providers: Iterable[str] = ALL, *, ips: bool = True) -> dict[str, Any]:
    d = etld1(domain)
    prov = set(providers)
    out: dict[str, Any] = {"domain": d}
    rd: dict = {}
    if "rdap" in prov:
        rd = rdap.lookup(d)
        out["registrar"] = rd.get("registrar")
        out["created"] = rd.get("created")
        out["expires"] = rd.get("expires")
        out["registrar_iana_id"] = rd.get("registrar_iana_id")
    if "dns" in prov:
        rec = dns.records(d)
        ns = [] if set(rec.get("NS", [])) & dns.CF_DEAD else [x.rstrip(".").lower() for x in rec.get("NS", [])]
        out["ns"] = ns or ([] if dns_dead(rec) else [x for x in rd.get("ns", [])])
        a = [x for x in rec.get("A", []) if not x.startswith("ERR")]
        out["ips"] = a
        if ips:
            asns = {dns.asn_of(ip).get("asn") for ip in a}
            out["asn"] = sorted(x for x in asns if x)
        out["nxdomain"] = bool(rec.get("nxdomain"))
    elif rd.get("ns"):
        out["ns"] = rd["ns"]
    if "crtsh" in prov:
        out["certs"] = [{"issuer": c["issuer"], "not_before": c["not_before"]} for c in crtsh.certs(d) if c.get("not_before")]
    if "certpl" in prov:
        out["certpl"] = certpl_mod.check(d)
    return out


def dns_dead(rec: dict) -> bool:
    return bool(set(rec.get("NS", [])) & dns.CF_DEAD)


def enrich_incident(inc: dict, providers: Iterable[str] = ALL, max_domains: int = 3, only_landing: bool = True) -> dict:
    """Mutates + returns one incident dict (infra.domains[].enrich, infra.on_certpl_list)."""
    doms = (inc.get("infra") or {}).get("domains") or []
    land = (inc.get("landing") or {}).get("host")
    todo = [x for x in doms if x.get("fqdn") == land] or doms[:1] if only_landing else doms
    seen: dict[str, dict] = {}
    for x in todo[:max_domains]:
        key = etld1(x["fqdn"])
        if key not in seen:
            seen[key] = enrich_domain(key, providers)
        x["enrich"] = {k: v for k, v in seen[key].items() if k != "domain"}
    for x in doms:                                   # share results with sibling hosts of the same eTLD+1
        e = seen.get(etld1(x["fqdn"]))
        if e and not x.get("enrich"):
            x["enrich"] = {k: v for k, v in e.items() if k != "domain"}
    flags = [(x.get("enrich") or {}).get("certpl", {}).get("listed") for x in doms]
    if any(f is True for f in flags):
        inc.setdefault("infra", {})["on_certpl_list"] = True
    elif flags and all(f is False for f in flags):
        inc.setdefault("infra", {})["on_certpl_list"] = False
    return inc


def enrich_incidents_file(path: str | Path, out: str | Path | None = None, providers: Iterable[str] = ALL,
                          only_landing: bool = True, progress=None) -> dict:
    path = Path(path)
    incs = json.loads(path.read_text(encoding="utf-8"))
    n = 0
    for i, inc in enumerate(incs):
        enrich_incident(inc, providers, only_landing=only_landing)
        n += sum(1 for d in (inc.get("infra") or {}).get("domains", []) if d.get("enrich"))
        if progress:
            progress(i + 1, len(incs))
    dest = Path(out) if out else path
    dest.write_text(json.dumps(incs, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"incidents": len(incs), "enriched_domains": n, "out": str(dest)}
