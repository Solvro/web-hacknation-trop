"""Notice texts (Polish): the DSA Art. 16 notice body drafted by Gemini Flash (editable), and the CERT PL draft.

DSA Art. 16(2) asks for: (a) a substantiated explanation why the content is illegal, (b) the exact electronic
locations (URLs: Ad Library ids, landing URLs), (c) the notifier's name and e-mail, (d) a good-faith statement.
(b)-(d) are filled from data by the PDF/JSON builder; the model writes only the explanation, from facts we pass it.
A template is used when no model is available. Wording needs a legal check before any real sending.
"""
from __future__ import annotations

from typing import Any

REPORTER = {"name": "Zespół analityczny TROP (HackNation 2026, projekt demonstracyjny)", "email": "trop@example.org"}
GOOD_FAITH = ("Oświadczam w dobrej wierze, że informacje i zarzuty zawarte w niniejszym zgłoszeniu są prawidłowe "
              "i kompletne (art. 16 ust. 2 lit. d DSA).")
LEGAL_BASIS = ("Art. 16 rozporządzenia (UE) 2022/2065 (akt o usługach cyfrowych, DSA) — mechanizm zgłaszania nielegalnych "
               "treści; treści stanowią usiłowanie oszustwa (art. 286 § 1 Kodeksu karnego) i wprowadzają w błąd "
               "co do tożsamości osób i mediów, pod które się podszywają.")

SYSTEM = ("Jesteś analitykiem CERT piszącym zgłoszenie nielegalnych treści na podstawie art. 16 DSA do platformy "
          "reklamowej. Piszesz po polsku, rzeczowo, bez przesady, 4–7 zdań w 3 akapitach. Opisz: co robią reklamy i "
          "strony (podszycie, obietnica, wyłudzenie), dlaczego to jedna kampania (wspólne ślady techniczne podane w "
          "faktach), czego oczekujemy (usunięcie wszystkich wymienionych reklam i zablokowanie kont reklamodawców). "
          "Używaj WYŁĄCZNIE liczb i nazw z faktów. Nie wymieniaj identyfikatorów reklam (są w załączniku). "
          "Nie dodawaj nagłówka, podpisu ani formułek grzecznościowych.")


def facts(d: dict[str, Any]) -> dict[str, Any]:
    c = d["counts"]
    return {
        "kampania": f"{d['id']} «{d['name']}»", "narracja": d.get("narrative"), "branża": d.get("vertical"),
        "reklamy": c["ads"], "reklamodawcy": c["advertisers"], "domeny": c["domains"], "materiały": c["incidents"],
        "podszywa_się_pod_osoby": d.get("persons", [])[:6], "podszywa_się_pod_media": d.get("brands", [])[:4],
        "wspólne_ślady": [f"{e['display']} ({e['members_with']} z {e['members_total']})" for e in d["evidence"][:6]],
        "przykładowe_teksty_reklam": sorted({(a.get("text") or "")[:120] for a in d["ads"] if a.get("text")})[:3],
    }


def template_notice(d: dict[str, Any]) -> str:
    f = facts(d)
    who = ", ".join(f["podszywa_się_pod_media"] + f["podszywa_się_pod_osoby"][:3]) or "znane media i osoby publiczne"
    traces = "; ".join(f["wspólne_ślady"][:3]) or "wspólne elementy techniczne stron"
    return (f"Zgłoszenie na podstawie art. 16 DSA.\n\n"
            f"Zgłaszamy {f['reklamy']} reklam z {f['reklamodawcy']} kont reklamodawców. Wszystkie należą do jednej kampanii "
            f"oszustwa {f['kampania']}. Reklamy podszywają się pod: {who}, a prowadzą na {f['domeny']} domen z fałszywymi "
            f"stronami, które wyłudzają dane i pieniądze.\n\n"
            f"Wspólne ślady: {traces}. Lista reklam, adresów i dowodów jest w załączniku.\n\n"
            f"Prosimy o usunięcie wszystkich wymienionych reklam i zablokowanie kont reklamodawców.")


def draft_notice(d: dict[str, Any], *, use_llm: bool = True) -> tuple[str, dict]:
    """-> (text, meta {model, cost_usd, cached, fallback})."""
    if use_llm:
        try:
            import json

            from trop.media.gateway import gateway
            r = gateway.llm("act_dsa_notice", [{"role": "system", "content": SYSTEM},
                                               {"role": "user", "content": "Fakty:\n" + json.dumps(facts(d), ensure_ascii=False, indent=1)}],
                            model="flash")
            text = (r.get("text") or "").strip()
            if text and not r.get("missing"):
                return "Zgłoszenie na podstawie art. 16 DSA.\n\n" + text, {"model": r.get("model"), "cost_usd": r.get("cost_usd", 0.0),
                                                                          "cached": r.get("cached"), "fallback": False}
        except Exception:  # noqa: BLE001
            pass
    return template_notice(d), {"model": "template", "cost_usd": 0.0, "cached": False, "fallback": True}


def certpl_text(d: dict[str, Any], domains: list[dict]) -> str:
    lines = "\n".join(f"- {x['fqdn']}" + (f" (certyfikat {x['cert_issued_at'][:16].replace('T', ' ')})" if x.get("cert_issued_at") else "")
                      for x in domains)
    traces = "; ".join(e["display"] for e in d["evidence"][:3])
    return (f"Do: CERT Polska — lista ostrzeżeń (incydent@cert.pl)\nTemat: {len(domains)} domen kampanii oszustwa "
            f"{d['id']} «{d['name']}» do wpisania na listę ostrzeżeń\n\n"
            f"Dzień dobry,\n\nprzekazujemy {len(domains)} domen, których jeszcze nie ma na liście ostrzeżeń, a które należą do "
            f"jednej kampanii oszustwa ({d['counts']['ads']} reklam, {d['counts']['domains']} domen łącznie). "
            f"Łączą je wspólne ślady techniczne: {traces}.\n\n{lines}\n\n"
            f"Szczegóły i dowody dla każdej domeny są w załączonym pliku JSON/STIX 2.1.\n\nZ poważaniem\n{REPORTER['name']}")
