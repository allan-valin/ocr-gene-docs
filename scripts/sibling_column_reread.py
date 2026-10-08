"""Read again the pages whose name column is unlike their dossier's, through
the column the dossier's other pages agree on.

After the 2026-10-08 re-read, 271 of 2,543 pages still carry a name column
that is the ordinal strip or the whole sheet — mostly cursive pages whose
rules are too faint to measure. The same printed form runs the length of a
dossier, and 225 of those pages have at least one sibling page measured
plausibly. So the page keeps its own row bands and borrows the median column
of its siblings, the engine's own recogniser reads the crops that makes, and
the readings go into a sidecar keyed to the page's bands — the reversible
shape, applied with `apply_second_opinion.py --write`.

    .venv-ocr/bin/python scripts/sibling_column_reread.py --out data/sibling-column.json
    .venv/bin/python scripts/apply_second_opinion.py --sidecar data/sibling-column.json \\
        --records data/transcriptions --bands data/reread-index --write

Counted beside the reading: rows on those pages that the index could reach
before, and that it can reach through the new reading.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from desembarque.search import searchable   # noqa: E402

COLUMN_WIDTH = (0.07, 0.6)


def sibling_column(record: dict) -> tuple[float, float] | None:
    good = []
    for p in record.get("pages") or ():
        c = ((p or {}).get("geometry") or {}).get("columns") or []
        if len(c) >= 2 and COLUMN_WIDTH[0] <= c[1] - c[0] <= COLUMN_WIDTH[1]:
            good.append((c[0], c[1]))
    if not good:
        return None
    return (statistics.median(a for a, _ in good), statistics.median(b for _, b in good))


def suspect_pages(record: dict) -> list[tuple[int, dict]]:
    out = []
    for p in record.get("pages") or ():
        g = (p or {}).get("geometry") or {}
        c = g.get("columns") or []
        if len(c) < 2 or not g.get("rows"):
            continue
        if not COLUMN_WIDTH[0] <= c[1] - c[0] <= COLUMN_WIDTH[1]:
            out.append((int(p["n"]), g))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=0, help="pages, for a dry run")
    a = ap.parse_args(argv)

    from page_geometry import page_image
    from desembarque.bandcrops import crops_for
    from desembarque.engine_paddle import PaddleEngine
    eng = PaddleEngine()
    eng._import()

    read: dict[str, dict] = {}
    if a.out.exists():
        try:
            read = json.loads(a.out.read_text(encoding="utf-8")).get("read") or {}
            print(f"resuming: {sum(len(v) for v in read.values())} pages done")
        except ValueError:
            read = {}
    began, pages, before, after = time.time(), 0, 0, 0
    for f in sorted(a.records.glob("*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        doc = rec.get("hash")
        suspects = suspect_pages(rec)
        if not suspects:
            continue
        col = sibling_column(rec)
        if col is None:
            continue
        pdf = a.scans / (rec.get("file") or "")
        if not pdf.is_file():
            continue
        for n, geo in suspects:
            if str(n) in (read.get(doc) or {}):
                continue
            if a.limit and pages >= a.limit:
                break
            img = page_image(pdf, n, a.work)
            if img is None:
                continue
            borrowed = {**geo, "columns": [col[0], col[1]], "measured_by": "siblings"}
            crops = crops_for(Path(img), borrowed)
            keys = sorted(crops)
            said = eng._recognize([crops[k]["carved"] for k in keys])
            got = {str(k): t for k, (t, _s) in zip(keys, said) if t}
            read.setdefault(doc, {})[str(n)] = got
            pages += 1
            was = sum(1 for r in rec.get("rows") or () if r.get("page") == n
                      and searchable(r.get("name_raw") or ""))
            now = sum(1 for t in got.values() if searchable(t))
            before += was
            after += now
            print(f"  {doc[:8]} p{n}: column {geo['columns'][0]:.3f}-{geo['columns'][1]:.3f}"
                  f" -> {col[0]:.3f}-{col[1]:.3f}, searchable rows {was} -> {now}", flush=True)
            a.out.write_text(json.dumps({"model": "PP-OCRv6-sibling-column", "by": "row",
                                         "variant": "carved", "read": read},
                                        ensure_ascii=False), encoding="utf-8")
    print(f"\n{pages} pages in {(time.time() - began) / 60:.1f} min; searchable rows on "
          f"them {before} -> {after}. Wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
