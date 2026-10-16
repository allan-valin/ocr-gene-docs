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
