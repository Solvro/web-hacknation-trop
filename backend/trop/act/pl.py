"""Polish wording for generated Act texts: plurals, vertical names, campaign names/descriptions from trop/api/campaigns_pl.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

VERTICAL_PL = {"investment": "inwestycje", "investments": "inwestycje", "invest": "inwestycje", "health": "zdrowie", "loan": "pożyczki",
               "loans": "pożyczki", "crypto": "kryptowaluty", "finance": "finanse", "shopping": "zakupy", "e-commerce": "zakupy online",
               "dating": "randki", "job": "praca", "jobs": "praca", "gambling": "hazard", "other": "inne", "unknown": "nieokreślona"}


def plural(n: int, one: str, few: str, many: str) -> str:
    """'1 domena' / '4 domeny' / '5 domen' (Polish: 2-4 but not 12-14 -> few)."""
    n = int(n)
    if n == 1:
        form = one
    elif 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        form = few
    else:
        form = many
    return f"{n} {form}"


def n_ads(n: int) -> str:
    return plural(n, "reklama", "reklamy", "reklam")


def n_domains(n: int) -> str:
    return plural(n, "domena", "domeny", "domen")


def n_accounts(n: int) -> str:
    return plural(n, "konto reklamodawcy", "konta reklamodawców", "kont reklamodawców")


def n_advertisers(n: int) -> str:
    return plural(n, "reklamodawca", "reklamodawców", "reklamodawców")


def n_traces(n: int) -> str:
    return plural(n, "ślad", "ślady", "śladów")


def n_materials(n: int) -> str:
    return plural(n, "materiał", "materiały", "materiałów")


def vertical_pl(v: str | None) -> str | None:
    if not v:
        return v
    return VERTICAL_PL.get(str(v).lower().strip(), v)


def _campaigns_pl() -> dict:
    from trop.config import settings
    for p in (Path(settings.data_dir) / "corpus" / "campaigns_pl.json", Path(__file__).resolve().parents[1] / "api" / "campaigns_pl.json"):
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                return {}
    return {}


def polish_dossier(d: dict[str, Any]) -> dict[str, Any]:
    """Real campaigns: Polish name + description + vertical instead of the raw (English) database values. Fictional demo dossiers are left as is."""
    if d.get("fictional"):
        return d
    pl = _campaigns_pl().get(d.get("id") or "")
    if pl:
        d["name"] = pl.get("name") or d["name"]
        d["narrative"] = pl.get("description") or pl.get("headline") or d.get("narrative")
        d["vertical"] = pl.get("vertical") or vertical_pl(d.get("vertical"))
    else:
        d["vertical"] = vertical_pl(d.get("vertical"))
    return d
