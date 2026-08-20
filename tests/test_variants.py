"""The other things the recogniser said about the same name.

A row is read more than once — from the PDF's ink mask and from a composited
render — and the two disagree exactly where the hand is hard: `Nayomgo` and
`Raymundo` are one word on one page. Today one reading wins and the other is
thrown away, so a person correcting the row retypes a name the engine had
already offered.

These are the engine's own readings, never inventions. A name the recogniser
never produced must not appear in a list of what it read.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque.variants import token_alternatives


def test_the_other_reading_of_a_word_is_offered_against_it():
    alts = token_alternatives(["Nayomgo Cassaudii", "Raymundo Cassaudie"])
    assert alts == [["Raymundo"], ["Cassaudie"]]


def test_a_word_both_readings_agree_on_has_no_alternatives():
    assert token_alternatives(["JOSE MUESSO", "JOSE MUERSO"]) == [[], ["MUERSO"]]


def test_the_chosen_reading_is_never_offered_against_itself():
    alts = token_alternatives(["JOSE MUESSO", "JOSE MUESSO"])
    assert alts == [[], []]


def test_three_readings_give_two_alternatives():
    alts = token_alternatives(["Guudo", "Guido", "Gnudo"])
    assert alts == [["Guido", "Gnudo"]]


def test_a_reading_with_more_words_does_not_shift_the_rest():
    """`A. VIEIRA MIRANDA` against `VIEIRA MIRANDA` — one reading dropped the
    initial. Aligning by position would offer `VIEIRA` as an alternative for
    `A.`, which is not a disagreement about a word, it is a different word."""
    alts = token_alternatives(["A. VIEIRA MIRANDA", "VIEIRA MIRANDA"])
    assert alts == [[], [], []]


def test_a_word_one_reading_spells_differently_inside_a_longer_name():
    alts = token_alternatives(["CEZARIO SAMMAMED SILVA", "CEZARIO SOMMAMED SILVA"])
    assert alts == [[], ["SOMMAMED"], []]


def test_an_empty_reading_offers_nothing():
    assert token_alternatives(["", "Raymundo"]) == []
    assert token_alternatives([]) == []
    assert token_alternatives(["Raymundo", ""]) == [[]]


def test_duplicates_across_readings_are_offered_once():
    alts = token_alternatives(["Guudo", "Guido", "Guido"])
    assert alts == [["Guido"]]
