"""Re-read every stored record's voyage from the pages already on disk.

    .venv/bin/python scripts/reparse_voyages.py --dry-run
    .venv/bin/python scripts/reparse_voyages.py

Reading a page as prose costs about twenty seconds and the corpus takes hours,
so a change to the way these printed forms are parsed used to mean re-indexing
everything. The text and boxes each voyage was read from are kept with the
record, so this does the same work in seconds — over whatever has already been
indexed at a schema that kept them.

It touches the voyage and the schema stamp and nothing else. A change that
needs the page image again is a re-index and should be one.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque.reparse import reparse       # noqa: E402
from desembarque.search import SCHEMA         # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--dry-run", action="store_true",
                    help="say what would change and write nothing")
    args = ap.parse_args(argv)

    seen = changed = skipped = 0
    gained, lost = [], []
    for f in sorted(args.cache.glob("*.json")):
        try:
            record = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        seen += 1
        out = reparse(record, schema=SCHEMA)
        if out is None:
            skipped += 1
            continue
        before = (record.get("voyage") or {}).get("ship")
        after = (out.get("voyage") or {}).get("ship")
        if after and not before:
            gained.append((record.get("notation"), after))
        elif before and not after:
            lost.append((record.get("notation"), before))
        changed += 1
        if not args.dry_run:
            f.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                         encoding="utf-8")

    verb = "would change" if args.dry_run else "changed"
    print(f"{seen} records, {verb} {changed}, {skipped} left alone")
    if gained:
        print(f"\nships gained ({len(gained)}):")
        for notation, ship in gained[:20]:
            print(f"  {notation or '?':16s} {ship}")
    if lost:
        print(f"\nships no longer read ({len(lost)}):")
        for notation, ship in lost[:20]:
            print(f"  {notation or '?':16s} {ship}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
