"""The parts of the CHURRO runner that are not a model.

The model is measured, not tested — but what it says arrives wrapped in the
tags its own prompt asks for, and a sidecar that keeps the tags would score
every row as wrong for a reason that has nothing to do with reading.
"""
import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
churro = runpy.run_path(str(ROOT / "scripts" / "read_vlm.py"))
unwrap = churro["unwrap"]
rows_from = churro["rows_from"]


class TestUnwrap:
    def test_it_takes_what_is_between_the_tags(self):
        assert unwrap("<output>Guido Cantadore</output>") == "Guido Cantadore"

    def test_it_survives_the_model_chattering_first(self):
        assert unwrap("Sure!\n<output>José Muesso</output>\n") == "José Muesso"

    def test_an_unclosed_tag_still_gives_the_reading(self):
        assert unwrap("<output>Emma Contadore") == "Emma Contadore"

    def test_a_bare_answer_is_taken_as_it_stands(self):
        assert unwrap("  Pedro Lammenn  ") == "Pedro Lammenn"

    def test_nothing_said_is_nothing_read(self):
        assert unwrap("<output></output>") == ""


class TestRowsFrom:
    def make(self, tmp_path, n):
        lines = [json.dumps({"image": f"images/x_{i}.png", "label": "A",
                             "doc": "d", "page": 2, "n": i}) for i in range(n)]
        (tmp_path / "labels.jsonl").write_text("\n".join(lines) + "\n",
                                               encoding="utf-8")
        return tmp_path

    def test_a_limit_reads_a_prefix_and_no_more(self, tmp_path):
        assert len(rows_from(self.make(tmp_path, 10), 3)) == 3

    def test_no_limit_reads_the_lot(self, tmp_path):
        assert len(rows_from(self.make(tmp_path, 10), 0)) == 10

    def test_a_blank_line_is_not_a_row(self, tmp_path):
        d = self.make(tmp_path, 2)
        (d / "labels.jsonl").write_text(
            (d / "labels.jsonl").read_text(encoding="utf-8") + "\n",
            encoding="utf-8")
        assert len(rows_from(d, 0)) == 2


class TestOnlyOneHand:
    def make(self, tmp_path):
        rows = [{"image": "a.png", "source": "cursive-p2.json", "doc": "d",
                 "page": 2, "n": 1, "label": "A"},
                {"image": "b.png", "source": "typed-p2.json", "doc": "d",
                 "page": 2, "n": 2, "label": "B"},
                {"image": "c.png", "source": "unknown-hash.json", "doc": "d",
                 "page": 2, "n": 3, "label": "C"}]
        (tmp_path / "labels.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        return tmp_path, {"cursive-p2.json": "cursive", "typed-p2.json": "typed"}

    def test_it_reads_only_the_hand_asked_for(self, tmp_path):
        d, hands = self.make(tmp_path)
        got = rows_from(d, 0, hand="cursive", hands=hands)
        assert [r["n"] for r in got] == [1]

    def test_a_page_of_unrecorded_hand_is_not_guessed_into_either(self, tmp_path):
        d, hands = self.make(tmp_path)
        assert [r["n"] for r in rows_from(d, 0, hand="typed", hands=hands)] == [2]

    def test_no_hand_asked_for_reads_everything(self, tmp_path):
        d, hands = self.make(tmp_path)
        assert len(rows_from(d, 0, hands=hands)) == 3
