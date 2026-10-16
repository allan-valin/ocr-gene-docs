"""Re-rowing the stored corpus from the line files already on disk."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import rerow_from_lines as rr  # noqa: E402


def write_record(tmp_path, cursive=True):
    conf = 0.4 if cursive else 0.95
    rec = {"hash": "abc", "notation": "X.1",
           "pages": [{"n": 1, "kind": "cover"},
                     {"n": 2, "kind": "list", "geometry": {"columns": [0.1, 0.4],
                                                             "rows": [[0.1, 0.19], [0.2, 0.29]]}}],
           "rows": [{"page": 2, "n": 1, "name_raw": "noise", "conf": {"name": conf}},
                    {"page": 2, "n": 2, "name_raw": "more", "conf": {"name": conf}},
                    # a third named row on the typed page: the hand label wants
                    # three readings before it calls a page anything
                    {"page": 2, "n": 3, "name_raw": "" if cursive else "x",
                     "conf": {"name": conf}}]}
    (tmp_path / "records").mkdir()
    f = tmp_path / "records" / "abc.json"
    f.write_text(json.dumps(rec))
    (tmp_path / "lines").mkdir()
    (tmp_path / "lines" / "abc-p2.json").write_text(json.dumps({"hand": "cursive", "lines": [
        {"x0": 0.12, "x1": 0.38, "y0": 0.11, "y1": 0.14, "text": "Carlos Cook", "cuts": []},
        {"x0": 0.12, "x1": 0.38, "y0": 0.15, "y1": 0.18, "text": "James Wheatley", "cuts": []},
        {"x0": 0.12, "x1": 0.38, "y0": 0.21, "y1": 0.28, "text": "Gregorio Bonel", "cuts": []}]}))
    return f


def test_a_dry_run_reports_and_writes_nothing(tmp_path, capsys):
    f = write_record(tmp_path)
    was = f.read_text()
    rr.main(["--records", str(tmp_path / "records"), "--lines", str(tmp_path / "lines")])
    assert f.read_text() == was
    assert "X.1: 1 pages, rows 3 -> 3" in capsys.readouterr().out


def test_write_rerows_the_page_and_a_second_run_leaves_it(tmp_path, capsys):
    f = write_record(tmp_path)
    args = ["--records", str(tmp_path / "records"), "--lines", str(tmp_path / "lines")]
    rr.main(args + ["--write"])
    rec = json.loads(f.read_text())
    assert [r["name_raw"] for r in rec["rows"]] == ["Carlos Cook", "James Wheatley", "Gregorio Bonel"]
    assert rec["pages"][1]["geometry"]["rows_from"] == "lines"
    assert rec["second_reading"]["rerowed"] == [2]
    rr.main(args + ["--write"])
    assert "0 pages in 0 documents" in capsys.readouterr().out


def test_a_typed_page_is_the_engine_s(tmp_path, capsys):
    write_record(tmp_path, cursive=False)
    rr.main(["--records", str(tmp_path / "records"), "--lines", str(tmp_path / "lines")])
    assert "0 pages in 0 documents" in capsys.readouterr().out
