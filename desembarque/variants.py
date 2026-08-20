"""The other things the recogniser said about the same name.

Every row is read from the PDF's embedded ink mask and, where that reading came
back thin, again from a composited render. The two disagree exactly where the
hand is hard — `Nayomgo` and `Raymundo` are one word on one page — and until now
whichever read more names won and the other was discarded. A person correcting
that row then retyped a name the engine had already produced.

What is offered is only ever what was read. A spelling the recogniser never
returned must not appear in a list of what it returned, which is the same rule
the rest of this follows: the tool may be wrong, but it may not invent.
"""
from __future__ import annotations

import difflib


def token_alternatives(readings: list[str]) -> list[list[str]]:
    """Per word of the first reading, the other readings' word for it.

    Alignment is by content rather than by position. One reading dropping an
    initial — `A. VIEIRA MIRANDA` against `VIEIRA MIRANDA` — would otherwise
    offer `VIEIRA` as an alternative spelling of `A.`, which is not a
    disagreement about a word but a different word.
    """
    if not readings:
        return []
    chosen = (readings[0] or "").split()
    out: list[list[str]] = [[] for _ in chosen]
    for other in readings[1:]:
        words = (other or "").split()
        if not words:
            continue
        matcher = difflib.SequenceMatcher(None, chosen, words, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != "replace" or (i2 - i1) != (j2 - j1):
                # An insertion or a deletion is not a second opinion about a
                # word, and a stretch that replaces two words with three has no
                # word-to-word reading to offer.
                continue
            for i, j in zip(range(i1, i2), range(j1, j2)):
                if words[j] not in out[i] and words[j] != chosen[i]:
                    out[i].append(words[j])
    return out
