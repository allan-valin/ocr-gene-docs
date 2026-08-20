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
# only the detection pipeline behind `_page_text` trips on it. That path reads
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
    eng._page_text(Path("cover.png"))
    assert built[0] is True, "oneDNN is worth having where it works"


def test_a_pipeline_that_dies_on_use_is_rebuilt_without_onednn():
    """The failure is at predict, not at build: both pipelines construct."""
    from desembarque.engine_paddle import PaddleEngine
    eng = PaddleEngine(mkldnn=True)
    built = []
    eng._build_page = lambda mkldnn: built.append(mkldnn) or FakePipeline(mkldnn)
    text = eng._page_text(Path("cover.png"))
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
        eng._page_text(Path("cover.png"))
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
        eng._page_text(Path("cover.png"))


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
    eng._page_text(big)

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
    eng._page_text(small)
    assert seen == [small]
