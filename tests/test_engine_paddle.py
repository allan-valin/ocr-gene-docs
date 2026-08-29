"""The recogniser's output becomes rows, and the row-building is testable
without the model: recognition is injected, so what is under test is the part
that can silently ruin a transcription — which crop belongs to which row, and
what happens when the recogniser returns nothing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque.engine_paddle import rows_from_bands, split_name


class Band:
    """Minimal stand-in for the geometry a real page produces."""
    def __init__(self, bands, col=(0.1, 0.4), skew=0.0):
        self._bands = bands
        self._col = col
        self.skew = skew
        self.rows = bands

    def normalized_rows(self):
        return self._bands

    def name_column(self, index=0):
        return self._col


def test_each_band_becomes_one_row_in_order():
    geo = Band([(0.1, 0.2), (0.2, 0.3), (0.3, 0.4)])
    said = [("ROCA REBULLIDA AMPARO", 0.94), ("VAZQUEZ JOSE", 0.81), ("", 0.0)]
    rows = rows_from_bands(geo, (1000, 2000), lambda crops: said,
                           crop=lambda i, box: box)
    assert [r["n"] for r in rows] == [1, 2, 3]
    assert rows[0]["surname"] == "ROCA REBULLIDA" and rows[0]["given"] == "AMPARO"
    assert rows[0]["conf"]["surname"] == 0.94


def test_an_unread_row_is_null_not_invented():
    geo = Band([(0.1, 0.2), (0.2, 0.3)])
    rows = rows_from_bands(geo, (1000, 2000), lambda crops: [("", 0.0), ("X", 0.9)],
                           crop=lambda i, box: box)
    assert rows[0]["surname"] is None and rows[0]["given"] is None
    assert rows[0]["conf"]["surname"] == 0.0


def test_recogniser_returning_short_falls_back_to_null_rows():
    """A truncated result must not shift every later name up by one row."""
    geo = Band([(0.1, 0.2), (0.2, 0.3), (0.3, 0.4)])
    rows = rows_from_bands(geo, (1000, 2000), lambda crops: [("A B", 0.9)],
                           crop=lambda i, box: box)
    assert len(rows) == 3
    assert rows[1]["surname"] is None and rows[2]["surname"] is None


def test_split_name_keeps_compound_surnames_together():
    assert split_name("ROCA REBULLIDA AMPARO") == ("ROCA REBULLIDA", "AMPARO")
    assert split_name("VAZQUEZ JOSE") == ("VAZQUEZ", "JOSE")
    assert split_name("SOLO") == ("SOLO", "")
    assert split_name("") == (None, None)


def test_engine_reports_unavailable_rather_than_guessing(monkeypatch):
    from desembarque.engine_paddle import PaddleEngine
    eng = PaddleEngine()
    monkeypatch.setattr(eng, "_import", lambda: (_ for _ in ()).throw(ImportError("no paddle")))
    assert eng.available() is False
    res = eng.transcribe_page(Path("nope.png"), "list")
    assert res.rows == [] and res.error


def test_refine_trims_blank_paper_around_the_writing():
    from PIL import Image
    from desembarque.engine_paddle import refine
    im = Image.new("L", (400, 120), 245)
    for x in range(150, 260):
        for y in range(50, 78):
            im.putpixel((x, y), 20)
    out = refine(im)
    assert out.width < 200 and out.height < 60
    assert out.width > 100 and out.height > 20


def test_refine_leaves_a_blank_band_alone():
    from PIL import Image
    from desembarque.engine_paddle import refine
    im = Image.new("L", (400, 120), 245)
    assert refine(im).size == (400, 120)


def test_predictors_are_per_thread(monkeypatch):
    """Workers share one engine object; a predictor is not shared across
    threads, because paddle's is not thread-safe."""
    import threading
    from desembarque.engine_paddle import PaddleEngine
    eng = PaddleEngine()
    monkeypatch.setattr(eng, "_make_recogniser", lambda: object())
    seen = []
    def grab():
        seen.append(eng._recogniser())
    ts = [threading.Thread(target=grab) for _ in range(3)]
    for t in ts: t.start()
    for t in ts: t.join()
    assert len({id(x) for x in seen}) == 3
    assert eng._recogniser() is eng._recogniser()


def test_the_printed_column_heading_is_not_a_passenger():
    """The row comb includes the header band, so "Nomes e Cognomes" was being
    indexed as a person — and scoring 1.0 against anyone searching "nome"."""
    from desembarque.engine_paddle import rows_from_bands
    geo = Band([(0.1, 0.2), (0.2, 0.3)])
    said = [("Nomes e Cognomes", 1.0), ("JOSE MUESSO", 0.9)]
    rows = rows_from_bands(geo, (1000, 2000), lambda crops: said, crop=lambda i, b: b)
    assert rows[0]["header"] is True
    assert rows[1].get("header") is not True
    assert rows[0]["name_raw"] == "Nomes e Cognomes"   # recorded, not discarded


# --- the bilevel mask destroys faint pages -----------------------------------
#
# `page_image` prefers the PDF's embedded MRC ink mask, because geometry needs
# it: the mask yields nine column rules where a render yields three. But the
# mask is one bit deep, so faint strokes fall below its threshold and are gone
# before recognition ever runs. On BS_ENT_015741 p2 the recogniser read 7 of 39
# bands from the mask and 26 from a grayscale render -- the whole Bloch family
# was invisible.
#
# It is not a blanket win. Measured over ten pages the mask read 63.3% of bands
# and the render 68.2%: seven pages were unchanged, one gained nineteen rows,
# and one *lost* five. So the render is a fallback for pages the mask ruins,
# never a replacement, and the two are compared by what they actually read.

def rows_with(texts):
    """Rows shaped like the engine's, with the given name strings."""
    return [{"n": i + 1, "name_raw": t, "surname": t or None, "given": ""}
            for i, t in enumerate(texts)]


def test_read_ratio_is_the_share_of_rows_that_produced_text():
    from desembarque.engine_paddle import read_ratio
    assert read_ratio(rows_with(["ANNA", "", "JOSE", ""])) == 0.5
    assert read_ratio(rows_with(["", "", ""])) == 0.0
    assert read_ratio(rows_with(["ANNA"])) == 1.0


def test_read_ratio_ignores_the_printed_heading():
    """A page whose only legible line is its own column caption has read
    nothing, and must not score 1/1."""
    from desembarque.engine_paddle import read_ratio
    rows = rows_with(["Nomes e Cognomes", "", ""])
    rows[0]["header"] = True
    assert read_ratio(rows) == 0.0


def test_read_ratio_of_a_page_with_no_rows_is_zero():
    from desembarque.engine_paddle import read_ratio
    assert read_ratio([]) == 0.0


def test_a_well_read_page_is_not_retried():
    from desembarque.engine_paddle import wants_retry
    assert wants_retry(rows_with(["ANNA", "JOSE", "MARIA", ""]), floor=0.5) is False


def test_a_barely_read_page_is_retried():
    from desembarque.engine_paddle import wants_retry
    assert wants_retry(rows_with(["ANNA", "", "", ""]), floor=0.5) is True


def test_a_page_with_no_rows_is_not_retried():
    """No bands means no grid, which the render cannot fix -- retrying would
    only pay for a second recognition pass to get nothing again."""
    from desembarque.engine_paddle import wants_retry
    assert wants_retry([], floor=0.5) is False


def test_the_richer_reading_wins():
    from desembarque.engine_paddle import richer
    mask = rows_with(["", "L", "", ""])
    render = rows_with(["BLOCH ALEXANDRE", "BLOCH LINE", "", "BLOCH MADELON"])
    assert richer(mask, render) is render


def test_a_tie_keeps_the_mask():
    """The mask is the default and the better-tested path; a fallback has to
    earn the swap by reading more, not by reading the same."""
    from desembarque.engine_paddle import richer
    mask = rows_with(["ANNA", ""])
    render = rows_with(["ANNA", ""])
    assert richer(mask, render) is mask


def test_a_worse_fallback_is_discarded():
    """ENT_017053: the render read five rows fewer than the mask. Falling back
    blindly would have lost five people."""
    from desembarque.engine_paddle import richer
    mask = rows_with(["ANNA", "JOSE", "MARIA"])
    render = rows_with(["ANNA", "", ""])
    assert richer(mask, render) is mask


def test_fallback_is_not_attempted_when_the_page_reads_well():
    from desembarque.engine_paddle import with_fallback
    called = []
    rows = rows_with(["ANNA", "JOSE", "MARIA", ""])
    out, used = with_fallback(rows, lambda: called.append(1) or rows_with(["X"]))
    assert out is rows and used is False and called == []


def test_fallback_runs_and_wins_on_a_ruined_page():
    from desembarque.engine_paddle import with_fallback
    mask = rows_with(["", "L", "", ""])
    render = rows_with(["BLOCH ALEXANDRE", "BLOCH LINE", "", "BLOCH MADELON"])
    out, used = with_fallback(mask, lambda: render)
    assert out is render and used is True


def test_a_fallback_that_cannot_be_produced_leaves_the_page_alone():
    """No source PDF, or a render that fails: the mask reading still stands."""
    from desembarque.engine_paddle import with_fallback
    mask = rows_with(["", "", ""])
    out, used = with_fallback(mask, lambda: None)
    assert out is mask and used is False


def test_the_source_pdf_reaches_the_fallback(tmp_path, monkeypatch):
    """The engine is handed a page image, not a document, so the PDF has to be
    threaded through for the render to be producible at all. Without it the
    fallback silently never fires and a ruined page stays ruined."""
    from desembarque.engine_paddle import PaddleEngine
    eng = PaddleEngine()
    seen = {}
    monkeypatch.setattr(eng, "_render_rows",
                        lambda source, page, geo, size, workdir:
                            seen.update(source=source, page=page) or None)
    geo = Band([(0.1, 0.2), (0.2, 0.3)])
    rows = rows_with(["", ""])
    from desembarque.engine_paddle import with_fallback
    out, used = with_fallback(
        rows, lambda: eng._render_rows(tmp_path / "d.pdf", 2, geo, (10, 10), tmp_path))
    assert seen == {"source": tmp_path / "d.pdf", "page": 2}
    assert out is rows and used is False


def test_a_page_read_from_the_render_says_so(monkeypatch):
    """Which image a row came from changes how much to trust it, so it is
    recorded rather than inferred later."""
    from desembarque import engine_paddle as ep
    rows, used = ep.with_fallback(rows_with(["", "", ""]),
                                  lambda: rows_with(["ANNA", "JOSE", "MARIA"]))
    assert used is True
    assert [r["name_raw"] for r in rows] == ["ANNA", "JOSE", "MARIA"]


# --- oneDNN refuses the full-page pipeline -----------------------------------
#
# 167 of 168 indexed documents failed page 1 with
#   NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute
#     not support [pir::ArrayAttribute<pir::DoubleAttribute>]
# and the run reported success anyway. The row recogniser is fine with oneDNN;
# only the detection pipeline behind `read_page` trips on it. That path reads
# the archive cover card, which is what `identify()` uses -- which is why every
# stored record fell back to identifying itself by filename.
#
# The flag is not simply turned off, because oneDNN is worth having where it
# works. The pipeline is built once with it, and if that build or its first use
# raises, it is rebuilt without and the choice remembered for the page.

class FakePipeline:
    """Stands in for PaddleOCR: oneDNN builds happily and dies on use."""
    def __init__(self, mkldnn):
        self.mkldnn = mkldnn
        self.calls = 0

    def predict(self, path):
        self.calls += 1
        if self.mkldnn:
            raise NotImplementedError(
                "(Unimplemented) ConvertPirAttribute2RuntimeAttribute not support")
        return [type("R", (), {"json": {"res": {"rec_texts": ["ARQUIVO NACIONAL"]}}})()]


def test_onednn_is_tried_first():
    from desembarque.engine_paddle import PaddleEngine
    eng = PaddleEngine(mkldnn=True)
    built = []
    eng._build_page = lambda mkldnn: built.append(mkldnn) or FakePipeline(mkldnn)
    eng.read_page(Path("cover.png"))["text"]
    assert built[0] is True, "oneDNN is worth having where it works"


def test_a_pipeline_that_dies_on_use_is_rebuilt_without_onednn():
    """The failure is at predict, not at build: both pipelines construct."""
    from desembarque.engine_paddle import PaddleEngine
    eng = PaddleEngine(mkldnn=True)
    built = []
    eng._build_page = lambda mkldnn: built.append(mkldnn) or FakePipeline(mkldnn)
    text = eng.read_page(Path("cover.png"))["text"]
    assert built == [True, False]
    assert "ARQUIVO NACIONAL" in text


def test_the_fallback_is_remembered_rather_than_rediscovered():
    """Rebuilding costs seconds, and every page of every document would pay it
    again -- 167 of 168 documents took this path."""
    from desembarque.engine_paddle import PaddleEngine
    eng = PaddleEngine(mkldnn=True)
    built = []
    eng._build_page = lambda mkldnn: built.append(mkldnn) or FakePipeline(mkldnn)
    for _ in range(3):
        eng.read_page(Path("cover.png"))["text"]
    assert built == [True, False], "rebuilt once, not once per page"


def test_a_failure_that_is_not_onednn_still_raises():
    """Falling back must not turn every other fault into a silent empty page."""
    import pytest
    from desembarque.engine_paddle import PaddleEngine
    eng = PaddleEngine(mkldnn=False)

    class Broken:
        def predict(self, path):
            raise RuntimeError("no engine at all")

    eng._build_page = lambda mkldnn: Broken()
    with pytest.raises(RuntimeError):
        eng.read_page(Path("cover.png"))["text"]


# --- the line number is not part of the surname ------------------------------
#
# Where the Numero divider does not print clearly enough to be detected, the
# ordinal sits inside the name crop and arrives glued to the front of the name:
# 28.2% of indexed rows begin with a digit, and `split_name` then treats ".9" as
# part of the surname. Measured samples: ".9 tharia. Stanziola.",
# ".10 Amalia Stangiola.", "1I alfredode Oliviera bezar."

def test_a_leading_ordinal_is_taken_off_the_name():
    from desembarque.engine_paddle import strip_ordinal
    assert strip_ordinal(".9 tharia. Stanziola.") == "tharia. Stanziola."
    assert strip_ordinal(".10 Amalia Stangiola.") == "Amalia Stangiola."
    assert strip_ordinal("12 alicia S ihelan") == "alicia S ihelan"
    assert strip_ordinal("1. JOSE MUESSO") == "JOSE MUESSO"


def test_a_name_without_an_ordinal_is_untouched():
    from desembarque.engine_paddle import strip_ordinal
    assert strip_ordinal("ROCA REBULLIDA AMPARO") == "ROCA REBULLIDA AMPARO"
    assert strip_ordinal("") == ""


def test_a_cell_holding_only_a_number_keeps_nothing():
    """A row whose name column read as an ordinal and nothing else has no name
    in it. Returning the digits would file a passenger called "14"."""
    from desembarque.engine_paddle import strip_ordinal
    assert strip_ordinal("14") == ""
    assert strip_ordinal(" 7. ") == ""


def test_a_number_joined_to_a_letter_is_not_an_ordinal():
    """"2a" is 2ª — second class — and is data, not a line number. An ordinal
    is followed by space or punctuation, never by a letter."""
    from desembarque.engine_paddle import strip_ordinal
    assert strip_ordinal("2a CLASSE MARIA") == "2a CLASSE MARIA"
    assert strip_ordinal("Oliveira 2") == "Oliveira 2"


def test_a_long_number_is_not_an_ordinal():
    """Line numbers run to three digits at most on these forms; a longer run is
    something else and is left where it is."""
    from desembarque.engine_paddle import strip_ordinal
    assert strip_ordinal("12345 SILVA") == "12345 SILVA"


# --- line numbers mark where one list ends and the next begins ---------------
#
# Allan: the numbering can restart when the port changes, and a dossier may
# carry the same passengers twice — once in German with the surname first, then
# again in pt-BR with the surname last. So a restart is a real boundary, and the
# rows on either side of it must not be treated as one list.
#
# The numbering is clerk shorthand, not a plain sequence. On BS_ENT_017290 it
# runs 1-9, 10, 1-9, 20, 1-9, 30: only the tens are written in full.

def test_a_plain_sequence_is_one_list():
    from desembarque.engine_paddle import list_breaks
    assert list_breaks(["1", "2", "3", "4", "5"]) == []


def test_a_restart_begins_a_new_list():
    from desembarque.engine_paddle import list_breaks
    assert list_breaks(["1", "2", "3", "1", "2", "3"]) == [3]


def test_the_tens_shorthand_is_not_a_restart():
    """1-9, 10, 1-9, 20 is one list counted the way the clerk wrote it."""
    from desembarque.engine_paddle import list_breaks
    seq = ["1","2","3","4","5","6","7","8","9","10",
           "1","2","3","4","5","6","7","8","9","20"]
    assert list_breaks(seq) == []


def test_unreadable_numbers_do_not_invent_a_break():
    """Most ordinals read badly or not at all. A gap is not a boundary."""
    from desembarque.engine_paddle import list_breaks
    assert list_breaks(["1", "", "3", "", "", "6"]) == []
    assert list_breaks(["", "", ""]) == []


def test_a_restart_after_unreadable_rows_is_still_found():
    from desembarque.engine_paddle import list_breaks
    assert list_breaks(["8", "9", "", "1", "2"]) == [3]


def test_a_single_misread_number_is_not_a_break():
    """A stray low reading in the middle of a run is a misread, not a restart:
    the count picks up where it left off straight after."""
    from desembarque.engine_paddle import list_breaks
    assert list_breaks(["5", "6", "1", "8", "9"]) == []


# ---- reading a whole page, at a size that does not cost five minutes ---------

def test_a_whole_page_is_read_at_a_workable_size(tmp_path, monkeypatch):
    """Detection over a 5287x3817 scan takes about five minutes on this
    machine. Two of those per dossier is twenty-seven hours for the corpus,
    which is not a run anybody leaves going. The text wanted from a whole page
    is printed letterhead and a clerk's hand filling in a form — both large —
    so it is read from a copy scaled to something detection can cross."""
    from PIL import Image
    from desembarque.engine_paddle import PaddleEngine, TEXT_MAX_SIDE

    big = tmp_path / "page.jpg"
    Image.new("L", (5287, 3817), 255).save(big)
    seen = []

    eng = PaddleEngine()
    monkeypatch.setattr(eng, "_predict_page", lambda p: seen.append(Path(p)) or [])
    eng.read_page(big)

    assert seen, "nothing was read"
    with Image.open(seen[0]) as im:
        assert max(im.size) <= TEXT_MAX_SIDE, f"read at {im.size}"


def test_a_page_already_small_enough_is_not_copied(tmp_path, monkeypatch):
    """Rewriting a file to change nothing costs a disk write per page and loses
    a generation of JPEG on the way."""
    from PIL import Image
    from desembarque.engine_paddle import PaddleEngine

    small = tmp_path / "page.jpg"
    Image.new("L", (1200, 900), 255).save(small)
    seen = []
    eng = PaddleEngine()
    monkeypatch.setattr(eng, "_predict_page", lambda p: seen.append(Path(p)) or [])
    eng.read_page(small)
    assert seen == [small]


def test_the_printed_header_above_a_list_is_read_when_the_voyage_is_missing():
    """Almost every page two is a passenger list *with* a grid, and a page with
    a grid was never read as prose at all — so the printed header that states
    the ship, the port and the date was seen on no dossier that kept its list
    and lost its PARTE form. That is most of them: twelve documents indexed,
    twelve without a voyage."""
    from desembarque.engine_paddle import header_box

    class Geo:
        height, width = 4000, 3000
        row_edges = [1200.0, 1300.0, 1400.0]
        table_box = (100.0, 1150.0, 2900.0, 3900.0)

    box = header_box(Geo(), (3000, 4000))
    assert box is not None
    x0, y0, x1, y1 = box
    assert y0 == 0 and y1 <= 1200, "the header is what sits above the first row"
    assert (x0, x1) == (0, 3000)


def test_a_table_that_starts_at_the_top_has_no_header_to_read():
    """Some sheets are all table. Cropping a sliver and running detection over
    it costs the same twenty seconds and returns nothing."""
    from desembarque.engine_paddle import header_box

    class Geo:
        height, width = 4000, 3000
        row_edges = [40.0, 140.0]
        table_box = (100.0, 20.0, 2900.0, 3900.0)

    assert header_box(Geo(), (3000, 4000)) is None


def test_a_page_with_no_measured_table_offers_its_top_third():
    """Where the geometry found no rows the page is read whole anyway, so this
    only has to be right when there is a grid."""
    from desembarque.engine_paddle import header_box

    class Geo:
        height, width = 4000, 3000
        row_edges = []
        table_box = None

    box = header_box(Geo(), (3000, 4000))
    assert box and box[3] == 4000 // 3


# ---- both readings of a row, not just the winning one ------------------------

def test_the_losing_reading_is_kept_against_the_winning_one():
    """The mask and the render disagree exactly where the hand is hard. One of
    them won and the other was discarded, so a person correcting the row
    retyped a name the engine had already produced."""
    from desembarque.engine_paddle import attach_alternatives
    mask = [{"n": 1, "name_raw": "Nayomgo Cassaudii"}]
    render = [{"n": 1, "name_raw": "Raymundo Cassaudie"}]
    rows = attach_alternatives(mask, render)
    assert rows[0]["name_raw"] == "Nayomgo Cassaudii"
    assert rows[0]["name_alts"] == [["Raymundo"], ["Cassaudie"]]


def test_attaching_alternatives_does_not_change_which_reading_won():
    """Which reading wins is `with_fallback`'s question, settled by measurement
    across ten pages: the render is a second opinion, not an improvement to
    adopt wholesale. Taking it here would quietly overturn that."""
    from desembarque.engine_paddle import attach_alternatives
    mask = [{"n": 1, "name_raw": "GUIDO"}]
    render = [{"n": 1, "name_raw": "GUIDO CONTADORE ESQ"}]
    assert attach_alternatives(mask, render)[0]["name_raw"] == "GUIDO"


def test_a_row_the_two_readings_agree_on_carries_no_alternatives():
    """An empty list on every row is noise in a file somebody may open."""
    from desembarque.engine_paddle import attach_alternatives
    rows = attach_alternatives([{"n": 1, "name_raw": "JOSE MUESSO"}],
                               [{"n": 1, "name_raw": "JOSE MUESSO"}])
    assert "name_alts" not in rows[0]


def test_no_second_reading_leaves_the_rows_as_they_were():
    from desembarque.engine_paddle import attach_alternatives
    mask = [{"n": 1, "name_raw": "JOSE MUESSO"}]
    assert attach_alternatives(mask, None) is mask


def test_the_readings_are_paired_by_row_number_not_by_position():
    """A reading that skipped a band would otherwise offer every name below it
    as an alternative spelling of the name above."""
    from desembarque.engine_paddle import attach_alternatives
    mask = [{"n": 1, "name_raw": "GUIDO"}, {"n": 2, "name_raw": "EMMA"}]
    render = [{"n": 2, "name_raw": "EMMO"}]
    rows = attach_alternatives(mask, render)
    assert "name_alts" not in rows[0]
    assert rows[1]["name_alts"] == [["EMMO"]]


def test_an_empty_ruled_row_is_not_sent_to_the_recogniser():
    """A passenger list is printed with thirty rows and often carries three.
    Every blank one was being cropped, resized and handed to the recogniser to
    be told it says nothing — which is most of the corpus's reading time."""
    from PIL import Image, ImageDraw
    from desembarque.engine_paddle import rows_from_bands

    W, H = 400, 300
    page = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(page)
    for y in (0, 100, 200, 300):          # the ruled lines
        d.line([0, y, W, y], fill=0, width=1)
    d.text((20, 40), "MARTINEZ FRANCISCO", fill=0)   # only the first row is written on

    class Geo:
        skew = 0.0

        def normalized_rows(self):
            return [(0.0, 0.33), (0.34, 0.66), (0.67, 1.0)]

        def name_column(self, i=0):
            return (0.0, 1.0)

    seen = []

    def recognize(crops):
        seen.append(len(crops))
        return [("MARTINEZ FRANCISCO", 0.9)] * len(crops)

    rows = rows_from_bands(Geo(), (W, H), recognize,
                           lambda i, box: page.crop(box))
    assert len(rows) == 3, "an empty row is still a row"
    assert seen == [1], f"the recogniser was handed {seen} crops, not one"
    assert rows[0]["name_raw"] and rows[1]["name_raw"] == ""


# --- what the carried columns are for, and what they are not -----------------
#
# A passenger list runs to many pages of the same printed sheet, and the columns
# found on one page are carried to the next. It is tempting to let them save the
# search for a table altogether — a detection pass and a recogniser batch per
# page. Measured on OL.PRJ.16326 that reads 20% faster and loses a quarter of
# the names: the pages of that dossier do print their own headings, and the
# rules under the carried columns account for 14 rows of a page whose printing
# accounts for 164. The saving that is safe is already here — a page that finds
# no table of its own falls back to the carried columns before it pays for the
# 2000 px detection — and the order is the whole point.

class Detects:
    """An engine with the paddle parts replaced by counters."""

    def __init__(self, tmp_path, boxes=None):
        from PIL import Image
        from desembarque.engine_paddle import PaddleEngine
        from desembarque.tablegrid import TableGeometry
        self.page = tmp_path / "p.png"
        Image.new("L", (40, 60), 255).save(self.page)
        self.sides = []
        eng = PaddleEngine()
        eng._readable_copy = lambda image: self.page
        eng._detect = lambda image, side=None: (self.sides.append(side) or
                                                (boxes if boxes is not None else
                                                 [{"x0": 1.0, "y0": 1.0,
                                                   "x1": 9.0, "y1": 5.0}]))
        eng._read_boxes = lambda image, boxes: []
        geo = TableGeometry(40, 60, [(float(i), i + 1.0) for i in range(8)],
                            (5.0, 30.0), None, 0.0)
        geo.rows_from = "rules"
        eng._ruled_rows = lambda image, w, h, col: geo
        self.eng, self.geo = eng, geo


def test_carried_columns_save_the_expensive_detection(tmp_path):
    """A page that prints no headings of its own is measured from the columns
    the dossier already gave up, rather than from a second detection at 2000 px
    that will not find headings that are not there."""
    d = Detects(tmp_path)
    found = d.eng._printed_table(d.page, hint={"name": (5.0, 30.0), "ordinal": None})
    assert found is d.geo
    assert d.sides == [None], "the 2000 px detection ran when the columns were known"


def test_a_page_with_no_columns_to_carry_still_pays_for_the_search(tmp_path):
    d = Detects(tmp_path)
    d.eng._ruled_rows = lambda image, w, h, col: None
    d.eng._printed_table(d.page)
    assert d.sides == [None, 2000]


def test_the_stored_geometry_carries_every_column_the_page_measured():
    """The name column's edges have been stored since the beginning; the eight
    beside it were measured off the same heading line and thrown away, so
    nothing downstream could read a cell it did not have. Stored under its own
    key, so a record written before this still loads."""
    from desembarque.engine_paddle import stored_geometry

    class Geo:
        skew = 0.0
        def normalized_rows(self): return [(0.1, 0.2)]
        def normalized_cols(self): return [0.05, 0.35]
        def normalized_columns(self):
            return {"nome": (0.05, 0.35), "idade": (0.44, 0.49)}

    got = stored_geometry(Geo(), measured_by="printing", read_from="mask")
    assert got["columns"] == [0.05, 0.35], "the old key keeps its old meaning"
    assert got["all_columns"]["idade"] == (0.44, 0.49)

    class Older:
        skew = 0.0
        def normalized_rows(self): return [(0.1, 0.2)]
        def normalized_cols(self): return [0.05, 0.35]

    assert "all_columns" not in stored_geometry(Older(), measured_by="rules",
                                                read_from="mask")


def test_a_column_is_read_band_by_band_like_the_name_is():
    """The same shape as `rows_from_bands`, and for the same reason: a short
    result from the recogniser pads with nulls rather than shifting every later
    row up one, which is a silent corruption nobody would see."""
    from desembarque.engine_paddle import cells_from_bands

    class Geo:
        def normalized_rows(self): return [(0.10, 0.14), (0.15, 0.19), (0.20, 0.24)]
        def normalized_columns(self): return {"nome": (0.05, 0.35), "idade": (0.44, 0.49)}

    seen = []
    def crop(i, box):
        seen.append((i, box))
        return f"crop{i}"
    got = cells_from_bands(Geo(), (1000, 2000), "idade",
                           lambda crops: [("23", 0.9), ("37", 0.8)], crop)
    assert got == [{"n": 1, "text": "23", "conf": 0.9},
                   {"n": 2, "text": "37", "conf": 0.8},
                   {"n": 3, "text": "", "conf": 0.0}]
    # cropped inside the column the page measured, not the whole width
    assert all(430 <= box[0] and box[2] <= 500 for _i, box in seen)


def test_a_column_the_page_never_measured_is_not_invented():
    from desembarque.engine_paddle import cells_from_bands

    class Geo:
        def normalized_rows(self): return [(0.1, 0.2)]
        def normalized_columns(self): return {"nome": (0.05, 0.35)}

    assert cells_from_bands(Geo(), (1000, 2000), "idade",
                            lambda crops: [("23", 0.9)], lambda i, b: b) == []


def test_a_band_too_short_to_hold_writing_is_skipped_and_still_numbered():
    """The same rule the name column follows, so a row number means the same
    thing in both and a cell can be put beside the name it belongs to."""
    from desembarque.engine_paddle import cells_from_bands

    class Geo:
        # a band at the very top of the sheet, too shallow to hold writing
        # even with the padding the crops carry
        def normalized_rows(self): return [(0.0, 0.0), (0.15, 0.19)]
        def normalized_columns(self): return {"nome": (0.05, 0.35), "idade": (0.44, 0.49)}

    got = cells_from_bands(Geo(), (1000, 2000), "idade",
                           lambda crops: [("37", 0.8)], lambda i, b: f"c{i}")
    assert [c["n"] for c in got] == [1, 2]
    assert got[0] == {"n": 1, "text": "", "conf": 0.0}
    assert got[1]["text"] == "37"


def test_a_cell_is_cut_at_the_band_and_not_padded_out_onto_the_rule():
    """A name is 300 px wide on the full-resolution page and its crop is padded
    out by `PAD_PX` to catch a descender. A cell of *Idade* is 98 px wide, with
    a printed rule at each edge and the band's own rule under the figures, so
    the same padding hands the recogniser three lines around two digits — which
    is what it reads back: `一`, `_`, `11`, `十`. Measured over the sweep on
    BS.ENT.017397 p2, cutting at the band exactly reads best in every column."""
    from desembarque.engine_paddle import cells_from_bands

    class Geo:
        def normalized_rows(self): return [(0.10, 0.14), (0.15, 0.19)]
        def normalized_columns(self): return {"nome": (0.05, 0.35),
                                              "idade": (0.40, 0.50)}

    seen = []
    got = cells_from_bands(Geo(), (1000, 2000), "idade",
                           lambda crops: [("23", 0.9), ("37", 0.8)],
                           lambda i, box: seen.append(box) or f"c{i}")
    assert [c["text"] for c in got] == ["23", "37"]
    assert seen[0] == (400, 200, 500, 280), seen[0]


def test_a_cell_can_be_trimmed_off_its_rules_when_asked():
    """The knob the bench swept, kept because it is what will sweep a cursive
    page: the trim is a margin off each edge, never a second column."""
    from desembarque.engine_paddle import cells_from_bands

    class Geo:
        def normalized_rows(self): return [(0.10, 0.14)]
        def normalized_columns(self): return {"nome": (0.05, 0.35),
                                              "idade": (0.40, 0.50)}

    seen = []
    cells_from_bands(Geo(), (1000, 2000), "idade",
                     lambda crops: [("23", 0.9)],
                     lambda i, box: seen.append(box) or "c", inset=(0.10, 0.10))
    x0, y0, x1, y1 = seen[0]
    assert (x0, x1) == (410, 490) and (y0, y1) == (208, 272), seen[0]


def test_an_empty_cell_is_not_handed_to_the_recogniser():
    """The rule the name column has had since the rows were cut from the comb,
    and it matters more here: a page is forty bands by eight columns, most of
    the cells are blank paper between two printed rules, and reading one costs
    what reading a name costs. A blank cell read anyway comes back `一` or `1`
    — the rules — which is a wrong value where there was no writing."""
    from PIL import Image, ImageDraw
    from desembarque.engine_paddle import cells_from_bands

    class Geo:
        def normalized_rows(self): return [(0.10, 0.14), (0.15, 0.19),
                                           (0.20, 0.24)]
        def normalized_columns(self): return {"nome": (0.05, 0.35),
                                              "idade": (0.40, 0.50)}

    written = Image.new("L", (100, 80), 255)
    ImageDraw.Draw(written).text((20, 20), "23", fill=0)
    ImageDraw.Draw(written).rectangle((20, 20, 60, 60), outline=0, width=6)
    blank = Image.new("L", (100, 80), 255)
    # the printed rule at each edge of the cell, which is not writing
    ImageDraw.Draw(blank).line((1, 0, 1, 80), fill=0, width=2)
    ImageDraw.Draw(blank).line((98, 0, 98, 80), fill=0, width=2)

    handed = []

    def recognize(crops):
        handed.extend(crops)
        return [("23", 0.9)] * len(crops)

    got = cells_from_bands(Geo(), (1000, 2000), "idade", recognize,
                           lambda i, box: written if i == 1 else blank)
    assert len(handed) == 1, "only the cell somebody wrote in"
    assert [c["text"] for c in got] == ["", "23", ""]
    assert [c["n"] for c in got] == [1, 2, 3]


def test_a_read_cell_is_put_beside_the_row_and_never_in_the_typed_field():
    """Every non-name value in this corpus was typed by a person — the engine
    has never written one — and the review screen says so on the page. So a
    cell the engine reads goes under `cells`, with what it read, what it was
    snapped to and how sure both were; `nationality`, `occupation` and the rest
    stay the fields a person types into, and stay empty until one does."""
    from desembarque.engine_paddle import attach_cells
    from desembarque.vocab import Vocabulary

    rows = [{"n": 1, "name_raw": "Alfieri"}, {"n": 2, "name_raw": "Santos"}]
    cells = {"nacionalidade": [{"n": 1, "text": "SEAGNOLA", "conf": 0.4},
                               {"n": 2, "text": "", "conf": 0.0}],
             "estado": [{"n": 1, "text": "cau", "conf": 0.3},
                        {"n": 2, "text": "", "conf": 0.0}]}
    voc = Vocabulary({"nacionalidade": ["ESPANHOLA"], "estado": ["CASADO"]},
                     floors={"nacionalidade": 0.62, "estado": 0.55})
    got = attach_cells(rows, cells, voc)

    assert got[0]["cells"]["nacionalidade"]["text"] == "SEAGNOLA"
    assert got[0]["cells"]["nacionalidade"]["value"] == "ESPANHOLA"
    assert got[0]["cells"]["estado"]["value"] == "CASADO"
    assert "nationality" not in got[0] and "status" not in got[0]
    # a cell nobody wrote in is not a cell
    assert "cells" not in got[1] or got[1]["cells"] == {}
    # and the rows themselves are not rewritten
    assert got[0]["name_raw"] == "Alfieri"


def test_a_column_that_snaps_to_nothing_still_keeps_what_was_read():
    """The reading is the evidence. A cell that reaches no word on the list is
    a cell somebody has to look at, not a cell to throw away."""
    from desembarque.engine_paddle import attach_cells
    from desembarque.vocab import Vocabulary

    rows = [{"n": 1}]
    cells = {"nacionalidade": [{"n": 1, "text": "LNE ARE", "conf": 0.2}]}
    got = attach_cells(rows, cells, Vocabulary({"nacionalidade": ["ESPANHOLA"]}))
    cell = got[0]["cells"]["nacionalidade"]
    assert cell["text"] == "LNE ARE" and "value" not in cell


def test_the_other_columns_are_not_read_unless_they_are_asked_for():
    """A page is 31 bands by 8 columns and the recogniser is about twenty
    seconds a column, against the eighty seconds a page costs now. Reading them
    all doubles a corpus pass that already takes 34 hours, so which columns to
    read is a decision somebody takes, not a default that arrives with an
    upgrade."""
    from desembarque.engine_paddle import PaddleEngine, READABLE_COLUMNS
    assert PaddleEngine().columns == ()
    assert PaddleEngine(columns=READABLE_COLUMNS).columns == (
        "nacionalidade", "estado", "profissao")


def test_a_faint_page_is_lifted_before_it_is_given_up_on():
    """The scans are grey ink on grey paper and a few of them are faint enough
    that detection finds nothing to cross: OL.PRJ.17851 p2, which the archive
    itself stamped *ORIGINAL ILEGÍVEL*, came back with 32 boxes and no rows at
    all. Equalising the page — spreading its histogram, not stretching its ends
    — puts 29 rows on it. Stretching the black and white points does not: these
    scans already use their range end to end, which is why `autocontrast` and a
    2nd/98th-percentile stretch both move the box count by one."""
    from PIL import Image
    from desembarque.engine_paddle import lift
    import numpy as np

    # grey ink on grey paper, using a third of the range
    faint = Image.fromarray(
        np.clip(np.random.default_rng(0).normal(150, 8, (60, 200)), 120, 180)
        .astype("uint8"), "L")
    got = lift(faint)
    assert got.size == faint.size
    before = np.asarray(faint, dtype=float)
    after = np.asarray(got, dtype=float)
    assert after.std() > 2 * before.std(), (before.std(), after.std())


def test_lifting_a_page_that_cannot_be_lifted_gives_the_page_back():
    """A blank crop, a page already black and white: nothing to spread, and an
    exception here would lose a page that reads perfectly well as it is."""
    from PIL import Image
    from desembarque.engine_paddle import lift
    flat = Image.new("L", (40, 10), 255)
    assert lift(flat).size == (40, 10)
    assert lift(None) is None
