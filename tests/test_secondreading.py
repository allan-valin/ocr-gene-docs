"""The kraken second reading runs per document at index time, so an install
made from the launcher reads cursive pages the way the corpus on Allan's
machine is read, instead of showing the engine's noise alone."""
from pathlib import Path

from desembarque import secondreading as sr


def row(page, n, name, conf):
    return {"page": page, "n": n, "name_raw": name, "conf": {"name": conf}}


def record(typed_conf=0.95, cursive_conf=0.40):
    rows = ([row(2, i, f"Typed {i}", typed_conf) for i in range(1, 6)]
            + [row(3, i, f"xyzzy {i}", cursive_conf) for i in range(1, 6)])
    bands = [[0.1 * i, 0.1 * i + 0.09] for i in range(1, 6)]
    return {"rows": rows,
            "pages": [{"n": 1, "kind": "cover"},
                      {"n": 2, "kind": "list", "geometry": {"columns": [0.1, 0.4], "rows": bands}},
                      {"n": 3, "kind": "list", "geometry": {"columns": [0.1, 0.4], "rows": bands}}]}


def line(y0, y1, text, x0=0.12, x1=0.38):
    return {"x0": x0, "x1": x1, "y0": y0, "y1": y1, "text": text, "cuts": []}


def test_only_the_handwritten_pages_are_read():
    assert sr.pages_to_read(record()) == [3]


def test_a_page_without_a_grid_has_nothing_to_put_lines_on():
    rec = record()
    rec["pages"][2]["geometry"] = {}
    assert sr.pages_to_read(rec) == []


def test_the_lines_land_on_the_rows_as_a_second_reading():
    seen = []

    def read(image):
        seen.append(image)
        return [line(0.1 * i, 0.1 * i + 0.08, f"Joseph Brooks {i}") for i in range(1, 6)]

    out, n = sr.read_record(record(), {2: Path("p2.png"), 3: Path("p3.png")}, read=read)
    assert seen == [Path("p3.png")], "the typed page is the engine's"
    assert n == 5
    got = {r["n"]: r.get("second_read") for r in out["rows"] if r["page"] == 3}
    assert got[1] == {"model": sr.MODEL_TAG, "text": "Joseph Brooks 1"}
    assert all(r.get("second_read") is None for r in out["rows"] if r["page"] == 2)
    assert out["second_reading"]["pages"] == [3]


def test_a_row_a_person_typed_keeps_their_word():
    rec = record()
    rec["rows"][5]["edits"] = [{"field": "name_raw", "by": "allan"}]
    out, n = sr.read_record(rec, {3: Path("p3.png")},
                            read=lambda _: [line(0.1, 0.18, "machine")])
    assert out["rows"][5].get("second_read") is None


def test_a_page_kraken_cannot_read_keeps_the_engine_rows_and_says_so():
    def read(image):
        raise RuntimeError("out of memory")

    out, n = sr.read_record(record(), {3: Path("p3.png")}, read=read)
    assert n == 0
    assert len(out["rows"]) == 10
    assert out["second_reading"]["failed"][0]["page"] == 3
    assert "out of memory" in out["second_reading"]["failed"][0]["error"]


def test_without_kraken_the_document_is_indexed_and_marked(monkeypatch):
    monkeypatch.setattr(sr, "kraken_installed", lambda: False)
    out, n = sr.read_record(record(), {3: Path("p3.png")})
    assert n == 0 and len(out["rows"]) == 10
    assert "kraken" in out["second_reading"]["skipped"]


def test_the_column_is_clipped_out_of_a_line_by_its_cuts():
    ln = {"x0": 0.0, "x1": 1.0, "y0": 0.1, "y1": 0.18, "text": "12Joseph Brooks Bra",
          "cuts": [0.02, 0.04] + [0.15 + 0.01 * i for i in range(13)] + [0.5, 0.52, 0.54, 0.56]}
    _by_line, by_col = sr.onto_bands([ln], {"columns": [0.1, 0.4], "rows": [[0.1, 0.19]]})
    assert by_col == {"1": "Joseph Brooks"}


def test_the_corpus_scripts_still_find_the_helpers():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import spike_fullpage
    assert spike_fullpage.onto_bands is sr.onto_bands
    assert spike_fullpage.read_page is sr.read_page
