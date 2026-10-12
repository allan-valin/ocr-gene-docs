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


class FakeRecord:
    def __init__(self, text, cuts):
        self.prediction, self.cuts = text, cuts


class FakeSevenOne:
    """A kraken 7.1 model: loaded by `kraken.models.load_models`, given its
    config by `prepare_for_inference`, run through `.predict(im, segmentation)`,
    no `rpred` involved."""
    def __init__(self):
        self.calls, self.config = [], None

    def prepare_for_inference(self, config):
        self.config = config

    def predict(self, im, segmentation):
        self.calls.append((segmentation.type, self.config.padding, self.config.accelerator))
        for line in segmentation.lines:
            yield FakeRecord("Kubach", [[(10, 0), (12, 0)]])


def test_a_model_with_predict_is_read_through_it_and_the_padding_follows(tmp_path):
    from PIL import Image
    im = Image.new("L", (1000, 2000), 255)
    lines = [{"x0": 0.1, "x1": 0.5, "y0": 0.2, "y1": 0.25, "text": "", "cuts": []}]
    model = FakeSevenOne()
    got = spike["reread"](im, lines, model, pad=8)
    assert got[0]["text"] == "Kubach"
    assert got[0]["cuts"] == [0.011]
    assert model.calls == [("bbox", 8, "cpu")]


def test_safetensors_weights_go_to_the_seven_one_loader(monkeypatch):
    seen = {}
    import kraken.models as km
    monkeypatch.setattr(km, "load_models", lambda path, tasks=None: seen.update(path=path, tasks=tasks) or ["m"])
    assert spike["load_recogniser"](Path("medium.safetensors"), "cpu") == "m"
    assert seen["tasks"] == ["recognition"]
