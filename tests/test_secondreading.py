"""The kraken second reading runs per document at index time, so an install
made from the launcher reads cursive pages the way the corpus on Allan's
machine is read, instead of showing the engine's noise alone."""
import json
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

    out, n = sr.read_record(record(), {2: Path("p2.png"), 3: Path("p3.png")}, read=read,
                            rerow=False)
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


# --- one row per written line -------------------------------------------------
#
# On the corpus's cursive pages 7,530 of 58,915 engine bands hold two or more
# written lines and 1,339 lines fall on no band (counted 2026-10-16), so about
# one name in six had no row of its own. The segmenter's lines become the rows.

def band_rows(n=4, conf=0.4, named=()):
    """Engine bands, blank unless `named` says which carry a reading: a
    named band the lines miss keeps its row, so a test says what it needs."""
    return [{"page": 3, "n": i, "name_raw": f"band {i}" if i in named else "",
             "conf": {"name": conf}, "nacionalidade": f"nat {i}"} for i in range(1, n + 1)]


GEO = {"columns": [0.1, 0.4], "rows": [[0.10, 0.19], [0.20, 0.29], [0.30, 0.39], [0.40, 0.49]]}


def test_two_lines_in_one_band_become_two_rows():
    lines = [line(0.11, 0.14, "James Albert Wheatley"), line(0.15, 0.18, "Carlos Cook"),
             line(0.21, 0.28, "Gregorio Bonel"), line(0.31, 0.38, "Angele Primi"),
             line(0.41, 0.48, "Johannes Kuhre")]
    rows, extents = sr.rows_from_lines(band_rows(), lines, GEO)
    assert [r["name_raw"] for r in rows] == ["James Albert Wheatley", "Carlos Cook",
                                             "Gregorio Bonel", "Angele Primi", "Johannes Kuhre"]
    assert [r["n"] for r in rows] == [1, 2, 3, 4, 5]
    assert [r["band"] for r in rows] == [1, 1, 2, 3, 4]
    assert extents == [[0.11, 0.14], [0.15, 0.18], [0.21, 0.28], [0.31, 0.38], [0.41, 0.48]]
    assert all(r["read_by"] == sr.MODEL_TAG for r in rows)


def test_the_band_reading_stays_as_the_second_reading():
    rows, _ = sr.rows_from_lines(band_rows(named={2}), [line(0.21, 0.28, "Gregorio Bonel")], GEO)
    assert rows == [{"n": 1, "name_raw": "Gregorio Bonel", "read_by": sr.MODEL_TAG,
                     "second_read": {"model": sr.BAND_TAG, "text": "band 2"},
                     "page": 3, "conf": {"name": 0.4}, "nacionalidade": "nat 2", "band": 2}]


def test_a_band_shared_by_two_lines_lends_neither_its_other_columns():
    lines = [line(0.11, 0.14, "A"), line(0.15, 0.18, "B")]
    rows, _ = sr.rows_from_lines(band_rows(), lines, GEO)
    assert all("nacionalidade" not in r for r in rows), "whose nationality is it?"
    assert all(r["conf"] == {"name": 0.4} for r in rows), "the hand label still needs it"


def test_a_line_between_bands_is_a_row_too():
    rows, extents = sr.rows_from_lines(band_rows(), [line(0.192, 0.198, "Between")], GEO)
    assert rows[0]["name_raw"] == "Between" and "band" not in rows[0]
    assert "second_read" not in rows[0]


def test_a_line_outside_the_name_column_is_not_a_row():
    rows, _ = sr.rows_from_lines(band_rows(), [line(0.11, 0.18, "Brazileiro", x0=0.5, x1=0.7)], GEO)
    assert rows == []


def test_a_row_a_person_typed_stands_for_the_first_line_of_its_band():
    bands = band_rows()
    bands[1]["name_raw"] = "Gregorio Bonel"
    bands[1]["edits"] = [{"field": "name_raw", "by": "allan"}]
    lines = [line(0.11, 0.18, "x"), line(0.21, 0.24, "Gregoria Bonnel"), line(0.25, 0.28, "Maria Bonel")]
    rows, _ = sr.rows_from_lines(bands, lines, GEO)
    assert rows[1]["name_raw"] == "Gregorio Bonel" and rows[1]["edits"]
    assert rows[2]["name_raw"] == "Maria Bonel"


def test_a_person_s_row_with_no_line_is_kept_where_its_band_is():
    bands = band_rows(named={4})
    bands[3]["edits"] = [{"field": "name_raw", "by": "allan"}]
    rows, extents = sr.rows_from_lines(bands, [line(0.11, 0.18, "First")], GEO)
    assert [r["name_raw"] for r in rows] == ["First", "band 4"]
    assert extents[1] == [0.40, 0.49]


def test_the_printed_heading_keeps_its_row_and_its_lines_are_not_names():
    bands = band_rows()
    bands[0]["header"] = True
    bands[0]["name_raw"] = "Nomes"
    rows, _ = sr.rows_from_lines(bands, [line(0.11, 0.18, "Nomes"), line(0.21, 0.28, "Bonel")], GEO)
    assert [r["name_raw"] for r in rows] == ["Nomes", "Bonel"]
    assert rows[0]["header"] is True and rows[0]["band"] == 1


def test_read_record_rerows_the_handwritten_page_and_repaints_its_bands():
    def read(image):
        return [line(0.1 * i, 0.1 * i + 0.03, f"A {i}") for i in range(1, 6)] + \
               [line(0.1 * i + 0.04, 0.1 * i + 0.08, f"B {i}") for i in range(1, 6)]

    out, n = sr.read_record(record(), {3: Path("p3.png")}, read=read)
    p3 = [r for r in out["rows"] if r["page"] == 3]
    assert len(p3) == 10 and n == 10
    assert [r["n"] for r in p3] == list(range(1, 11))
    assert p3[0]["name_raw"] == "A 1" and p3[1]["name_raw"] == "B 1"
    assert [r for r in out["rows"] if r["page"] == 2] == record()["rows"][:5], "typed page untouched"
    geo = next(p for p in out["pages"] if p["n"] == 3)["geometry"]
    assert len(geo["rows"]) == 10 and geo["rows_from"] == "lines"
    assert geo["columns"] == [0.1, 0.4]
    assert out["second_reading"]["rerowed"] == [3]


def test_without_rerow_the_lines_are_read_onto_the_bands_as_before():
    out, n = sr.read_record(record(), {3: Path("p3.png")}, rerow=False,
                            read=lambda _: [line(0.1 * i, 0.1 * i + 0.08, f"L {i}") for i in range(1, 6)])
    p3 = [r for r in out["rows"] if r["page"] == 3]
    assert len(p3) == 5 and p3[0]["name_raw"] == "xyzzy 1"
    assert p3[0]["second_read"]["text"] == "L 1"


def test_the_bench_pairs_a_sheet_keyed_by_bands_with_the_rows_the_bands_became():
    """The held-out sheets number rows by the engine's bands. After a page is
    re-rowed from its lines, band 1 may be rows 1 and 2: each name goes to
    the row of its band that reads most like it."""
    from desembarque import truthset
    rows = [{"page": 3, "n": 1, "name_raw": "James Wheatley", "band": 1},
            {"page": 3, "n": 2, "name_raw": "Carlos Cook", "band": 1},
            {"page": 3, "n": 3, "name_raw": "Gregorio Bonel", "band": 2},
            {"page": 3, "n": 4, "name_raw": "Between", }]
    truth = {"page": 3, "rows": {"1": "Carlos Cook", "2": "Gregorio Bonel"}}
    got = truthset.pairs(truth, rows)
    assert [(p["truth"], p["row"]["n"]) for p in got] == [("Carlos Cook", 2), ("Gregorio Bonel", 3)]


def test_a_line_above_the_first_band_is_the_printed_header_not_a_row():
    lines = [line(0.02, 0.05, "NOME"), line(0.11, 0.18, "John Wynne"), line(0.93, 0.96, "of passengers")]
    rows, _ = sr.rows_from_lines(band_rows(), lines, GEO)
    assert [r["name_raw"] for r in rows] == ["John Wynne"]


def test_a_line_the_recogniser_read_nothing_off_is_not_a_row():
    lines = [line(0.11, 0.18, ""), line(0.21, 0.28, "  "), line(0.31, 0.38, "Angele Primi")]
    rows, _ = sr.rows_from_lines(band_rows(), lines, GEO)
    assert [r["name_raw"] for r in rows] == ["Angele Primi"]


def test_a_band_the_engine_named_that_no_line_fell_in_keeps_its_row():
    """The segmenter misses a line now and then (OL.PRJ.17347 p14: 28 named
    bands, 26 lines). The band's row stays, as the engine read it; only
    blank bands go."""
    bands = band_rows(named={1, 2, 4})
    rows, extents = sr.rows_from_lines(bands, [line(0.11, 0.18, "First"), line(0.41, 0.48, "Last")], GEO)
    assert [(r["name_raw"], r.get("band")) for r in rows] == [("First", 1), ("band 2", 2), ("Last", 4)]
    assert "read_by" not in rows[1]
    assert extents[1] == [0.20, 0.29]


def test_a_grid_that_found_a_fraction_of_the_writing_is_not_trusted():
    """APESP list, p6 (Allan, 2026-10-16): the rule detector found 5 bands
    on a page of 33 written lines, in a column that is not the name's, and
    the page came out as five empty rows. When the bands are fewer than
    half the lines the grid is wrong, and every line on the page becomes a
    row carrying its whole text — a name in a line is found; a name in no
    row is not."""
    geo = {"columns": [0.14, 0.20, 0.23, 0.26, 0.36],
           "rows": [[0.27, 0.35], [0.35, 0.42], [0.42, 0.50], [0.50, 0.57], [0.57, 0.65]]}
    bands = [{"page": 6, "n": i, "name_raw": "K" if i == 3 else "", "conf": {"name": 0.0}}
             for i in range(1, 6)]
    # the segmenter finds a line per cell: number, name, age, and a tick
    lines = []
    for i in range(30):
        y = 0.05 + i * 0.027
        # letters only: a digit in a name cell is age and sex the segmenter
        # joined on, and spills right by design
        lines += [line(y, y + 0.02, f"Name {'ABCDEFGHIJKLMNOPQRSTUVWXYZabcd'[i]}", x0=0.18, x1=0.35),
                  line(y + 0.002, y + 0.021, f"{18 + i} m", x0=0.40, x1=0.45),
                  line(y - 0.001, y + 0.019, str(166 + i), x0=0.12, x1=0.16),
                  line(y, y + 0.02, "-", x0=0.5, x1=0.52)]
    rows, extents = sr.rows_from_lines(bands, lines, geo)
    assert len(rows) == 30, "one row per written row, not per cell"
    assert rows[0]["name_raw"] == "Name A" and rows[0]["line"] == "166 · Name A · 18 m"
    assert rows[0]["cells"]["numero"]["text"] == "166"
    assert rows[0]["cells"]["idade"]["text"] == "18" and rows[0]["cells"]["sexo"]["text"] == "m"
    assert rows[29]["name_raw"] == "Name d" and rows[29]["cells"]["numero"]["text"] == "195"
    assert all(r["whole_line"] for r in rows)
    assert all("band" not in r for r in rows)
    assert extents[0] == [0.049, 0.071]


# --- a real page ---------------------------------------------------------------
#
# The tests above hand made-up lines to the function and passed while the real
# page came out as five empty rows (Allan, 2026-10-16: "the tests don't seem to
# be doing much if they don't catch this stuff"). This one is the segmenter's
# own 201 lines off that page, as kraken produced them, with the engine's
# bands and grid as stored. What a person asked of that page: the row with
# the name they were looking for.

def test_the_apesp_page_gives_the_row_with_kubach_on_it():
    fx = json.loads((Path(__file__).parent / "fixtures" / "apesp_p6_lines.json").read_text())
    rows, extents = sr.rows_from_lines(fx["bands"], fx["lines"], fx["geometry"])
    texts = [r["line"] for r in rows]
    hit = [t for t in texts if "Kuboch August" in t]
    assert hit, texts
    assert "92" in hit[0], hit[0]                      # his row number on the list
    # one row per written row, not per cell and not three rows in one:
    # 33 passengers and the sheet's heading, give or take the segmenter
    assert 36 <= len(rows) <= 60, len(rows)
    assert all(r.get("whole_line") for r in rows)
    assert extents == sorted(extents)
    # the neighbours are on their own rows, in order
    at = texts.index(hit[0])
    assert "Helbing" in texts[at - 2] and "Klara" in texts[at - 1]
    assert "Julian" in texts[at + 1]


# --- the GPU, when there is one ------------------------------------------------

def test_the_second_reading_runs_on_the_gpu_when_torch_has_one(monkeypatch):
    """Allan, 2026-10-17: the server read everything on the CPU of a laptop
    with an RTX 4050. The device is chosen by what torch can see, once;
    `cpu` on a machine with none, which is every friend's."""
    monkeypatch.setattr(sr, "_cuda", lambda: True)
    assert sr.device_for() == "cuda:0", "kraken wants the index; bare `cuda` broke its recogniser"
    monkeypatch.setattr(sr, "_cuda", lambda: False)
    assert sr.device_for() == "cpu"
    import inspect
    assert inspect.signature(sr.read_record).parameters["device"].default is None, \
        "read_record picks the device itself unless told"


def test_a_distrusted_grid_still_puts_the_cells_in_their_columns():
    """Allan, 2026-10-17: "everything is being put under Nome, cell
    information not cut/distributed". The sheet's column rules are there
    even when its row rules were not found: the name column is where the
    letters are, a number to its left is the list number, and to its
    right the cells are read by what they hold — a kinship word before
    the age, the age, m/f, s/c/v, then nationality and trade in the order
    every one of these forms prints them."""
    fx = json.loads((Path(__file__).parent / "fixtures" / "apesp_p6_lines.json").read_text())
    rows, _ = sr.rows_from_lines(fx["bands"], fx["lines"], fx["geometry"])
    k = next(r for r in rows if "Kuboch" in r["name_raw"])
    assert k["name_raw"] == "Kuboch August"
    assert k["cells"]["numero"]["text"] == "92"
    assert k["cells"]["idade"]["text"] == "18"
    assert k["cells"]["sexo"]["text"] == "m"
    assert "NR. E" not in k["name_raw"] and k["line"].startswith("NR. E")
    g = next(r for r in rows if "Irignn" in r["name_raw"])
    assert g["cells"]["numero"]["text"] == "68"
    assert g["cells"]["idade"]["text"] == "18" and g["cells"]["sexo"]["text"] == "m"
    assert g["cells"]["nacionalidade"]["text"] == "Talions"
    assert g["cells"]["profissao"]["text"] == "Maratore"
    m = next(r for r in rows if "Gengna Maria" in r["name_raw"])
    assert m["cells"]["idade"]["text"] == "41" and m["cells"]["parentesco"]["text"] == "chece"
    assert all(r.get("columns_by") == "content" for r in rows)


def test_the_person_can_force_the_cpu_or_the_card(monkeypatch):
    """The launcher's toggle has to have teeth when both builds are there:
    `DESEMBARQUE_DEVICE=cpu` reads on the CPU with a card in the machine;
    `gpu` asks for the card and gets the CPU when there is none."""
    monkeypatch.setattr(sr, "_cuda", lambda: True)
    monkeypatch.setenv("DESEMBARQUE_DEVICE", "cpu")
    assert sr.device_for() == "cpu"
    monkeypatch.setenv("DESEMBARQUE_DEVICE", "gpu")
    assert sr.device_for() == "cuda:0"
    monkeypatch.setattr(sr, "_cuda", lambda: False)
    assert sr.device_for() == "cpu"


def test_the_second_reading_reports_each_page_it_is_on_and_how_long_it_took(monkeypatch):
    """On the Windows CPU the second reading was 133 of a page's 181
    seconds, and the page watching saw nothing of it: the box said the
    names were all read and the table stayed empty. Each page is reported
    through `live` before it is read, and its seconds after."""
    from desembarque import live
    seen = []
    live.watch("x.pdf", pages=3)
    try:
        read = lambda img: (seen.append(live.get("x.pdf")["second"]),
                            [line(0.1 * i, 0.1 * i + 0.03, f"A {i}") for i in range(1, 6)])[1]
        sr.read_record(record(), {3: Path("p3.png")}, read=read)
        assert seen == [{"page": 3, "done": 0, "total": 1}]
        got = live.get("x.pdf")
        assert got["second"] == {"page": 3, "done": 1, "total": 1}
        assert live.timings()["second"] and live.timings()["second"][0] >= 0
    finally:
        live.unwatch("x.pdf")


def test_the_segmentation_model_is_loaded_once_and_the_warm_up_reads_a_blank(monkeypatch):
    """kraken's `blla.segment` loads its default segmentation model from
    disk on every call when given none; the server read every page that
    way. Loaded once, kept. `warm()` loads both models from disk — not a
    read of a blank page: that asked the card for 3.7 GB and OOMed
    (2026-10-18); a failure is returned, never raised."""
    loads = []
    monkeypatch.setattr(sr, "_SEG", None)
    monkeypatch.setattr(sr, "_load_seg", lambda: loads.append("seg") or "SEG")
    assert sr.seg_model() == "SEG" and sr.seg_model() == "SEG"
    assert loads == ["seg"]
    calls = []
    monkeypatch.setattr(sr, "load_model", lambda *a, **k: calls.append("rec") or "REC")
    monkeypatch.setattr(sr, "read_page", lambda *a, **k: calls.append("read"))
    monkeypatch.setattr(sr, "available", lambda *a, **k: True)
    assert sr.warm() == ""
    assert calls == ["rec"], "the models, and no read"
    monkeypatch.setattr(sr, "load_model", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no cuda")))
    assert "no cuda" in sr.warm()
    n = len(calls)
    monkeypatch.setattr(sr, "available", lambda *a, **k: False)
    assert sr.warm() == "" and len(calls) == n, "nothing to warm without kraken"
