"""Re-reading lines a page segmenter already found, with another model: the
stored boxes become a bbox segmentation in pixels, nothing is segmented again."""
import runpy

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pytest.importorskip("kraken")
spike = runpy.run_path(str(ROOT / "scripts" / "spike_lines_model.py"))


def test_stored_lines_become_a_bbox_segmentation_in_pixels():
    lines = [{"x0": 0.1, "x1": 0.5, "y0": 0.2, "y1": 0.25, "text": "a", "cuts": []},
             {"x0": 0.0, "x1": 1.0, "y0": 0.9, "y1": 1.0, "text": "b", "cuts": []}]
    seg = spike["bbox_segmentation"](lines, 1000, 2000, "page.png")
    assert seg.type == "bbox" and len(seg.lines) == 2
    assert seg.lines[0].bbox == (100, 400, 500, 500)
    assert seg.lines[1].bbox == (0, 1800, 1000, 2000)
    assert seg.lines[0].id != seg.lines[1].id


def test_a_line_with_its_polygon_becomes_a_baseline_line_not_a_box():
    lines = [{"x0": 0.1, "x1": 0.5, "y0": 0.2, "y1": 0.25, "text": "", "cuts": [],
              "boundary": [[0.1, 0.2], [0.5, 0.2], [0.5, 0.25], [0.1, 0.25]],
              "baseline": [[0.1, 0.24], [0.5, 0.24]]}]
    seg = spike["segmentation_of"](lines, 1000, 2000, "page.png")
    assert seg.type == "baselines"
    assert seg.lines[0].baseline == [(100, 480), (500, 480)]
    assert seg.lines[0].boundary[0] == (100, 400)
    bare = spike["segmentation_of"]([{k: v for k, v in lines[0].items()
                                      if k not in ("boundary", "baseline")}], 1000, 2000, "p")
    assert bare.type == "bbox"
