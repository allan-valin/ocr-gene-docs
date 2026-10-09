"""The corpus pass behind `scripts/read_fullpage.py`, minus the models: which
pages it reads and in what order, how it knows a page is already read, and
how the per-page files it leaves become the sidecars `apply_second_opinion.py`
takes."""
import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pas = runpy.run_path(str(ROOT / "scripts" / "read_fullpage.py"))

HANDS = {
    "b.pdf": {"hash": "hb", "document": "typed", "pages": {"2": "typed", "3": "cursive"}},
    "a.pdf": {"hash": "ha", "document": "cursive", "pages": {"2": "cursive", "3": "unknown"}},
}


def test_cursive_pages_come_first_then_unknown_then_typed(tmp_path):
    got = pas["pages_wanted"](HANDS, tmp_path)
    assert got == [("a.pdf", "ha", 2, "cursive"), ("b.pdf", "hb", 3, "cursive"),
                   ("a.pdf", "ha", 3, "unknown"), ("b.pdf", "hb", 2, "typed")]


def test_a_page_already_on_disk_is_not_read_again(tmp_path):
    pas["page_file"](tmp_path, "ha", 2).write_text("{}")
    got = pas["pages_wanted"](HANDS, tmp_path)
    assert ("a.pdf", "ha", 2, "cursive") not in got
    assert len(got) == 3


def test_only_one_hand_when_asked(tmp_path):
    got = pas["pages_wanted"](HANDS, tmp_path, only=("typed",))
    assert got == [("b.pdf", "hb", 2, "typed")]


def test_collect_clips_cursive_lines_to_the_column_and_keeps_typed_lines_raw(tmp_path):
    out = tmp_path / "pages"
    out.mkdir()
    records = tmp_path / "records"
    records.mkdir()
    geo = {"columns": [0.1, 0.4], "rows": [[0.10, 0.20], [0.20, 0.30]]}
    (records / "ha.json").write_text(json.dumps(
        {"hash": "ha", "file": "a.pdf", "pages": [{"n": 2, "geometry": geo}]}))
    (records / "hb.json").write_text(json.dumps(
        {"hash": "hb", "file": "b.pdf", "pages": [{"n": 2, "geometry": geo}]}))
    text = "12 Maria Rossi"
    cuts = [0.05, 0.07, 0.09] + [0.15 + i * 0.02 for i in range(len(text) - 3)]
    lines = [{"x0": 0.02, "x1": 0.5, "y0": 0.11, "y1": 0.19, "text": text, "cuts": cuts}]
    pas["page_file"](out, "ha", 2).write_text(json.dumps(
        {"pdf": "a.pdf", "page": 2, "hand": "cursive", "lines": lines}))
    raw_typed = [{"x0": 0.02, "x1": 0.5, "y0": 0.21, "y1": 0.29, "text": "", "cuts": []}]
    pas["page_file"](out, "hb", 2).write_text(json.dumps(
        {"pdf": "b.pdf", "page": 2, "hand": "typed", "lines": raw_typed}))

    column, typed = pas["collect"](out, records)
    assert column["by"] == "row" and column["model"] == "ManuMcFondue-page-column"
    assert column["read"] == {"ha": {"2": {"1": "Maria Rossi"}}}
    assert typed == {"hb": {"2": raw_typed}}


def test_shards_split_the_work_without_overlap_or_loss(tmp_path):
    todo = pas["pages_wanted"](HANDS, tmp_path)
    parts = [pas["shard"](todo, f"{i}/3") for i in range(3)]
    assert sum(len(p) for p in parts) == len(todo)
    assert sorted(x for p in parts for x in p) == sorted(todo)
    assert pas["shard"](todo, None) == todo


def test_a_line_record_keeps_the_polygon_so_no_model_has_to_segment_again():
    import runpy
    sp = runpy.run_path(str(ROOT / "scripts" / "spike_fullpage.py"))

    class Line:
        boundary = [(10, 20), (90, 20), (90, 40), (10, 40)]
        baseline = [(10, 35), (90, 35)]

    class Rec:
        prediction = "Maria"
        cuts = [[(12, 20), (12, 40)], [(30, 20), (30, 40)], [(50, 20), (50, 40)],
                [(70, 20), (70, 40)], [(85, 20), (85, 40)]]

    got = sp["line_record"](Line(), Rec(), 100, 200)
    assert got["x0"] == 0.1 and got["x1"] == 0.9 and got["y0"] == 0.1 and got["y1"] == 0.2
    assert got["text"] == "Maria" and len(got["cuts"]) == 5 and got["cuts"][0] == 0.12
    assert got["boundary"] == [[0.1, 0.1], [0.9, 0.1], [0.9, 0.2], [0.1, 0.2]]
    assert got["baseline"] == [[0.1, 0.175], [0.9, 0.175]]
    bare = sp["line_record"](Line(), None, 100, 200)
    assert bare["text"] == "" and bare["cuts"] == [] and bare["baseline"]


def test_a_page_the_gpu_cannot_hold_is_read_on_the_cpu_instead():
    calls = []

    def read(im, seg, model, device="cpu"):
        calls.append(device)
        if device == "cuda":
            raise RuntimeError("CUDA out of memory. Tried to allocate 2.54 GiB")
        return [{"text": "ok"}]

    got = pas["read_with_fallback"]("im", {"cuda": "m-gpu", "cpu": "m-cpu"}, "cuda", read=read)
    assert got == [{"text": "ok"}] and calls == ["cuda", "cpu"]
    calls.clear()
    assert pas["read_with_fallback"]("im", {"cpu": "m-cpu"}, "cpu", read=read) == [{"text": "ok"}]
    assert calls == ["cpu"]
