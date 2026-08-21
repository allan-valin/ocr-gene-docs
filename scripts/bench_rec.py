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


def read_page(eng, pdf: Path, page: int) -> tuple[list[str], float]:
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
    rows = ep.rows_from_bands(geo, im.size, eng._recognize, eng._carved_crops(im, geo))
    print(f"    measured from the {source}: {len(rows)} rows")
    return [r.get("name_raw") or "" for r in rows], time.time() - t0


def score(names: list[str], truth: list[str], first: int) -> dict:
    """Truth row i against whatever the engine put on that row."""
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
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    ep.REC_INPUT_SHAPE = tuple(int(n) for n in args.shape.split("x"))
    eng = ep.PaddleEngine(rec_model=args.model)
    eng._import()

    print(f"{args.model}, input {ep.REC_INPUT_SHAPE}")
    report = []
    for t in truths():
        pdf = ROOT / "data" / "scans" / t["pdf"]
        if not pdf.exists():
            print(f"  {t['pdf']}: not in data/scans, skipped")
            continue
        print(f"  {t['pdf']} p{t['page']}")
        names, secs = read_page(eng, pdf, t["page"])
        s = score(names, t["names"], t.get("first_row", 1))
        s.update(page=f"{t['pdf']}#{t['page']}", seconds=round(secs, 1))
        report.append(s)
        print(f"    CER {s['cer']:.3f} | exact {s['exact']}/{s['rows']} | "
              f"findable {s['findable']}/{s['rows']} | {s['seconds']}s")
        for i, want in enumerate(t["names"][:6]):
            got = names[t.get("first_row", 1) - 1 + i] if names else ""
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
