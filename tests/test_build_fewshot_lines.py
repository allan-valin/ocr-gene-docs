"""Few-shot lines: one column crop per hand-read name, ground truth beside it,
pages dealt into folds so no model is scored on a page it trained on."""
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
mod = runpy.run_path(str(ROOT / "scripts" / "build_fewshot_lines.py"))

GEO = {"columns": [0.1, 0.4], "rows": [[0.0, 0.1], [0.1, 0.2], [0.2, 0.3]]}


def line(x0, y0, x1, y1, text=""):
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "text": text, "cuts": []}


def test_lines_land_on_the_band_they_sit_on_and_only_in_the_name_column():
    lines = [line(0.05, 0.11, 0.5, 0.19, "on band 2"),
             line(0.6, 0.11, 0.9, 0.19, "another column"),
             line(0.05, 0.21, 0.5, 0.29, "on band 3")]
    by = mod["lines_by_band"](lines, GEO)
    assert [l["text"] for l in by[2]] == ["on band 2"]
    assert [l["text"] for l in by[3]] == ["on band 3"]
    assert 1 not in by


def test_crop_is_the_line_clipped_to_the_column_with_a_margin():
    l = line(0.02, 0.11, 0.7, 0.19)
    assert mod["crop_box"](l, GEO, margin=0.01) == pytest.approx((0.09, 0.11, 0.41, 0.19))
    short = line(0.15, 0.11, 0.3, 0.19)
    assert mod["crop_box"](short, GEO, margin=0.01) == (0.15, 0.11, 0.3, 0.19)


def test_a_ditto_or_bad_cut_is_not_a_training_line():
    assert mod["usable"]("Rossi Giovanni", "Rossi Giovani")
    assert mod["usable"]("Rossi Giovanni", "Rosi Gio")
    assert not mod["usable"]("Rossi Giovanni", "„ Gio")
    assert not mod["usable"]("Rossi", "")


def test_write_pairs_cuts_one_png_and_gt_per_usable_name(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    work = tmp_path / "work"
    work.mkdir()
    page = work / "page.png"
    Image.new("L", (1000, 1000), 255).save(page)
    (work / "doc-p1-chosen.txt").write_text(str(page))
    lines = {"h" * 64: {"1": [line(0.05, 0.11, 0.5, 0.19), line(0.05, 0.21, 0.5, 0.29),
                              line(0.05, 0.01, 0.5, 0.05), line(0.05, 0.05, 0.5, 0.09)]}}
    lf = tmp_path / "lines.json"
    lf.write_text(json.dumps(lines))
    by_hash = {"h" * 64: {"pages": [{"n": 1, "geometry": GEO}]}}
    rows = [
        {"name": "Rossi Giovanni", "doc": "h" * 64, "page": 1, "row": 2, "read": "Rossi Giov",
         "hand": "cursive", "pdf": "doc.pdf"},
        {"name": "Bianchi Anna", "doc": "h" * 64, "page": 1, "row": 3, "read": "„ Anna",
         "hand": "cursive", "pdf": "doc.pdf"},                       # ditto: skipped
        {"name": "Verdi Luigi", "doc": "h" * 64, "page": 1, "row": 1, "read": "Verdi Luigi",
         "hand": "cursive", "pdf": "doc.pdf"},                       # two lines: skipped
        {"name": "Typed Name", "doc": "h" * 64, "page": 1, "row": 2, "read": "Typed Name",
         "hand": "typed", "pdf": "doc.pdf"},                         # wrong hand: skipped
    ]
    out = tmp_path / "out"
    written = mod["write_pairs"](rows, lf, by_hash, work, out)
    assert [w["text"] for w in written] == ["Rossi Giovanni"]
    # with the base model's readings: the ditto stays out, the two stacked
    # lines on band 1 stay out, and a name whose reading sits one band over moves
    readings = {"h" * 64: {"1": {"1": "Verdi Luigi", "2": "Rosi Giovani", "3": "„ Anna"}}}
    rows[0]["row"], rows[1]["row"] = 3, 4    # the sheet drifted a row from Rossi on
    written = mod["write_pairs"](rows, lf, by_hash, work, tmp_path / "out2", readings=readings)
    assert [(w["text"], w["row"], w["sheet_row"]) for w in written] == [("Rossi Giovanni", 2, 3)]
    png = Path(written[0]["image"])
    assert png.exists() and png.with_suffix("").with_suffix(".gt.txt").read_text() == "Rossi Giovanni\n"
    assert Image.open(png).size == (320, 80)


def test_folds_deal_pages_by_size_so_they_come_out_even():
    written = ([{"doc": "a", "page": 1}] * 30 + [{"doc": "b", "page": 1}] * 20
               + [{"doc": "c", "page": 2}] * 12 + [{"doc": "d", "page": 1}] * 10)
    f = mod["folds"](written, 2)
    sizes = [sum({("a", 1): 30, ("b", 1): 20, ("c", 2): 12, ("d", 1): 10}[p] for p in fold)
             for fold in f]
    assert sorted(sizes) == [32, 40]   # greedy: 30 | 20+12 | +10 to the lighter
    assert sorted(p for fold in f for p in fold) == [("a", 1), ("b", 1), ("c", 2), ("d", 1)]


def test_drifted_names_move_to_their_bands_in_order_and_families_keep_their_rows():
    bands = {"5": "", "6": "Flaherty Berthe", "7": "Flaherty Camille",
             "8": "Vandestraeten Marie 1", "9": "José Ribeiro po", "10": "Ana Augusta Garcia"}
    names = [(5, "o'flaherty berthe"), (6, "o'flaherty camille"), (7, "vandestraeten marie"),
             (8, "jose ribeiro"), (9, "ana augusta garcia")]
    assert mod["align_page"](names, bands) == {5: 6, 6: 7, 7: 8, 8: 9, 9: 10}
    # two family members on neighbouring bands keep their own rows
    fam = {"3": "Toto Giuseppe", "4": "Toto Giovani"}
    assert mod["align_page"]([(3, "toto giuseppe"), (4, "toto giovani")], fam) == {3: 3, 4: 4}
    # a name the readings place nowhere keeps its row when that row is free, else drops
    assert mod["align_page"]([(7, "burman estera")], bands) == {7: 7}
    assert mod["align_page"]([(7, "vandestraeten marie"), (8, "burman estera")], bands) == {7: 8, 8: None}


def test_two_lines_side_by_side_are_one_name_stacked_lines_are_not():
    a, b = line(0.1, 0.11, 0.25, 0.19), line(0.27, 0.12, 0.4, 0.2)
    assert mod["side_by_side"]([b, a]) == [a, b]
    stacked = [line(0.1, 0.10, 0.4, 0.15), line(0.1, 0.15, 0.4, 0.2)]
    assert mod["side_by_side"](stacked) is None
    assert mod["side_by_side"]([a]) == [a]
    # a sliver at the column's right rule is the next column's ink, not the name
    sliver = line(0.385, 0.12, 0.42, 0.2)
    assert mod["side_by_side"]([a, sliver], GEO) == [a]
    assert mod["side_by_side"]([a, b, sliver], GEO) == [a, b]


def test_crop_band_pastes_the_pieces_left_to_right(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    im = Image.new("L", (1000, 1000), 255)
    a, b = line(0.1, 0.11, 0.2, 0.19), line(0.25, 0.11, 0.3, 0.21)
    strip = mod["crop_band"](im, [a, b], GEO, 0.0, gap=10)
    assert strip.size == (100 + 10 + 50, 100)
    assert mod["crop_band"](im, [a], GEO, 0.0).size == (100, 80)


def test_merge_takes_each_fold_page_from_the_model_that_never_saw_it():
    base = {"read": {"d1": {"1": {"1": "base a"}, "2": {"1": "base b"}}, "d2": {"3": {"1": "base c"}}}}
    side_a = {"read": {"d1": {"1": {"1": "A a"}, "2": {"1": "A b"}}, "d2": {"3": {"1": "A c"}}}}
    side_b = {"read": {"d1": {"1": {"1": "B a"}, "2": {"1": "B b"}}, "d2": {"3": {"1": "B c"}}}}
    folds = [[("d1", 1)], [("d2", 3)]]
    m = mod["merge_folds"]([side_a, side_b], folds, base, "t")
    assert m["read"]["d1"]["1"] == {"1": "A a"}      # fold A's held-out page, read by model A
    assert m["read"]["d2"]["3"] == {"1": "B c"}      # fold B's, by model B
    assert m["read"]["d1"]["2"] == {"1": "base b"}   # a page in no fold keeps the base reading
    assert m["model"] == "t" and base["read"]["d1"]["1"] == {"1": "base a"}
