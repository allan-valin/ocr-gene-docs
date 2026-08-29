"""What a row says its name is, asked in one place.

T6: `surname` and `given` are a claim these forms do not support — the clerks
wrote the name in more than one order and the split was derived the wrong way
round often enough to matter. They stop being written here. But 660 records on
disk carry them, and the corpus is deliberately not re-read (see PROGRESS), so
every reader has to understand both shapes and only one of them is written.
"""


def test_the_score_of_a_name_read_today():
    from desembarque.rowfields import name_score

    assert name_score({"conf": {"name": 0.82}}) == 0.82


def test_the_score_of_a_name_read_before_the_key_was_renamed():
    """`conf` was keyed `surname`, and that key was never the surname's score:
    it is the score of the whole name strip, which is why it is renamed with
    the field. Records written before today still spell it the old way."""
    from desembarque.rowfields import name_score

    assert name_score({"conf": {"surname": 0.44}}) == 0.44


def test_the_new_key_wins_where_a_row_carries_both():
    from desembarque.rowfields import name_score

    assert name_score({"conf": {"name": 0.9, "surname": 0.1}}) == 0.9


def test_a_row_with_no_score_says_so_rather_than_scoring_zero():
    """Nothing read and read badly are different claims, and a row the engine
    never attempted must not sort above one it read with no confidence."""
    from desembarque.rowfields import name_score

    assert name_score({}) is None
    assert name_score({"conf": {}}) is None
    assert name_score(None) is None
