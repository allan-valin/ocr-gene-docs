#!/usr/bin/env python3
"""Collapse rows that were saved twice, one record at a time.

BS.ENT.017397 doubled on every save until it held 26,624 rows — 1,024 copies of
twenty-six — because a row carrying no page number was kept beside the posted
copy instead of being replaced. `batch.merge_page_rows` no longer does that, and
the repair that followed the discovery collapsed rows that were *equal*: a row
saved twice carries a different `edits` list each time, so fourteen copies of
row 1 survived it, and the document the demo runs on showed 41 rows for 26
passengers.

`batch.dedupe_rows` uses the identity that actually holds — two rows of one page
cannot both be row 1 — keeps the fullest copy, and merges the edits of every
copy so no record of what a person did is lost.

    python scripts/dedupe_corpus.py --dry-run       # say what would change
    python scripts/dedupe_corpus.py                 # write it, keeping a backup
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque.batch import dedupe_rows, tidy_edits  # noqa: E402


def repaired(rows: list[dict]) -> list[dict]:
    """One row per place, and one entry per act in each row's edit log."""
    out = []
    for r in dedupe_rows(rows):
        if isinstance(r, dict) and r.get("edits"):
            r = {**r, "edits": tidy_edits(r["edits"])}
        out.append(r)
    return out


def counts(record: dict) -> tuple[int, int, int, int]:
    rows = record.get("rows") or []
    fixed = repaired(rows)
    edits = sum(len(r.get("edits") or []) for r in rows if isinstance(r, dict))
    kept = sum(len(r.get("edits") or []) for r in fixed if isinstance(r, dict))
    return len(rows), len(fixed), edits, kept


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    changed = 0
    for f in sorted(a.dir.glob("*.json")):
        try:
            record = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            print(f"unreadable, left alone: {f.name}")
            continue
        before, after, edits, kept = counts(record)
        if before == after and edits == kept:
            continue
        changed += 1
        print(f"{record.get('notation') or f.stem}: {before} -> {after} rows, "
              f"{edits} -> {kept} edits")
        if a.dry_run:
            continue
        # the work in this file is somebody's typing; it is copied before it is
        # rewritten, and the copy is what to go back to if this was wrong
        shutil.copy2(f, f.with_suffix(".json.before-dedupe"))
        record["rows"] = repaired(record["rows"])
        f.write_text(json.dumps(record, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"{changed} record(s) {'would change' if a.dry_run else 'rewritten'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
