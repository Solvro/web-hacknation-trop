"""Seed loader: migrations → sample_v1 → labels → ad transcriptions → rarity stats → summary.

    python db/seed_sample.py                     # default: data/raw/sample_v1, compose DB on :55432
    python db/seed_sample.py --path data/raw/sample_v1 --db postgresql://…

Labels: experiments/labels.yaml (verified ground truth from the experiments session) when present,
otherwise the rough PLAN §2 grouping. Ad fields: experiments/ad_truth.yaml (manual transcription of the
ad screenshots: advertiser, library id, caption, CTA, display link) when present.
Artifacts go to ARTIFACT_STORE (default data/artifacts, git-ignored). Nothing here talks to the network.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from psycopg.types.json import Jsonb  # noqa: E402

from scrapers.store.db import connect  # noqa: E402

ROUGH_LABELS = {  # PLAN §2, used only when experiments/labels.yaml is absent
    "A": (["p1", "p2", "p3", "p4", "p7", "p15"], "F-kitA"), "A-health": (["p11"], "F-kitA"),
    "B": (["p5", "p6", "p9", "p10", "p12", "p13", "p14"], None), "C": (["p8"], None),
}


def load_yaml(p: Path):
    try:
        import yaml
    except ImportError:
        print("pyyaml not installed; skipping", p)
        return None
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.is_file() else None


def seed_labels(conn, labels_path: Path) -> str:
    gt = load_yaml(labels_path)
    if gt and gt.get("incidents"):
        ls = conn.execute(
            """INSERT INTO label_sets (key, kind, description) VALUES ('sample_v1_gt', 'ground_truth', %s)
               ON CONFLICT (key) DO UPDATE SET description = EXCLUDED.description RETURNING id""",
            (f"Verified labels from {labels_path.relative_to(ROOT).as_posix()} (experiments session)",)).fetchone()[0]
        for p, lab in gt["incidents"].items():
            conn.execute(
                """INSERT INTO labels (label_set_id, incident_id, campaign_key, variant_key, family_key, duplicate_of_ref,
                                      confidence, created_by)
                   SELECT %s, id, %s, %s, %s, %s, 1.0, 'experiments/labels.yaml' FROM incidents WHERE source_ref = %s
                   ON CONFLICT (label_set_id, incident_id) DO UPDATE SET campaign_key = EXCLUDED.campaign_key,
                     variant_key = EXCLUDED.variant_key, family_key = EXCLUDED.family_key,
                     duplicate_of_ref = EXCLUDED.duplicate_of_ref""",
                (ls, lab.get("campaign"), lab.get("variant"), lab.get("operator"),
                 f"sample_v1/{lab['dup_of']}" if lab.get("dup_of") else None, f"sample_v1/{p}"))
        # pairwise must/cannot-link constraints at campaign level (for M1 training / eval)
        conn.execute("DELETE FROM pair_labels WHERE label_set_id = %s", (ls,))
        conn.execute(
            """INSERT INTO pair_labels (label_set_id, a_id, b_id, same, source, created_by)
               SELECT %s, a.incident_id, b.incident_id, a.campaign_key = b.campaign_key, 'labels.yaml', 'seed'
               FROM labels a JOIN labels b ON a.label_set_id = b.label_set_id AND a.incident_id < b.incident_id
               WHERE a.label_set_id = %s""", (ls, ls))
        return "sample_v1_gt"
    ls = conn.execute("SELECT id FROM label_sets WHERE key = 'sample_v1_manual'").fetchone()[0]
    for camp, (folders, fam) in ROUGH_LABELS.items():
        for f in folders:
            conn.execute(
                """INSERT INTO labels (label_set_id, incident_id, campaign_key, family_key, confidence, created_by)
                   SELECT %s, id, %s, %s, 0.6, 'PLAN.md §2 (rough)' FROM incidents WHERE source_ref = %s
                   ON CONFLICT (label_set_id, incident_id) DO NOTHING""", (ls, camp, fam, f"sample_v1/{f}"))
    return "sample_v1_manual"


def seed_ads(conn, ad_truth_path: Path) -> int:
    """Fill the ads layer from the manual screenshot transcription (stand-in for OCR/VLM until those run)."""
    truth = load_yaml(ad_truth_path)
    if not truth:
        return 0
    n = 0
    for p, a in truth.items():
        row = conn.execute("SELECT id, ad_id FROM incidents WHERE source_ref = %s", (f"sample_v1/{p}",)).fetchone()
        if not row or not row[1]:
            continue
        iid, ad_id = row
        adv = a.get("advertiser")
        adv_id = None
        if adv:
            adv_id = conn.execute(
                """INSERT INTO advertisers (platform, name) VALUES ('meta', %s)
                   ON CONFLICT (platform, lower(name)) WHERE platform_id IS NULL DO UPDATE SET last_seen_at = now()
                   RETURNING id""", (adv,)).fetchone()[0]
        lib = str(a["library_id"]) if a.get("library_id") else None
        clash = conn.execute("SELECT id FROM ads WHERE platform = 'meta' AND library_id = %s AND id <> %s", (lib, ad_id)).fetchone() if lib else None
        conn.execute(
            """UPDATE ads SET advertiser_id = %s, library_id = coalesce(%s, library_id), body = %s, cta = %s,
                   display_link = %s, creative_is_decoy = %s, raw = raw || %s WHERE id = %s""",
            (adv_id, None if clash else lib, a.get("caption") or None, a.get("cta"), a.get("display_link"),
             a.get("decoy"), Jsonb({"transcription": a}), ad_id))
        obs = []
        if adv:
            obs.append(("advertiser_name", adv.lower(), adv))
        if a.get("display_link"):
            obs.append(("ad_display_link", a["display_link"].lower(), a["display_link"]))
        if a.get("caption"):
            import re
            tpl = re.sub(r"\d+", "{NUM}", a["caption"].strip())
            obs.append(("clickbait_template", tpl, a["caption"]))
        for person in a.get("persons") or []:
            obs.append(("person", person.title(), person.title()))
        for typ, val, disp in obs:
            oid = conn.execute(
                """INSERT INTO observables (type, value, display) VALUES (%s, %s, %s)
                   ON CONFLICT (type, md5(value)) DO UPDATE SET last_seen_at = now() RETURNING id""",
                (typ, val, disp)).fetchone()[0]
            conn.execute(
                """INSERT INTO incident_observables (incident_id, observable_id, field, extractor, confidence, context)
                   VALUES (%s, %s, 'ad.transcription', 'manual@experiments', 0.9, '{}')
                   ON CONFLICT DO NOTHING""", (iid, oid))
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=str(ROOT / "data" / "raw" / "sample_v1"))
    ap.add_argument("--labels", default=str(ROOT / "experiments" / "labels.yaml"))
    ap.add_argument("--ad-truth", default=str(ROOT / "experiments" / "ad_truth.yaml"))
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    py = sys.executable
    db_args = ["--url", args.db] if args.db else []
    subprocess.run([py, str(ROOT / "db" / "migrate.py"), *db_args], check=True)
    ingest_args = ["--db", args.db] if args.db else []
    subprocess.run([py, "-m", "scrapers.ingest", args.path, "--source", "sample_v1", *ingest_args], check=False, cwd=ROOT)

    with connect(args.db) as conn:
        label_key = seed_labels(conn, Path(args.labels))
        n_ads = seed_ads(conn, Path(args.ad_truth))
        conn.execute("SELECT refresh_observable_stats()")
        conn.commit()
        print(f"\nlabels: {label_key}; ads filled from transcription: {n_ads}")
        print("\n== incidents")
        for r in conn.execute(
                """SELECT i.id, i.source_ref, i.kind, coalesce(i.final_etld1, i.entry_etld1), i.narrative,
                          d.source_ref AS dup_of, l.campaign_key, l.family_key,
                          (SELECT count(DISTINCT observable_id) FROM incident_observables io WHERE io.incident_id = i.id)
                   FROM incidents i LEFT JOIN incidents d ON d.id = i.duplicate_of
                   LEFT JOIN labels l ON l.incident_id = i.id
                        AND l.label_set_id = (SELECT id FROM label_sets WHERE key = %s)
                   ORDER BY i.id""", (label_key,)):
            print(f"  {r[0]:>3} {r[1]:<16} {r[2]:<12} {str(r[3]):<26} {str(r[4]):<17} dup_of={str(r[5]):<14} "
                  f"label={r[6]}/{r[7]} obs={r[8]}")
        print("\n== shared high-strength values (df >= 2, not noise, excluding asset hashes)")
        for r in conn.execute(
                """SELECT o.type, left(coalesce(o.display, o.value), 70), o.df_incidents,
                          string_agg(DISTINCT split_part(i.source_ref, '/', 2), ',' ORDER BY split_part(i.source_ref, '/', 2))
                   FROM observables o JOIN observable_types t ON t.type = o.type
                   JOIN incident_observables io ON io.observable_id = o.id JOIN incidents i ON i.id = io.incident_id
                   WHERE NOT o.noise AND t.strength = 'H' AND o.df_incidents >= 2 AND o.type <> 'asset_sha256'
                   GROUP BY o.id, o.type ORDER BY o.type, o.df_incidents DESC LIMIT 60"""):
            print(f"  {r[0]:<18} df={r[2]:<3} {r[1]:<72} [{r[3]}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
