"""STIX 2.1 bundle (hand-rolled, MISP-importable) + a MISP core-format event + CSV of indicators.

Objects: identity (TROP), campaign, intrusion-set (operator, when known), domain-name SCOs, one indicator per domain
(pattern [domain-name:value = '…']), url indicators for landing URLs, relationships indicator→campaign `indicates`,
campaign→intrusion-set `attributed-to`, a note with the shared evidence. Ids are UUIDv5 over stable keys, so
re-exporting the same campaign gives the same ids.
"""
from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Any

NS = uuid.UUID("6f1e7a52-3d0b-4f43-9a8e-7c2b51a0d017")


def _id(kind: str, key: str) -> str:
    return f"{kind}--{uuid.uuid5(NS, kind + '|' + key)}"


def _ts(x: str | None, default: str) -> str:
    if not x:
        return default
    x = x.replace(" ", "T")
    if len(x) == 10:
        x += "T00:00:00"
    x = x[:19]
    return x + ".000Z"


def stix_bundle(pkg: dict[str, Any], d: dict[str, Any]) -> dict[str, Any]:
    now = _ts(pkg["created_at"], "2026-01-01T00:00:00.000Z")
    ident = {"type": "identity", "spec_version": "2.1", "id": _id("identity", "trop"), "created": now, "modified": now,
             "name": "TROP (HackNation 2026)", "identity_class": "system"}
    camp = {"type": "campaign", "spec_version": "2.1", "id": _id("campaign", d["id"]), "created": now, "modified": now,
            "created_by_ref": ident["id"], "name": f"{d['id']} {d['name']}", "description": d.get("narrative") or "",
            "objective": "fraud (scam ads)", "labels": ["scam-ad-campaign"] + (["fictional"] if d.get("fictional") else [])}
    if d["incidents"]:
        camp["first_seen"] = _ts(min(i["captured_at"] for i in d["incidents"] if i.get("captured_at")) if any(
            i.get("captured_at") for i in d["incidents"]) else None, now)
    objs: list[dict] = [ident, camp]
    if d.get("operator_id"):
        iset = {"type": "intrusion-set", "spec_version": "2.1", "id": _id("intrusion-set", d["operator_id"]), "created": now,
                "modified": now, "created_by_ref": ident["id"], "name": d["operator_id"]}
        objs += [iset, _rel(camp["id"], "attributed-to", iset["id"], now, ident["id"])]
    for x in d["domains"]:
        dn = {"type": "domain-name", "spec_version": "2.1", "id": _id("domain-name", x["fqdn"]), "value": x["fqdn"]}
        ind = {"type": "indicator", "spec_version": "2.1", "id": _id("indicator", "domain|" + x["fqdn"]), "created": now,
               "modified": now, "created_by_ref": ident["id"], "name": x["fqdn"], "indicator_types": ["malicious-activity"],
               "pattern": f"[domain-name:value = '{x['fqdn']}']", "pattern_type": "stix",
               "valid_from": _ts(x.get("cert_issued_at") or x.get("registered_at"), now),
               "description": "Domena kampanii " + d["id"] + (" (z śledztwa White Rabbit)" if x.get("source") == "investigation" else ""),
               "labels": (["certpl-listed"] if x.get("on_certpl") else ["certpl-not-listed"])}
        objs += [dn, ind, _rel(ind["id"], "indicates", camp["id"], now, ident["id"])]
    for a in d["ads"]:
        if a.get("library_url") and a.get("library_id"):
            u = {"type": "url", "spec_version": "2.1", "id": _id("url", a["library_url"]), "value": a["library_url"]}
            objs.append(u)
    ev = "\n".join(f"- [{e['type']}] {e['display']} ({e['members_with']}/{e['members_total']}, {e['strength']})" for e in d["evidence"])
    objs.append({"type": "note", "spec_version": "2.1", "id": _id("note", d["id"] + "|evidence"), "created": now, "modified": now,
                 "created_by_ref": ident["id"], "abstract": "Wspólne ślady kampanii", "content": ev or "-",
                 "object_refs": [camp["id"]]})
    return {"type": "bundle", "id": _id("bundle", pkg["id"]), "objects": objs}


def _rel(src: str, rel: str, dst: str, now: str, by: str) -> dict:
    return {"type": "relationship", "spec_version": "2.1", "id": _id("relationship", f"{src}|{rel}|{dst}"), "created": now,
            "modified": now, "created_by_ref": by, "relationship_type": rel, "source_ref": src, "target_ref": dst}


def misp_event(pkg: dict[str, Any], d: dict[str, Any]) -> dict[str, Any]:
    attrs = [{"type": "domain", "category": "Network activity", "to_ids": True, "value": x["fqdn"],
              "comment": "CERT PL: " + ("na liście" if x.get("on_certpl") else "brak")} for x in d["domains"]]
    attrs += [{"type": "url", "category": "Network activity", "to_ids": False, "value": u} for x in d["domains"] for u in x.get("urls", [])[:1]]
    attrs += [{"type": "text", "category": "Other", "to_ids": False, "value": f"{e['field']}: {e['value']}",
               "comment": f"{e['members_with']}/{e['members_total']}"} for e in d["evidence"]]
    attrs += [{"type": "text", "category": "External analysis", "to_ids": False, "value": f"Meta Ad Library {a['library_id']} · {a.get('advertiser')}"}
              for a in d["ads"] if a.get("library_id")]
    return {"Event": {"info": f"TROP {d['id']} «{d['name']}» — kampania reklam oszukańczych" + (" [FIKCYJNE]" if d.get("fictional") else ""),
                      "date": pkg["created_at"][:10], "threat_level_id": "2", "analysis": "1", "distribution": "0",
                      "uuid": str(uuid.uuid5(NS, "misp|" + pkg["id"])),
                      "Tag": [{"name": "tlp:amber"}, {"name": "type:scam-ad-campaign"}], "Attribute": attrs}}


def indicators_csv(d: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["kind", "value", "campaign", "on_certpl", "registered_at", "cert_issued_at", "source"])
    for x in d["domains"]:
        w.writerow(["domain", x["fqdn"], d["id"], int(bool(x.get("on_certpl"))), x.get("registered_at") or "",
                    x.get("cert_issued_at") or "", x.get("source") or ""])
    for a in d["ads"]:
        w.writerow(["ad", a.get("library_id") or "", d["id"], "", "", "", a.get("advertiser") or ""])
    return buf.getvalue()


def dumps(o: Any) -> bytes:
    return json.dumps(o, ensure_ascii=False, indent=1).encode("utf-8")
