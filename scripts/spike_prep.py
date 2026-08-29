"""Does anything done to a crop before recognition help a cursive hand?

The recogniser is the ceiling — a wider input, a bigger model, removing the
printed rules and a pretrained handwriting model were each measured against it
and none moved it. What has not been tried is the crop itself: the contrast it
arrives with, its resolution, and the lean of the writing, which every classical
handwriting pipeline corrects for and this one does not.

The geometry is measured once per page and the same crops are then read by each
variant, so the comparison is of the preprocessing and nothing else.

    .venv-ocr/bin/python scripts/spike_prep.py
    .venv-ocr/bin/python scripts/spike_prep.py --only deslant,none
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

from bench_rec import align, cer, prepared, truths            # noqa: E402
from desembarque import engine_paddle as ep                   # noqa: E402
from desembarque.search import similarity                     # noqa: E402
from page_geometry import page_image                          # noqa: E402

VARIANTS = ("none", "autocontrast", "upscale2", "sharpen", "deslant",
            # the faded-document moves, which had never been tried: the paper
            # browns unevenly and the ink fades where the pen ran dry, so one
            # curve for the whole crop serves the darkest corner and the
            # faintest stroke at once
            "bgdiv", "clahe", "bgdiv_clahe", "bgdiv_up2", "adaptive",
            "bgdiv_adaptive")


def crops_of(eng, pdf: Path, page: int):
    """The name-column crops of one page, measured the way the engine does."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    img = page_image(pdf, page, ROOT / "data" / "pagecache")
    geo = eng._printed_table(img)
    if geo is None:
        from page_geometry import analyze
        geo = analyze(img)
    if not geo.rows or not geo.name_column(0):
        return None, None
    im = Image.open(img).convert("L")
    im = im.rotate(geo.skew, resample=Image.BICUBIC, fillcolor=255)
    return geo, (im, eng._carved_crops(im, geo))


def read(eng, geo, made, prep: str) -> list[str]:
    im, crop = made
    rows = ep.rows_from_bands(geo, im.size, prepared(eng._recognize, prep), crop)
    return [r.get("name_raw") or "" for r in rows]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", default=",".join(VARIANTS))
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "spike_prep.json")
    args = ap.parse_args(argv)
    wanted = [v for v in args.only.split(",") if v in VARIANTS]

    eng = ep.PaddleEngine()
    eng._import()
    pages = []
    for t in truths():
        pdf = ROOT / "data" / "scans" / t["pdf"]
        if not pdf.exists():
            continue
        geo, made = crops_of(eng, pdf, t["page"])
        if geo is None:
            print(f"  {t['pdf']} p{t['page']}: no table, skipped")
            continue
        pages.append((t, geo, made))
    print(f"{len(pages)} truth pages, {len(wanted)} variants")

    # What each variant read of each row, so the last question can be asked:
    # whether the *union* of the readings finds people none of them finds alone.
    # Search already scores a row by the best of its readings.
    said: dict[str, list[str]] = {}
    report = {}
    for prep in wanted:
        rows = exact = findable = 0
        cers = []
        t0 = time.time()
        for t, geo, made in pages:
            names = read(eng, geo, made, prep)
            first = align(names, t["names"]) + 1
            for i, want in enumerate(t["names"]):
                got = names[first - 1 + i] if 0 <= first - 1 + i < len(names) else ""
                said.setdefault(f"{t['pdf']}#{t['page']}#{i}", []).append(got)
                rows += 1
                cers.append(cer(want, got))
                exact += cer(want, got) == 0
                findable += similarity(want, got) >= 0.10
        report[prep] = {"rows": rows, "cer": round(sum(cers) / max(len(cers), 1), 3),
                        "exact": exact, "findable": findable,
                        "seconds": round(time.time() - t0, 1)}
        r = report[prep]
        print(f"  {prep:13s} CER {r['cer']:.3f}  exact {r['exact']:3d}/{rows}  "
              f"findable {r['findable']:3d}/{rows}  {r['seconds']}s")
    if len(wanted) > 1:
        truth_of = {f"{t['pdf']}#{t['page']}#{i}": name
                    for t, _g, _m in pages for i, name in enumerate(t["names"])}
        union = sum(1 for k, reads in said.items()
                    if max(similarity(truth_of[k], g) for g in reads) >= 0.10)
        best = max(r["findable"] for r in report.values())
        print(f"  {'union':13s} findable {union}/{len(said)} — against "
              f"{best} for the best single variant")
        report["union"] = {"findable": union, "rows": len(said)}
    args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
