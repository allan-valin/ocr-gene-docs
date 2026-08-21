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
