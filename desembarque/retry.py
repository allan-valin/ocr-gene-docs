"""Read again the pages a record says nobody could read.

The corpus carries 301 pages stored as `unknown`: the geometry found no table
on them, so the page went by with nothing on it. They are not blank paper —
today's engine reads 28 names off one of them, and 19 off another in the same
dossier. What kept them empty is that the record around them is *current* by
every stamp an index run checks, so the run skips the document and reports
success. That is the silent-loss shape this repository keeps meeting in new
clothes: the empty manual note, the errored page stored at the current schema,
and now a page the geometry could not measure when it was read.

A full re-read would find them, and it costs eleven hours for 660 dossiers —
against half an hour for the 301 pages that are actually in question. Measured
on a dossier with no unknown pages, today's engine reads exactly what is
already stored, so the rest of the corpus has nothing to gain from being read
again.

The refusals are the substance here, and they are the same ones the geometry
backfill makes: a page that reads nothing is not written, a page that already
has rows is never given a second set, and the schema stamps are left where they
are. One page of a record was read again; the document was not.
"""
from __future__ import annotations


def pages_wanting_a_reading(record: dict) -> list[int]:
    """Page numbers stored with no reading that the engine could try again.

    A page the engine *failed* on is not one of them: an error makes the whole
    record stale, and an index run reads the document from the top. Repairing
    it here would take the document off that list with nobody told.
    """
    if not record or not record.get("engine"):
        return []          # a document nobody read is an index run's work
    has_rows = {r.get("page") for r in record.get("rows") or []
                if isinstance(r, dict)}
    out = []
    for p in record.get("pages") or []:
        if not isinstance(p, dict) or p.get("error"):
            continue
        if p.get("kind") != "unknown" or p.get("n") in has_rows:
            continue
        out.append(p.get("n"))
    return [n for n in out if n]


def with_page(record: dict, page_n: int, page: dict,
              rows: list[dict]) -> dict | None:
    """The record with `page_n` read again, or None to refuse the reading.

    None is returned when the page still reads nothing — rewriting the file
    would cost every future run the cache it resumes from — and when the page
    already has rows, because row `n` is a band index and a second set of rows
    would draw two names against one line of the scan.
    """
    if not rows:
        return None
    if any(r.get("page") == page_n for r in record.get("rows") or []
           if isinstance(r, dict)):
        return None
    pages, found = [], False
    for p in record.get("pages") or []:
        if isinstance(p, dict) and p.get("n") == page_n:
            p, found = page, True
        pages.append(p)
    if not found:
        return None
    fresh = [{**r, "page": page_n} for r in rows]
    out = dict(record)
    out["pages"] = pages
    out["rows"] = sorted([*(record.get("rows") or []), *fresh],
                         key=lambda r: (r.get("page") or 0, r.get("n") or 0))
    return out
