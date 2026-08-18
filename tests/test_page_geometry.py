"""Tests for deskew + rule detection.

The geometric parts are tested on synthetic pages, where the true angle and
rule positions are known. Real scans are the fixture for the integration check.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from page_geometry import comb_fit, detect_rules, estimate_skew, ink_mask


def synthetic_table(rows=20, pitch=100, angle=0.0, w=1200, h=2400, text=True):
    """White page, black ruled table, a bar of "writing" in each row.

    The written line matters: detection keys on the text, because on real scans
    the rules print faintly and break up while a row of typing does not.
    """
    from PIL import Image, ImageDraw

    im = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(im)
    x0, x1, y0 = 100, w - 100, 200
    for c in (x0, 400, 700, x1):
        d.line([(c, y0), (c, y0 + rows * pitch)], fill=0, width=3)
    for r in range(rows + 1):
        y = y0 + r * pitch
        d.line([(x0, y), (x1, y)], fill=0, width=3)
    if text:
        for r in range(rows):
            cy = y0 + r * pitch + pitch // 2
            d.rectangle([x0 + 30, cy - 12, 380, cy + 12], fill=0)
            d.rectangle([420, cy - 12, 680, cy + 12], fill=0)
    if angle:
        im = im.rotate(-angle, resample=Image.BICUBIC, fillcolor=255)
    return im


def test_estimates_zero_skew_on_a_straight_page():
    assert abs(estimate_skew(ink_mask(synthetic_table()))) < 0.1


@pytest.mark.parametrize("angle", [-0.8, -0.35, 0.35, 0.8])
def test_estimates_known_skew_within_a_tenth_of_a_degree(angle):
    est = estimate_skew(ink_mask(synthetic_table(angle=angle)))
    assert abs(est - angle) < 0.15, f"wanted {angle}, got {est}"


def test_finds_every_row_on_a_straight_synthetic_table():
    mask = ink_mask(synthetic_table(rows=20, pitch=100))
    g = detect_rules(mask)
    assert len(g.rows) == 20
    assert abs(np.median(np.diff(g.row_edges)) - 100) < 2


def test_bands_bracket_the_writing_rather_than_bisecting_it():
    """A band that cuts through its own line of text is useless for cropping."""
    pitch = 100
    g = detect_rules(ink_mask(synthetic_table(rows=20, pitch=pitch)))
    for i, (top, bottom) in enumerate(g.rows[:5]):
        centre_of_text = 200 + i * pitch + pitch / 2
        assert top < centre_of_text < bottom, f"row {i} does not contain its text"


def test_table_extent_is_bounded_by_the_vertical_rules():
    """Without this bound the row comb runs off into the letterhead."""
    g = detect_rules(ink_mask(synthetic_table(rows=20, pitch=100)))
    assert g.table_box is not None
    x0, top, x1, bottom = g.table_box
    assert abs(top - 200) < 12 and abs(bottom - 2200) < 12
    assert all(top - 100 <= e <= bottom + 100 for e in g.row_edges)


def test_ignores_writing_outside_the_table(tmp_path):
    """Letterhead above the table must not extend the row comb."""
    from PIL import ImageDraw
    im = synthetic_table(rows=20, pitch=100)
    d = ImageDraw.Draw(im)
    for k in range(3):                      # "letterhead" lines above the table
        d.rectangle([300, 40 + k * 45, 900, 60 + k * 45], fill=0)
    g = detect_rules(ink_mask(im))
    assert g.table_box[1] > 150
    assert min(g.row_edges) > 120


def test_recovers_rows_after_deskewing_a_rotated_table():
    mask = ink_mask(synthetic_table(rows=20, pitch=100, angle=0.6), deskew=True)
    assert len(detect_rules(mask).rows) >= 18


def test_comb_fit_recovers_rules_dropped_by_faint_ink():
    # a perfect comb with three interior rules missing
    full = [200 + 100 * i for i in range(21)]
    observed = [y for i, y in enumerate(full) if i not in (5, 11, 12)]
    filled = comb_fit(observed)
    assert len(filled) == 21
    assert max(abs(a - b) for a, b in zip(filled, full)) <= 2


def test_comb_fit_leaves_a_clean_sequence_alone():
    full = [100 + 50 * i for i in range(10)]
    assert comb_fit(full) == pytest.approx(full, abs=1)


def test_comb_fit_declines_when_spacing_is_not_periodic():
    assert comb_fit([10, 200, 213, 900, 1500]) is None


def test_bands_are_normalized_and_ordered():
    g = detect_rules(ink_mask(synthetic_table(rows=10, pitch=120)))
    bands = g.normalized_rows()
    assert all(0.0 <= t < b <= 1.0 for t, b in bands)
    assert bands == sorted(bands)
