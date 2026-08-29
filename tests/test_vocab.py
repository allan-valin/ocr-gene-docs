"""What a column of a closed vocabulary is worth after the recogniser.

The name column has no closed vocabulary — whose names exist is the question
the archive is being read to answer. Nationality, civil state and profession
are the opposite: a passenger list prints the same forty words over and over,
and the recogniser's `SEAGNOLA`, `LASIERCL` and `conercio` are all one fuzzy
match from the word the clerk typed. A snapped value is still a guess, so it is
kept beside the reading and never instead of it.
"""


def test_a_reading_snaps_to_the_word_the_clerk_typed():
    from desembarque.vocab import Vocabulary
    v = Vocabulary({"nacionalidade": ["ESPANHOLA", "BRASILEIRO"]})
    got = v.snap("nacionalidade", "SEAGNOLA")
    assert got["value"] == "ESPANHOLA"
    assert 0.6 <= got["score"] <= 1.0


def test_a_reading_close_to_nothing_snaps_to_nothing():
    """A column of forty words is not a licence to put one of them on every
    row. Half the cells on these pages are blank and the rest are faint."""
    from desembarque.vocab import Vocabulary
    v = Vocabulary({"nacionalidade": ["ESPANHOLA", "BRASILEIRO"]})
    assert v.snap("nacionalidade", "XQZ") is None
    assert v.snap("nacionalidade", "") is None
    assert v.snap("nacionalidade", None) is None


def test_the_reading_is_kept_beside_the_snapped_value():
    """The rule the whole gazetteer runs on: a suggestion is never a value, and
    what the page was read as has to stay legible next to what it was snapped
    to, or nobody can tell the two apart later."""
    from desembarque.vocab import Vocabulary
    v = Vocabulary({"estado": ["SOLT", "CASADO"]})
    cell = {"text": "cau", "conf": 0.4}
    got = v.snapped(cell, "estado")
    assert got["text"] == "cau", "the reading is untouched"
    assert got["value"] == "CASADO" and got["snap"] >= 0.6
    assert got["conf"] == 0.4


def test_each_column_is_snapped_to_its_own_list():
    """`SOLT` is a civil state and never a nationality; a list that leaks puts
    a profession in the age column the first time the crops slip."""
    from desembarque.vocab import Vocabulary
    v = Vocabulary({"nacionalidade": ["ESPANHOLA"], "estado": ["SOLT"]})
    assert v.snap("nacionalidade", "SOLT") is None
    assert v.snap("estado", "SOLT")["value"] == "SOLT"
    assert v.snap("profissao", "ESPANHOLA") is None


def test_case_and_accents_are_folded_and_the_stored_word_keeps_its_own():
    from desembarque.vocab import Vocabulary
    v = Vocabulary({"profissao": ["COMÉRCIO", "LAVRADOR"]})
    got = v.snap("profissao", "conercio")
    assert got["value"] == "COMÉRCIO"


def test_the_list_on_disk_says_where_it_came_from():
    """The same claim `data/language_names.json` makes: this is a word these
    forms print, never a word this archive has been read to contain.

    Skipped where the file is not there. Nothing under `data/` is versioned —
    the records are public records about real people and this remote is public
    — so a clone has the code and none of the lists, and a test that needs one
    says so rather than failing."""
    import json
    from pathlib import Path
    import pytest
    from desembarque.vocab import Vocabulary
    p = Path(__file__).resolve().parents[1] / "data" / "column_vocab.json"
    if not p.exists():
        pytest.skip("data/column_vocab.json is not versioned")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d.get("source") and d.get("why")
    v = Vocabulary.load(p)
    assert v.snap("nacionalidade", "ISPAGNOLA")["value"] == "ESPANHOLA"
    assert v.snap("estado", "SOLT")["value"] == "SOLT"


def test_a_column_can_ask_for_a_nearer_match_than_the_others():
    """Measured on BS.ENT.017397 p2: at 0.55 the civil state snaps 13 rows and
    12 of them are the word the clerk typed, and the profession 8 with 7 right —
    those two are short lists of words that look like nothing else. Nationality
    at the same floor snaps 10 and gets 4: `BIG` is as near INGLEZ as it is to
    BELGICA, and the list is fifty long words that share their endings. So the
    floor is per column, and a column that guesses badly is made to ask for a
    nearer match rather than dragging the others up with it."""
    from desembarque.vocab import Vocabulary
    v = Vocabulary({"nacionalidade": ["INGLEZ", "BELGICA"], "estado": ["CASADO"]},
                   floors={"nacionalidade": 0.9})
    assert v.snap("nacionalidade", "BIG") is None
    assert v.snap("estado", "cau")["value"] == "CASADO"


def test_the_floors_travel_with_the_list_on_disk():
    from pathlib import Path
    import pytest
    from desembarque.vocab import Vocabulary
    p = Path(__file__).resolve().parents[1] / "data" / "column_vocab.json"
    if not p.exists():
        pytest.skip("data/column_vocab.json is not versioned")
    v = Vocabulary.load(p)
    assert v.floors.get("nacionalidade", 0) > v.floors.get("estado", 1)
    assert v.snap("estado", "cau")["value"] == "CASADO"
