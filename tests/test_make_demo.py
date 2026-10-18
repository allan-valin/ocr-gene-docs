"""The public demo: a folder of PDFs the server has read, built into one
static page with its images beside it, for GitHub Pages (Allan,
2026-10-18: photos of his own exam notes, typed and handwritten, so the
archive's pages stay unpublished)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import make_demo


def test_the_demo_embeds_each_document_s_reading_and_renders_its_pages(tmp_path, monkeypatch):
    folder = tmp_path / "samples"
    (folder / "transcriptions").mkdir(parents=True)
    (folder / "a.pdf").write_bytes(b"%PDF-1.7\n")
    (folder / "b.pdf").write_bytes(b"%PDF-1.7\n")
    hashes = {"a.pdf": "h" * 64, "b.pdf": "g" * 64}
    (folder / "transcriptions" / f"{hashes['a.pdf']}.json").write_text(json.dumps({
        "hash": hashes["a.pdf"], "file": "a.pdf", "engine": "paddle",
        "pages": [{"n": 1, "kind": "unknown", "form": {"text": "15. Wie kann..."}}],
        "rows": [],
        "custom": {"1": {"regions": [{"x0": 0, "y0": 0, "x1": 1, "y1": 1}], "reader": "kraken",
                         "rows": [{"n": 1, "name_raw": "This is a test", "cells": ["This is a test"],
                                   "page": 1, "page_y": [0.1, 0.12]}]}}}))
    monkeypatch.setattr(make_demo, "page_count", lambda pdf: 1)
    monkeypatch.setattr(make_demo, "doc_hash", lambda pdf: hashes[pdf.name])
    rendered = []

    def render(pdf, n, dest, dpi=120, grayscale=False):
        rendered.append((pdf.name, n, dest.name))
        dest.write_bytes(b"jpg")
        return True
    monkeypatch.setattr(make_demo, "render_page", render)
    monkeypatch.setattr(make_demo, "image_size", lambda p: (1530, 2040))
    html_src = tmp_path / "review.html"
    html_src.write_text("<html><script id='payload'>__DATA__</script></html>")
    out = tmp_path / "out"
    assert make_demo.build(folder, out, review=html_src, dpi=72) == 0
    assert rendered == [("a.pdf", 1, "a-p1.jpg"), ("b.pdf", 1, "b-p1.jpg")]
    html = (out / "index.html").read_text()
    assert "__DATA__" not in html and "This is a test" in html
    data = json.loads((out / "data.json").read_text())
    a, b = data["documents"]
    assert a["file"] == "a.pdf" and a["pages"] == [{"n": 1, "file": "pages/a-p1.jpg", "w": 1530, "h": 2040}]
    assert a["custom"]["1"]["rows"][0]["name_raw"] == "This is a test"
    assert a["texts"] == {"1": "15. Wie kann..."} and a["pageTexts"] == a["texts"]
    assert a["transcribed"] is True
    assert b["transcribed"] is False and b["rows"] is None and b["custom"] is None
    assert data["demo"] is True
