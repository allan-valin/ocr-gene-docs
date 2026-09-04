"""Refreshing a record's reading in the same pass that cuts its crops.

The second opinion is pasted onto the corpus by document, page and row, and
the corpus was read whenever that dossier was last touched: on the 15-dossier
subcorpus today's reading agrees with the stored one on 100% of the hand-read
pages and 58% of the rest. That gap is the whole fairness problem — the rows
being searched for keep their second reading and the rows competing with them
lose it — and it closes if the pass that cuts the crops also writes down what
it read.
"""
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "export_bands_test", ROOT / "scripts" / "export_bands.py")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:                      # the engine is not installed here
        return None
    return mod


def test_a_refreshed_record_keeps_the_pages_this_run_did_not_read():
    mod = load()
    if mod is None:
        import pytest
        pytest.skip("the OCR engine is not importable in this environment")
    existing = [{"page": 2, "n": 1, "name_raw": "old"},
                {"page": 3, "n": 1, "name_raw": "untouched"}]
    fresh = {2: [{"n": 1, "name_raw": "new"}]}
    got = mod.merged_rows(existing, fresh)
    assert got == [{"page": 2, "n": 1, "name_raw": "new"},
                   {"page": 3, "n": 1, "name_raw": "untouched"}]


def test_a_page_read_to_nothing_still_replaces_what_was_there():
    """A page the engine now reads as empty is a reading, not an absence: a
    record left holding last month's names for it would be paired against a
    sidecar that has none."""
    mod = load()
    if mod is None:
        import pytest
        pytest.skip("the OCR engine is not importable in this environment")
    got = mod.merged_rows([{"page": 2, "n": 1, "name_raw": "old"}], {2: []})
    assert got == []


def test_a_row_somebody_typed_survives_the_refresh():
    """The refresh exists so a bench pairs like with like, and it is still a
    re-read: a row a person typed, chose a reading for, or ticked is theirs
    (T4), and a re-read is not allowed to take it."""
    mod = load()
    if mod is None:
        import pytest
        pytest.skip("the OCR engine is not importable in this environment")
    existing = [{"page": 2, "n": 1, "name_raw": "Raymundo Cassaudii",
                 "verified": True, "edits": [{"field": "name"}]},
                {"page": 2, "n": 2, "name_raw": "the engine's"}]
    fresh = {2: [{"n": 1, "name_raw": "re-read over the top"},
                 {"n": 2, "name_raw": "re-read, and welcome"}]}
    got = mod.merged_rows(existing, fresh)
    assert got[0]["name_raw"] == "Raymundo Cassaudii"
    assert got[0]["edits"], "the provenance travels with the row"
    assert got[1]["name_raw"] == "re-read, and welcome"
