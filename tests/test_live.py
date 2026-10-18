"""The engine's progress on a document, as a page can watch it."""
import threading

from desembarque import live


def test_nothing_is_recorded_on_a_thread_that_watches_nothing():
    live.emit({"event": "bands", "page": 2, "bands": [[0.1, 0.2]]})
    assert live.get("x.pdf") is None


def test_the_bands_come_first_then_the_names_in_batches():
    live.watch("x.pdf")
    try:
        live.emit({"event": "bands", "page": 2, "bands": [(0.1, 0.2), (0.2, 0.3), (0.3, 0.4)],
                   "columns": [0.1, 0.4], "written": [0, 2]})
        got = live.get("x.pdf")
        assert got["page"] == 2 and got["total"] == 2 and got["done"] == 0
        assert [r["name_raw"] for r in got["rows"]] == ["", "", ""]
        live.emit({"event": "read", "bands": [(0, "ROCA AMPARO")]})
        got = live.get("x.pdf")
        assert got["rows"][0]["name_raw"] == "ROCA AMPARO" and got["done"] == 1 and got["at"] == 0
        live.emit({"event": "read", "bands": [(2, "VAZQUEZ JOSE")]})
        assert live.get("x.pdf")["at"] == 2
    finally:
        live.unwatch("x.pdf")
    assert live.get("x.pdf") is None


def test_each_thread_reports_on_its_own_document():
    seen = {}

    def read(name, text):
        live.watch(name)
        live.emit({"event": "bands", "page": 1, "bands": [(0.1, 0.2)]})
        live.emit({"event": "read", "bands": [(0, text)]})
        seen[name] = live.get(name)["rows"][0]["name_raw"]
        live.unwatch(name)

    ts = [threading.Thread(target=read, args=(f"d{i}.pdf", f"name {i}")) for i in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert seen == {f"d{i}.pdf": f"name {i}" for i in range(4)}


def test_a_document_reports_which_page_it_is_on_and_how_many_there_are():
    """Allan, 2026-10-16: five minutes with no sign of progress until a
    whole file was done. The folder index counts documents; the page the
    engine is on, of how many, is what moves in between — and it moves on
    a page with no table too, where no bands are ever cut."""
    live.watch("x.pdf", pages=9)
    try:
        live.emit({"event": "page", "page": 3})
        got = live.get("x.pdf")
        assert got["page"] == 3 and got["pages"] == 9
        assert got["bands"] == [] and got["rows"] == [] and got["done"] == 0
        live.emit({"event": "bands", "page": 3, "bands": [(0.1, 0.2)]})
        live.emit({"event": "read", "bands": [(0, "A")]})
        live.emit({"event": "page", "page": 4})
        got = live.get("x.pdf")
        assert got["page"] == 4 and got["rows"] == [] and got["done"] == 0
        [s] = live.summary()
        assert s["page_s"] is not None and s["page_s"] < 5
        assert {k: v for k, v in s.items() if k not in ("page_s", "phase", "second")} == {
            "file": "x.pdf", "page": 4, "pages": 9, "done": 0, "total": 0}
    finally:
        live.unwatch("x.pdf")
    assert live.summary() == []


def test_a_page_says_which_phase_it_is_in_and_the_times_are_kept():
    """The page bar was a clock against a fixed twenty seconds, and sat at
    the end while the Windows CPU took fifty. The phases are what the bar
    shows: `cutting` from the page event until the bands come, `reading`
    while the names are read, `second` while kraken reads the page's
    lines. Each page's seconds are kept, so the estimate shown is the one
    measured on this machine."""
    live.watch("x.pdf", pages=2)
    try:
        live.emit({"event": "page", "page": 1})
        assert live.get("x.pdf")["phase"] == "cutting"
        live.emit({"event": "bands", "page": 1, "bands": [(0.1, 0.2)]})
        assert live.get("x.pdf")["phase"] == "reading"
        live.emit({"event": "page", "page": 2})
        assert live.get("x.pdf")["phase"] == "cutting"
        live.emit({"event": "page_done", "page": 2, "seconds": 48.0})
        live.emit({"event": "second", "page": 1, "done": 0, "total": 1})
        got = live.get("x.pdf")
        assert got["phase"] == "second" and got["second"] == {"page": 1, "done": 0, "total": 1}
        [s] = live.summary()
        assert s["phase"] == "second" and s["second"]["total"] == 1
        live.emit({"event": "second_done", "page": 1, "seconds": 133.0})
        assert live.get("x.pdf")["second"]["done"] == 1
    finally:
        live.unwatch("x.pdf")
    t = live.timings()
    assert 48.0 in t["page"] and 133.0 in t["second"]
    assert live.estimate() is not None and live.estimate() >= 48.0


def test_the_estimate_is_a_page_s_median_engine_time_plus_the_second_reading_s():
    live.forget_timings()
    assert live.estimate() is None
    for s in (40.0, 48.0, 200.0):
        live.emit_timing("page", s)
    assert live.estimate() == 48.0, "the median, not the mean: one slow page is not the norm"
    for s in (130.0, 136.0):
        live.emit_timing("second", s)
    assert live.estimate() == 48.0 + 133.0
    live.forget_timings()
