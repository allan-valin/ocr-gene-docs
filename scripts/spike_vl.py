"""PaddleOCR-VL against the recogniser, on the pages the corpus actually has.

The 26/26 retrieval result came from a *typed* passenger list. Most of the
archive is handwritten, and there the small recogniser returns things like
"Guudo Camtadore" — legible enough to know it failed, not enough to find
anyone. This measures whether the vision-language model reads what the
recogniser cannot, and what that costs per page.

It runs on the name-column strip, not the whole page, so both engines are
asked the same question.
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

TYPED = ROOT / "data/scans/BR_RJANRIO_BS_0_RPV_ENT_017397_d0001de0001.pdf"


def strip_for(pdf: Path, page: int, work: Path):
    from spike_speed import name_strip
    strip, rel, geom_s, size = name_strip(pdf, page, work)
    out = work / f"{pdf.stem}-p{page}-vl.png"
    strip.save(out)
    return out, len(rel), geom_s


def vl_text(image: Path, ocr) -> list[str]:
    res = ocr.predict(str(image))
    lines = []
    for r in res:
        d = r.json.get("res", r.json) if hasattr(r, "json") else {}
        md = d.get("markdown") or {}
        text = md.get("text") if isinstance(md, dict) else None
        if text:
            lines.extend(t.strip() for t in str(text).splitlines() if t.strip())
            continue
        for blk in d.get("parsing_res_list") or []:
            t = (blk.get("block_content") or "").strip()
            if t:
                lines.extend(x.strip() for x in t.splitlines() if x.strip())
    return lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", type=Path, action="append", default=None,
                    help="repeatable; defaults to the typed page plus a handwritten one")
    ap.add_argument("--page", type=int, default=2)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "spike_vl.json")
    args = ap.parse_args(argv)

    pdfs = args.pdf or [TYPED]
    work = ROOT / "data" / "pagecache" / "vl"
    work.mkdir(parents=True, exist_ok=True)

    from paddleocr import PaddleOCRVL
    t0 = time.time()
    ocr = PaddleOCRVL(vl_rec_backend="native")
    load_s = time.time() - t0
    print(f"model loaded in {load_s:.0f}s", file=sys.stderr)

    report = {"load_s": round(load_s, 1), "pages": []}
    for pdf in pdfs:
        try:
            img, bands, geom_s = strip_for(pdf, args.page, work)
        except SystemExit as e:
            print(f"{pdf.name}: {e}", file=sys.stderr)
            continue
        t1 = time.time()
        lines = vl_text(img, ocr)
        dt = time.time() - t1
        print(f"\n=== {pdf.name} p{args.page}  {bands} bands  "
              f"VL {dt:.0f}s (geometry {geom_s:.1f}s)")
        for ln in lines[:30]:
            print("   ", ln)
        report["pages"].append({"pdf": pdf.name, "page": args.page, "bands": bands,
                                "vl_s": round(dt, 1), "lines": lines})
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nreport: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
