"""The parts of the CHURRO runner that are not a model.

The model is measured, not tested — but what it says arrives wrapped in the
tags its own prompt asks for, and a sidecar that keeps the tags would score
every row as wrong for a reason that has nothing to do with reading.
"""
import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
churro = runpy.run_path(str(ROOT / "scripts" / "read_vlm.py"))
unwrap = churro["unwrap"]
rows_from = churro["rows_from"]
pick_documents = churro["pick_documents"]
done_already = churro["done_already"]
read_document = churro["read_document"]


class TestUnwrap:
    def test_it_takes_what_is_between_the_tags(self):
        assert unwrap("<output>Guido Cantadore</output>") == "Guido Cantadore"

    def test_it_survives_the_model_chattering_first(self):
        assert unwrap("Sure!\n<output>José Muesso</output>\n") == "José Muesso"

    def test_an_unclosed_tag_still_gives_the_reading(self):
        assert unwrap("<output>Emma Contadore") == "Emma Contadore"

    def test_a_bare_answer_is_taken_as_it_stands(self):
        assert unwrap("  Pedro Lammenn  ") == "Pedro Lammenn"

    def test_nothing_said_is_nothing_read(self):
        assert unwrap("<output></output>") == ""


class TestRowsFrom:
    def make(self, tmp_path, n):
        lines = [json.dumps({"image": f"images/x_{i}.png", "label": "A",
                             "doc": "d", "page": 2, "n": i}) for i in range(n)]
        (tmp_path / "labels.jsonl").write_text("\n".join(lines) + "\n",
                                               encoding="utf-8")
        return tmp_path

    def test_a_limit_reads_a_prefix_and_no_more(self, tmp_path):
        assert len(rows_from(self.make(tmp_path, 10), 3)) == 3

    def test_no_limit_reads_the_lot(self, tmp_path):
        assert len(rows_from(self.make(tmp_path, 10), 0)) == 10

    def test_a_blank_line_is_not_a_row(self, tmp_path):
        d = self.make(tmp_path, 2)
        (d / "labels.jsonl").write_text(
            (d / "labels.jsonl").read_text(encoding="utf-8") + "\n",
            encoding="utf-8")
        assert len(rows_from(d, 0)) == 2


class TestOnlyOneHand:
    def make(self, tmp_path):
        rows = [{"image": "a.png", "source": "cursive-p2.json", "doc": "d",
                 "page": 2, "n": 1, "label": "A"},
                {"image": "b.png", "source": "typed-p2.json", "doc": "d",
                 "page": 2, "n": 2, "label": "B"},
                {"image": "c.png", "source": "unknown-hash.json", "doc": "d",
                 "page": 2, "n": 3, "label": "C"}]
        (tmp_path / "labels.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        return tmp_path, {"cursive-p2.json": "cursive", "typed-p2.json": "typed"}

    def test_it_reads_only_the_hand_asked_for(self, tmp_path):
        d, hands = self.make(tmp_path)
        got = rows_from(d, 0, hand="cursive", hands=hands)
        assert [r["n"] for r in got] == [1]

    def test_a_page_of_unrecorded_hand_is_not_guessed_into_either(self, tmp_path):
        d, hands = self.make(tmp_path)
        assert [r["n"] for r in rows_from(d, 0, hand="typed", hands=hands)] == [2]

    def test_no_hand_asked_for_reads_everything(self, tmp_path):
        d, hands = self.make(tmp_path)
        assert len(rows_from(d, 0, hands=hands)) == 3


class TestPickDocuments:
    """Which scans a VLM pass should spend its seconds on.

    A row costs 8.5 s, so a whole-corpus pass is 170 hours and choosing is the
    whole design. `data/hands.json` (T4) says which documents are cursive, and
    those are the ones a VLM is worth paying for.
    """

    HANDS = {
        "a.pdf": {"document": "cursive", "hash": "aaa", "rows": {"cursive": 40}},
        "b.pdf": {"document": "typed", "hash": "bbb", "rows": {"typed": 30}},
        "c.pdf": {"document": "cursive", "hash": "ccc", "rows": {"cursive": 12}},
        "d.pdf": {"document": "unknown", "hash": "ddd", "rows": {}},
    }

    def test_it_takes_only_the_hand_asked_for(self):
        assert pick_documents(self.HANDS, hand="cursive") == ["a.pdf", "c.pdf"]

    def test_a_limit_stops_it_early(self):
        assert pick_documents(self.HANDS, hand="cursive", limit=1) == ["a.pdf"]

    def test_no_hand_asked_for_takes_them_all_in_order(self):
        assert pick_documents(self.HANDS) == ["a.pdf", "b.pdf", "c.pdf", "d.pdf"]

    def test_a_document_of_unknown_hand_is_never_a_cursive_one(self):
        assert "d.pdf" not in pick_documents(self.HANDS, hand="cursive")


class TestResume:
    """A pass that costs hours has to survive being stopped, like every other."""

    def test_a_page_already_read_is_not_read_again(self):
        said = {"aaa": {"2": {"1": "José"}}}
        assert done_already(said, "aaa", 2) is True

    def test_a_page_never_reached_is_not_done(self):
        assert done_already({"aaa": {"2": {}}}, "aaa", 3) is False

    def test_a_page_that_read_as_nothing_is_still_done(self):
        assert done_already({"aaa": {"2": {}}}, "aaa", 2) is True


class TestPagesLimit:
    """A pass that costs minutes a page needs a way to take a look first."""

    class FakeServer:
        def __init__(self):
            self.asked = 0

        def read(self, image, prompt, predict=64):
            self.asked += 1
            return f"row {self.asked}", 0.1

    def record(self):
        geo = {"rows": [[0.1, 0.2], [0.2, 0.3]], "columns": [[0.1, 0.5]],
               "skew": 0.0}
        return {"pages": [{"n": 2, "geometry": geo}, {"n": 3, "geometry": geo}]}

    def test_it_stops_after_the_pages_asked_for(self, tmp_path, monkeypatch):
        import desembarque.bandcrops as bandcrops
        from PIL import Image
        monkeypatch.setattr(bandcrops, "crops_for",
                            lambda *a, **k: {1: {"carved": Image.new("L", (40, 12))}})
        import page_geometry
        img = tmp_path / "p.png"
        Image.new("L", (100, 100)).save(img)
        monkeypatch.setattr(page_geometry, "page_image", lambda *a, **k: img)

        said = {}
        server = self.FakeServer()
        read_document(server, tmp_path / "x.pdf", self.record(), tmp_path,
                      said, "aaa", pages_limit=1)
        assert list(said["aaa"]) == ["2"]
        assert server.asked == 1


class TestOnlyTheseP4ges:
    """The held-out draw is read page for page, or it is not the same set."""

    def test_a_page_not_asked_for_is_not_read(self, tmp_path, monkeypatch):
        import desembarque.bandcrops as bandcrops
        from PIL import Image
        monkeypatch.setattr(bandcrops, "crops_for",
                            lambda *a, **k: {1: {"carved": Image.new("L", (40, 12))}})
        import page_geometry
        img = tmp_path / "p.png"
        Image.new("L", (100, 100)).save(img)
        monkeypatch.setattr(page_geometry, "page_image", lambda *a, **k: img)

        geo = {"rows": [[0.1, 0.2]], "columns": [[0.1, 0.5]], "skew": 0.0}
        rec = {"pages": [{"n": 2, "geometry": geo}, {"n": 5, "geometry": geo}]}

        class Server:
            def read(self, image, prompt, predict=64):
                return "a name", 0.1

        said = {}
        read_document(Server(), tmp_path / "x.pdf", rec, tmp_path, said, "aaa",
                      only={5})
        assert list(said["aaa"]) == ["5"]


class TestMessages:
    """A model is asked the way its own card asks it, or the measurement is of
    the prompt and not the model. PaddleOCR-VL takes `OCR:` and no persona."""

    def test_churro_style_carries_the_system_prompt(self):
        got = churro["messages"]("read this", "abc")
        assert got[0]["role"] == "system"
        assert got[1]["role"] == "user"
        assert got[1]["content"][0]["text"] == "read this"
        assert got[1]["content"][1]["image_url"]["url"].endswith(",abc")

    def test_no_system_means_no_system_message_at_all(self):
        got = churro["messages"]("OCR:", "abc", system=None)
        assert [m["role"] for m in got] == ["user"]

    def test_every_style_names_a_row_prompt(self):
        for name, style in churro["STYLES"].items():
            assert style["row"], name
        assert churro["STYLES"]["paddleocr"]["system"] is None
        assert churro["STYLES"]["paddleocr"]["row"] == "OCR:"


class TestReadRows:
    """One row the server chokes on is one row unread, not a run lost.

    llama-server answers 500 when a model emits half a multibyte character,
    which PaddleOCR-VL did on row 132 of 155 -- and the 131 readings before
    it were never written. The reading is saved after every row, and a row
    that fails is recorded as nothing read, so the pass can be scored and
    resumed."""

    class Server:
        def __init__(self, fail_on: int):
            self.fail_on, self.asked, self.system = fail_on, 0, None

        def read(self, image, prompt, predict=64):
            import urllib.error
            self.asked += 1
            if self.asked == self.fail_on:
                raise urllib.error.HTTPError("http://x", 500, "peg", {}, None)
            return f"read {self.asked}", 0.5

    def rows(self):
        return [{"doc": "d", "page": 2, "n": i, "image": f"images/{i}.png",
                 "label": f"name {i}"} for i in (1, 2, 3)]

    def test_a_failed_row_is_recorded_as_nothing_and_the_rest_are_read(self, tmp_path):
        out = tmp_path / "side.json"
        got = churro["read_rows"](self.Server(fail_on=2), self.rows(), "OCR:",
                                  tmp_path, out, "m")
        assert got["read"]["d"]["2"] == {"1": "read 1", "2": "", "3": "read 3"}
        assert got["rows"] == 3

    def test_the_sidecar_is_on_disk_after_every_row(self, tmp_path):
        out = tmp_path / "side.json"
        seen = []

        class Peek(self.Server):
            def read(self, image, prompt, predict=64):
                if out.exists():
                    seen.append(len(json.loads(out.read_text())["read"]["d"]["2"]))
                return super().read(image, prompt, predict)

        churro["read_rows"](Peek(fail_on=0), self.rows(), "OCR:", tmp_path, out, "m")
        assert seen == [1, 2]
        assert json.loads(out.read_text())["model"] == "m"

    def test_a_row_already_in_the_sidecar_is_not_read_again(self, tmp_path):
        out = tmp_path / "side.json"
        out.write_text(json.dumps({"model": "m", "read": {"d": {"2": {"1": "old"}}},
                                   "seconds": 1.0, "rows": 1}))
        server = self.Server(fail_on=0)
        got = churro["read_rows"](server, self.rows(), "OCR:", tmp_path, out, "m")
        assert server.asked == 2
        assert got["read"]["d"]["2"]["1"] == "old"

    def test_another_models_sidecar_is_not_resumed(self, tmp_path):
        out = tmp_path / "side.json"
        out.write_text(json.dumps({"model": "other", "read": {"d": {"2": {"1": "old"}}}}))
        server = self.Server(fail_on=0)
        churro["read_rows"](server, self.rows(), "OCR:", tmp_path, out, "m")
        assert server.asked == 3
