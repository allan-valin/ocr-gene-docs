"""A vision-language model on this corpus's ink, row by row.

Written for CHURRO and kept general, because the question CHURRO answered is
now "does a model this project may actually ship do the same?" — point
`--model` and `--mmproj` at any llama.cpp-servable VLM and the measurement is
the same one. The prompts stay CHURRO's own, so every model is asked the
question in the words the best of them was tuned for.

CHURRO itself is a 3B open-weight VLM trained on ~100K pages of historical documents
across 46 language clusters (arXiv 2509.19768). Every recogniser this project
has scored was a TrOCR variant, so this is a different class of model and
docs/TASKS-honest-measurement.md T6 asks the cheapest question first: **does it
run here at all**, on a 14 GB laptop with no GPU?

It runs quantised, through llama.cpp, because the released weights are 7.5 GB
in bfloat16 and this machine does not have that to spare beside a browser.
Q4_K_M is 1.9 GB and the vision projector 1.3 GB.

    # once: build llama.cpp and fetch the weights (see docs/PROGRESS.md)
    .venv/bin/python scripts/read_vlm.py --serve --rows 40 --out data/churro.json
    .venv/bin/python scripts/score_crops.py --sidecar data/churro.json \
        --trainset data/trainset-fair

**Its licence is not this project's licence.** CHURRO inherits Qwen-Research
terms: open weights, research use, no commercial use. Desembarque is AGPL with
a commercial licence in mind (LICENSING.md), so a number measured here is
evidence about what a page-level VLM can do, not a component that can ship.
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

HUB = Path.home() / ".cache/huggingface/hub"
LLAMA = Path.home() / "opt/llama.cpp/build/bin"

# The prompts CHURRO's own client sends, so this measures the model and not a
# guess at how to ask it: stanford-oval/Churro, src/churro_ocr/prompts/ocr.py
SYSTEM = ("You are an expert in diplomatic transcription of historical documents "
          "from various languages. Your task is to extract the full text from a "
          "given page. Only output the transcribed text between <output> and "
          "</output> tags.")
PAGE_PROMPT = (
    "Follow these instructions:\n\n"
    "1. You will be provided with a scanned document page.\n\n"
    "2. Perform transcription on the entirety of the page, converting all visible "
    "text into the following format. Include handwritten and print text, if any. "
    "Include tables, captions, headers, main text and all other visible text.\n\n"
    "3. If you encounter any non-text elements, simply skip them without attempting "
    "to describe them.\n\n"
    "4. Do not modernize or standardize the text.\n\n"
    "5. When you come across text in languages other than English, transcribe it as "
    "accurately as possible without translation.\n\n"
    "6. Output the OCR result in the following format:\n\n"
    "<output>\nextracted text here\n</output>")
# a row crop is not a page, and asking for a page's worth of structure from one
# line of writing invites the model to invent the rest of the form
ROW_PROMPT = ("This is a single line cut from a scanned passenger list: one "
              "person's name. Transcribe exactly what is written, and nothing "
              "else, between <output> and </output> tags.")
# The name column of a page, in one look. This is the shape that would pay:
# one inference for forty rows instead of forty, and the reading order carries
# the row numbering with it -- which is the pairing problem that made every
# character-error figure before 2026-09-04 a name scored against a neighbour.
STRIP_PROMPT = ("This is the name column cut from a scanned passenger list. "
                "Transcribe every name you can read, one per line, in the "
                "order they appear down the page. Write nothing else: no "
                "numbering, no table, no commentary. If a line is illegible, "
                "write a single ? for it. Put the whole list between <output> "
                "and </output> tags.")


# How each model is asked. A model is measured the way its own card asks it:
# CHURRO's client sends a persona and wants tags, PaddleOCR-VL's card sends the
# two characters `OCR:` and nothing else -- it is a recogniser with a chat
# template, not a chat model, and a system message it never saw only costs tokens.
# DeepSeek-OCR (Apache-2.0, 3B MoE) is prompted `<image>\nFree OCR.` -- the
# picture first, then the words. Its GGUF carries no chat template; llama.cpp's
# `deepseek-ocr` template wraps nothing and joins the image marker to the text
# with no newline, so the newline is the prompt's own.
STYLES = {
    "churro": {"system": SYSTEM, "row": ROW_PROMPT},
    "paddleocr": {"system": None, "row": "OCR:"},
    "deepseek-ocr": {"system": None, "row": "\nFree OCR.", "image_first": True,
                     "chat_template": "deepseek-ocr"},
}


def messages(prompt: str, b64: str, system: str | None = SYSTEM,
             image_first: bool = False) -> list[dict]:
    """The chat turn a crop is read with: a persona only if the model has one,
    the picture before or after the words as the model's card has it."""
    out = []
    if system:
        out.append({"role": "system", "content": system})
    parts = [{"type": "text", "text": prompt},
             {"type": "image_url",
              "image_url": {"url": f"data:image/png;base64,{b64}"}}]
    if image_first:
        parts.reverse()
    out.append({"role": "user", "content": parts})
    return out


def find(pattern: str) -> Path | None:
    got = sorted(HUB.glob(f"**/{pattern}"))
    return got[-1] if got else None


def unwrap(text: str) -> str:
    """What the model put between the tags it was asked to use."""
    out = text.strip()
    if "<output>" in out:
        out = out.split("<output>", 1)[1]
    if "</output>" in out:
        out = out.split("</output>", 1)[0]
    return out.strip()


class Server:
    """A llama-server holding the model, so a hundred crops load it once."""

    def __init__(self, model: Path, mmproj: Path, port: int, threads: int,
                 ctx: int = 8192, system: str | None = SYSTEM,
                 image_first: bool = False, chat_template: str | None = None):
        self.url = f"http://127.0.0.1:{port}"
        self.system = system
        self.image_first = image_first
        self.cmd = [str(LLAMA / "llama-server"), "-m", str(model),
                    "--mmproj", str(mmproj), "--port", str(port),
                    "-t", str(threads), "-c", str(ctx), "--no-warmup"]
        if chat_template:
            # llama-server renders chat with jinja by default, and a built-in
            # template name only works through the legacy engine: with jinja
            # the image part is dropped and the server says 400.
            self.cmd += ["--no-jinja", "--chat-template", chat_template]
        self.proc = None

    @classmethod
    def from_style(cls, model: Path, mmproj: Path, port: int, threads: int,
                   style: dict, **kw) -> "Server":
        """A server asked the way one of STYLES asks."""
        return cls(model, mmproj, port, threads, system=style["system"],
                   image_first=bool(style.get("image_first")),
                   chat_template=style.get("chat_template"), **kw)

    def turn(self, prompt: str, b64: str) -> list[dict]:
        return messages(prompt, b64, getattr(self, "system", SYSTEM),
                        getattr(self, "image_first", False))

    def __enter__(self):
        log = open(ROOT / "data" / "churro-server.log", "w")
        self.proc = subprocess.Popen(self.cmd, stdout=log, stderr=log)
        for _ in range(600):
            try:
                with urllib.request.urlopen(f"{self.url}/health", timeout=2) as r:
                    if r.status == 200:
                        return self
            except (urllib.error.URLError, OSError):
                time.sleep(1)
        raise RuntimeError("llama-server did not come up; see data/churro-server.log")

    def __exit__(self, *_):
        if self.proc:
            self.proc.terminate()
            self.proc.wait(timeout=30)

    def read(self, image: Path, prompt: str, predict: int = 512) -> tuple[str, float]:
        b64 = base64.b64encode(image.read_bytes()).decode()
        body = json.dumps({
            "messages": self.turn(prompt, b64),
            "temperature": 0.0, "n_predict": predict, "max_tokens": predict,
        }).encode()
        req = urllib.request.Request(f"{self.url}/v1/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        began = time.time()
        with urllib.request.urlopen(req, timeout=3600) as r:
            got = json.loads(r.read())
        said = got["choices"][0]["message"]["content"]
        return unwrap(said), time.time() - began


def hand_of(truth_dir: Path) -> dict[str, str]:
    """Which hand each truth page is written in, keyed by its file name."""
    out = {}
    for f in sorted(Path(truth_dir).glob("*.json")):
        try:
            out[f.name] = json.loads(f.read_text(encoding="utf-8")).get("hand") or ""
        except (OSError, ValueError):
            continue
    return out


def rows_from(trainset: Path, limit: int, hand: str = "",
              hands: dict[str, str] | None = None) -> list[dict]:
    """The labelled rows to read, optionally only those of one hand.

    A model is worth ranking on the pages it is for. The engine is far better
    on typed pages and far worse on cursive ones, so a mean over both says
    less than either half, and an hour of machine spent on typed rows to
    confirm the engine wins there is an hour wasted.
    """
    lines = [json.loads(l) for l in
             (trainset / "labels.jsonl").read_text(encoding="utf-8").splitlines() if l]
    if hand:
        by_page = hands if hands is not None else hand_of(ROOT / "data" / "truth")
        lines = [r for r in lines if by_page.get(r.get("source") or "") == hand]
    return lines[:limit] if limit else lines


def pick_documents(hands: dict, hand: str = "", limit: int = 0) -> list[str]:
    """Which scans to spend the seconds on, in name order.

    A row costs 4 to 9 seconds, so the whole corpus is 85 to 170 hours and
    choosing is the design rather than a convenience. `data/hands.json` says
    which documents are cursive; those are the ones a VLM is worth paying for,
    and a document whose hand could not be called is not one of them.
    """
    got = [f for f, v in sorted(hands.items())
           if not hand or (v.get("document") == hand)]
    return got[:limit] if limit else got


def done_already(said: dict, doc: str, page: int) -> bool:
    """Has this page been read in a previous run of the same pass?

    A page that read as nothing counts as done: that is a reading and not an
    absence, and re-reading it every restart would never finish.
    """
    return str(page) in (said.get(doc) or {})


def read_document(server, pdf: Path, record: dict, work: Path, said: dict,
                  doc: str, prompt: str = ROW_PROMPT, on_page=None,
                  pages_limit: int = 0, only: set[int] | None = None) -> int:
    """Read every row of every page of one scan. Returns rows read.

    The crops are cut from the geometry the record already carries, by the
    same function the review screen uses, so the VLM is handed exactly the
    picture the engine read and a reading can be put back on the right row.
    """
    from PIL import Image
    from page_geometry import page_image
    from desembarque.bandcrops import crops_for

    pages = {p.get("n"): p.get("geometry") for p in (record.get("pages") or ())
             if p.get("geometry")}
    rows_read, seen = 0, 0
    for page in sorted(pages):
        if only is not None and page not in only:
            continue
        if done_already(said, doc, page):
            continue
        if pages_limit and seen >= pages_limit:
            break
        seen += 1
        img = page_image(pdf, page, work)
        if img is None:
            continue
        crops = crops_for(Path(img), pages[page])
        if not crops:
            said.setdefault(doc, {})[str(page)] = {}
            continue
        got, began = {}, time.time()
        for n, band in sorted(crops.items()):
            tmp = work / f"{doc[:8]}-p{page}-r{n}.png"
            band["carved"].convert("RGB").save(tmp)
            text, _ = server.read(tmp, prompt, predict=64)
            tmp.unlink(missing_ok=True)
            if text:
                got[str(n)] = text
        said.setdefault(doc, {})[str(page)] = got
        rows_read += len(got)
        if on_page:
            on_page(doc, page, len(got), time.time() - began)
    return rows_read


def read_rows(server, rows: list[dict], prompt: str, trainset: Path, out: Path,
              tag: str) -> dict:
    """Read the labelled crops one by one, saving after each.

    A row the server cannot answer -- llama-server says 500 when a model
    emits half a multibyte character -- is recorded as nothing read and the
    pass goes on, because 131 readings lost to the 132nd is a run wasted.
    A sidecar already on disk for the same model is resumed, not redone.
    """
    read: dict[str, dict] = {}
    seconds, done = 0.0, 0
    if out.exists():
        try:
            was = json.loads(out.read_text(encoding="utf-8"))
            if was.get("model") == tag:
                read = was.get("read") or {}
                seconds, done = float(was.get("seconds") or 0), int(was.get("rows") or 0)
        except ValueError:
            pass

    def save():
        out.write_text(json.dumps({"model": tag, "by": "row", "read": read,
                                   "seconds": seconds, "rows": done,
                                   "seconds_per_row": seconds / max(1, done)},
                                  ensure_ascii=False, indent=1), encoding="utf-8")

    for i, row in enumerate(rows, 1):
        page = read.setdefault(row["doc"], {}).setdefault(str(row["page"]), {})
        if str(row["n"]) in page:
            continue
        img = trainset / row["image"]
        try:
            said, secs = server.read(img, prompt, predict=64)
        except urllib.error.HTTPError as e:
            said, secs = "", 0.0
            print(f"  {i}/{len(rows)} the server refused this row: {e}", flush=True)
        page[str(row["n"])] = said
        seconds += secs
        done += 1
        save()
        print(f"  {i}/{len(rows)} {secs:5.1f}s  {said[:40]!r}"
              f"   (label {row['label'][:30]!r})", flush=True)
    save()
    return {"model": tag, "by": "row", "read": read, "seconds": seconds,
            "rows": done, "seconds_per_row": seconds / max(1, done)}


def whole_documents(server, a, tag: str, prompt: str = ROW_PROMPT) -> int:
    """The 'read this one properly' pass, over documents rather than crops."""
    hands = json.loads(a.hands.read_text(encoding="utf-8")) if a.hands.exists() else {}
    if not hands:
        print(f"no {a.hands}: run scripts/classify_hands.py first")
        return 1
    said: dict[str, dict] = {}
    if a.out.exists():
        try:
            was = json.loads(a.out.read_text(encoding="utf-8"))
            if was.get("model") == tag:
                said = was.get("read") or {}
                print(f"resuming: {sum(len(v) for v in said.values())} pages read")
        except ValueError:
            pass

    def note(doc, page, rows, secs):
        print(f"  {doc[:8]} p{page}: {rows} rows in {secs:.0f}s", flush=True)

    wanted = None
    if a.pages_json:
        asked = json.loads(a.pages_json.read_text(encoding="utf-8"))
        wanted = {}
        for row in asked:
            wanted.setdefault(row["pdf"], set()).add(int(row["page"]))

    began, total = time.time(), 0
    names = sorted(wanted) if wanted else pick_documents(hands, a.hand,
                                                        a.documents_limit)
    for name in names:
        pdf = a.scans / name
        rec = a.records / f"{hands[name]['hash']}.json"
        if not pdf.exists() or not rec.exists():
            print(f"  {name}: not on disk, skipped")
            continue
        record = json.loads(rec.read_text(encoding="utf-8"))
        total += read_document(server, pdf, record, a.work, said,
                               hands[name]["hash"], prompt=prompt, on_page=note,
                               pages_limit=a.pages_limit,
                               only=wanted.get(name) if wanted else None)
        a.out.write_text(json.dumps({"model": tag, "by": "row",
                                     "variant": "carved", "read": said},
                                    ensure_ascii=False), encoding="utf-8")
    print(f"\n{total} rows in {(time.time() - began) / 60:.1f} min. Wrote {a.out}"
          "\nPut it on the rows:  .venv/bin/python scripts/apply_second_opinion.py "
          f"--sidecar {a.out} --write")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", type=Path, default=None)
    ap.add_argument("--mmproj", type=Path, default=None)
    ap.add_argument("--style", choices=sorted(STYLES), default="churro",
                    help="how the model is asked: the CHURRO/Qwen persona with "
                         "<output> tags, or PaddleOCR-VL's bare `OCR:`")
    ap.add_argument("--port", type=int, default=8788)
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--serve", action="store_true",
                    help="start llama-server here and stop it after")
    ap.add_argument("--url", default="http://127.0.0.1:8788",
                    help="a server already running, if not --serve")
    ap.add_argument("--trainset", type=Path, default=ROOT / "data" / "trainset-fair")
    ap.add_argument("--hand", default="",
                    help="read only the rows of pages written in this hand "
                         "(typed, cursive), per each truth file's own label")
    ap.add_argument("--rows", type=int, default=0,
                    help="how many labelled row crops to read (0 = all)")
    ap.add_argument("--pdf", type=Path, default=None,
                    help="time it on a whole page instead: the question T6 asks first")
    ap.add_argument("--page", type=int, default=2)
    ap.add_argument("--strip", action="store_true",
                    help="with --pdf: read the name column in one look rather "
                         "than the whole page")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "churro.json")
    ap.add_argument("--documents", action="store_true",
                    help="read whole documents out of the corpus rather than "
                         "the labelled crops: the 'read this one properly' "
                         "pass. Resumable, and writes the same sidecar shape "
                         "`apply_second_opinion.py` takes")
    ap.add_argument("--records", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--hands", type=Path, default=ROOT / "data" / "hands.json")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--documents-limit", type=int, default=1,
                    help="how many documents to read this run")
    ap.add_argument("--pages-limit", type=int, default=0,
                    help="stop after this many pages of each document")
    ap.add_argument("--pages-json", type=Path, default=None,
                    help="read exactly these pages: a JSON list of "
                         "{pdf, page}. This is how the held-out draw is read — "
                         "the same pages the reading sheet put in front of a "
                         "person, and no others")
    a = ap.parse_args(argv)

    model = a.model or find("churro-3B.Q4_K_M.gguf")
    mmproj = a.mmproj or find("churro-3B.mmproj-f16.gguf")
    if not model or not mmproj:
        print("no CHURRO weights in the hub cache; see this file's docstring")
        return 1

    tag = model.name.replace("churro-3B.", "churro-3B-").replace(".gguf", "")
    style = STYLES[a.style]

    def run(server):
        if a.pdf:
            from page_geometry import page_image
            if a.strip:
                from spike_speed import name_strip
                strip, rel, _, _ = name_strip(a.pdf, a.page, a.work)
                img = a.work / f"{a.pdf.stem}-p{a.page}-churro.png"
                strip.save(img)
                said, secs = server.read(Path(img), STRIP_PROMPT, predict=1024)
                print(f"name column ({len(rel)} bands) in {secs:.1f} s\n")
            else:
                img = page_image(a.pdf, a.page, a.work)
                said, secs = server.read(Path(img), PAGE_PROMPT, predict=2048)
                print(f"whole page in {secs:.1f} s\n")
            print(said[:2000])
            payload = {"model": tag,
                       "kind": "strip" if a.strip else "page",
                       "pdf": a.pdf.name, "page": a.page,
                       "seconds": secs, "text": said}
            a.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                             encoding="utf-8")
            return 0

        if a.documents:
            return whole_documents(server, a, tag, prompt=style["row"])
        rows = rows_from(a.trainset, a.rows, hand=a.hand)
        payload = read_rows(server, rows, style["row"], a.trainset, a.out, tag)
        total, times = payload["seconds"], range(payload["rows"])
        print(f"\n{len(times)} rows in {total / 60:.1f} min — "
              f"{total / max(1, len(times)):.1f} s a row. Wrote {a.out}")
        return 0

    if a.serve:
        with Server.from_style(model, mmproj, a.port, a.threads, style) as s:
            return run(s)

    class Remote(Server):
        def __init__(self, url):
            self.url, self.proc, self.system = url, None, style["system"]
            self.image_first = bool(style.get("image_first"))
    return run(Remote(a.url))


if __name__ == "__main__":
    raise SystemExit(main())
