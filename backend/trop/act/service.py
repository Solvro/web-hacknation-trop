"""Act service: one takedown package per campaign (DSA Art. 16 + CERT PL + STIX 2.1/MISP + rules).

    create_package(body: ActPackageCreate, *, use_llm=True) -> ActPackage
    build_package(body | dict) -> dict                      # alias used by WS2's arq task placeholder
    get_package(pid) -> ActPackage · list_packages(campaign_id=None, status=None) -> list[ActPackage]
    update_notice(pid, text) -> ActPackage                  # the notice text is editable (board 7)
    download(pid, format) -> (bytes, mime, filename)        # format: pdf | json | stix | misp | csv | certpl
    submit(pid, emit=None) -> ActPackage                    # NEVER sends: marks "sent" = prepared + exported + logged
    rules(campaign_id) -> list[Rule] · test_rule(kind, body, campaign_id=None) -> RuleTest

Storage: data/act/<ACT-n>/{package.json, dossier.json, certpl.json, rules.json, export/…}; data/act/submissions.jsonl.
"""
from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trop.config import settings
from trop.schema import ActPackage, ActPackageCreate, Rule, RuleTest

from . import rules as _rules
from .campaign import load_campaign
from .notice import GOOD_FAITH, LEGAL_BASIS, REPORTER, certpl_text, draft_notice
from .pdf import render_dsa_pdf
from .stix import dumps, indicators_csv, misp_event, stix_bundle

DISCLAIMER = "Nic nie zostało wysłane — pakiet przygotowany i wyeksportowany."
MIME = {"pdf": "application/pdf", "json": "application/json", "stix": "application/stix+json", "misp": "application/json",
        "csv": "text/csv; charset=utf-8", "certpl": "text/plain; charset=utf-8"}
EXT = {"pdf": "pdf", "json": "json", "stix": "stix.json", "misp": "misp.json", "csv": "csv", "certpl": "certpl.txt"}
RECIPIENTS = {"meta_dsa": "Meta · zgłoszenie DSA art. 16", "certpl": "CERT PL · lista ostrzeżeń",
              "google": "Google Safe Browsing", "registrar": "Rejestrator · abuse"}
_LOCK = threading.Lock()


def root() -> Path:
    p = Path(settings.data_dir) / "act"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _dir(pid: str) -> Path:
    if not pid or "/" in pid or ".." in pid:
        raise ValueError("bad package id")
    return root() / pid


def _new_id() -> str:
    with _LOCK:
        ns = [int(p.name.split("-")[1]) for p in root().glob("ACT-*") if p.name.split("-")[1].isdigit()]
        pid = f"ACT-{max(ns + [99]) + 1}"
        _dir(pid).mkdir(parents=True)
        return pid


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _certpl_domains(d: dict, check: Callable[[str], dict] | None) -> list[dict]:
    """Domains not yet on the CERT PL warning list (live check via WS5's cached list; dossier flag as fallback)."""
    out = []
    for x in d["domains"]:
        listed = x.get("on_certpl")
        if check and not d.get("fictional"):
            try:
                r = check(x["fqdn"])
                if r.get("listed") is not None:
                    listed = bool(r["listed"])
            except Exception:  # noqa: BLE001
                pass
        x["on_certpl"] = bool(listed)
        if not listed:
            out.append({"fqdn": x["fqdn"], "registered_at": x.get("registered_at"), "cert_issued_at": x.get("cert_issued_at"),
                        "source": x.get("source"), "urls": x.get("urls", [])[:2],
                        "evidence": [e["display"] for e in d["evidence"][:4]] + list(x.get("evidence") or [])})
    return out


def create_package(body: ActPackageCreate | dict, *, use_llm: bool = True,
                   certpl_check: Callable[[str], dict] | None = None, dossier: dict | None = None) -> ActPackage:
    b = body if isinstance(body, ActPackageCreate) else ActPackageCreate.model_validate(body)
    d = dossier or load_campaign(b.campaign_id)
    if certpl_check is None and not d.get("fictional"):
        try:
            from trop.enrich.tools import certpl_check as certpl_check
        except Exception:  # noqa: BLE001
            certpl_check = None
    unlisted = _certpl_domains(d, certpl_check)
    pid = _new_id()
    text, meta = draft_notice(d, use_llm=use_llm)
    c = d["counts"]
    totals = {"meta_dsa": c["ads"] or c["incidents"], "certpl": len(unlisted), "google": c["domains"], "registrar": c["domains"]}
    recips = [{"id": r, "label": RECIPIENTS[r], "enabled": r in b.recipients, "progress": {"done": 0, "total": totals[r]},
               "status": "ready" if r in b.recipients else "off"} for r in RECIPIENTS]
    parts = [
        {"key": "ads", "label": f"{c['ads']} reklam z linkami do Ad Library", "bot": "zwiadowca", "ready": True, "count": c["ads"]},
        {"key": "advertisers", "label": f"{c['advertisers']} kont reklamodawców", "bot": "archiwista", "ready": True,
         "count": c["advertisers"]},
        {"key": "domains", "label": f"{c['domains']} domen z certyfikatami i datami"
         + (f", w tym {sum(1 for x in d['domains'] if x.get('source') == 'investigation')} ze śledztwa"
            if any(x.get("source") == "investigation" for x in d["domains"]) else ""), "bot": "notariusz", "ready": True,
         "count": c["domains"]},
        {"key": "evidence", "label": "Ślady, które łączą reklamy", "bot": "tropiciel", "ready": True, "count": c["evidence_items"]},
        {"key": "notice", "label": "Uzasadnienie i plik STIX 2.1 dla CERT PL", "bot": "sedzia", "ready": True},
        {"key": "rules", "label": "Reguły wykrywania (urlscan, URL, HTML)", "bot": "tropiciel", "ready": True},
    ]
    pkg = ActPackage(id=pid, kind=b.kind, campaign_id=d["id"], status="ready",
                     contents={"ads": c["ads"], "advertisers": c["advertisers"], "domains": c["domains"],
                               "evidence_items": c["evidence_items"], "certpl_new": len(unlisted)},
                     recipients=recips, parts=parts, notice_text=text, formats=["pdf", "json", "stix", "misp", "csv"],
                     created_at=_now(), disclaimer=DISCLAIMER)
    rl = _rules.rules_for(d)
    tests = {r.id: _rules.test_rule(r.kind, r.body, dossier=d).model_dump() for r in rl}
    dd = _dir(pid)
    (dd / "dossier.json").write_text(json.dumps(d, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (dd / "certpl.json").write_text(json.dumps(unlisted, ensure_ascii=False, indent=1), encoding="utf-8")
    (dd / "rules.json").write_text(json.dumps({"rules": [r.model_dump() for r in rl], "tests": tests}, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    (dd / "notice_meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    _save(pkg)
    return pkg


def build_package(body: ActPackageCreate | dict, **kw: Any) -> dict:
    return create_package(body, **kw).model_dump()


def _save(pkg: ActPackage) -> None:
    (_dir(pkg.id) / "package.json").write_text(pkg.model_dump_json(indent=1), encoding="utf-8")


def get_package(pid: str) -> ActPackage:
    p = _dir(pid) / "package.json"
    if not p.is_file():
        raise FileNotFoundError(pid)
    return ActPackage.model_validate_json(p.read_text(encoding="utf-8"))


get = get_package


def list_packages(campaign_id: str | None = None, status: str | None = None) -> list[ActPackage]:
    out = []
    for p in sorted(root().glob("ACT-*/package.json"), key=lambda p: int(p.parent.name.split("-")[1])):
        pkg = ActPackage.model_validate_json(p.read_text(encoding="utf-8"))
        if (not campaign_id or pkg.campaign_id == campaign_id) and (not status or pkg.status == status):
            out.append(pkg)
    return out


def update_notice(pid: str, text: str) -> ActPackage:
    pkg = get_package(pid)
    pkg.notice_text = text
    if pkg.status == "sent":
        pkg.status = "ready"       # edited after export: needs a new export
    _save(pkg)
    return pkg


def _dossier(pid: str) -> dict:
    return json.loads((_dir(pid) / "dossier.json").read_text(encoding="utf-8"))


def package_json(pkg: ActPackage, d: dict) -> dict:
    """Machine-readable notice: Art. 16(2) a–d + every ad, advertiser, domain and evidence item."""
    unl = json.loads((_dir(pkg.id) / "certpl.json").read_text(encoding="utf-8"))
    rl = json.loads((_dir(pkg.id) / "rules.json").read_text(encoding="utf-8"))
    return {
        "package": pkg.model_dump(), "fictional": bool(d.get("fictional")),
        "campaign": {k: d.get(k) for k in ("id", "name", "narrative", "vertical", "operator_id", "persons", "brands", "counts")},
        "dsa_art16": {"explanation": pkg.notice_text, "legal_basis": LEGAL_BASIS,
                      "locations": [a.get("library_url") or a.get("landing_url") for a in d["ads"]] + [u for x in d["domains"] for u in x.get("urls", [])[:1]],
                      "notifier": REPORTER, "good_faith_statement": GOOD_FAITH},
        "ads": d["ads"], "advertisers": d["advertisers"], "domains": d["domains"], "evidence": d["evidence"],
        "certpl": {"domains_not_listed": unl, "draft": certpl_text(d, unl)}, "rules": rl,
        "disclaimer": pkg.disclaimer,
    }


def download(pid: str, format: str = "pdf") -> tuple[bytes, str, str]:
    fmt = format.lower()
    if fmt not in MIME:
        raise ValueError(f"format must be one of {sorted(MIME)}")
    pkg, d = get_package(pid), _dossier(pid)
    if fmt == "pdf":
        data = render_dsa_pdf(pkg.model_dump(), d, pkg.notice_text)
    elif fmt == "json":
        data = dumps(package_json(pkg, d))
    elif fmt == "stix":
        data = dumps(stix_bundle(pkg.model_dump(), d))
    elif fmt == "misp":
        data = dumps(misp_event(pkg.model_dump(), d))
    elif fmt == "csv":
        data = indicators_csv(d).encode("utf-8")
    else:
        unl = json.loads((_dir(pid) / "certpl.json").read_text(encoding="utf-8"))
        data = certpl_text(d, unl).encode("utf-8")
    return data, MIME[fmt], f"{pkg.id}_{pkg.campaign_id}.{EXT[fmt]}"


def submit(pid: str, emit: Callable[[str, dict], None] | None = None) -> ActPackage:
    """Mark the package 'sent' = prepared + exported + logged. NOTHING leaves the machine."""
    pkg = get_package(pid)
    exp = _dir(pid) / "export"
    exp.mkdir(exist_ok=True)
    files = []
    for fmt in ("pdf", "json", "stix", "misp", "csv", "certpl"):
        data, _, name = download(pid, fmt)
        (exp / name).write_bytes(data)
        files.append(name)
    pkg.status = "sent"
    pkg.sent_at = _now()
    pkg.disclaimer = DISCLAIMER
    for r in pkg.recipients:
        if r.get("enabled"):
            r["status"] = "prepared"
    _save(pkg)
    with (root() / "submissions.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": pkg.sent_at, "package_id": pid, "campaign_id": pkg.campaign_id, "kind": pkg.kind,
                            "recipients": [r["id"] for r in pkg.recipients if r.get("enabled")], "files": files,
                            "sent_externally": False, "note": DISCLAIMER}, ensure_ascii=False) + "\n")
    if emit:
        emit("act.submitted", {"package_id": pid, "kind": pkg.kind, "campaign_id": pkg.campaign_id})
    return pkg


def rules(campaign_id: str) -> list[Rule]:
    return _rules.rules_for(load_campaign(campaign_id))


def test_rule(kind: str, body: str, campaign_id: str | None = None) -> RuleTest:
    return _rules.test_rule(kind, body, campaign_id)
