"""What the corpus knows about its own voyages.

    .venv/bin/python scripts/voyages.py

Reads the stored transcriptions and reports what they state: how many name a
ship, how many resolve to a year, which ships and which lines recur. Run it
after an indexing pass to see whether the forms are being read, and after a
change to the parser to see that it has not started filing letterhead as
vessels — a sudden crowd of one-off "ships" is what that looks like from here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque.search import SCHEMA  # noqa: E402
from desembarque.voyages_report import summarise  # noqa: E402


def load(cache: Path) -> list[dict]:
    out = []
    for f in sorted(cache.glob("*.json")):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--schema", type=int, default=SCHEMA,
                    help="only records the engine wrote at this schema (0 = all). "
                         "Older records were read before the forms were, and "
                         "counting them makes the yield look far worse than it is.")
    args = ap.parse_args(argv)

    everything = load(args.cache)
    records = [r for r in everything
               if not args.schema or int(r.get("schema", 0)) >= args.schema]
    stale = len(everything) - len(records)
    if not records:
        print(f"nothing indexed under {args.cache}", file=sys.stderr)
        return 1
    s = summarise(records)

    def share(n: int) -> str:
        return f"{n:5d}  {n / max(1, s['documents']):5.1%}"

    print(f"{s['documents']} documents read at schema {args.schema}"
          + (f", {stale} older not counted" if stale else "") + "\n")
    print(f"  state a voyage   {share(s['with_voyage'])}")
    print(f"  name a ship      {share(s['with_ship'])}")
    print(f"  give a year      {share(s['with_year'])}")
    print(f"  give a full date {share(s['with_full_date'])}")
    print(f"  give a port      {share(s['with_port'])}")
    print(f"  name a line      {share(s['with_line'])}")

    if s["years"]:
        lo, hi = s["years"][0][0], s["years"][-1][0]
        print(f"\nyears {lo}-{hi}: " + ", ".join(f"{y} ({n})" for y, n in s["years"]))
    if s["ships"]:
        print(f"\n{len(s['ships'])} distinct ships. Commonest:")
        for name, n in s["ships"][:args.top]:
            print(f"  {n:4d}  {name}")
    if s["lines"]:
        print("\nshipping lines:")
        for name, n in s["lines"][:args.top]:
            print(f"  {n:4d}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
