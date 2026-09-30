"""Throwaway spike: does a kraken model built for historical hands read this ink?

Every recogniser measured here so far was a TrOCR variant, a PaddleOCR model
or a vision-language model. Kraken is a fourth class -- a CTC line recogniser
trained by archives on their own hands, Apache-2.0, and an order of magnitude
cheaper a row than any VLM. McCATMuS is its model for Latin-script handwriting
from the 16th to the 21st century in French, Spanish, Italian, Latin, English
and German, which is the closest published prior to this archive's clerks.

It reads exactly the labelled crops of `data/trainset-fair`, the same picture
every other recogniser was handed, and writes the sidecar `score_crops.py`
scores so the number lands in the same table as CHURRO's and Qwen's:

    .venv-kraken/bin/python scripts/spike_kraken.py \\
        --model ~/.cache/kraken/McCATMuS_nfd_nofix_V1.mlmodel
    .venv/bin/python scripts/score_crops.py --sidecar data/kraken-rows.json \\
        --trainset data/trainset-fair
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from read_vlm import rows_from  # noqa: E402


def load(model_path: Path):
    from kraken.lib import models
    return models.load_any(str(model_path))


def read_line(model, image_path: Path, pad: int) -> str:
    """One crop is one line: no segmentation, the box is the whole picture."""
    from PIL import Image, ImageOps
    from kraken import rpred
    from kraken.containers import BBoxLine, Segmentation

    im = Image.open(image_path).convert("L")
    if pad:
        im = ImageOps.expand(im, border=pad, fill=255)
    w, h = im.size
    # the model was trained on baselines, and handing it a box degrades it;
    # a synthesised baseline a quarter up from the crop's bottom edge, the
    # box as its polygon, is what kraken itself casts a box to
    # inset a pixel: a polygon on the image's own edge is "outside" to kraken
    line = BBoxLine(id="row", bbox=(1, 1, w - 2, h - 2)).to_baseline()
    seg = Segmentation(type="baselines", imagename=str(image_path),
                       text_direction="horizontal-lr", script_detection=False,
                       lines=[line], regions={}, line_orders=[])
    out = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for rec in rpred.rpred(model, im, seg):
            out.append(rec.prediction)
    # the model writes NFD; the labels and the index are NFC
    return unicodedata.normalize("NFC", " ".join(out)).strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--trainset", type=Path, default=ROOT / "data" / "trainset-fair")
    ap.add_argument("--hand", default="", help="cursive | typed | '' for all")
    ap.add_argument("--rows", type=int, default=0)
    ap.add_argument("--pad", type=int, default=8,
                    help="white border around the crop, px; a CTC model wants "
                         "a little air above and below the line")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "kraken-rows.json")
    a = ap.parse_args(argv)

    model = load(a.model)
    rows = rows_from(a.trainset, a.rows, hand=a.hand)
    read: dict[str, dict] = {}
    times = []
    for i, row in enumerate(rows, 1):
        began = time.time()
        said = read_line(model, a.trainset / row["image"], a.pad)
        times.append(time.time() - began)
        read.setdefault(row["doc"], {}).setdefault(str(row["page"]), {})[
            str(row["n"])] = said
        print(f"  {i}/{len(rows)} {times[-1]:5.2f}s  {said[:40]!r}"
              f"   (label {row['label'][:30]!r})", flush=True)
    total = sum(times)
    tag = a.model.stem + (f"-pad{a.pad}" if a.pad else "")
    a.out.write_text(json.dumps({"model": tag, "by": "row", "read": read,
                                 "seconds": total, "rows": len(times),
                                 "seconds_per_row": total / max(1, len(times))},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(times)} rows in {total / 60:.1f} min — "
          f"{total / max(1, len(times)):.2f} s a row. Wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
