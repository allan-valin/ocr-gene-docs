"""Which pages are the hard ones — T4 of docs/TASKS-honest-measurement.md.

Every score this repository quotes has to be split typed from cursive, and a
stratified sample cannot be drawn without knowing which is which. The engine
already says it: a typed page reads back as `Eliza da Costa Guimaraes` and a
cursive one as `Jogriey elborgues`, and its own confidence follows.
"""
from desembarque.hands import (
    CURSIVE, CUT, TYPED, UNKNOWN, label_document, label_page, page_features,
)


def rows(page, confs, name="Someone"):
    return [{"page": page, "n": i + 1, "name_raw": name,
             "conf": {"surname": c}} for i, c in enumerate(confs)]


class TestFeatures:
    def test_it_measures_the_middle_reading_not_the_mean(self):
        got = page_features(rows(2, [0.5, 0.9, 0.95, 0.96, 0.97]))
        assert got["rows"] == 5
        assert got["median_conf"] == 0.95

    def test_rows_with_no_reading_are_not_measured(self):
        blank = [{"page": 2, "n": 9, "name_raw": "  ", "conf": {"surname": 0.99}}]
        got = page_features(rows(2, [0.5, 0.6, 0.7]) + blank)
        assert got["rows"] == 3

    def test_a_row_with_no_confidence_is_not_measured(self):
        got = page_features(rows(2, [0.8, 0.8]) + [{"page": 2, "n": 3,
                                                    "name_raw": "X", "conf": {}}])
        assert got["rows"] == 2

    def test_an_empty_page_measures_nothing(self):
        assert page_features([]) == {"rows": 0, "median_conf": None}


class TestLabelPage:
    def test_a_confident_page_is_typed(self):
        assert label_page(rows(2, [0.95, 0.99, 0.97, 0.98])) == TYPED

    def test_an_unsure_page_is_cursive(self):
        assert label_page(rows(2, [0.79, 0.80, 0.86, 0.64])) == CURSIVE

    def test_the_cut_sits_in_the_gap_the_six_known_pages_leave(self):
        # cursive tops out at 0.869 and typed starts at 0.952 on the pages
        # whose hand is known, so the cut is between them and near neither
        assert 0.869 < CUT < 0.952

    def test_too_few_readings_to_say_is_not_a_guess(self):
        assert label_page(rows(2, [0.99, 0.99])) == UNKNOWN

    def test_a_page_with_no_readings_at_all_is_unknown(self):
        assert label_page([]) == UNKNOWN


class TestLabelDocument:
    def test_a_document_takes_the_hand_of_most_of_its_rows(self):
        rec = {"rows": rows(2, [0.99] * 10) + rows(3, [0.70] * 30)}
        assert label_document(rec)["document"] == CURSIVE

    def test_each_page_keeps_its_own_label(self):
        rec = {"rows": rows(2, [0.99] * 10) + rows(3, [0.70] * 30)}
        assert label_document(rec)["pages"] == {2: TYPED, 3: CURSIVE}

    def test_pages_it_cannot_call_do_not_decide_the_document(self):
        rec = {"rows": rows(2, [0.99, 0.99]) + rows(3, [0.70] * 8)}
        got = label_document(rec)
        assert got["pages"][2] == UNKNOWN
        assert got["document"] == CURSIVE

    def test_a_document_it_can_say_nothing_about_is_unknown(self):
        assert label_document({"rows": []})["document"] == UNKNOWN


import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
script = runpy.run_path(str(ROOT / "scripts" / "classify_hands.py"))
classify = script["classify"]


class TestClassifyDirectory:
    def record(self, tmp_path, name, file, rows_):
        (tmp_path / name).write_text(json.dumps({"file": file, "hash": name[:-5],
                                                 "rows": rows_}), encoding="utf-8")

    def test_it_keys_the_labels_by_the_scan_they_belong_to(self, tmp_path):
        self.record(tmp_path, "aa.json", "one.pdf", rows(2, [0.99] * 6))
        got = classify(tmp_path)
        assert list(got) == ["one.pdf"]
        assert got["one.pdf"]["document"] == TYPED

    def test_the_confidence_behind_each_label_is_written_down(self, tmp_path):
        self.record(tmp_path, "aa.json", "one.pdf", rows(2, [0.7] * 5))
        assert got_median(classify(tmp_path)["one.pdf"], "2") == 0.7

    def test_a_record_naming_no_scan_is_skipped(self, tmp_path):
        (tmp_path / "bb.json").write_text(json.dumps({"rows": rows(2, [0.9] * 5)}),
                                          encoding="utf-8")
        assert classify(tmp_path) == {}

    def test_unreadable_json_does_not_stop_the_pass(self, tmp_path):
        (tmp_path / "aa.json").write_text("{not json", encoding="utf-8")
        self.record(tmp_path, "bb.json", "two.pdf", rows(2, [0.6] * 5))
        assert list(classify(tmp_path)) == ["two.pdf"]


def got_median(entry, page):
    return entry["median_conf"][page]


def test_the_confidence_is_read_under_its_current_key_too():
    """`conf` is keyed `name` since T6; the re-read of 2026-10-08 writes only
    that, and a classifier reading `surname` alone called the corpus unknown."""
    from desembarque.hands import page_features
    new = [{"page": 2, "n": i, "name_raw": "X", "conf": {"name": c}}
           for i, c in enumerate((0.9, 0.95, 0.99))]
    assert page_features(new)["median_conf"] == 0.95
