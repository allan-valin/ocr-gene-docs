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
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque.gazetteer import Names, menu_for, spoken_names  # noqa: E402
from desembarque.truthset import (fold, pairs, rank_of,  # noqa: E402
                                  word_pairs, words_from_disk)
from desembarque import strokes                    # noqa: E402

DEPTHS = (1, 3, 5, 10)


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


def sources(names: Names, limit: int = 10) -> dict:
    """The candidate sources, alone and together, as the menu could offer them."""
    def archive(word, row, i):
        return [c["name"] for c in names.suggest(word, limit=limit)]

    def alts(word, row, i):
        return alts_for(word, row, i)

    def both(word, row, i):
        out = list(alts(word, row, i))
        for c in archive(word, row, i):
            if fold(c) not in {fold(x) for x in out}:
                out.append(c)
        return out

    spoken = spoken_names(ROOT / "data" / "language_names.json")
    known = {k.upper() for k in names.counts} | spoken

    def ink(word, row, i, rules=None):
        return [c.word for c in strokes.variants(word, known=known,
                                                 limit=limit, rules=rules)]

    def joined(word, row, i):
        """The menu as it would ship: the engine's own readings first, then the
        candidates the ink supports that somebody has read before, then the
        archive's near spellings, then the rest of what the ink supports."""
        ours = strokes.variants(word, known=known, limit=limit * 3)
        seen_names = {c.word for c in ours if c.word.replace(" ", "") in known}
        near = archive(word, row, i)
        out, seen = [], set()
        for c in (alts(word, row, i)
                  + near[:1]
                  + [c.word for c in ours if c.word in seen_names]
                  + near[1:]
                  + [c.word for c in ours if c.word not in seen_names]):
            if fold(c) not in seen:
                seen.add(fold(c))
                out.append(c)
        return out

    def shipped(word, row, i):
        """The menu the server actually returns, so the number measured here
        is the number a reader gets."""
        return alts(word, row, i) + [g["name"] for g in
                                     menu_for(word, names, limit=limit,
                                              spoken=spoken)]

    def guesses(word, row, i):
        """The guesses block alone, without the engine's own readings above it:
        the two are separate sections on screen and the reader can put either
        first, so a rank that mixes them answers neither question."""
        return [g["name"] for g in menu_for(word, names, limit=limit,
                                            spoken=spoken)]

    picked = {"alts": alts, "archive": archive, "menu": both,
              "guesses": guesses,
              "strokes": ink, "all": joined, "shipped": shipped}
    for rule in ("minims", "ascender", "round", "abbreviation", "edge",
                 "capital", "space", "two changes"):
        picked[f"only:{rule}"] = (lambda r: lambda w, row, i: ink(w, row, i, rules={r}))(rule)
    return picked


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default=None,
                    help="one source alone: alts, archive, menu, strokes, all, "
                         "or only:<rule> for a single stroke rule")
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--limit", type=int, default=10,
                    help="how many candidates a source may offer")
    a = ap.parse_args(argv)

    cases, seen = words_from_disk()
    names = Names.load(ROOT / "data" / "names.json")
    picked = sources(names, a.limit)
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
