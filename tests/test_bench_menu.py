"""The menu bench and the pairing under it.

The instrument comes with tests because every number in the reading-quality
plan is decided by it, and a bench that pairs the wrong row with the wrong
truth reports improvements that are not there. The pairing itself lives in
`desembarque.truthset`, because the check bench needs the same one.
"""
import runpy
from pathlib import Path

from desembarque import truthset as bench

ROOT = Path(__file__).resolve().parents[1]
menu_bench = runpy.run_path(str(ROOT / "scripts" / "bench_menu.py"))


def test_a_truth_page_is_paired_with_the_stored_rows_by_row_number():
    truth = {"page": 2, "first_row": 4, "names": ["Rossi Mario", "Rossi Ana"]}
    rows = [{"page": 2, "n": 3, "name_raw": "somebody else"},
            {"page": 2, "n": 4, "name_raw": "Rossi Wario"},
            {"page": 2, "n": 5, "name_raw": "Rossi Ana"},
            {"page": 3, "n": 4, "name_raw": "another page"}]
    got = bench.pairs(truth, rows)
    assert [(p["truth"], p["read"]) for p in got] == [
        ("Rossi Mario", "Rossi Wario"), ("Rossi Ana", "Rossi Ana")]
    assert got[0]["row"] is rows[1]


def test_a_truth_row_the_engine_never_read_is_not_counted_as_a_bad_reading():
    """A missing row is a recogniser question, not a menu question. It is
    left out so a bench run says how much of the page the menu ever saw."""
    truth = {"page": 2, "first_row": 1, "names": ["Rossi Mario", "Turino Ana"]}
    rows = [{"page": 2, "n": 1, "name_raw": "Rossi Wario"}]
    assert len(bench.pairs(truth, rows)) == 1


def test_words_are_aligned_by_position_when_the_counts_match():
    got = bench.word_pairs("Rossi Mario", "Rosri Wario")
    assert [(w["truth"], w["read"], w["i"]) for w in got] == [
        ("ROSSI", "ROSRI", 0), ("MARIO", "WARIO", 1)]


def test_a_word_read_correctly_is_still_returned_so_the_bench_can_skip_it():
    got = bench.word_pairs("Rossi Mario", "Rossi Wario")
    assert [w["read"] for w in got] == ["ROSSI", "WARIO"]


def test_a_merged_word_is_aligned_to_the_truth_it_covers():
    """`MorvettoFianciico` is one token where the page has two, and the menu
    has to be able to offer both. Alignment falls back to matching each truth
    token against the reading token that resembles it most."""
    got = bench.word_pairs("Morvetto Francisco", "MorvettoFianciico")
    assert [(w["truth"], w["read"], w["i"]) for w in got] == [
        ("MORVETTO", "MORVETTOFIANCIICO", 0),
        ("FRANCISCO", "MORVETTOFIANCIICO", 0)]


def test_the_rank_of_the_true_word_is_one_based_and_ignores_accents_and_case():
    assert bench.rank_of("José", ["FRE", "JOSE", "JORGE"]) == 2
    assert bench.rank_of("José", ["FRE", "JORGE"]) is None
    assert bench.rank_of("José", []) is None


def test_a_measurement_counts_recall_at_each_depth_over_the_bad_words_only():
    cases = [{"truth": "MARIA", "read": "MANIA", "i": 0, "row": {}},
             {"truth": "ROSSI", "read": "ROSSI", "i": 1, "row": {}}]

    def candidates(word, row, i):
        return ["NOISE", "MARIA"] if word == "MANIA" else []

    m = menu_bench["measure"](cases, candidates)
    assert m["words"] == 1                      # the correctly read word is not scored
    assert m["at"][1] == 0.0
    assert m["at"][3] == 1.0
    assert m["found"] == 1


def test_a_measurement_over_no_bad_words_reports_zeroes_rather_than_dividing_by_zero():
    m = menu_bench["measure"]([{"truth": "MARIA", "read": "MARIA", "i": 0, "row": {}}],
                         lambda w, r, i: [])
    assert m["words"] == 0 and m["at"][1] == 0.0


def test_the_engine_alternates_of_a_row_are_a_candidate_source():
    """`name_alts` runs parallel to the words of `name_raw`, and holds the
    other readings of that word only — never the one already on screen."""
    row = {"name_raw": "fore Gulerti", "name_alts": [["fose"], []]}
    assert menu_bench["alts_for"]("FORE", row, 0) == ["fose"]
    assert menu_bench["alts_for"]("GULERTI", row, 1) == []
    assert menu_bench["alts_for"]("ANYTHING", {}, 0) == []


def test_a_truth_page_may_name_the_rows_it_read_rather_than_run_from_the_first():
    """Somebody reading a scan writes down the rows they are sure of, which on
    a cursive page is not the first twenty-four in a row. A page that says
    which row each name belongs to is scored on exactly those rows."""
    truth = {"page": 2, "rows": {"1": "José Fernandes", "9": "Maria Sanchez"}}
    rows = [{"page": 2, "n": 1, "name_raw": "Yosé Fernandes"},
            {"page": 2, "n": 5, "name_raw": "Gayatana"},
            {"page": 2, "n": 9, "name_raw": "Mania Danchez"}]
    got = bench.pairs(truth, rows)
    assert [(p["truth"], p["read"]) for p in got] == [
        ("José Fernandes", "Yosé Fernandes"), ("Maria Sanchez", "Mania Danchez")]


# --- a run of hand-read names against the rows a page was cut into -----------
#
# Two things go wrong at once and each cure is the other's poison. The stored
# `first_row` goes stale — BS_ENT_014541-p2 says 4 because the comb that read
# it in July counted the header bands, and measured from the printing those
# passengers are rows one to six — so pairing on it labels every crop with the
# name three rows above. And a page whose middle rows carry no reading has gaps
# — BS_ENT_015061-p6 — so a single best-fit offset drifts past the first gap
# and labels every later crop with the name above it. Both were happening: the
# first to the bench, the second to the training set, which is worse, because a
# mislabelled pair teaches a recogniser the wrong name and no measurement of it
# says so.


def test_a_run_finds_its_place_when_the_stored_row_number_is_stale():
    got = bench.aligned(["Gudo Camtadome", "Pgmia,lamtadie", "bmike Meesoo"],
                        ["GUIDO CONTADORE", "EMMA CONTADORE", "EMILI MUESSO"])
    assert got == {0: "GUIDO CONTADORE", 1: "EMMA CONTADORE",
                   2: "EMILI MUESSO"}


def test_a_run_skips_the_rows_that_carry_no_reading_of_their_own():
    got = bench.aligned(["Palmira Ie Yesus", "Maria Yose de Yesus",
                         "", "Ignez Marqnes"],
                        ["Palmira de Jesus", "Maria Jose de Jesus",
                         "Albertina Jorge Ferreira", "Ignez Marques"])
    assert got[0] == "Palmira de Jesus"
    assert got[1] == "Maria Jose de Jesus"
    assert got[3] == "Ignez Marques", "the gap must not shift the rest"


def test_a_run_that_starts_below_the_header_is_not_pulled_up_to_it():
    got = bench.aligned(["Nome e Cognomes", "", "GUIDO Camtadore"],
                        ["GUIDO CONTADORE"])
    assert got == {2: "GUIDO CONTADORE"}


def test_nothing_to_align_is_nothing():
    assert bench.aligned([], ["A"]) == {}
    assert bench.aligned(["a"], []) == {}
