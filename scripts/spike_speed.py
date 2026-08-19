"""Where the 27 s/page goes, and what removes it.

The corpus this has to serve is on the order of 7,000 dossiers of ~10 pages.
At 37 s/page that is ~720 CPU-hours, so speed is not a refinement here — it
decides whether the tool can index a real archive at all.

Three levers are measured against the same page, so accuracy is visible next to
every speed claim:

  * oneDNN (mkldnn), which the spikes had switched off
  * a mobile recogniser instead of the medium one the defaults pick
  * skipping detection entirely: the grid already knows where the rows are, so
    each row band can be cropped and fed straight to the recogniser

Row attribution is by construction in the last case, which is also why it can
drop detection without losing the thing detection was buying.
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


def name_strip(pdf: Path, page: int, work: Path, pad: float = 0.004):
    """Deskewed name-column crop, plus its row bands in strip coordinates."""
    from PIL import Image
    from page_geometry import analyze, page_image
    Image.MAX_IMAGE_PIXELS = None

    img_path = page_image(pdf, page, work)
    if img_path is None:
        raise SystemExit("no page image")
    t0 = time.time()
    geo = analyze(img_path)
    geom_s = time.time() - t0
    if not geo.rows or not geo.name_column(0):
        raise SystemExit("no grid detected")

    im = Image.open(img_path).convert("L")
    im = im.rotate(geo.skew, resample=Image.BICUBIC, fillcolor=255)
    W, H = im.size
    nx0, nx1 = geo.name_column(0)
    bands = geo.normalized_rows()
    x0 = max(0, int((nx0 - pad) * W)); x1 = min(W, int((nx1 + pad) * W))
    y0 = max(0, int((bands[0][0] - pad) * H)); y1 = min(H, int((bands[-1][1] + pad) * H))
    strip = im.crop((x0, y0, x1, y1))
    # band edges relative to the strip, in pixels
    rel = [(int(bt * H) - y0, int(bb * H) - y0) for bt, bb in bands]
    return strip, rel, geom_s, (W, H)


def row_images(strip, rel, pad_px: int = 6, min_h: int = 12):
    """One image per row band — what the recogniser is actually meant to see."""
    out = []
    for i, (a, b) in enumerate(rel):
        a2 = max(0, a - pad_px); b2 = min(strip.height, b + pad_px)
        if b2 - a2 < min_h:
            continue
        out.append((i, strip.crop((0, a2, strip.width, b2))))
    return out


def score(per_row: dict[int, str], names: list[str]) -> dict:
    """Bands include the header and trailing blanks, so align by offset."""
    best_off, best_mean = 0, 1.0
    for off in range(0, 6):
        m = sum(cer(n, per_row.get(k + off, "")) for k, n in enumerate(names)) / len(names)
        if m < best_mean:
            best_off, best_mean = off, m
    detail = [{"truth": n, "got": per_row.get(k + best_off, ""),
               "cer": round(cer(n, per_row.get(k + best_off, "")), 3)}
              for k, n in enumerate(names)]
    return {
        "cer_mean": round(best_mean, 3),
        "exact": sum(1 for d in detail if d["cer"] == 0),
        "within_25pct": sum(1 for d in detail if d["cer"] <= 0.25),
        "total": len(names),
        "detail": detail,
    }


def run_pipeline(strip_path: Path, rel, det_model, rec_model, mkldnn, threads):
    """Full detect+recognise on the strip, boxes assigned to bands by y centre."""
    from paddleocr import PaddleOCR
    from spike_guided import texts_and_boxes
    kw = dict(use_doc_orientation_classify=False, use_doc_unwarping=False,
              use_textline_orientation=False, enable_mkldnn=mkldnn,
              cpu_threads=threads, lang="pt")
    if det_model:
        kw["text_detection_model_name"] = det_model
    if rec_model:
        kw["text_recognition_model_name"] = rec_model
    ocr = PaddleOCR(**kw)
    ocr.predict(str(strip_path))          # warm up; first call pays graph setup
    t0 = time.time()
    res = ocr.predict(str(strip_path))
    dt = time.time() - t0
    per: dict[int, list[str]] = {}
    for text, y in texts_and_boxes(res):
        if y is None:
            continue
        for i, (a, b) in enumerate(rel):
            if a <= y <= b:
                per.setdefault(i, []).append(text)
                break
    return dt, {i: " ".join(v).strip() for i, v in per.items()}


def run_reconly(strip, rel, rec_model, mkldnn, threads, batch_size=16):
    """No detection: the grid says where the rows are, so recognise them directly."""
    import numpy as np
    from paddleocr import TextRecognition
    rec = TextRecognition(model_name=rec_model, enable_mkldnn=mkldnn,
                          cpu_threads=threads)
    crops = row_images(strip, rel)
    arrs = [np.array(im.convert("RGB")) for _, im in crops]
    if arrs:
        list(rec.predict(arrs[:1]))       # warm up
    t0 = time.time()
    results = list(rec.predict(arrs, batch_size=batch_size))
    dt = time.time() - t0
    per: dict[int, str] = {}
    for (i, _), r in zip(crops, results):
        d = r.json.get("res", r.json) if hasattr(r, "json") else {}
        per[i] = (d.get("rec_text") or "").strip()
    return dt, per


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", type=Path,
                    default=ROOT / "data/scans/BR_RJANRIO_BS_0_RPV_ENT_017397_d0001de0001.pdf")
    ap.add_argument("--page", type=int, default=2)
    ap.add_argument("--threads", type=int, default=0, help="0 = paddle default")
    ap.add_argument("--only", default="", help="comma-separated variant names")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "spike_speed.json")
    args = ap.parse_args(argv)

    work = ROOT / "data" / "pagecache" / "speed"
    work.mkdir(parents=True, exist_ok=True)
    strip, rel, geom_s, (W, H) = name_strip(args.pdf, args.page, work)
    sp = work / f"{args.pdf.stem}-p{args.page}-namecol.png"
    strip.save(sp)
    truth = json.loads((ROOT / "prototype" / "sample_rows.json").read_text(encoding="utf-8"))
    names = [f"{r['given']} {r['surname']}" for r in truth["rows"]]
    threads = args.threads or None
    tkw = {"threads": threads} if threads else {"threads": None}

    print(f"page {W}x{H}  strip {strip.width}x{strip.height}  "
          f"{len(rel)} bands  geometry {geom_s:.1f}s\n")

    V6D, V6R = "PP-OCRv6_medium_det", "PP-OCRv6_medium_rec"
    V5D, V5R = "PP-OCRv5_mobile_det", "PP-OCRv5_mobile_rec"
    variants = [
        ("baseline",      lambda: run_pipeline(sp, rel, None, None, False, threads)),
        ("mkldnn",        lambda: run_pipeline(sp, rel, None, None, True, threads)),
        ("mobile+mkldnn", lambda: run_pipeline(sp, rel, V5D, V5R, True, threads)),
        ("reconly-v6",    lambda: run_reconly(strip, rel, V6R, True, threads)),
        ("reconly-v5",    lambda: run_reconly(strip, rel, V5R, True, threads)),
    ]
    wanted = {s.strip() for s in args.only.split(",") if s.strip()}
    report = {"pdf": args.pdf.name, "page": args.page, "geometry_s": round(geom_s, 2),
              "bands": len(rel), "threads": args.threads, "variants": {}}
    for label, fn in variants:
        if wanted and label not in wanted:
            continue
        try:
            dt, per = fn()
        except Exception as e:
            print(f"{label:16s} FAILED  {type(e).__name__}: {e}")
            report["variants"][label] = {"error": f"{type(e).__name__}: {e}"}
            continue
        s = score(per, names)
        total = dt + geom_s
        report["variants"][label] = {"infer_s": round(dt, 2), "page_s": round(total, 2),
                                     **{k: v for k, v in s.items() if k != "detail"},
                                     "detail": s["detail"]}
        print(f"{label:16s} infer {dt:6.1f}s   page {total:6.1f}s   "
              f"CER {s['cer_mean']:.3f}   ok {s['within_25pct']}/{s['total']}")
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    print(f"\nreport: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
