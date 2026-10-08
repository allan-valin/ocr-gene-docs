"""The bands a reader can see on the sheet, and where their typing lands.

Measured off BS.ENT.016317 p4 as Allan read it on 2026-10-07: 42 engine bands,
three of them slivers under the band below, 39 rows typed, and the 32nd typed
row is the engine's 35th band.
"""
from desembarque.sheetbands import (heading_offset, positional_map,
                                    representative_bands, visible_bands)

# evenly cut bands, 0.024 tall, overlapping their neighbours by a third as the
# engine's do
EVEN = [(0.10 + i * 0.016, 0.10 + i * 0.016 + 0.024) for i in range(6)]


def test_evenly_cut_bands_are_all_visible():
    assert visible_bands(EVEN) == [1, 2, 3, 4, 5, 6]


def test_a_band_almost_under_the_next_one_is_a_sliver():
    # the engine's bands 3 and 4 on 016317 p4: 3 shows 0.0056 of its 0.0276
    rows = [(0.2590, 0.2890), (0.2786, 0.3060), (0.2949, 0.3225),
            (0.3005, 0.3274), (0.3170, 0.3436), (0.3350, 0.3599)]
    assert visible_bands(rows) == [1, 2, 4, 5, 6]


def test_a_band_half_shown_is_still_a_row():
    # band 35 of the same page: 0.012 shown of a 0.024 median, and Allan read it
    rows = [(0.7910, 0.8149), (0.8060, 0.8311), (0.8180, 0.8500),
            (0.8420, 0.8645)]
    assert visible_bands(rows) == [1, 2, 3, 4]


def test_the_last_band_is_judged_by_its_own_height():
    assert visible_bands(EVEN[:2] + [(0.20, 0.224)]) == [1, 2, 3]


def test_no_rows_no_bands():
    assert visible_bands([]) == []


class TestHeadingOffset:
    def test_a_typed_page_counts_its_heading_and_the_blank_under_it(self):
        assert heading_offset(["Noie e Cognomes", "", "MARIASZABO"]) == 2

    def test_a_heading_read_in_capitals(self):
        assert heading_offset(["NOME E COGNOMES", "", "Edward Weigall"]) == 2

    def test_a_page_whose_first_band_is_a_name_has_no_heading(self):
        assert heading_offset(["Marmol Adela", "2Munist Pedro"]) == 0

    def test_an_unread_first_row_on_a_cursive_page_is_not_a_heading(self):
        assert heading_offset(["", "", "adm"]) == 0

    def test_a_heading_with_nothing_blank_under_it(self):
        assert heading_offset(["nome e Cognomes", "JULIA HUNT JONES"]) == 1


ROWS = [(0.2590, 0.2890), (0.2786, 0.3060), (0.2949, 0.3225),
        (0.3005, 0.3274), (0.3170, 0.3436)]


class TestRepresentativeBands:
    def test_a_visible_band_that_read_nothing_is_numbered_by_its_hidden_twin(self):
        texts = {1: "Fousae", 2: "vogcti", 3: "oase1lasto", 4: "", 5: ""}
        assert representative_bands(ROWS, texts) == [1, 2, 3, 5]

    def test_a_visible_band_with_a_reading_keeps_its_own_number(self):
        texts = {1: "Fousae", 2: "vogcti", 3: "oase1lasto", 4: "Fortazel", 5: ""}
        assert representative_bands(ROWS, texts) == [1, 2, 4, 5]


class TestPositionalMap:
    def test_boxes_land_on_the_rows_in_order_by_the_band_that_can_be_scored(self):
        texts = {1: "Fousae", 2: "vogcti", 3: "oase1lasto", 4: "", 5: ""}
        assert positional_map([1, 2, 3, 4], ROWS, texts) == \
            {1: 1, 2: 2, 3: 3, 4: 5}

    def test_the_heading_is_skipped_first(self):
        texts = {1: "Nome e Cognomes", 2: "", 3: "A", 4: "B", 5: "C"}
        assert positional_map([1, 2, 3], EVEN[:5], texts) == {1: 3, 2: 4, 3: 5}

    def test_a_box_past_the_last_band_is_lost_not_mislabelled(self):
        texts = {1: "Nome", 2: "", 3: "A", 4: "B", 5: "C"}
        assert positional_map([3, 4], EVEN[:5], texts) == {3: 5, 4: None}


from desembarque.sheetbands import align_by_text


class TestAlignByText:
    ENGINE = [(1, "Nome e Cognomes"), (2, ""), (3, "JON GULACBI"),
              (4, "ROZAKLIA GULACSI"), (5, "ANAGULACSI"), (6, "HAJNALIA GULACSI"),
              (7, "KAROL GULAOSI")]

    def test_a_typed_page_is_aligned_by_what_the_engine_read(self):
        mine = [(1, "Jon Gulacsi"), (2, "Rozaklia Gulacsi"), (3, "Ana Gulacsi"),
                (4, "Hajnalia Gulacsi"), (5, "Karol Gulasci")]
        assert align_by_text(mine, self.ENGINE) == {1: 3, 2: 4, 3: 5, 4: 6, 5: 7}

    def test_a_row_the_engine_never_cut_is_dropped_not_shifted(self):
        # the reader has a row between Jon and Rozaklia that no band carries
        mine = [(1, "Jon Gulacsi"), (2, "Hajnalia Gulacsi"), (3, "Rozaklia Gulacsi"),
                (4, "Ana Gulacsi"), (5, "Hajnalia Gulacsi"), (6, "Karol Gulasci")]
        got = align_by_text(mine, self.ENGINE)
        assert got == {1: 3, 2: None, 3: 4, 4: 5, 5: 6, 6: 7}

    def test_an_empty_typed_row_pairs_with_nothing_in_particular(self):
        mine = [(1, "Jon Gulacsi"), (2, ""), (3, "Rozaklia Gulacsi")]
        got = align_by_text(mine, self.ENGINE)
        assert got[1] == 3 and got[3] == 4
