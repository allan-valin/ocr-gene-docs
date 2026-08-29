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


def pages_wanting_a_reading(record: dict, schema: int = 0) -> list[int]:
    """Page numbers stored with no reading that the engine could try again.

    A page the engine *failed* on is not one of them: an error makes the whole
    record stale, and an index run reads the document from the top. Repairing
    it here would take the document off that list with nobody told.

    Nor is a page that was already read again by this engine and came back
    empty. Two hundred of them are genuinely blank paper, and re-proving that
    on every future run costs an hour and finds nobody. The stamp is the
    engine's schema, so when the engine learns something they all come back.

    A page stored as a `list` with no rows on it counts as well, and did not
    before. It is the same failure wearing the other label — the geometry found
    a table and no rows on it, and nobody was told — and after the last retry
    pass twelve records on disk are in exactly that state. They are the pages
    the faint lift in `engine_paddle.lift` was written for.
    """
    if not record or not record.get("engine"):
        return []          # a document nobody read is an index run's work
    has_rows = {r.get("page") for r in record.get("rows") or []
                if isinstance(r, dict)}
    out = []
    for p in record.get("pages") or []:
        if not isinstance(p, dict) or p.get("error"):
            continue
        if p.get("n") in has_rows:
            continue
        if p.get("kind") not in ("unknown", "list"):
            continue
        if schema and int(p.get("retried") or 0) >= schema:
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


def with_page_remeasured(record: dict, page_n: int, page: dict,
                         rows: list[dict]) -> dict | None:
    """The record with `page_n` read again over rows it already had, or None.

    `with_page` refuses a page that already has rows, and it is right to: it
    exists so a second reading never draws two names against one line of the
    scan. This is the other case. A page whose name column was measured wrong
    has rows, and they are the ordinal strip read as a name — `ete do Coeto`
    for *Julio Augusto da Costa*. Those rows are the engine's own and the point
    of reading again is to replace them.

    What a person typed is never replaced. The mark is the row's, not the
    record's — `typed_by_a_person` — so a corrected row survives at its own
    place and everything the engine wrote goes.

    None when the re-read produced nothing: an empty page is a failure, not a
    page with nobody on it, and it must not stand in for what was there.
    """
    from desembarque.batch import typed_by_a_person
    if not rows:
        return None
    if not any(isinstance(p, dict) and p.get("n") == page_n
               for p in record.get("pages") or []):
        return None
    theirs = {r.get("n"): r for r in record.get("rows") or []
              if isinstance(r, dict) and r.get("page") == page_n
              and typed_by_a_person(r)}
    fresh = [dict(theirs.get(r.get("n"), r), page=page_n) for r in rows]
    # a row somebody typed that the new reading has no band for is kept
    kept = [r for n, r in theirs.items()
            if not any(f.get("n") == n for f in fresh)]
    others = [r for r in record.get("rows") or []
              if isinstance(r, dict) and r.get("page") != page_n]
    pages = [page if isinstance(p, dict) and p.get("n") == page_n else p
             for p in record.get("pages") or []]
    out = dict(record)
    out["pages"] = pages
    out["rows"] = sorted([*others, *fresh, *kept],
                         key=lambda r: (r.get("page") or 0, r.get("n") or 0))
    return out


def with_nothing_found(record: dict, page_n: int, schema: int) -> dict | None:
    """The record with `page_n` marked as read again and still empty.

    Nothing else moves — not the rows, not what a person typed over them, not
    the record's own stamps. This says one page was tried by one engine, which
    is the only thing that was learned.
    """
    pages, found = [], False
    for p in record.get("pages") or []:
        if isinstance(p, dict) and p.get("n") == page_n:
            p, found = {**p, "retried": int(schema)}, True
        pages.append(p)
    if not found:
        return None
    out = dict(record)
    out["pages"] = pages
    return out
