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


# --- taking the first sheet back in, the way Allan actually typed it ----------
#
# The boxes were numbered by the engine's bands and the reader counted the rows
# he could see: box 1 was the first name, not the heading, and a sliver band
# under its neighbour was not a row. `--positional` maps that back.

RECORD = {
    "hash": "abc", "file": SHEET[0]["pdf"],
    "pages": [{"n": 2, "geometry": {
        "columns": [0.08, 0.30],
        # bands 3 and 4 are the same ink, 3 a sliver under 4
        "rows": [[0.100, 0.130], [0.120, 0.150], [0.140, 0.170],
                 [0.146, 0.176], [0.164, 0.194], [0.184, 0.214]]}}],
    "rows": [{"page": 2, "n": 1, "name_raw": "Nome e Cognomes"},
             {"page": 2, "n": 2, "name_raw": ""},
             {"page": 2, "n": 3, "name_raw": "Ana Silva"},
             {"page": 2, "n": 4, "name_raw": ""},
             {"page": 2, "n": 5, "name_raw": "Jose Costa"},
             {"page": 2, "n": 6, "name_raw": "Rui Pires"}],
}


def records_dir(tmp_path):
    d = tmp_path / "records"
    d.mkdir()
    (d / "abc.json").write_text(json.dumps(RECORD), encoding="utf-8")
    return d


class TestPositional:
    def test_boxes_counted_down_the_page_land_on_the_bands_they_meant(self, tmp_path):
        typed = [{**SHEET[0], "rows": {"1": "Ana Silva", "2": "Jose Costa",
                                       "3": "Rui Pires", "4": "Zé Extra"}}]
        written = import_sheet(sheet_file(tmp_path, typed), tmp_path / "out",
                               records=records_dir(tmp_path), positional=True)
        got = json.loads(written[0].read_text(encoding="utf-8"))
        assert got["rows"] == {"3": "Ana Silva", "5": "Jose Costa", "6": "Rui Pires"}
        assert got["lost"] == ["Zé Extra"]
        assert got["mapping"] == "positional"

    def test_a_sheet_typed_against_the_numbers_is_taken_as_it_stands(self, tmp_path):
        written = import_sheet(sheet_file(tmp_path, SHEET), tmp_path / "out",
                               records=records_dir(tmp_path))
        got = json.loads(written[0].read_text(encoding="utf-8"))
        assert got["rows"]["2"] == "José Fernandes"
        assert got["mapping"] == "by band number"


class TestUnusablePages:
    def test_a_page_read_as_the_ordinal_column_is_set_aside_not_imported(self, tmp_path):
        ordinal = {**SHEET[0], "page": 3,
                   "rows": {str(i): str(i) for i in range(1, 12)}}
        written = import_sheet(sheet_file(tmp_path, [ordinal, SHEET[0]]),
                               tmp_path / "out")
        assert [p.name for p in written] == ["BS_ENT_016429-p2.json"]

    def test_a_page_with_one_word_on_it_is_set_aside_too(self, tmp_path):
        cover = {**SHEET[0], "page": 5,
                 "rows": {str(i): ("immigration" if i == 5 else "")
                          for i in range(1, 49)}}
        assert import_sheet(sheet_file(tmp_path, [cover]), tmp_path / "out") == []


class TestTypedPagesAlignByText:
    def test_a_typed_row_the_engine_never_cut_is_lost_and_the_rest_stay_put(self, tmp_path):
        # the reader typed an extra row between Ana and Jose that no band holds
        typed = [{**SHEET[0], "hand": "typed",
                  "rows": {"1": "Ana Silva", "2": "Rita Mota", "3": "Jose Costa",
                           "4": "Rui Pires"}}]
        written = import_sheet(sheet_file(tmp_path, typed), tmp_path / "out",
                               records=records_dir(tmp_path), positional=True)
        got = json.loads(written[0].read_text(encoding="utf-8"))
        assert got["rows"] == {"3": "Ana Silva", "5": "Jose Costa", "6": "Rui Pires"}
        assert got["lost"] == ["Rita Mota"]
