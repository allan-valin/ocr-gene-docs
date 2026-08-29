"""What a row says, asked in one place.

A row of a passenger list has been through three shapes. It began carrying
`surname` and `given`, split off the reading by `split_name`; the repetition
mark was resolved into `surname` too; and `conf` was keyed `surname`, though
that number was never the surname's score — it is the score of the whole name
strip the recogniser read.

T6 in `docs/TASKS-reading-quality.md` says why the split goes: these forms are
written in more than one order, the same passengers appear twice in one dossier
with the surname at either end, and a derivation made the wrong way round is a
claim the archive does not support. `name_raw` is the row's name; `inherited`
is what a repetition mark repeats; nothing asserts an order.

660 records on disk carry the old shape, and the corpus is deliberately not
re-read — re-reading it to pick up a rename produces data, not knowledge. So
every reader understands both shapes and only the new one is ever written, and
that rule lives here rather than being spelled out at nine call sites.
"""
from __future__ import annotations


def name_score(row: dict | None) -> float | None:
    """The recogniser's score for the name strip, or None if it never read one.

    Nothing read and read badly are different claims: a row the engine never
    attempted must not sort above one it read with no confidence, so an absent
    score is None and never 0.0.
    """
    conf = (row or {}).get("conf") or {}
    for key in ("name", "surname"):
        if conf.get(key) is not None:
            return conf[key]
    return None
