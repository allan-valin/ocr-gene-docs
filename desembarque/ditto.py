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
        if _first_token_is_mark(raw) and last and since <= MAX_GAP:
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
