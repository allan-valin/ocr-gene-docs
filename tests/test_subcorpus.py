"""Choosing the slice a second reading is measured over.

The slice has to hold the rows the bench searches for *and* the rows competing
with them, and it has to be the same slice next time or two runs cannot be
compared. Everything the choice depends on is the corpus's own hash order,
which is arbitrary and stable: no dossier is picked for reading well.
"""
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
chosen = runpy.run_path(str(ROOT / "scripts" / "subcorpus.py"))["chosen"]

RECORDS = [{"file": "a.pdf"}, {"file": "b.pdf"}, {"file": "c.pdf"},
           {"file": "d.pdf"}]


def test_the_hand_read_dossiers_come_first():
    got = chosen(RECORDS, {"c.pdf"}, 2)
    assert [r["file"] for r in got] == ["c.pdf", "a.pdf"]


def test_the_rest_follow_in_the_order_they_were_given():
    got = chosen(RECORDS, set(), 3)
    assert [r["file"] for r in got] == ["a.pdf", "b.pdf", "c.pdf"]


def test_asking_for_more_than_there_are_gives_what_there_is():
    assert len(chosen(RECORDS, {"d.pdf"}, 99)) == 4


def test_a_hand_read_dossier_is_never_counted_twice():
    got = chosen(RECORDS, {"a.pdf", "b.pdf"}, 3)
    assert [r["file"] for r in got] == ["a.pdf", "b.pdf", "c.pdf"]
