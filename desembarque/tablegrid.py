"""Where the table is, read off what is printed on it.

The rules on these sheets are the least reliable thing about them, and until now
they decided everything. The vertical ones are faint or absent on most pages, so
the name column — taken as the widest gap between the rules that *were* found —
came out as the Procedencia column on BS.ENT.013947 p3 and as two thirds of the
sheet on BS.ENT.013983 p2, and the recogniser was handed a strip of ditto marks
or half the form. The horizontal ones are dotted: the comb fitted to them locked
onto the empty ruled area below the list on 013983, and sat half a row out of
phase on 013942, so every crop carried the descenders of one row and the
ascenders of the next. That is where the gibberish comes from.

Two things on these pages are printed and read cleanly, on every list in the
corpus: the column headings, and the ordinal in the first column — printed on
every ruled row whether anybody wrote on it or not. This module finds the table
from those, using the detector's own boxes, which cost nothing extra: the same
pass already reads the letterhead and the voyage.
"""
from __future__ import annotations

import difflib
import re
import statistics
import unicodedata

# What the name column is called on the seven printings in this corpus.
NAME_HEADINGS = ("nome e cognomes", "nomes e cognomes", "nome e cognome",
                 "nomes e sobrenomes", "nomes", "cognomes")
HEADING_FLOOR = 0.72
# A heading has to sit on the heading's own line to bound the column. The
# printings put the headings at slightly different heights, and the detector
# reports each in its own box.
ROW_OVERLAP = 0.3
# How much of a fragment has to lie in the name column before it counts as
# written on that row. The detector often runs a whole row into one box —
# `Potrcelli Soveni Nalia 3% eado` is a name, a nationality, an age and a marital
# state — so the test is overlap, not the box's centre.
COLUMN_OVERLAP = 0.35
# How many printed ordinals have to be legible before they are trusted to set
# the pitch rather than the writing.
MIN_ORDINALS = 8


def fold(text: str) -> str:
    s = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in s if not unicodedata.combining(c)).strip().lower()


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _same_box(a: dict, b: dict, tol: float = 2.0) -> bool:
    return all(abs(a[k] - b[k]) <= tol for k in ("x0", "y0", "x1", "y1"))


def _heading(fragments: list[dict]) -> dict | None:
    best, score = None, 0.0
    for f in fragments:
        t = " ".join(fold(f.get("text", "")).split())
        if not t:
            continue
        s = max(difflib.SequenceMatcher(None, t, h).ratio() for h in NAME_HEADINGS)
        if s > score:
            best, score = f, s
    return best if score >= HEADING_FLOOR else None


def columns(fragments: list[dict], width: float, height: float,
            labelled: list[dict] | None = None) -> dict | None:
    """The name column, the ordinal column beside it, and where the table starts.

    None when the page prints no name heading — a cover card, the interpreter's
    PARTE, a sheet whose top is torn away. That is a legitimate answer and the
    caller falls back to the rules.
    """
    # The heading is found among the fragments that carry text; the column's
    # edges are then taken from every box on the heading's line, read or not.
    head = _heading(labelled if labelled is not None else fragments)
    if head is None:
        return None
    hh = head["y1"] - head["y0"]
    same = [f for f in fragments
            if not _same_box(f, head)
            and _overlap(f["y0"], f["y1"], head["y0"], head["y1"]) >= ROW_OVERLAP * hh]
    left = [f for f in same if f["x1"] <= head["x0"] + 2]
    right = [f for f in same if f["x0"] >= head["x1"] - 2]
    margin = 0.02 * width
    x0 = max((f["x1"] for f in left), default=head["x0"] - margin)
    x1 = min((f["x0"] for f in right), default=head["x1"] + margin)
    ordinal = None
    if left:
        nearest = max(left, key=lambda f: f["x1"])
        ordinal = (min(f["x0"] for f in left
                       if f["x1"] >= nearest["x1"] - 0.05 * width), x0)
    return {"name": (x0, x1), "ordinal": ordinal, "top": head["y1"],
            "heading": head}


def _pitch(centres: list[float]) -> float | None:
    # the detector reports its boxes in its own order, which is not the page's
    centres = sorted(centres)
    gaps = [b - a for a, b in zip(centres, centres[1:]) if b - a > 1]
    if not gaps:
        return None
    rough = statistics.median(gaps)
    # A row is missed here and there, so a gap is often two rows or three. Only
    # the gaps near the median vote on the pitch.
    near = [g for g in gaps if 0.6 * rough <= g <= 1.4 * rough]
    return statistics.median(near) if near else rough


def _ordinals(fragments: list[dict], col: dict) -> list[dict]:
    """The printed line numbers, which are on every row including the empty ones.

    A box with no text is judged by where it sits and how big it is: measuring
    the table needs the detector's boxes and not the recogniser's opinion of
    them, and detection alone costs three seconds against the eighty a dense
    page costs to read.
    """
    if not col.get("ordinal"):
        return []
    a, b = col["ordinal"]
    out = []
    for f in fragments:
        if f["y0"] <= col["top"]:
            continue
        if _overlap(f["x0"], f["x1"], a, b) < 0.5 * (f["x1"] - f["x0"]):
            continue
        if f.get("text") is None:
            # unread box: it is in the ordinal column and no wider than it
            if f["x1"] - f["x0"] <= 1.2 * (b - a):
                out.append(f)
            continue
        t = re.sub(r"\W", "", f.get("text", ""))
        if t and len(t) <= 3 and sum(c.isdigit() for c in t) >= len(t) - 1:
            out.append(f)
    return out


def written_lines(fragments: list[dict], col: dict) -> list[dict]:
    """The fragments that lie on the name column, below the heading.

    Two ways to qualify, because the detector's boxes vary in how much of a row
    they take in. A box that is mostly inside the column is a name. So is a box
    that *covers* the column — on BS.ENT.013942 the whole row comes back as one
    box from the number to the observations, `Potrcelli Soveni Nalia 3% eado`,
    and only a quarter of it is the name. Judged by the box alone that row was
    thrown away, and the page reported thirty-one empty rows with the one name
    on it missing.
    """
    x0, x1 = col["name"]
    out = []
    for f in fragments:
        if f["y0"] <= col["top"]:
            continue
        over = _overlap(f["x0"], f["x1"], x0, x1)
        if over >= COLUMN_OVERLAP * (f["x1"] - f["x0"]) or over >= 0.5 * (x1 - x0):
            out.append(f)
    out.sort(key=lambda f: f["y0"])
    return out


def row_anchors(fragments: list[dict], col: dict | None,
                height: float) -> list[tuple[float, float]]:
    """One band per ruled row, in page order.

    The pitch comes from the printed ordinals where they are legible, because
    they are printed on empty rows too and a list is mostly empty rows. The
    phase comes from the same place, so a band is centred on its row rather than
    on the rule between two of them. A row somebody wrote on is widened to hold
    what they wrote: the hand runs above and below the ruled line, and cutting
    at the line cuts the ascenders off.
    """
    if not col:
        return []
    ords_ = _ordinals(fragments, col)
    written = written_lines(fragments, col)
    ord_c = [(f["y0"] + f["y1"]) / 2 for f in ords_]
    wri_c = [(f["y0"] + f["y1"]) / 2 for f in written]
    # The ordinals are the better anchor because they are printed on the empty
    # rows too — but only while they are actually being read. On BS.ENT.015061
    # p6 five of the seventy-odd numbers came through, three rows apart, and
    # they outvoted forty-six written lines: the page came back with sixteen
    # bands, each three rows tall. Whichever source has more anchors wins.
    use = ord_c if len(ord_c) >= max(MIN_ORDINALS, 0.5 * len(wri_c)) else wri_c
    pitch = _pitch(use) or _pitch(ord_c) or _pitch(wri_c)
    if not pitch:
        return []

    anchors = sorted(use or ord_c or wri_c)
    base = anchors[0]
    # Index every anchor against the pitch, then take the phase that most of
    # them agree on rather than whichever happened to come first.
    offsets = [(c - base) - round((c - base) / pitch) * pitch for c in anchors]
    base += statistics.median(offsets)

    lo = min([*ord_c, *wri_c])
    hi = max([*ord_c, *wri_c])
    first = round((lo - base) / pitch)
    last = round((hi - base) / pitch)
    bands = []
    for i in range(first, last + 1):
        centre = base + i * pitch
        top, bottom = centre - pitch / 2, centre + pitch / 2
        for f in written:
            c = (f["y0"] + f["y1"]) / 2
            if top <= c <= bottom:
                top = min(top, f["y0"] - 1)
                bottom = max(bottom, f["y1"] + 1)
        bands.append((max(0.0, top), min(height, bottom)))
    return bands


class TableGeometry:
    """The same interface `Geometry` offers, measured from the printing instead.

    The engine, the row cutter and the review UI all take a geometry and ask it
    for normalised bands and a name column; where those numbers come from is
    this module's business. Kept as a separate type rather than a `Geometry`
    with different numbers in it, because the fields differ in kind: there are
    no rule edges here, only bands that were fitted to what is printed on the
    rows.
    """

    def __init__(self, width: float, height: float, bands: list[tuple[float, float]],
                 name: tuple[float, float], ordinal: tuple[float, float] | None = None,
                 top: float = 0.0):
        self.width = float(width)
        self.height = float(height)
        self.skew = 0.0
        self.bands = bands
        self.name = name
        self.ordinal = ordinal
        self.top = top

    @property
    def rows(self) -> list[tuple[float, float]]:
        return list(self.bands)

    @property
    def row_edges(self) -> list[float]:
        # what `header_box` reads: the strip above the table ends where the
        # first row begins
        return [self.top] + [e for band in self.bands for e in band]

    @property
    def table_box(self):
        return (self.name[0], self.top, self.name[1], self.bands[-1][1]) if self.bands else None

    def normalized_rows(self) -> list[tuple[float, float]]:
        return [(t / self.height, b / self.height) for t, b in self.bands]

    def normalized_cols(self) -> list[float]:
        return [self.name[0] / self.width, self.name[1] / self.width]

    def name_column(self, index: int = 0):
        return tuple(self.normalized_cols())


def table(fragments: list[dict], width: float, height: float,
          labelled: list[dict] | None = None) -> TableGeometry | None:
    """The table on this page, or None when the page prints no name heading.

    `fragments` are the detector's boxes, which may carry no text; `labelled`
    are the few that were recognised in order to find the heading.
    """
    col = columns(fragments, width, height, labelled)
    if not col:
        return None
    bands = row_anchors(fragments, col, height)
    if not bands:
        return None
    return TableGeometry(width, height, bands, col["name"], col["ordinal"],
                         col["top"])


# A table's heading row is a line of several short boxes across the sheet, and
# it is the only line that has to be read to know which column is which.
HEADING_MIN_CELLS = 4
HEADING_MAX_LINES = 4
# A table's heading row runs the width of the sheet. The letterhead above it
# does not: it is centred, or set in two columns, and on the busier printings
# there are three or four such lines above the table — enough to crowd the
# heading out of the candidates entirely on BS.ENT.015937 and BS.ENT.016574.
HEADING_MIN_SPAN = 0.55


def lines_of(boxes: list[dict], tolerance: float = 0.5) -> list[list[dict]]:
    """The boxes grouped into the lines they sit on."""
    out: list[list[dict]] = []
    for b in sorted(boxes, key=lambda f: f["y0"]):
        h = b["y1"] - b["y0"]
        for line in out:
            ref = line[-1]
            if _overlap(b["y0"], b["y1"], ref["y0"], ref["y1"]) >= tolerance * h:
                line.append(b)
                break
        else:
            out.append([b])
    return out


def heading_lines(boxes: list[dict], height: float) -> list[dict]:
    """The few boxes worth recognising to find the column headings.

    A heading row is several short boxes on one line, above the writing. The
    candidates are read; everything else on the page stays a box.
    """
    width = max((b["x1"] for b in boxes), default=0.0)
    lines = [ln for ln in lines_of(boxes)
             if len(ln) >= HEADING_MIN_CELLS
             and min(b["y0"] for b in ln) < 0.7 * height
             and (max(b["x1"] for b in ln) - min(b["x0"] for b in ln))
             >= HEADING_MIN_SPAN * width]
    # The topmost such lines, not the most populous: a data row has a cell in
    # every column and often one more than the heading — on BS.ENT.013983 the
    # rows outvoted the heading and the page fell back to its rules.
    lines.sort(key=lambda ln: min(b["y0"] for b in ln))
    return [b for ln in lines[:HEADING_MAX_LINES] for b in ln]
