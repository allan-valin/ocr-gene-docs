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


# --- the second sheet, after Allan read the first (2026-10-07) ---------------
#
# Five of the ten pages showed the ordinal strip or a cover note, because the
# sheet was cut from geometry the corpus re-read had since corrected, and the
# boxes were numbered by bands a reader could not tell apart from the page.

import random

draw = sheet["draw"]
pick_page = sheet["pick_page"]
SEED = sheet["SEED"]


def test_the_draw_is_the_recorded_one_and_a_prefix_of_a_longer_draw():
    pool = [f"doc{i:03d}.pdf" for i in range(100)]
    assert draw(pool, 10) == random.Random(SEED).sample(sorted(pool), 10)
    assert draw(pool, 25)[:10] == draw(pool, 10)


def geo(cols, n=8, first=0.1):
    return {"columns": cols,
            "rows": [[first + i * 0.02, first + i * 0.02 + 0.03] for i in range(n)]}


def record(pages, rows):
    return {"pages": [{"n": n, "geometry": g} for n, g in pages.items()],
            "rows": [{"page": p, "n": i + 1, "name_raw": t}
                     for p, texts in rows.items() for i, t in enumerate(texts)]}


class TestPickPage:
    def test_the_page_with_the_most_names_read_wins(self):
        rec = record({2: geo([0.08, 0.30]), 3: geo([0.08, 0.30])},
                     {2: ["Nome", "", "Ana Silva", "Jose Costa", "", "Rui Pires",
                          "Eva Luz", "Tim Ras"],
                      3: ["Nome", "", "Ana Silva", "", "", "", "", ""]})
        page, g, reads = pick_page(rec)
        assert page == 2
        assert reads[3] == "Ana Silva"

    def test_a_page_whose_column_is_the_ordinal_strip_is_not_offered(self):
        rec = record({2: geo([0.015, 0.038])},
                     {2: ["1", "2", "3", "4", "5", "6", "7", "8"]})
        assert pick_page(rec) is None

    def test_a_page_whose_column_is_the_whole_sheet_is_not_offered(self):
        rec = record({5: geo([0.009, 0.987], n=48)},
                     {5: ["MANNNOOION"] + [""] * 47})
        assert pick_page(rec) is None

    def test_a_page_with_under_five_names_is_not_worth_a_reader(self):
        rec = record({2: geo([0.08, 0.30])},
                     {2: ["Nome", "", "Ana Silva", "Jose Costa", "", "", "", ""]})
        assert pick_page(rec) is None


def test_each_box_shows_the_engines_own_reading_of_its_band():
    page = [{**PAGE[0], "reads": {1: "Nome <e> Cognomes", 2: "", 3: "Ana & Rui"}}]
    html = render(page)
    assert 'placeholder="Nome &lt;e&gt; Cognomes"' in html
    assert 'placeholder="Ana &amp; Rui"' in html


def test_the_sheet_says_which_reading_its_bands_came_from():
    html = render([{**PAGE[0], "cut_from": "reread"}])
    assert 'data-cut="reread"' in html
    assert "cut_from:s.dataset.cut" in html
