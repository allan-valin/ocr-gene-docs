"""Find a name among the lines a whole-page reader left on disk.

`read_hospedaria.py` (and the corpus pass) write one JSON per page with every
line's text and box. This asks those files for a name the way `desembarque.
search` asks the index: folded, by trigram similarity and by edit ratio over
the words of each line, forgiving the clerk's and the recogniser's spelling.

    .venv/bin/python scripts/search_lines.py --dir data/hospedaria/lines \\
        "Kubach August"
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque.search import fold, similarity  # noqa: E402

FLOOR = 0.45


def _score(query: str, text: str) -> float:
    q, t = fold(query), fold(text)
    if not q or not t:
        return 0.0
    qw = q.split()
    tw = t.split()
    best = similarity(q, t)
    # the query's words against windows of the line, so a surname alone or a
    # name written given-first still finds its row
    for n in range(1, len(qw) + 1):
        for i in range(0, max(1, len(tw) - n + 1)):
            win = " ".join(tw[i:i + n])
            best = max(best, difflib.SequenceMatcher(None, q, win).ratio(),
                       difflib.SequenceMatcher(None, qw[0], win).ratio() * 0.9)
    return round(best, 3)


def hits(lines: list[dict], query: str, book: str, page: int) -> list[dict]:
    out = []
    for i, line in enumerate(lines):
        text = (line.get("text") or "").strip()
        if not text:
            continue
        s = _score(query, text)
        if s >= FLOOR:
            out.append({"book": book, "page": page, "line": i, "text": text,
                        "score": s, "y0": line.get("y0")})
    return sorted(out, key=lambda h: -h["score"])


def search(lines_dir: Path, query: str, limit: int = 30) -> list[dict]:
    found = []
    for f in sorted(lines_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        found.extend(hits(d.get("lines") or [], query, d.get("book", f.stem),
                          int(d.get("page") or 0)))
    return sorted(found, key=lambda h: -h["score"])[:limit]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("query")
    ap.add_argument("--dir", type=Path, default=ROOT / "data" / "hospedaria" / "lines")
    ap.add_argument("--limit", type=int, default=30)
    a = ap.parse_args(argv)
    for h in search(a.dir, a.query, a.limit):
        print(f"{h['score']:.2f}  {h['book']} p{h['page']:>4} l{h['line']:<3}  {h['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
