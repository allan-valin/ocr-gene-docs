"""Which hand a page is written in, from what the engine already said.

Every number this repository quotes has to be split typed from cursive
(docs/TASKS-honest-measurement.md, T3): the typed pages are effectively solved
and the cursive ones are the point, and blended they say nothing. Splitting
needs a label on every page, and there are 660 documents nobody is going to
look at.

The engine's own confidence does it. On the six pages whose hand is known the
two do not overlap and are not close:

    cursive  0.640  0.793  0.806  0.869
    typed                              0.952  0.989

so the cut is the middle of that gap. This is a threshold on a number already
stored, not new reading — it costs a pass over the records and no OCR at all.

The caution belongs beside it: six pages is a thin thing to set a threshold
on, and four of the six were read by the assistant rather than by a person.
The gap is wide enough that the exact cut hardly matters — anything from 0.87
to 0.95 labels the same six the same way — but a page that lands near it is
the tool guessing, and `--check` prints how many do.
"""
from __future__ import annotations

import statistics

TYPED = "typed"
CURSIVE = "cursive"
UNKNOWN = "unknown"

# the middle of the gap the six known pages leave, rounded to two figures
CUT = 0.91

# a median over one or two readings is noise, not a hand
MIN_ROWS = 3


def page_features(rows: list[dict]) -> dict:
    """What the stored reading says about a page, before any threshold.

    The median rather than the mean: a page is a column of rows and one
    blank-but-confident band should not carry it.
    """
    confs = [(r.get("conf") or {}).get("surname") for r in rows
             if (r.get("name_raw") or "").strip()]
    confs = [float(c) for c in confs if c is not None]
    return {"rows": len(confs),
            "median_conf": statistics.median(confs) if confs else None}


def label_page(rows: list[dict], cut: float = CUT,
               min_rows: int = MIN_ROWS) -> str:
    """`typed`, `cursive`, or `unknown` when there is too little to say."""
    got = page_features(rows)
    if got["rows"] < min_rows or got["median_conf"] is None:
        return UNKNOWN
    return TYPED if got["median_conf"] >= cut else CURSIVE


def label_document(rec: dict, cut: float = CUT,
                   min_rows: int = MIN_ROWS) -> dict:
    """Every page of a record labelled, and the document's own hand.

    The document takes the hand of most of its *rows* rather than most of its
    pages, since a dossier is often one long list and a cover: counting pages
    would let a three-row cover outvote forty rows of cursive. Pages it cannot
    call do not vote.
    """
    by_page: dict[int, list[dict]] = {}
    for r in rec.get("rows") or ():
        if r.get("page"):
            by_page.setdefault(int(r["page"]), []).append(r)

    pages, weight = {}, {TYPED: 0, CURSIVE: 0}
    features = {}
    for n in sorted(by_page):
        got = page_features(by_page[n])
        pages[n] = label_page(by_page[n], cut=cut, min_rows=min_rows)
        features[n] = got
        if pages[n] in weight:
            weight[pages[n]] += got["rows"]

    if not weight[TYPED] and not weight[CURSIVE]:
        document = UNKNOWN
    else:
        document = TYPED if weight[TYPED] > weight[CURSIVE] else CURSIVE
    return {"pages": pages, "features": features, "rows": weight,
            "document": document}


def near_the_cut(median: float | None, margin: float = 0.03,
                 cut: float = CUT) -> bool:
    """Is this page's hand the threshold guessing rather than the gap talking?"""
    return median is not None and abs(median - cut) <= margin
