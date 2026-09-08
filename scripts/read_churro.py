"""CHURRO, the historical-hand vision-language model, on this corpus's ink.

CHURRO is a 3B open-weight VLM trained on ~100K pages of historical documents
across 46 language clusters (arXiv 2509.19768). Every recogniser this project
has scored was a TrOCR variant, so this is a different class of model and
docs/TASKS-honest-measurement.md T6 asks the cheapest question first: **does it
run here at all**, on a 14 GB laptop with no GPU?

It runs quantised, through llama.cpp, because the released weights are 7.5 GB
in bfloat16 and this machine does not have that to spare beside a browser.
Q4_K_M is 1.9 GB and the vision projector 1.3 GB.

    # once: build llama.cpp and fetch the weights (see docs/PROGRESS.md)
    .venv/bin/python scripts/read_churro.py --serve --rows 40 --out data/churro.json
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
                 ctx: int = 8192):
        self.url = f"http://127.0.0.1:{port}"
        self.cmd = [str(LLAMA / "llama-server"), "-m", str(model),
                    "--mmproj", str(mmproj), "--port", str(port),
                    "-t", str(threads), "-c", str(ctx), "--no-warmup"]
        self.proc = None

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
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{b64}"}}]}],
            "temperature": 0.0, "n_predict": predict, "max_tokens": predict,
        }).encode()
        req = urllib.request.Request(f"{self.url}/v1/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        began = time.time()
        with urllib.request.urlopen(req, timeout=3600) as r:
            got = json.loads(r.read())
        said = got["choices"][0]["message"]["content"]
        return unwrap(said), time.time() - began


def rows_from(trainset: Path, limit: int) -> list[dict]:
    lines = [json.loads(l) for l in
             (trainset / "labels.jsonl").read_text(encoding="utf-8").splitlines() if l]
    return lines[:limit] if limit else lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", type=Path, default=None)
    ap.add_argument("--mmproj", type=Path, default=None)
    ap.add_argument("--port", type=int, default=8788)
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--serve", action="store_true",
                    help="start llama-server here and stop it after")
    ap.add_argument("--url", default="http://127.0.0.1:8788",
                    help="a server already running, if not --serve")
    ap.add_argument("--trainset", type=Path, default=ROOT / "data" / "trainset-fair")
    ap.add_argument("--rows", type=int, default=0,
                    help="how many labelled row crops to read (0 = all)")
    ap.add_argument("--pdf", type=Path, default=None,
                    help="time it on a whole page instead: the question T6 asks first")
    ap.add_argument("--page", type=int, default=2)
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "churro.json")
    a = ap.parse_args(argv)

    model = a.model or find("churro-3B.Q4_K_M.gguf")
    mmproj = a.mmproj or find("churro-3B.mmproj-f16.gguf")
    if not model or not mmproj:
        print("no CHURRO weights in the hub cache; see this file's docstring")
        return 1

    def run(server):
        if a.pdf:
            from page_geometry import page_image
            img = page_image(a.pdf, a.page, a.work)
            said, secs = server.read(Path(img), PAGE_PROMPT, predict=2048)
            print(f"whole page in {secs:.1f} s\n")
            print(said[:2000])
            payload = {"model": "churro-3B-Q4_K_M", "kind": "page",
                       "pdf": a.pdf.name, "page": a.page,
                       "seconds": secs, "text": said}
            a.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                             encoding="utf-8")
            return 0

        rows = rows_from(a.trainset, a.rows)
        read: dict[str, dict] = {}
        times = []
        for i, row in enumerate(rows, 1):
            img = a.trainset / row["image"]
            said, secs = server.read(img, ROW_PROMPT, predict=64)
            times.append(secs)
            read.setdefault(row["doc"], {}).setdefault(str(row["page"]), {})[
                str(row["n"])] = said
            print(f"  {i}/{len(rows)} {secs:5.1f}s  {said[:40]!r}"
                  f"   (label {row['label'][:30]!r})", flush=True)
        total = sum(times)
        payload = {"model": "churro-3B-Q4_K_M", "by": "row", "read": read,
                   "seconds": total, "rows": len(times),
                   "seconds_per_row": total / max(1, len(times))}
        a.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                         encoding="utf-8")
        print(f"\n{len(times)} rows in {total / 60:.1f} min — "
              f"{total / max(1, len(times)):.1f} s a row. Wrote {a.out}")
        return 0

    if a.serve:
        with Server(model, mmproj, a.port, a.threads) as s:
            return run(s)

    class Remote(Server):
        def __init__(self, url):
            self.url, self.proc = url, None
    return run(Remote(a.url))


if __name__ == "__main__":
    raise SystemExit(main())
