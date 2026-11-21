"""Ported from experiments/rp/perturb.py.

Synthetic perturbations of incidents (robustness tests + training augmentation for the linkage model)."""
from __future__ import annotations

import copy
import random
import string

from trop.extract.rules import extract_incident


def _rand_domain(rng: random.Random) -> str:
    syl = ["dor", "que", "sio", "fal", "mur", "ek", "gren", "ta", "vo", "lun", "dev", "ra", "wer", "nu", "lio", "zen", "ith"]
    return "".join(rng.choice(syl) for _ in range(3)) + rng.choice([".click", ".live", ".top", ".pro", ".com", ".shop"])


def swap_domain(inc: dict, rng: random.Random) -> dict:
    """Infra rotation: new landing domain, new IPs, new cert. Tracking/kit/content unchanged."""
    x = copy.deepcopy(inc)
    old = x["landing"].get("host") or ""
    new = _rand_domain(rng)
    x["landing"]["host"] = new
    x["landing"]["etld1"] = new
    if x["landing"].get("entry_url"):
        x["landing"]["entry_url"] = x["landing"]["entry_url"].replace(old, new)
    for d in x["infra"]["domains"]:
        if d["fqdn"] == old:
            d.update({"fqdn": new, "etld1": new, "tld": new.rsplit(".", 1)[-1], "ips": [f"203.0.113.{rng.randint(1, 250)}"]})
            d.pop("cert", None)
    x["infra"]["origin_ips"] = [f"203.0.113.{rng.randint(1, 250)}"]
    x["infra"]["ips"] = list(x["infra"]["origin_ips"])
    return x


def rotate_tracking(inc: dict, rng: random.Random) -> dict:
    """New ad account: new pixel/CAPI/Google IDs + new domain. Kit tenant + content remain (realistic rotation)."""
    x = swap_domain(inc, rng)
    t = x["tracking"]
    t["fb_pixels"] = [str(rng.randint(10**14, 10**16))] if t.get("fb_pixels") else []
    t["capi_gateways"] = [f"xd-{rng.getrandbits(128):032x}.ecs.us-east-1.on.aws"] if t.get("capi_gateways") else []
    t["google_ads"] = [f"AW-{rng.randint(10**10, 10**11)}"] if t.get("google_ads") else []
    t["ga4"] = []
    return x


def full_rotation(inc: dict, rng: random.Random) -> dict:
    """Everything infra/tracking/kit rotates; only content + ad creative survive (M2 'infra-blind' case)."""
    x = rotate_tracking(inc, rng)
    t = x["tracking"]
    for k in ("kit_tenants", "lander_ids", "landing_type_ids", "asset_hashes", "video_hosts", "third_party", "kmnr_key"):
        t[k] = []
    t["kit_endpoints"] = []
    t["url_param_schema"] = ""
    t["entry_path_template"] = ""
    x["content"]["ad_name"] = None
    return x


def error_page(inc: dict, rng: random.Random) -> dict:
    """Landing returned a Cloudflare 502 (like the p1 archive): no landing content/assets, ad screenshot survives."""
    x = copy.deepcopy(inc)
    x["landing"].update({"title": "502: Bad gateway", "text": "Bad gateway Error code 502", "h1": [], "dom_paths": [],
                         "css_classes": [], "page_role": "error"})
    t = x["tracking"]
    for k in ("asset_hashes", "kit_endpoints", "third_party", "lander_ids", "landing_type_ids", "video_hosts",
              "fb_pixels", "capi_gateways", "google_ads", "ga4", "kit_tenants", "kmnr_key"):
        t[k] = []
    x["content"].update({"headline_template": "", "h1_template": "", "persons": [], "brands": [], "products": [],
                         "vertical": "other", "lang": "unk", "comment_names": [], "ad_name": None})
    x.get("emb", {}).pop("text_emb", None)          # landing text is gone -> its embedding must go too
    x["tracking"]["url_param_schema"] = x["tracking"].get("url_param_schema", "")   # entry URL survives (it is what we visited)
    return x


def drop_screenshot(inc: dict, rng: random.Random) -> dict:
    x = copy.deepcopy(inc)
    x["ad"] = {}
    x.get("emb", {}).pop("ad_emb", None)
    x.get("emb", {}).pop("shot_emb", None)
    x.get("media", {}).pop("faces", None)
    return x


def reextract(inc: dict, drop: set[str]) -> dict:
    """Real re-extraction with inputs removed (drop HAR / HTML). Keeps ad/emb layers computed from screenshot."""
    x = extract_incident(inc["source"]["path"], inc_id=inc["id"], drop=drop)
    if "screenshot" not in drop:
        x["ad"] = copy.deepcopy(inc.get("ad", {}))
        x["media"] = copy.deepcopy(inc.get("media", {}))
        if inc.get("emb", {}).get("shot_emb") is not None:
            x.setdefault("emb", {})["shot_emb"] = inc["emb"]["shot_emb"]
    return x


def duplicate(inc: dict, rng: random.Random) -> dict:
    return copy.deepcopy(inc)


PERTURBATIONS = {
    "duplicate": duplicate,
    "drop_screenshot": drop_screenshot,
    "drop_har": lambda inc, rng: reextract(inc, {"har"}),
    "drop_html": lambda inc, rng: reextract(inc, {"html"}),
    "swap_domain": swap_domain,
    "rotate_tracking": rotate_tracking,
    "error_502": error_page,
    "full_rotation": full_rotation,
}


def tag(inc: dict, suffix: str) -> dict:
    inc = dict(inc)
    inc["id"] = f"{inc['id']}~{suffix}"
    return inc


def random_suffix(rng):
    return "".join(rng.choice(string.ascii_lowercase) for _ in range(4))
