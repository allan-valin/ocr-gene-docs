"""Take the line number off names that read as `1Ismenia Pinto Saldanha`.

Where the name column's left rule hugs the Numero column, the crop sweeps up
the number's last digit with no gap, and `strip_ordinal` used to leave a digit
welded to a capital alone. It no longer does, for pages read from now on; this
pass gives the same treatment to what is already on disk. Only `name_raw`
changes, and never on a row a person typed.

    python scripts/strip_glued_ordinals.py            # report what would change
    python scripts/strip_glued_ordinals.py --write    # change it
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque.batch import typed_by_a_person  # noqa: E402
from desembarque.engine_paddle import strip_ordinal  # noqa: E402


def strip_record(record: dict) -> list[tuple[str, str]]:
    """Fix the record in place; the (before, after) pairs that changed."""
    changed = []
    for row in record.get("rows") or []:
        if not isinstance(row, dict) or typed_by_a_person(row):
            continue
        was = row.get("name_raw") or ""
        now = strip_ordinal(was)
        if now != was:
            row["name_raw"] = now
            changed.append((was, now))
    return changed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    files = rows = 0
    for f in sorted(a.cache.glob("*.json")):
        try:
            record = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        changed = strip_record(record)
        if not changed:
            continue
        files += 1
        rows += len(changed)
        for was, now in changed[:2]:
            print(f"  {record.get('notation')}: {was!r} -> {now!r}")
        if a.write:
            f.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    print(f"{rows} names in {files} dossiers {'changed' if a.write else 'would change'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
