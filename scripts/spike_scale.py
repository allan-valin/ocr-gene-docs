"""Retrieval at scale: can a name still be found among rows from many pages?

The single-page result (26/26 ranked first) had only 25 distractors. This pools
the OCR'd name column of every tabular page it can find, then queries the known
Gelria names against the whole pool. That is the number that decides whether the
small recogniser is enough, or whether a larger model is needed.
"""
from __future__ import annotations

import json
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from page_geometry import analyze_pdf_page  # noqa: E402
from desembarque import pdf as pdflib       # noqa: E402


def fold(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


def tri(s):
    p = "  " + fold(s) + " "
    return {p[i:i + 3] for i in range(len(p) - 2)}


def sim(a, b):
    A, B = tri(a), tri(b)
    if not A or not B:
        return 0.0
    n = len(A & B)
    return n / (len(A) + len(B) - n)


def main() -> int:
    from PIL import Image
    from paddleocr import PaddleOCR
    from spike_guided import texts_and_boxes
    Image.MAX_IMAGE_PIXELS = None

    work = ROOT / "data" / "pagecache" / "scale"
    work.mkdir(parents=True, exist_ok=True)
    ocr = PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False,
                    use_textline_orientation=False, enable_mkldnn=False, lang="pt")

    pool: list[dict] = []
    t_all = time.time()
    pdfs = sorted(Path(ROOT / "data/scans").glob("BR_RJANRIO_BS_*.pdf"))[:14]
    for pdf in pdfs:
        for pg in range(2, min(pdflib.page_count(pdf), 4) + 1):
            try:
                geo = analyze_pdf_page(pdf, pg, work)
            except Exception:
                continue
            if not geo or len(geo.rows) < 10 or not geo.name_column(0):
                continue
            img = None
            from page_geometry import page_image
            img = page_image(pdf, pg, work)
            if img is None:
                continue
            im = Image.open(img).convert("L").rotate(geo.skew, resample=Image.BICUBIC, fillcolor=255)
            W, H = im.size
            nx0, nx1 = geo.name_column(0)
            bands = geo.normalized_rows()
            x0, x1 = max(0, int((nx0 - .004) * W)), min(W, int((nx1 + .004) * W))
            y0, y1 = max(0, int((bands[0][0] - .004) * H)), min(H, int((bands[-1][1] + .004) * H))
            strip = im.crop((x0, y0, x1, y1))
            sp = work / f"{pdf.stem}-p{pg}-col.png"
            strip.save(sp)
            t0 = time.time()
            res = ocr.predict(str(sp))
            dt = time.time() - t0
            per: dict[int, list[str]] = {}
            for text, yc in texts_and_boxes(res):
                if yc is None:
                    continue
                py = (y0 + yc) / H
                for i, (bt, bb) in enumerate(bands):
                    if bt <= py <= bb:
                        per.setdefault(i, []).append(text)
                        break
            for i, parts in per.items():
                txt = " ".join(parts).strip()
                if len(fold(txt)) >= 4:
                    pool.append({"doc": pdf.name, "page": pg, "row": i, "text": txt})
            print(f"  {pdf.stem[-16:]} p{pg}: {len(per)} rows, {dt:.0f}s", file=sys.stderr)
            break  # one tabular page per dossier is enough for a distractor pool

    truth = json.loads((ROOT / "prototype" / "sample_rows.json").read_text(encoding="utf-8"))
    names = [f"{r['given']} {r['surname']}" for r in truth["rows"]]
    gelria = [p for p in pool if "017397" in p["doc"]]

    rank1 = top5 = 0
    misses = []
    for n in names:
        scored = sorted(((sim(n, p["text"]), p) for p in pool), key=lambda t: -t[0])
        best = scored[0][1]
        correct = [i for i, (_, p) in enumerate(scored) if p in gelria and sim(n, p["text"]) > 0]
        is1 = best in gelria and sim(n, best["text"]) >= scored[0][0]
        # correct = the gelria row whose text best matches this name
        gscored = sorted(((sim(n, p["text"]), p) for p in gelria), key=lambda t: -t[0])
        target = gscored[0][1] if gscored else None
        pos = next((i for i, (_, p) in enumerate(scored) if p is target), 999)
        if pos == 0:
            rank1 += 1
        if pos < 5:
            top5 += 1
        else:
            misses.append((n, best["text"], round(scored[0][0], 2)))

    print(f"\npool: {len(pool)} rows from {len({p['doc'] for p in pool})} dossiers")
    print(f"total time: {time.time()-t_all:.0f}s")
    print(f"correct row ranked #1 : {rank1}/{len(names)}")
    print(f"correct row in top 5  : {top5}/{len(names)}")
    if misses:
        print("\nlost in the crowd:")
        for n, got, s in misses[:6]:
            print(f"   {n!r} -> top hit {got!r} ({s})")
    (ROOT / "data" / "spike_scale.json").write_text(json.dumps(
        {"pool_size": len(pool), "rank1": rank1, "top5": top5, "queries": len(names)},
        indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
