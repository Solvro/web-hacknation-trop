"""RDAP domain lookup via the IANA bootstrap (no WHOIS port 43; gTLD WHOIS obligations ended 2025-01-28).

    python -m scrapers.enrich.rdap example.com

Fills obs_domains (registrar, IANA id, created/expires/updated, status, nameservers) and adds
registered_by / uses_ns relations + registrar / nameserver / registrant_email observables.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from ..ingest.model import RelationDraft
from ..store import artifacts
from ..store.db import Loader, connect
from ..util.urls import split_host
from .http import CachedClient

BOOTSTRAP = "https://data.iana.org/rdap/dns.json"


def _bootstrap(client: CachedClient) -> dict[str, str]:
    res = client.get_json("bootstrap:dns", BOOTSTRAP)
    table: dict[str, str] = {}
    if res.status == "ok":
        for tlds, urls in res.data.get("services", []):
            base = next((u for u in urls if u.startswith("https://")), urls[0])
            for t in tlds:
                table[t.lower()] = base if base.endswith("/") else base + "/"
    return table


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _vcard_fn(entity: dict) -> str | None:
    for item in (entity.get("vcardArray") or [None, []])[1]:
        if item and item[0] == "fn":
            return item[3]
    return None


def _vcard_email(entity: dict) -> str | None:
    for item in (entity.get("vcardArray") or [None, []])[1]:
        if item and item[0] == "email":
            return str(item[3]).lower()
    return None


def _norm_registrar(name: str | None) -> str | None:
    """'Dynadot, LLC' / 'Dynadot Inc' → 'dynadot'; 'NameCheap, Inc.' / 'Namecheap Inc.' → 'namecheap'."""
    import re
    if not name:
        return None
    n = re.sub(r"[,.]", " ", name.lower())
    n = re.sub(r"\b(inc|llc|ltd|limited|corp|co|gmbh|uab|operations|group|international|s a|sa)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip() or name.lower()


def lookup(conn, domain: str) -> dict | None:
    client = CachedClient(conn, "rdap")
    etld1, _, tld = split_host(domain)
    last = tld.split(".")[-1] if tld else ""
    base = _bootstrap(client).get(last)
    url = f"{base}domain/{etld1}" if base else f"https://rdap.org/domain/{etld1}"
    res = client.get_json(f"domain:{etld1}", url, headers={"Accept": "application/rdap+json"})
    if res.status != "ok":
        return {"status": res.status, "error": res.error}
    d = res.data
    ev = {e.get("eventAction"): e.get("eventDate") for e in d.get("events", [])}
    registrar, iana, emails = None, None, []
    for ent in d.get("entities", []):
        roles = ent.get("roles", [])
        if "registrar" in roles:
            registrar = _vcard_fn(ent) or ent.get("handle")
            for pid in ent.get("publicIds", []) or []:
                if "IANA" in pid.get("type", ""):
                    iana = int(pid["identifier"]) if str(pid.get("identifier", "")).isdigit() else None
        if "registrant" in roles:
            em = _vcard_email(ent)
            if em and "redacted" not in em and "privacy" not in em and "proxy" not in em:
                emails.append(em)
    return {
        "status": "ok", "domain": etld1, "registrar": registrar, "registrar_iana_id": iana,
        "created": _dt(ev.get("registration")), "expires": _dt(ev.get("expiration")),
        "updated": _dt(ev.get("last changed")), "rdap_status": d.get("status", []),
        "nameservers": sorted({(ns.get("ldhName") or "").lower().rstrip(".") for ns in d.get("nameservers", []) if ns.get("ldhName")}),
        "registrant_emails": emails, "source_url": url,
    }


def enrich_domain(loader: Loader, domain: str) -> dict:
    info = lookup(loader.conn, domain)
    if not info or info.get("status") != "ok":
        return {"domain": domain, **(info or {})}
    etld1 = info["domain"]
    loader.conn.execute(
        """UPDATE obs_domains SET registrar = %s, registrar_iana_id = %s, created_at = %s, expires_at = %s,
               updated_at = %s, rdap_status = %s, nameservers = %s, enriched_at = now()
           WHERE etld1 = %s""",
        (info["registrar"], info["registrar_iana_id"], info["created"], info["expires"], info["updated"],
         info["rdap_status"], info["nameservers"], etld1))
    reg = _norm_registrar(info["registrar"])
    if reg:
        loader.relate(RelationDraft(("etld1", etld1), "registered_by", ("registrar", reg), "rdap",
                                    {"created": str(info["created"]), "name": info["registrar"]}))
        loader.propagate(etld1, "registrar", reg, "enrich.rdap", "rdap@1", display=info["registrar"])
        if info["created"]:
            batch = f"{reg}|{info['created']:%Y-%m-%dT%H}"
            loader.propagate(etld1, "registration_batch", batch, "enrich.rdap", "rdap@1",
                             context={"created": info["created"].isoformat()})
    for ns in info["nameservers"]:
        loader.relate(RelationDraft(("etld1", etld1), "uses_ns", ("nameserver", ns), "rdap"))
        loader.propagate(etld1, "nameserver", ns, "enrich.rdap", "rdap@1")
    if info["nameservers"]:
        loader.propagate(etld1, "ns_set", "+".join(info["nameservers"]), "enrich.rdap", "rdap@1")
    for em in info["registrant_emails"]:
        loader.relate(RelationDraft(("etld1", etld1), "registered_by", ("registrant_email", em), "rdap"))
    loader.conn.commit()
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in info.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("domain")
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    with connect(args.db) as conn:
        print(enrich_domain(Loader(conn, artifacts.from_env(), sensitivity="public"), args.domain.lower()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
