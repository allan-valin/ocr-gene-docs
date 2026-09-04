"""Cutting a row's ink again, from what the record already says.

A recogniser trained on this archive's own hands needs labelled crops, and
every row somebody has retyped on the review screen is one — the image the
engine read and the name a person says it is. The image was thrown away, but
the record keeps the geometry the rows were cut from (per page, since T4), so
the same crop can be cut again from the same page image without a recogniser
and without guessing. It has to be *the same* crop: a training pair whose
picture is a neighbouring row is a mislabelled one.
"""
from PIL import Image, ImageDraw

from desembarque import bandcrops
from desembarque.engine_paddle import carved_crops, rows_from_bands

STORED = {"rows": [[0.0, 0.33], [0.34, 0.66], [0.67, 1.0]],
          "columns": [0.0, 1.0], "skew": 0.0, "measured_by": "printing",
          "read_from": "mask"}


def a_page(path):
    im = Image.new("L", (400, 300), 255)
    d = ImageDraw.Draw(im)
    d.text((20, 40), "MARTINEZ FRANCISCO", fill=0)
    d.text((20, 140), "ROCA REBULLIDA", fill=0)
    d.text((20, 240), "PONTICELLI GIUSEPPE", fill=0)
    im.save(path)
    return im


def test_the_stored_geometry_answers_what_the_engine_asks_of_a_page():
    geo = bandcrops.StoredGeometry(STORED)
    assert geo.normalized_rows() == [(0.0, 0.33), (0.34, 0.66), (0.67, 1.0)]
    assert geo.name_column(0) == (0.0, 1.0)
    assert geo.skew == 0.0


def test_a_geometry_with_no_rows_or_no_name_column_is_refused():
    assert bandcrops.StoredGeometry({"rows": [], "columns": [0.0, 1.0]}).usable() is False
    assert bandcrops.StoredGeometry({"rows": [[0, 1]], "columns": []}).usable() is False
    assert bandcrops.StoredGeometry(STORED).usable() is True


def test_the_crop_is_the_same_ink_the_engine_read(tmp_path):
    """Cut again from the record, it is byte-for-byte the engine's own crop."""
    page = tmp_path / "p.png"
    im = a_page(page)

    sink = {}
    rows_from_bands(bandcrops.StoredGeometry(STORED), im.size,
                    lambda crops: [("x", 0.9)] * len(crops),
                    carved_crops(im, bandcrops.StoredGeometry(STORED), sink=sink))

    again = bandcrops.crops_for(page, STORED)
    assert sorted(again) == [1, 2, 3], "keyed by row number, as the record is"
    for n in (1, 2, 3):
        assert again[n]["carved"].tobytes() == sink[n - 1]["carved"].tobytes()
        assert again[n]["strip"].tobytes() == sink[n - 1]["strip"].tobytes()


def test_only_the_rows_asked_for_are_cut(tmp_path):
    page = tmp_path / "p.png"
    a_page(page)
    got = bandcrops.crops_for(page, STORED, rows=[2])
    assert sorted(got) == [2]


def test_a_page_whose_geometry_says_nothing_yields_nothing(tmp_path):
    page = tmp_path / "p.png"
    a_page(page)
    assert bandcrops.crops_for(page, {"rows": [], "columns": []}) == {}
