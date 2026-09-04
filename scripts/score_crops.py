"""What a second recogniser's sidecar says, scored against the labels.

`read_bands.py` reads every exported crop of a subcorpus with another model
and writes what it said, by row. `training_set.py` says what a person says
those rows say. This joins the two and reports character error, which is the
number every recogniser in `docs/TASKS-reading-quality.md` is ranked by --
so the same sidecar answers both questions asked of a second opinion: does it
read the ink, and does it make anybody findable (`bench_search.py --matrix`).

It scores the engine's own reading on the same rows, because a CER without the
one it has to beat is not a comparison.

    .venv/bin/python scripts/score_crops.py --sidecar strip.json --trainset data/trainset
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from spike_ocr import cer                              # noqa: E402


def scored(labels: list[dict], said: dict) -> list[dict]:
    """Every labelled row the sidecar also read, with both readings' error."""
    out = []
    for row in labels:
        doc, page, n = row.get("doc"), row.get("page"), row.get("n")
        if not doc or page is None or n is None:
            continue
        text = ((said.get(doc, {}).get(str(page), {}) or {}).get(str(n)) or "").strip()
        if not text:
            continue
        out.append({"label": row["label"], "second": text,
                    "engine": row.get("engine") or "",
                    "source": row.get("source") or "",
                    "cer_second": cer(row["label"], text),
                    "cer_engine": cer(row["label"], row.get("engine") or "")})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sidecar", type=Path, required=True)
    ap.add_argument("--trainset", type=Path, required=True)
    ap.add_argument("--show", type=int, default=10)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    d = json.loads(args.sidecar.read_text(encoding="utf-8"))
    labels = [json.loads(l) for l in
              (args.trainset / "labels.jsonl").open(encoding="utf-8")]
    rows = scored(labels, d.get("read") or {})
    if not rows:
        raise SystemExit("no labelled row was read by this sidecar")

    def mid(key: str) -> float:
        got = sorted(r[key] for r in rows)
        return got[len(got) // 2]

    # A mean over this set is pulled about by a handful of rows whose truth
    # label is a word where the ink is a whole name, so both readings score
    # above 1 on them; the median says what a typical row reads like and the
    # mean is kept because every other number in the plan is one.
    second = sum(r["cer_second"] for r in rows) / len(rows)
    engine = sum(r["cer_engine"] for r in rows) / len(rows)
    print(f"{len(rows)} labelled rows read by {d.get('model')} "
          f"({d.get('variant', 'carved')} crop, refine {d.get('refine', 0)})")
    print(f"  second opinion CER {second:.3f} mean, {mid('cer_second'):.3f} median")
    print(f"  engine          CER {engine:.3f} mean, {mid('cer_engine'):.3f} median")
    won = sum(1 for r in rows if r["cer_second"] < r["cer_engine"])
    print(f"  the second reading is closer on {won} of {len(rows)} rows")
    # per page, because the number this is being compared with was taken on
    # one page and a mean over six hides which hand it was taken on
    per: dict[str, list] = {}
    for r in rows:
        per.setdefault(r["source"], []).append(r)
    for src, got in sorted(per.items()):
        s2 = sum(r["cer_second"] for r in got) / len(got)
        e2 = sum(r["cer_engine"] for r in got) / len(got)
        print(f"    {src:24} {len(got):>4} rows  second {s2:.3f}  engine {e2:.3f}")
    for r in sorted(rows, key=lambda r: r["cer_second"])[:args.show]:
        print(f"     {r['label']!r} -> {r['second']!r} "
              f"(engine {r['engine']!r})")
    if args.out:
        args.out.write_text(json.dumps(
            {"model": d.get("model"), "variant": d.get("variant", "carved"),
             "refine": d.get("refine", 0), "rows": len(rows),
             "cer_second": round(second, 3), "cer_engine": round(engine, 3),
             "median_second": round(mid("cer_second"), 3),
             "median_engine": round(mid("cer_engine"), 3),
             "second_closer": won}, indent=2))


if __name__ == "__main__":
    main()
