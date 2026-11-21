#!/usr/bin/env python3
"""Build deploy/bundle/samples/: jury sample zips (DANE folders + a few sample_v1 items) and samples.json (served by GET /api/v1/samples).

    deploy/make_samples.py [DATA_DIR] [OUT_DIR]      (called by make_bundle.sh)
Each zip contains ONE top-level folder with the item files, the layout `trop analyze` / POST /analyze accepts.
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "deploy" / "bundle" / "samples"
DANE = DATA / "raw" / "dane" / "unpacked" / "do_udostępnienia"
SAMPLE = DATA / "raw" / "sample_v1"

# id, source dir, Polish title, Polish description, expected outcome (what the engine decides offline; checked in tests)
ITEMS = [
    ("dane-1", DANE / "1", "Fałszywa Gazeta.pl — „Wiem, kto strzelał”", "Zrzut reklamy, HAR i zapisana strona z fałszywym artykułem o zamachu na znaną osobę. Znana kampania.", "assign:KMP-001"),
    ("dane-3", DANE / "3", "Olejnik kontra NBP — fałszywy artykuł", "Reklama i strona z wywiadem, który nigdy się nie odbył; ta sama sieć lejków co kampania A. Znana kampania.", "assign:KMP-003"),
    ("dane-36", DANE / "36", "„Poland Invest Summit 2026”", "Przynęta „wydarzenie inwestycyjne” z przeciekiem tokenu w adresie. Nowy wzorzec: system nie dopasowuje go do znanej kampanii.", "new"),
    ("dane-5", DANE / "5", "Ból pleców — samo nagranie reklamy", "Materiał z samym filmem, bez strony docelowej: transkrypcja i analiza nagrania dają dowody (warstwa media), ale nie pasują do znanej kampanii — nowy wzorzec.", "new"),
    ("dane-48", DANE / "48", "Reklama „37 minut po emisji…”", "Ta sama historia na Facebooku i w Google Ads, ten sam operator co kampania A (wspólna operacja).", "new"),
    ("p13", SAMPLE / "p13", "Grzybica paznokci — „Dr Merritz”", "Materiał, który system już zna (zbiór wzorcowy): pokazuje, jak wygląda wykrycie duplikatu (L0).", "assign:KMP-008"),
    ("p14", SAMPLE / "p14", "Divine Script — oferta po angielsku", "Niepowiązana kampania referencyjna (afiliacja z Brazylii); znany materiał.", "assign:KMP-009"),
]
MAX_ZIP = 15 * 1024 * 1024


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    meta = []
    for sid, src, title, desc, expect in ITEMS:
        if not src.is_dir():
            print("skip (missing):", sid)
            continue
        z = OUT / f"{sid}.zip"
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for f in sorted(src.rglob("*")):
                if f.is_file() and not f.name.startswith("."):
                    zf.write(f, Path(sid) / f.relative_to(src))
        size = z.stat().st_size
        if size > MAX_ZIP:
            z.unlink()
            print(f"skip (zip {size/1e6:.1f} MB > limit): {sid}")
            continue
        meta.append({"id": sid, "title": title, "description": desc, "expected": expect, "file": z.name, "size": size})
        print(f"{sid}: {size/1e6:.1f} MB")
    (OUT / "samples.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print("total", sum(m["size"] for m in meta) / 1e6, "MB")


if __name__ == "__main__":
    build()
