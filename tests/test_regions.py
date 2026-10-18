"""Read only this area / column (Windows test report, 2026-10-17, §7).

When the table's grid cannot be found — no ruled lines, two pages in one
scan — the person draws the column(s) to read on the scan and only those
are read: one row per written line, the regions' lines aligned into rows
by height, the first region the name. Kept beside the full reading, never
over it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque import regions as rg


def line(y0, y1, text, x0=0.1, x1=0.9):
    return {"x0": x0, "x1": x1, "y0": y0, "y1": y1, "text": text}


def test_regions_are_normalised_ordered_clamped_and_the_tiny_dropped():
    out = rg.normalize([{"x0": 0.6, "y0": 0.9, "x1": 0.2, "y1": 0.1},
                        {"x0": -0.2, "y0": 0.0, "x1": 0.3, "y1": 1.4},
                        {"x0": 0.5, "y0": 0.5, "x1": 0.502, "y1": 0.9},
                        "junk"])
    assert out == [{"x0": 0.2, "y0": 0.1, "x1": 0.6, "y1": 0.9},
                   {"x0": 0.0, "y0": 0.0, "x1": 0.3, "y1": 1.0}]
    assert rg.normalize(None) == []


def test_the_lines_of_each_region_are_aligned_into_rows_by_height():
    """A ruleless certidão: nome do marido | nome da mulher | ano. A line
    in the second region at the height of one in the first is the same
    row; a line with no neighbour is a row on its own, its other cells
    blank; the first region is the name."""
    names = [line(0.10, 0.13, "KUBACH AUGUST"), line(0.15, 0.18, "ROSSI PIETRO"),
             line(0.30, 0.33, "SILVA JOAO")]
    wives = [line(0.105, 0.135, "MARIA"), line(0.31, 0.335, "ANA")]
    years = [line(0.10, 0.13, "1920"), line(0.15, 0.18, "1921"), line(0.50, 0.53, "1930")]
    rows = rg.rows_from_regions([names, wives, years])
    assert [r["cells"] for r in rows] == [
        ["KUBACH AUGUST", "MARIA", "1920"],
        ["ROSSI PIETRO", "", "1921"],
        ["SILVA JOAO", "ANA", ""],
        ["", "", "1930"]]
    assert [r["n"] for r in rows] == [1, 2, 3, 4]
    assert rows[0]["name_raw"] == "KUBACH AUGUST" and rows[3]["name_raw"] == ""
    assert rows[0]["y0"] == 0.10 and rows[0]["y1"] == 0.135, "the row spans its lines"
    assert rows[0]["region"] == 0 and rows[3]["region"] == 2


def test_two_lines_in_one_region_at_the_same_height_stay_two_rows():
    """A double page: left column and right column are the same height
    throughout, and are two regions — but inside one region two lines
    never merge."""
    left = [line(0.1, 0.13, "A"), line(0.1, 0.13, "B")]
    rows = rg.rows_from_regions([left])
    assert [r["cells"] for r in rows] == [["A"], ["B"]]


def test_a_region_is_cropped_read_and_its_lines_put_back_on_the_page(tmp_path):
    """The reader sees the crop; the record keeps page coordinates, so the
    scan can outline the row where it is."""
    from PIL import Image
    img = tmp_path / "p.png"
    Image.new("L", (1000, 500), 255).save(img)
    seen = []

    def read(im):
        seen.append(im.size)
        return [line(0.0, 0.5, "TOP", x0=0.0, x1=1.0), line(0.5, 1.0, "BOTTOM", x0=0.0, x1=0.5)]

    regs = [{"x0": 0.1, "y0": 0.2, "x1": 0.5, "y1": 0.6}]
    rows, lines = rg.read_regions(img, regs, read)
    assert seen == [(400, 200)]
    assert [l["text"] for l in lines[0]] == ["TOP", "BOTTOM"]
    top = lines[0][0]
    assert (top["x0"], top["y0"], top["x1"], top["y1"]) == (0.1, 0.2, 0.5, 0.4)
    bottom = lines[0][1]
    assert (round(bottom["x0"], 3), round(bottom["y0"], 3), round(bottom["x1"], 3), round(bottom["y1"], 3)) == (0.1, 0.4, 0.3, 0.6)
    assert [r["cells"] for r in rows] == [["TOP"], ["BOTTOM"]]
    assert rows[0]["page_y"] == [0.2, 0.4]


def test_a_region_the_reader_cannot_read_is_empty_and_said_so(tmp_path):
    from PIL import Image
    img = tmp_path / "p.png"
    Image.new("L", (100, 100), 255).save(img)

    def read(im):
        raise RuntimeError("no cuda")

    rows, lines = rg.read_regions(img, [{"x0": 0, "y0": 0, "x1": 1, "y1": 1}], read)
    assert rows == [] and lines == [[]]
