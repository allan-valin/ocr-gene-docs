"""What a re-read did to the corpus, before anybody keeps it.

The whole-corpus re-read writes into a copy (`export_bands.py
--write-records`) and that copy becomes the corpus only if it is better. This
is the number that decides it: rows carrying a name, per document, and the
safety property underneath — every row a person typed still there and still
saying what they typed. A pass that gained ten thousand names and quietly
rewrote one correction has not gained anything worth having.

    .venv/bin/python scripts/compare_corpora.py \
        --before data/transcriptions --after data/reread

The pass writes into a *copy*, so every document is present in the second
directory from the first second of the run and an unfinished pass shows as
documents whose rows have not moved. Those are counted apart from the ones that
came back different: a pass that stopped halfway and a pass that changed
nothing are opposite conclusions about whether to keep the copy, and the
totals below mean nothing until the run is done.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque.batch import typed_by_a_person   # noqa: E402
from desembarque.search import row_text           # noqa: E402


def named(record: dict) -> int:
    """Rows carrying a name somebody could search for."""
    return sum(1 for r in record.get("rows") or ()
               if not r.get("header") and (row_text(r) or "").strip())


def _typed(record: dict) -> dict[tuple, dict]:
    return {(r.get("page"), r.get("n")): r for r in record.get("rows") or ()
            if typed_by_a_person(r)}


def compare(before: dict[str, dict], after: dict[str, dict]) -> dict:
    """Both corpora, document by document."""
    out = {"docs": [], "named_before": 0, "named_after": 0,
           "rows_before": 0, "rows_after": 0,
           "lost": [], "missing": [], "identical": [],
           "human_changed": []}
    for doc in sorted(before):
        was, now = before[doc], after.get(doc)
        nb = named(was)
        out["named_before"] += nb
        out["rows_before"] += len(was.get("rows") or ())
        if now is None:
            out["missing"].append(doc)
            out["docs"].append({"doc": doc, "before": nb, "after": None,
                                "gained": None})
            continue
        if (was.get("rows") or []) == (now.get("rows") or []):
            out["identical"].append(doc)
        na = named(now)
        out["named_after"] += na
        out["rows_after"] += len(now.get("rows") or ())
        out["docs"].append({"doc": doc, "before": nb, "after": na,
                            "gained": na - nb})
        if na < nb:
            out["lost"].append(doc)
        theirs, mine = _typed(was), _typed(now)
        for place, row in theirs.items():
            if mine.get(place) != row:
                out["human_changed"].append((doc, *place))
    return out


def load(d: Path) -> dict[str, dict]:
    out = {}
    for f in sorted(d.glob("*.json")):
        try:
            out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--before", type=Path,
                    default=ROOT / "data" / "transcriptions")
    ap.add_argument("--after", type=Path, default=ROOT / "data" / "reread")
    ap.add_argument("--show", type=int, default=20,
                    help="how many documents to list, worst first")
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)

    got = compare(load(a.before), load(a.after))
    reached = [d for d in got["docs"] if d["after"] is not None]
    moved = len(reached) - len(got["identical"])
    # The pass writes into a copy, so every document is present from the start
    # and a half-finished run shows as documents whose rows did not move — not
    # as documents that are absent.
    print(f"{moved} of {len(got['docs'])} documents came back different"
          f", {len(got['identical'])} unchanged or not yet reached"
          + (f", {len(got['missing'])} absent" if got["missing"] else ""))
    print(f"rows           {got['rows_before']:>8} -> {got['rows_after']}")
    print(f"carrying a name{got['named_before']:>8} -> {got['named_after']}"
          f"  ({got['named_after'] - got['named_before']:+})")
    if got["lost"]:
        print(f"\n{len(got['lost'])} documents came back with fewer names:")
        worst = sorted((d for d in reached if d["gained"] < 0),
                       key=lambda d: d["gained"])
        for d in worst[:a.show]:
            print(f"  {d['doc'][:8]}  {d['before']:5} -> {d['after']:<5}"
                  f" ({d['gained']:+})")
    # The one that is not a trade-off. A correction rewritten by a machine is
    # work destroyed, and no number of gained names buys it back.
    if got["human_changed"]:
        print(f"\nSTOP: {len(got['human_changed'])} rows a person typed are "
              f"not what they typed any more:")
        for doc, page, n in got["human_changed"][:a.show]:
            print(f"  {doc[:8]} p{page} row {n}")
    else:
        print("\nevery row a person typed survived verbatim")
    if a.json:
        a.json.write_text(json.dumps(got, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    return 1 if got["human_changed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
