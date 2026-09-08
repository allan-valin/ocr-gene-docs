"""Scores split by hand, which is T3 of docs/TASKS-honest-measurement.md.

The 138 was one blended figure over pages of unlike difficulty: two typed
pages that are effectively solved and four cursive ones that are the point.
Blended, the typed pages inflate every number the repository quotes. So the
matrix prints them apart or it prints nothing.
"""
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
bench = runpy.run_path(str(ROOT / "scripts" / "bench_search.py"))
truth_rows = bench["truth_rows"]
tally = bench["tally"]


def corpus(tmp_path, truth: dict, rows: list[dict]):
    """A scans directory, a record cache and a truth directory for one page."""
    from desembarque.identity import cached_hash

    scans, cache, truth_dir = (tmp_path / n for n in ("scans", "cache", "truth"))
    for d in (scans, cache, truth_dir):
        d.mkdir()
    pdf = scans / truth["pdf"]
    pdf.write_bytes(b"%PDF-1.4 not really a pdf, only a thing to hash")
    doc = cached_hash(pdf)
    (cache / f"{doc}.json").write_text(json.dumps(
        {"file": truth["pdf"], "rows": rows, "voyage": {"year": 1907}}),
        encoding="utf-8")
    (truth_dir / "page.json").write_text(json.dumps(truth, ensure_ascii=False),
                                         encoding="utf-8")
    return scans, cache, truth_dir


ROWS = [{"page": 2, "n": 1, "name_raw": "ANTONIO COPPOLA"},
        {"page": 2, "n": 2, "name_raw": "LUUGI FERRERO"}]


def test_a_page_written_in_the_rows_form_is_scored_at_all(tmp_path):
    """Allan's page is the only one a person read, and it was being skipped."""
    truth = {"pdf": "a.pdf", "page": 2, "reader": "Allan", "hand": "cursive",
             "rows": {"1": "Antonio Coppola", "2": "Luigi Ferrero"}}
    scans, cache, truth_dir = corpus(tmp_path, truth, ROWS)
    got = truth_rows(cache, scans, truth_dir=truth_dir)
    assert [w["name"] for w in got] == ["Antonio Coppola", "Luigi Ferrero"]


def test_every_scored_name_carries_the_hand_it_was_written_in(tmp_path):
    truth = {"pdf": "a.pdf", "page": 2, "reader": "assistant", "hand": "typed",
             "names": ["Antonio Coppola", "Luigi Ferrero"]}
    scans, cache, truth_dir = corpus(tmp_path, truth, ROWS)
    assert {w["hand"] for w in truth_rows(cache, scans, truth_dir=truth_dir)} == {"typed"}


def test_it_carries_the_reader_too_so_a_score_can_say_who_wrote_it(tmp_path):
    truth = {"pdf": "a.pdf", "page": 2, "reader": "assistant", "hand": "cursive",
             "names": ["Antonio Coppola"]}
    scans, cache, truth_dir = corpus(tmp_path, truth, ROWS)
    assert {w["reader"] for w in truth_rows(cache, scans, truth_dir=truth_dir)} == {"assistant"}


def test_a_truth_page_with_no_reader_stops_the_bench(tmp_path):
    truth = {"pdf": "a.pdf", "page": 2, "hand": "typed", "names": ["Antonio Coppola"]}
    scans, cache, truth_dir = corpus(tmp_path, truth, ROWS)
    with pytest.raises(ValueError, match="reader"):
        truth_rows(cache, scans, truth_dir=truth_dir)


class TestTally:
    def test_it_counts_each_hand_apart_and_blended(self):
        scored = [("typed", 1), ("typed", 3), ("cursive", 30), ("cursive", None)]
        got = tally(scored, cutoffs=(5, 10, 20))
        assert got["typed"] == {"n": 2, "found": [2, 2, 2]}
        assert got["cursive"] == {"n": 2, "found": [0, 0, 0]}
        assert got["blended"] == {"n": 4, "found": [2, 2, 2]}

    def test_a_rank_past_the_cutoff_is_not_found(self):
        got = tally([("cursive", 7)], cutoffs=(5, 10, 20))
        assert got["cursive"]["found"] == [0, 1, 1]

    def test_a_hand_nobody_read_is_absent_rather_than_zero(self):
        got = tally([("cursive", 1)], cutoffs=(5,))
        assert "typed" not in got
        assert got["blended"]["n"] == 1

    def test_pages_of_unknown_hand_are_their_own_row(self):
        got = tally([("unknown", 1)], cutoffs=(5,))
        assert got["unknown"] == {"n": 1, "found": [1]}
