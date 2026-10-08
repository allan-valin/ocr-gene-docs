"""Throwaway spike (2026-10-08): the engine's own recogniser on kraken's lines.

`spike_fullpage.py` showed kraken's page segmenter finds every row of a page
with coordinates, and McFondue reads those lines no better than the engine
reads its own bands. The half it did not test: the *engine's* recogniser
(PP-OCRv6) on those lines. On a cursive page the engine's bands are a
uniform grid with slivers and duplicates (BS.ENT.016317 p4), so a crop often
straddles two rows; a segmenter's line follows the ink. If the recogniser
reads better off the line, the row cut is the lever, not the model.

Reads the lines in `<prefix>-lines.json`, clipped to the stored name column,
and writes `<prefix>-engine.json` keyed to the engine's bands by overlap, so
`bench_search.py --second-opinion` scores it through the index.

    .venv-ocr/bin/python scripts/spike_engine_on_lines.py \\
        --lines data/fullpage-heldout-lines.json --records data/transcriptions
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from spike_fullpage import chosen_image   # noqa: E402

PAD = 4


def band_for(line: dict, bands: list[tuple[float, float]]) -> int | None:
    yc = (line["y0"] + line["y1"]) / 2
    best, best_ov = None, 0.0
    for n, (a, b) in enumerate(bands, start=1):
        ov = min(b, line["y1"]) - max(a, line["y0"])
        if ov > best_ov and a <= yc <= b:
            best, best_ov = n, ov
    return best


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lines", type=Path, required=True)
    ap.add_argument("--records", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    out = a.out or a.lines.with_name(a.lines.name.replace("-lines.json", "-engine.json"))

    from PIL import Image
    from desembarque.engine_paddle import PaddleEngine
    Image.MAX_IMAGE_PIXELS = None
    eng = PaddleEngine()
    eng._import()

    raw = json.loads(a.lines.read_text(encoding="utf-8"))
    by_hash = {}
    for f in a.records.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        by_hash[d.get("hash")] = d
    read: dict[str, dict] = {}
    began = time.time()
    for doc, pages in raw.items():
        rec = by_hash.get(doc)
        if not rec:
            print(f"  {doc[:8]}: no record, skipped")
            continue
        for page, lines in pages.items():
            geo = next((p.get("geometry") for p in rec.get("pages") or ()
                        if str(p.get("n")) == page), None) or {}
            cols = geo.get("columns") or []
            x0, x1 = (cols[0], cols[1]) if len(cols) >= 2 else (0.05, 0.35)
            bands = [tuple(b) for b in geo.get("rows") or [] if b and len(b) == 2]
            img = chosen_image(a.work, rec["file"], int(page))
            if img is None:
                print(f"  {doc[:8]} p{page}: no image, skipped")
                continue
            im = Image.open(img).convert("RGB")
            W, H = im.size
            crops, keys = [], []
            for line in lines:
                if line["x1"] < x0 or line["x0"] > x1:
                    continue
                n = band_for(line, bands)
                if n is None:
                    continue
                lx0, lx1 = max(line["x0"], x0), min(line["x1"], x1)
                if lx1 - lx0 < 0.01:
                    continue
                box = (int(lx0 * W) - PAD, int(line["y0"] * H) - PAD,
                       int(lx1 * W) + PAD, int(line["y1"] * H) + PAD)
                crops.append(im.crop(box))
                keys.append(n)
            said = eng._recognize(crops)
            got: dict[str, str] = {}
            for n, (text, _score) in zip(keys, said):
                if text:
                    got[str(n)] = (got.get(str(n), "") + " " + text).strip()
            read.setdefault(doc, {})[page] = got
            print(f"  {rec['file'][16:28]} p{page}: {len(crops)} line crops, "
                  f"{len(got)} bands read", flush=True)
    out.write_text(json.dumps({"model": "PP-OCRv6-on-kraken-lines", "by": "row",
                               "variant": "line-column", "read": read},
                              ensure_ascii=False))
    print(f"wrote {out} in {time.time() - began:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
