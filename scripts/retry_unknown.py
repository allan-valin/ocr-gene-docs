"""Read again every page a record stored as unreadable.

    .venv-ocr/bin/python scripts/retry_unknown.py --dry-run
    .venv-ocr/bin/python scripts/retry_unknown.py

301 pages of this corpus are stored as `unknown`: when they were read the
geometry found no table on them, so nothing was recorded and nobody was told.
They are not blank paper — today's engine reads 28 names off one of them. The
records around them carry the current schema stamp, so an index run skips all
660 dossiers and reports success, which is why this needs a pass of its own.

It is the cheap half of a re-index: 301 pages against 660 dossiers, half an hour
against eleven hours. That is the right trade because a dossier with no unknown
pages was measured to read exactly what is already on disk — there is nothing
for the rest of the corpus to gain from being read again.

What it will not do is quietly replace work: a page that reads nothing is left
alone, a page that already has rows is never given a second set, and the schema
stamps stay where they are. One page of a record was read again; the document
was not, and the next index run should still think so.
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

from desembarque.batch import collect_pdfs                            # noqa: E402
from desembarque.identity import cached_hash                          # noqa: E402
from desembarque.retry import pages_wanting_a_reading, with_page      # noqa: E402
from page_geometry import page_image                                  # noqa: E402

_ENGINE = None


def engine():
    """One engine per worker process, loaded once and kept.

    Loading the models costs about fifteen seconds; a page costs twenty. A
    fresh engine per page would double the run.
    """
    global _ENGINE
    if _ENGINE is None:
        from desembarque.engine_paddle import PaddleEngine
        _ENGINE = PaddleEngine()
        _ENGINE._import()
    return _ENGINE


def read_pages(job: tuple[Path, list[int], Path]) -> dict[int, dict]:
    """One record's worth of reading, done in a worker process."""
    pdf, wanted, pagecache = job
    eng = engine()
    out: dict[int, dict] = {}
    for n in wanted:
        img = page_image(pdf, n, pagecache)
        if img is None:
            continue
        res = eng.transcribe_page(img, "list", source=pdf, page=n, text=True)
        page = {"n": n, "kind": res.kind, "error": res.error}
        if res.text or res.fragments:
            page["form"] = {"text": res.text, "fragments": res.fragments}
        if res.geometry:
            page["geometry"] = res.geometry
        out[n] = {"page": page, "rows": res.rows or []}
    return out


def sources(scans: Path) -> dict[str, Path]:
    """Content hash -> the PDF, for the folder the corpus was read from."""
    out: dict[str, Path] = {}
    for pdf in collect_pdfs(scans):
        try:
            out[cached_hash(pdf)] = pdf
        except OSError:
            continue
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--pagecache", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after this many records (0 = all)")
    ap.add_argument("--dry-run", action="store_true",
                    help="read and report, write nothing")
    # Three rather than one per core: each worker holds its own copy of the
    # models and a decompressed page, and this has to leave the laptop usable.
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args(argv)

    by_hash = sources(args.scans)
    jobs, missing, done_already = [], 0, 0
    for f in sorted(args.cache.glob("*.json")):
        if args.limit and len(jobs) >= args.limit:
            break
        try:
            record = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        wanted = pages_wanting_a_reading(record)
        if not wanted:
            done_already += 1
            continue
        pdf = by_hash.get(record.get("hash", ""))
        if pdf is None:
            missing += 1
            continue
        jobs.append((f, record, wanted, pdf))

    pages = sum(len(j[2]) for j in jobs)
    print(f"{len(jobs)} records, {pages} pages to read again, "
          f"{args.workers} workers, {done_already} records with nothing to retry")

    gained = rows_gained = names_gained = refused = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        read = pool.map(read_pages, [(pdf, wanted, args.pagecache)
                                     for _, _, wanted, pdf in jobs])
        for (f, record, wanted, _), got in zip(jobs, read):
            out, wrote, names = record, 0, 0
            for n in wanted:
                fresh = got.get(n)
                if fresh is None:
                    refused += 1
                    continue
                nxt = with_page(out, n, fresh["page"], fresh["rows"])
                if nxt is None:
                    refused += 1
                    continue
                out, wrote = nxt, wrote + len(fresh["rows"])
                names += sum(1 for r in fresh["rows"]
                             if (r.get("name_raw") or "").strip())
            if not wrote:
                continue
            gained += 1
            rows_gained += wrote
            names_gained += names
            if not args.dry_run:
                f.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                             encoding="utf-8")
            print(f"  {record.get('notation') or record.get('file')}: "
                  f"{names} names in {wrote} rows off {len(wanted)} page(s)"
                  f"{' (dry run)' if args.dry_run else ''}", flush=True)

    verb = "would gain" if args.dry_run else "gained"
    print(f"{len(jobs)} records had unread pages; {verb} {names_gained} names "
          f"in {rows_gained} rows on "
          f"{gained} of them, {refused} pages still read nothing, "
          f"{missing} without a PDF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
