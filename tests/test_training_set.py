"""The labelled pairs, and where they come from.

Two sources, both of them a person's word about what a row says: the hand-read
truth pages, and every row somebody has retyped on the review screen. The
second is the one that grows — nothing else on the training list is possible
without it — so it is read out of the records themselves, retroactively,
rather than captured at the moment somebody types.
"""
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ts = runpy.run_path(str(ROOT / "scripts" / "training_set.py"))
corrections_in = ts["corrections_in"]
band_rows_of = ts["band_rows_of"]


def record(rows, pages=None):
    return {"file": "d.pdf", "rows": rows,
            "pages": pages or [{"n": 2, "geometry": {"rows": [[0, 1]],
                                                     "columns": [0, 1]}}]}


def test_a_retyped_name_is_a_label():
    rec = record([{"n": 4, "page": 2, "name_raw": "Nayomgo Cassaudi",
                   "verified": True,
                   "edits": [{"field": "name", "to": "Naymogo Cassandi",
                              "at": "2026-08-21T11:17:03Z"}]}])
    assert corrections_in(rec) == [
        {"page": 2, "n": 4, "label": "Naymogo Cassandi", "how": "typed",
         "engine": "Nayomgo Cassaudi"}]


def test_the_last_word_on_a_row_is_the_label():
    rec = record([{"n": 4, "page": 2, "name_raw": "x",
                   "edits": [{"field": "name", "to": "first",
                              "at": "2026-08-21T11:17:03Z"},
                             {"field": "name", "to": "second",
                              "at": "2026-08-28T09:00:00Z"}]}])
    assert [c["label"] for c in corrections_in(rec)] == ["second"]


def test_choosing_an_alternative_reading_is_still_a_persons_word():
    rec = record([{"n": 4, "page": 2, "name_raw": "x",
                   "edits": [{"field": "name", "to": "Maria",
                              "from": "leitura alternativa",
                              "at": "2026-08-28T12:07:57Z"}]}])
    assert [(c["label"], c["how"]) for c in corrections_in(rec)] == [
        ("Maria", "chosen")]


def test_an_edit_to_another_column_says_nothing_about_the_name():
    rec = record([{"n": 4, "page": 2, "name_raw": "Pouticelli Sooai",
                   "verified": True, "occupation": "SIRVIENTA",
                   "edits": [{"field": "occupation", "to": "SIRVIENTA",
                              "at": "2026-08-21T18:08:20Z"}]}])
    assert corrections_in(rec) == []


def test_a_verified_row_is_a_weaker_label_and_is_asked_for(rec=None):
    """Somebody accepting the reading is evidence about it, but they may have
    been checking another column, so it is not counted with the typing."""
    rec = record([{"n": 4, "page": 2, "name_raw": "Ponticelli Giuseppe",
                   "verified": True}])
    assert corrections_in(rec) == []
    assert corrections_in(rec, verified=True) == [
        {"page": 2, "n": 4, "label": "Ponticelli Giuseppe", "how": "verified",
         "engine": "Ponticelli Giuseppe"}]


def test_a_row_on_a_page_that_was_never_measured_cannot_be_cut():
    rec = record([{"n": 4, "page": 9, "name_raw": "x",
                   "edits": [{"field": "name", "to": "Maria", "at": "z"}]}])
    assert corrections_in(rec) == []


def test_an_empty_correction_is_not_a_label():
    rec = record([{"n": 4, "page": 2, "name_raw": "x",
                   "edits": [{"field": "name", "to": "  ", "at": "z"}]}])
    assert corrections_in(rec) == []


def test_the_rows_of_a_page_read_like_an_exported_band_index():
    rec = record([{"n": 2, "page": 2, "name_raw": "ROCA"},
                  {"n": 1, "page": 2, "name_raw": "MARTINEZ"},
                  {"n": 1, "page": 3, "name_raw": "other page"},
                  {"n": 3, "page": 2, "name_raw": ""}])
    assert band_rows_of(rec, 2) == [{"n": 1, "engine": "MARTINEZ"},
                                    {"n": 2, "engine": "ROCA"}]


def test_a_run_of_names_is_labelled_by_row_number_not_by_position():
    """A page the engine cut into fewer bands has rows missing in the middle.
    Aligning the run against what the engine said finds one offset and then
    drifts past the gap, which puts a name on the row below it — on
    BS_ENT_015061-p6 that scored 42 rows at CER above 1, both readings, which
    is the signature of a mislabelled set rather than a bad recogniser."""
    labels_for_page = ts["labels_for_page"]
    band_rows = [{"n": 1, "engine": "Palmira Ie Yesus"},
                 {"n": 2, "engine": "Maria Yose de Yesus"},
                 # row 3 carries no reading and was never exported
                 {"n": 4, "engine": "Ignez Marqnes"}]
    truth = {"first_row": 1,
             "names": ["Palmira de Jesus", "Maria Jose de Jesus",
                       "Albertina Jorge Ferreira", "Ignez Marques"]}
    assert labels_for_page(band_rows, truth) == {
        1: "Palmira de Jesus", 2: "Maria Jose de Jesus", 4: "Ignez Marques"}


def test_a_page_keyed_by_row_is_taken_as_it_is():
    labels_for_page = ts["labels_for_page"]
    band_rows = [{"n": 4, "engine": "x"}, {"n": 9, "engine": "y"}]
    truth = {"rows": {"4": "Rossi Mario", "7": "not exported"}}
    assert labels_for_page(band_rows, truth) == {4: "Rossi Mario"}
