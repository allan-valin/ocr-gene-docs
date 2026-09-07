"""A second recogniser's readings, written onto the rows they were read from.

The measurement lived in a sidecar `bench_search.py` understood and nothing
else did, so the three names it was worth in the top five were three names the
application could not find. This is the write that ends that: the reading goes
on the row as `second_read`, and `desembarque.search` spells the row by it.

The care is the same care every write to this corpus takes. A row a person
typed is never given a machine's reading — the mark is the row's, not the
record's (`batch.typed_by_a_person`) — a reading for a row that is not there is
refused rather than invented, and running the pass twice leaves the corpus as
running it once did, because a run that is not resumable is a run nobody dares
interrupt.
"""
from __future__ import annotations

import difflib

from .batch import typed_by_a_person
from .gazetteer import fold


def same_row(reading: str, text: str, floor: float = 0.8) -> bool:
    """Whether an exported reading and a stored row are the same ink.

    Not a plain comparison, because the two are not the same kind of string.
    The export carries what the recogniser said; the record carries what the
    row is *searched by*, and for a row written with a repetition mark that is
    the words above it followed by its own — `" Maria` is `Martinez Maria`. So
    the reading is also tried against the tail of the stored text, word for
    word, and the better of the two decides.
    """
    a, b = fold(reading), fold(text)
    best = difflib.SequenceMatcher(None, a, b).ratio()
    words = b.split()
    mine = a.split()
    if len(words) > len(mine) >= 1:
        tail = " ".join(words[-len(mine):])
        best = max(best, difflib.SequenceMatcher(None, a, tail).ratio())
    return best >= floor


def with_second_readings(record: dict, said: dict[int, dict[int, str]],
                         model: str,
                         was: dict[tuple[int, int], str] | None = None
                         ) -> tuple[dict, int]:
    """The record with `said` written onto its rows, and how many landed.

    `said` is page number -> row number -> what the other recogniser read,
    which is the shape `read_bands.py`'s sidecar carries once its string keys
    are numbers: those row numbers are the engine's own, given to the crop when
    it was cut, so nothing has to be aligned.

    `was` is what the engine said about each row *on the day the crops were
    cut* — `export_bands.py`'s own index. Those numbers age: the corpus is read
    again, a page is renumbered, and row 14 is no longer the ink row 14's crop
    was cut from. A reading pasted onto it names a stranger, silently, on a row
    that looks no different from a right one. So a row whose stored reading no
    longer resembles what was exported is refused, exactly as the bench refuses
    it — 21 of 1,787 on the fifteen-dossier subcorpus, and every one of them a
    name that would have been given to somebody else. Left out, nothing is
    checked, which is only safe when the sidecar and the records are the same
    reading.

    The count is the caller's reason to save. Nothing landing means nothing to
    write, and a pass over a corpus that rewrites every file to change nothing
    is how mtimes stop meaning anything.
    """
    landed = 0
    rows = []
    for r in record.get("rows") or ():
        want = (said.get(r.get("page")) or {}).get(r.get("n"))
        want = (want or "").strip()
        if not want or typed_by_a_person(r):
            rows.append(r)
            continue
        exported = (was or {}).get((r.get("page"), r.get("n")))
        if exported is not None and not same_row(exported, _text(r)):
            rows.append(r)
            continue
        had = r.get("second_read") or {}
        if had.get("text") == want and had.get("model") == model:
            rows.append(r)
            continue
        rows.append({**r, "second_read": {"model": model, "text": want}})
        landed += 1
    if not landed:
        return record, 0
    return {**record, "rows": rows}, landed


def _text(row: dict) -> str:
    """What the row is searched by, which is what the export has to match."""
    from .search import row_text
    return row_text(row)
