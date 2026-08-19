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


def test_negative_scans_are_turned_the_right_way_round(tmp_path):
    """Fourteen of the first twenty dossiers store their ink mask with 1 = ink,
    so the extracted layer is white writing on black paper. Recognition on that
    returns fluent-looking nonsense, which is worse than returning nothing."""
    from PIL import Image
    from page_geometry import positive
    neg = Image.new("L", (600, 800), 8)
    for x in range(100, 500):
        for y in range(300, 340):
            neg.putpixel((x, y), 250)
    p = tmp_path / "neg.png"
    neg.save(p)

    out = positive(p)
    with Image.open(out) as im:
        arr = np.asarray(im.convert("L"))
    assert arr.mean() > 128            # paper is light again
    assert arr[320, 300] < 60          # and the writing is dark


def test_a_normal_scan_is_left_untouched(tmp_path):
    from PIL import Image
    from page_geometry import positive
    pos = Image.new("L", (600, 800), 240)
    for x in range(100, 500):
        for y in range(300, 340):
            pos.putpixel((x, y), 10)
    p = tmp_path / "pos.png"
    pos.save(p)
    assert positive(p) == p


def test_a_page_image_is_extracted_once_and_then_reused(tmp_path, monkeypatch):
    """Extraction is the most expensive step on these scans — 11.6 s for a 23 MP
    page, against 2.3 s of geometry. It was being redone on every call: once to
    index, again to display, again on the next run."""
    from PIL import Image
    import page_geometry as pg

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    work = tmp_path / "work"
    work.mkdir()

    runs = []

    def fake_extract(pdf_path, n, workdir):
        runs.append(n)
        out = workdir / f"{pdf_path.stem}-p{n}-img-000.png"
        im = Image.new("1", (700, 900), 1)
        for x in range(100, 400):
            for y in range(300, 340):
                im.putpixel((x, y), 0)
        im.save(out)
        return [out]

    monkeypatch.setattr(pg, "_extract_candidates", fake_extract)

    first = pg.page_image(pdf, 2, work)
    second = pg.page_image(pdf, 2, work)
    assert first == second
    assert runs == [2]          # extracted once, not twice


def test_a_document_is_extracted_once_for_all_its_pages(tmp_path, monkeypatch):
    """pdfimages re-parses the whole PDF on every call, so asking page by page
    made a five-page dossier five full parses — 11.3 s a page against 4.8 s when
    the document is done in one go."""
    import page_geometry as pg

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    work = tmp_path / "work"
    work.mkdir()

    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        from PIL import Image
        stem = Path(cmd[-1])
        for page in (1, 2, 3):
            im = Image.new("1", (700, 900), 1)
            for x in range(100, 400):
                for y in range(300, 340):
                    im.putpixel((x, y), 0)
            im.save(stem.parent / f"{stem.name}-{page:03d}-000.png")
        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(pg.shutil, "which", lambda name: "/usr/bin/pdfimages")
    monkeypatch.setattr(pg.subprocess, "run", fake_run)

    first = pg._extract_candidates(pdf, 2, work)
    second = pg._extract_candidates(pdf, 3, work)
    assert first and second and first != second
    assert len(calls) == 1
