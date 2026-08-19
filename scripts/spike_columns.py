"""Throwaway spike: is the name column pickable by width, and are blanks dittos?

Two questions, one pass over a sample of real pages, because both need the same
expensive thing (geometry) and the same careful thing (ignoring the ruled lines).

1. `Geometry.name_column(0)` picks a column by rule index, so whether it lands
   on the names depends on whether the faint Numero divider printed well enough
   to be detected. The proposed fix is to pick the *widest* column starting in
   the left of the page. This measures how often that disagrees with what the
   engine does today, which is the size of the bug.

2. 23.4% of indexed rows are blank while sitting between two named rows. The
   hypothesis is that they are ditto marks -- a small isolated stroke meaning
   "same surname as above" -- which the recogniser returns as nothing. A ditto
   is narrow; a name is wide; blank paper has no ink at all. Measuring the ink
   bounding box in each band separates the three.

The measurement must exclude the table's own rules. A horizontal rule spans the
full column width, so a band containing one reports a bounding box as wide as
the column no matter what is written in it -- which is how a first look at this
made every row appear to hold a name.

    .venv-htr/bin/python scripts/spike_columns.py --sample 25
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

RULE_FRAC = 0.80      # a line of pixels this inked is a printed rule, not writing
INK_MIN = 0.02        # ignore speckle when finding the ink's extent
DITTO_MAX = 0.14      # bbox narrower than this share of the column: a mark
NAME_MIN = 0.25       # wider than this: writing


def deruled(crop):
    """The crop with its printed rules blanked out.

    Returns a boolean ink mask. Rows and columns of pixels that are almost
    entirely ink are the table's own lines; keeping them makes every band look
    like it spans the column.
    """
    import numpy as np
    a = np.asarray(crop.convert("L"), dtype=np.uint8)
    if a.size == 0:
        return np.zeros((0, 0), dtype=bool)
    thr = max(60, int(a.mean()) - 35)
    ink = a < thr
    ink[ink.mean(axis=1) > RULE_FRAC, :] = False
    ink[:, ink.mean(axis=0) > RULE_FRAC] = False
    return ink


def extent(ink) -> tuple[float, int]:
    """Width of the writing as a share of the column, and its pixel height."""
    import numpy as np
    if ink.size == 0 or not ink.any():
        return 0.0, 0
    h, w = ink.shape
    xs = np.flatnonzero(ink.sum(axis=0) > max(1, int(INK_MIN * h)))
    ys = np.flatnonzero(ink.sum(axis=1) > max(1, int(INK_MIN * w)))
    if xs.size == 0 or ys.size == 0:
        return 0.0, 0
    return float(xs[-1] - xs[0] + 1) / w, int(ys[-1] - ys[0] + 1)


def widest_column(cols, left_limit: float = 0.6):
    """The widest column whose left edge is in the left of the page.

    A manifest puts the name early and gives it more room than anything else;
    the only comparable column is Observações, far to the right.
    """
    best, span = None, 0.0
    for a, b in zip(cols, cols[1:]):
        if a > left_limit:
            continue
        if b - a > span:
            best, span = (a, b), b - a
    return best


def classify_bands(im, geo, colrange):
    """One verdict per row band in the given column."""
    W, H = im.size
    x0 = max(0, int((colrange[0] - 0.004) * W))
    x1 = min(W, int((colrange[1] + 0.004) * W))
    out = []
    for i, (bt, bb) in enumerate(geo.normalized_rows()):
        a = max(0, int(bt * H) - 6)
        b = min(H, int(bb * H) + 6)
        if b - a < 12:
            continue
        frac, hpx = extent(deruled(im.crop((x0, a, x1, b))))
        if frac <= 0.0:
            verdict = "empty"
        elif frac < DITTO_MAX:
            verdict = "mark"
        elif frac >= NAME_MIN:
            verdict = "name"
        else:
            verdict = "short"
        out.append({"band": i, "width_frac": round(frac, 3),
                    "ink_h": hpx, "verdict": verdict})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=25)
    ap.add_argument("--page", type=int, default=2)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "spike_columns.json")
    args = ap.parse_args()

    from PIL import Image
    from page_geometry import analyze, page_image
    Image.MAX_IMAGE_PIXELS = None

    pdfs = sorted(args.scans.glob("*.pdf"))
    random.Random(args.seed).shuffle(pdfs)

    records, agree, disagree, nogrid = [], 0, 0, 0
    tally = {"name": 0, "mark": 0, "short": 0, "empty": 0}

    for pdf in pdfs[:args.sample]:
        try:
            img = page_image(pdf, args.page, args.work)
            if img is None:
                nogrid += 1
                continue
            geo = analyze(img)
            cols = geo.normalized_cols()
            picked = geo.name_column(0)
            wide = widest_column(cols)
            if not geo.rows or picked is None or wide is None:
                nogrid += 1
                continue
            same = picked == wide
            agree += same
            disagree += not same

            im = Image.open(img).convert("L")
            im = im.rotate(geo.skew, resample=Image.BICUBIC, fillcolor=255)
            bands = classify_bands(im, geo, wide)
            for b in bands:
                tally[b["verdict"]] += 1

            rec = {
                "pdf": pdf.name, "cols": [round(c, 4) for c in cols],
                "picked": [round(v, 4) for v in picked],
                "widest": [round(v, 4) for v in wide],
                "agree": same,
                "picked_width": round(picked[1] - picked[0], 4),
                "widest_width": round(wide[1] - wide[0], 4),
                "bands": bands,
            }
            records.append(rec)
            print(f"{'ok ' if same else 'MISS'} {pdf.name[:44]:44s} "
                  f"picked {rec['picked_width']:.3f}  widest {rec['widest_width']:.3f}  "
                  f"bands n={sum(1 for b in bands if b['verdict']=='name')} "
                  f"mark={sum(1 for b in bands if b['verdict']=='mark')} "
                  f"empty={sum(1 for b in bands if b['verdict']=='empty')}", flush=True)
        except Exception as e:  # a spike: a page that will not open is a datum
            print(f"ERR  {pdf.name[:44]:44s} {type(e).__name__}: {e}", flush=True)
            nogrid += 1

    total = agree + disagree
    print(f"\npages measured {total}   no grid/err {nogrid}")
    if total:
        print(f"width choice agrees with today's index choice : {agree} ({100*agree/total:.0f}%)")
        print(f"width choice DIFFERS                          : {disagree} ({100*disagree/total:.0f}%)")
    n = sum(tally.values())
    if n:
        print("\nband content in the width-chosen column:")
        for k in ("name", "short", "mark", "empty"):
            print(f"  {k:6s} {tally[k]:5d}  {100*tally[k]/n:5.1f}%")
    args.out.write_text(json.dumps(
        {"summary": {"pages": total, "agree": agree, "disagree": disagree,
                     "bands": tally}, "pages_detail": records},
        ensure_ascii=False, indent=2))
    print(f"\nwritten {args.out}")


if __name__ == "__main__":
    main()
