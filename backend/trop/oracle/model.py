"""Domain DNA model: char n-gram logistic regression on the label + TLD/structure features, then metadata evidence
(NS pair, registrar, cert issuer) that only exists once the domain has been resolved/RDAP'ed (stage 2)."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from trop.enrich.util import etld1, tld
from trop.schema import DomainDNA

VOWELS = set("aeiouy")


def split_domain(domain: str) -> tuple[str, str]:
    e = etld1(domain)
    t = tld(domain)
    return (e[: -(len(t) + 1)] if t and e.endswith("." + t) else e), t


def _struct(sld: str, t: str) -> dict[str, float]:
    letters = [c for c in sld if c.isalpha()]
    vr = sum(c in VOWELS for c in letters) / max(1, len(letters))
    f = {f"tld={t}": 1.0, "len": len(sld) / 20.0, "hyph": float(sld.count("-")), "digit": sum(c.isdigit() for c in sld) / max(1, len(sld)),
         "vowel": vr, "app_suffix": float(bool(re.search(r"-(app|apps|platform|ai|pro)$", sld)))}
    f["cv_alt"] = sum(1 for a, b in zip(sld, sld[1:]) if a.isalpha() and b.isalpha() and ((a in VOWELS) != (b in VOWELS))) / max(1, len(sld) - 1)
    return f


class DomainModel:
    def __init__(self, C: float = 3.0):
        self.tf = TfidfVectorizer(analyzer="char", ngram_range=(2, 4), sublinear_tf=True, min_df=2, lowercase=True)
        self.dv = DictVectorizer()
        self.lr = LogisticRegression(C=C, class_weight="balanced", max_iter=2000)
        self.fitted = False

    def _X(self, doms: list[str], fit: bool = False):
        parts = [split_domain(d) for d in doms]
        txt = [f"^{s}$" for s, _ in parts]
        st = [_struct(s, t) for s, t in parts]
        if fit:
            return sp.hstack([self.tf.fit_transform(txt), self.dv.fit_transform(st)]).tocsr()
        return sp.hstack([self.tf.transform(txt), self.dv.transform(st)]).tocsr()

    def fit(self, pos: list[str], neg: list[str]) -> "DomainModel":
        X = self._X(pos + neg, fit=True)
        y = np.array([1] * len(pos) + [0] * len(neg))
        self.lr.fit(X, y)
        self.fitted = True
        return self

    def p_lex(self, doms: list[str]) -> np.ndarray:
        if not doms:
            return np.zeros(0)
        return self.lr.predict_proba(self._X(doms))[:, 1]

    def explain(self, domain: str, top: int = 4) -> list[str]:
        """Top n-gram contributions pushing the score up."""
        X = self._X([domain])
        names = list(self.tf.get_feature_names_out()) + list(self.dv.get_feature_names_out())
        contrib = X.multiply(self.lr.coef_[0]).tocoo()
        best = sorted(zip(contrib.col, contrib.data), key=lambda x: -x[1])[:top]
        return [f"{names[c]} ({v:+.2f})" for c, v in best if v > 0.05]


def logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def meta_bonus(dna: DomainDNA, enrich: dict | None, issuer: str | None = None) -> tuple[float, list[str]]:
    """Stage-2 log-odds bonus from metadata: NS pair, registrar, cert issuer, ASN (only when enrichment is available)."""
    b, why = 0.0, []
    e = enrich or {}
    ns_pairs = set(dna.model.get("ns_pairs", []))
    if e.get("ns") and "|".join(e["ns"]) in ns_pairs:
        b += 2.0
        why.append(f"NS pair {'|'.join(e['ns'][:2])} seen in campaign")
    elif e.get("ns") and set(e["ns"]) & {n for p in ns_pairs for n in p.split("|")}:
        b += 0.8
        why.append("shares a nameserver with the campaign")
    from trop.enrich.util import norm_registrar
    regs = {norm_registrar(r) for r in dna.registrars}
    if e.get("registrar") and norm_registrar(e["registrar"]) in regs:
        b += 0.7
        why.append(f"registrar {e['registrar']}")
    if issuer and any(issuer[-12:] == i[-12:] for i in dna.model.get("issuers", []) if i):
        b += 0.4
        why.append(f"issuer {issuer[-20:]}")
    if set(e.get("asn", [])) & set(dna.asns):
        b += 0.6
        why.append("hosted on a campaign ASN")
    return b, why


def grammar_summary(recs: list[dict]) -> tuple[str, Counter]:
    c: Counter = Counter()
    for r in recs:
        s, t = split_domain(r["domain"])
        f = _struct(s, t)
        if f["app_suffix"] or s.count("-") >= 2:
            k = f"word-word-app.{t}"
        elif "-" in s:
            k = f"word-word.{t}"
        elif f["cv_alt"] > 0.8 and len(s) >= 8:
            k = f"cv-pseudoword.{t}"
        else:
            k = f"compound-word.{t}"
        c[k] += 1
    n = sum(c.values()) or 1
    return "; ".join(f"{100 * v // n}% {k}" for k, v in c.most_common(4)), c


def build_dna(campaign_id: str, recs: list[dict], auc: float | None, threshold: float, issuers: list[str] | None = None) -> DomainDNA:
    from trop.enrich.util import norm_registrar
    grammar, _ = grammar_summary(recs)
    tlds = Counter(split_domain(r["domain"])[1] for r in recs)
    n = sum(tlds.values()) or 1
    lens = Counter()
    for r in recs:
        L = len(split_domain(r["domain"])[0])
        lens[f"{(L // 4) * 4}-{(L // 4) * 4 + 3}"] += 1
    regs = Counter(norm_registrar(r.get("registrar")) for r in recs if r.get("registrar"))
    nsp = Counter("|".join(r["ns"]) for r in recs if r.get("ns"))
    hrs = sorted({int(str(r["cert_time"])[11:13]) for r in recs if r.get("cert_time") and len(str(r["cert_time"])) >= 13})
    return DomainDNA(
        campaign_id=campaign_id, grammar=grammar, examples=[r["domain"] for r in recs[:8]],
        tld_dist={k: round(v / n, 3) for k, v in tlds.most_common(10)}, length_hist=dict(sorted(lens.items())),
        registrars=[k for k, _ in regs.most_common(5) if k], issuance_hours=hrs,
        asns=[], model={"name": "char-ngram(2-4) LR + tld/struct", "auc": None if auc is None else round(auc, 3),
                        "ns_pairs": [k for k, v in nsp.most_common(12) if v >= 2], "issuers": sorted({r["issuer"] for r in recs if r.get("issuer")})[:8] if issuers is None else issuers,
                        "n_train": len(recs)},
        threshold=threshold)
