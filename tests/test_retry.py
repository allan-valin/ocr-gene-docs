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
    r = record(rows=[{"page": 3, "n": 1, "name_raw": "MARIA"}])
    assert pages_wanting_a_reading(r) == []


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
