"""Which rows are worth a second look, and why.

Written three times before it was written once: the review screen marks rows
for a person, `bench_check.py` scores the marking against the hand-read pages,
and the offline batch has to decide which rows to hand a second recogniser —
before any index exists, from the stored record alone. Three copies drift, and
these two had: the bench knew a reading could be one stroke from a name in a
language list and the screen did not, so the screen was measured on a rule it
was not running.

The reasons, and what each was measured to be worth over 139 hand-read rows of
which 67 were badly read (`scripts/bench_check.py`):

* `score` — the recogniser's own confidence below `CHECK_SCORE`. Catches 81%,
  and 71% of what it flags is wrong.
* `inferido` — a surname inherited from the row above by position rather than
  by a repetition mark. Wrong 94% of the times it fires.
* `desconhecido` — nothing in the reading resembles a name the archive carries.
  Nearly always wrong and nearly never fires: 3 rows of 139.
* `quase` — a word that is not a name but is one stroke from one. 56% on its
  own, and takes the first three from 74% to 86% together. It stops a person
  on one correctly read row in five.
* `quase-lista` — the same question asked of the spoken-name lists rather than
  of the archive, for a passenger whose name this archive has never carried.
* `colado` — two names the recogniser ran into one word. Search reaches such a
  row through the split it indexes beside the reading (T13); a person scanning
  the page has nothing to tell `MarcelloNittoms` from a long surname.
"""
from __future__ import annotations

from .gazetteer import Names
from .rowfields import name_score

# Measured, not chosen: below this the recogniser's own score is worth a
# person's time. See the module docstring for what each reason catches.
CHECK_SCORE = 0.85


def why_check(row: dict, names: Names,
              spoken: set[str] | None = None) -> list[str]:
    """The reasons this row is worth a second look, in the order they matter.

    `spoken` is the union of the language name lists. Left out, the row is
    asked about only against the archive's own names, which is what the review
    screen did for as long as the two copies disagreed.
    """
    from . import search as _s          # imports this module's siblings

    out = []
    score = name_score(row)
    if score is not None and score < CHECK_SCORE:
        out.append("score")
    if row.get("ditto_source") == "position":
        out.append("inferido")
    text = _s.row_text(row)
    if names.doubtful(text):
        out.append("desconhecido")
    if names.near_miss(text):
        out.append("quase")
    elif spoken and names.near_miss(text, spoken=spoken):
        # the same reason found in the other list, and a row already flagged
        # `quase` is not worth flagging twice
        out.append("quase-lista")
    if any(_s.unglued(w) for w in text.split()):
        out.append("colado")
    return out


def flagged(record: dict, names: Names,
            spoken: set[str] | None = None) -> set[tuple[int, int]]:
    """The `(page, row)` of every row in a stored record worth reading again.

    What the batch asks before it spends two seconds of a second recogniser on
    a row. Headings are not somebody's name and are never worth the reading —
    the engine stores the printed heading line as a row, and a heading resembles
    no name in the archive, so `desconhecido` flags every one of them.
    """
    out = set()
    for r in record.get("rows") or ():
        if r.get("header"):
            continue
        if why_check(r, names, spoken):
            out.add((r.get("page"), r.get("n")))
    return out
