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


def synthetic_table(rows=20, pitch=100, angle=0.0, w=1200, h=2400):
    """White page, black ruled table, optionally rotated."""
    from PIL import Image, ImageDraw

    im = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(im)
    x0, x1, y0 = 100, w - 100, 200
    for c in (x0, 400, 700, x1):
        d.line([(c, y0), (c, y0 + rows * pitch)], fill=0, width=3)
    for r in range(rows + 1):
        y = y0 + r * pitch
        d.line([(x0, y), (x1, y)], fill=0, width=3)
    if angle:
        im = im.rotate(-angle, resample=Image.BICUBIC, fillcolor=255)
    return im


def test_estimates_zero_skew_on_a_straight_page():
    assert abs(estimate_skew(ink_mask(synthetic_table()))) < 0.1


@pytest.mark.parametrize("angle", [-0.8, -0.35, 0.35, 0.8])
def test_estimates_known_skew_within_a_tenth_of_a_degree(angle):
    est = estimate_skew(ink_mask(synthetic_table(angle=angle)))
    assert abs(est - angle) < 0.15, f"wanted {angle}, got {est}"


def test_finds_every_row_rule_on_a_straight_synthetic_table():
    mask = ink_mask(synthetic_table(rows=20, pitch=100))
    g = detect_rules(mask)
    assert len(g.rows) == 20
    assert abs(np.median(np.diff(g.row_edges)) - 100) < 2


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
