"""Names offered as guesses, and never mistaken for readings.

The recogniser is at its ceiling on cursive — five separate measurements say so
— and the remaining help for somebody reading `Dantalarlraia Saliador` is a list
of names these ships are known to have carried. The whole design rests on the
difference between *what the page says* and *what it might have said*, so these
tests are mostly about keeping that line.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque.gazetteer import Names

ARCHIVE = Names({"SANTABARBARA": 12, "SALVADOR": 30, "MARIA": 161, "JOSE": 143,
                 "MARTINEZ": 22, "CONTADORE": 4, "SILVA": 40, "PEREIRA": 31})


def test_a_mangled_reading_is_matched_to_a_name_the_archive_carries():
    got = [c["name"] for c in ARCHIVE.suggest("Saliador")]
    assert "SALVADOR" in got


def test_the_commoner_name_breaks_a_tie():
    """Between two names equally close to a mangled word, the one that sailed
    forty times is the better guess."""
    names = Names({"SILVA": 40, "SILRA": 1})
    got = ARCHIVE.suggest("Silva") + names.suggest("Silwa")
    assert got[0]["name"] in ("SILVA",)


def test_a_reading_that_is_already_a_name_needs_no_guess():
    assert ARCHIVE.score("MARIA") == 1.0
    assert "MARIA" not in [c["name"] for c in ARCHIVE.suggest("MARIA")]


def test_nothing_close_enough_is_offered_rather_than_the_nearest_thing():
    """A list of names that share three letters and nothing else is not help."""
    assert ARCHIVE.suggest("Kowalczyk") == []
    assert ARCHIVE.suggest("Xy") == []


def test_a_guess_carries_its_score_and_how_often_the_archive_saw_it():
    c = ARCHIVE.suggest("Martines")[0]
    assert c["name"] == "MARTINEZ"
    assert 0 < c["score"] <= 1 and c["seen"] == 22


def test_the_engine_s_own_readings_are_ranked_by_being_names():
    """The menu already offers what the engine read twice. Which of those is a
    name in this archive is the question the person is answering."""
    ranked = ARCHIVE.rank(["Mavia", "Maria"])
    assert ranked[0]["word"] == "Maria" and ranked[0]["score"] == 1.0


def test_ranking_invents_nothing():
    ranked = ARCHIVE.rank(["Zzz", "Qqq"])
    assert [r["word"] for r in ranked] == ["Zzz", "Qqq"]


def test_a_missing_dictionary_is_an_empty_one_not_an_error():
    assert len(Names.load(Path("/nonexistent/names.json"))) == 0


def test_a_rebuilt_dictionary_is_picked_up_without_a_restart(tmp_path):
    """The list is rebuilt whenever the corpus is re-read, and a server that
    reads it once at startup keeps offering yesterday's names all day."""
    import json
    f = tmp_path / "names.json"
    f.write_text(json.dumps({"names": {"SILVA": 3}}), encoding="utf-8")
    names = Names.load(f)
    assert len(names) == 1
    f.write_text(json.dumps({"names": {"SILVA": 3, "PEREIRA": 2}}), encoding="utf-8")
    assert len(names.fresh()) == 2
    assert len(names.fresh().fresh()) == 2


def test_a_reading_that_resembles_no_name_here_is_flagged_for_a_person():
    """For deciding which rows to look at first, and nothing else."""
    assert ARCHIVE.doubtful("Xqzw Vbnm")
    assert not ARCHIVE.doubtful("Maria Silva")
    # a mangled reading that still resembles a name is not flagged: the person
    # has better uses for their afternoon
    assert not ARCHIVE.doubtful("Mavia Silwa")


def test_an_empty_reading_is_not_doubtful():
    """A blank row is a fact about the page, not a suspect one."""
    assert not ARCHIVE.doubtful("")
    assert not ARCHIVE.doubtful("  ")


def test_the_menu_puts_the_archive_s_first_guess_first_then_what_the_ink_supports():
    """Measured, not chosen: over the five hand-read pages `bench_menu.py` says
    the archive's own first suggestion is right for 24% of badly-read words —
    better than anything else at rank one — while the candidates built from
    the strokes are what lift the menu from 47 of 112 words to 58. So the
    archive speaks first, then the ink's readings that are names somebody has
    read, then the rest of the archive, then the ink's unknown readings."""
    from desembarque.gazetteer import Names, menu_for
    names = Names({"MARIA": 40, "MARQUES": 5, "MARIO": 2})
    got = menu_for("ELBARIA", names, limit=6)
    assert got[0]["name"] == "MARIA"
    assert {g["how"] for g in got} <= {"arquivo", "traço", "arquivo+traço"}


def test_a_candidate_from_the_ink_says_which_stroke_it_re_read():
    from desembarque.gazetteer import Names, menu_for
    got = menu_for("YOSE", Names({"JOSE": 10}), limit=10)
    ink = [g for g in got if g["how"] == "traço"]
    assert ink and all(g["why"] for g in ink), "a guess from the ink has to say why"


def test_the_two_sources_agreeing_is_said_once_and_in_the_better_place():
    """The archive says *José is a name these ships carried and this is close
    to it*; the strokes say *this ink supports José*. Both at once is the
    strongest thing the tool can say, and showing it twice would read as two
    guesses instead of one."""
    from desembarque.gazetteer import Names, menu_for
    got = menu_for("YOSE", Names({"JOSE": 10}), limit=10)
    jose = [g for g in got if g["name"] == "JOSE"]
    assert len(jose) == 1
    assert jose[0]["how"] == "arquivo+traço"
    assert "haste alta" in jose[0]["why"]


def test_the_menu_offers_a_reading_no_name_list_contains():
    """The archive has not read every name correctly yet, so a candidate that
    spells nothing known is still offered — below the ones that do."""
    from desembarque.gazetteer import Names, menu_for
    got = menu_for("POUTICELLI", Names({"MARIA": 3}), limit=30)
    assert any(g["name"] == "PONTICELLI" for g in got)


def test_the_menu_never_offers_the_word_that_is_already_on_screen():
    from desembarque.gazetteer import Names, menu_for
    assert all(g["name"] != "MARIA" for g in menu_for("MARIA", Names({"MARIA": 9})))
