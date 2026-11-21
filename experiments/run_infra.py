"""Approach (f): public infra enrichment of landing domains — DNS (1.1.1.1), RDAP (rdap.org), crt.sh, ASN (Team Cymru DNS).
Never contacts the scam hosts themselves. Cached in <dir>/infra_enrich.json.
Usage: uv run python run_infra.py [incidents.json]"""
import json
import os
import sys
import time

import dns.resolver
import httpx

from rp.extract import etld1

INC = sys.argv[1] if len(sys.argv) > 1 else "../data/experiments/sample_v1/incidents.json"
OUT = os.path.join(os.path.dirname(INC), "infra_enrich.json")
incs = json.load(open(INC, encoding="utf-8"))
cache = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
R = dns.resolver.Resolver(configure=False)
R.nameservers = ["1.1.1.1", "8.8.8.8"]
R.lifetime = 6
H = httpx.Client(timeout=40, headers={"User-Agent": "research-client/0.1"}, follow_redirects=True)

domains = sorted({etld1(d["fqdn"]) for i in incs for d in i["infra"]["domains"]} | {i["landing"]["etld1"] for i in incs if i["landing"].get("etld1")})


def q(name, rtype):
    try:
        return sorted(r.to_text() for r in R.resolve(name, rtype))
    except Exception as e:  # noqa: BLE001
        return [f"ERR:{type(e).__name__}"]


def asn(ip):
    try:
        rev = ".".join(reversed(ip.split(".")))
        txt = R.resolve(f"{rev}.origin.asn.cymru.com", "TXT")[0].to_text().strip('"')
        a = txt.split("|")[0].strip()
        name = R.resolve(f"AS{a}.asn.cymru.com", "TXT")[0].to_text().strip('"').split("|")[-1].strip()
        return {"asn": a, "prefix": txt.split("|")[1].strip(), "cc": txt.split("|")[2].strip(), "name": name}
    except Exception as e:  # noqa: BLE001
        return {"err": type(e).__name__}


for d in domains:
    if d in cache and "crtsh" in cache[d]:
        continue
    t0 = time.time()
    rec = {"A": q(d, "A"), "AAAA": q(d, "AAAA"), "NS": q(d, "NS"), "MX": q(d, "MX"), "TXT": q(d, "TXT")[:5]}
    rec["asn"] = {ip: asn(ip) for ip in rec["A"] if not ip.startswith("ERR")}
    try:
        r = H.get(f"https://rdap.org/domain/{d}")
        j = r.json() if r.status_code == 200 else {}
        ev = {e.get("eventAction"): e.get("eventDate") for e in j.get("events", [])}
        reg = next((e for e in j.get("entities", []) if "registrar" in (e.get("roles") or [])), {})
        regname = next((v[3] for v in (reg.get("vcardArray") or [None, []])[1] if v[0] == "fn"), None) if reg else None
        rec["rdap"] = {"status_code": r.status_code, "registrar": regname, "created": ev.get("registration"),
                       "expires": ev.get("expiration"), "updated": ev.get("last changed"),
                       "ns": sorted(n.get("ldhName", "").lower() for n in j.get("nameservers", [])), "status": j.get("status")}
    except Exception as e:  # noqa: BLE001
        rec["rdap"] = {"err": str(e)[:100]}
    try:
        r = H.get("https://crt.sh/", params={"q": d, "output": "json"})
        certs = r.json() if r.status_code == 200 else []
        rec["crtsh"] = sorted(({"issuer": c.get("issuer_name", "")[-60:], "not_before": c.get("not_before"),
                                "names": sorted(set(c.get("name_value", "").split("\n")))[:10], "id": c.get("id")} for c in certs),
                              key=lambda c: c["not_before"] or "")[:40]
    except Exception as e:  # noqa: BLE001
        rec["crtsh"] = [{"err": str(e)[:100]}]
    rec["t"] = round(time.time() - t0, 1)
    cache[d] = rec
    json.dump(cache, open(OUT, "w", encoding="utf-8"), indent=1)
    print(d, rec["A"][:2], rec["NS"][:2], rec.get("rdap", {}).get("registrar"), rec.get("rdap", {}).get("created"),
          f"crt={len(rec['crtsh'])}", f"{rec['t']}s", flush=True)
    time.sleep(1.5)
print("saved", OUT)
