"""Throwaway spike: what do pretrained handwriting models give with no training?

The engine that ships reads a cursive name as `Guudo Camtadore` (CER 0.205),
which fuzzy search rescues at three thousand rows and will not rescue at
seventy thousand. Before labelling a training set, the cheap question is
whether somebody has already trained the model we need.

This runs pretrained HTR models over *exactly* the crops the shipping engine
uses -- same geometry, same row bands, same `refine()` trim -- and scores them
with the same CER against the same hand-read truth. Anything else would be
comparing two pipelines rather than two recognisers.

Not intended to be kept. If a model wins here it earns a real integration; if
none does, the answer is that this archive needs its own training data.

    .venv-htr/bin/python scripts/spike_htr.py --model microsoft/trocr-base-handwritten
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

from spike_ocr import cer  # noqa: E402
from spike_speed import name_strip, refine, row_images, score  # noqa: E402

DEFAULT_TRUTH = ROOT / "data" / "truth" / "BS_ENT_014541-p2.json"


def load_truth(path: Path) -> tuple[Path, int, list[str]]:
    d = json.loads(path.read_text())
    pdf = ROOT / "data" / "scans" / d["pdf"]
    return pdf, int(d["page"]), list(d["names"])


def crops_for(pdf: Path, page: int, work: Path, target_h: int):
    """The row-band images the engine would hand its recogniser."""
    strip, rel, _geom_s, _size = name_strip(pdf, page, work)
    out = []
    for i, im in row_images(strip, rel):
        out.append((i, refine(im, target_h).convert("RGB")))
    return out


def run_trocr(crops, model_id: str, beams: int, batch: int):
    """TrOCR is an encoder-decoder: an image in, a text sequence out."""
    import torch
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel

    torch.set_grad_enabled(False)
    proc = TrOCRProcessor.from_pretrained(model_id)
    model = VisionEncoderDecoderModel.from_pretrained(model_id)
    model.eval()

    said: dict[int, str] = {}
    t0 = time.time()
    for k in range(0, len(crops), batch):
        chunk = crops[k:k + batch]
        px = proc(images=[im for _, im in chunk], return_tensors="pt").pixel_values
        ids = model.generate(px, num_beams=beams, max_new_tokens=32)
        for (i, _), text in zip(chunk, proc.batch_decode(ids, skip_special_tokens=True)):
            said[i] = (text or "").strip()
    return time.time() - t0, said


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="microsoft/trocr-base-handwritten")
    ap.add_argument("--truth", type=Path, default=DEFAULT_TRUTH)
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--target-h", type=int, default=64,
                    help="upscale short bands; TrOCR wants 384x384 anyway")
    ap.add_argument("--beams", type=int, default=4)
    ap.add_argument("--batch", type=int, default=6)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "spike_htr.json")
    args = ap.parse_args()

    pdf, page, names = load_truth(args.truth)
    if not pdf.exists():
        raise SystemExit(f"scan not found: {pdf}")

    args.work.mkdir(parents=True, exist_ok=True)
    crops = crops_for(pdf, page, args.work, args.target_h)
    print(f"{len(crops)} row bands from {pdf.name} p{page}", flush=True)

    dt, said = run_trocr(crops, args.model, args.beams, args.batch)
    res = score(said, names)
    res.update(model=args.model, seconds=round(dt, 1),
               seconds_per_row=round(dt / max(1, len(crops)), 2),
               rows=len(crops), beams=args.beams)

    print(json.dumps(res, ensure_ascii=False, indent=2))
    prev = json.loads(args.out.read_text()) if args.out.exists() else []
    prev.append(res)
    args.out.write_text(json.dumps(prev, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
