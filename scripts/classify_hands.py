"""Label every page of the corpus typed or cursive, and say how well.

    .venv/bin/python scripts/classify_hands.py            # write data/hands.json
    .venv/bin/python scripts/classify_hands.py --check    # score the labels

The measure is `desembarque.hands`: a threshold on the confidence already
stored beside every reading, so this is a pass over the records and no OCR.
`--check` scores it against the six pages in `data/truth` whose hand is
recorded, which is all the evidence there is — thin, and four of the six were
read by the assistant, so the accuracy printed is worth what that is worth.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]

from desembarque import truthset                       # noqa: E402
from desembarque.hands import (                        # noqa: E402
    CURSIVE, CUT, TYPED, UNKNOWN, label_document, near_the_cut,
)


def classify(records: Path, cut: float = CUT) -> dict:
    """Every record in a directory, labelled, keyed by the file it came from."""
    out = {}
    for f in sorted(records.glob("*.json")):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not rec.get("file"):
            continue
        got = label_document(rec, cut=cut)
        out[rec["file"]] = {
            "hash": rec.get("hash") or f.stem,
            "document": got["document"],
            "pages": {str(n): h for n, h in got["pages"].items()},
            "median_conf": {str(n): got["features"][n]["median_conf"]
                            for n in got["features"]},
            "rows": got["rows"],
        }
    return out


def check(labels: dict) -> int:
    """Score the labels against the pages whose hand somebody wrote down."""
    right = wrong = 0
    print(f"{'page':28}{'said':10}{'known':10}{'median':>8}")
    for page in truthset.load_pages():
        got = labels.get(page.pdf)
        if not got:
            print(f"{page.path.name:28}{'(not in this corpus)':20}")
            continue
        said = got["pages"].get(str(page.page), UNKNOWN)
        median = got["median_conf"].get(str(page.page))
        mark = "" if said == page.hand else "   <-- wrong"
        right += said == page.hand
        wrong += said != page.hand
        shown = f"{median:.3f}" if median is not None else "-"
        print(f"{page.path.name:28}{said:10}{page.hand:10}{shown:>8}{mark}")
    print(f"\n{right} of {right + wrong} pages of known hand labelled right, "
          f"cut at {CUT}")
    print("Four of those six pages were read by the assistant, so this is a "
          "weak check on a thin set — the gap it sits in is what makes it "
          "believable, not the count.")
    return 0 if wrong == 0 else 1


def summarise(labels: dict) -> None:
    docs = Counter(v["document"] for v in labels.values())
    pages = Counter(h for v in labels.values() for h in v["pages"].values())
    near = sum(1 for v in labels.values()
               for m in v["median_conf"].values() if near_the_cut(m))
    total_pages = sum(pages.values())
    print(f"{len(labels)} documents: " +
          ", ".join(f"{n} {k}" for k, n in docs.most_common()))
    print(f"{total_pages} pages: " +
          ", ".join(f"{n} {k}" for k, n in pages.most_common()))
    if total_pages:
        share = 100 * pages[CURSIVE] / max(1, pages[TYPED] + pages[CURSIVE])
        print(f"{share:.0f}% of the pages it can call are cursive — the hard "
              "ones, and the ones the work is for")
    print(f"{near} pages sit within 0.03 of the cut, where the label is the "
          "threshold guessing")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "hands.json")
    ap.add_argument("--cut", type=float, default=CUT)
    ap.add_argument("--check", action="store_true",
                    help="score the labels against the pages of known hand "
                         "and write nothing")
    args = ap.parse_args(argv)

    labels = classify(args.records, cut=args.cut)
    if args.check:
        summarise(labels)
        print()
        return check(labels)
    args.out.write_text(json.dumps(labels, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    summarise(labels)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
