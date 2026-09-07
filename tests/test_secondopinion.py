"""A second recogniser's readings, written into the records they belong to.

The reading was measured through a sidecar the bench understood and nothing
else did. Putting it on the row is what the application searches, so the write
has to be as careful as any other write to the corpus: it never touches a row
a person typed, it never invents a row, and running it twice leaves the same
corpus as running it once.
"""
import pytest

from desembarque.secondopinion import with_second_readings

MODEL = "Riksarkivet/trocr-base-handwritten-hist-swe-2"


def record(**over):
    base = {"hash": "h", "file": "d.pdf", "engine": "paddle", "rows": [
        {"n": 1, "page": 2, "name_raw": "GUUDO CAMTADORE"},
        {"n": 2, "page": 2, "name_raw": "MARIA SILVA"},
    ]}
    base.update(over)
    return base


def test_a_reading_lands_on_the_row_it_was_read_from():
    got, n = with_second_readings(record(), {2: {1: "Guiso Cantadore"}}, MODEL)
    assert n == 1
    assert got["rows"][0]["second_read"] == {"model": MODEL,
                                            "text": "Guiso Cantadore"}
    assert "second_read" not in got["rows"][1]


def test_a_row_nobody_read_again_is_left_alone():
    got, n = with_second_readings(record(), {}, MODEL)
    assert n == 0
    assert all("second_read" not in r for r in got["rows"])


def test_a_row_a_person_typed_is_never_given_a_machine_reading():
    """`typed_by_a_person`: the mark is the row's, not the record's."""
    rec = record()
    rec["rows"][0]["edits"] = {"name": "Guido Contadore"}
    got, n = with_second_readings(rec, {2: {1: "Guiso Cantadore"}}, MODEL)
    assert n == 0
    assert "second_read" not in got["rows"][0]


def test_a_reading_for_a_row_that_is_not_there_is_refused_not_invented():
    got, n = with_second_readings(record(), {2: {9: "Somebody Else"}}, MODEL)
    assert n == 0
    assert len(got["rows"]) == 2


def test_an_empty_reading_is_not_a_reading():
    got, n = with_second_readings(record(), {2: {1: "   "}}, MODEL)
    assert n == 0
    assert "second_read" not in got["rows"][0]


def test_running_it_twice_leaves_the_same_corpus():
    once, _ = with_second_readings(record(), {2: {1: "Guiso Cantadore"}}, MODEL)
    twice, n = with_second_readings(once, {2: {1: "Guiso Cantadore"}}, MODEL)
    assert twice == once
    assert n == 0


def test_a_newer_model_replaces_an_older_one_and_says_so():
    once, _ = with_second_readings(record(), {2: {1: "Guiso Cantadore"}}, MODEL)
    twice, n = with_second_readings(once, {2: {1: "Guido Contadore"}}, "other")
    assert n == 1
    assert twice["rows"][0]["second_read"] == {"model": "other",
                                              "text": "Guido Contadore"}


def test_the_record_it_was_given_is_not_the_record_it_returns():
    """Every other writer in this package returns a new record; a caller that
    compares the two to decide whether to save must be told the truth."""
    rec = record()
    got, _ = with_second_readings(rec, {2: {1: "Guiso Cantadore"}}, MODEL)
    assert got is not rec
    assert "second_read" not in rec["rows"][0]


# The script over a corpus on disk: what it refuses, and what it leaves alone.
import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
apply_script = runpy.run_path(str(ROOT / "scripts" / "apply_second_opinion.py"))


def corpus(tmp_path, side):
    records = tmp_path / "records"
    records.mkdir()
    (records / "h.json").write_text(json.dumps(record()), encoding="utf-8")
    sidecar = tmp_path / "side.json"
    sidecar.write_text(json.dumps(side), encoding="utf-8")
    return records, sidecar


def test_nothing_is_written_until_it_is_asked_for(tmp_path, capsys):
    records, side = corpus(tmp_path, {
        "model": MODEL, "by": "row",
        "read": {"h": {"2": {"1": "Guiso Cantadore"}}}})
    before = (records / "h.json").read_text(encoding="utf-8")
    assert apply_script["main"](["--sidecar", str(side),
                                 "--records", str(records)]) == 0
    assert (records / "h.json").read_text(encoding="utf-8") == before
    assert "1 rows would be written" in capsys.readouterr().out


def test_the_write_lands_on_disk(tmp_path):
    records, side = corpus(tmp_path, {
        "model": MODEL, "by": "row",
        "read": {"h": {"2": {"1": "Guiso Cantadore"}}}})
    apply_script["main"](["--sidecar", str(side), "--records", str(records),
                          "--write"])
    got = json.loads((records / "h.json").read_text(encoding="utf-8"))
    assert got["rows"][0]["second_read"]["text"] == "Guiso Cantadore"


def test_a_sidecar_keyed_by_a_band_is_refused_rather_than_paired(tmp_path):
    """Its row numbers are band positions; pairing them blindly hands a name
    somebody else's ink, which is the fault the sidecar format exists to avoid.
    """
    records, side = corpus(tmp_path, {
        "model": MODEL, "read": {"h": {"2": {"7": "Guiso Cantadore"}}},
        "map": {"h": {"2": {"7": 1}}}})
    before = (records / "h.json").read_text(encoding="utf-8")
    assert apply_script["main"](["--sidecar", str(side),
                                 "--records", str(records), "--write"]) == 2
    assert (records / "h.json").read_text(encoding="utf-8") == before


def test_a_document_the_sidecar_names_and_the_corpus_does_not_is_reported(
        tmp_path, capsys):
    records, side = corpus(tmp_path, {
        "model": MODEL, "by": "row",
        "read": {"gone": {"2": {"1": "Guiso Cantadore"}}}})
    apply_script["main"](["--sidecar", str(side), "--records", str(records)])
    assert "1 documents in the sidecar are not in" in capsys.readouterr().out
