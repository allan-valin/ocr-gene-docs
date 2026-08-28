"""Finding the table from what is printed on it, not from its rules.

The rules on these sheets are the least reliable thing about them. The vertical
ones are missing or faint on most pages, so the name column — chosen as the
widest gap between the rules that were found — came out as the *Procedencia*
column on BS.ENT.013947 p3, and as two thirds of the sheet on BS.ENT.013983 p2.
The horizontal ones are dotted, and the comb fitted to them locked onto the
empty ruled area below the list on 013983 and sat half a row out of phase on
013942, so every crop straddled two rows.

Two things on the page are printed and read cleanly: the column headings, and
the ordinal in the first column, which is printed on every ruled row whether
anybody wrote on it or not. The fixtures here are the detector's verbatim
output over the whole page at 2000 px.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque.tablegrid import columns, row_anchors

FIX = Path(__file__).parent / "fixtures"


def page(name):
    d = json.loads((FIX / f"frags-{name}.json").read_text(encoding="utf-8"))
    return d["fragments"], d["width"], d["height"]


def test_the_name_column_is_the_one_under_its_own_heading():
    """`Nome e Cognomes` is printed above it on every list in the corpus."""
    frs, W, H = page("013947-3")
    col = columns(frs, W, H)
    assert col is not None
    x0, x1 = col["name"]
    # the names on this page are written between 0.11 and 0.36 of the width
    assert 0.05 <= x0 / W <= 0.12, x0 / W
    assert 0.33 <= x1 / W <= 0.40, x1 / W


def test_the_column_is_bounded_by_the_headings_beside_it():
    """`Nacionalidade` prints to its right and `Ordem numerica` to its left, so
    neither the number nor the nationality is handed to the recogniser as part
    of somebody's name."""
    frs, W, H = page("013983-2")
    col = columns(frs, W, H)
    x0, x1 = col["name"]
    assert 0.04 <= x0 / W <= 0.11
    assert 0.26 <= x1 / W <= 0.32


def test_the_heading_row_is_where_the_table_starts():
    frs, W, H = page("013942-2")
    col = columns(frs, W, H)
    # the printed heading band sits at 0.28 of the height on this sheet
    assert 0.27 <= col["top"] / H <= 0.30


def test_the_ordinal_column_is_found_beside_the_names():
    frs, W, H = page("013942-2")
    col = columns(frs, W, H)
    assert col["ordinal"] is not None
    a, b = col["ordinal"]
    assert b <= col["name"][0] + 2 and a / W < 0.10


def test_a_page_with_no_heading_reports_none():
    assert columns([{"text": "nothing", "x0": 0, "y0": 0, "x1": 5, "y1": 5}],
                   100, 100) is None


def test_the_rows_are_where_the_ordinals_are_printed():
    """013942 p2 lists one passenger and the rest of the sheet is blank, but
    the ordinals are printed down all thirty ruled rows. The comb fitted to the
    ink put band 1 over printed row 3 and half a row low; the ordinals put every
    band on its own row."""
    frs, W, H = page("013942-2")
    col = columns(frs, W, H)
    rows = row_anchors(frs, col, H)
    assert 28 <= len(rows) <= 32, len(rows)
    top, bottom = rows[0]
    # the first written row — `Ponticelli Giovanni` — sits at 0.309-0.344
    assert top / H <= 0.315 and bottom / H >= 0.335, (top / H, bottom / H)


def test_a_row_holds_the_line_that_was_written_on_it():
    frs, W, H = page("013983-2")
    col = columns(frs, W, H)
    rows = row_anchors(frs, col, H)
    # fourteen typed passengers, then the tally block below them
    assert len(rows) >= 14
    first = rows[0]
    name = next(f for f in frs if f["text"].startswith("Oswaldo"))
    mid = (name["y0"] + name["y1"]) / 2
    assert first[0] <= mid <= first[1], "the first row does not cover the first name"


def test_every_written_line_falls_inside_exactly_one_row():
    """A band that straddles two rows is what produced the gibberish: the crop
    carried the descenders of one name and the ascenders of the next."""
    frs, W, H = page("013947-3")
    col = columns(frs, W, H)
    rows = row_anchors(frs, col, H)
    x0, x1 = col["name"]
    written = [f for f in frs
               if min(f["x1"], x1) - max(f["x0"], x0) > 0.4 * (f["x1"] - f["x0"])
               and f["y0"] > col["top"]]
    assert len(written) >= 30
    homeless = [f["text"] for f in written
                if not any(r[0] <= (f["y0"] + f["y1"]) / 2 <= r[1] for r in rows)]
    assert len(homeless) <= 2, homeless


def test_the_table_is_offered_in_the_shape_the_engine_already_reads():
    """`rows_from_bands`, the row cutter and the review UI all take a geometry
    and ask it for normalised bands and a name column."""
    from desembarque.tablegrid import table
    frs, W, H = page("013983-2")
    t = table(frs, W, H)
    assert t is not None
    assert len(t.normalized_rows()) == len(t.rows) >= 14
    a, b = t.name_column(0)
    assert 0.04 <= a <= 0.11 and 0.26 <= b <= 0.32
    assert all(0 <= x <= 1 for band in t.normalized_rows() for x in band)
    # the strip above the table, which is where the voyage is printed
    assert min(t.row_edges) == t.top


def test_a_page_with_no_table_offers_nothing():
    from desembarque.tablegrid import table
    assert table([{"text": "x", "x0": 0, "y0": 0, "x1": 1, "y1": 1}], 10, 10) is None


def strip_text(frs):
    return [{k: v for k, v in f.items() if k != "text"} for f in frs]


def test_the_table_is_measured_from_boxes_the_recogniser_never_read():
    """Detection alone costs three seconds on a page that costs eighty to read,
    and the measurement needs where the printing is, not what it says. Only the
    heading has to be read, to know which column is which."""
    from desembarque.tablegrid import table
    frs, W, H = page("013947-3")
    heading = [f for f in frs if "cognome" in f["text"].lower()
               or "nacionalidade" in f["text"].lower()]
    t = table(strip_text(frs), W, H, labelled=heading)
    assert t is not None
    assert 44 <= len(t.rows) <= 50, len(t.rows)
    a, b = t.name_column(0)
    assert 0.05 <= a <= 0.12 and 0.33 <= b <= 0.40


def test_without_the_heading_there_is_no_table_to_measure():
    from desembarque.tablegrid import table
    frs, W, H = page("013947-3")
    assert table(strip_text(frs), W, H, labelled=[]) is None


def test_only_the_heading_row_is_worth_reading():
    """The whole page costs eighty seconds to read and three to detect. What
    has to be read is the line that says which column is which."""
    from desembarque.tablegrid import heading_lines
    frs, W, H = page("013947-3")
    boxes = strip_text(frs)
    picked = heading_lines(boxes, H)
    assert len(picked) <= 40, len(picked)
    heads = [f for f in frs if f["text"].strip().lower() == "nome e cognomes"]
    assert heads, "fixture lost its heading"
    h = heads[0]
    assert any(abs(b["x0"] - h["x0"]) < 2 and abs(b["y0"] - h["y0"]) < 2
               for b in picked), "the name heading was not among the boxes read"


def test_the_boxes_come_in_the_detector_s_order_not_the_page_s():
    """The pitch is the median gap between the printed ordinals, and the
    detector reports its boxes in whatever order it found them. Measured over
    that order, the gaps are half of them negative and the page reports no rows
    at all — which is how BS.ENT.013942 fell back to its rules."""
    import random
    from desembarque.tablegrid import table
    frs, W, H = page("013942-2")
    shuffled = list(frs)
    random.Random(7).shuffle(shuffled)
    a = table(frs, W, H)
    b = table(shuffled, W, H)
    assert a is not None and b is not None
    assert len(a.rows) == len(b.rows)


def test_the_heading_is_the_first_such_line_not_the_busiest():
    """A data row has a cell in every column, and often one more than the
    heading: on 013983 the rows outvoted it."""
    from desembarque.tablegrid import heading_lines
    frs, W, H = page("013983-2")
    picked = heading_lines(strip_text(frs), H)
    head = next(f for f in frs if f["text"].strip().lower() == "nome e cognomes")
    assert any(abs(b["y0"] - head["y0"]) < 2 and abs(b["x0"] - head["x0"]) < 2
               for b in picked)


def test_a_row_the_detector_returned_whole_is_still_a_row():
    """On 013942 the detector hands back the entire row as one box — the name,
    the nationality, the age and the marital state — and only a quarter of it
    is the name. Judged by the box alone that row is thrown away, and the page
    reports thirty-one empty rows with its one passenger missing."""
    from desembarque.tablegrid import columns, written_lines
    frs, W, H = page("013942-2")
    col = columns(frs, W, H)
    x0, x1 = col["name"]
    whole_row = {"x0": 0.086 * W, "x1": 0.778 * W,
                 "y0": 0.306 * H, "y1": 0.343 * H}
    assert written_lines([whole_row], col) == [whole_row]
    # and a box that merely touches the column's edge is not a name
    edge = {"x0": x1 - 3, "x1": x1 + 400, "y0": 0.5 * H, "y1": 0.52 * H}
    assert written_lines([edge], col) == []


def test_a_few_stray_ordinals_do_not_outvote_the_writing():
    """On BS.ENT.015061 p6 five of the seventy printed numbers came through the
    scan, three rows apart, and set the pitch for the page: sixteen bands, each
    three rows tall, over a list of forty-six names."""
    from desembarque.tablegrid import row_anchors
    col = {"name": (100.0, 400.0), "ordinal": (60.0, 100.0), "top": 100.0}
    sparse = [{"x0": 70, "x1": 90, "y0": 100 + 105 * i, "y1": 120 + 105 * i}
              for i in range(5)]
    dense = [{"x0": 110, "x1": 380, "y0": 110 + 35 * i, "y1": 140 + 35 * i}
             for i in range(46)]
    bands = row_anchors(sparse + dense, col, 2000)
    assert len(bands) >= 40, len(bands)
    heights = [b - a for a, b in bands]
    assert max(heights) < 70, "a band is covering more than one row"


def test_a_continuation_page_uses_the_columns_of_the_page_before_it():
    """A dossier is twenty pages of one printed sheet and only the first page
    prints its headings. Measured alone, the rest fall back to the rules that
    lost the column in the first place."""
    from desembarque.tablegrid import table
    frs, W, H = page("013947-3")
    first = table(frs, W, H)
    # a page with the same boxes but nothing recognised on it at all
    blind = table(strip_text(frs), W, H, labelled=[],
                  hint={"name": first.name, "ordinal": first.ordinal})
    assert blind is not None
    assert blind.name == first.name
    assert not blind.heading_found
    assert len(blind.rows) >= len(first.rows) - 2


def test_without_a_hint_a_headingless_page_is_still_refused():
    from desembarque.tablegrid import table
    frs, W, H = page("013947-3")
    assert table(strip_text(frs), W, H, labelled=[]) is None


def test_the_printing_at_the_foot_of_the_sheet_is_not_more_rows():
    """The form's footnote sits in the name column, well below the last row, and
    the rows were being extended down to meet it: BS.ENT.014231 p3 came back
    with a hundred and twenty-eight bands on a form that holds fifty."""
    from desembarque.tablegrid import row_anchors
    col = {"name": (100.0, 400.0), "ordinal": (60.0, 100.0), "top": 100.0}
    rows_ = [{"x0": 110, "x1": 380, "y0": 110 + 30 * i, "y1": 135 + 30 * i}
             for i in range(20)]
    footnote = [{"x0": 105, "x1": 395, "y0": 1800, "y1": 1820}]
    # the footing runs most of the sheet's width, well below the last row
    footnote[0].update(x0=80, x1=1900, y0=1800, y1=1820)
    bands = row_anchors(rows_ + footnote, col, 2000)
    assert 18 <= len(bands) <= 24, len(bands)
    assert bands[-1][1] < 1000, "the rows reached the footing"


def test_the_blank_ruled_rows_are_kept_when_their_numbers_are_printed():
    """A blank row is a fact about the page: the clerk was given thirty lines and
    used seven. Trimming the table at the last name would also drop a passenger
    written after a long gap, which is worse."""
    from desembarque.tablegrid import row_anchors
    col = {"name": (100.0, 400.0), "ordinal": (60.0, 100.0), "top": 100.0}
    ordinals = [{"x0": 70, "x1": 90, "y0": 110 + 30 * i, "y1": 130 + 30 * i}
                for i in range(30)]
    written = [{"x0": 110, "x1": 380, "y0": 110 + 30 * i, "y1": 135 + 30 * i}
               for i in range(7)]
    bands = row_anchors(ordinals + written, col, 2000)
    assert len(bands) >= 28, len(bands)


def test_every_column_the_page_prints_a_heading_for_is_measured():
    """The name column is the one the engine reads, and it is not the only one
    printed: `Nacionalidade`, `Idade`, `Estado civil`, `Profissão`,
    `Procedencia`, `Destino`, `Classe` and `Observações` are on the same
    heading line, read as cleanly, and each of them is a column nobody has
    measured because nobody was going to read it."""
    frs, W, H = page("013947-3")
    col = columns(frs, W, H)
    got = {c["field"]: c for c in col["others"]}
    assert set(got) == {"nacionalidade", "idade", "estado", "profissao",
                        "procedencia", "destino", "classe", "observacoes"}
    # each one sits where its heading is printed, and they do not overlap
    boxes = sorted((c["box"] for c in col["others"]), key=lambda b: b[0])
    assert all(a[1] <= b[0] + 1 for a, b in zip(boxes, boxes[1:]))
    idade = got["idade"]["box"]
    assert 0.43 <= idade[0] / W <= 0.46 and 0.46 <= idade[1] / W <= 0.50


def test_a_column_reaches_halfway_to_the_heading_beside_it():
    """A heading is narrower than its column — `Idade` is five letters over a
    column of two-digit numbers — so the edge is put between the headings and
    not at them."""
    frs, W, H = page("013947-3")
    got = {c["field"]: c["box"] for c in columns(frs, W, H)["others"]}
    assert got["nacionalidade"][0] >= columns(frs, W, H)["name"][1] - 1
    assert got["observacoes"][1] >= 0.93 * W


def test_the_columns_are_offered_to_whoever_reads_the_page():
    """The geometry is what the engine, the row cutter and the review screen
    all ask; a column nobody can ask for is a column nobody will read."""
    frs, W, H = page("013947-3")
    from desembarque.tablegrid import table
    geo = table(frs, W, H)
    cols = geo.normalized_columns()
    assert cols["idade"][0] < cols["idade"][1] <= 1.0
    assert cols["nome"] == tuple(geo.normalized_cols())


def test_a_page_whose_heading_line_is_only_the_name_still_measures():
    """Nothing downstream may assume the other columns were found: a torn top
    or a printing with fewer headings is an ordinary page."""
    from desembarque.tablegrid import table
    frs = [{"text": "Nome e Cognomes", "x0": 200, "y0": 120, "x1": 350, "y1": 148},
           {"text": "Ordem", "x0": 60, "y0": 120, "x1": 120, "y1": 148},
           {"text": "1", "x0": 70, "y0": 200, "x1": 90, "y1": 230},
           {"text": "2", "x0": 70, "y0": 240, "x1": 90, "y1": 270}]
    col = columns(frs, 1000, 1400)
    assert col["others"] == []
    geo = table(frs, 1000, 1400)
    assert geo is None or geo.normalized_columns()["nome"]


def test_the_columns_carry_to_the_pages_that_print_no_heading():
    """A list runs to twenty pages of the same printed sheet and only the first
    prints its headings. The name column has been carried over since that was
    found; the eight beside it have to travel with it, or every page but the
    first has a name column and no cells."""
    from desembarque.tablegrid import table
    frs, W, H = page("013947-3")
    first = table(frs, W, H)
    hint = {"name": first.name, "ordinal": first.ordinal, "others": first.others}
    # a page with rows printed on it and no heading line at all
    plain = [f for f in frs if f["y0"] > first.top + 10]
    later = table(plain, W, H, hint=hint)
    assert later is not None
    assert set(later.normalized_columns()) == set(first.normalized_columns())
