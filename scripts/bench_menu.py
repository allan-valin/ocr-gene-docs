"""When a word is read wrong, is the right name in the menu, and at what rank?

The reading-quality plan turns on a number nobody has: a person opens the
readings menu on a badly-read word, and either the name the page carries is in
that list or it is not. This measures exactly that, over the hand-read pages in
`data/truth` paired against the rows already stored in `data/transcriptions` —
no recogniser is run, because the readings being judged are the stored ones.

    .venv/bin/python scripts/bench_menu.py                 # every source, one table
    .venv/bin/python scripts/bench_menu.py --source alts   # one source alone
    .venv/bin/python scripts/bench_menu.py --json out.json

Only words the engine got wrong are scored: a word already right needs no menu.
A row of truth the engine never produced is left out and reported apart, so a
run says how much of the page the menu ever had a chance at.
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque.gazetteer import Names            # noqa: E402

DEPTHS = (1, 3, 5, 10)


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


def pairs(truth: dict, rows: list[dict]) -> list[dict]:
    """Each hand-read name beside the row the engine stored for it.

    Paired by row number, not by order: a page whose bands the engine cut
    differently has rows missing in the middle, and pairing by position would
    then compare every later name with somebody else's.
    """
    by_n = {r.get("n"): r for r in rows if r.get("page") == truth.get("page")}
    out = []
    for k, name in enumerate(truth.get("names") or []):
        row = by_n.get(int(truth.get("first_row", 1)) + k)
        if row is None or not (row.get("name_raw") or "").strip():
            continue
        out.append({"truth": name, "read": row["name_raw"], "row": row})
    return out


def word_pairs(truth: str, read: str) -> list[dict]:
    """The words of a truth name beside the words of the reading.

    Position when the counts agree, which is the ordinary case. When they do
    not — a word the recogniser merged or split — each truth word is matched
    to the reading word that resembles it most, so a merged reading is
    measured against both names it swallowed rather than dropped.
    """
    t = [fold(w) for w in (truth or "").split()]
    r = [fold(w) for w in (read or "").split()]
    if not t or not r:
        return []
    if len(t) == len(r):
        return [{"truth": a, "read": b, "i": i} for i, (a, b) in enumerate(zip(t, r))]
    out = []
    for a in t:
        i = max(range(len(r)),
                key=lambda j: difflib.SequenceMatcher(None, a, r[j]).ratio())
        out.append({"truth": a, "read": r[i], "i": i})
    return out


def rank_of(target: str, candidates: list[str]) -> int | None:
    """Where the true name sits in a menu, counting from one; None if absent."""
    want = fold(target)
    for k, c in enumerate(candidates, start=1):
        if fold(c) == want:
            return k
    return None


def alts_for(word: str, row: dict, i: int) -> list[str]:
    """The engine's other readings of this word — what the menu shows today."""
    alts = row.get("name_alts") or []
    if i >= len(alts):
        return []
    return [a for a in (alts[i] or []) if a]


def measure(cases: list[dict], candidates) -> dict:
    """Recall at each depth over the words the engine read wrong.

    A word read correctly is not scored: the menu is not asked about it, and
    counting it would flatter every source equally.
    """
    ranks: list[int | None] = []
    for c in cases:
        if fold(c["truth"]) == fold(c["read"]):
            continue
        ranks.append(rank_of(c["truth"], candidates(c["read"], c["row"], c["i"])))
    n = len(ranks)
    at = {d: (sum(1 for r in ranks if r is not None and r <= d) / n if n else 0.0)
          for d in DEPTHS}
    return {"words": n,
            "found": sum(1 for r in ranks if r is not None),
            "at": {d: round(v, 3) for d, v in at.items()},
            "median_rank": sorted(r for r in ranks if r is not None)[
                sum(1 for r in ranks if r is not None) // 2]
            if any(r is not None for r in ranks) else None}


def cases_from_disk() -> tuple[list[dict], dict]:
    """Every hand-read word, beside what the engine stored for it."""
    records = {}
    for f in sorted((ROOT / "data" / "transcriptions").glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if d.get("file"):
            records[d["file"]] = d

    cases, seen = [], {"pages": 0, "truth_rows": 0, "paired_rows": 0, "unpaired": []}
    for f in sorted((ROOT / "data" / "truth").glob("*.json")):
        t = json.loads(f.read_text(encoding="utf-8"))
        if not t.get("names"):
            continue
        seen["pages"] += 1
        seen["truth_rows"] += len(t["names"])
        rec = records.get(t.get("pdf"))
        got = pairs(t, rec.get("rows") or []) if rec else []
        seen["paired_rows"] += len(got)
        if len(got) < len(t["names"]):
            seen["unpaired"].append({"page": f.name,
                                     "missing": len(t["names"]) - len(got)})
        for p in got:
            for w in word_pairs(p["truth"], p["read"]):
                cases.append({**w, "row": p["row"]})
    return cases, seen


def sources(names: Names) -> dict:
    """The candidate sources, alone and together, as the menu could offer them."""
    def archive(word, row, i, limit=10):
        return [c["name"] for c in names.suggest(word, limit=limit)]

    def alts(word, row, i):
        return alts_for(word, row, i)

    def both(word, row, i):
        out = list(alts(word, row, i))
        for c in archive(word, row, i):
            if fold(c) not in {fold(x) for x in out}:
                out.append(c)
        return out

    return {"alts": alts, "archive": archive, "menu": both}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", choices=["alts", "archive", "menu"], default=None)
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)

    cases, seen = cases_from_disk()
    names = Names.load(ROOT / "data" / "names.json")
    picked = sources(names)
    if a.source:
        picked = {a.source: picked[a.source]}

    report = {"pages": seen["pages"], "truth_rows": seen["truth_rows"],
              "paired_rows": seen["paired_rows"], "unpaired": seen["unpaired"],
              "words": len(cases), "dictionary": len(names), "sources": {}}
    for label, fn in picked.items():
        report["sources"][label] = measure(cases, fn)

    print(f"{seen['paired_rows']} of {seen['truth_rows']} hand-read rows have a "
          f"stored reading, over {seen['pages']} pages; {len(cases)} words")
    for u in seen["unpaired"]:
        print(f"  {u['page']}: {u['missing']} rows never read")
    head = "source      words  found   " + "  ".join(f"@{d:<4}" for d in DEPTHS)
    print(head)
    for label, m in report["sources"].items():
        cells = "  ".join(f"{m['at'][d]:<5.3f}" for d in DEPTHS)
        print(f"{label:<10}  {m['words']:<5}  {m['found']:<5}  {cells}")
    if a.json:
        a.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
