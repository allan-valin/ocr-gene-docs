"""The parts of the VLM-on-lines spike that are not a model: which model it
names a sidecar after, and how it asks."""
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spike = runpy.run_path(str(ROOT / "scripts" / "spike_vlm_on_lines.py"))


def test_churro_weights_keep_the_tag_the_sidecars_already_carry():
    assert spike["tag_for"](Path("churro-3B.Q4_K_M.gguf")) == "churro-3B-Q4_K_M"


def test_another_models_weights_are_named_by_their_file():
    assert spike["tag_for"](Path("deepseek-ocr-2-q8_0.gguf")) == "deepseek-ocr-2-q8_0"
