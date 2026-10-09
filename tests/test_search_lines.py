"""Finding a name in the lines a page reader left behind, forgivingly."""
import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
mod = runpy.run_path(str(ROOT / "scripts" / "search_lines.py"))


def test_the_right_name_outranks_a_lookalike_and_noise():
    lines = [
        {"text": "Kuhlmann Wilhelm", "y0": 0.5},
        {"text": "Kubach August Friedrich", "y0": 0.3},
        {"text": "Santinon Eugenio", "y0": 0.1},
        {"text": "", "y0": 0.2},
    ]
    got = mod["hits"](lines, "Kubach August", book="b", page=3)
    assert got[0]["text"] == "Kubach August Friedrich" and got[0]["page"] == 3
    assert "Santinon Eugenio" not in [h["text"] for h in got]   # noise is out
    assert all(h["score"] < got[0]["score"] for h in got[1:])   # lookalikes below
    assert all(h["text"] for h in got)


def test_a_misread_still_scores_above_the_floor():
    got = mod["hits"]([{"text": "Kuback Augusto", "y0": 0}], "Kubach August", book="b", page=1)
    assert got and got[0]["score"] >= mod["FLOOR"]


def test_search_walks_every_page_file(tmp_path):
    (tmp_path / "b1-p0003.json").write_text(json.dumps(
        {"book": "b1", "page": 3, "lines": [{"text": "Kubach August", "y0": 0.3}]}))
    (tmp_path / "b1-p0004.json").write_text(json.dumps(
        {"book": "b1", "page": 4, "lines": [{"text": "Rossi Maria", "y0": 0.3}]}))
    got = mod["search"](tmp_path, "Kubach", limit=5)
    assert got[0]["page"] == 3 and got[0]["book"] == "b1"
