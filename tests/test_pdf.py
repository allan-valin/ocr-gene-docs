"""pypdfium2 replacements for the poppler tools, checked against a real dossier."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pdf_mod = pytest.importorskip("desembarque.pdf")
SAMPLE = Path(__file__).resolve().parents[1] / "data/scans/BR_RJANRIO_BS_0_RPV_ENT_017397_d0001de0001.pdf"
needs_sample = pytest.mark.skipif(not SAMPLE.exists(), reason="sample dossier not downloaded")


@needs_sample
def test_page_count_matches_the_known_dossier():
    assert pdf_mod.page_count(SAMPLE) == 3


def test_page_count_of_a_missing_file_is_zero(tmp_path):
    assert pdf_mod.page_count(tmp_path / "nope.pdf") == 0


@needs_sample
def test_renders_a_page_to_jpeg(tmp_path):
    size = pdf_mod.render_page(SAMPLE, 2, tmp_path / "p2.jpg", dpi=60)
    assert size and size[0] > 100 and size[1] > 100
    assert (tmp_path / "p2.jpg").stat().st_size > 1000


@needs_sample
def test_render_refuses_a_page_out_of_range(tmp_path):
    assert pdf_mod.render_page(SAMPLE, 99, tmp_path / "x.jpg") is None


@needs_sample
def test_extracts_embedded_images_largest_first(tmp_path):
    imgs = pdf_mod.extract_images(SAMPLE, 2, tmp_path)
    assert len(imgs) >= 2
    from PIL import Image
    sizes = []
    for p in imgs:
        with Image.open(p) as im:
            sizes.append(im.width * im.height)
    assert sizes == sorted(sizes, reverse=True)


@needs_sample
def test_extracts_a_bilevel_layer_for_geometry(tmp_path):
    """The MRC mask is what grid detection needs; a render loses the rules."""
    from PIL import Image
    found = False
    for p in pdf_mod.extract_images(SAMPLE, 2, tmp_path):
        with Image.open(p) as im:
            colours = im.getcolors(4)
            if im.mode == "1" or (colours is not None and len(colours) <= 2):
                found = True
    assert found, "no bilevel layer found in an MRC-compressed page"


@needs_sample
def test_extracts_the_text_layer():
    text = pdf_mod.extract_text(SAMPLE, range(2, 3))
    assert len(text) > 200
    assert "HOLLANDSCHE" in text.upper()
