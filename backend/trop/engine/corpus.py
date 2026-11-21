"""The known corpus: labelled/attributed incidents + their campaign / operator / operation assignments.

    corpus = Corpus.load()                    # JSON corpus (data/corpus/known.json), built on first use
    corpus = Corpus.load(source="db")         # Postgres (trop.store), when available

Built from the organizer's labelled sample_v1 (RESULTS: 9 campaigns, 7 operators). Label letters are mapped to product
ids at build time (campaign A -> KMP-001, operator OP1 -> OP-01, operation -> OPN-01, in label-file order); the
mapping lives in the corpus file under DATA_DIR, never in the repo.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from trop.config import settings

log = logging.getLogger(__name__)
CORPUS_VERSION = 1


def corpus_path() -> Path:
    return Path(os.environ.get("TROP_CORPUS") or (Path(os.environ.get("DATA_DIR") or settings.data_dir) / "corpus" / "known.json"))


@dataclass
class Corpus:
    incidents: list[dict] = field(default_factory=list)
    campaign_of: dict[str, str] = field(default_factory=dict)      # incident -> KMP-…
    operator_of: dict[str, str] = field(default_factory=dict)      # incident -> OP-…
    operation_of: dict[str, str] = field(default_factory=dict)     # incident -> OPN-…
    variant_of: dict[str, str] = field(default_factory=dict)
    campaigns: dict[str, dict] = field(default_factory=dict)       # KMP -> {name, vertical, operator_id, operation_id, label}
    operators: dict[str, dict] = field(default_factory=dict)
    operations: dict[str, dict] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    # ------------------------------------------------------------------------------------------ access
    @property
    def ids(self) -> list[str]:
        return [i["id"] for i in self.incidents]

    def get(self, iid: str) -> dict | None:
        return next((i for i in self.incidents if i["id"] == iid), None)

    def members(self, campaign_id: str) -> list[dict]:
        return [i for i in self.incidents if self.campaign_of.get(i["id"]) == campaign_id]

    def next_campaign_id(self) -> str:
        nums = [int(c.split("-")[1]) for c in self.campaigns if c.startswith("KMP-") and c.split("-")[1].isdigit()]
        return f"KMP-{(max(nums) + 1 if nums else 1):03d}"

    def add(self, inc: dict, campaign_id: str | None, operator_id: str | None = None, operation_id: str | None = None,
            campaign_meta: dict | None = None) -> str:
        """Add an attributed incident (incremental mode). A None campaign creates a new one."""
        cid = campaign_id or self.next_campaign_id()
        if cid not in self.campaigns:
            self.campaigns[cid] = {"name": (campaign_meta or {}).get("name") or f"Nowa kampania {cid}",
                                   "operator_id": operator_id, "operation_id": operation_id, "status": "candidate"}
        self.incidents = [i for i in self.incidents if i["id"] != inc["id"]] + [inc]
        self.campaign_of[inc["id"]] = cid
        if operator_id or self.campaigns[cid].get("operator_id"):
            self.operator_of[inc["id"]] = operator_id or self.campaigns[cid]["operator_id"]
        if operation_id or self.campaigns[cid].get("operation_id"):
            self.operation_of[inc["id"]] = operation_id or self.campaigns[cid]["operation_id"]
        return cid

    def copy(self) -> "Corpus":
        import copy
        return Corpus(list(self.incidents), dict(self.campaign_of), dict(self.operator_of), dict(self.operation_of),
                      dict(self.variant_of), copy.deepcopy(self.campaigns), copy.deepcopy(self.operators),
                      copy.deepcopy(self.operations), dict(self.meta))

    # ------------------------------------------------------------------------------------------ io
    def to_json(self) -> dict:
        strip = [{k: v for k, v in i.items() if not k.startswith("_")} for i in self.incidents]
        return {"version": CORPUS_VERSION, "meta": self.meta, "incidents": strip, "campaign_of": self.campaign_of,
                "operator_of": self.operator_of, "operation_of": self.operation_of, "variant_of": self.variant_of,
                "campaigns": self.campaigns, "operators": self.operators, "operations": self.operations}

    @classmethod
    def from_json(cls, d: dict) -> "Corpus":
        return cls(d["incidents"], d["campaign_of"], d.get("operator_of", {}), d.get("operation_of", {}),
                   d.get("variant_of", {}), d.get("campaigns", {}), d.get("operators", {}), d.get("operations", {}),
                   d.get("meta", {}))

    def save(self, path: Path | None = None) -> Path:
        p = Path(path or corpus_path())
        p.parent.mkdir(parents=True, exist_ok=True)
        json.dump(self.to_json(), open(p, "w", encoding="utf-8"), ensure_ascii=False, default=list)
        return p

    @classmethod
    def load(cls, path: str | Path | None = None, *, source: str = "json", rebuild: bool = False,
             include_dane: bool = False) -> "Corpus":
        if source == "db":
            try:
                from trop.store import corpus as store_corpus  # type: ignore
                return store_corpus.load_corpus()
            except Exception as e:  # noqa: BLE001
                log.warning("DB corpus unavailable (%s); falling back to JSON", e)
        p = Path(path or corpus_path())
        if include_dane and path is None:
            p = p.with_name("known_with_dane.json")
        if p.exists() and not rebuild:
            d = json.load(open(p, encoding="utf-8"))
            if d.get("version") == CORPUS_VERSION:
                return cls.from_json(d)
        c = build_from_labels(include_dane=include_dane)
        try:
            c.save(p)
        except OSError as e:
            log.warning("could not cache corpus at %s: %s", p, e)
        return c

    @classmethod
    def empty(cls) -> "Corpus":
        return cls()


def _known_incidents(corpus: str, live: bool = False) -> list[dict]:
    """Re-extract from the raw folders; when they are absent fall back to the experiments' precomputed
    incidents_q36.json (VLM qwen36 ad fields) + face-gallery identities."""
    from trop.eval import data
    from trop.extract.cache import _exp_file
    from trop.extract.layers import face_hits_to_faces
    if data.raw_dir(corpus).exists():
        return data.extract_corpus(corpus, phash="compute", faces="gallery", live=live)
    log.warning("raw %s absent: building the corpus from precomputed incidents_q36.json", corpus)
    incs = data.load_precomputed(corpus, "incidents_q36.json")
    hits = (_exp_file("joint", "faces_gallery_id.json").get("hits") or {})
    for inc in incs:
        inc.setdefault("media", {})["faces"] = face_hits_to_faces(hits.get(inc["id"]) or [])
        inc.setdefault("quality", {}).setdefault("provenance", {})["source"] = "precomputed incidents_q36.json"
    return incs


def build_from_labels(include_dane: bool = False, incidents: list[dict] | None = None, live: bool = False) -> Corpus:
    """Re-extract sample_v1 (+ optionally DANE) with the product pipeline and attach the hand labels."""
    from trop.eval import data
    t0 = time.time()
    lab = data.load_yaml("labels.yaml")
    S = incidents if incidents is not None else _known_incidents("sample_v1", live)
    inc_lab = dict(lab["incidents"])
    ops_of_inc: dict[str, str] = {}
    if include_dane or (data.labels_path("labels_dane.yaml") is not None):
        try:
            LD = data.load_yaml("labels_dane.yaml")
            ops_of_inc.update(LD.get("sample_operations") or {})
        except FileNotFoundError:
            LD = None
    else:
        LD = None
    if include_dane and LD and incidents is None:
        D = _known_incidents("dane", live)
        for k, v in LD["incidents"].items():
            if v.get("campaign") not in (None, "UNK"):
                inc_lab[k] = v
                ops_of_inc[k] = v.get("operation") or v.get("operator")
        S = S + [x for x in D if x["id"] in inc_lab]
    letters = list((lab.get("campaigns") or {}).keys())
    for v in inc_lab.values():
        if v["campaign"] not in letters:
            letters.append(v["campaign"])
    cmap = {c: f"KMP-{i + 1:03d}" for i, c in enumerate(letters)}
    op_letters = list((lab.get("operators") or {}).keys())
    for v in inc_lab.values():
        if v.get("operator") and v["operator"] not in op_letters:
            op_letters.append(v["operator"])
    omap = {o: f"OP-{i + 1:02d}" for i, o in enumerate(op_letters)}
    opn_letters: list[str] = []
    for k in [i["id"] for i in S]:
        o = ops_of_inc.get(k) or inc_lab[k].get("operator")
        if o and o not in opn_letters:
            opn_letters.append(o)
    nmap = {o: f"OPN-{i + 1:02d}" for i, o in enumerate(opn_letters)}

    c = Corpus(meta={"built_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "source": "labels.yaml" + (" + labels_dane.yaml" if include_dane else ""),
                     "n": len(S), "build_s": round(time.time() - t0, 1), "label_map": {"campaign": cmap, "operator": omap, "operation": nmap}})
    for inc in S:
        L = inc_lab[inc["id"]]
        cid, oid = cmap[L["campaign"]], omap.get(L.get("operator"))
        nid = nmap.get(ops_of_inc.get(inc["id"]) or L.get("operator"))
        c.incidents.append(inc)
        c.campaign_of[inc["id"]] = cid
        if oid:
            c.operator_of[inc["id"]] = oid
        if nid:
            c.operation_of[inc["id"]] = nid
        if L.get("variant"):
            c.variant_of[inc["id"]] = f"{cid}/{L['variant']}"
    camp_meta = lab.get("campaigns") or {}
    camp_meta_d = (LD or {}).get("campaigns") or {}
    for letter, cid in cmap.items():
        m = camp_meta.get(letter) or camp_meta_d.get(letter) or {}
        mem = [i for i, x in c.campaign_of.items() if x == cid]
        if not mem:
            continue
        c.campaigns[cid] = {"name": m.get("name") or cid, "vertical": m.get("vertical"), "label": letter,
                            "operator_id": c.operator_of.get(mem[0]), "operation_id": c.operation_of.get(mem[0]),
                            "status": "active"}
    for letter, oid in omap.items():
        mem = [i for i, x in c.operator_of.items() if x == oid]
        if mem:
            c.operators[oid] = {"label": letter, "campaigns": sorted({c.campaign_of[i] for i in mem})}
    for letter, nid in nmap.items():
        mem = [i for i, x in c.operation_of.items() if x == nid]
        if mem:
            c.operations[nid] = {"label": letter, "campaigns": sorted({c.campaign_of[i] for i in mem}),
                                 "operators": sorted({c.operator_of[i] for i in mem if i in c.operator_of})}
    return c
