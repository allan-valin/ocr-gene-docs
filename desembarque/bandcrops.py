"""Cut a row's ink again, from the geometry the record already carries.

The one lever left on this archive's handwriting is a recogniser trained on
it (see `docs/TASKS-reading-quality.md`), and that wants labelled crops. Every
row somebody retypes on the review screen is one: the image the engine read,
and the name a person says it is. The image is not kept — a corpus pass would
be storing a hundred thousand of them — but since T4 every page stores the
geometry its rows were cut from, and a crop is a pure function of that
geometry and the page image. So the label costs nothing at the time and the
picture is cut when somebody asks for it, for corrections made months ago as
readily as for today's.

It has to be *the same* crop the engine read, or a pair is a name against a
neighbour's handwriting. That is why the cutting is the engine's own
`carved_crops` and `band_boxes` rather than a second implementation of them.
"""
from __future__ import annotations

from pathlib import Path

from .engine_paddle import INK_MARGIN, band_boxes, carved_crops


class StoredGeometry:
    """What a stored page geometry can answer, in the shape the engine asks.

    `columns` has meant the name column since the first record on disk, and a
    geometry measured off the rules stores only that; `all_columns` is the rest
    where a page printed its headings. The engine only needs the name column
    here, because a name is what anybody has retyped.
    """

    def __init__(self, stored: dict | None) -> None:
        stored = stored or {}
        self._rows = [tuple(b) for b in (stored.get("rows") or [])
                      if b and len(b) == 2]
        self._name = tuple(stored.get("columns") or ())
        self.skew = float(stored.get("skew") or 0.0)
        self.measured_by = stored.get("measured_by")
        self.read_from = stored.get("read_from")

    def usable(self) -> bool:
        """A page with no bands or no name column was never measured."""
        return bool(self._rows) and len(self._name) == 2

    def normalized_rows(self) -> list[tuple[float, float]]:
        return list(self._rows)

    def name_column(self, index: int = 0) -> tuple[float, float] | None:
        return self._name if len(self._name) == 2 else None


def crops_for(image: Path, stored: dict | None, rows=None,
              margin: int = INK_MARGIN) -> dict[int, dict]:
    """Both pictures of the named rows of a page, keyed by row number.

    `rows` are row numbers as the record numbers them — the band's index plus
    one — and all of them when it is None. Each entry holds the `carved` crop
    the engine's recogniser was handed and the plain `strip` rectangle of the
    band, which a second recogniser reads very differently.
    """
    from PIL import Image

    geo = StoredGeometry(stored)
    if not geo.usable():
        return {}
    want = None if rows is None else {int(n) for n in rows}

    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(image).convert("L")
    if geo.skew:
        im = im.rotate(geo.skew, resample=Image.BICUBIC, fillcolor=255)

    sink: dict[int, dict] = {}
    crop = carved_crops(im, geo, margin, sink=sink)
    for i, box in band_boxes(geo, im.size):
        if want is not None and i + 1 not in want:
            continue
        crop(i, box)
    return {i + 1: band for i, band in sink.items()}
