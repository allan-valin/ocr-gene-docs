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
        elif _first_token_is_mark(raw) and last and since <= MAX_GAP:
            rest = " ".join(parts[1:]).strip()
            row["surname"] = last
            row["given"] = rest or row.get("given") or ""
            row["ditto"] = ["surname"]
        elif is_mark(raw):
            # nothing but the mark: the row means the same surname and the
            # clerk wrote no given name to go with it
            if last and since <= MAX_GAP:
                row["surname"] = last
                row["ditto"] = ["surname"]
        else:
            if row.get("surname") and not is_mark(row.get("surname")):
                last = row["surname"]
        since = 0
        out.append(row)
    return out
