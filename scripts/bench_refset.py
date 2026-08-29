#!/usr/bin/env python3
"""Read the seven reference pages and say what each one comes back as.

`data/refset.json` holds one page per failure shape — a typewritten table with
its headings over its columns, a cursive table with hand-read truth, a heading
printed away from its column, a page whose stored name column was the ordinal
strip, a faint cursive page, a continuation page that prints no headings, and a
cover card that must keep coming back as no table.

The corpus is not a test set: re-reading 700 pages to see whether a change
worked is hours spent learning what seven pages already say. This is the check
that replaces it, and it is deliberately cheap enough to run after every fix.

    .venv-ocr/bin/python scripts/bench_refset.py
    .venv-ocr/bin/python scripts/bench_refset.py --json out.json

Reported per page: what kind the reader decided it was, how many rows it cut,
how many of those carry any reading, how many carry a word this archive has
read before, and — where the columns are asked for — how many cells came back
and how many snapped to a word these forms print. Nothing here is scored
against a truth file: five of the seven have none, and what these numbers are
for is *did this page stop being empty*.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from desembarque.engine_paddle import READABLE_COLUMNS, PaddleEngine  # noqa: E402
from desembarque.gazetteer import Names, fold                         # noqa: E402
from page_geometry import page_image                                  # noqa: E402


def scan_for(notation: str, scans: Path) -> Path | None:
    """The dossier filed under a notation, found by the digits in its name."""
    stem = notation.split(".")[-1]
    return next((p for p in sorted(scans.rglob("*.pdf")) if stem in p.name), None)


def known_words(row: dict, names: Names) -> int:
    """How many words of this row's reading the archive has read before.

    The plainest signal that a page went from noise to names, and the one used
    when OL.PRJ.18109 p20 went from no dictionary words to five.
    """
    return sum(1 for w in (row.get("name_raw") or "").split()
               if names.counts.get(fold(w)))


def read_one(eng: PaddleEngine, pdf: Path, page: int, pagecache: Path,
             names: Names) -> dict:
    img = page_image(pdf, page, pagecache)
    t = time.time()
    res = eng.transcribe_page(img, kind="unknown", source=pdf, page=page)
    rows = res.rows or []
    read = [r for r in rows if (r.get("name_raw") or "").strip()]
    cells = [c for r in rows for c in (r.get("cells") or {}).values()]
    return {
        "kind": res.kind,
        "error": res.error,
        "seconds": round(time.time() - t, 1),
        "rows": len(rows),
        "read": len(read),
        "dictionary_words": sum(known_words(r, names) for r in read),
        "cells": len(cells),
        "snapped": sum(1 for c in cells if c.get("value")),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refset", type=Path, default=ROOT / "data" / "refset.json")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--pagecache", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--shape", default=None, help="one shape, by substring")
    ap.add_argument("--no-columns", action="store_true",
                    help="the name column alone, as a pass in a hurry reads it")
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)

    try:
        shapes = json.loads(a.refset.read_text(encoding="utf-8"))["shapes"]
    except (OSError, ValueError, KeyError):
        print(f"no reference set at {a.refset} — see docs/PROGRESS.md")
        return 1
    if a.shape:
        shapes = [s for s in shapes if a.shape.lower() in s["shape"].lower()]

    names = Names.load(ROOT / "data" / "names.json")
    eng = PaddleEngine(columns=() if a.no_columns else READABLE_COLUMNS)
    eng._import()

    out = []
    for s in shapes:
        pdf = scan_for(s["notation"], a.scans)
        if pdf is None:
            out.append({**s, "error": "scan not on disk"})
            continue
        try:
            got = read_one(eng, pdf, int(s["page"]), a.pagecache, names)
        except Exception as e:                       # a shape that throws is a result
            got = {"error": f"{type(e).__name__}: {e}"}
        out.append({**s, **got})

    head = (f"{'shape':<44} {'kind':<8} {'rows':>5} {'read':>5} "
            f"{'dict':>5} {'cells':>6} {'snap':>5} {'s':>5}")
    print(head)
    for r in out:
        if r.get("error"):
            print(f"{r['shape'][:43]:<44} {r['error']}")
            continue
        print(f"{r['shape'][:43]:<44} {r['kind']:<8} {r['rows']:>5} {r['read']:>5} "
              f"{r['dictionary_words']:>5} {r['cells']:>6} {r['snapped']:>5} "
              f"{r['seconds']:>5}")
    if a.json:
        a.json.write_text(json.dumps(out, indent=2, ensure_ascii=False),
                          encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
