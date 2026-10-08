"""Which of the engine's bands a reader can actually see on the reading sheet.

Allan read the first sheet (2026-10-07) and the numbers did not line up: the
engine cuts bands that overlap their neighbours, and on BS.ENT.016317 p4 three
of its 42 bands are almost entirely under the band below them. On the sheet,
each band's number sits in a gutter box drawn in band order, so a band mostly
covered by the next one shows as a sliver with no legible number, and a reader
counting rows down the page skips it. Three skipped slivers and the typed
numbers are three off by the bottom of the page.

So a band whose own extent above the next band is under `MIN_VISIBLE` of the
page's median band height is not a row anybody can type against. The sheet
draws only the visible ones, and a sheet typed positionally (the first sheet,
before the boxes carried the engine's own reading) is mapped back through the
same rule.

The second thing a reader skips is the printed heading. The engine counts the
heading line and the blank under it as bands 1 and 2 on most typed pages, and
a reader types the first *name* into box 1. `heading_offset` says how many
leading bands carry no passenger.
"""
from __future__ import annotations

import re
import statistics

MIN_VISIBLE = 0.4

# What the engine reads off a heading band: the printed column titles, in the
# three languages these forms come in, and the ordinal column's own title.
HEADING = re.compile(r"NOME|COGNOME|NAME|APELLIDO|NUMERO|ORDEM|PASSAGEIRO",
                     re.IGNORECASE)


def visible_bands(rows: list, min_visible: float = MIN_VISIBLE) -> list[int]:
    """The 1-based numbers of the bands a reader can see on the sheet.

    `rows` is the page geometry's list of (top, bottom) in page fractions, in
    the order the engine numbered them.
    """
    bands = [tuple(b) for b in rows if b and len(b) == 2]
    if not bands:
        return []
    median = statistics.median(b - a for a, b in bands) or 1e-9
    out = []
    for i, (a, b) in enumerate(bands):
        nxt = bands[i + 1][0] if i + 1 < len(bands) else b
        shown = min(b, nxt) - a
        if shown / median >= min_visible:
            out.append(i + 1)
    return out


def representative_bands(rows: list, texts: dict[int, str | None],
                         min_visible: float = MIN_VISIBLE) -> list[int]:
    """One band number per row a reader can see: the visible band itself, or
    the sliver hidden under it when that is the one carrying the reading.

    On 016317 p4 the engine's band 3 is a sliver under band 4 and the two are
    the same ink, but the reading sits on 3 and 4 says nothing. A name typed
    against 4 would be paired with nothing and drop out of the measure, so
    the row is numbered by the band that can be scored.
    """
    bands = [tuple(b) for b in rows if b and len(b) == 2]
    shown = visible_bands(bands, min_visible)
    hidden = [n for n in range(1, len(bands) + 1) if n not in shown]
    out = []
    for n in shown:
        if (texts.get(n) or "").strip():
            out.append(n)
            continue
        a, b = bands[n - 1]
        twin = None
        for h in hidden:
            c, d = bands[h - 1]
            overlap = min(b, d) - max(a, c)
            if overlap > 0.5 * (d - c) and (texts.get(h) or "").strip():
                twin = h
                break
        out.append(twin or n)
    return out


def is_heading(text: str | None) -> bool:
    return bool(HEADING.search(text or ""))


def heading_offset(texts: list[str | None]) -> int:
    """How many leading bands are the printed heading and the blank under it.

    Counted only when a heading is actually read among the leading bands: a
    cursive page whose first band the engine read as nothing is a page whose
    first row is a name nobody could read, not a heading.
    """
    offset = 0
    saw_heading = False
    for t in texts:
        t = (t or "").strip()
        if is_heading(t):
            saw_heading = True
            offset += 1
        elif not t and saw_heading:
            offset += 1
        else:
            break
    return offset if saw_heading else 0


def positional_map(keys: list[int], rows: list, texts: dict[int, str | None]
                   ) -> dict[int, int | None]:
    """Where each positionally typed box lands among the engine's bands.

    Box k (1-based) is the k-th visible band after the heading. A box with no
    band left under it maps to None — the page had more names than the engine
    cut bands, and those names are lost to this measurement, not mislabelled.
    """
    visible = representative_bands(rows, texts)
    offset = heading_offset([texts.get(n) for n in visible])
    targets = visible[offset:]
    return {k: (targets[k - 1] if 0 < k <= len(targets) else None)
            for k in keys}


def _sim(a: str, b: str) -> float:
    import difflib
    import re
    a = re.sub(r"[^a-z]", "", (a or "").lower())
    b = re.sub(r"[^a-z]", "", (b or "").lower())
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def align_by_text(mine: list[tuple[int, str]], engine: list[tuple[int, str]],
                  skip_engine: float = 0.9, drop_mine: float = 0.8
                  ) -> dict[int, int | None]:
    """Where each typed box lands, decided by what the engine read there.

    On a typed page the engine's reading is close enough to the name that the
    text itself says which band a box belongs to, and that is worth more than
    counting: on BS.ENT.016429 p3 the engine's bands are a uniform grid that
    misses three of the page's 44 rows, so a count runs ahead of the page
    from the first missed row down. Both sequences are walked in order; a
    pair costs their dissimilarity; skipping an engine band that read as a
    heading or as nothing is free, skipping one that carries a reading costs
    `skip_engine` (a page is read in order, and a name on the page is not
    passed over lightly); dropping a typed row (a row the engine never cut)
    costs `drop_mine`. A dropped row maps to None: the engine lost it, and
    the measure should say so. The families on these lists share a surname
    down twenty rows, so a shifted chain of pairs still looks half right by
    text; the dear skip is what keeps the count honest where the text is
    ambiguous.
    """
    M, E = len(mine), len(engine)
    big = float(M + E + 2)
    free = [not (t or "").strip() or is_heading(t) for _, t in engine]
    best = [[big] * (E + 1) for _ in range(M + 1)]
    back = [[None] * (E + 1) for _ in range(M + 1)]
    # bands above the first typed row and below the last are not evidence
    # against the typing: the dear skip is only for a band between two rows
    # the reader typed
    best[0][0] = 0.0
    for j in range(1, E + 1):
        best[0][j] = 0.0
        back[0][j] = "skip"
    for i in range(1, M + 1):
        best[i][0] = best[i - 1][0] + drop_mine
        back[i][0] = "drop"
        for j in range(1, E + 1):
            take = best[i - 1][j - 1] + (1.0 - _sim(mine[i - 1][1], engine[j - 1][1]))
            skip = best[i][j - 1] + (0.0 if free[j - 1] else skip_engine)
            drop = best[i - 1][j] + drop_mine
            best[i][j] = min(take, skip, drop)
            back[i][j] = ("take" if best[i][j] == take else
                          "skip" if best[i][j] == skip else "drop")
    out: dict[int, int | None] = {}
    i, j = M, min(range(E + 1), key=lambda j: (best[M][j], -j))
    while i > 0 or j > 0:
        step = back[i][j]
        if step == "take":
            out[mine[i - 1][0]] = engine[j - 1][0]
            i, j = i - 1, j - 1
        elif step == "skip":
            j -= 1
        else:
            out[mine[i - 1][0]] = None
            i -= 1
    return out
