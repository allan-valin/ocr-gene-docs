"""Cut rows along the paper rather than along a ruler.

A manifest hand does not respect the ruled line. The tail of a `y` in one row
lands inside the row below it -- on ITAPEMA 013990 the leg of "Raymundo" falls
between the `l` and the `f` of "Alfredo J. Tavares" -- and names run past the
column rule into Nacionalidade.

A straight cut at the nominal boundary corrupts both neighbours: one loses the
stroke it owns, the other gains a stroke belonging to nobody on its line. And
`refine()` compounds it, because trimming to ink *expands* a crop toward
whatever intruded into it.

So a boundary is found rather than assumed: the path of least ink across the
strip, free to wander a little around a descender but not free to leave the
neighbourhood of the rule it is replacing. The same routine does columns --
transpose the strip and a horizontal seam becomes a vertical one.

Nothing here is a model. It is the ink telling us where the writing is thin,
which on a table is very nearly always the gap between two lines.
"""
from __future__ import annotations

import numpy as np

# How strongly a seam is pulled back toward the nominal line, per pixel of
# deviation. Small enough that a descender is cheap to go around, large enough
# that the path does not drift off through a blank margin and come back with a
# neighbour's letter in tow.
DRIFT_COST = 0.05


def seam(ink: np.ndarray, at: int, margin: int = 12,
         drift: float = DRIFT_COST) -> np.ndarray:
    """A least-ink path across `ink`, staying within `margin` of row `at`.

    `ink` is a 2-D array where a larger value means more ink. Returns one row
    index per column. Transpose the input to cut between columns instead: the
    result is then one column index per row.

    The path may step at most one pixel per column, which keeps it continuous;
    a boundary that could jump would be free to cut a letter in half.
    """
    if ink.ndim != 2 or ink.size == 0:
        return np.full(max(1, ink.shape[-1] if ink.ndim == 2 else 1), at)
    h, w = ink.shape
    lo = max(0, at - margin)
    hi = min(h, at + margin + 1)
    if hi - lo <= 1:
        return np.full(w, min(max(at, 0), h - 1))

    band = np.asarray(ink[lo:hi], dtype=np.float64)
    rows = band.shape[0]
    # a cheap pull toward the original line, so an empty strip returns it
    band = band + drift * np.abs(np.arange(lo, hi) - at)[:, None]

    cost = np.empty_like(band)
    back = np.zeros(band.shape, dtype=np.int16)
    cost[:, 0] = band[:, 0]
    big = np.inf
    for x in range(1, w):
        prev = cost[:, x - 1]
        up = np.concatenate(([big], prev[:-1]))       # came from y-1
        down = np.concatenate((prev[1:], [big]))      # came from y+1
        stack = np.stack((up, prev, down))            # -1, 0, +1
        choice = np.argmin(stack, axis=0)
        back[:, x] = choice - 1
        cost[:, x] = band[:, x] + stack[choice, np.arange(rows)]

    path = np.empty(w, dtype=np.int64)
    y = int(np.argmin(cost[:, -1]))
    for x in range(w - 1, -1, -1):
        path[x] = y + lo
        y = int(np.clip(y + back[y, x], 0, rows - 1)) if x else y
    return path


def cut_row(grey: np.ndarray, upper: np.ndarray, lower: np.ndarray,
            fill: int = 255) -> np.ndarray:
    """`grey` with everything outside the two seams cleared to `fill`.

    The image keeps its shape: callers trim it afterwards, and a row that has
    been emptied is a real answer worth seeing as an empty band rather than as
    a crop that silently changed size.
    """
    out = np.array(grey, copy=True)
    h, w = out.shape[:2]
    ys = np.arange(h)[:, None]
    up = np.asarray(upper, dtype=np.int64)[None, :]
    dn = np.asarray(lower, dtype=np.int64)[None, :]
    out[(ys < up) | (ys >= dn)] = fill
    return out


def row_seams(ink: np.ndarray, edges: list[tuple[int, int]],
              margin: int | None = None) -> list[tuple[np.ndarray, np.ndarray]]:
    """One (upper, lower) seam pair per band, sharing the boundaries between.

    Neighbouring rows are cut along the *same* path, so a stroke lands on
    exactly one side of it. Cutting each row independently would let a
    descender be claimed twice, or by neither.
    """
    if not edges:
        return []
    if margin is None:
        spans = [b - a for a, b in edges]
        margin = max(4, int(0.35 * (sum(spans) / len(spans))))
    lines = [edges[0][0]] + [b for _, b in edges]
    paths = [seam(ink, int(y), margin=margin) for y in lines]
    return list(zip(paths[:-1], paths[1:]))


def ink_of(grey: np.ndarray) -> np.ndarray:
    """Ink as a positive quantity, however dark the paper is.

    The same threshold `refine()` uses, so a band judged empty here is judged
    empty there too and the two do not disagree about what is on the page.
    """
    a = np.asarray(grey, dtype=np.uint8)
    if a.size == 0:
        return np.zeros_like(a, dtype=np.float64)
    thr = max(60, int(a.mean()) - 35)
    return (a < thr).astype(np.float64)


def carve(strip: np.ndarray, edges: list[tuple[int, int]],
          margin: int | None = None, fill: int = 255) -> list[np.ndarray]:
    """One image per band, with the neighbouring rows' ink removed.

    `strip` is the name column for the whole table, `edges` the band tops and
    bottoms in strip coordinates. Each band is cut along the seams it shares
    with its neighbours, so a descender crossing the nominal line goes to
    whichever row its body is on -- and to exactly one of them.

    Each image is returned cropped to its own band's extent plus the room the
    seams needed, which is what makes the descender a visible difference: the
    row below no longer contains it.
    """
    if not edges:
        return []
    grey = np.asarray(strip)
    ink = ink_of(grey)
    out = []
    for upper, lower in row_seams(ink, edges, margin=margin):
        cut = cut_row(grey, upper, lower, fill=fill)
        top = max(0, int(upper.min()))
        bottom = min(grey.shape[0], int(lower.max()))
        if bottom <= top:
            top, bottom = 0, grey.shape[0]
        out.append(cut[top:bottom])
    return out
