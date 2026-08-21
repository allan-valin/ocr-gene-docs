"""Resolve the repetition mark without erasing it.

These lists are written by family: the surname once, and a ditto mark under it
for every relative below. BS.ENT.013947 p3 lists forty-eight people under nine
surnames, so thirty-nine of its rows say `"` where the name goes. Indexed as
written, one Martinez is findable and the other six are not — and a person
searching for an ancestor knows the surname far better than anything else on the
sheet.

The mark is what the page says; the surname is what the row means. Both are
kept: `name_raw` is untouched, the surname is filled in from the row the mark
points at, and `ditto` names the fields that were inherited so the UI can show
them as inherited rather than as read.
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
MAX_GAP = 4
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


def _first_token_is_mark(text: str | None) -> bool:
    parts = (text or "").split()
    return bool(parts) and is_mark(parts[0])


def resolve(rows: list[dict]) -> list[dict]:
    """The same rows, with inherited surnames filled in and marked."""
    out: list[dict] = []
    last: str | None = None
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
            row["surname"] = last
            row["given"] = raw
            row["ditto"] = ["surname"]
            row["ditto_source"] = "indent"
        elif (_first_token_is_mark(raw) or _strip_mark(raw)) and last and since <= MAX_GAP:
            rest = (" ".join(parts[1:]).strip() if _first_token_is_mark(raw)
                    else _strip_mark(raw))
            row["surname"] = last
            row["given"] = rest or row.get("given") or ""
            row["ditto"] = ["surname"]
            row["ditto_source"] = "mark"
        elif is_mark(raw):
            # nothing but the mark: the row means the same surname and the
            # clerk wrote no given name to go with it
            if last and since <= MAX_GAP:
                row["surname"] = last
                row["ditto"] = ["surname"]
                row["ditto_source"] = "mark"
        elif len(parts) >= 2 and row.get("surname") and not is_mark(row["surname"]):
            # Only a row that names two things sets the family surname. A row
            # read as one word is far more often a given name under a mark the
            # recogniser dropped than a new family — taking it made `"ose`
            # inherit `Maria`.
            last = row["surname"]
        elif last and since <= MAX_GAP and len(parts) == 1:
            # A single name under a family, with no mark that survived and no
            # indent to prove one: on these forms that is a continuation, and
            # read as written the row is unfindable by the only thing a
            # searcher reliably knows. Inherited, and labelled as inferred
            # rather than read, because the difference is the whole point.
            row["surname"] = last
            row["given"] = raw
            row["ditto"] = ["surname"]
            row["ditto_source"] = "position"
        since = 0
        out.append(row)
    return out
