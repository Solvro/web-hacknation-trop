"""Engine evidence dicts -> schema.EvidenceItem (UI chips).

Mapping (RESULTS §4): engine LAYER -> UI layer (tracking/kit/infra/content/persons/visual/ad), negatives -> the layer
of the conflicting field; level = platform (shared commercial tooling: kit endpoints) | operator_only
(evidence.OPERATOR_ONLY) | campaign; strength from the a-priori STRENGTH: H >= 5, M >= 2.5, else L.
"""
from __future__ import annotations

import math

from trop.schema import EvidenceItem

from . import evidence as E

NEG_LAYER = {"kit_tenant_conflict": "kit", "lang_conflict": "content", "vertical_conflict": "content"}
PLATFORM = {"kit_endpoints"}
BOT_OF_LAYER = {"tracking": "tropiciel", "kit": "tropiciel", "infra": "notariusz", "content": "czytelnik",
                "persons": "czytelnik", "ad": "czytelnik", "visual": "czytelnik", "media": "czytelnik"}
LABEL = {   # short Polish display prefixes for chips
    "fb_pixel": "Piksel FB", "capi_gateway": "Bramka CAPI", "google_ads": "Google Ads", "ga4": "GA4", "gtm": "GTM",
    "tiktok_pixel": "Piksel TikTok", "kit_tenant": "Tenant kitu", "lander_id": "Lander", "landing_type_id": "Typ landingu",
    "video_host": "Host wideo", "etld1": "Domena", "fqdn": "Host", "asset_hash": "Wspólne pliki", "kit_endpoints": "Endpointy kitu",
    "url_param_schema": "Gramatyka URL", "entry_path_template": "Szablon ścieżki", "third_party": "Usługi zewnętrzne",
    "dom_minhash": "Struktura DOM", "origin_ip": "IP serwera", "cert_batch": "Partia certyfikatów", "domain_dna": "Kształt domeny",
    "headline_template": "Szablon nagłówka", "h1_template": "Szablon H1", "text_minhash": "Tekst strony", "persons": "Osoby",
    "brands": "Marki", "products": "Produkt", "vertical": "Branża", "ad_name_grammar": "Nazwa reklamy",
    "comment_names": "Fałszywi komentujący", "brand_asset": "Pliki marki", "ns_pair": "Para NS", "registrar_batch": "Partia rejestracji",
    "entry_url": "Ten sam URL wejścia", "path_shape": "Kształt ścieżki", "chain_etld1": "Domena lejka",
    "advertiser": "Reklamodawca", "ad_text": "Tekst reklamy", "creative_phash": "Kreacja (pHash)", "ad_persons": "Osoby w reklamie",
    "text_emb": "Podobieństwo tekstu", "shot_emb": "Podobieństwo zrzutu", "face_identity": "Twarz",
    "kit_tenant_conflict": "Różny tenant kitu", "lang_conflict": "Różny język", "vertical_conflict": "Różna branża",
}


def ui_layer(ftype: str) -> str:
    if ftype in NEG_LAYER:
        return NEG_LAYER[ftype]
    return E.LAYER.get(ftype, "content")


def level_of(ftype: str) -> str:
    if ftype in PLATFORM:
        return "platform"
    if ftype in E.OPERATOR_ONLY or ftype == "kit_tenant_conflict":
        return "operator_only"
    return "campaign"


def strength_of(ftype: str) -> str:
    s = abs(E.STRENGTH.get(ftype, E.NEG.get(ftype, 0.0)))
    return "H" if s >= 5 else ("M" if s >= 2.5 else "L")


def df_of(ftype: str, raw, df: dict | None) -> int:
    if not df or raw is None:
        return 0
    vals = raw if isinstance(raw, (list, tuple, set)) else [raw]
    tbl = df.get(ftype) or {}
    got = [tbl.get(v, 0) for v in vals if isinstance(v, (str, int))]
    return int(min(got)) if got else 0


def to_item(e: dict, df: dict | None = None, n: int = 0, state: str | None = None, bot: str | None = None,
            sides: dict | None = None) -> EvidenceItem:
    ftype = e["type"]
    raw = e.get("raw")
    value = str(raw[0]) if isinstance(raw, list) and raw else str(e.get("value", ""))
    d = df_of(ftype, raw, df)
    layer = ui_layer(ftype)
    disp = f"{LABEL.get(ftype, ftype)}: {e.get('value', value)}"
    return EvidenceItem(
        type=layer, field=ftype, value=value[:300], display=disp[:300], strength=strength_of(ftype),
        weight=float(e.get("weight", 0.0)), level=level_of(ftype), df=d, N=n,
        idf=round(math.log((n + 1) / d), 3) if d and n else 0.0,
        state=state or ("conflict" if e.get("weight", 0) < 0 else "match"), sides=sides,
        bot=bot or BOT_OF_LAYER.get(layer))


# --------------------------------------------------------------------------- material evidence (one incident)
MATERIAL = {   # step -> engine feature types read from incident['_v'] after evidence.prepare([inc])
    "tracking": ["fb_pixel", "capi_gateway", "google_ads", "ga4", "gtm", "tiktok_pixel", "kit_tenant", "lander_id",
                 "landing_type_id", "video_host", "path_shape", "entry_url", "url_param_schema", "asset_hash", "kit_endpoints"],
    "content": ["headline_template", "persons", "comment_names", "brands", "products", "advertiser", "ad_text",
                "face_identity"],
    "infra": ["etld1", "chain_etld1", "ns_pair"],
}
COUNT_ONLY = {"asset_hash", "kit_endpoints", "comment_names"}


def material_items(inc: dict, step: str, df: dict | None = None, n: int = 0) -> list[EvidenceItem]:
    """Findings about the material itself (before comparison): value + corpus rarity; weight = prior strength."""
    if "_v" not in inc:
        E.prepare([inc])
    v = inc["_v"]
    out = []
    for ftype in MATERIAL.get(step, []):
        vals = v.get(ftype)
        if not vals:
            continue
        vals = sorted(vals) if isinstance(vals, set) else [vals]
        if ftype == "chain_etld1":
            vals = [x for x in vals if x not in v.get("etld1", set())]
            if not vals:
                continue
        if ftype in COUNT_ONLY:
            out.append(to_item({"type": ftype, "value": f"{len(vals)} (np. {str(vals[0])[:40]})", "raw": vals,
                                "weight": E.STRENGTH.get(ftype, 0.0)}, df, n, bot=None))
            continue
        for x in vals[:5]:
            out.append(to_item({"type": ftype, "value": str(x)[:120], "raw": [x], "weight": E.STRENGTH.get(ftype, 0.0)}, df, n))
    if step == "infra":
        for d in (inc.get("infra") or {}).get("domains", [])[:1]:
            enr = d.get("enrich") or {}
            if enr.get("registrar") and enr.get("created"):
                out.append(to_item({"type": "registrar_batch", "value": f"{enr['registrar']} · {str(enr['created'])[:16]}",
                                    "raw": [enr["registrar"]], "weight": E.STRENGTH["registrar_batch"]}, None, n))
    return out
