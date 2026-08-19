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
                           crop=lambda box: box)
    assert [r["n"] for r in rows] == [1, 2, 3]
    assert rows[0]["surname"] == "ROCA REBULLIDA" and rows[0]["given"] == "AMPARO"
    assert rows[0]["conf"]["surname"] == 0.94


def test_an_unread_row_is_null_not_invented():
    geo = Band([(0.1, 0.2), (0.2, 0.3)])
    rows = rows_from_bands(geo, (1000, 2000), lambda crops: [("", 0.0), ("X", 0.9)],
                           crop=lambda box: box)
    assert rows[0]["surname"] is None and rows[0]["given"] is None
    assert rows[0]["conf"]["surname"] == 0.0


def test_recogniser_returning_short_falls_back_to_null_rows():
    """A truncated result must not shift every later name up by one row."""
    geo = Band([(0.1, 0.2), (0.2, 0.3), (0.3, 0.4)])
    rows = rows_from_bands(geo, (1000, 2000), lambda crops: [("A B", 0.9)],
                           crop=lambda box: box)
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
