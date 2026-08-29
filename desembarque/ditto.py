"""Resolve the repetition mark without erasing it.

These lists are written by family: the surname once, and a ditto mark under it
for every relative below. BS.ENT.013947 p3 lists forty-eight people under nine
surnames, so thirty-nine of its rows say `"` where the name goes. Indexed as
written, one Martinez is findable and the other six are not — and a person
searching for an ancestor knows the surname far better than anything else on the
sheet.

The mark is what the page says; the words it repeats are what the row means.
Both are kept: `name_raw` is untouched, `inherited` holds the words taken from
the row the mark points at, and `ditto` names the field that was inherited so
the UI can show it as inherited rather than as read.

Nothing here says which part of a name is the family name. That was
`split_name`'s assumption, and on a page written given-name-first it filed four
people under *Benito*; see T6 in docs/TASKS-reading-quality.md.
"""
from __future__ import annotations

# What the clerk's mark comes back as. It is drawn as a pair of small strokes,
# and the recogniser calls it whatever it happens to look like — never the same
# character twice across a page. `n` and `u` are in here because a pair of
# strokes joined at the foot is exactly what they look like; a single letter
# alone in the name column is not a name anyone can search for either way.
MARKS = set('"“”„«»\'‘’,.-=/|〃_~*:;`^·')
MARK_WORDS = {"11", "n", "u", "ii", "il", "li", "y", "v"}
# How many blank rows may sit between a mark and the name it points at. A blank
# line is a ruled line nobody wrote on; a run of them is the end of the list.
#
# Two rather than four, on a measurement that came out flat: findable names are
# 95 of 142 at a gap of two and of four, and 94 at eight or twenty. Since it buys
# nothing, the tighter gap is right — it leaves 28.9% of rows with an inferred
# surname instead of 30.9%, and an inference the tool did not have to make is one
# nobody has to check.
MAX_GAP = 2
# How far into the name column the writing has to start before the row reads as
# a continuation rather than a name. The clerk indents under the mark, and the
# mark itself is small enough that the recogniser often returns the given name
# with nothing else — on BS.ENT.013947 p3 that is most of the page.
INDENT_FLOOR = 0.18


def is_mark(text: str | None) -> bool:
    """Whether this reading is a repetition mark rather than a name."""
    t = (text or "").strip()
    if not t:
        return False
    if t.lower() in MARK_WORDS:
        return True
    return all(c in MARKS for c in t)


def _strip_mark(text: str) -> str | None:
    """What is left of a reading after the repetition mark in front of it.

    The mark is a pair of small strokes and the recogniser rarely gives it a
    space: `"Joze`, `"ose`, `,Friancisca`, `6yElviia`. Read as written, those
    rows are unfindable — a search for the surname the mark stands for cannot
    reach them, and they are most of a family list.
    """
    t = (text or "").lstrip()
    i = 0
    while i < len(t) and t[i] in MARKS:
        i += 1
    rest = t[i:].lstrip()
    if not i or not rest:
        return None
    # what remains has to look like a name rather than the tail of the mark
    return rest if sum(c.isalpha() for c in rest) >= 3 else None


def written(name_raw: str | None) -> list[str]:
    """The words this row writes for itself, with any repetition mark dropped.

    `" Maria` writes *Maria*; `"ose` writes *ose*, since the clerk's mark rarely
    comes back with a space after it; a mark alone writes nothing. What the row
    means is these words after the ones it inherits.
    """
    raw = (name_raw or "").strip()
    if not raw:
        return []
    if is_mark(raw):
        return []
    parts = raw.split()
    if _first_token_is_mark(raw):
        return parts[1:]
    rest = _strip_mark(raw)
    return rest.split() if rest else parts


def _first_token_is_mark(text: str | None) -> bool:
    parts = (text or "").split()
    return bool(parts) and is_mark(parts[0])


def inherited_from(above: list[str], written: int) -> list[str]:
    """Which words of the row above a mark stands for.

    The clerk wrote *the same as above* and wrote it in a place: the words this
    row does not write, counted from the left, which is where the column puts
    them. A mark with nothing beside it repeats the whole name.

    Deliberately not a claim about which word is the family name. `split_name`
    made that claim — everything but the last word is the surname — and on a
    page written given-name-first it filed four people under *Benito* and four
    under *Pastre marco*. One document carries both orders, and which is which
    is the reader's call.
    """
    if not above:
        return []
    keep = len(above) - written
    if keep <= 0:
        keep = 1 if written < len(above) else len(above)
    return above[:keep]


def resolve(rows: list[dict]) -> list[dict]:
    """The same rows, with what the mark repeats filled in and marked."""
    out: list[dict] = []
    last: str | None = None
    above: list[str] = []
    since = 0
    for row in rows:
        row = dict(row)
        raw = (row.get("name_raw") or "").strip()
        parts = raw.split()
        if not raw:
            since += 1
            out.append(row)
            continue
        indented = (row.get("indent") is not None
                    and row["indent"] >= INDENT_FLOOR
                    and len(parts) == 1
                    and not is_mark(raw))
        if indented and last and since <= MAX_GAP:
            # the mark itself did not survive the recogniser; the indent it was
            # written under did
            row["inherited"] = inherited_from(above, len(parts))
            row["ditto"] = ["name"]
            row["ditto_source"] = "indent"
        elif (_first_token_is_mark(raw) or _strip_mark(raw)) and last and since <= MAX_GAP:
            rest = (" ".join(parts[1:]).strip() if _first_token_is_mark(raw)
                    else _strip_mark(raw))
            row["inherited"] = inherited_from(above, len(rest.split()))
            row["ditto"] = ["name"]
            row["ditto_source"] = "mark"
        elif is_mark(raw):
            # nothing but the mark: the row means the same surname and the
            # clerk wrote no given name to go with it
            if last and since <= MAX_GAP:
                row["inherited"] = inherited_from(above, 0)
                row["ditto"] = ["name"]
                row["ditto_source"] = "mark"
        elif len(parts) >= 2 and not is_mark(parts[0]):
            # Only a row that names two things sets the family surname. A row
            # read as one word is far more often a given name under a mark the
            # recogniser dropped than a new family — taking it made `"ose`
            # inherit `Maria`.
            # What the marks below repeat: the words of this row, as written.
            # Read off `name_raw` rather than off a stored `surname`, because
            # that field is the assumption this work is removing — and for a
            # row the engine split, the two agree anyway.
            above = parts
            # that there *is* a family above, which is all this now says. It
            # used to be the family name, read off a stored `surname`, and that
            # field is the assumption T6 removes: `inherited` is the output.
            last = raw
        elif last and since <= MAX_GAP and len(parts) == 1:
            # A single name under a family, with no mark that survived and no
            # indent to prove one: on these forms that is a continuation, and
            # read as written the row is unfindable by the only thing a
            # searcher reliably knows. Inherited, and labelled as inferred
            # rather than read, because the difference is the whole point.
            row["inherited"] = inherited_from(above, len(parts))
            row["ditto"] = ["name"]
            row["ditto_source"] = "position"
        since = 0
        out.append(row)
    return out
