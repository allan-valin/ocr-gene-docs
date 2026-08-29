"""Reading again the pages a record says nobody could read.

The corpus carries 301 pages stored as `unknown` — the geometry found no table
on them and the page went by with nothing. They are not blank paper: today's
engine reads 28 names off one of them. The records are current by every stamp
the run checks, so a re-index skips all 660 of them and reports success, which
is the silent-loss shape this repository keeps finding in new clothes.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque.retry import pages_wanting_a_reading, with_page


def record(**kw):
    base = {"hash": "h", "engine": "paddle", "file": "d.pdf", "schema": 18,
            "pages": [{"n": 1, "kind": "cover"},
                      {"n": 2, "kind": "list"},
                      {"n": 3, "kind": "unknown"}],
            "rows": [{"page": 2, "n": 1, "name_raw": "JOSE MUESSO"}]}
    return {**base, **kw}


def test_a_page_that_produced_nothing_is_worth_reading_again():
    assert pages_wanting_a_reading(record()) == [3]


def test_a_page_that_produced_rows_is_left_alone():
    """Page 3 read something, so it is not read again — a second set of rows
    would draw two names against one line of the scan. Page 2 is in the list
    because it is a `list` page with nothing on it, which is the same failure
    as an `unknown` page and is now retried too."""
    r = record(rows=[{"page": 3, "n": 1, "name_raw": "MARIA"}])
    assert pages_wanting_a_reading(r) == [2]


def test_a_page_the_engine_failed_on_is_not_this_job():
    """An errored page makes the whole record stale, and an index run reads the
    document again from the top. Repairing it here would hide that."""
    r = record(pages=[{"n": 1, "kind": "unknown", "error": "oneDNN"}])
    assert pages_wanting_a_reading(r) == []


def test_a_record_nobody_read_is_not_this_job():
    """A document with no engine record at all is an index run's work."""
    assert pages_wanting_a_reading({"pages": [{"n": 1, "kind": "unknown"}]}) == []


def test_the_new_rows_go_in_at_their_page():
    out = with_page(record(), 3, {"n": 3, "kind": "list"},
                    [{"n": 1, "name_raw": "ANNA"}, {"n": 2, "name_raw": "PIETRO"}])
    assert [(r["page"], r["n"], r["name_raw"]) for r in out["rows"]] == [
        (2, 1, "JOSE MUESSO"), (3, 1, "ANNA"), (3, 2, "PIETRO")]
    assert out["pages"][2] == {"n": 3, "kind": "list"}


def test_rows_stay_in_page_order_when_the_repaired_page_is_first():
    r = record(pages=[{"n": 1, "kind": "unknown"}, {"n": 2, "kind": "list"}],
               rows=[{"page": 2, "n": 1, "name_raw": "JOSE MUESSO"}])
    out = with_page(r, 1, {"n": 1, "kind": "list"}, [{"n": 1, "name_raw": "ANNA"}])
    assert [r["page"] for r in out["rows"]] == [1, 2]


def test_a_page_already_tried_by_this_engine_is_not_tried_again():
    """A page that came back empty when it was read again will come back empty
    every time, and there are two hundred of them: an hour of every future run
    spent proving the same thing. The stamp is the engine's schema, so the next
    time the engine learns something they all come back into the list."""
    from desembarque.retry import with_nothing_found
    r = with_nothing_found(record(), 3, schema=18)
    assert r["pages"][2]["retried"] == 18
    assert pages_wanting_a_reading(r, schema=18) == []
    assert pages_wanting_a_reading(r, schema=19) == [3]


def test_marking_a_page_tried_touches_nothing_else():
    from desembarque.retry import with_nothing_found
    r = with_nothing_found(record(), 3, schema=18)
    assert r["rows"] == record()["rows"]
    assert r["schema"] == 18 and "read_schema" not in r


def test_a_page_that_still_reads_nothing_is_refused():
    """Nothing was gained, and rewriting the file would cost every future run
    the cache it resumes from."""
    assert with_page(record(), 3, {"n": 3, "kind": "unknown"}, []) is None


def test_a_page_that_already_had_rows_is_refused():
    """Row `n` is a band index. Putting a second reading of the same page beside
    the first would draw two rows against one line of the scan."""
    r = record(rows=[{"page": 3, "n": 1, "name_raw": "MARIA"}])
    assert with_page(r, 3, {"n": 3, "kind": "list"},
                     [{"n": 1, "name_raw": "ANNA"}]) is None


def test_a_page_the_record_does_not_have_is_refused():
    assert with_page(record(), 9, {"n": 9, "kind": "list"},
                     [{"n": 1, "name_raw": "ANNA"}]) is None


def test_what_a_person_typed_is_untouched():
    r = record(source="manual", saved_at="2026-08-01",
               rows=[{"page": 2, "n": 1, "name_raw": "Jose Muesso", "typed": True}])
    out = with_page(r, 3, {"n": 3, "kind": "list"}, [{"n": 1, "name_raw": "ANNA"}])
    assert out["rows"][0]["typed"] is True
    assert out["source"] == "manual" and out["saved_at"] == "2026-08-01"


def test_the_stamps_are_left_where_they_are():
    """The record was read at this schema and still is: one page of it was read
    again by the same engine. Lifting the stamp would say the whole document
    had been, which is the mistake that made these pages stale in the first
    place."""
    out = with_page(record(), 3, {"n": 3, "kind": "list"},
                    [{"n": 1, "name_raw": "ANNA"}])
    assert out["schema"] == 18 and "read_schema" not in out


def test_a_list_that_came_back_with_no_rows_is_worth_reading_again():
    """A page stored as `list` with nothing on it is the same failure as a page
    stored as `unknown`: the geometry found no rows and nobody was told. Twelve
    records on disk are in exactly that state, and they are the pages the faint
    lift was written for — the earlier retry pass moved them off `unknown`
    without putting a name on them."""
    r = record(pages=[{"n": 1, "kind": "list"}, {"n": 2, "kind": "list"}],
               rows=[{"page": 1, "name_raw": "Alfieri"}])
    assert pages_wanting_a_reading(r) == [2]


def test_a_list_with_no_rows_that_this_engine_already_retried_is_left_alone():
    """The same stamp rule the unknown pages have: two hundred of them are
    genuinely blank paper, and re-proving that on every run costs an hour and
    finds nobody."""
    r = record(pages=[{"n": 2, "kind": "list", "retried": 4}], rows=[])
    assert pages_wanting_a_reading(r, schema=4) == []
    assert pages_wanting_a_reading(r, schema=5) == [2]


def test_a_page_measured_wrong_can_be_read_again_over_its_own_rows():
    """Half the pages on disk carry a name column measured before the table was
    measured from the printing: 946 of 2,543 are narrower than a name, which is
    the ordinal strip, and the crops behind them held the page number and two
    letters. Those pages have rows — bad ones — so `with_page` refuses them,
    and it is right to: it exists so a second reading never draws two names
    against one line. Re-measuring is the other case, and it replaces the
    engine's rows on that page while every row a person typed stays."""
    from desembarque.retry import with_page_remeasured
    r = record(pages=[{"n": 2, "kind": "list"}],
               rows=[{"page": 2, "n": 1, "name_raw": "lio da C"},
                     {"page": 2, "n": 2, "name_raw": "MARIA CORRECTED",
                      "edits": {"name_raw": "2026-08-01T10:00"}},
                     {"page": 3, "n": 1, "name_raw": "OTHER PAGE"}])
    fresh = [{"n": 1, "name_raw": "JULIO DA COSTA"},
             {"n": 2, "name_raw": "maria something"},
             {"n": 3, "name_raw": "NEW ROW"}]
    out = with_page_remeasured(r, 2, {"n": 2, "kind": "list"}, fresh)
    got = {(x.get("page"), x.get("n")): x.get("name_raw") for x in out["rows"]}
    assert got[(2, 1)] == "JULIO DA COSTA", "the engine's own row is replaced"
    assert got[(2, 2)] == "MARIA CORRECTED", "what a person typed is untouched"
    assert got[(2, 3)] == "NEW ROW"
    assert got[(3, 1)] == "OTHER PAGE", "another page is not touched"


def test_a_re_measure_that_reads_nothing_is_refused():
    """A page that comes back empty is a failure, not a page with nobody on it,
    and it must never stand in for what was there."""
    from desembarque.retry import with_page_remeasured
    r = record(pages=[{"n": 2, "kind": "list"}],
               rows=[{"page": 2, "n": 1, "name_raw": "lio da C"}])
    assert with_page_remeasured(r, 2, {"n": 2, "kind": "list"}, []) is None
