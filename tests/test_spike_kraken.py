"""The parts of the kraken runner that are not a model: the adapter that lets
`read_vlm.whole_documents` drive it over the corpus, so the held-out pages
are read by kraken the same way they were read by the VLMs."""
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spike = runpy.run_path(str(ROOT / "scripts" / "spike_kraken.py"))


def test_the_reader_answers_like_a_server(monkeypatch, tmp_path):
    spike["read_line"] = lambda model, image, pad: "Maria Sanchez"
    reader = spike["Reader"](model=object(), pad=8, read_line=spike["read_line"])
    said, secs = reader.read(tmp_path / "x.png", "ignored", predict=64)
    assert said == "Maria Sanchez"
    assert secs >= 0.0
    assert reader.system is None


def test_the_document_arguments_are_the_ones_whole_documents_reads():
    ns = spike["document_args"](out=Path("o.json"), pages_json=Path("p.json"),
                                hand="cursive", documents_limit=2, pages_limit=1)
    for name in ("hands", "out", "pages_json", "scans", "records", "work",
                 "hand", "documents_limit", "pages_limit"):
        assert hasattr(ns, name), name
    assert ns.out == Path("o.json") and ns.hand == "cursive"
