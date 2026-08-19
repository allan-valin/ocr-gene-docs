"""Does the row comb sit on the writing, or somewhere else on the page?

BS_ENT_013990 p2 lists eighteen passengers and the engine read three of them:
the comb had fitted the empty ruled area *below* the table, because the table's
top is derived from the longest unbroken vertical rule and handwriting shatters
those rules exactly where people are listed. The failure is silent — the run
reports success, and the page simply comes back mostly blank.

Recognition is far too slow to check that across a corpus, and it also answers
a different question. What is measured here is coverage: of all the ink in the
name column, how much falls inside a detected row band? A comb on the writing
scores high; a comb on blank ruled paper scores near zero however many bands it
produces and however confident the fit was.

Two modes, because the rule is that no page may regress:

    scripts/bench_geometry.py --out data/bench-before.json
    ...change the geometry...
    scripts/bench_geometry.py --out data/bench-after.json
    scripts/bench_geometry.py --compare data/bench-before.json data/bench-after.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

# a page whose coverage falls by more than this is a regression, not noise;
# geometry is deterministic, so the tolerance only absorbs rounding
REGRESSION_EPS = 0.02


def measure(pdf: Path, page: int, work: Path) -> dict | None:
    """Coverage and shape of the comb on one page."""
    import numpy as np
    from PIL import Image
    from page_geometry import analyze, page_image
    Image.MAX_IMAGE_PIXELS = None

    img = page_image(pdf, page, work)
    if img is None:
        return None
    geo = analyze(img)
    bands = geo.normalized_rows()
    col = geo.name_column(0)
    if not geo.rows or not col:
        return {"pdf": pdf.name, "page": page, "bands": 0, "coverage": 0.0,
                "top": None, "bottom": None, "no_grid": True}

    im = Image.open(img).convert("L")
    im = im.rotate(geo.skew, resample=Image.BICUBIC, fillcolor=255)
    W, H = im.size
    x0 = max(0, int((col[0] - 0.004) * W))
    x1 = min(W, int((col[1] + 0.004) * W))
    a = np.asarray(im.crop((x0, 0, x1, H)), dtype=np.uint8)
    thr = max(60, int(a.mean()) - 35)
    ink = (a < thr)
    # the printed rules span the column; they are not writing and would
    # otherwise credit a comb sitting on blank ruled paper
    ink[ink.mean(axis=1) > 0.8, :] = False
    per_row = ink.sum(axis=1).astype(np.float64)
    total = per_row.sum()

    inside = 0.0
    for bt, bb in bands:
        inside += per_row[max(0, int(bt * H)):min(H, int(bb * H))].sum()

    return {
        "pdf": pdf.name, "page": page,
        "bands": len(bands),
        "coverage": round(float(inside / total), 4) if total else 0.0,
        "top": round(bands[0][0], 4),
        "bottom": round(bands[-1][1], 4),
        "skew": round(geo.skew, 3),
    }


def run(scans: Path, work: Path, sample: int, page: int, seed: int,
        only_from: Path | None = None) -> list[dict]:
    """Measure a sample, or exactly the pages a previous run measured.

    The corpus grows while work is going on, so a seeded sample drifts and a
    before/after comparison silently ends up describing different pages.
    `--from` pins the set to whatever the baseline actually looked at.
    """
    import random
    if only_from:
        want = [(r["pdf"], r["page"]) for r in json.loads(only_from.read_text())]
        pairs = [(scans / name, pg) for name, pg in want]
    else:
        pdfs = sorted(scans.glob("*.pdf"))
        random.Random(seed).shuffle(pdfs)
        pairs = [(pdf, page) for pdf in pdfs[:sample]]
    out = []
    for pdf, page in pairs:
        if not pdf.exists():
            continue
        try:
            rec = measure(pdf, page, work)
        except Exception as e:
            rec = {"pdf": pdf.name, "page": page, "error": f"{type(e).__name__}: {e}"}
        if rec:
            out.append(rec)
            cov = rec.get("coverage")
            print(f"  {rec['pdf'][-26:]:28s} bands={rec.get('bands', 0):3d} "
                  f"coverage={cov if cov is None else f'{cov:.3f}'} "
                  f"top={rec.get('top')}", flush=True)
    return out


def compare(before: Path, after: Path) -> int:
    """Regressions first, because they are the ones that block a change."""
    b = {(r["pdf"], r["page"]): r for r in json.loads(before.read_text())}
    a = {(r["pdf"], r["page"]): r for r in json.loads(after.read_text())}
    shared = sorted(set(b) & set(a))
    worse, better = [], []
    for k in shared:
        db = b[k].get("coverage")
        da = a[k].get("coverage")
        if db is None or da is None:
            continue
        if da < db - REGRESSION_EPS:
            worse.append((k, db, da))
        elif da > db + REGRESSION_EPS:
            better.append((k, db, da))

    print(f"pages compared: {len(shared)}")
    print(f"improved: {len(better)}   regressed: {len(worse)}")
    covb = [b[k]["coverage"] for k in shared if b[k].get("coverage") is not None]
    cova = [a[k]["coverage"] for k in shared if a[k].get("coverage") is not None]
    if covb:
        print(f"mean coverage: {sum(covb)/len(covb):.4f} -> {sum(cova)/len(cova):.4f}")
    if worse:
        print("\nREGRESSED:")
        for (pdf, pg), db, da in sorted(worse, key=lambda t: t[2] - t[1])[:20]:
            print(f"  {pdf[-30:]:32s} p{pg}  {db:.3f} -> {da:.3f}")
    if better:
        print("\nimproved:")
        for (pdf, pg), db, da in sorted(better, key=lambda t: t[1] - t[2])[:20]:
            print(f"  {pdf[-30:]:32s} p{pg}  {db:.3f} -> {da:.3f}")
    return 1 if worse else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--sample", type=int, default=60)
    ap.add_argument("--page", type=int, default=2)
    ap.add_argument("--seed", type=int, default=1919)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--compare", type=Path, nargs=2)
    ap.add_argument("--from", dest="only_from", type=Path,
                    help="measure exactly the pages this bench file lists")
    args = ap.parse_args()

    if args.compare:
        return compare(*args.compare)

    rows = run(args.scans, args.work, args.sample, args.page, args.seed,
               only_from=args.only_from)
    cov = [r["coverage"] for r in rows if r.get("coverage") is not None]
    print(f"\n{len(rows)} pages, mean coverage {sum(cov)/len(cov):.4f}" if cov else "no pages")
    poor = [r for r in rows if (r.get("coverage") or 0) < 0.5]
    print(f"pages under 0.5 coverage: {len(poor)}")
    for r in sorted(poor, key=lambda r: r.get("coverage") or 0)[:15]:
        print(f"  {r['pdf'][-30:]:32s} coverage={r.get('coverage')} top={r.get('top')}")
    if args.out:
        args.out.write_text(json.dumps(rows, indent=2))
        print(f"\nwritten {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
