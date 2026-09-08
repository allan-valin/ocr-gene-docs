"""Taking a reading sheet back in, which is what makes the held-out set exist.

The sheet is one HTML file somebody reads a manifest into on a machine with
none of this installed, and it hands back a JSON array. This is the gate
between that array and `data/truth-heldout`: a page that does not say who read
it, or what hand it is, does not become evidence.
"""
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
script = runpy.run_path(str(ROOT / "scripts" / "import_reading_sheet.py"))
page_name = script["page_name"]
import_sheet = script["import_sheet"]

SHEET = [{
    "pdf": "BR_RJANRIO_BS_0_RPV_ENT_016429_d0001de0001.pdf",
    "page": 2,
    "hand": "cursive",
    "reader": "Allan",
    "read_on": "2026-09-08",
    "complete": True,
    "rows": {"1": "-", "2": "José Fernandes", "3": "", "4": "?Lorenzo ?"},
}]


def sheet_file(tmp_path, payload):
    p = tmp_path / "reading-sheet.json"
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return p


class TestPageName:
    def test_it_names_the_file_the_way_the_truth_set_already_does(self):
        assert page_name("BR_RJANRIO_BS_0_RPV_ENT_016429_d0001de0001.pdf", 2) \
            == "BS_ENT_016429-p2.json"

    def test_a_projeto_notation_names_itself_too(self):
        assert page_name("BR_RJANRIO_OL_0_RPV_PRJ_17318_d0001de0001.pdf", 6) \
            == "OL_PRJ_17318-p6.json"

    def test_a_scan_named_like_nothing_keeps_its_own_stem(self):
        assert page_name("somebodys-scan.pdf", 1) == "somebodys-scan-p1.json"


class TestImport:
    def test_it_writes_one_file_per_page_in_the_truth_format(self, tmp_path):
        out = tmp_path / "truth-heldout"
        written = import_sheet(sheet_file(tmp_path, SHEET), out)
        assert [p.name for p in written] == ["BS_ENT_016429-p2.json"]
        got = json.loads(written[0].read_text(encoding="utf-8"))
        assert got["reader"] == "Allan"
        assert got["rows"]["2"] == "José Fernandes"

    def test_the_written_file_loads_as_a_truth_page(self, tmp_path):
        from desembarque.truthset import load_page
        written = import_sheet(sheet_file(tmp_path, SHEET), tmp_path / "out")
        page = load_page(written[0])
        assert [c.n for c in page.read()] == [2, 4]
        assert [c.n for c in page.unreadable()] == [3]
        assert [c.n for c in page.absent()] == [1]

    def test_a_page_that_does_not_say_who_read_it_is_refused(self, tmp_path):
        bad = [{k: v for k, v in SHEET[0].items() if k != "reader"}]
        with pytest.raises(ValueError, match="reader"):
            import_sheet(sheet_file(tmp_path, bad), tmp_path / "out")

    def test_a_page_that_does_not_say_which_hand_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match="hand"):
            import_sheet(sheet_file(tmp_path, [{**SHEET[0], "hand": None}]),
                         tmp_path / "out")

    def test_a_page_with_nothing_read_on_it_is_refused(self, tmp_path):
        empty = [{**SHEET[0], "rows": {"1": "", "2": "  "}}]
        with pytest.raises(ValueError, match="nothing"):
            import_sheet(sheet_file(tmp_path, empty), tmp_path / "out")

    def test_one_page_wrapped_in_no_array_is_still_a_sheet(self, tmp_path):
        written = import_sheet(sheet_file(tmp_path, SHEET[0]), tmp_path / "out")
        assert len(written) == 1

    def test_it_will_not_overwrite_a_reading_already_on_disk(self, tmp_path):
        out = tmp_path / "out"
        import_sheet(sheet_file(tmp_path, SHEET), out)
        with pytest.raises(FileExistsError):
            import_sheet(sheet_file(tmp_path, SHEET), out)

    def test_unless_it_is_told_to(self, tmp_path):
        out = tmp_path / "out"
        import_sheet(sheet_file(tmp_path, SHEET), out)
        again = import_sheet(sheet_file(tmp_path, SHEET), out, replace=True)
        assert len(again) == 1
