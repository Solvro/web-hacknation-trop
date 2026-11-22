"""DSA Art. 16 notice as PDF (fpdf2, pure Python). Font: DejaVu Sans (Bitstream Vera licence, fonts/LICENSE-DejaVu.txt)
so Polish diacritics render without system fonts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from .notice import GOOD_FAITH, LEGAL_BASIS, REPORTER
from .pl import n_ads, n_advertisers, n_domains, n_traces

FONTS = Path(__file__).parent / "fonts"
INK, MUTED, LINE = (20, 28, 24), (90, 100, 95), (200, 208, 204)


class _Doc(FPDF):
    def __init__(self, footer_text: str) -> None:
        super().__init__(format="A4")
        self.footer_text = footer_text
        self.add_font("DejaVu", "", str(FONTS / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONTS / "DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(True, margin=16)
        self.set_margins(16, 16, 16)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*MUTED)
        self.cell(0, 5, f"{self.footer_text} · strona {self.page_no()}/{{nb}}", align="C")


def _h(pdf: _Doc, text: str, size: float = 11) -> None:
    pdf.ln(2)
    pdf.set_font("DejaVu", "B", size)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 6, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(*LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(1.5)


def _p(pdf: _Doc, text: str, size: float = 9.5, color=INK) -> None:
    pdf.set_font("DejaVu", "", size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, 5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _table(pdf: _Doc, head: list[str], rows: list[list[Any]], widths: list[float], size: float = 7.5) -> None:
    pdf.set_font("DejaVu", "B", size)
    pdf.set_fill_color(235, 240, 237)
    pdf.set_text_color(*INK)
    with pdf.table(col_widths=widths, text_align="LEFT", line_height=4.2, first_row_as_headings=True,
                   borders_layout="HORIZONTAL_LINES") as t:
        r = t.row()
        for h in head:
            r.cell(h)
        pdf.set_font("DejaVu", "", size)
        for row in rows:
            r = t.row()
            for v in row:
                r.cell("" if v is None else str(v))
    pdf.ln(2)


def render_dsa_pdf(pkg: dict[str, Any], d: dict[str, Any], notice_text: str) -> bytes:
    fict = " · DANE FIKCYJNE (demo)" if d.get("fictional") else ""
    pdf = _Doc(f"TROP · {pkg['id']} · {d['id']}{fict} · nic nie zostało wysłane — pakiet przygotowany i wyeksportowany")
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font("DejaVu", "B", 15)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 8, f"Zgłoszenie nielegalnych treści (art. 16 DSA)\nKampania {d['id']} «{d['name']}»",
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    c = d["counts"]
    _p(pdf, f"Pakiet {pkg['id']} · przygotowano {pkg['created_at'][:16].replace('T', ' ')} UTC · "
            f"{n_ads(c['ads'])} · {n_advertisers(c['advertisers'])} · {n_domains(c['domains'])} · {n_traces(c['evidence_items'])} wspólnych"
            + fict, 8.5, MUTED)
    if d.get("fictional"):
        _p(pdf, "Uwaga: wszystkie dane w tym dokumencie są fikcyjne (materiał demonstracyjny).", 8.5, (150, 60, 30))

    _h(pdf, "1. Uzasadnienie (art. 16 ust. 2 lit. a)")
    _p(pdf, notice_text)
    _h(pdf, "Podstawa prawna", 10)
    _p(pdf, LEGAL_BASIS, 8.5)

    _h(pdf, "2. Dokładne lokalizacje treści (art. 16 ust. 2 lit. b) — reklamy")
    rows = [[a.get("library_id") or "brak id", a.get("advertiser") or "?", (a.get("start") or "")[:10],
             (a.get("landing_url") or a.get("display_link") or "—").split("?")[0][:60]] for a in d["ads"]]
    if rows:
        _p(pdf, "Adres reklamy: https://www.facebook.com/ads/library/?id=<ID>. Pełne adresy stron docelowych w załączniku JSON.",
           8, MUTED)
        _table(pdf, ["ID w Bibliotece reklam", "Reklamodawca", "Start", "Strona docelowa"], rows, [38, 48, 20, 72])
    else:
        _p(pdf, "Brak reklam z identyfikatorem w materiale — zgłaszane są adresy stron poniżej.", 8.5, MUTED)

    _h(pdf, "Konta reklamodawców")
    _table(pdf, ["Reklamodawca", "ID strony", "Platforma", "Reklam"],
           [[a["name"], a.get("page_id") or "—", a.get("platform") or "meta", a["n_ads"]] for a in d["advertisers"]], [70, 45, 30, 33])

    _h(pdf, "Domeny docelowe")
    _table(pdf, ["Domena", "Rejestracja", "Certyfikat", "CERT PL", "Źródło"],
           [[x["fqdn"], (x.get("registered_at") or "—")[:16].replace("T", " "), (x.get("cert_issued_at") or "—")[:16].replace("T", " "),
             "na liście" if x.get("on_certpl") else "brak", "śledztwo" if x.get("source") == "investigation" else "kampania"]
            for x in d["domains"]], [52, 36, 36, 24, 30])

    _h(pdf, "3. Dowody wspólnego pochodzenia")
    _table(pdf, ["Warstwa", "Ślad", "Siła", "Pokrycie"],
           [[e["type"], e["display"], e["strength"], f"{e['members_with']} z {e['members_total']}"] for e in d["evidence"]],
           [24, 104, 16, 34])

    _h(pdf, "4. Zgłaszający (art. 16 ust. 2 lit. c) i oświadczenie (lit. d)")
    _p(pdf, f"{REPORTER['name']} · {REPORTER['email']}")
    _p(pdf, GOOD_FAITH)
    _p(pdf, pkg.get("disclaimer", ""), 8.5, MUTED)
    return bytes(pdf.output())
