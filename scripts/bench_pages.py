"""Read a handful of pages and check the measurement, in about two minutes.

The corpus is not a test set. Nothing here is trained — the recogniser's weights
are fixed and no amount of scanned paper changes them — so a re-index proves
nothing about a change; it only refreshes what the app serves. What a change has
to be checked against is a small set of pages chosen to cover the ways these
sheets differ: a typed list, a dense cursive family list, a nearly empty sheet, a
busy letterhead, a continuation page that prints no headings, a sheet whose rules
are gone.

    .venv-ocr/bin/python scripts/bench_pages.py            # check against data/golden.json
    .venv-ocr/bin/python scripts/bench_pages.py --record   # write what it reads as the baseline

Each page records what was measured — where the name column is, how many rows,
whether the table was found from the printing — and the run fails when a page
moves outside the tolerance. The tolerances are wide on purpose: this catches a
column landing on the wrong side of the sheet, not a band moving by a pixel.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from page_geometry import page_image                      # noqa: E402

GOLDEN = ROOT / "data" / "golden.json"
# How far a measurement may move before it counts as a change.
COLUMN_TOLERANCE = 0.03      # of the page width
ROW_TOLERANCE = 0.10         # of the row count


def measure(eng, pdf: Path, page: int) -> dict:
    img = page_image(pdf, page, ROOT / "data" / "pagecache")
    t0 = time.time()
    geo = eng._printed_table(img)
    out = {"printed": geo is not None, "seconds": round(time.time() - t0, 1)}
    if geo is not None:
        a, b = geo.name_column(0)
        out.update(rows=len(geo.rows), name_column=[round(a, 3), round(b, 3)],
                   heading=bool(getattr(geo, "heading_found", True)))
    return out


def compare(want: dict, got: dict) -> list[str]:
    bad = []
    if want.get("printed") != got.get("printed"):
        bad.append(f"measured from the printing: {want.get('printed')} -> {got.get('printed')}")
        return bad
    if not want.get("printed"):
        return bad
    for i, side in enumerate(("left", "right")):
        if abs(want["name_column"][i] - got["name_column"][i]) > COLUMN_TOLERANCE:
            bad.append(f"name column {side}: {want['name_column'][i]} -> {got['name_column'][i]}")
    if abs(want["rows"] - got["rows"]) > max(2, ROW_TOLERANCE * want["rows"]):
        bad.append(f"rows: {want['rows']} -> {got['rows']}")
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--record", action="store_true",
                    help="write what it reads now as the baseline")
    ap.add_argument("--golden", type=Path, default=GOLDEN)
    args = ap.parse_args(argv)

    from desembarque.engine_paddle import PaddleEngine
    eng = PaddleEngine()
    eng._import()

    spec = json.loads(args.golden.read_text(encoding="utf-8"))
    failures = 0
    for p in spec["pages"]:
        pdf = next((ROOT / "data" / "scans").glob(f"*{p['dossier']}*.pdf"), None)
        if pdf is None:
            print(f"  {p['dossier']} p{p['page']}: not in data/scans, skipped")
            continue
        got = measure(eng, pdf, p["page"])
        if args.record:
            p.update({k: v for k, v in got.items() if k != "seconds"})
            print(f"  {p['dossier']} p{p['page']}: {got}")
            continue
        bad = compare(p, got)
        mark = "ok  " if not bad else "MOVED"
        print(f"  {mark} {p['dossier']} p{p['page']} — {p['what']} ({got['seconds']}s)")
        for b in bad:
            print(f"        {b}")
        failures += len(bad)
    if args.record:
        args.golden.write_text(json.dumps(spec, indent=1, ensure_ascii=False),
                               encoding="utf-8")
        print(f"\nbaseline written to {args.golden}")
        return 0
    print(f"\n{failures} measurement(s) moved")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
