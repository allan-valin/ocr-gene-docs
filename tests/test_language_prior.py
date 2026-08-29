"""The language of the hand (T11, §7 of the reading-quality plan).

The nationality column says *ITALIANA* on one row and *ESPANHOLA* on the next,
so the prior is per row and never per page. It re-ranks the menu a reader opens
on a badly-read word: an Italian passenger's mangled given name is compared
with Italian names first.

It never filters. Half these families carry a Spanish surname on an Italian
passport, and a menu that hid the right name because the nationality disagreed
would be worse than no prior at all.
"""


def test_a_nationality_names_the_language_it_is_written_in():
    from desembarque.vocab import language_for

    assert language_for("ITALIANA") == "it"
    assert language_for("ESPANHOL") == "es"
    assert language_for("BRASILEIRA") == "pt"
    assert language_for("PORTUGUEZ") == "pt"


def test_the_spanish_speaking_republics_are_read_as_spanish():
    """A passenger boarding at Buenos Aires and writing ARGENTINO carries a
    Spanish name, and these lists print a dozen such nationalities."""
    from desembarque.vocab import language_for

    assert language_for("ARGENTINO") == "es"
    assert language_for("URUGUAYA") == "es"


def test_a_nationality_with_no_list_behind_it_gets_no_prior():
    """The file speaks for Italian, Spanish, Portuguese, the Levantine names
    these lists spell in Portuguese, and nothing else. A Japanese or Polish
    passenger is read with the menu the rules already build."""
    from desembarque.vocab import language_for

    assert language_for("JAPONEZ") is None
    assert language_for("POLACA") is None
    assert language_for("") is None
    assert language_for(None) is None


def test_a_reading_that_was_never_snapped_names_no_language():
    """The prior is taken from the snapped word, not the reading: `LASIERCL`
    is not a nationality and must not be matched against one."""
    from desembarque.vocab import language_for

    assert language_for("LASIERCL") is None


def test_the_names_of_one_language_can_be_asked_for():
    from desembarque.gazetteer import names_by_language
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    by = names_by_language(ROOT / "data" / "language_names.json")
    assert "GIUSEPPE" in by["it"] and "GIUSEPPE" not in by["pt"]
    assert "JOAO" in by["pt"] and "JOAO" not in by["it"]
    # the overlap is real and is kept
    assert "MARIA" in by["it"] and "MARIA" in by["es"] and "MARIA" in by["pt"]


def test_a_missing_file_leaves_every_language_empty_rather_than_failing():
    from desembarque.gazetteer import names_by_language

    assert names_by_language("/nonexistent/language_names.json") == {}


def _names(counts):
    from desembarque.gazetteer import Names
    return Names(counts)


def test_the_menu_puts_the_row_s_own_language_first():
    """`Guseppe` on a row whose nationality reads ITALIANA: the menu offers the
    same candidates, with the Italian one ahead of the others."""
    from desembarque.gazetteer import menu_for

    names = _names({"MARINO": 5, "MARTINS": 40, "MARINS": 30})
    plain = [g["name"] for g in menu_for("MARIN", names)]
    italian = [g["name"] for g in menu_for("MARIN", names,
                                           language_names={"MARINO"})]
    assert set(plain) == set(italian), "the prior orders the menu, never filters it"
    assert plain[0] == "MARINS" and italian[0] == "MARINO"


def test_a_name_the_language_does_not_use_is_still_offered():
    """Half these families carry a Spanish surname on an Italian passport. A
    menu that dropped the right name because the nationality disagreed would be
    worse than no prior at all."""
    from desembarque.gazetteer import menu_for

    names = _names({"MARINO": 5, "MARTINS": 40, "MARINS": 30})
    got = [g["name"] for g in menu_for("MARIN", names, language_names={"MARINO"})]
    assert "MARINS" in got and "MARTINS" in got


def test_a_row_with_no_language_gets_the_menu_the_rules_build():
    from desembarque.gazetteer import menu_for

    names = _names({"MARINO": 5, "MARTINS": 40, "MARINS": 30})
    assert ([g["name"] for g in menu_for("MARIN", names, language_names=None)]
            == [g["name"] for g in menu_for("MARIN", names)])


def test_a_candidate_lifted_by_the_language_says_so():
    """Every guess in this menu says where it came from, and a re-ranking is
    something the reader is entitled to see."""
    from desembarque.gazetteer import menu_for

    names = _names({"MARINO": 5, "MARTINS": 40, "MARINS": 30})
    got = menu_for("MARIN", names, language_names={"MARINO"})
    lifted = next(g for g in got if g["name"] == "MARINO")
    assert lifted.get("language") is True
    assert "língua" in lifted["why"] or "lingua" in lifted["why"]


# --- through the endpoint the review screen actually calls -------------------

def test_the_menu_endpoint_takes_the_row_s_nationality():
    """The review screen opens the menu on a word of one row, and that row's
    nationality is what says which language to look in first. Passed as the
    snapped value: the reading `LASIERCL` names no language."""
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
    import serve

    assert serve.language_names_for("ITALIANA")
    assert "GIUSEPPE" in serve.language_names_for("ITALIANA")
    assert serve.language_names_for("JAPONEZ") is None
    assert serve.language_names_for(None) is None
    assert serve.language_names_for("LASIERCL") is None
