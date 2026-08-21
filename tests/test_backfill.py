"""Putting back the measurement the rows were cut from.

The engine measures a page's grid to cut the rows out of it and returns that
measurement; until today it was dropped on the way to disk, so 658 of the 660
records store no geometry at all and a search hit cannot show where on the scan
its row sits. The repair does not need the engine and does not need the corpus
read again: the geometry is a measurement on the page image, and the extracted
page images are still in the cache. Recomputing one page per dossier is half an
hour against three and a half hours.

What it must not do is attach rows to bands they were not cut from. A band list
that no longer matches the rows on disk is a wrong answer with a picture beside
it, which is worse than no picture.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque.backfill import pages_wanting_geometry, with_geometry

GEO = {"rows": [[0.28, 0.30], [0.30, 0.32], [0.32, 0.34]],
       "columns": [0.07, 0.29, 0.55], "skew": -0.4, "read_from": "mask"}


def record(**over):
    base = {
        "hash": "h", "schema": 14, "engine": "paddle",
        "file": "BR_x_16548_d0001de0001.pdf",
        "pages": [{"n": 1, "kind": "cover"},
                  {"n": 2, "kind": "list", "form": {"text": "x"}}],
        "rows": [{"n": 1, "surname": "A", "page": 2},
                 {"n": 2, "surname": "B", "page": 2},
                 {"n": 3, "surname": "C", "page": 2}],
    }
    base.update(over)
    return base


def test_the_page_the_rows_came_from_is_the_page_to_measure():
    assert pages_wanting_geometry(record()) == [2]


def test_a_page_that_already_has_its_geometry_is_left_alone():
    r = record()
    r["pages"][1]["geometry"] = GEO
    assert pages_wanting_geometry(r) == []


def test_a_page_with_no_rows_is_not_measured():
    """Most of them are the interpreter's PARTE form, which has no grid. There
    is nothing to put a band beside."""
    assert pages_wanting_geometry(record(rows=[])) == []


def test_the_measurement_is_stored_on_the_page_it_was_taken_from():
    out = with_geometry(record(), 2, GEO)
    assert out is not None
    assert out["pages"][1]["geometry"] == GEO
    assert "geometry" not in out["pages"][0]


def test_backfilling_does_not_restamp_the_record():
    """This is a measurement that was taken and dropped, not a fresh reading.
    Moving the schema would mark the record stale and call for hours of work."""
    out = with_geometry(record(), 2, GEO)
    assert out["schema"] == 14


def test_what_a_person_typed_is_untouched():
    r = record()
    r["rows"][0] = {"n": 1, "surname": "GOMES", "page": 2, "by": "person"}
    out = with_geometry(r, 2, GEO)
    assert out["rows"][0]["surname"] == "GOMES"
    assert out["rows"][0]["by"] == "person"


def test_fewer_bands_than_rows_is_refused():
    """Row `n` is its band's index. A shorter band list does not mean a few
    rows lose their band — it means every row after the first difference is
    drawn against somebody else's line."""
    short = {**GEO, "rows": [[0.28, 0.30], [0.30, 0.32]]}
    assert with_geometry(record(), 2, short) is None


def test_more_bands_than_rows_is_kept():
    """A band whose row the recogniser refused — a heading, a tally line — is
    dropped from the rows and stays in the measurement. The indices still line
    up, which is the thing that matters."""
    longer = {**GEO, "rows": GEO["rows"] + [[0.34, 0.36]]}
    assert with_geometry(record(), 2, longer) is not None


def test_a_measurement_that_found_no_grid_is_refused():
    assert with_geometry(record(), 2, None) is None
    assert with_geometry(record(), 2, {"rows": [], "columns": []}) is None
