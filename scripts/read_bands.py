"""Read the engine's own crops with a second recogniser.

`export_bands.py` saved the images the engine read, named by the row number it
gave them. This reads the same images with another model, so the two readings
of a row need no alignment at all to be put beside each other -- which is what
the first attempt could not do, and why it reached only 28% of rows.

    .venv-htr/bin/python scripts/read_bands.py --bands DIR --out sidecar.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from PIL import Image


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bands", type=Path, required=True)
    ap.add_argument("--model",
                    default="Riksarkivet/trocr-base-handwritten-hist-swe-2")
    ap.add_argument("--batch", type=int, default=3)
    ap.add_argument("--beams", type=int, default=4)
    ap.add_argument("--processor", default=None,
                    help="where the image processor and tokenizer live, if "
                         "not beside the weights: `repo` or `repo#subfolder`")
    ap.add_argument("--pages", type=int, default=0,
                    help="stop after this many pages, for a quick look")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from spike_htr import run_trocr

    index = json.loads((args.bands / "bands.json").read_text(encoding="utf-8"))
    said: dict[str, dict] = {}
    if args.out.exists():
        try:
            was = json.loads(args.out.read_text(encoding="utf-8"))
            if was.get("model") == args.model:
                said = was.get("read") or {}
                print(f"resuming: {sum(len(v) for v in said.values())} pages")
        except ValueError:
            pass

    t0 = time.time()
    seen = 0
    for key, rows in index.items():
        if args.pages and seen >= args.pages:
            break
        doc, page = key.split("/")
        if not rows or str(page) in said.get(doc, {}):
            continue
        crops = []
        for r in rows:
            path = args.bands / r["file"]
            if path.exists():
                crops.append((r["n"], Image.open(path).convert("RGB")))
        if not crops:
            continue
        dt, got = run_trocr(crops, args.model, args.beams, args.batch,
                            args.processor)
        said.setdefault(doc, {})[str(page)] = {str(n): t for n, t in got.items()}
        args.out.write_text(json.dumps(
            {"model": args.model, "by": "row", "read": said},
            ensure_ascii=False, indent=2))
        seen += 1
        print(f"  {doc[:8]} p{page}: {len(crops)} crops in {dt:.0f}s", flush=True)
    print(f"wrote {args.out} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
