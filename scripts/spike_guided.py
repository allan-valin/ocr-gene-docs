"""Geometry-guided OCR: recognise the name column, attribute text by row band.

The full-page run scored a mean name CER of 0.31 at 110s/page, but it threw
away what this project already measures. Instead of recognising a whole page
and reassembling it:

  1. detect the grid (deskew, column rules, row comb)
  2. crop the *name column* — about 5% of the page area
  3. recognise that strip once
  4. assign each returned box to a row band by its y centre

Row attribution then holds by construction, so a name can no longer be scored
against a column header or a neighbouring row, and the recogniser works on a
fraction of the pixels.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from spike_ocr import cer  # noqa: E402


def load_engine():
    from paddleocr import PaddleOCR
    return PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False,
                     use_textline_orientation=False, enable_mkldnn=False, lang="pt")


def texts_and_boxes(result) -> list[tuple[str, float]]:
    """(text, y-centre) for every recognised box."""
    out = []
    for res in result:
        d = res.json.get("res", res.json) if hasattr(res, "json") else {}
        texts = d.get("rec_texts") or d.get("texts") or []
        polys = d.get("rec_polys") or d.get("dt_polys") or d.get("boxes") or []
        for i, t in enumerate(texts):
            if not t or not t.strip():
                continue
            y = None
            if i < len(polys):
                pts = polys[i]
                try:
                    ys = [p[1] for p in pts]
                    y = sum(ys) / len(ys)
                except Exception:
                    y = None
            out.append((t.strip(), y))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", type=Path,
                    default=ROOT / "data/scans/BR_RJANRIO_BS_0_RPV_ENT_017397_d0001de0001.pdf")
    ap.add_argument("--page", type=int, default=2)
    ap.add_argument("--pad", type=float, default=0.004, help="crop padding, page fraction")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "spike_guided.json")
    args = ap.parse_args(argv)

    from PIL import Image
    from page_geometry import analyze, page_image, ink_mask, trim_border, rotate_mask
    Image.MAX_IMAGE_PIXELS = None

    work = ROOT / "data" / "pagecache" / "spike"
    img_path = page_image(args.pdf, args.page, work)
    if img_path is None:
        print("no page image", file=sys.stderr)
        return 1

    t0 = time.time()
    geo = analyze(img_path)
    geom_s = time.time() - t0
    if not geo.rows or not geo.name_column(0):
        print("no grid detected on this page", file=sys.stderr)
        return 1

    # deskewed, full-resolution page, as the geometry describes it
    im = Image.open(img_path).convert("L")
    im = im.rotate(geo.skew, resample=Image.BICUBIC, fillcolor=255)
    W, H = im.size
    nx0, nx1 = geo.name_column(0)
    pad = args.pad
    x0 = max(0, int((nx0 - pad) * W)); x1 = min(W, int((nx1 + pad) * W))
    bands = geo.normalized_rows()
    y0 = max(0, int((bands[0][0] - pad) * H)); y1 = min(H, int((bands[-1][1] + pad) * H))
    strip = im.crop((x0, y0, x1, y1))
    strip_path = work / f"{args.pdf.stem}-p{args.page}-namecol.png"
    strip.save(strip_path)

    page_px = W * H
    strip_px = strip.width * strip.height
    print(f"page {W}x{H} = {page_px/1e6:.1f}MP   name column {strip.width}x{strip.height} "
          f"= {strip_px/1e6:.1f}MP  ({100*strip_px/page_px:.1f}% of the page)")

    ocr = load_engine()
    t1 = time.time()
    result = ocr.predict(str(strip_path))
    infer_s = time.time() - t1

    found = texts_and_boxes(result)
    # assign each box to a row band by its y centre, in page coordinates
    per_row: dict[int, list[str]] = {}
    for text, ycen in found:
        if ycen is None:
            continue
        page_y = (y0 + ycen) / H
        for i, (bt, bb) in enumerate(bands):
            if bt <= page_y <= bb:
                per_row.setdefault(i, []).append(text)
                break

    truth = json.loads((ROOT / "prototype" / "sample_rows.json").read_text(encoding="utf-8"))
    names = [f"{r['given']} {r['surname']}" for r in truth["rows"]]

    # bands include the header row and trailing blanks; align by offset search
    best_off, best_mean = 0, 1.0
    for off in range(0, 6):
        scores = []
        for k, n in enumerate(names):
            got = " ".join(per_row.get(k + off, []))
            scores.append(cer(n, got))
        m = sum(scores) / len(scores)
        if m < best_mean:
            best_off, best_mean = off, m

    detail = []
    for k, n in enumerate(names):
        got = " ".join(per_row.get(k + best_off, []))
        detail.append({"row": k + 1, "truth": n, "got": got, "cer": round(cer(n, got), 3)})

    exact = sum(1 for d in detail if d["cer"] == 0)
    usable = sum(1 for d in detail if d["cer"] <= 0.25)
    report = {
        "mode": "geometry-guided", "pdf": args.pdf.name, "page": args.page,
        "geometry_s": round(geom_s, 1), "inference_s": round(infer_s, 1),
        "page_megapixels": round(page_px / 1e6, 1),
        "strip_megapixels": round(strip_px / 1e6, 2),
        "strip_pct_of_page": round(100 * strip_px / page_px, 1),
        "band_offset": best_off, "boxes_found": len(found),
        "name_cer_mean": round(best_mean, 3),
        "names_exact": exact, "names_within_25pct": usable, "names_total": len(names),
    }
    args.out.write_text(json.dumps({**report, "detail": detail}, ensure_ascii=False, indent=2))

    print(f"\ngeometry       {report['geometry_s']}s")
    print(f"inference      {report['inference_s']}s  (full page was 110.7s)")
    print(f"name CER mean  {report['name_cer_mean']}  (full page was 0.31)")
    print(f"names exact    {exact}/{len(names)}  (full page was 2/26)")
    print(f"within 25% CER {usable}/{len(names)}  (full page was 12/26)")
    print("\nworst rows:")
    for d in sorted(detail, key=lambda x: -x["cer"])[:5]:
        print(f"   {d['cer']:.2f}  {d['truth']!r} -> {d['got']!r}")
    print(f"\nfull report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
