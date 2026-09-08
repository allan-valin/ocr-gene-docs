"""The truth-file format of docs/TASKS-honest-measurement.md, T1.

A page somebody read by hand records every band on it, and keeps three
answers apart: a name they read, a row they could not read, and a band that
is not a row at all. The middle class is the point of the format — a row
nobody can read is data, because a recogniser that produces confident text
there is either better than a person or inventing.
"""
from __future__ import annotations

import json

import pytest

from desembarque.truthset import (
    ABSENT, READ, UNREADABLE, TruthPage, load_page, load_pages, parse_cell,
)


class TestParseCell:
    def test_a_plain_name_is_read_and_certain(self):
        cell = parse_cell("José Fernandes")
        assert (cell.kind, cell.text, cell.certain) == (READ, "José Fernandes", True)

    def test_a_leading_question_mark_marks_the_row_uncertain(self):
        cell = parse_cell("?José Guberti")
        assert (cell.kind, cell.text, cell.certain) == (READ, "José Guberti", False)

    def test_a_word_nobody_could_read_stays_in_the_text(self):
        cell = parse_cell("?Lorenzo ?")
        assert cell.kind == READ
        assert cell.certain is False
        assert cell.text == "Lorenzo ?"

    def test_empty_is_a_row_nobody_can_read_and_that_is_the_answer(self):
        for empty in ("", "   "):
            cell = parse_cell(empty)
            assert cell.kind == UNREADABLE
            assert cell.text == ""
            assert cell.certain is False

    def test_a_dash_is_no_row_there(self):
        cell = parse_cell("-")
        assert (cell.kind, cell.text) == (ABSENT, "")


def write(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


NEW = {
    "pdf": "BR_RJANRIO_BS_0_RPV_ENT_016429_d0001de0001.pdf",
    "page": 2,
    "hand": "cursive",
    "reader": "Allan",
    "read_on": "2026-09-08",
    "complete": True,
    "rows": {"1": "José Fernandes", "2": "?José Guberti", "3": "", "4": "?Lorenzo ?", "5": "-"},
}


class TestLoadPage:
    def test_it_reads_the_shape_the_task_specifies(self, tmp_path):
        page = load_page(write(tmp_path, "new.json", NEW))
        assert isinstance(page, TruthPage)
        assert page.pdf == NEW["pdf"]
        assert page.page == 2
        assert page.hand == "cursive"
        assert page.reader == "Allan"
        assert page.read_on == "2026-09-08"
        assert page.complete is True

    def test_the_three_classes_are_kept_apart(self, tmp_path):
        page = load_page(write(tmp_path, "new.json", NEW))
        assert [c.n for c in page.read()] == [1, 2, 4]
        assert [c.n for c in page.unreadable()] == [3]
        assert [c.n for c in page.absent()] == [5]

    def test_uncertain_rows_are_countable_on_their_own(self, tmp_path):
        page = load_page(write(tmp_path, "new.json", NEW))
        assert [c.n for c in page.read() if not c.certain] == [2, 4]

    def test_a_file_with_no_reader_is_not_evidence(self, tmp_path):
        bad = {k: v for k, v in NEW.items() if k != "reader"}
        with pytest.raises(ValueError, match="reader"):
            load_page(write(tmp_path, "bad.json", bad))

    def test_a_blank_reader_is_no_reader(self, tmp_path):
        with pytest.raises(ValueError, match="reader"):
            load_page(write(tmp_path, "bad.json", {**NEW, "reader": "  "}))

    def test_complete_is_false_unless_it_is_asserted(self, tmp_path):
        page = load_page(write(tmp_path, "p.json", {k: v for k, v in NEW.items()
                                                   if k != "complete"}))
        assert page.complete is False

    def test_hand_is_unknown_unless_the_file_says(self, tmp_path):
        page = load_page(write(tmp_path, "p.json", {k: v for k, v in NEW.items()
                                                   if k != "hand"}))
        assert page.hand == "unknown"


LEGACY_RUN = {
    "source": "read from the scan by eye at 150 dpi, page 2 name column",
    "reader": "assistant",
    "hand": "typed",
    "pdf": "BR_RJANRIO_BS_0_RPV_ENT_013981_d0001de0001.pdf",
    "page": 2,
    "first_row": 1,
    "names": ["Eliza da Costa", "Manoel Ferreira"],
}

LEGACY_ROWS = {
    "source": "read from the scan by Allan on 2026-08-28",
    "reader": "Allan",
    "hand": "cursive",
    "pdf": "BR_RJANRIO_BS_0_RPV_ENT_013947_d0001de0001.pdf",
    "page": 2,
    "rows": {"3": "Antonio Coppola", "7": "Luigi Ferrero"},
}


class TestTheOldFilesStillLoad:
    def test_a_run_of_names_keeps_its_run(self, tmp_path):
        page = load_page(write(tmp_path, "old.json", LEGACY_RUN))
        assert page.names == ("Eliza da Costa", "Manoel Ferreira")
        assert page.rows == {}
        assert page.reader == "assistant"
        assert page.hand == "typed"

    def test_a_run_of_names_is_not_claimed_complete(self, tmp_path):
        assert load_page(write(tmp_path, "old.json", LEGACY_RUN)).complete is False

    def test_rows_keyed_by_row_number_load_as_readings(self, tmp_path):
        page = load_page(write(tmp_path, "old.json", LEGACY_ROWS))
        assert [(c.n, c.text) for c in page.read()] == [(3, "Antonio Coppola"),
                                                        (7, "Luigi Ferrero")]

    def test_the_original_dict_travels_with_the_page(self, tmp_path):
        page = load_page(write(tmp_path, "old.json", LEGACY_ROWS))
        assert page.raw["source"].startswith("read from the scan by Allan")


class TestLoadPages:
    def test_it_reads_a_directory_in_name_order(self, tmp_path):
        write(tmp_path, "b.json", NEW)
        write(tmp_path, "a.json", LEGACY_RUN)
        assert [p.reader for p in load_pages(tmp_path)] == ["assistant", "Allan"]

    def test_one_unlabelled_file_stops_the_lot(self, tmp_path):
        write(tmp_path, "a.json", {k: v for k, v in NEW.items() if k != "reader"})
        with pytest.raises(ValueError, match="reader"):
            load_pages(tmp_path)
