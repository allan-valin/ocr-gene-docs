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

    .venv-ocr/bin/python scripts/spike_kraken.py \\
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

from read_vlm import rows_from, whole_documents  # noqa: E402


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


class Reader:
    """What `read_vlm.whole_documents` asks of a server, answered by kraken.

    The VLM runner reads a document page by page, cutting each row from the
    geometry the record stores and handing the picture to `server.read`.
    Kraken is not a server, but it can answer the same question, so the
    held-out pages are read by it exactly as they were read by the VLMs.
    """

    def __init__(self, model, pad: int, read_line=None):
        self.model, self.pad, self.system = model, pad, None
        self._read = read_line or globals()["read_line"]

    def read(self, image: Path, prompt: str, predict: int = 64) -> tuple[str, float]:
        began = time.time()
        return self._read(self.model, Path(image), self.pad), time.time() - began


def document_args(out: Path, pages_json: Path | None = None, hand: str = "",
                  documents_limit: int = 1, pages_limit: int = 0,
                  records: Path | None = None) -> argparse.Namespace:
    """The arguments `whole_documents` reads off the VLM runner's parser."""
    return argparse.Namespace(
        hands=ROOT / "data" / "hands.json", out=out, pages_json=pages_json,
        scans=ROOT / "data" / "scans", records=records or ROOT / "data" / "transcriptions",
        work=ROOT / "data" / "pagecache", hand=hand,
        documents_limit=documents_limit, pages_limit=pages_limit)


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
    ap.add_argument("--documents", action="store_true",
                    help="read whole documents out of the corpus instead of "
                         "the labelled crops, as read_vlm.py --documents does")
    ap.add_argument("--pages-json", type=Path, default=None,
                    help="the exact pages to read, as the reading sheet lists them")
    ap.add_argument("--records", type=Path, default=None)
    ap.add_argument("--documents-limit", type=int, default=1)
    ap.add_argument("--pages-limit", type=int, default=0)
    a = ap.parse_args(argv)

    model = load(a.model)
    tag = a.model.stem + (f"-pad{a.pad}" if a.pad else "")
    if a.documents:
        ns = document_args(a.out, a.pages_json, a.hand, a.documents_limit,
                           a.pages_limit, a.records)
        return whole_documents(Reader(model, a.pad), ns, tag, prompt="")
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
    a.out.write_text(json.dumps({"model": tag, "by": "row", "read": read,
                                 "seconds": total, "rows": len(times),
                                 "seconds_per_row": total / max(1, len(times))},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(times)} rows in {total / 60:.1f} min — "
          f"{total / max(1, len(times)):.2f} s a row. Wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
