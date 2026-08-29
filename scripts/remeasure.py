"""Read again the pages whose name column was measured wrong.

Half the corpus was read before the table was measured from the printing, and
the geometry those pages carry says so: of 2,543 stored pages, 946 have a name
column narrower than a name — 0.017 to 0.06 of the sheet is the ordinal strip,
not a name — and the crops behind them held a page number and two letters. The
rows are there and they are wrong: `ete do Coeto` for *Julio Augusto da Costa*.
A person searching for a passenger on one of those pages does not find them.

Nothing here is a constant about how a page is laid out. These forms differ by
country, decade and printer, so a page is judged against its own dossier: the
same printed sheet runs the length of a list, its pages measure alike, and a
page that measures unlike its siblings is the suspect one. Where a dossier has
too few pages to say, the corpus's own distribution of column widths is used —
measured at run time from the records on disk, not written into this file.

    .venv-ocr/bin/python scripts/remeasure.py --dry-run --limit 8
    .venv-ocr/bin/python scripts/remeasure.py --workers 2

What it will not do is replace anybody's typing: a row a person edited or
ticked stays at its place, and only the engine's own rows are re-read. A page
that comes back empty is refused, because an empty page is a failure and not a
page with nobody on it.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from desembarque.retry import with_page_remeasured   # noqa: E402
from page_geometry import page_image                 # noqa: E402

# How far from its dossier's own measurement a page has to fall before it is
# read again. Both are ratios of that dossier's median column width, so they
# say "unlike its siblings" and never "this many hundredths of a sheet".
NARROW = 0.6
MOVED = 0.5


def stored_columns(record: dict) -> dict[int, tuple[float, float]]:
    out = {}
    for p in record.get("pages") or []:
        if not isinstance(p, dict):
            continue
        cols = ((p.get("geometry") or {}).get("columns"))
        if cols and len(cols) >= 2:
            out[p.get("n")] = (float(cols[0]), float(cols[1]))
    return out


def suspect_pages(record: dict, corpus_width: float) -> list[int]:
    """The pages of this record whose name column is unlike the others'."""
    cols = stored_columns(record)
    if not cols:
        return []
    widths = [b - a for a, b in cols.values()]
    if len(cols) >= 3:
        typical = statistics.median(widths)
        left = statistics.median(a for a, _b in cols.values())
    else:
        typical, left = corpus_width, None
    out = []
    for n, (a, b) in cols.items():
        if (b - a) < NARROW * typical:
            out.append(n)
        elif left is not None and abs(a - left) > MOVED * typical:
            out.append(n)
    return sorted(x for x in out if x)


def corpus_median_width(records: list[dict]) -> float:
    widths = [b - a for r in records for a, b in stored_columns(r).values()]
    return statistics.median(widths) if widths else 0.2


_ENGINE = None


def engine():
    """One engine for the whole pass.

    It was being built per page, which loads the detector and the recogniser
    again for every page — most of the nineteen seconds a page cost. The models
    are the expensive part and they do not change between pages.
    """
    global _ENGINE
    if _ENGINE is None:
        from desembarque.engine_paddle import PaddleEngine
        _ENGINE = PaddleEngine()
        _ENGINE._import()
    return _ENGINE


def read_page(pdf: Path, page: int, pagecache: Path) -> tuple[list[dict], dict]:
    eng = engine()
    img = page_image(pdf, page, pagecache)
    if img is None:
        return [], {}
    res = eng.transcribe_page(img, "list", source=pdf, page=page)
    return list(res.rows or []), {"n": page, "kind": res.kind,
                                  "geometry": res.geometry}


def named(rows) -> int:
    return sum(1 for r in rows if (r.get("name_raw") or "").strip())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--pagecache", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many pages")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    files, records = [], []
    for f in sorted(a.cache.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        files.append(f)
        records.append(d)
    width = corpus_median_width(records)
    by_name = {p.name: p for p in a.scans.rglob("*.pdf")}

    jobs = []
    for f, d in zip(files, records):
        pdf = by_name.get(d.get("file") or "")
        for n in suspect_pages(d, width):
            if pdf is None:
                continue
            jobs.append((f, d, n, pdf))
    print(f"{len(records)} records, median stored column {width:.3f} of the sheet")
    print(f"{len(jobs)} pages measured unlike their dossier")

    wanted = jobs[:a.limit] if a.limit else jobs
    before = after = pages = 0
    for f, d, n, pdf in wanted:
        was = [r for r in d.get("rows") or [] if r.get("page") == n]
        rows, page = read_page(pdf, n, a.pagecache)
        pages += 1
        before += named(was)
        after += named(rows)
        cols = (page.get("geometry") or {}).get("columns")
        print(f"  {d.get('notation')} p{n}: names {named(was)} -> {named(rows)}"
              f"   column {stored_columns(d).get(n)} -> "
              f"{tuple(round(c, 3) for c in cols) if cols else None}")
        if a.dry_run:
            continue
        out = with_page_remeasured(d, n, page, rows)
        if out is None:
            continue
        f.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"\n{pages} pages read: {before} names before, {after} after")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
