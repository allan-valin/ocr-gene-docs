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

from .batch import typed_by_a_person


def with_second_readings(record: dict, said: dict[int, dict[int, str]],
                         model: str) -> tuple[dict, int]:
    """The record with `said` written onto its rows, and how many landed.

    `said` is page number -> row number -> what the other recogniser read,
    which is the shape `read_bands.py`'s sidecar carries once its string keys
    are numbers: those row numbers are the engine's own, given to the crop when
    it was cut, so nothing has to be aligned.

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
        had = r.get("second_read") or {}
        if had.get("text") == want and had.get("model") == model:
            rows.append(r)
            continue
        rows.append({**r, "second_read": {"model": model, "text": want}})
        landed += 1
    if not landed:
        return record, 0
    return {**record, "rows": rows}, landed
