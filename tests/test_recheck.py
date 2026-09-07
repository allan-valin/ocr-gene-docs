"""Which rows are worth a second look, in one place.

The reasons were written three times — the review screen's, the bench's, and
now the batch's, which has to decide what to hand a second recogniser before
any index exists. Three copies had already drifted: the bench knew about the
spoken-name lists and the screen did not. These tests hold the one copy.
"""
from desembarque.gazetteer import Names
from desembarque.recheck import CHECK_SCORE, flagged, why_check

ARCHIVE = Names({"JOSE": 143, "MARIA": 161, "CONTADORE": 9, "SILVA": 40})
SPOKEN = {"JUAN"}


def test_a_low_score_is_a_reason():
    row = {"name_raw": "JOSE", "conf": {"name": CHECK_SCORE - 0.1}}
    assert "score" in why_check(row, ARCHIVE)


def test_a_confident_reading_of_a_known_name_is_no_reason_at_all():
    row = {"name_raw": "JOSE SILVA", "conf": {"name": 0.99}}
    assert why_check(row, ARCHIVE) == []


def test_a_surname_inherited_from_a_position_is_a_reason():
    row = {"name_raw": "JOSE", "conf": {"name": 0.99}, "ditto_source": "position"}
    assert "inferido" in why_check(row, ARCHIVE)


def test_a_reading_that_resembles_no_name_is_a_reason():
    row = {"name_raw": "XQZKWV PLRTZ", "conf": {"name": 0.99}}
    assert "desconhecido" in why_check(row, ARCHIVE)


def test_a_reading_that_is_near_a_name_but_is_not_one_is_a_reason():
    row = {"name_raw": "YOSE", "conf": {"name": 0.99}}
    assert "quase" in why_check(row, ARCHIVE)


def test_two_names_run_into_one_word_is_a_reason():
    row = {"name_raw": "MarcelloNittoms", "conf": {"name": 0.99}}
    assert "colado" in why_check(row, ARCHIVE)


def test_the_spoken_lists_are_a_reason_only_when_they_are_given():
    row = {"name_raw": "TUAN", "conf": {"name": 0.99}}
    assert "quase-lista" not in why_check(row, ARCHIVE)
    assert "quase-lista" in why_check(row, ARCHIVE, spoken=SPOKEN)


def test_a_row_already_near_an_archive_name_is_not_flagged_twice():
    """`quase` and `quase-lista` are the same reason found in two lists."""
    row = {"name_raw": "YOSE", "conf": {"name": 0.99}}
    why = why_check(row, ARCHIVE, spoken=SPOKEN)
    assert "quase" in why and "quase-lista" not in why


def test_flagged_names_the_rows_of_a_record_worth_reading_again():
    record = {"rows": [
        {"n": 1, "page": 2, "name_raw": "JOSE SILVA", "conf": {"name": 0.99}},
        {"n": 2, "page": 2, "name_raw": "YOSE", "conf": {"name": 0.99}},
        {"n": 3, "page": 3, "name_raw": "MARIA", "conf": {"name": 0.1}},
    ]}
    assert flagged(record, ARCHIVE) == {(2, 2), (3, 3)}


def test_a_heading_is_not_a_row_anybody_reads_again():
    """The engine stores the heading line; it is not somebody's name."""
    record = {"rows": [
        {"n": 1, "page": 2, "name_raw": "XQZKWV", "conf": {"name": 0.1},
         "header": True},
    ]}
    assert flagged(record, ARCHIVE) == set()
