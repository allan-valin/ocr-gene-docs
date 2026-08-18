"""Benchmark a document model on real manifest pages.

Answers the question everything downstream depends on: is transcription on
commodity CPU fast enough and accurate enough to be worth shipping?

Measures per page:
  * wall-clock seconds (the number that decides whether on-demand transcription
    is tolerable on the friend's machine)
  * how many text lines came back, against the row count our geometry detects
  * character error rate on the name column, against hand-checked ground truth

Ground truth is prototype/sample_rows.json, which was transcribed by hand from
Gelria page 2.

Usage:
    .venv-ocr/bin/python scripts/spike_ocr.py --pages 2 --pdf data/scans/....pdf
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(truth: str, got: str) -> float:
    t, g = fold(truth), fold(got)
    return levenshtein(t, g) / max(1, len(t))


def best_match(name: str, candidates: list[str]) -> tuple[str, float]:
    """Nearest returned line for a known name — the model has no row alignment."""
    best, score = "", 1.0
    for c in candidates:
        s = cer(name, c)
        if s < score:
            best, score = c, s
    return best, score


def run(pdf: Path, page: int, dpi: int) -> dict:
    from paddleocr import PaddleOCR  # imported late: heavy

    t0 = time.time()
    # oneDNN crashes this paddle build on this CPU with an unimplemented PIR
    # attribute conversion, so the plain CPU kernels are used instead
    ocr = PaddleOCR(use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                    enable_mkldnn=False,
                    lang="pt")
    load_s = time.time() - t0

    from page_geometry import page_image
    img = page_image(pdf, page, ROOT / "data" / "pagecache" / "spike", dpi=dpi)
    if img is None:
        return {"error": "could not extract a page image"}

    t1 = time.time()
    result = ocr.predict(str(img))
    infer_s = time.time() - t1

    lines: list[str] = []
    for res in result:
        d = res.json.get("res", res.json) if hasattr(res, "json") else {}
        for key in ("rec_texts", "texts"):
            if key in d:
                lines.extend([t for t in d[key] if t and t.strip()])
                break
    return {"load_s": round(load_s, 1), "infer_s": round(infer_s, 1),
            "lines": lines, "image": str(img)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", type=Path,
                    default=ROOT / "data/scans/BR_RJANRIO_BS_0_RPV_ENT_017397_d0001de0001.pdf")
    ap.add_argument("--page", type=int, default=2)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "spike_ocr.json")
    args = ap.parse_args(argv)

    out = run(args.pdf, args.page, args.dpi)
    if "error" in out:
        print(out["error"], file=sys.stderr)
        return 1

    truth = json.loads((ROOT / "prototype" / "sample_rows.json").read_text(encoding="utf-8"))
    names = [f"{r['given']} {r['surname']}" for r in truth["rows"]]

    scored = []
    for n in names:
        got, score = best_match(n, out["lines"])
        scored.append({"truth": n, "best": got, "cer": round(score, 3)})

    mean = sum(s["cer"] for s in scored) / max(1, len(scored))
    exact = sum(1 for s in scored if s["cer"] == 0)
    usable = sum(1 for s in scored if s["cer"] <= 0.25)

    report = {
        "pdf": args.pdf.name, "page": args.page, "dpi": args.dpi,
        "model_load_s": out["load_s"], "inference_s": out["infer_s"],
        "lines_returned": len(out["lines"]),
        "names_expected": len(names),
        "name_cer_mean": round(mean, 3),
        "names_exact": exact, "names_within_25pct": usable,
        "worst": sorted(scored, key=lambda s: -s["cer"])[:5],
        "best": sorted(scored, key=lambda s: s["cer"])[:5],
    }
    args.out.write_text(json.dumps({**report, "detail": scored}, ensure_ascii=False, indent=2))

    print(f"\nmodel load     {report['model_load_s']}s")
    print(f"inference      {report['inference_s']}s for one page at {args.dpi} dpi")
    print(f"lines returned {report['lines_returned']} (expected ~{len(names)} names + other columns)")
    print(f"name CER mean  {report['name_cer_mean']}")
    print(f"names exact    {exact}/{len(names)}")
    print(f"within 25% CER {usable}/{len(names)}  <- usable for fuzzy search")
    print("\nworst:")
    for w in report["worst"]:
        print(f"   {w['cer']:.2f}  {w['truth']!r} -> {w['best']!r}")
    print("\nbest:")
    for b in report["best"]:
        print(f"   {b['cer']:.2f}  {b['truth']!r} -> {b['best']!r}")
    print(f"\nfull report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
