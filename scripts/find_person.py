"""Search the index for one person under every spelling at once.

A name on these lists is spelled by a purser, then by a recogniser, so one
query is one guess. This asks every form given, pools the hits by row, and
prints each row once with its best score and the query that reached it, so a
person can be looked for the way the search screen cannot: forty spellings,
one list. Reads the records as the application does (every reading, the
catalogue's ships, the known names), so what it finds the app finds.

    .venv/bin/python scripts/find_person.py --queries data/kubach-queries.txt --limit 20
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from desembarque.search import load_index, search  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queries", type=Path, help="one query per line; # comments")
    ap.add_argument("--query", action="append", default=[], help="repeatable")
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--limit", type=int, default=20, help="hits kept per query")
    ap.add_argument("--min-score", type=float, default=0.0)
    ap.add_argument("--out", type=Path, default=None, help="write every hit as JSON")
    a = ap.parse_args(argv)

    from bench_search import catalogue_ships, known_names
    queries = list(a.query)
    if a.queries:
        queries += [l.strip() for l in a.queries.read_text(encoding="utf-8").splitlines()
                    if l.strip() and not l.startswith("#")]
    if not queries:
        print("no queries", file=sys.stderr)
        return 1
    rows = load_index(a.cache, engine_only=False, ships=catalogue_ships(a.scans) or None,
                      known=known_names())
    print(f"{len(rows)} indexed rows, {len(queries)} spellings", file=sys.stderr)

    best: dict[tuple, dict] = {}
    for q in queries:
        for h in search(rows, q, limit=a.limit, min_score=a.min_score):
            key = (h.get("doc"), h.get("page"), h.get("row"))
            if key not in best or h.get("score", 0) > best[key]["score"]:
                best[key] = {**h, "query": q}
    hits = sorted(best.values(), key=lambda h: -h.get("score", 0))
    for h in hits:
        print(f"{h.get('score', 0):.2f}  {(h.get('file') or h.get('doc') or '')[16:28]:>12} "
              f"p{h.get('page')} r{h.get('row')}  {h.get('text', '')!r}"
              f"{'  [' + h['spelling'] + ']' if h.get('spelling') and h['spelling'] != h.get('text') else ''}"
              f"  <- {h['query']}")
    if a.out:
        a.out.write_text(json.dumps(hits, ensure_ascii=False, indent=1))
    print(f"{len(hits)} rows reached", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
