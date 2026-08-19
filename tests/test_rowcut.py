"""Rows are cut along the paper, not along a ruler.

A manifest hand puts the tail of a `y` through the line below it. Allan's
reading of ITAPEMA 013990: row 1 is "Raymundo Cassandie", and the leg of its
`y` lands inside row 2's "Alfredo J. Tavares", between the `l` and the `f`.

A straight horizontal cut at the band boundary therefore corrupts *both* rows:
the upper one loses its descender, the lower one gains a stroke that is not
part of any of its letters. `refine()` makes it worse rather than better, since
it trims to ink and so expands the crop to swallow whatever intruded.

So the boundary between two rows is found as a path of least ink across the
column, which goes around a descender instead of through it.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque.rowcut import cut_row, seam


def blank(h=60, w=120):
    return np.zeros((h, w), dtype=np.float64)


def test_a_clean_gap_is_cut_straight():
    """With no ink anywhere near the boundary there is nothing to go around."""
    ink = blank()
    ink[5:15, :] = 1.0        # upper row's body
    ink[45:55, :] = 1.0       # lower row's body
    path = seam(ink, 30, margin=12)
    assert path.shape == (120,)
    assert path.min() >= 18 and path.max() <= 42
    assert np.ptp(path) <= 1          # essentially flat


def test_the_seam_goes_below_a_descender_rather_than_through_it():
    """The tail of a `y` from the row above must stay with the row above."""
    ink = blank()
    ink[5:15, :] = 1.0
    ink[15:38, 40:48] = 1.0           # the descender, crossing the boundary
    ink[45:55, :] = 1.0
    path = seam(ink, 30, margin=12)
    assert path[44] > 37, "seam must pass under the descender"
    assert path[10] < 35, "and must not drag the whole boundary down with it"


def test_the_seam_stays_within_its_margin():
    """A runaway seam would start stealing whole letters from a neighbour."""
    ink = blank()
    ink[:, :] = 1.0                   # ink everywhere: no cheap path exists
    path = seam(ink, 30, margin=8)
    assert path.min() >= 22 and path.max() <= 38


def test_a_seam_on_an_empty_strip_is_the_nominal_line():
    path = seam(blank(), 30, margin=10)
    assert np.all(path == 30)


def test_cut_row_keeps_only_what_lies_between_the_two_seams():
    grey = np.full((60, 120), 0, dtype=np.uint8)      # all ink-dark
    upper = np.full(120, 20)
    lower = np.full(120, 40)
    out = cut_row(grey, upper, lower, fill=255)
    assert out.shape == (60, 120)
    assert (out[:20] == 255).all(), "above the upper seam is cleared"
    assert (out[40:] == 255).all(), "below the lower seam is cleared"
    assert (out[20:40] == 0).all(), "the row's own band is untouched"


def test_cut_row_follows_a_curved_seam():
    """The point of the exercise: the cleared region is not a rectangle."""
    grey = np.zeros((60, 120), dtype=np.uint8)
    upper = np.full(120, 20)
    lower = np.full(120, 40)
    lower[60:] = 50                                    # seam dips on the right
    out = cut_row(grey, upper, lower, fill=255)
    assert out[45, 10] == 255, "left half ends at 40"
    assert out[45, 80] == 0, "right half still belongs to this row"


def test_a_descender_is_removed_from_the_row_below():
    """End to end, on the shape Allan described."""
    ink = blank()
    ink[5:15, :] = 1.0
    ink[15:38, 40:48] = 1.0
    ink[45:55, :] = 1.0
    grey = np.where(ink > 0, 0, 255).astype(np.uint8)

    top = seam(ink, 30, margin=12)
    bottom = seam(ink, 60, margin=12)
    lower_row = cut_row(grey, top, bottom, fill=255)

    assert (lower_row[15:38, 40:48] == 255).all(), \
        "the descender belongs to the row above and must not appear here"
    assert (lower_row[45:55, :] == 0).any(), "the row's own writing survives"


# --- the same bleed, sideways ------------------------------------------------
#
# Names run past the column rule too: a long name overflows into Nacionalidade,
# and the neighbouring column's writing reaches back into the name column. It
# is the same problem rotated, so it is the same seam, cut across the other
# axis -- pass the strip transposed and the path is an x per row instead of a
# y per column.

def test_a_vertical_seam_goes_around_an_overflowing_name():
    ink = blank(h=120, w=60)
    ink[:, 5:15] = 1.0                 # this column's writing
    ink[40:48, 15:38] = 1.0            # a name running past the rule
    ink[:, 45:55] = 1.0                # the next column's writing
    path = seam(ink.T, 30, margin=12)  # transposed: one x per row
    assert path.shape == (120,)
    assert path[44] > 37, "the overflowing name stays with its own column"
    assert path[10] < 35, "without dragging the whole rule across"


def test_a_column_is_cut_with_the_transposed_seam():
    grey = np.zeros((120, 60), dtype=np.uint8)
    left = np.full(120, 10)
    right = np.full(120, 30)
    right[60:] = 45
    out = cut_row(grey.T, left, right, fill=255).T
    assert out.shape == (120, 60)
    assert out[10, 35] == 255, "top half of the column ends at 30"
    assert out[80, 35] == 0, "bottom half reaches 45"
    assert (out[:, :10] == 255).all(), "left of the seam is cleared"


# --- what the engine actually asks for ---------------------------------------

def test_carve_returns_one_image_per_band():
    from desembarque.rowcut import carve
    strip = np.full((90, 100), 255, dtype=np.uint8)
    strip[10:20, :] = 0
    strip[40:50, :] = 0
    strip[70:80, :] = 0
    out = carve(strip, [(5, 30), (35, 60), (65, 90)])
    assert len(out) == 3
    assert all(a.ndim == 2 for a in out)


def test_carve_strips_the_neighbours_descender():
    """The whole point: row 2's crop must not contain row 1's `y` tail."""
    from desembarque.rowcut import carve
    strip = np.full((90, 100), 255, dtype=np.uint8)
    strip[10:20, :] = 0            # row 1 body
    strip[20:38, 40:48] = 0        # row 1 descender, crossing into row 2
    strip[45:55, :] = 0            # row 2 body
    rows = carve(strip, [(5, 32), (33, 60)])
    mid = rows[1]
    assert (mid == 0).any(), "row 2 keeps its own writing"
    # nothing of the descender survives in row 2: its columns are blank above
    # the row's own writing, which starts well below where the tail ended
    assert (mid[:6, 40:48] == 255).all()


def test_a_descender_longer_than_the_margin_is_not_fully_removed():
    """The honest limit. The seam may only wander `margin` from the rule it
    replaces, because a boundary free to go anywhere would start claiming a
    neighbour's letters. A tail reaching further than that into the next row
    is beyond what cutting can fix -- it needs the stroke to be traced, not a
    path to be found."""
    from desembarque.rowcut import carve
    strip = np.full((90, 100), 255, dtype=np.uint8)
    strip[10:20, :] = 0
    strip[20:44, 40:48] = 0        # a tail crossing far past any sane margin
    strip[45:55, :] = 0
    mid = carve(strip, [(5, 32), (33, 60)], margin=4)[1]
    assert (mid[:, 40:48] == 0).any(), "documented shortfall, not a silent one"


def test_carve_survives_a_band_with_no_ink():
    from desembarque.rowcut import carve
    strip = np.full((60, 40), 255, dtype=np.uint8)
    out = carve(strip, [(0, 30), (30, 60)])
    assert len(out) == 2
    assert all((a == 255).all() for a in out)


def test_carve_with_no_bands_is_empty():
    from desembarque.rowcut import carve
    assert carve(np.full((10, 10), 255, dtype=np.uint8), []) == []
