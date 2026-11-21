"""Read-only corpus access for White Rabbit: `db_search`, `incident_neighborhood`, campaign domain lookup.

Order: Postgres (settings.database_url, read-only transactions) -> JSON corpus under DATA_DIR/experiments.
`trop.engine.service` (WS1) is used for campaign membership when it exists; nothing here ever writes.
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from trop.config import settings

log = logging.getLogger("trop.agent.db")

# observable type -> evidence level (ATLAS vocabulary): operator = same account, campaign = same operation,
# platform = shared commercial tooling (never proof of the same operator).
LEVEL = {
    "kit_tenant": "operator", "fb_pixel": "operator", "capi_gateway": "operator", "google_tag": "operator",
    "tiktok_pixel": "operator", "tds_key": "operator", "third_party_account": "operator", "ns_set": "operator",
    "meta_campaign_id": "operator", "meta_adset_id": "operator", "registrant_email": "operator",
    "lander_id": "campaign", "headline_template": "campaign", "clickbait_template": "campaign", "product": "campaign",
    "registration_batch": "campaign", "cert_batch": "campaign", "phone": "campaign", "iban": "campaign",
    "telegram": "campaign", "crypto_wallet": "campaign", "email": "campaign", "favicon_mmh3": "campaign",
    "asset_sha256": "campaign", "ad_page_id": "campaign", "domain_pattern": "campaign", "cert": "campaign",
    "kit_endpoint": "platform", "lander_path": "platform", "url_param_schema": "platform", "form_schema": "platform",
    "ip": "infra", "asn": "infra", "nameserver": "infra", "registrar": "infra",
}
PIVOT_TYPES = tuple(LEVEL)
DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9-]{1,63}\.)+[a-z]{2,63}$", re.IGNORECASE)


def is_domain(q: str) -> bool:
    return bool(DOMAIN_RE.match(q.strip().lower().rstrip(".")))


def etld1(x: str) -> str:
    try:
        from trop.enrich.util import etld1 as _e
        return _e(x)
    except Exception:  # noqa: BLE001
        parts = x.lower().strip(".").split(".")
        return ".".join(parts[-2:])


def inc_id(n: Any) -> str:
    return f"INC-{n}"


def level_of(typ: str, df: int = 0, noise_reason: str | None = None) -> str:
    if noise_reason and noise_reason.startswith("platform"):
        return "platform"
    lvl = LEVEL.get(typ, "campaign")
    if typ == "asset_sha256" and df > 40:      # SDK bundles shared by a whole multi-tenant kit
        return "platform"
    return lvl


# ============================================================================== Postgres
class _PG:
    def __init__(self) -> None:
        self._conn = None
        self.ok: bool | None = None

    def conn(self):
        if self.ok is False:
            return None
        if self._conn is None or self._conn.closed:
            try:
                import psycopg
                self._conn = psycopg.connect(settings.database_url, connect_timeout=3, autocommit=True)
                self._conn.execute("SET default_transaction_read_only = on")
                self._conn.execute("SET statement_timeout = '15s'")
                self.ok = True
            except Exception as e:  # noqa: BLE001
                log.warning("Postgres unavailable (%s); using the JSON corpus", str(e)[:120])
                self.ok = False
                return None
        return self._conn

    def q(self, sql: str, args: tuple | dict = ()) -> list[dict]:
        c = self.conn()
        if c is None:
            raise RuntimeError("db unavailable")
        from psycopg.rows import dict_row
        with c.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, args)
            return list(cur.fetchall())


PG = _PG()


def db_available() -> bool:
    return PG.conn() is not None


def _pg_incidents_for_domain(d: str, limit: int) -> list[dict]:
    return PG.q(
        """SELECT i.id, i.source_ref, s.name AS source, i.entry_etld1, i.final_etld1, i.title, i.observed_at, i.kind
             FROM incidents i JOIN sources s ON s.id = i.source_id
            WHERE i.entry_etld1 = %(d)s OR i.final_etld1 = %(d)s
               OR i.id IN (SELECT io.incident_id FROM incident_observables io JOIN observables o ON o.id = io.observable_id
                            WHERE o.type IN ('etld1','fqdn') AND (o.value = %(d)s OR o.value LIKE '%%.' || %(d)s))
            ORDER BY i.observed_at DESC NULLS LAST LIMIT %(n)s""", {"d": d, "n": limit})


def _pg_traces(incident_ids: list[int], limit: int) -> list[dict]:
    if not incident_ids:
        return []
    return PG.q(
        """SELECT o.id, o.type, o.value, o.display, o.df_incidents AS df, o.noise, o.noise_reason
             FROM incident_observables io JOIN observables o ON o.id = io.observable_id
            WHERE io.incident_id = ANY(%(ids)s) AND o.type = ANY(%(types)s) AND o.df_incidents >= 2
            GROUP BY o.id ORDER BY o.df_incidents ASC LIMIT %(n)s""",
        {"ids": incident_ids, "types": list(PIVOT_TYPES), "n": limit})


def _pg_domains_for_observable(oid: int, exclude: set[str], limit: int = 40) -> list[str]:
    rows = PG.q(
        """SELECT DISTINCT coalesce(i.final_etld1, i.entry_etld1) AS d FROM incident_observables io
             JOIN incidents i ON i.id = io.incident_id WHERE io.observable_id = %s LIMIT %s""", (oid, limit + len(exclude)))
    return [r["d"] for r in rows if r["d"] and r["d"] not in exclude][:limit]


def _pg_value(q: str, limit: int) -> list[dict]:
    return PG.q(
        """SELECT o.id, o.type, o.value, o.display, o.df_incidents AS df, o.noise, o.noise_reason FROM observables o
            WHERE o.value = %(q)s OR (length(%(q)s) >= 8 AND o.value LIKE %(q)s || '%%' AND o.type = ANY(%(types)s))
            ORDER BY o.df_incidents DESC LIMIT %(n)s""", {"q": q, "types": list(PIVOT_TYPES), "n": limit})


def _summ_inc(r: dict) -> dict:
    return {"id": inc_id(r["id"]), "ref": r.get("source_ref"), "source": (r.get("source") or "")[:40],
            "domain": r.get("final_etld1") or r.get("entry_etld1"), "title": (r.get("title") or "")[:90],
            "observed_at": str(r.get("observed_at") or "")[:19] or None}


def _trace_row(t: dict, exclude: set[str], with_domains: bool) -> dict:
    lvl = level_of(t["type"], t["df"], t.get("noise_reason"))
    row = {"type": t["type"], "value": (t.get("value") or "")[:120], "df": t["df"], "level": lvl,
           "noise": bool(t.get("noise")) or None}
    if with_domains and not t.get("noise") and lvl != "infra":
        doms = _pg_domains_for_observable(t["id"], exclude, 40)
        row["domains"] = doms
        row["n_domains"] = len(doms)
    return row


def db_search(query: str, limit: int = 15) -> dict[str, Any]:
    """Look a domain or a trace value (tenant UUID, pixel, sha256, template…) up in our corpus."""
    q = (query or "").strip().lower().rstrip(".")
    if not q:
        return {"query": query, "error": "empty query"}
    try:
        if PG.conn() is None:
            return _json_search(q, limit)
        if is_domain(q):
            d = etld1(q)
            incs = _pg_incidents_for_domain(d, limit)
            traces = _pg_traces([r["id"] for r in incs], 60)
            # keep the most specific traces, but always the operator-level ones
            traces = sorted(traces, key=lambda t: ({"operator": 0, "campaign": 1, "platform": 2, "infra": 3}[
                level_of(t["type"], t["df"], t.get("noise_reason"))], t["df"]))
            seen_types: dict[str, int] = {}
            picked = []
            for t in traces:
                if t.get("noise") and t["type"] not in ("kit_endpoint", "lander_path"):
                    continue
                if seen_types.get(t["type"], 0) >= 3:
                    continue
                seen_types[t["type"]] = seen_types.get(t["type"], 0) + 1
                picked.append(t)
            return {"query": q, "kind": "domain", "domain": d, "known": bool(incs),
                    "incidents": [_summ_inc(r) for r in incs],
                    "traces": [_trace_row(t, {d}, True) for t in picked[:limit]],
                    "campaigns": campaigns_for_domain(d)}
        obs = _pg_value(q, 5)
        return {"query": q, "kind": "value", "matches": [_trace_row(o, set(), True) for o in obs]}
    except Exception as e:  # noqa: BLE001
        log.warning("db_search failed: %s", e)
        return {"query": q, "error": str(e)[:200]}


def incident_neighborhood(incident_id: str | int, depth: int = 1, max_df: int = 50) -> dict[str, Any]:
    """Incidents linked to one incident through shared H/M traces (SQL incident_neighborhood())."""
    n = int(str(incident_id).replace("INC-", "")) if str(incident_id).replace("INC-", "").isdigit() else None
    if n is None:
        return {"incident_id": incident_id, "error": "expected an INC-<n> id from db_search"}
    if PG.conn() is None:
        return {"incident_id": incident_id, "error": "database unavailable (JSON corpus has no neighbourhood index)"}
    try:
        rows = PG.q(
            """SELECT nb.incident_id, nb.depth, nb.via_type, nb.via_value, coalesce(i.final_etld1, i.entry_etld1) AS domain,
                      i.title FROM incident_neighborhood(%s, %s, %s) nb JOIN incidents i ON i.id = nb.incident_id
              WHERE nb.depth > 0 ORDER BY nb.depth, nb.incident_id LIMIT 200""", (n, max(1, min(depth, 2)), max_df))
    except Exception as e:  # noqa: BLE001
        return {"incident_id": incident_id, "error": str(e)[:200]}
    by_via: dict[tuple, dict] = {}
    for r in rows:
        k = (r["via_type"], r["via_value"])
        g = by_via.setdefault(k, {"via_type": r["via_type"], "via_value": (r["via_value"] or "")[:100],
                                  "level": level_of(r["via_type"] or ""), "domains": [], "incidents": []})
        if r["domain"] and r["domain"] not in g["domains"]:
            g["domains"].append(r["domain"])
        g["incidents"].append(inc_id(r["incident_id"]))
    groups = sorted(by_via.values(), key=lambda g: -len(g["domains"]))
    return {"incident_id": inc_id(n), "neighbours": len(rows), "groups": groups[:15]}


# ============================================================================== campaigns
def campaigns_for_domain(domain: str) -> list[str]:
    """Campaign ids a domain already belongs to (engine service when available, else DB campaigns, else labels)."""
    d = etld1(domain)
    try:
        from trop.engine import service as eng  # type: ignore
        fn = getattr(eng, "campaigns_for_domain", None)
        if fn:
            return list(fn(d))
    except Exception:  # noqa: BLE001
        pass
    out: list[str] = []
    try:
        if PG.conn() is not None:
            rows = PG.q(
                """SELECT DISTINCT coalesce(c.code, 'KMP-' || c.id) AS code FROM campaign_memberships m
                     JOIN campaigns c ON c.id = m.campaign_id JOIN incidents i ON i.id = m.incident_id
                    WHERE m.valid_to IS NULL AND (i.entry_etld1 = %(d)s OR i.final_etld1 = %(d)s)""", {"d": d})
            out = [r["code"] for r in rows]
    except Exception:  # noqa: BLE001
        pass
    if not out:
        out = [c for c, doms in label_campaign_domains().items() if d in doms]
    return out


def campaign_domains(campaign_id: str | None) -> set[str]:
    if not campaign_id:
        return set()
    try:
        from trop.act.campaign import load_campaign
        return {x["fqdn"] for x in load_campaign(campaign_id).get("domains", [])} | {
            etld1(x["fqdn"]) for x in load_campaign(campaign_id).get("domains", [])}
    except Exception:  # noqa: BLE001
        return set(label_campaign_domains().get(campaign_id, set()))


def experiments_dir() -> Path | None:
    for p in (Path(settings.data_dir).resolve().parent / "experiments", Path(__file__).resolve().parents[3] / "experiments"):
        if (p / "labels.yaml").is_file():
            return p
    return None


@lru_cache(maxsize=1)
def label_campaign_domains() -> dict[str, set[str]]:
    """Hand-labelled campaigns (experiments/labels*.yaml) -> domains, via the DB source refs. Ids: 'LAB-A' etc."""
    exp = experiments_dir()
    if exp is None:
        return {}
    import yaml
    out: dict[str, set[str]] = {}
    refs: dict[str, str] = {}
    for fn, prefix in (("labels.yaml", "sample_v1/"), ("labels_dane.yaml", "dane/")):
        f = exp / fn
        if not f.is_file():
            continue
        y = yaml.safe_load(f.read_text()) or {}
        for k, v in (y.get("incidents") or {}).items():
            c = (v or {}).get("campaign")
            if c:
                refs[prefix + (k[1:] if prefix == "dane/" and k.startswith("d") else k)] = f"LAB-{c}"
    try:
        if PG.conn() is not None and refs:
            rows = PG.q("SELECT source_ref, entry_etld1, final_etld1 FROM incidents WHERE source_ref = ANY(%s)", (list(refs),))
            for r in rows:
                for d in {r["entry_etld1"], r["final_etld1"]} - {None}:
                    out.setdefault(refs[r["source_ref"]], set()).add(d)
    except Exception:  # noqa: BLE001
        pass
    return out


def known_domains(domains: list[str]) -> set[str]:
    """Which registrable domains already have an incident in our corpus (batch)."""
    ds = sorted({etld1(d) for d in domains if d})
    if not ds:
        return set()
    try:
        if PG.conn() is not None:
            rows = PG.q("""SELECT DISTINCT d FROM (SELECT entry_etld1 AS d FROM incidents UNION SELECT final_etld1 FROM incidents) x
                            WHERE d = ANY(%s)""", (ds,))
            return {r["d"] for r in rows}
    except Exception:  # noqa: BLE001
        pass
    have = {((i.get("landing") or {}).get("etld1") or "").lower() for i in _corpus()}
    return {d for d in ds if d in have}


def oracle_flags(domains: list[str]) -> dict[str, dict]:
    """Oracle predictions (oracle_candidates) for these domains: {etld1: {score, seen_at, source, status}}."""
    ds = sorted({etld1(d) for d in domains if d})
    try:
        if ds and PG.conn() is not None:
            rows = PG.q("""SELECT DISTINCT ON (etld1) etld1, score, seen_at, source, status FROM oracle_candidates
                            WHERE etld1 = ANY(%s) ORDER BY etld1, seen_at""", (ds,))
            return {r["etld1"]: {"score": r["score"], "seen_at": str(r["seen_at"])[:19], "source": r["source"],
                                 "status": r["status"]} for r in rows}
    except Exception:  # noqa: BLE001
        pass
    return {}


def observable_df(value: str) -> dict | None:
    """df / noise of one exact observable value (e.g. an asset sha256 used as a urlscan pivot)."""
    try:
        if PG.conn() is not None:
            rows = PG.q("SELECT type, df_incidents AS df, noise, noise_reason FROM observables WHERE value = %s "
                        "ORDER BY df_incidents DESC LIMIT 1", (value,))
            return rows[0] if rows else None
    except Exception:  # noqa: BLE001
        pass
    return None


# ============================================================================== JSON corpus fallback
@lru_cache(maxsize=1)
def _corpus() -> list[dict]:
    root = Path(settings.data_dir) / "experiments"
    incs: list[dict] = []
    for f in (root / "sample_v1" / "incidents_enriched.json", root / "dane" / "incidents.json"):
        try:
            incs += json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            continue
    return incs


def _json_traces(inc: dict) -> list[tuple[str, str]]:
    t = inc.get("tracking") or {}
    out = [("kit_tenant", v) for v in t.get("kit_tenants", [])] + [("fb_pixel", v) for v in t.get("fb_pixels", [])]
    out += [("capi_gateway", v) for v in t.get("capi_gateways", [])] + [("lander_id", v) for v in t.get("lander_ids", [])]
    out += [("asset_sha256", v) for v in t.get("asset_hashes", [])[:30]]
    return out


def _json_search(q: str, limit: int) -> dict[str, Any]:
    incs = _corpus()
    if not incs:
        return {"query": q, "error": "no corpus available (database down, JSON corpus missing)"}

    def dom(i: dict) -> str:
        return ((i.get("landing") or {}).get("etld1") or "").lower()

    if is_domain(q):
        d = etld1(q)
        hit = [i for i in incs if dom(i) == d]
        traces = []
        for typ, v in {x for i in hit for x in _json_traces(i)}:
            doms = sorted({dom(j) for j in incs if (typ, v) in _json_traces(j)} - {d, ""})
            if doms:
                traces.append({"type": typ, "value": v, "df": len(doms) + 1, "level": level_of(typ, len(doms)),
                               "domains": doms[:40], "n_domains": len(doms)})
        return {"query": q, "kind": "domain", "domain": d, "known": bool(hit), "source": "json",
                "incidents": [{"id": i["id"], "domain": dom(i), "title": ((i.get("landing") or {}).get("title") or "")[:90]}
                              for i in hit[:limit]], "traces": traces[:limit], "campaigns": campaigns_for_domain(d)}
    m = [{"type": typ, "value": v, "domains": sorted({dom(i) for i in incs if (typ, v) in _json_traces(i)})}
         for typ, v in {x for i in incs for x in _json_traces(i) if x[1].startswith(q)}]
    return {"query": q, "kind": "value", "source": "json", "matches": m[:5]}
