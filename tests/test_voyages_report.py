"""What the corpus knows about its own voyages, counted.

The voyage fields are only worth the search they narrow, and the way to know
whether they are worth anything is to look at what came out: how many dossiers
name a ship, how many resolve to a year, which ships recur. It is also the
cheapest check that a change to the parser has not quietly started filing
letterhead as vessels.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque.voyages_report import summarise


RECORDS = [
    {"notation": "A.1", "engine": "paddle",
     "voyage": {"ship": "Valdivia", "year": 1924, "port": "Santos",
                "line": "Lloyd Brazileiro", "arrival": "1924-12-10"}},
    {"notation": "A.2", "engine": "paddle",
     "voyage": {"ship": "Valdivin", "year": 1924}},
    {"notation": "A.3", "engine": "paddle", "voyage": {"line": "Lloyd Brazileiro"}},
    {"notation": "A.4", "engine": "paddle"},
]


def test_it_counts_how_much_of_the_corpus_states_anything_at_all():
    s = summarise(RECORDS)
    assert s["documents"] == 4
    assert s["with_voyage"] == 3
    assert s["with_ship"] == 2
    assert s["with_year"] == 2
    assert s["with_full_date"] == 1


def test_two_spellings_of_one_ship_are_counted_as_one():
    """`Valdivia` and `Valdivin` are the same vessel through the same
    recogniser. Counting them apart would report twice as many ships as sailed
    and hide the fact that the corpus has any depth at all."""
    s = summarise(RECORDS)
    ships = dict(s["ships"])
    assert len(ships) == 1
    assert list(ships.values())[0] == 2


def test_the_years_are_reported_in_order():
    s = summarise(RECORDS + [{"engine": "e", "voyage": {"year": 1919}}])
    assert [y for y, _ in s["years"]] == [1919, 1924]


def test_a_corpus_that_has_been_read_but_states_nothing_is_not_an_error():
    s = summarise([{"notation": "X", "engine": "paddle"}])
    assert s["with_voyage"] == 0 and s["ships"] == []


def test_three_spellings_of_one_shipping_line_are_counted_as_one():
    """The corpus run returned `Companhia`, `Conpanhia` and `Comnpanhia
    Nacional de Navegação Costeira` — one letterhead, read three ways. Listed
    apart they look like three companies with one sailing each, which is the
    opposite of what the page shows."""
    recs = [{"engine": "e", "voyage": {"line": name}} for name in (
        "Companhia Nacional de Navegação Costeira",
        "Conpanhia Nacional de Navegação Costeira",
        "Comnpanhia Nacional de Navegação Costeira",
        "LLOYD ITALIANO")]
    lines = dict(summarise(recs)["lines"])
    assert len(lines) == 2
    assert max(lines.values()) == 3
