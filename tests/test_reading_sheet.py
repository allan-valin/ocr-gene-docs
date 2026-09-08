"""The sheet has to record who read it, and it cannot assume.

Five of the six files in the old truth set were the assistant's reading in
wording that implied a person, and that is the whole reason this sheet exists.
A sheet that fills the reader's name in for them repeats the mistake in one
more place.
"""
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sheet = runpy.run_path(str(ROOT / "scripts" / "make_reading_sheet.py"))
render = sheet["render"]

PAGE = [{"pdf": "BR_RJANRIO_BS_0_RPV_ENT_016429_d0001de0001.pdf", "page": 2,
         "rows": [1, 2, 3], "jpg": ""}]


def test_it_asks_who_is_reading():
    assert 'id=reader' in render(PAGE)


def test_it_puts_nobody_in_that_field_for_them():
    html = render(PAGE)
    assert "reader:'Allan'" not in html
    assert "reader:document.getElementById('reader').value.trim()" in html


def test_an_unnamed_sheet_cannot_be_handed_back():
    html = render(PAGE)
    assert "function save(){if(!named())return;" in html
    assert "function copy(){if(!named())return;" in html


def test_every_row_the_engine_cut_gets_a_box():
    html = render(PAGE)
    assert html.count('data-n="') == 3


def test_the_page_says_which_scan_and_page_it_is():
    html = render(PAGE)
    assert 'data-pdf="BR_RJANRIO_BS_0_RPV_ENT_016429_d0001de0001.pdf"' in html
    assert 'data-page="2"' in html
