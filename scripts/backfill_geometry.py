"""Restore the geometry of every page whose rows are already on disk.

    .venv-ocr/bin/python scripts/backfill_geometry.py --dry-run
    .venv-ocr/bin/python scripts/backfill_geometry.py

The engine measured each page's grid to cut its rows out and the server never
stored the measurement, so a search hit can name a row and not show where on
the scan it sits. This puts it back without reading a single page again: the
geometry is a measurement on the page image, and the extracted images are still
in `data/pagecache`.

It touches one key on one page of a record and nothing else — not the rows, not
what a person typed over them, not the schema stamp. A page whose recomputed
band list is shorter than the rows stored against it is refused and reported,
because row `n` is its band's index and a short list draws every row after the
first difference against somebody else's line.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from desembarque.backfill import pages_wanting_geometry, with_geometry  # noqa: E402
from desembarque.batch import collect_pdfs                              # noqa: E402
from desembarque.identity import cached_hash                            # noqa: E402
from page_geometry import analyze, page_image                           # noqa: E402


def measure(pdf: Path, n: int, cache: Path) -> dict | None:
    """The same measurement the engine takes, on the same image it took it from.

    `page_image` returns the extracted bilevel layer it recorded during
    indexing, so this reads a file rather than decompressing a 23-megapixel
    scan again.
    """
    img = page_image(pdf, n, cache)
    if img is None:
        return None
    geo = analyze(img)
    if not geo.rows:
        return None
    return {"rows": geo.normalized_rows(),
            "columns": geo.normalized_cols(),
            "skew": geo.skew,
            # where the bands came from, so a band that disagrees with the scan
            # can be traced to the run that drew it
            "measured_by": "backfill"}


def sources(scans: Path) -> dict[str, Path]:
    """Content hash -> the PDF, for the folder the corpus was read from."""
    out: dict[str, Path] = {}
    for pdf in collect_pdfs(scans):
        try:
            out[cached_hash(pdf)] = pdf
        except OSError:
            continue
    return out


def measured_pages(job: tuple[Path, list[int], Path]) -> dict[int, dict | None]:
    """One record's worth of measuring, done in a worker process."""
    pdf, wanted, pagecache = job
    return {n: measure(pdf, n, pagecache) for n in wanted}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--pagecache", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after this many records (0 = all)")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and report, write nothing")
    # Three rather than one per core: each worker holds a decompressed
    # 23-megapixel page, and this has to leave the laptop usable while it runs.
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args(argv)

    by_hash = sources(args.scans)
    print(f"{len(by_hash)} dossiers in {args.scans}")

    jobs, skipped_files = [], []
    seen = filled = done_already = missing = refused = 0
    for f in sorted(args.cache.glob("*.json")):
        if args.limit and len(jobs) >= args.limit:
            break
        try:
            record = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        wanted = pages_wanting_geometry(record)
        if not wanted:
            done_already += 1
            continue
        seen += 1
        pdf = by_hash.get(record.get("hash", ""))
        if pdf is None:
            missing += 1
            print(f"  {record.get('notation') or f.stem[:12]}: PDF not in {args.scans}")
            continue
        jobs.append((f, record, wanted, pdf))

    pages = sum(len(j[2]) for j in jobs)
    print(f"{len(jobs)} records, {pages} pages to measure, {args.workers} workers")

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        measured = pool.map(measured_pages,
                            [(pdf, wanted, args.pagecache)
                             for _, _, wanted, pdf in jobs])
        for (f, record, wanted, _), geos in zip(jobs, measured):
            out, wrote = record, False
            for n in wanted:
                nxt = with_geometry(out, n, geos.get(n))
                if nxt is None:
                    refused += 1
                    print(f"  {record.get('notation')} p{n}: no measurement, or "
                          "one that disagrees with the rows on disk; left alone")
                    continue
                out, wrote = nxt, True
            if not wrote:
                continue
            filled += 1
            if not args.dry_run:
                f.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                             encoding="utf-8")
            print(f"  {record.get('notation')}: {len(wanted)} page(s) measured"
                  f"{' (dry run)' if args.dry_run else ''}", flush=True)

    verb = "would gain" if args.dry_run else "gained"
    print(f"{seen} records wanted geometry, {verb} it on {filled}; "
          f"{refused} pages refused, {missing} without a PDF, "
          f"{done_already} already complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
