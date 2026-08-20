"""Re-derive a stored record's voyage from the pages already read.

Reading a page as prose costs about twenty seconds and the corpus takes hours,
so every improvement to the way these printed forms are parsed made the whole
corpus stale and unaffordable to refresh — the kind of cost that quietly stops
improvements being made. The text and boxes each voyage was read from are kept
with the record, and this turns a parser change into a re-parse of what is
already on disk.

It is deliberately narrow. It touches the voyage and the schema stamp and
nothing else: not the rows, not what a person typed over them, not the
geometry. Anything that would need the page image again is a re-index, and
should be one.
"""
from __future__ import annotations

from desembarque.voyage import is_complete, merge_voyages, parse_voyage


def reparse(record: dict, schema: int) -> dict | None:
    """The record with its voyage re-read, or None if nothing changed.

    None also covers the records written before the forms were kept: re-parsing
    nothing would replace a voyage that cost twenty seconds to read with no
    voyage at all.
    """
    forms = [p.get("form") for p in record.get("pages") or []
             if isinstance(p, dict) and p.get("form")]
    if not forms:
        return None

    voyage = None
    for form in forms:
        if is_complete(voyage):
            break
        voyage = merge_voyages(voyage, parse_voyage(form.get("text") or "",
                                                    fragments=form.get("fragments")))
    fresh = voyage.as_dict() if voyage else None
    if fresh == record.get("voyage") and int(record.get("schema", 0)) == schema:
        return None
    out = dict(record)
    out["schema"] = schema
    if fresh:
        out["voyage"] = fresh
    else:
        out.pop("voyage", None)
    return out
