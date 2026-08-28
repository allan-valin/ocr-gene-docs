"""Candidates from the strokes, not from the spelling distance.

A run of minims — the plain vertical strokes of `i`, `u`, `n`, `m`, `r`, `w` —
carries a reliable number of strokes and an unreliable division into letters.
The recogniser picks one division and prints it with confidence. These tests
are the divisions the ink could equally have carried, and the letter
confusions that come from the same place: a stroke and a direction.
"""
import pytest

from desembarque import strokes


def has(word, want, **kw):
    """Whether the candidate is generated at all — ranking and the menu's cap
    are measured by `scripts/bench_menu.py`, not asserted here."""
    return any(c.word == want for c in strokes.variants(word, limit=200, **kw))


def test_a_minim_run_is_re_cut_every_way_its_stroke_count_allows():
    """MANIA and MARIA are the same ink: `ni` and `ri` are three strokes each."""
    assert has("MANIA", "MARIA")
    assert has("POUTICELLI", "PONTICELLI")
    # `min` and `rnii` are six strokes each, so DOMINGO and DORNIIGO are one
    # page and two divisions of it.
    assert has("DORNIIGO", "DOMINGO")


def test_a_re_cut_never_changes_the_number_of_strokes():
    for c in strokes.variants("MANIA"):
        if c.rule == "minims":
            assert strokes.stroke_count(c.word) == strokes.stroke_count("MANIA")


def test_letters_that_differ_by_an_ascender_or_a_descender_are_offered():
    """`Yosé` and `fore` are both `José` with the tall stroke read the other way."""
    assert has("YOSE", "JOSE")
    assert has("BUCA", "LUCA")


def test_round_letters_are_offered_for_each_other():
    assert has("ALONMO", "ALONSO") or has("ALONSO", "ALONMO")
    assert has("DANCHEZ", "SANCHEZ")


def test_a_word_is_never_offered_as_a_candidate_for_itself():
    assert not has("MARIA", "MARIA")


def test_the_abbreviations_the_clerks_wrote_are_expanded():
    """`Antº` and `F'cº` come back from the recogniser as `Ant?` and `F'co`,
    and the superscript is a mark the recogniser has no glyph for."""
    assert has("ANT?", "ANTONIO")
    assert has("F'CO", "FRANCISCO")
    assert has("FCO", "FRANCISCO")


def test_a_candidate_costs_what_it_changed():
    """Ranking is by how few stroke-level changes a reading needs, so the cost
    is on the candidate and not left to the caller to guess."""
    c = [c for c in strokes.variants("YOSE") if c.word == "JOSE"][0]
    assert c.cost == 1 and c.rule == "ascender"


def test_a_stroke_lost_at_an_edge_is_offered_when_the_word_it_makes_is_known():
    """`zabel` is `Izabel` with the first stroke gone. Offering every letter of
    the alphabet in front of every word would drown the menu, so the edge rules
    only speak when a source of names has heard of the result."""
    known = {"IZABEL"}
    assert any(c.word == "IZABEL"
               for c in strokes.variants("ZABEL", known=known))
    assert not any(c.rule == "edge" for c in strokes.variants("ZABEL"))


def test_a_word_the_clerk_wrote_as_two_is_split_where_a_known_name_falls():
    got = strokes.variants("MORVETTOFIANCIICO", known={"MORVETTO"}, limit=200)
    assert any(c.word == "MORVETTO FIANCIICO" and c.rule == "space" for c in got)


def test_the_candidates_come_back_cheapest_first():
    got = strokes.variants("MANIA", known={"MARIA"})
    assert [c.cost for c in got] == sorted(c.cost for c in got)


def test_a_known_name_outranks_an_unknown_one_of_the_same_cost():
    got = strokes.variants("MANIA", known={"MARIA"})
    words = [c.word for c in got]
    assert words.index("MARIA") == 0


def test_an_unknown_candidate_is_still_offered():
    """The archive has not read every name correctly yet — Guberti, Alfieri,
    Ponticelli — so a dictionary can never be the gate on what the ink says."""
    assert has("POUTICELLI", "PONTICELLI")     # known to nothing here


def test_the_menu_is_capped_so_one_long_word_cannot_flood_it():
    got = strokes.variants("MINIMUM", limit=12)
    assert len(got) <= 12


@pytest.mark.parametrize("word", ["", "  ", "A", "AB"])
def test_a_word_too_short_to_carry_a_reading_gets_no_candidates(word):
    assert strokes.variants(word) == []
