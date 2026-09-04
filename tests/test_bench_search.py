"""The second opinion, and how a row keeps somebody else's reading of it.

`read_bands.py` writes a sidecar keyed by the row number the engine gave the
crop, because the crops come out of the engine itself. `spike_second_opinion.py`
writes one keyed by a band's position on the page, which needs a map to say
which row that band became. The bench understands both, and a sidecar it does
not understand must leave the index alone rather than pair readings blindly.
"""
import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
bench = runpy.run_path(str(ROOT / "scripts" / "bench_search.py"))
add_second_opinion = bench["add_second_opinion"]


def sidecar(tmp_path, payload):
    p = tmp_path / "sidecar.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_a_sidecar_keyed_by_row_needs_no_map(tmp_path):
    rows = [{"doc": "abc", "page": 2, "row": 4, "text": "GUUDO CAMTADORE"}]
    path = sidecar(tmp_path, {"model": "m", "by": "row",
                              "read": {"abc": {"2": {"4": "Guiso Cantadore"}}}})
    said = add_second_opinion(rows, path)
    assert rows[0]["alts"] == ["Guiso Cantadore"]
    assert "1 rows read twice" in said


def test_a_sidecar_keyed_by_band_is_paired_through_its_map(tmp_path):
    rows = [{"doc": "abc", "page": 2, "row": 4, "text": "GUUDO CAMTADORE"}]
    path = sidecar(tmp_path, {"model": "m", "read": {"abc": {"2": {"7": "Guiso"}}},
                              "map": {"abc": {"2": {"7": 4}}}})
    add_second_opinion(rows, path)
    assert rows[0]["alts"] == ["Guiso"]


def test_a_reading_that_matches_the_engine_adds_nothing(tmp_path):
    rows = [{"doc": "abc", "page": 2, "row": 4, "text": "GUUDO"}]
    path = sidecar(tmp_path, {"by": "row", "read": {"abc": {"2": {"4": "GUUDO"}}}})
    add_second_opinion(rows, path)
    assert "alts" not in rows[0]


def test_a_row_the_index_does_not_carry_is_counted_unpaired(tmp_path):
    rows = [{"doc": "abc", "page": 2, "row": 4, "text": "GUUDO"}]
    path = sidecar(tmp_path, {"by": "row", "read": {"abc": {"2": {"9": "Guiso"}}}})
    said = add_second_opinion(rows, path)
    assert rows[0].get("alts") is None
    assert "1 unpaired" in said


def test_as_a_guess_it_goes_behind_the_readings(tmp_path):
    """A recogniser worse on average than the one that ships is weaker
    evidence: counted with the guesses it is weighted below every reading and
    kept out of the pass that runs when a crossing was named."""
    rows = [{"doc": "abc", "page": 2, "row": 4, "text": "GUUDO",
             "alts": ["GUIDO"]}]
    path = sidecar(tmp_path, {"by": "row", "read": {"abc": {"2": {"4": "Guiso"}}}})
    add_second_opinion(rows, path, as_guess=True)
    assert rows[0]["alts"] == ["GUIDO", "Guiso"]
    assert rows[0]["guessed"] == 1
