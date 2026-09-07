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


def bands_dir(tmp_path, index):
    d = tmp_path / "bands"
    d.mkdir()
    (d / "bands.json").write_text(json.dumps(index), encoding="utf-8")
    return d


def test_a_row_the_export_read_differently_is_refused(tmp_path):
    """The sidecar's row numbers come from a reading taken today; the index's
    come from whenever that dossier was last read. On the subcorpus those agree
    on 100% of the hand-read pages and 58% of the rest — the engine has moved
    on and the corpus has not — so pasting a reading onto a row that no longer
    holds the same name is how a second opinion lands on a stranger."""
    rows = [{"doc": "abc", "page": 2, "row": 4, "text": "LISTA dos passag"}]
    side = sidecar(tmp_path, {"by": "row",
                              "read": {"abc": {"2": {"4": "Edwina Bennett"}}}})
    bands = bands_dir(tmp_path, {"abc/2": [{"n": 4, "file": "x.png",
                                            "engine": "Edwina Beunett"}]})
    said = add_second_opinion(rows, side, bands=bands)
    assert "alts" not in rows[0]
    assert "1 refused" in said


def test_a_row_the_export_read_the_same_way_is_paired(tmp_path):
    rows = [{"doc": "abc", "page": 2, "row": 4, "text": "Edwina Beunett"}]
    side = sidecar(tmp_path, {"by": "row",
                              "read": {"abc": {"2": {"4": "Edwina Bennett"}}}})
    bands = bands_dir(tmp_path, {"abc/2": [{"n": 4, "file": "x.png",
                                            "engine": "Edwina Beunett"}]})
    add_second_opinion(rows, side, bands=bands)
    assert rows[0]["alts"] == ["Edwina Bennett"]


def test_a_repetition_mark_is_not_a_stale_row(tmp_path):
    """The index carries what a row is searched by, and for a row written with
    a repetition mark that is the words above it followed by its own: `"
    Maria` is indexed as `Martinez Maria`. The export carries the reading. They
    are the same row and the guard has to say so."""
    rows = [{"doc": "abc", "page": 2, "row": 4, "text": "Martinez Maria"}]
    side = sidecar(tmp_path, {"by": "row",
                              "read": {"abc": {"2": {"4": "Martimez Maria"}}}})
    bands = bands_dir(tmp_path, {"abc/2": [{"n": 4, "file": "x.png",
                                            "engine": "Maria"}]})
    add_second_opinion(rows, side, bands=bands)
    assert rows[0]["alts"] == ["Martimez Maria"]


def test_only_the_rows_asked_for_are_read_twice(tmp_path):
    """The second recogniser is ~2 s a row, so the batch pays for a subset.

    `only` is the (doc, page, row) the check flagged; everything else keeps
    the engine's reading alone and is counted as passed over, not as unpaired.
    """
    rows = [{"doc": "abc", "page": 2, "row": 4, "text": "GUUDO CAMTADORE"},
            {"doc": "abc", "page": 2, "row": 5, "text": "MARIA SILVA"}]
    path = sidecar(tmp_path, {"model": "m", "by": "row",
                              "read": {"abc": {"2": {"4": "Guiso Cantadore",
                                                     "5": "Maria Silva"}}}})
    said = add_second_opinion(rows, path, only={("abc", 2, 4)})
    assert rows[0]["alts"] == ["Guiso Cantadore"]
    assert "alts" not in rows[1]
    assert "1 rows read twice" in said
    assert "1 passed over" in said


def test_no_restriction_reads_every_paired_row(tmp_path):
    rows = [{"doc": "abc", "page": 2, "row": 4, "text": "GUUDO CAMTADORE"},
            {"doc": "abc", "page": 2, "row": 5, "text": "MARIA SILVA"}]
    path = sidecar(tmp_path, {"model": "m", "by": "row",
                              "read": {"abc": {"2": {"4": "Guiso Cantadore",
                                                     "5": "Maria Sylva"}}}})
    said = add_second_opinion(rows, path)
    assert "2 rows read twice" in said
    assert "passed over" not in said
