"""Throwaway spike (2026-10-09): another recogniser on the lines kraken found.

`spike_fullpage.py` left the held-out pages' lines on disk with their boxes
(`<prefix>-lines.json`), so a second model can read the same ink without
segmenting the page again -- segmentation is the 12 s, recognition the 2.
The question is Allan's: a model trained on the clerk's own script (German
Kurrent for a Hamburg list, Dutch for a Royal Holland Lloyd one) might read a
hand McFondue cannot. Writes `<out>-column.json`, keyed to the engine's bands
exactly as the spike's sidecar is, so `bench_search.py --held-out
--second-opinion` scores it.

    .venv-kraken/bin/python scripts/spike_lines_model.py \\
        --lines data/fullpage-heldout15-lines.json \\
        --model ~/.cache/kraken/german_handwriting.mlmodel \\
        --out data/fullpage-heldout15-german
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

from spike_fullpage import chosen_image, onto_bands  # noqa: E402


def bbox_segmentation(lines: list[dict], width: int, height: int, imagename: str):
    """The stored line boxes as a kraken bbox segmentation, in pixels."""
    from kraken.containers import BBoxLine, Segmentation
    boxes = [BBoxLine(id=f"l{i}", bbox=(int(l["x0"] * width), int(l["y0"] * height),
                                       int(l["x1"] * width), int(l["y1"] * height)))
             for i, l in enumerate(lines)]
    return Segmentation(type="bbox", imagename=imagename, text_direction="horizontal-lr",
                        script_detection=False, lines=boxes)


def segmentation_of(lines: list[dict], width: int, height: int, imagename: str):
    """Lines stored with their polygon read as baseline lines, the shape the
    segmenter found; lines stored as boxes alone fall back to boxes, which
    catch the neighbours' ink and read badly on a crowded page."""
    from kraken.containers import BaselineLine, Segmentation
    if not all(l.get("boundary") and l.get("baseline") for l in lines):
        return bbox_segmentation(lines, width, height, imagename)
    recs = [BaselineLine(id=f"l{i}",
                         baseline=[(int(x * width), int(y * height)) for x, y in l["baseline"]],
                         boundary=[(int(x * width), int(y * height)) for x, y in l["boundary"]])
            for i, l in enumerate(lines)]
    return Segmentation(type="baselines", imagename=imagename, text_direction="horizontal-lr",
                        script_detection=False, lines=recs)


def load_recogniser(path: Path, device: str = "cpu"):
    """A kraken recogniser from either generation of weights: `.safetensors`
    (kraken >= 7.1, the PP-OCRv6 base models among them) through
    `kraken.models.load_models`, anything else through the CoreML loader."""
    if path.suffix == ".safetensors":
        from kraken.models import load_models
        return load_models(path, tasks=["recognition"])[0]
    from kraken.lib import models
    return models.load_any(str(path), device=device)


def predictions(model, im, seg, pad: int, device: str = "cpu"):
    """Records for every line of `seg`, from a 7.1 model's `.predict` or the
    older `rpred` -- both yield records with a prediction and cuts."""
    if hasattr(model, "prepare_for_inference"):
        from kraken.configs import RecognitionInferenceConfig
        from kraken.ketos.util import to_ptl_device
        accelerator, devices = to_ptl_device(device)
        model.prepare_for_inference(RecognitionInferenceConfig(
            padding=pad, accelerator=accelerator, device=devices, num_line_workers=0))
        return model.predict(im, seg)
    from kraken import rpred
    return rpred.rpred(model, im, seg, pad=pad)


def reread(im, lines: list[dict], model, pad: int = 8, device: str = "cpu") -> list[dict]:
    seg = segmentation_of(lines, im.width, im.height, "page")
    out = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for rec, line in zip(predictions(model, im, seg, pad, device), lines):
            cuts = []
            for cut in rec.cuts:
                pts = cut if isinstance(cut[0], (list, tuple)) else [cut]
                cuts.append(sum(p[0] for p in pts) / len(pts) / im.width)
            out.append({**line, "text": unicodedata.normalize("NFC", rec.prediction),
                        "cuts": cuts})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lines", type=Path, required=True)
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--records", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)

    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    model = load_recogniser(a.model, a.device)
    by_hash = {}
    for f in a.records.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        by_hash[d.get("hash")] = d
    raw = json.loads(a.lines.read_text(encoding="utf-8"))
    col_side, began = {}, time.time()
    for doc, pages in raw.items():
        rec = by_hash.get(doc)
        if not rec:
            continue
        for page, lines in pages.items():
            img = chosen_image(a.work, rec["file"], int(page))
            if img is None:
                continue
            geo = next((p.get("geometry") for p in rec.get("pages") or ()
                        if str(p.get("n")) == page), None) or {}
            im = Image.open(img).convert("L")
            said = reread(im, lines, model, device=a.device)
            _by_line, by_col = onto_bands(said, geo)
            col_side.setdefault(doc, {})[page] = by_col
            print(f"  {rec['file'][16:28]} p{page}: {len(by_col)} bands", flush=True)
    tag = a.model.stem
    p = a.out.with_name(a.out.name + "-column.json")
    p.write_text(json.dumps({"model": f"{tag}-page-column", "by": "row",
                             "variant": "column", "read": col_side}, ensure_ascii=False))
    print(f"wrote {p} in {time.time() - began:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
