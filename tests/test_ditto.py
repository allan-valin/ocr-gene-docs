"""The repetition mark, resolved without being erased.

These lists are written by family: the surname is written once and every
relative below gets a ditto mark under it. BS.ENT.013947 p3 lists forty-eight
people and nine surnames — thirty-nine rows carry a mark instead of a name. A
search for `Martinez` finds one of the seven Martinezes on that page, and the
other six are invisible, which is the failure this tool exists to prevent.

What the page says and what the row means are two different claims, so both are
kept: `name_raw` stays exactly as it was read, and the surname is filled in from
the row it points at, marked as inherited so the UI can say so.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque.ditto import resolve


def rows(*texts):
    from desembarque.engine_paddle import split_name
    out = []
    for i, t in enumerate(texts, 1):
        sur, giv = split_name(t)
        out.append({"n": i, "name_raw": t, "surname": sur, "given": giv})
    return out


def test_a_mark_under_a_surname_means_that_surname():
    out = resolve(rows("Martinez Francisco", '" Maria'))
    assert out[1]["surname"] == "Martinez"
    assert out[1]["given"] == "Maria"
    assert out[1]["ditto"] == ["surname"]


def test_what_the_page_says_is_not_overwritten():
    """A record used as evidence has to be able to show the mark itself."""
    out = resolve(rows("Martinez Francisco", '" Maria'))
    assert out[1]["name_raw"] == '" Maria'


def test_the_mark_is_whatever_the_recogniser_made_of_it():
    """Real readings off these pages: the clerk's mark comes back as a quote, a
    comma, a pair of ones, a slash — never as the same character twice."""
    for mark in ('"', "''", ",,", "11", "//", "”", "«", ".", "-", "n"):
        out = resolve(rows("Lorenzo Cipriano", f"{mark} Maria"))
        assert out[1]["surname"] == "Lorenzo", mark


def test_a_name_is_not_a_mark():
    """`Turino Cettore` under `Turino Angela` is a written surname, not a
    repetition of one, and `Ana Rosa` is two given names."""
    out = resolve(rows("Turino Angela", "Turino Cettore", "Ana Rosa"))
    assert "ditto" not in out[1] and out[1]["surname"] == "Turino"
    assert "ditto" not in out[2] and out[2]["surname"] == "Ana"


def test_a_mark_with_nothing_above_it_inherits_nothing():
    out = resolve(rows('" Maria', "Martinez Francisco"))
    assert out[0]["surname"] in (None, '"', "")
    assert "ditto" not in out[0]


def test_the_mark_carries_down_a_whole_family():
    out = resolve(rows("Santa Nicolas", '" Maria', '" Jose', '" Pedro',
                       "Arquentiri Jose", '" Gabriela'))
    assert [r["surname"] for r in out] == ["Santa", "Santa", "Santa", "Santa",
                                           "Arquentiri", "Arquentiri"]


def test_a_blank_row_between_two_families_does_not_pass_the_name_on():
    """An empty row is a blank ruled line, and a mark below it points at
    whatever the clerk last wrote — but eight blank rows mean the list moved on,
    and a surname carried across that gap is a guess."""
    out = resolve(rows("Santa Nicolas", "", "", "", "", "", "", "", "", '" Maria'))
    assert "ditto" not in out[-1]


def test_the_engine_s_own_rows_keep_their_other_fields():
    out = resolve([{"n": 1, "name_raw": "Martinez Francisco", "surname": "Martinez",
                    "given": "Francisco", "conf": {"surname": 0.8}},
                   {"n": 2, "name_raw": '" Maria', "surname": '"', "given": "Maria",
                    "conf": {"surname": 0.4}, "alternatives": ["x"]}])
    assert out[1]["conf"] == {"surname": 0.4}
    assert out[1]["alternatives"] == ["x"]


def indented(text, indent):
    from desembarque.engine_paddle import split_name
    sur, giv = split_name(text)
    return {"name_raw": text, "surname": sur, "given": giv, "indent": indent}


def test_a_row_written_under_the_mark_is_a_continuation_even_unmarked():
    """On 013947 p3 the mark is small and the recogniser mostly returns the
    given name alone — `Fetipe`, `Maria` — with nothing to say the row belongs
    to the family above it. What is left is where the writing starts: under the
    mark, a third of the way into the column."""
    out = resolve([indented("Santabarbara Salvador", 0.02),
                   indented("Felipe", 0.34),
                   indented("Maria", 0.31)])
    assert [r["surname"] for r in out] == ["Santabarbara"] * 3
    assert out[1]["given"] == "Felipe" and out[1]["ditto"] == ["surname"]


def test_a_single_name_under_a_family_is_taken_as_one_of_them():
    """This test said the opposite until the retrieval bench was run against
    the hand-read pages: a single name under a family, inherited, takes findable
    names from 39/68 to 51/68. Read as written those rows carry no surname at
    all, and the surname is the one thing a person searching for an ancestor
    reliably knows.

    It is a weaker claim than a mark on the page, so it is labelled as one —
    `ditto_source: position` — and the reading itself is untouched."""
    out = resolve([indented("Santa Nicolas", 0.02), indented("Turino", 0.03)])
    assert out[1]["surname"] == "Santa"
    assert out[1]["ditto_source"] == "position"
    assert out[1]["name_raw"] == "Turino"


def test_two_names_at_an_indent_are_not_a_continuation():
    """A whole name written a little to the right is still a whole name."""
    out = resolve([indented("Santa Nicolas", 0.02),
                   indented("De Pedres Miguel", 0.22)])
    assert "ditto" not in out[1]


def test_a_single_name_does_not_become_the_family_name():
    """`"ose` inherited `Maria` — the row above it was read as one word, which
    on a family list is a given name under a mark the recogniser dropped."""
    out = resolve(rows("Santa Nicolas", "Maria", '" ose'))
    assert out[2]["surname"] == "Santa"


def test_every_inherited_surname_says_how_it_was_arrived_at():
    """A mark on the page and a guess from position are different claims."""
    out = resolve(rows("Martinez Francisco", '" Maria', "Manuel"))
    assert out[1]["ditto_source"] == "mark"
    assert out[2]["ditto_source"] == "position"
    assert out[2]["surname"] == "Martinez"


def test_a_name_the_clerk_wrote_in_full_is_never_inherited_over():
    out = resolve(rows("Martinez Francisco", "De Pedres Miguel"))
    assert "ditto" not in out[1] and out[1]["surname"] == "De Pedres"
