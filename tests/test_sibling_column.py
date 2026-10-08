"""A page whose name column is unlike its dossier borrows the siblings' column."""
import runpy

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
script = runpy.run_path(str(ROOT / "scripts" / "sibling_column_reread.py"))
sibling_column = script["sibling_column"]
suspect_pages = script["suspect_pages"]


def page(n, cols, rows=5):
    return {"n": n, "geometry": {"columns": cols,
                                 "rows": [[0.1 + i * 0.02, 0.12 + i * 0.02] for i in range(rows)]}}


RECORD = {"pages": [page(2, [0.08, 0.30]), page(3, [0.09, 0.32]),
                    page(4, [0.015, 0.038]), page(5, [0.009, 0.987])]}


def test_the_siblings_column_is_the_median_of_the_plausible_pages():
    got = sibling_column(RECORD)
    assert got == pytest.approx((0.085, 0.31))


def test_the_ordinal_strip_and_the_whole_sheet_are_the_suspects():
    assert [n for n, _ in suspect_pages(RECORD)] == [4, 5]


def test_a_dossier_with_no_plausible_page_lends_nothing():
    assert sibling_column({"pages": [page(2, [0.01, 0.03])]}) is None


def test_a_page_with_no_rows_is_not_read_again():
    rec = {"pages": [page(2, [0.08, 0.30]), {"n": 3, "geometry": {"columns": [0.01, 0.03], "rows": []}}]}
    assert suspect_pages(rec) == []
