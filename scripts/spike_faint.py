"""Does lifting the contrast let the detector find writing it otherwise misses?

Two different questions have been asked about preprocessing and only one has
been answered. `spike_prep.py` asked whether a crop read *better* after
autocontrast, sharpening, upscaling or deslanting, and the answer was no: 0.362
character error against 0.361, which is noise. This asks the other one — whether
the detector *finds* boxes it otherwise misses on a faint page.

They are not the same question. On OL.PRJ.17851 the writing is too faint for the
detector to find at all: thirty boxes on a page of twenty-three names, so the
rows are supplied by the ruled fallback and the columns by the printing. A crop
that reads no better is still worth having if the alternative was not cutting
that crop at all.

    .venv-ocr/bin/python scripts/spike_faint.py
    .venv-ocr/bin/python scripts/spike_faint.py --pages OL.PRJ.17851:1
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

from desembarque.engine_paddle import PaddleEngine   # noqa: E402
from desembarque.tablegrid import (columns, heading_lines,  # noqa: E402
                                   table)
from page_geometry import page_image                 # noqa: E402

VARIANTS = ("none", "autocontrast", "equalize", "stretch", "gamma")


def prepare(im, how: str):
    """One picture, one way of lifting what is on it.

    `stretch` is the one worth naming: the scans are grey paper with grey ink
    and the histogram uses a third of its range, so the black point is put at
    the 2nd percentile of the ink and the white point at the 98th of the paper.
    """
    from PIL import Image, ImageOps
    import numpy as np
    if how == "none":
        return im
    if how == "autocontrast":
        return ImageOps.autocontrast(im, cutoff=1)
    if how == "equalize":
        return ImageOps.equalize(im)
    if how == "gamma":
        a = np.asarray(im, dtype=np.float32) / 255.0
        return Image.fromarray((np.power(a, 1.8) * 255).astype("uint8"))
    if how == "stretch":
        a = np.asarray(im, dtype=np.float32)
        lo, hi = np.percentile(a, 2), np.percentile(a, 98)
        if hi - lo < 1:
            return im
        a = np.clip((a - lo) * 255.0 / (hi - lo), 0, 255)
        return Image.fromarray(a.astype("uint8"))
    raise SystemExit(f"unknown variant {how}")


def one_page(eng, pdf: Path, page: int, wanted: list[str]) -> dict:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    img = page_image(pdf, page, ROOT / "data" / "pagecache")
    if img is None:
        return {"error": f"no page {page} in {pdf.name}"}
    small = eng._readable_copy(img)
    out = {}
    with Image.open(small) as opened:
        base = opened.convert("L")
        w, h = base.size
    for how in wanted:
        prepped = prepare(base, how)
        tmp = ROOT / "data" / "pagecache" / f"_faint_{how}.png"
        prepped.save(tmp)
        t0 = time.time()
        try:
            boxes = eng._detect(tmp, None)
        except Exception as e:
            out[how] = {"error": f"{type(e).__name__}: {e}"}
            continue
        # the heading line is read and handed back, exactly as the engine does
        # it: the detector's boxes carry no text, and a column measured from
        # boxes alone can never find the heading that names it
        labelled = eng._read_boxes(tmp, heading_lines(boxes, h))
        col = columns(boxes, w, h, labelled)
        geo = table(boxes, w, h, labelled=labelled)
        words = [f.get("text", "").strip() for f in labelled
                 if sum(c.isalpha() for c in f.get("text", "") or "") >= 3]
        out[how] = {"boxes": len(boxes),
                    "name_column": bool(col),
                    "rows": len(geo.rows) if geo else 0,
                    "headings_read": len(words),
                    "seconds": round(time.time() - t0, 1)}
        tmp.unlink(missing_ok=True)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pages", default="OL.PRJ.17851:1,OL.PRJ.17851:2",
                    help="notation:page, comma separated")
    ap.add_argument("--only", default=",".join(VARIANTS))
    ap.add_argument("--json", type=Path, default=ROOT / "data" / "spike_faint.json")
    a = ap.parse_args(argv)

    eng = PaddleEngine()
    eng._import()
    wanted = [v.strip() for v in a.only.split(",") if v.strip()]
    report = {}
    for spec in a.pages.split(","):
        notation, _, page = spec.strip().partition(":")
        stem = notation.split(".")[-1]
        pdf = next((p for p in (ROOT / "data" / "scans").rglob("*.pdf")
                    if stem in p.name), None)
        if pdf is None:
            print(f"no scan for {notation}")
            continue
        got = one_page(eng, pdf, int(page or 1), wanted)
        report[spec.strip()] = got
        if "error" in got:
            print(f"{spec.strip()}: {got['error']}")
            continue
        print(f"\n{spec.strip()}  ({pdf.name})")
        print("variant        boxes  name column  rows  headings  seconds")
        for how in wanted:
            d = got.get(how, {})
            if "error" in d:
                print(f"{how:<13}  {d['error']}")
                continue
            print(f"{how:<13}  {d['boxes']:<5}  {str(d['name_column']):<11}  "
                  f"{d['rows']:<4}  {d['headings_read']:<8}  {d['seconds']}")
    if a.json:
        a.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
