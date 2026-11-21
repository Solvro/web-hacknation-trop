"""Engine corpus <-> Postgres (tables from 0006 + 0013).

  save_corpus(corpus)      engine docs -> engine_incidents; KMP/OP/OPN -> campaigns / operator_families / operations;
                           labels -> campaign_memberships (current rows)
  load_corpus()            -> trop.engine.corpus.Corpus  (used by Corpus.load(source="db"))
  save_decision(decision)  -> engine_decisions (current row per incident + model version)

Engine ids map to the existing incidents rows by (source key, source_ref): 'p1' -> sample_v1/p1, 'd3' -> dane/3;
other ids are inserted under the 'trop' source.
"""
from __future__ import annotations

import hashlib
import re

from psycopg.types.json import Jsonb

from .db import connect


def _strip(inc: dict) -> dict:
    return {k: v for k, v in inc.items() if not k.startswith("_")}


def _source_ref(ext_id: str) -> tuple[str, str]:
    if re.fullmatch(r"p\d+", ext_id):
        return "sample_v1", f"sample_v1/{ext_id}"
    if re.fullmatch(r"d\d+", ext_id):
        return "dane", f"dane/{ext_id[1:]}"
    return "trop", f"trop/{ext_id}"


def _ensure_trop_source(cur) -> int:
    cur.execute("INSERT INTO sources(key, kind, name, redistribution) VALUES ('trop', 'manual', 'TROP analyses', 'internal') "
                "ON CONFLICT (key) DO NOTHING")
    return cur.execute("SELECT id FROM sources WHERE key='trop'").fetchone()[0]


def incident_pk(cur, inc: dict) -> int:
    key, ref = _source_ref(inc["id"])
    row = cur.execute("SELECT i.id FROM incidents i JOIN sources s ON s.id = i.source_id WHERE s.key=%s AND i.source_ref=%s",
                      (key, ref)).fetchone()
    if row:
        return row[0]
    sid = cur.execute("SELECT id FROM sources WHERE key=%s", (key,)).fetchone()
    sid = sid[0] if sid else _ensure_trop_source(cur)
    la, ad = inc.get("landing") or {}, inc.get("ad") or {}
    kind = "ad+landing" if la.get("entry_url") and ad.get("screenshot_path") else ("landing_only" if la.get("entry_url") else "ad_only")
    dk = hashlib.sha256((la.get("entry_url") or inc["id"]).encode()).hexdigest()
    return cur.execute(
        "INSERT INTO incidents(source_id, source_ref, kind, status, entry_url, entry_etld1, title, lang, headline_template, "
        "vertical, dedupe_key, raw) VALUES (%s,%s,%s,'extracted',%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (sid, ref, kind, la.get("entry_url"), la.get("etld1"), la.get("title"), (inc.get("content") or {}).get("lang"),
         (inc.get("content") or {}).get("headline_template"), (inc.get("content") or {}).get("vertical"), dk,
         Jsonb({"engine_id": inc["id"]}))).fetchone()[0]


def _upsert_code(cur, table: str, code: str, name: str | None, extra: dict | None = None) -> int:
    cols = {"code": code, "name": name, **(extra or {})}
    keys = ", ".join(cols)
    ph = ", ".join(["%s"] * len(cols))
    upd = ", ".join(f"{k}=EXCLUDED.{k}" for k in cols if k != "code")
    vals = [Jsonb(v) if isinstance(v, (dict, list)) else v for v in cols.values()]
    return cur.execute(f"INSERT INTO {table}({keys}) VALUES ({ph}) ON CONFLICT (code) DO UPDATE SET {upd} RETURNING id",
                       vals).fetchone()[0]


def save_corpus(corpus) -> dict:
    n = 0
    with connect() as conn, conn.cursor() as cur:
        opn_pk = {c: _upsert_code(cur, "operations", c, (m or {}).get("name") or c) for c, m in corpus.operations.items()}
        op_pk = {c: _upsert_code(cur, "operator_families", c, (m or {}).get("name") or c) for c, m in corpus.operators.items()}
        camp_pk = {}
        for cid, m in corpus.campaigns.items():
            camp_pk[cid] = _upsert_code(cur, "campaigns", cid, m.get("name"), {
                "status": "active" if m.get("status", "active") == "active" else "candidate", "vertical": m.get("vertical"),
                "family_id": op_pk.get(m.get("operator_id")), "operation_id": opn_pk.get(m.get("operation_id")),
                "meta": {"engine": True}})
        for inc in corpus.incidents:
            pk = incident_pk(cur, inc)
            cur.execute("INSERT INTO engine_incidents(incident_id, ext_id, doc) VALUES (%s,%s,%s) ON CONFLICT (incident_id) "
                        "DO UPDATE SET doc=EXCLUDED.doc, ext_id=EXCLUDED.ext_id, updated_at=now()",
                        (pk, inc["id"], Jsonb(_strip(inc))))
            cid = corpus.campaign_of.get(inc["id"])
            if cid:
                cur.execute("UPDATE campaign_memberships SET valid_to=now() WHERE incident_id=%s AND valid_to IS NULL", (pk,))
                cur.execute("INSERT INTO campaign_memberships(incident_id, campaign_id, decision, decided_by, reason) "
                            "VALUES (%s,%s,'manual','analyst',%s)", (pk, camp_pk[cid], Jsonb({"source": corpus.meta.get("source")})))
            n += 1
        cur.execute("UPDATE campaigns c SET n_members = (SELECT count(*) FROM campaign_memberships m WHERE m.campaign_id=c.id "
                    "AND m.valid_to IS NULL) WHERE c.code = ANY(%s)", (list(camp_pk),))
        conn.commit()
    return {"incidents": n, "campaigns": len(camp_pk), "operators": len(op_pk), "operations": len(opn_pk)}


def load_corpus():
    from trop.engine.corpus import Corpus
    c = Corpus(meta={"source": "db"})
    with connect() as conn, conn.cursor() as cur:
        rows = cur.execute(
            "SELECT e.ext_id, e.doc, c.code, c.name, c.vertical, c.status, f.code, o.code "
            "FROM engine_incidents e JOIN campaign_memberships m ON m.incident_id=e.incident_id AND m.valid_to IS NULL "
            "JOIN campaigns c ON c.id=m.campaign_id LEFT JOIN operator_families f ON f.id=c.family_id "
            "LEFT JOIN operations o ON o.id=c.operation_id ORDER BY e.incident_id").fetchall()
    for ext, doc, code, name, vert, st, fam, opn in rows:
        c.incidents.append(doc)
        c.campaign_of[ext] = code
        if fam:
            c.operator_of[ext] = fam
        if opn:
            c.operation_of[ext] = opn
        c.campaigns.setdefault(code, {"name": name, "vertical": vert, "status": st, "operator_id": fam, "operation_id": opn})
        if fam:
            c.operators.setdefault(fam, {"campaigns": []})
            if code not in c.operators[fam]["campaigns"]:
                c.operators[fam]["campaigns"].append(code)
        if opn:
            c.operations.setdefault(opn, {"campaigns": []})
            if code not in c.operations[opn]["campaigns"]:
                c.operations[opn]["campaigns"].append(code)
    if not c.incidents:
        raise LookupError("no engine corpus in the DB (run `trop db seed`)")
    return c


def save_decision(decision, inc: dict | None = None) -> int:
    with connect() as conn, conn.cursor() as cur:
        if inc is not None:
            pk = incident_pk(cur, inc)
            cur.execute("INSERT INTO engine_incidents(incident_id, ext_id, doc) VALUES (%s,%s,%s) ON CONFLICT (incident_id) "
                        "DO UPDATE SET doc=EXCLUDED.doc, updated_at=now()", (pk, inc["id"], Jsonb(_strip(inc))))
        else:
            pk = cur.execute("SELECT incident_id FROM engine_incidents WHERE ext_id=%s", (decision.incident_id,)).fetchone()[0]
        camp = None
        if decision.campaign_id:
            r = cur.execute("SELECT id FROM campaigns WHERE code=%s", (decision.campaign_id,)).fetchone()
            camp = r[0] if r else None
        cur.execute("UPDATE engine_decisions SET is_current=false WHERE incident_id=%s AND model_version=%s AND is_current",
                    (pk, decision.model_version))
        did = cur.execute("INSERT INTO engine_decisions(incident_id, model_version, state, campaign_id, score, p, decision) "
                          "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                          (pk, decision.model_version, decision.decision, camp, decision.score, decision.p,
                           Jsonb(decision.model_dump(mode="json")))).fetchone()[0]
        conn.commit()
    return did
