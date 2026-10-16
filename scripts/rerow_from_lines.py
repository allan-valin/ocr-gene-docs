"""Re-row the corpus's handwritten pages from the lines already on disk.

`reread_fullpage.py` left every cursive and unknown page's written lines,
with their text from PP-OCRv6-hist, under `data/fullpage-ppocrv6/<hash>-p<N>.json`.
Since 2026-10-16 a page indexed by the server is cut into one row per such
line (`secondreading.rows_from_lines`); this does the same to what is
stored, from those files, without reading anything again -- seconds, not
hours. A page already re-rowed (`geometry.rows_from == "lines"`) is left
alone, so the pass can run twice.

    .venv/bin/python scripts/rerow_from_lines.py --limit 10      # look first
    .venv/bin/python scripts/rerow_from_lines.py --limit 10 --write
    .venv/bin/python scripts/rerow_from_lines.py --write         # when Allan says

Nothing is written without `--write`; the default prints, per document,
rows before and after on the pages that would change.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque import hands                                  # noqa: E402
from desembarque.secondreading import (                        # noqa: E402
    HANDS_READ, _with_pages_rerowed, rows_from_lines)


def pages_with_lines(record: dict, lines_dir: Path) -> dict[int, Path]:
    """Page -> its line file, for the handwritten pages that have one and a
    grid, and were not re-rowed already."""
    out = {}
    by_page: dict[int, list[dict]] = {}
    for r in record.get("rows") or ():
        if r.get("page"):
            by_page.setdefault(int(r["page"]), []).append(r)
    for p in record.get("pages") or ():
        if not isinstance(p, dict):
            continue
        n, geo = int(p.get("n") or 0), p.get("geometry") or {}
        if not geo.get("rows") or geo.get("rows_from") == "lines":
            continue
        if hands.label_page(by_page.get(n, [])) not in HANDS_READ:
            continue
        f = lines_dir / f"{record.get('hash')}-p{n}.json"
        if f.exists():
            out[n] = f
    return out


def rerow_record(record: dict, lines_dir: Path) -> tuple[dict, dict[int, tuple[int, int]]]:
    """The record re-rowed, and per page (rows before, rows after)."""
    geo = {int(p.get("n") or 0): p.get("geometry") or {}
           for p in record.get("pages") or () if isinstance(p, dict)}
    rerowed, counts = {}, {}
    for n, f in pages_with_lines(record, lines_dir).items():
        try:
            lines = json.loads(f.read_text(encoding="utf-8")).get("lines") or []
        except ValueError:
            continue
        on_page = [r for r in record.get("rows") or () if r.get("page") == n]
        rows, extents = rows_from_lines(on_page, lines, geo.get(n, {}))
        if not rows:
            continue
        rerowed[n] = (rows, extents)
        counts[n] = (len(on_page), len(rows))
    if not rerowed:
        return record, {}
    out = _with_pages_rerowed(record, rerowed)
    note = dict(out.get("second_reading") or {})
    note["rerowed"] = sorted(set(note.get("rerowed") or []) | set(rerowed))
    note.setdefault("model", "PP-OCRv6-hist-medium-page-column")
    return {**out, "second_reading": note}, counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--records", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--lines", type=Path, default=ROOT / "data" / "fullpage-ppocrv6")
    ap.add_argument("--limit", type=int, default=0, help="documents to touch")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    docs = pages = before = after = 0
    for f in sorted(a.records.glob("*.json")):
        try:
            record = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        out, counts = rerow_record(record, a.lines)
        if not counts:
            continue
        docs += 1
        pages += len(counts)
        b, c = sum(x for x, _ in counts.values()), sum(y for _, y in counts.values())
        before += b
        after += c
        print(f"  {record.get('notation')}: {len(counts)} pages, rows {b} -> {c}"
              + "".join(f"  p{n} {x}->{y}" for n, (x, y) in sorted(counts.items())))
        if a.write:
            f.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        if a.limit and docs >= a.limit:
            break
    verb = "re-rowed" if a.write else "would be re-rowed"
    print(f"\n{pages} pages in {docs} documents {verb}: rows {before} -> {after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
