"""What a re-read did to the corpus, dossier by dossier.

The whole-corpus re-read writes into a copy and the copy only becomes the
corpus if it is better. "Better" has to be a number before it is a decision:
rows carrying a name, per document, and — the safety property — every row a
person typed still there and still saying what they typed.
"""
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
mod = runpy.run_path(str(ROOT / "scripts" / "compare_corpora.py"))
compare = mod["compare"]


def rec(rows):
    return {"hash": "h", "file": "d.pdf", "engine": "paddle", "rows": rows}


def test_a_row_that_gained_a_name_is_counted():
    before = rec([{"n": 1, "page": 2, "name_raw": ""},
                  {"n": 2, "page": 2, "name_raw": "MARIA"}])
    after = rec([{"n": 1, "page": 2, "name_raw": "JOSE"},
                 {"n": 2, "page": 2, "name_raw": "MARIA"}])
    got = compare({"h": before}, {"h": after})
    assert got["named_before"] == 1
    assert got["named_after"] == 2
    assert got["docs"][0]["gained"] == 1


def test_a_document_that_lost_names_is_reported_as_lost():
    before = rec([{"n": 1, "page": 2, "name_raw": "JOSE"}])
    after = rec([{"n": 1, "page": 2, "name_raw": ""}])
    got = compare({"h": before}, {"h": after})
    assert got["docs"][0]["gained"] == -1
    assert got["lost"] == ["h"]


def test_a_document_the_re_read_never_reached_is_not_counted_as_unchanged():
    """A pass that stopped halfway must not be read as a pass that changed
    nothing: those are opposite conclusions about whether to keep the copy."""
    before = rec([{"n": 1, "page": 2, "name_raw": "JOSE"}])
    got = compare({"h": before}, {})
    assert got["missing"] == ["h"]
    assert got["named_after"] == 0


def test_a_row_a_person_typed_must_survive_verbatim():
    typed = {"n": 1, "page": 2, "name_raw": "Guido Contadore",
             "edits": {"name": "Guido Contadore"}}
    before = rec([typed])
    after = rec([{**typed, "name_raw": "GUUDO CAMTADORE"}])
    got = compare({"h": before}, {"h": after})
    assert got["human_changed"] == [("h", 2, 1)]


def test_an_untouched_human_row_raises_nothing():
    typed = {"n": 1, "page": 2, "name_raw": "Guido Contadore",
             "edits": {"name": "Guido Contadore"}}
    got = compare({"h": rec([typed])}, {"h": rec([dict(typed)])})
    assert got["human_changed"] == []


def test_an_unchanged_document_is_named_as_unchanged():
    """The re-read writes into a *copy*, so every document exists in the second
    directory from the start and a missing one is not how a half-finished pass
    shows. An untouched document is one whose rows are what they were."""
    before = rec([{"n": 1, "page": 2, "name_raw": "MARIA"}])
    got = compare({"h": before}, {"h": rec([{"n": 1, "page": 2,
                                             "name_raw": "MARIA"}])})
    assert got["identical"] == ["h"]
    assert got["lost"] == []


def test_a_changed_document_is_not_called_unchanged():
    before = rec([{"n": 1, "page": 2, "name_raw": "MARIA"}])
    after = rec([{"n": 1, "page": 2, "name_raw": "MARIA GONSALVES"}])
    assert compare({"h": before}, {"h": after})["identical"] == []


# What counts as a row carrying a name is the index's rule, not a looser one:
# the verdict on a twenty-hour pass must not turn on whether `22222222` counts.

def test_a_printed_heading_is_not_a_name():
    got = compare({"h": rec([{"n": 1, "page": 2, "name_raw": "NOMS ET PRENOMS"}])},
                  {"h": rec([{"n": 1, "page": 2, "name_raw": "Carlos Fayet"}])})
    assert (got["named_before"], got["named_after"]) == (0, 1)


def test_a_row_too_short_to_index_is_not_a_name():
    """`load_index` drops a row under four folded characters, so counting it
    here would credit the corpus with a row nobody can ever search."""
    got = compare({"h": rec([{"n": 1, "page": 2, "name_raw": "1R"}])},
                  {"h": rec([{"n": 1, "page": 2, "name_raw": ""}])})
    assert (got["named_before"], got["named_after"]) == (0, 0)
    assert got["lost"] == []


def test_the_re_read_that_only_dropped_junk_is_not_counted_as_a_loss():
    """0a8e192e on the run of 2026-09-07: the pass read the names better and
    threw away `22222222` and the column caption, and the first count called
    that four names lost."""
    before = rec([{"n": 1, "page": 2, "name_raw": "NOMS ET PRENOMS"},
                  {"n": 2, "page": 2, "name_raw": "Carlos Fayet"},
                  {"n": 3, "page": 2, "name_raw": "22222222"}])
    after = rec([{"n": 1, "page": 2, "name_raw": "Carlos Fayet23"},
                 {"n": 2, "page": 2, "name_raw": "Deri Somis 60"}])
    got = compare({"h": before}, {"h": after})
    assert got["docs"][0]["gained"] == 1
    assert got["lost"] == []
