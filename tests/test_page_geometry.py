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


# --- the comb must sit on the writing, not on the blank ruled paper ----------
#
# BS_ENT_013990 p2 lists eighteen passengers; the engine read three. The table's
# top came from `rule_extent`, the longest *unbroken* vertical run of ink at
# each column rule — and handwriting shatters those rules precisely where people
# are listed, into 17-21 short runs, none longer than 5% of the page. Where the
# table is empty the rules print cleanly, so the longest run is always the blank
# region: the top came out at 0.559 of the page and the comb fitted the ruled
# emptiness below the list.
#
# Raising the gap tolerance is not the fix; measured over three pages, the value
# that recovers 013990 (250 px) drags the two working pages up into their
# letterheads. The extent has to come from where the writing actually is.

def half_written_table(rows=18, pitch=100, w=1200, h=3000, blanks=14):
    """A table written in its top half and ruled-but-empty in its bottom half,
    with the column rules broken wherever writing crosses them — the shape that
    defeats a longest-unbroken-run bound."""
    from PIL import Image, ImageDraw
    im = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(im)
    x0, x1, y0 = 100, w - 100, 300
    total = rows + blanks
    for c in (x0, 400, 700, x1):
        for r in range(total):
            top = y0 + r * pitch
            # written rows break the rule; empty ones print it whole
            if r < rows:
                # a break wider than the detector's gap tolerance, which is what
                # real handwriting does: 17-21 runs per rule, none of them long
                d.line([(c, top + 46), (c, top + pitch - 46)], fill=0, width=3)
            else:
                d.line([(c, top), (c, top + pitch)], fill=0, width=3)
    for r in range(total + 1):
        y = y0 + r * pitch
        d.line([(x0, y), (x1, y)], fill=0, width=2)
    for r in range(rows):
        cy = y0 + r * pitch + pitch // 2
        d.rectangle([x0 + 30, cy - 12, 380, cy + 12], fill=0)
        d.rectangle([420, cy - 12, 680, cy + 12], fill=0)
    return im


def written_span(geo, h, rows=18, pitch=100, y0=300):
    """How much of the written area the comb covers, 0..1."""
    if not geo.rows:
        return 0.0
    bands = geo.normalized_rows()
    top, bottom = bands[0][0] * h, bands[-1][1] * h
    lo, hi = y0, y0 + rows * pitch
    overlap = max(0.0, min(bottom, hi) - max(top, lo))
    return overlap / (hi - lo)


def test_the_comb_covers_rows_whose_rules_are_broken_by_writing():
    im = half_written_table()
    geo = detect_rules(ink_mask(im))
    assert written_span(geo, im.height) > 0.8, (
        "the comb sat on the blank ruled half instead of the written rows")


def test_a_fully_written_table_is_unchanged():
    """The straightforward case must not be disturbed by fixing the hard one."""
    im = synthetic_table(rows=20, pitch=100)
    geo = detect_rules(ink_mask(im))
    assert 18 <= len(geo.normalized_rows()) <= 23


def test_writing_above_the_table_does_not_drag_the_comb_into_it():
    """A letterhead sits on unruled paper above the table, separated from it by
    a clear strip — the shape every real form in this corpus has, and the
    failure the original rule bound existed to stop.

    The limit is that separation. A banner butted directly against the first
    row, with no blank paper between, is not distinguishable from a row by
    anything measured here: on BS_ENT_013990 the vertical rules score 0.00 to
    0.09 through the entire passenger block, so "is this inside the table?"
    cannot be answered from the rules either. What saves the real pages is that
    the gap exists — 013990's comb starts at 0.28, below its header block.
    """
    from PIL import ImageDraw
    im = half_written_table()
    d = ImageDraw.Draw(im)
    # off the table's pitch as well as clear of it: a printed letterhead has no
    # reason to share the ruling's spacing, and 013990's does not
    d.rectangle([150, 75, 900, 115], fill=0)      # a title
    d.rectangle([150, 170, 700, 205], fill=0)     # a subtitle
    geo = detect_rules(ink_mask(im))
    bands = geo.normalized_rows()
    assert bands, "still detects the table"
    assert bands[0][0] * im.height > 200, "comb reached up into the letterhead"


def test_blank_rows_inside_the_table_do_not_cut_the_comb_short():
    """Clerks leave a line unwritten; that is a row with nothing in it, not the
    end of the table."""
    from PIL import Image, ImageDraw
    im = half_written_table(rows=18, blanks=6)
    d = ImageDraw.Draw(im)
    for r in (5, 6, 11):                           # erase three written rows
        cy = 300 + r * 100 + 50
        d.rectangle([120, cy - 20, 900, cy + 20], fill=255)
    geo = detect_rules(ink_mask(im))
    assert written_span(geo, im.height) > 0.7


def broken_rules_table(rows=20, pitch=100, w=1200, h=2600):
    """A ruled table whose vertical rules are interrupted by the writing.

    This is the real corpus's most damaging layout. Ink crossing a rule breaks
    it, so the longest *unbroken* run of a rule is the empty stretch below the
    last passenger — and an extent taken from those runs puts the table in the
    blank paper under the list. Each rule is cut in a different place here, the
    way handwriting cuts them, so no single line of the page breaks all of them.
    """
    from PIL import Image, ImageDraw

    im = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(im)
    x0, x1, y0 = 100, w - 100, 400
    cols = [x0, 400, 700, x1]
    written = 14                      # the rest of the form is blank ruled paper
    d.text((120, 150), "MINISTERIO DA FAZENDA", fill=0)
    for i, c in enumerate(cols):
        d.line([(c, y0), (c, y0 + rows * pitch)], fill=0, width=3)
    for r in range(rows + 1):
        d.line([(x0, y0 + r * pitch), (x1, y0 + r * pitch)], fill=0, width=3)
    for r in range(written):
        cy = y0 + r * pitch + pitch // 2
        d.rectangle([x0 + 30, cy - 14, 380, cy + 14], fill=0)
        d.rectangle([420, cy - 14, 680, cy + 14], fill=0)
        # the writing overruns its cell and wipes out one rule on this row
        c = cols[1 + (r % 3)]
        d.rectangle([c - 6, cy - 40, c + 6, cy + 40], fill=255)
    return im


def test_a_table_whose_rules_the_writing_broke_is_still_found():
    """Fourteen written rows above blank ruled paper. The bands have to sit on
    the writing; landing on the empty half is the failure this pins."""
    g = detect_rules(ink_mask(broken_rules_table()))
    assert g.rows, "no rows at all — the page came back blank"
    top = g.rows[0][0]
    assert top < 600, f"the comb starts at {top}, below the first written row"
    assert len(g.rows) >= 14, f"only {len(g.rows)} rows for fourteen written ones"


def test_the_letterhead_is_still_left_out():
    """Reaching further up must not mean reaching all the way up."""
    g = detect_rules(ink_mask(broken_rules_table()))
    assert g.rows[0][0] > 200, "the comb climbed into the letterhead"


# ---- which of the two row combs to keep -------------------------------------
#
# The numbers in these cases are measured, not invented: they come from running
# the two candidate fits over the eighty-nine-page geometry bench and recording
# what each page offered. A comb is (edges, pitch).

def comb_of(first, count, pitch=94.0):
    return ([float(first + i * pitch) for i in range(count + 1)], pitch)


def test_a_working_narrow_comb_is_not_displaced_by_a_hair():
    """The narrow fit is the better-tested path. Without a margin the two traded
    places on pages where neither was clearly right, and fifteen of eighty-nine
    got worse."""
    from page_geometry import choose_comb
    narrow = comb_of(400, 20)
    wider = comb_of(300, 22)
    lines = [410 + i * 94 for i in range(20)]
    assert choose_comb(narrow, wider, lines, reaches=True) is narrow


def test_the_wider_comb_wins_when_it_explains_much_more_writing():
    from page_geometry import choose_comb
    narrow = comb_of(4000, 3)
    wider = comb_of(400, 30)
    lines = [410 + i * 94 for i in range(30)]
    assert choose_comb(narrow, wider, lines, reaches=True) is wider


def test_a_page_with_no_narrow_fit_at_all_takes_the_wider_comb():
    """BR_..._16456 page 2: thirty-seven passengers, and the table's rules are
    printed so faintly that the extent taken from them lands in the blank paper
    below the list. No narrow comb exists, the wider one sits on 37 of the 48
    detected lines, and the page came back completely empty."""
    from page_geometry import choose_comb
    wider = comb_of(830, 37)
    lines = [840 + i * 94 for i in range(37)] + [200, 300, 4800, 4900]
    assert choose_comb(None, wider, lines, reaches=False) is wider


def test_a_wider_comb_that_explains_little_is_still_refused():
    """BR_..._013991 page 2: eleven bands against thirty detected lines. A comb
    that accounts for a third of the writing is not evidence of a table, and a
    document with invented rows is worse than one with none."""
    from page_geometry import choose_comb
    wider = comb_of(1300, 11)
    lines = [1310 + i * 94 for i in range(11)] + [100 + i * 60 for i in range(19)]
    assert choose_comb(None, wider, lines, reaches=False) is None


def test_a_handful_of_bands_is_not_a_table():
    """BR_..._18763 page 2: six bands. Six lines that happen to be evenly spaced
    are a letterhead as often as they are a list."""
    from page_geometry import choose_comb
    wider = comb_of(100, 6)
    lines = [110 + i * 94 for i in range(6)]
    assert choose_comb(None, wider, lines, reaches=False) is None


def test_a_comb_that_starts_off_the_top_of_the_page_is_refused():
    from page_geometry import choose_comb
    wider = comb_of(-120, 20)
    lines = [-110 + i * 94 for i in range(20)]
    assert choose_comb(None, wider, lines, reaches=False) is None


def test_a_small_comb_the_rules_agree_with_is_kept():
    """No narrow fit, but the challenger sits inside the extent the vertical
    rules reported. Nothing is being displaced and the page's own rules
    corroborate it, so the size gate that guards an unvouched-for comb does not
    apply. BR_..._17347 lost its ten bands to that gate."""
    from page_geometry import choose_comb
    wider = comb_of(1000, 4)
    lines = [1010 + i * 94 for i in range(4)]
    assert choose_comb(None, wider, lines, reaches=True) is wider
