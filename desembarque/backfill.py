"""Put back the measurement a stored record's rows were cut from.

The engine measures a page's grid to cut the rows out of it, and returned that
measurement all along; the server never copied it onto the page it stored. So
658 of the 660 records on disk carry no geometry, and a search hit can name the
row it found without showing where on the scan it sits — which is the one thing
that makes a mangled reading usable, because the person checks the image and
not the transcription.

The repair does not need the engine and does not need the pages read again. Row
geometry is a measurement on the page image, the extracted images are still in
`data/pagecache`, and only the page a dossier's rows came from has to be
measured: half an hour against three and a half.

The refusal here is the point. Row `n` is its band's index, so a band list that
is shorter than the rows on disk does not lose a few bands at the end — it
draws every row after the first difference against somebody else's line. A
wrong band with a picture beside it is worse than no band.
"""
from __future__ import annotations


def pages_wanting_geometry(record: dict) -> list[int]:
    """Page numbers that have rows on disk and no measurement beside them."""
    have = {p.get("n"): p for p in record.get("pages") or []
            if isinstance(p, dict)}
    wanted = []
    for n in sorted({r.get("page") for r in record.get("rows") or []
                     if isinstance(r, dict) and r.get("page")}):
        page = have.get(n)
        if page is not None and not page.get("geometry"):
            wanted.append(n)
    return wanted


def with_geometry(record: dict, page_n: int, geo: dict | None) -> dict | None:
    """The record with `page_n`'s geometry restored, or None to refuse it.

    None is returned when nothing was measured, and when the measurement
    disagrees with the rows already stored. The schema is deliberately left
    where it is: this is a measurement that was taken and dropped, not a fresh
    reading of the page, and moving the stamp would mark every record stale.
    """
    bands = (geo or {}).get("rows") or []
    if not bands:
        return None
    highest = max((r.get("n") or 0) for r in record.get("rows") or []
                  if isinstance(r, dict) and r.get("page") == page_n)
    if len(bands) < highest:
        return None

    pages = []
    changed = False
    for p in record.get("pages") or []:
        if isinstance(p, dict) and p.get("n") == page_n:
            p = {**p, "geometry": geo}
            changed = True
        pages.append(p)
    if not changed:
        return None
    out = dict(record)
    out["pages"] = pages
    return out
