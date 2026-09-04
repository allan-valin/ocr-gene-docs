"""The join between what a second recogniser said and what a person says.

Every number in the reading-quality plan is decided by an instrument, and an
instrument that joins the wrong reading to the wrong label reports an
improvement that is not there. The sidecar is keyed by document, page and row;
so is the labelled set, since a training set built from crops named by their
first eight hash characters cannot be joined to anything.
"""
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
scored = runpy.run_path(str(ROOT / "scripts" / "score_crops.py"))["scored"]

SAID = {"abc": {"2": {"4": "Guiso Cantadore", "5": "Maria"}}}


def test_a_labelled_row_carries_both_readings_and_both_errors():
    got = scored([{"label": "Guido Cantadore", "engine": "Guudo Camtadore",
                   "doc": "abc", "page": 2, "n": 4}], SAID)
    assert len(got) == 1
    assert got[0]["second"] == "Guiso Cantadore"
    assert got[0]["cer_second"] < got[0]["cer_engine"], \
        "one letter wrong beats two"


def test_a_row_the_sidecar_never_read_is_not_scored_as_empty():
    """Counting an unread row as a miss would score the crops that failed to
    export rather than the reading."""
    assert scored([{"label": "Maria", "engine": "Maria",
                    "doc": "abc", "page": 2, "n": 9}], SAID) == []


def test_a_label_from_a_set_that_cannot_be_joined_is_skipped():
    assert scored([{"label": "Maria", "engine": "Maria",
                    "image": "images/abc_2_4.png"}], SAID) == []
