"""Re-reading the whole-page pass's lines with another recogniser: which pages
are due, what lands on disk, and the sidecar's tag."""
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytest.importorskip("kraken")
rr = runpy.run_path(str(ROOT / "scripts" / "reread_fullpage.py"))
pas = runpy.run_path(str(ROOT / "scripts" / "read_fullpage.py"))


def page(dir_, doc, n, hand, lines=1):
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / f"{doc}-p{n}.json").write_text(json.dumps(
        {"pdf": f"{doc}.pdf", "page": n, "hand": hand,
         "lines": [{"x0": 0.1, "x1": 0.3, "y0": 0.1, "y1": 0.12, "text": "x", "cuts": []}] * lines}))


def test_typed_pages_and_pages_already_reread_are_not_due(tmp_path):
    src, out = tmp_path / "in", tmp_path / "out"
    page(src, "a", 2, "cursive"); page(src, "a", 3, "typed")
    page(src, "b", 2, "unknown"); page(src, "c", 2, "cursive")
    page(out, "c", 2, "cursive")
    due = rr["pages_due"](src, out)
    assert [(p.stem) for p in due] == ["a-p2", "b-p2"]


def test_a_page_reread_keeps_its_lines_and_names_the_model(tmp_path):
    src, out = tmp_path / "in", tmp_path / "out"
    page(src, "a", 2, "cursive", lines=2)
    said = [{"x0": 0.1, "x1": 0.3, "y0": 0.1, "y1": 0.12, "text": "Kubach", "cuts": [0.2]}] * 2
    rr["write_page"](out, src / "a-p2.json", said, "medium", 1.5)
    got = json.loads((out / "a-p2.json").read_text())
    assert got["hand"] == "cursive" and got["pdf"] == "a.pdf" and got["page"] == 2
    assert got["model"] == "medium" and [l["text"] for l in got["lines"]] == ["Kubach", "Kubach"]
    assert not (out / "a-p2.tmp").exists()


def test_collect_takes_the_tag_of_the_model_that_read(tmp_path):
    out, records = tmp_path / "out", tmp_path / "records"
    records.mkdir()
    sidecar, _typed = pas["collect"](out, records, tag="PP-OCRv6-hist-medium-page-column")
    assert sidecar["model"] == "PP-OCRv6-hist-medium-page-column"
    sidecar, _typed = pas["collect"](out, records)
    assert sidecar["model"] == pas["MODEL_TAG"]


def test_a_page_without_a_hand_is_due_and_keeps_its_book(tmp_path):
    """The 1923 window's files (`read_hospedaria.py`) have a book and no hand."""
    src, out = tmp_path / "in", tmp_path / "out"
    src.mkdir()
    (src / "x-p0001.json").write_text(json.dumps(
        {"book": "x", "pdf": "x.pdf", "page": 1,
         "lines": [{"x0": 0.1, "x1": 0.3, "y0": 0.1, "y1": 0.12, "text": "x", "cuts": []}]}))
    assert [f.name for f in rr["pages_due"](src, out)] == ["x-p0001.json"]
    rr["write_page"](out, src / "x-p0001.json", [], "medium", 0.1)
    got = json.loads((out / "x-p0001.json").read_text())
    assert got["book"] == "x" and got["page"] == 1 and got["model"] == "medium"


def test_a_page_with_no_cached_image_is_rendered_from_its_scan(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setitem(rr["page_image"].__globals__, "chosen_image", lambda work, pdf, page: None)
    monkeypatch.setitem(rr["page_image"].__globals__, "render", lambda pdf, page, dpi, tmp: calls.append((pdf, page, dpi)) or "im")
    scans = tmp_path / "scans"; scans.mkdir(); (scans / "x.pdf").write_bytes(b"")
    got = rr["page_image"](tmp_path, "x.pdf", 3, scans, 200, tmp_path)
    assert got == "im" and calls == [(scans / "x.pdf", 3, 200)]


def test_a_page_with_no_cached_image_and_no_scan_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setitem(rr["page_image"].__globals__, "chosen_image", lambda work, pdf, page: None)
    assert rr["page_image"](tmp_path, "x.pdf", 3, tmp_path / "none", 200, tmp_path) is None


def test_shards_split_the_due_pages(tmp_path):
    src, out = tmp_path / "in", tmp_path / "out"
    for i in range(5):
        page(src, f"d{i}", 2, "cursive")
    a = rr["shard"](rr["pages_due"](src, out), "0/2")
    b = rr["shard"](rr["pages_due"](src, out), "1/2")
    assert sorted(f.name for f in a + b) == [f"d{i}-p2.json" for i in range(5)]
    assert not set(a) & set(b)
