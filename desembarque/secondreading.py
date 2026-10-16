"""The second reading of a document's handwritten pages, at index time.

The engine cuts a page into bands and reads each band; on cursive pages
that reading is mostly noise (`Taurte`, `escaleebatuo`). kraken's page
segmenter finds the written lines instead, and Kiessling's PP-OCRv6
medium for kraken (Apache-2.0, Zenodo 21788410) reads those lines well
enough to lift the held-out cursive names found in the top five from 64 to
107 of 212 (2026-10-12). Until 2026-10-16 that reading was an offline pass
over the corpus on one machine, in a venv of its own, so an install made
from the launcher read cursive pages with the engine alone and showed the
noise. This runs it on each document as it is indexed, when kraken and its
model are installed, and writes what it read onto the rows as
`second_read` — the slot `desembarque.search` already spells a row by.

Only the pages the stored reading calls cursive or unknown
(`hands.label_page`) are read: on typed pages the engine is the better
reader. A document indexed without kraken is not wrong, only poorer, so
nothing here raises past `read_record`; the record says in `second_reading`
whether the pass ran.
"""
from __future__ import annotations

import unicodedata
import warnings
from pathlib import Path

from . import hands
from .secondopinion import with_second_readings

MODEL_TAG = "PP-OCRv6-hist-medium-page-column"
MODEL_DIR = Path.home() / ".cache" / "kraken" / "ppocrv6-hist"
MODEL = MODEL_DIR / "medium.safetensors"
MODEL_URL = "https://zenodo.org/api/records/21788410/files/medium.safetensors/content"
MODEL_BYTES = 63_779_644
HANDS_READ = (hands.CURSIVE, hands.UNKNOWN)
_MODEL = None


def kraken_installed() -> bool:
    try:
        import kraken  # noqa: F401
        import torch   # noqa: F401
    except ImportError:
        return False
    return True


def available(model: Path = MODEL) -> bool:
    return kraken_installed() and model.exists()


def status(model: Path = MODEL) -> dict:
    if not kraken_installed():
        return {"available": False, "detail": "kraken is not installed"}
    if not model.exists():
        return {"available": False, "detail": f"no model at {model}"}
    return {"available": True, "detail": MODEL_TAG}


def fetch_model(dest: Path = MODEL, url: str = MODEL_URL) -> Path:
    """Download the recogniser weights once, to where kraken keeps models."""
    import urllib.request
    if dest.exists() and dest.stat().st_size == MODEL_BYTES:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    tmp.replace(dest)
    return dest


def load_model(path: Path = MODEL):
    """The recogniser, loaded once per process. kraken >= 7.1 reads the
    `.safetensors` PP-OCRv6 weights through `load_models`."""
    global _MODEL
    if _MODEL is None:
        from kraken.models import load_models
        _MODEL = load_models(path, tasks=["recognition"])[0]
    return _MODEL


# ---- one page: lines, then the name column of each band --------------------

def line_record(line, rec, width: int, height: int) -> dict:
    """One segmented line as the corpus pass stores it: its box, polygon and
    baseline, as fractions of the page, and what the recogniser said with
    where each character sits (so a column can be clipped out afterwards)."""
    xs = [p[0] for p in line.boundary]
    ys = [p[1] for p in line.boundary]
    cuts, text = [], ""
    if rec is not None:
        for cut in rec.cuts:
            pts = cut if isinstance(cut[0], (list, tuple)) else [cut]
            cuts.append(sum(p[0] for p in pts) / len(pts) / width)
        text = unicodedata.normalize("NFC", rec.prediction)
    return {"x0": min(xs) / width, "x1": max(xs) / width,
            "y0": min(ys) / height, "y1": max(ys) / height,
            "text": text, "cuts": cuts,
            "boundary": [[x / width, y / height] for x, y in line.boundary],
            "baseline": [[x / width, y / height] for x, y in (line.baseline or [])]}


def _predictions(model, im, seg, pad: int, device: str):
    """Records for every line of `seg`, from a 7.1 model's `.predict` or the
    older `rpred` — both yield records with a prediction and cuts."""
    if hasattr(model, "prepare_for_inference"):
        from kraken.configs import RecognitionInferenceConfig
        from kraken.ketos.util import to_ptl_device
        accelerator, devices = to_ptl_device(device)
        model.prepare_for_inference(RecognitionInferenceConfig(
            padding=pad, accelerator=accelerator, device=devices, num_line_workers=0))
        return model.predict(im, seg)
    from kraken import rpred
    return rpred.rpred(model, im, seg, pad=pad)


def read_page(im, seg_model, rec_model, pad: int = 8, device: str = "cpu") -> list[dict]:
    """Every line on the page: its box, its polygon, its text and where each
    character is. `rec_model` None only segments (a typed page)."""
    from kraken import blla
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        seg = (blla.segment(im, model=seg_model, device=device) if seg_model
               else blla.segment(im, device=device))
        if rec_model is None:
            return [line_record(line, None, im.width, im.height) for line in seg.lines]
        return [line_record(line, rec, im.width, im.height)
                for rec, line in zip(_predictions(rec_model, im, seg, pad, device),
                                     seg.lines)]


def clip(line: dict, x0: float, x1: float) -> str:
    """The characters of a line whose cuts fall inside the column."""
    text, cuts = line["text"], line["cuts"]
    if len(cuts) != len(text):
        # no per-character geometry: keep the whole line if it is mostly inside
        mid = (line["x0"] + line["x1"]) / 2
        return text if x0 <= mid <= x1 else ""
    return "".join(c for c, x in zip(text, cuts) if x0 <= x <= x1)


def onto_bands(lines: list[dict], geo: dict) -> tuple[dict, dict]:
    """Each band's text, two ways, from the lines that cross the name column:
    the whole line, and the part of it inside the column."""
    cols = geo.get("columns") or []
    x0, x1 = (cols[0], cols[1]) if len(cols) >= 2 else (0.05, 0.35)
    bands = [tuple(b) for b in geo.get("rows") or [] if b and len(b) == 2]
    by_line, by_col = {}, {}
    for line in lines:
        if line["x1"] < x0 or line["x0"] > x1:
            continue
        yc = (line["y0"] + line["y1"]) / 2
        best, best_ov = None, 0.0
        for n, (a, b) in enumerate(bands, start=1):
            ov = min(b, line["y1"]) - max(a, line["y0"])
            if ov > best_ov and a <= yc <= b:
                best, best_ov = n, ov
        if best is None:
            continue
        col = clip(line, x0, x1).strip()
        whole = line["text"].strip()
        if whole:
            by_line[str(best)] = (by_line.get(str(best), "") + " " + whole).strip()
        if col:
            by_col[str(best)] = (by_col.get(str(best), "") + " " + col).strip()
    return by_line, by_col


# ---- one document ----------------------------------------------------------

def pages_to_read(record: dict) -> list[int]:
    """The pages whose stored rows read as cursive or unknown and that have a
    grid to put lines onto. A page with no rows has no bands to name."""
    by_page: dict[int, list[dict]] = {}
    for r in record.get("rows") or ():
        if r.get("page"):
            by_page.setdefault(int(r["page"]), []).append(r)
    geo = {int(p.get("n") or 0): p.get("geometry") or {}
           for p in record.get("pages") or () if isinstance(p, dict)}
    return [n for n in sorted(by_page)
            if hands.label_page(by_page[n]) in HANDS_READ and geo.get(n, {}).get("rows")]


def _lines_of(image: Path, model, device: str) -> list[dict]:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(image) as im:
        return read_page(im.convert("L"), None, model, device=device)


def read_record(record: dict, images: dict[int, Path], read=None,
                model_path: Path = MODEL, device: str = "cpu",
                log=None) -> tuple[dict, int]:
    """The record with every handwritten page read a second time, and how
    many rows got a reading. `images` maps page number to its picture;
    `read` stands in for kraken in tests (page image -> lines).

    Never raises: a page kraken cannot read keeps the engine's rows, and the
    record notes under `second_reading` what happened, since a document
    silently read by one engine looks exactly like one read by two.
    """
    wanted = [n for n in pages_to_read(record) if n in images]
    note = {"model": MODEL_TAG, "pages": [], "failed": []}
    if not wanted:
        return {**record, "second_reading": note}, 0
    if read is None:
        if not available(model_path):
            return {**record, "second_reading": {**note, "skipped": status(model_path)["detail"]}}, 0
        model = load_model(model_path)
        read = lambda image: _lines_of(image, model, device)   # noqa: E731
    geo = {int(p.get("n") or 0): p.get("geometry") or {}
           for p in record.get("pages") or () if isinstance(p, dict)}
    said: dict[int, dict[int, str]] = {}
    for n in wanted:
        try:
            lines = read(images[n])
        except Exception as e:      # one page must not cost the document
            note["failed"].append({"page": n, "error": f"{type(e).__name__}: {e}"})
            if log:
                log(f"second reading of page {n} failed: {e}")
            continue
        _by_line, by_col = onto_bands(lines, geo.get(n, {}))
        said[n] = {int(k): v for k, v in by_col.items()}
        note["pages"].append(n)
    out, landed = with_second_readings(record, said, MODEL_TAG)
    return {**out, "second_reading": note}, landed
