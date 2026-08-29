#!/usr/bin/env python3
"""Read the nationality column of the hand-read pages, once, into a side file.

`bench_menu.py` scores the menu over the pages in `data/truth`, and the
language prior (T11) needs each row's nationality to know which language to
look in first. The stored transcriptions of those pages were written before the
column reading was wired, so they carry no cells.

Read here rather than by re-transcribing those pages, deliberately: a
re-transcription would change the very readings the bench pairs against, and
the bench would then be measuring two changes at once.

    .venv-ocr/bin/python scripts/read_nationalities.py
    .venv-ocr/bin/python scripts/read_nationalities.py --out data/truth_nationalities.json

Keyed `pdf|page|row`. Both the reading and the word it snapped to are kept, and
the prior is taken from the snapped word — `LASIERCL` names no language.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from desembarque.engine_paddle import PaddleEngine, cells_from_bands  # noqa: E402
from desembarque.vocab import Vocabulary                              # noqa: E402
from page_geometry import page_image                                  # noqa: E402

FIELD = "nacionalidade"


def truth_pages() -> list[tuple[str, int]]:
    out = []
    for f in sorted((ROOT / "data" / "truth").glob("*.json")):
        t = json.loads(f.read_text(encoding="utf-8"))
        if t.get("pdf") and t.get("page"):
            out.append((t["pdf"], int(t["page"])))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--pagecache", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "data" / "truth_nationalities.json")
    a = ap.parse_args(argv)

    from PIL import Image

    eng = PaddleEngine()
    eng._import()
    vocab = Vocabulary.load(ROOT / "data" / "column_vocab.json")
    out: dict[str, dict] = {}
    for pdf_name, page in truth_pages():
        pdf = next((p for p in a.scans.rglob("*.pdf") if p.name == pdf_name), None)
        if pdf is None:
            print(f"scan not found, skipped: {pdf_name}")
            continue
        img = page_image(pdf, page, a.pagecache)
        geo = eng._printed_table(img)
        if geo is None or FIELD not in geo.normalized_columns():
            print(f"{pdf_name} p{page}: no {FIELD} column measured")
            continue
        im = Image.open(img).convert("L").rotate(geo.skew, resample=Image.BICUBIC,
                                                 fillcolor=255)
        cells = cells_from_bands(geo, im.size, FIELD, eng._recognize,
                                 lambda i, box: im.crop(box))
        wrote = 0
        for c in cells:
            text = (c.get("text") or "").strip()
            if not text:
                continue
            snapped = vocab.snap(FIELD, text)
            out[f"{pdf_name}|{page}|{c['n']}"] = {
                "text": text,
                "value": snapped["value"] if snapped else None,
            }
            wrote += 1
        print(f"{pdf_name} p{page}: {wrote} cells with ink")
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    snapped = sum(1 for v in out.values() if v["value"])
    print(f"{len(out)} cells, {snapped} snapped to a nationality -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
