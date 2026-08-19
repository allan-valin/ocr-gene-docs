"""Can someone find a passenger in what the app has already indexed?

CER is a proxy. The question the product answers is "is my ancestor on this
ship", so the measure is retrieval: given a name as a person would type it,
does the right row come back first?

This queries the app's own transcription cache — whatever the folder indexer
has produced — rather than a bespoke pool, so the number describes the
product and not a spike.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque.search import similarity   # noqa: E402


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


def tri(s: str) -> set[str]:
    p = "  " + fold(s) + " "
    return {p[i:i + 3] for i in range(len(p) - 2)}


def sim(a: str, b: str) -> float:
    """The application's own scorer, so the measurement describes the product."""
    return similarity(a, b)


def load_pool(cache: Path) -> list[dict]:
    pool = []
    for f in sorted(cache.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not d.get("engine"):
            # manually typed rows are perfect by construction and would flatter
            # the engine they are meant to be measuring
            continue
        for r in d.get("rows", []):
            text = r.get("name_raw") or " ".join(
                x for x in (r.get("surname"), r.get("given")) if x)
            if len(fold(text)) >= 4:
                pool.append({"doc": d.get("notation") or f.stem[:8],
                             "row": r.get("n"), "text": text})
    return pool


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--truth", type=Path, default=ROOT / "data" / "truth")
    args = ap.parse_args(argv)

    pool = load_pool(args.cache)
    if not pool:
        print("nothing indexed yet", file=sys.stderr)
        return 1
    print(f"pool: {len(pool)} rows from {len({p['doc'] for p in pool})} documents\n")

    total = rank1 = top5 = 0
    margins: list[float] = []
    for tf in sorted(args.truth.glob("*.json")):
        truth = json.loads(tf.read_text(encoding="utf-8"))
        names = truth.get("names") or []
        first = truth.get("first_row")
        print(f"--- {tf.name}  ({len(names)} names)")
        for i, n in enumerate(names):
            # the row this name is *known* to be, so the rank is measured
            # against the truth rather than against whatever looks plausible
            want = None if first is None else first + i
            scored = sorted(((sim(n, p["text"]), p) for p in pool), key=lambda t: -t[0])
            total += 1
            pos = next((k for k, (s, p) in enumerate(scored)
                        if want is not None and p["row"] == want
                        and p["doc"] == scored[0][1]["doc"]), None)
            if pos is None:
                pos = next((k for k, (s, p) in enumerate(scored)
                            if want is not None and p["row"] == want), 999)
            if pos == 0:
                rank1 += 1
            if pos < 5:
                top5 += 1
            best_s, best = scored[0]
            # the margin is the number that decides whether this survives a
            # bigger pool: how far ahead of the best *wrong* row the right one
            # sits. A win by 0.01 is a win that more rows will take away.
            right = scored[pos][0] if pos < len(scored) else 0.0
            wrong = next((sc for k, (sc, pp) in enumerate(scored) if k != pos), 0.0)
            margin = round(right - wrong, 3)
            margins.append(margin)
            place = "1st" if pos == 0 else (f"#{pos+1}" if pos < 999 else "lost")
            print(f"   {place:5} {n!r:26} -> {best['text']!r} "
                  f"({best_s:.2f}, margem {margin:+.2f})")

    print(f"\nranked first: {rank1}/{total}    in top 5: {top5}/{total}")
    if margins:
        thin = sum(1 for m in margins if m < 0.05)
        print(f"margin over the best wrong row: mean {sum(margins)/len(margins):+.3f}, "
              f"worst {min(margins):+.3f}, thin (<0.05) {thin}/{len(margins)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
