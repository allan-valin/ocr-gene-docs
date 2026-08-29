"""How well does a recogniser read the name column, page by page, against truth.

The geometry is settled — the crops now hold one whole name each — so what is
left is the recogniser. This cuts the rows the way the engine does, hands them
to whichever recogniser is being tried, and scores the reading against the
hand-read truth in `data/truth`.

    .venv-ocr/bin/python scripts/bench_rec.py                       # the engine as configured
    .venv-ocr/bin/python scripts/bench_rec.py --shape 3x64x960      # a wider input
    .venv-ocr/bin/python scripts/bench_rec.py --model PP-OCRv5_mobile_rec

CER is reported because it ranks variants, and retrieval because it is what the
tool is for: a name is *findable* when its reading still scores above the search
floor against what somebody would type.
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from desembarque import engine_paddle as ep          # noqa: E402
from desembarque.identity import cached_hash          # noqa: E402
from desembarque.search import similarity             # noqa: E402
from page_geometry import page_image                  # noqa: E402


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


def cer(truth: str, got: str) -> float:
    t, g = fold(truth), fold(got)
    if not t:
        return 0.0 if not g else 1.0
    same = sum(b.size for b in difflib.SequenceMatcher(None, t, g).get_matching_blocks())
    return max(0.0, min(1.0, 1 - same / max(len(t), len(g))))


def truths() -> list[dict]:
    out = []
    for f in sorted((ROOT / "data" / "truth").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("names"):
            out.append(d)
    return out


def deslant(im):
    """The crop sheared upright, by the average slope of its ink.

    Cursive leans, and a recogniser trained on print has no reason to know it.
    The shear is estimated the classical way — the horizontal offset between
    the ink's centre of mass at the top of the band and at the bottom — and
    applied to the whole crop.
    """
    from PIL import Image
    import statistics
    g = im.convert("L")
    w, h = g.size
    px = g.load()
    rows = []
    for y in range(h):
        xs = [x for x in range(w) if px[x, y] < 128]
        if xs:
            rows.append((y, statistics.fmean(xs)))
    if len(rows) < 4:
        return im
    ys = [y for y, _c in rows]
    cs = [c for _y, c in rows]
    spread = max(ys) - min(ys)
    if spread < 4:
        return im
    top = statistics.fmean([c for y, c in rows if y < min(ys) + spread / 3])
    bottom = statistics.fmean([c for y, c in rows if y > max(ys) - spread / 3])
    shear = (top - bottom) / spread
    if abs(shear) < 0.05 or abs(shear) > 1.0:
        return im
    # PIL maps output back to input: source_x = x - shear*y + offset, which is
    # the inverse of the lean measured above. The canvas is widened by what the
    # shear moves, and the offset keeps the ink inside it whichever way it
    # leans.
    offset = 0.0 if shear > 0 else shear * h
    return im.transform((int(w + abs(shear) * h), h), Image.AFFINE,
                        (1, -shear, offset, 0, 1, 0),
                        resample=Image.BICUBIC, fillcolor=255)


def _cv(im):
    import numpy as np
    return np.asarray(im.convert("L"), dtype=np.uint8)


def _pil(a):
    from PIL import Image
    return Image.fromarray(a)


def background_divided(im):
    """The crop divided by its own background, which is what fading is.

    A scan of a hundred-year-old sheet is not uniformly dark: the paper browns
    unevenly, the ink fades where the pen ran dry, and one global contrast
    curve for the whole crop — which is what `autocontrast` is — has to serve
    the darkest corner and the faintest stroke at once. Dividing by a heavily
    blurred copy of the crop removes the paper and leaves the ink, whatever the
    paper was doing locally. It is the standard first move on a faded document
    and it had never been tried here.
    """
    import cv2
    import numpy as np
    a = _cv(im).astype(np.float32)
    k = max(15, (min(a.shape) // 2) * 2 + 1)
    bg = cv2.GaussianBlur(a, (k, k), 0) + 1.0
    out = np.clip(a * 255.0 / bg, 0, 255)
    return _pil(out.astype(np.uint8))


def clahe(im, clip: float = 2.0, tile: int = 8):
    """Contrast lifted tile by tile rather than over the whole crop."""
    import cv2
    a = _cv(im)
    grid = (max(2, min(tile, a.shape[1] // 8 or 2)),
            max(2, min(tile, a.shape[0] // 8 or 2)))
    return _pil(cv2.createCLAHE(clipLimit=clip, tileGridSize=grid).apply(a))


def adaptive(im, block: int = 31, c: int = 15):
    """Black and white, thresholded against the local paper."""
    import cv2
    a = _cv(im)
    b = max(3, min(block, (min(a.shape) // 2) * 2 - 1))
    if b % 2 == 0:
        b += 1
    return _pil(cv2.adaptiveThreshold(a, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                      cv2.THRESH_BINARY, b, c))


def prepared(recognize, how: str):
    """The engine's recogniser with every crop put through `how` first."""
    from PIL import Image, ImageOps

    def prep(im):
        if how == "autocontrast":
            return ImageOps.autocontrast(im.convert("L"), cutoff=1)
        if how == "upscale2":
            return im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
        if how == "sharpen":
            from PIL import ImageFilter
            return im.filter(ImageFilter.UnsharpMask(radius=2, percent=150))
        if how == "deslant":
            return deslant(im)
        if how == "bgdiv":
            return background_divided(im)
        if how == "clahe":
            return clahe(im)
        if how == "bgdiv_clahe":
            return clahe(background_divided(im))
        if how == "bgdiv_up2":
            out = background_divided(im)
            return out.resize((out.width * 2, out.height * 2), Image.LANCZOS)
        if how == "adaptive":
            return adaptive(im)
        if how == "bgdiv_adaptive":
            return adaptive(background_divided(im))
        return im

    if how == "none":
        return recognize
    return lambda crops: recognize([prep(c) for c in crops])


def read_page(eng, pdf: Path, page: int, prep: str = "none") -> tuple[list[str], float]:
    """The name column of one page, row by row, as this engine reads it."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    img = page_image(pdf, page, ROOT / "data" / "pagecache")
    t0 = time.time()
    geo = eng._printed_table(img)
    source = "printing"
    if geo is None:
        from page_geometry import analyze
        geo = analyze(img)
        source = "rules"
    if not geo.rows or not geo.name_column(0):
        return [], time.time() - t0
    im = Image.open(img).convert("L")
    im = im.rotate(geo.skew, resample=Image.BICUBIC, fillcolor=255)
    rows = ep.rows_from_bands(geo, im.size, prepared(eng._recognize, prep),
                              eng._carved_crops(im, geo))
    print(f"    measured from the {source}: {len(rows)} rows")
    return [r.get("name_raw") or "" for r in rows], time.time() - t0


def align(names: list[str], truth: list[str]) -> int:
    """Where the truth block starts among the rows the engine produced.

    Not a stored row number. `data/truth/BS_ENT_014541-p2.json` records
    `first_row: 4` because the comb that read it in July put six passengers on
    rows four to nine; measured from the printing they are rows one to six, and
    a stored offset would score the right reading as a total failure. The offset
    is chosen as the one that fits best, which is also what a person comparing
    the two lists would do.
    """
    if not names:
        return 0
    best, best_cost = 0, None
    for off in range(0, max(1, len(names) - len(truth) + 1)):
        cost = sum(cer(w, names[off + i] if off + i < len(names) else "")
                   for i, w in enumerate(truth))
        if best_cost is None or cost < best_cost:
            best, best_cost = off, cost
    return best


def score(names: list[str], truth: list[str], first: int) -> dict:
    """Truth row i against whatever the engine put on that row."""
    first = align(names, truth) + 1
    hits, cers, found = 0, [], 0
    for i, want in enumerate(truth):
        got = names[first - 1 + i] if 0 <= first - 1 + i < len(names) else ""
        c = cer(want, got)
        cers.append(c)
        if c == 0:
            hits += 1
        # what search does with it: the reading against the name somebody types
        if similarity(want, got) >= 0.10:
            found += 1
    return {"rows": len(truth), "exact": hits, "findable": found,
            "cer": round(sum(cers) / len(cers), 3)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default=ep.DEFAULT_REC)
    ap.add_argument("--shape", default="x".join(str(n) for n in ep.REC_INPUT_SHAPE),
                    help="recogniser input as CxHxW, e.g. 3x64x960")
    ap.add_argument("--prep", default="none",
                    choices=("none", "autocontrast", "upscale2", "sharpen",
                             "deslant"),
                    help="what to do to each crop before it is recognised")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    ep.REC_INPUT_SHAPE = tuple(int(n) for n in args.shape.split("x"))
    eng = ep.PaddleEngine(rec_model=args.model)
    eng._import()

    print(f"{args.model}, input {ep.REC_INPUT_SHAPE}, crops {args.prep}")
    report = []
    for t in truths():
        pdf = ROOT / "data" / "scans" / t["pdf"]
        if not pdf.exists():
            print(f"  {t['pdf']}: not in data/scans, skipped")
            continue
        print(f"  {t['pdf']} p{t['page']}")
        names, secs = read_page(eng, pdf, t["page"], prep=args.prep)
        s = score(names, t["names"], t.get("first_row", 1))
        s.update(page=f"{t['pdf']}#{t['page']}", seconds=round(secs, 1))
        report.append(s)
        print(f"    CER {s['cer']:.3f} | exact {s['exact']}/{s['rows']} | "
              f"findable {s['findable']}/{s['rows']} | {s['seconds']}s")
        first = align(names, t["names"]) + 1
        for i, want in enumerate(t["names"][:6]):
            j = first - 1 + i
            got = names[j] if 0 <= j < len(names) else ""
            print(f"      {want!r} -> {got!r}")
    if report:
        n = sum(r["rows"] for r in report)
        print(f"\nover {n} rows: CER {sum(r['cer'] * r['rows'] for r in report) / n:.3f} | "
              f"exact {sum(r['exact'] for r in report)}/{n} | "
              f"findable {sum(r['findable'] for r in report)}/{n}")
    if args.out:
        args.out.write_text(json.dumps({"model": args.model,
                                        "shape": ep.REC_INPUT_SHAPE,
                                        "pages": report}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
