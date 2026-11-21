"""The single write path into Postgres for every adapter (sample_dir, bundle, capture, hunter, extension).

Idempotent: re-ingesting the same (source, source_ref) replaces that incident's captures and
observable postings, bumps feature_version and flags it for incremental re-linking.
"""
from __future__ import annotations

import json
import mimetypes
import os
from datetime import datetime
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from ..ingest.model import AdDraft, ArtifactDraft, CaptureDraft, IncidentDraft, ObsHit, RelationDraft
from ..util.hashing import favicon_mmh3, image_hashes, sha256_bytes
from ..util.urls import etld1_of, normalize_url, split_host

DEFAULT_URL = "postgresql://redpill:redpill_dev@127.0.0.1:55432/redpill"
CORE_ROLES = ("ad_screenshot", "landing_har", "landing_html_saved", "landing_html_rendered", "landing_screenshot_full")


def connect(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or os.environ.get("DATABASE_URL", DEFAULT_URL))


def _json(v: Any) -> Jsonb:
    # Postgres jsonb/text cannot hold NUL; hostile pages and third-party scans sometimes contain it
    return Jsonb(v, dumps=lambda o: json.dumps(o, default=str, ensure_ascii=False).replace("\\u0000", "").replace("\x00", ""))


def _nul(s: str | None) -> str | None:
    return s.replace("\x00", "") if isinstance(s, str) else s


def _mime(a: ArtifactDraft, data: bytes) -> str | None:
    if a.mime:
        return a.mime
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"%PDF":
        return "application/pdf"
    if data[:2] == b"PK":
        return "application/zip"
    name = a.rel_path or (a.path.name if a.path else "")
    return mimetypes.guess_type(name)[0]


class Loader:
    def __init__(self, conn: psycopg.Connection, store, sensitivity: str = "restricted"):
        self.conn = conn
        self.store = store
        self.sensitivity = sensitivity
        self._obs: dict[tuple[str, str], int] = {}
        self._src: dict[str, int] = {}
        self.stats: dict[str, int] = {}

    def _bump(self, k: str, n: int = 1) -> None:
        self.stats[k] = self.stats.get(k, 0) + n

    # ---------- provenance ----------
    def source_id(self, key: str) -> int:
        if key not in self._src:
            row = self.conn.execute("SELECT id FROM sources WHERE key = %s", (key,)).fetchone()
            if not row:
                raise KeyError(f"unknown source {key!r} (add it to sources)")
            self._src[key] = row[0]
        return self._src[key]

    def start_run(self, source_key: str, trigger: str = "manual", params: dict | None = None, job_key: str | None = None) -> int:
        job_id = None
        if job_key:
            r = self.conn.execute("SELECT id FROM jobs WHERE key = %s", (job_key,)).fetchone()
            job_id = r[0] if r else None
        return self.conn.execute(
            "INSERT INTO job_runs (job_id, source_id, trigger, params) VALUES (%s, %s, %s, %s) RETURNING id",
            (job_id, self.source_id(source_key), trigger, _json(params or {}))).fetchone()[0]

    def finish_run(self, run_id: int, status: str = "ok", stats: dict | None = None, error: str | None = None,
                   cursor_after: dict | None = None) -> None:
        self.conn.execute(
            "UPDATE job_runs SET finished_at = now(), status = %s, stats = %s, error = %s, cursor_after = %s WHERE id = %s",
            (status, _json(stats if stats is not None else self.stats), error,
             _json(cursor_after) if cursor_after is not None else None, run_id))
        self.conn.execute("UPDATE jobs SET last_run_at = now() FROM job_runs r WHERE r.id = %s AND jobs.id = r.job_id", (run_id,))

    # ---------- artifacts ----------
    def put_artifact(self, a: ArtifactDraft) -> str:
        data = a.read()
        sha = sha256_bytes(data)
        mime = _mime(a, data)
        img = image_hashes(data) if (mime or "").startswith("image/") and not (mime or "").endswith("svg+xml") else None
        fav = favicon_mmh3(data) if a.role == "favicon" else None
        uri = self.store.put(data, sha, mime)
        self.conn.execute(
            """INSERT INTO artifacts (sha256, size_bytes, mime, storage_uri, sensitivity, phash, dhash, favicon_mmh3, width, height)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (sha256) DO NOTHING""",
            (sha, len(data), mime, uri, self.sensitivity, img and img.get("phash"), img and img.get("dhash"),
             fav, img and img.get("width"), img and img.get("height")))
        self._bump("artifacts")
        return sha

    def ref_artifact(self, sha: str, a: ArtifactDraft, incident_id=None, capture_id=None, ad_id=None) -> None:
        self.conn.execute(
            """INSERT INTO artifact_refs (sha256, incident_id, capture_id, ad_id, role, rel_path, url)
               VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
            (sha, incident_id, capture_id, ad_id, a.role, a.rel_path, a.url))

    # ---------- observables ----------
    def observable_id(self, type_: str, value: str, display: str | None = None, noise_reason: str | None = None,
                      attrs: dict | None = None) -> int:
        key = (type_, value)
        if key in self._obs and not noise_reason:
            return self._obs[key]
        oid = self.conn.execute(
            """INSERT INTO observables (type, value, display, noise, noise_reason, attrs)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (type, md5(value)) DO UPDATE SET
                   last_seen_at = now(),
                   display = coalesce(observables.display, EXCLUDED.display),
                   noise = observables.noise OR EXCLUDED.noise,
                   noise_reason = coalesce(observables.noise_reason, EXCLUDED.noise_reason),
                   attrs = observables.attrs || EXCLUDED.attrs
               RETURNING id""",
            (type_, value, display, noise_reason is not None, noise_reason, _json(attrs or {}))).fetchone()[0]
        if key not in self._obs:
            self._typed_details(oid, type_, value, attrs or {})
        self._obs[key] = oid
        return oid

    def _typed_details(self, oid: int, type_: str, value: str, attrs: dict) -> None:
        if type_ in ("fqdn", "etld1"):
            etld1, sld, tld = split_host(value)
            self.conn.execute(
                """INSERT INTO obs_domains (observable_id, fqdn, etld1, tld, sld, lexical)
                   VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (observable_id) DO NOTHING""",
                (oid, value, etld1, tld or "", sld, _json(_lexical(sld))))
        elif type_ == "ip":
            from ..ingest.extract import cdn_of
            cdn = attrs.get("cdn") or cdn_of(value)
            self.conn.execute(
                """INSERT INTO obs_ips (observable_id, ip, cdn, is_cdn) VALUES (%s,%s,%s,%s)
                   ON CONFLICT (observable_id) DO NOTHING""", (oid, value, cdn, cdn is not None))
        elif type_ == "cert":
            self.conn.execute(
                """INSERT INTO obs_certs (observable_id, serial, issuer_cn, issuer_org, subject_cn, sans, not_before, not_after)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (observable_id) DO UPDATE SET
                     sans = coalesce(obs_certs.sans, EXCLUDED.sans),
                     not_before = coalesce(obs_certs.not_before, EXCLUDED.not_before),
                     not_after = coalesce(obs_certs.not_after, EXCLUDED.not_after)""",
                (oid, attrs.get("serial"), attrs.get("issuer_cn"), attrs.get("issuer_org"), attrs.get("subject_cn"),
                 attrs.get("sans"), _cert_time(attrs.get("not_before")), _cert_time(attrs.get("not_after"))))
        elif type_ == "person":
            self.conn.execute(
                """INSERT INTO obs_persons (observable_id, canonical_name, role) VALUES (%s,%s,%s)
                   ON CONFLICT (observable_id) DO NOTHING""", (oid, value, attrs.get("role")))

    def link(self, incident_id: int, h: ObsHit) -> None:
        oid = self.observable_id(h.type, h.value, h.display, h.noise_reason, h.attrs)
        self.conn.execute(
            """INSERT INTO incident_observables (incident_id, observable_id, field, extractor, confidence, context)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON CONFLICT (incident_id, observable_id, field) DO UPDATE SET
                 confidence = greatest(incident_observables.confidence, EXCLUDED.confidence)""",
            (incident_id, oid, h.field, h.extractor, h.confidence, _json(h.context)))

    def propagate(self, domain: str, type_: str, value: str, field: str, extractor: str,
                  display: str | None = None, noise_reason: str | None = None, context: dict | None = None,
                  valid_from: datetime | None = None, valid_to: datetime | None = None) -> int:
        """Attach an enrichment-derived value (NS set, registration batch, cert, ASN …) to every incident whose
        landing chain contains `domain`, so blocking, df/idf and evidence treat it like any other observable.
        valid_from/valid_to restrict it to incidents observed in that window (a cert only belongs to the
        incidents seen while it was the live certificate — long-lived domains have hundreds)."""
        oid = self.observable_id(type_, value, display, noise_reason)
        cur = self.conn.execute(
            """INSERT INTO incident_observables (incident_id, observable_id, field, extractor, confidence, context)
               SELECT DISTINCT io.incident_id, %s, %s, %s, 1.0, %s
               FROM incident_observables io JOIN observables o ON o.id = io.observable_id
               JOIN incidents i ON i.id = io.incident_id
               WHERE o.type IN ('etld1','fqdn') AND o.value = %s AND io.field LIKE 'landing.%%'
                 AND (%s::timestamptz IS NULL OR i.observed_at IS NULL OR i.observed_at >= %s::timestamptz - interval '2 days')
                 AND (%s::timestamptz IS NULL OR i.observed_at IS NULL OR i.observed_at <= %s::timestamptz)
               ON CONFLICT (incident_id, observable_id, field) DO NOTHING""",
            (oid, field, extractor, _json({"via_domain": domain, **(context or {})}), domain,
             valid_from, valid_from, valid_to, valid_to))
        return cur.rowcount

    def relate(self, r: RelationDraft) -> None:
        if not r.src[1] or not r.dst[1]:
            return
        s = self.observable_id(*r.src)
        d = self.observable_id(*r.dst)
        if s == d:
            return
        self.conn.execute(
            """INSERT INTO observable_relations (src_id, rel, dst_id, source, attrs) VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT (src_id, rel, dst_id) DO UPDATE SET last_seen_at = now(),
                 attrs = observable_relations.attrs || EXCLUDED.attrs""",
            (s, r.rel, d, r.source, _json(r.attrs)))

    # ---------- ads ----------
    def upsert_ad(self, ad: AdDraft, source_id: int, shas: list[str]) -> int:
        if ad.library_id:
            key = f"{ad.platform}:{ad.library_id}"
        elif shas:
            key = f"shot:{shas[0]}"
        else:
            key = "text:" + sha256_bytes(f"{(ad.body or '').strip().lower()}|{ad.advertiser_name or ''}".encode())
        ad.dedupe_key = key
        adv_id = None
        if ad.advertiser_platform_id or ad.advertiser_name:
            if ad.advertiser_platform_id:
                adv_id = self.conn.execute(
                    """INSERT INTO advertisers (platform, platform_id, name) VALUES (%s,%s,%s)
                       ON CONFLICT (platform, platform_id) WHERE platform_id IS NOT NULL
                       DO UPDATE SET last_seen_at = now(), name = coalesce(EXCLUDED.name, advertisers.name)
                       RETURNING id""", (ad.platform, ad.advertiser_platform_id, ad.advertiser_name)).fetchone()[0]
            else:
                adv_id = self.conn.execute(
                    """INSERT INTO advertisers (platform, name) VALUES (%s,%s)
                       ON CONFLICT (platform, lower(name)) WHERE platform_id IS NULL
                       DO UPDATE SET last_seen_at = now() RETURNING id""", (ad.platform, ad.advertiser_name)).fetchone()[0]
        return self.conn.execute(
            """INSERT INTO ads (platform, library_id, dedupe_key, advertiser_id, body, title, display_link, cta, link_url,
                                delivery_start, delivery_stop, eu_total_reach, targeting, snapshot_url, source_id, raw)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (dedupe_key) DO UPDATE SET last_seen_at = now(),
                 body = coalesce(EXCLUDED.body, ads.body), eu_total_reach = coalesce(EXCLUDED.eu_total_reach, ads.eu_total_reach),
                 delivery_stop = coalesce(EXCLUDED.delivery_stop, ads.delivery_stop), raw = ads.raw || EXCLUDED.raw
               RETURNING id""",
            (ad.platform, ad.library_id, key, adv_id, ad.body, ad.title, ad.display_link, ad.cta, ad.link_url,
             ad.delivery_start, ad.delivery_stop, ad.eu_total_reach, _json(ad.targeting), ad.snapshot_url,
             source_id, _json(ad.raw))).fetchone()[0]

    # ---------- captures ----------
    def insert_capture(self, incident_id: int, c: CaptureDraft) -> int:
        cid = self.conn.execute(
            """INSERT INTO captures (incident_id, tool, tool_version, profile, user_agent, viewport, locale, timezone,
                   referer, entry_url, entry_url_norm, final_url, final_status, title, captured_at, page_role, cloak_verdict,
                   dom_sha256, text_sha256, text_simhash, dom_minhash, page_text, forms, outlinks, tls, meta, error)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (incident_id, c.tool, c.tool_version, c.profile, c.user_agent, c.viewport, c.locale, c.timezone,
             c.referer, c.entry_url, normalize_url(c.entry_url) if c.entry_url else None, c.final_url, c.final_status,
             _nul(c.title), c.captured_at, c.page_role, c.cloak_verdict, c.dom_sha256, c.text_sha256, c.text_simhash,
             c.dom_minhash, _nul(c.page_text), _json(c.forms), _json(c.outlinks), _json(c.tls) if c.tls else None,
             _json(c.meta), c.error)).fetchone()[0]
        if c.hops:
            with self.conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO capture_hops (capture_id, hop, url, host, status, kind, ip, at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    [(cid, i, h.url, _host(h.url), h.status, h.kind, h.ip, h.at) for i, h in enumerate(c.hops)])
        if c.requests:
            with self.conn.cursor() as cur, cur.copy(
                    "COPY capture_requests (capture_id, seq, captured_at, started_at, method, url, host, path_template, status,"
                    " mime, resource_type, server_ip, body_sha256, body_size, is_third_party, initiator) FROM STDIN") as cp:
                for r in c.requests:
                    cp.write_row((cid, r.seq, c.captured_at, r.started_at, r.method, r.url, r.host, r.path_template,
                                  r.status, r.mime, r.resource_type, r.server_ip, r.body_sha256, r.body_size,
                                  r.is_third_party, (r.initiator or "")[:500] or None))
        self._bump("captures")
        self._bump("requests", len(c.requests))
        return cid

    # ---------- re-captures ----------
    def find_incident_for_url(self, url: str) -> int | None:
        """The canonical incident whose landing was captured at the same normalized URL (re-capture target)."""
        row = self.conn.execute(
            """SELECT i.id FROM captures c JOIN incidents i ON i.id = c.incident_id
               WHERE c.entry_url_norm = %s AND i.duplicate_of IS NULL AND i.source_id <> %s
               ORDER BY i.id LIMIT 1""", (normalize_url(url), self.source_id("redpill_capture"))).fetchone()
        if row:
            return row[0]
        # landing URL learned from an ad snapshot → that ad's incident
        row = self.conn.execute(
            """SELECT i.id FROM ads a JOIN incidents i ON i.ad_id = a.id
               WHERE a.link_url = %s OR a.link_url = %s ORDER BY i.id LIMIT 1""", (url, url.rstrip("/"))).fetchone()
        return row[0] if row else None

    def add_capture(self, incident_id: int, cap: CaptureDraft, hits: list[ObsHit], rels: list[RelationDraft],
                    extractor: str = "capture@1") -> int:
        """Attach one more capture (re-capture, other profile) to an existing incident. Its postings use their own
        extractor tag, so re-ingesting the original incident (rules@1) does not wipe them."""
        shas = [(a, self.put_artifact(a)) for a in cap.artifacts]
        cid = self.insert_capture(incident_id, cap)
        for a, s in shas:
            self.ref_artifact(s, a, incident_id=incident_id, capture_id=cid)
        seen: set[tuple[str, str, str]] = set()
        for h in hits:
            f = "recapture." + h.field
            if not h.value or (h.type, h.value, f) in seen:
                continue
            seen.add((h.type, h.value, f))
            self.link(incident_id, ObsHit(h.type, h.value, f, h.display, h.confidence,
                                          {**h.context, "capture_id": cid}, extractor, h.noise_reason, h.attrs))
        for r in rels:
            self.relate(r)
        self.conn.execute(
            """UPDATE incidents SET needs_relink = true, feature_version = feature_version + 1,
                   kind = CASE WHEN kind = 'ad_only' THEN 'ad+landing' ELSE kind END,
                   primary_capture_id = coalesce(primary_capture_id, CASE WHEN %s = 'served' THEN %s END),
                   entry_etld1 = coalesce(entry_etld1, %s), final_etld1 = coalesce(final_etld1, %s)
               WHERE id = %s""",
            (cap.cloak_verdict, cid, etld1_of(cap.entry_url) if cap.entry_url.startswith("http") else None,
             etld1_of(cap.final_url) if (cap.final_url or "").startswith("http") else None, incident_id))
        self._bump("recaptures")
        return cid

    def mark_cloaking(self, since: datetime) -> int:
        """Victim profile vs bot profile of the same URL within an hour: different served content ⇒ cloaked.
        The bot-side capture gets cloak_verdict='cloaked'; both get a cloak_delta summary in meta."""
        cur = self.conn.execute(
            """WITH pairs AS (
                 SELECT v.id AS vid, b.id AS bid, v.title AS vt, b.title AS bt,
                        length(coalesce(v.page_text,'')) AS vl, length(coalesce(b.page_text,'')) AS bl,
                        (SELECT count(*) FROM capture_requests r WHERE r.capture_id = v.id) AS vr,
                        (SELECT count(*) FROM capture_requests r WHERE r.capture_id = b.id) AS br
                 FROM captures v JOIN captures b
                   ON b.entry_url = v.entry_url AND b.profile = 'plain_headless' AND v.profile <> 'plain_headless'
                  AND abs(extract(epoch FROM v.captured_at - b.captured_at)) < 3600
                 WHERE v.captured_at >= %s AND v.final_status BETWEEN 200 AND 299
                   AND v.text_sha256 IS DISTINCT FROM b.text_sha256)
               UPDATE captures c SET
                 cloak_verdict = CASE WHEN c.id = p.bid THEN 'cloaked' ELSE c.cloak_verdict END,
                 meta = c.meta || jsonb_build_object('cloak_delta', jsonb_build_object(
                     'victim_capture', p.vid, 'bot_capture', p.bid, 'victim_title', p.vt, 'bot_title', p.bt,
                     'victim_text_len', p.vl, 'bot_text_len', p.bl, 'victim_requests', p.vr, 'bot_requests', p.br))
               FROM pairs p WHERE c.id IN (p.vid, p.bid)""", (since,))
        return cur.rowcount

    # ---------- incidents ----------
    def ingest(self, inc: IncidentDraft, run_id: int | None = None) -> int:
        src = self.source_id(inc.source_key)
        # 1) blobs first (their hashes define the dedupe key)
        ad_shas = [(a, self.put_artifact(a)) for a in (inc.ad.artifacts if inc.ad else [])]
        cap_shas = [[(a, self.put_artifact(a)) for a in c.artifacts] for c in inc.captures]
        inc_shas = [(a, self.put_artifact(a)) for a in inc.artifacts]
        core = sorted({s for a, s in ad_shas + [x for cs in cap_shas for x in cs] if a.role in CORE_ROLES})
        allh = sorted({s for _, s in ad_shas + inc_shas + [x for cs in cap_shas for x in cs]})
        dedupe_key = sha256_bytes("|".join(core or allh).encode())

        ad_id = self.upsert_ad(inc.ad, src, [s for _, s in ad_shas]) if inc.ad else None

        entry_etld1 = etld1_of(inc.entry_url) if inc.entry_url else None
        web = [c for c in inc.captures if (c.final_url or c.entry_url or "").startswith(("http://", "https://"))]
        primary = next((c for c in web if c.cloak_verdict == "served"), web[0] if web else (inc.captures[0] if inc.captures else None))
        final_etld1 = etld1_of(primary.final_url) if primary and primary.final_url else None
        row = self.conn.execute(
            """INSERT INTO incidents (source_id, run_id, source_ref, kind, status, ad_id, entry_url, entry_etld1, final_etld1,
                   title, lang, headline, headline_template, narrative, vertical, observed_at, dedupe_key, quality,
                   sensitivity, raw)
               VALUES (%s,%s,%s,%s,'extracted',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (source_id, source_ref) DO UPDATE SET
                   run_id = EXCLUDED.run_id, kind = EXCLUDED.kind, status = 'extracted', ad_id = EXCLUDED.ad_id,
                   entry_url = EXCLUDED.entry_url, entry_etld1 = EXCLUDED.entry_etld1, final_etld1 = EXCLUDED.final_etld1,
                   title = EXCLUDED.title, lang = EXCLUDED.lang, headline = EXCLUDED.headline,
                   headline_template = EXCLUDED.headline_template, narrative = EXCLUDED.narrative,
                   vertical = EXCLUDED.vertical, observed_at = EXCLUDED.observed_at, dedupe_key = EXCLUDED.dedupe_key,
                   quality = EXCLUDED.quality, raw = EXCLUDED.raw, primary_capture_id = NULL,
                   feature_version = incidents.feature_version + 1, needs_relink = true
               RETURNING id, (xmax = 0)""",
            (src, run_id, inc.source_ref, inc.kind, ad_id, inc.entry_url, entry_etld1, final_etld1, inc.title, inc.lang,
             inc.headline, inc.headline_template, inc.narrative, inc.vertical, inc.observed_at, dedupe_key,
             _json(inc.quality), inc.sensitivity, _json(inc.to_contract()))).fetchone()
        iid, inserted = row
        if not inserted:  # re-ingest: replace derived children
            self.conn.execute("DELETE FROM captures WHERE incident_id = %s", (iid,))
            # only postings this extractor produced; enrichment (enrich.*) and manual ones survive re-ingest
            self.conn.execute("DELETE FROM incident_observables WHERE incident_id = %s AND extractor LIKE 'rules@%%'", (iid,))
            self.conn.execute("DELETE FROM artifact_refs WHERE incident_id = %s", (iid,))
            self._bump("reingested")
        else:
            self._bump("incidents")
        for a, s in inc_shas:
            self.ref_artifact(s, a, incident_id=iid)
        for a, s in ad_shas:
            self.ref_artifact(s, a, incident_id=iid, ad_id=ad_id)
        primary_id = None
        for c, shas in zip(inc.captures, cap_shas):
            cid = self.insert_capture(iid, c)
            if c is primary:
                primary_id = cid
            for a, s in shas:
                self.ref_artifact(s, a, incident_id=iid, capture_id=cid)
        if primary_id:
            self.conn.execute("UPDATE incidents SET primary_capture_id = %s WHERE id = %s", (primary_id, iid))

        seen: set[tuple[str, str, str]] = set()
        for h in inc.observables:
            if not h.value or (h.type, h.value, h.field) in seen:
                continue
            seen.add((h.type, h.value, h.field))
            self.link(iid, h)
        self._bump("observable_postings", len(seen))
        for r in inc.relations:
            self.relate(r)

        self.mark_duplicates(iid)
        return iid

    def mark_duplicates(self, iid: int) -> None:
        """L0 exact duplicate = this incident's core blobs (ad screenshot, HAR, saved/rendered page) are a subset
        of another incident's (p2 ⊂ p1 = p2 + organizer bundle). The richer / older one stays canonical."""
        roles = list(CORE_ROLES)
        q = """WITH mine AS (SELECT DISTINCT sha256 FROM artifact_refs WHERE incident_id = %(a)s AND role = ANY(%(roles)s)),
                    theirs AS (SELECT DISTINCT incident_id, sha256 FROM artifact_refs
                               WHERE incident_id <> %(a)s AND role = ANY(%(roles)s))
               SELECT t.incident_id,
                      count(*) AS shared,
                      (SELECT count(*) FROM mine) AS n_mine,
                      (SELECT count(DISTINCT sha256) FROM theirs t2 WHERE t2.incident_id = t.incident_id) AS n_theirs
               FROM theirs t JOIN mine USING (sha256)
               GROUP BY t.incident_id HAVING count(*) >= 2
               ORDER BY count(*) DESC, t.incident_id LIMIT 1"""
        r = self.conn.execute(q, {"a": iid, "roles": roles}).fetchone()
        self.conn.execute("UPDATE incidents SET duplicate_of = NULL WHERE id = %s", (iid,))
        if not r:
            return
        other, shared, n_mine, n_theirs = r
        if shared == n_mine and (n_mine < n_theirs or other < iid):
            self.conn.execute("UPDATE incidents SET duplicate_of = %s WHERE id = %s", (other, iid))
            self._bump("duplicates")
        elif shared == n_theirs:
            self.conn.execute("UPDATE incidents SET duplicate_of = %s WHERE id = %s AND duplicate_of IS NULL", (iid, other))
            self._bump("duplicates")


def _host(url: str) -> str:
    from ..util.urls import host_of
    return host_of(url)


def _lexical(sld: str | None) -> dict:
    import math
    s = sld or ""
    if not s:
        return {}
    counts = {c: s.count(c) for c in set(s)}
    ent = -sum(n / len(s) * math.log2(n / len(s)) for n in counts.values())
    vowels = sum(c in "aeiouy" for c in s)
    return {"len": len(s), "digits": sum(c.isdigit() for c in s), "hyphens": s.count("-"),
            "entropy": round(ent, 3), "vowel_ratio": round(vowels / len(s), 3)}


def _cert_time(s: str | None) -> datetime | None:
    if not s:
        return None
    from datetime import timezone
    for fmt in ("%b %d %H:%M:%S %Y %Z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(s.replace("  ", " "), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
