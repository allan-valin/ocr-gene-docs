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

import threading
import time

import re

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


def _cuda() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def device_for() -> str:
    """Where kraken runs: the GPU when torch can see one, else the CPU.
    Decided by the machine, not by a flag: Allan's laptop has an RTX
    4050 and read every page on the CPU for a day (2026-10-17); a friend's
    has none and must not be told to look for one. The one exception is
    the launcher's toggle, `DESEMBARQUE_DEVICE=cpu`, which keeps a card
    idle on purpose; `gpu` asks for the card and gets the CPU without one."""
    import os
    if os.environ.get("DESEMBARQUE_DEVICE", "").lower() == "cpu":
        return "cpu"
    # `cuda:0`, not `cuda`: kraken's recogniser splits the device on the
    # colon and fell over without one (segmentation took either)
    return "cuda:0" if _cuda() else "cpu"


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


_SEG = None
_SEG_LOCK = threading.Lock()


def _load_seg():
    """kraken's default segmentation model, from its package."""
    import importlib.resources as resources
    from kraken.lib import vgsl
    return vgsl.TorchVGSLModel.load_model(resources.files("kraken").joinpath("blla.mlmodel"))


def seg_model():
    """The segmentation model, loaded once: `blla.segment` given none
    loads it from disk on every page (2026-10-18)."""
    global _SEG
    with _SEG_LOCK:
        if _SEG is None:
            _SEG = _load_seg()
        return _SEG


# a blank the shape of a page, for the warm read: kraken scales what it
# segments to its input height, so a 256×64 blank became 4800×1200 and
# asked the card for 3.7 GB (OOM, 2026-10-18); a page-shaped one is
# scaled down, not up
WARM_BLANK = (1240, 1754)


def warm(model_path: Path = MODEL) -> str:
    """Load both models and segment a page-shaped blank, so the card's
    first-call cost (two minutes on the RTX 4050 with paddle resident,
    against ten seconds steady, measured 2026-10-18) is paid at start and
    not inside the first page a person asks for. Returns "" or what went
    wrong; never raises. Nothing to do without kraken or its model."""
    if not available(model_path):
        return ""
    try:
        from PIL import Image
        rec = load_model(model_path)
        seg = seg_model()
        read_page(Image.new("L", WARM_BLANK, 255), seg, rec, device=device_for())
        return ""
    except Exception as e:
        return f"kraken: {type(e).__name__}: {e}"


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


# ---- one row per written line -------------------------------------------------

BAND_TAG = "paddle-band"


def _band_of(line: dict, bands: list[tuple[float, float]]) -> int | None:
    """The band (1-based) the line's centre falls in, the widest overlap when
    two touch it; None for a line between bands or outside them."""
    yc = (line["y0"] + line["y1"]) / 2
    best, best_ov = None, 0.0
    for n, (a, b) in enumerate(bands, start=1):
        ov = min(b, line["y1"]) - max(a, line["y0"])
        if ov > best_ov and a <= yc <= b:
            best, best_ov = n, ov
    return best


def _table_extent(bands: list[tuple[float, float]]) -> tuple[float, float]:
    """Top and bottom of the rows, with half a band of slack either side."""
    if not bands:
        return 0.0, 1.0
    heights = sorted(b - a for a, b in bands)
    slack = heights[len(heights) // 2] / 2
    return min(a for a, _ in bands) - slack, max(b for _, b in bands) + slack


def _written_rows(lines: list[dict]) -> list[dict]:
    """The lines of a page grouped into the written rows they belong to.

    The segmenter finds a line per cell — the number, the name, the age,
    the trade — so a page of 33 written rows gave 201 lines (APESP p6).
    A line whose centre falls within the span of the row's first line is
    on that row, read left to right with a separator between cells; the
    first line alone decides, since a row that grew with each cell it took
    swallowed the next row (page 6, rows of two and three names). A line
    with fewer than two letters or digits (a tick, a dash, a rule) is not
    writing.
    """
    def letters(t: str) -> int:
        return sum(ch.isalnum() for ch in t)
    centre = lambda ln: (ln["y0"] + ln["y1"]) / 2   # noqa: E731
    kept = sorted((ln for ln in lines if letters(ln.get("text") or "") >= 2), key=centre)
    groups: list[list[dict]] = []
    for ln in kept:
        if groups and groups[-1][0]["y0"] <= centre(ln) <= groups[-1][0]["y1"]:
            groups[-1].append(ln)
            continue
        groups.append([ln])
    out = []
    for g in groups:
        g.sort(key=lambda m: m["x0"])
        out.append({"x0": min(m["x0"] for m in g), "x1": max(m["x1"] for m in g),
                    "y0": min(m["y0"] for m in g), "y1": max(m["y1"] for m in g),
                    "text": " · ".join((m.get("text") or "").strip() for m in g),
                    "cells": [(m["x0"], m["x1"], (m.get("text") or "").strip()) for m in g],
                    "cuts": []})
    return out


def _letters(t: str) -> int:
    return sum(ch.isalpha() for ch in t)


# the neighbours of the densest hundredth that still belong to the name
# column: at a quarter the kinship column next to it (chefe, filho, só) came
# in; at half it stays out (APESP p6, span 0.18-0.32 of the width)
_NAME_FLOOR = 0.5


def _name_span(rows: list[dict], cols: list[float] | None = None) -> tuple[float, float]:
    """Where the name column is: the stretch of the page with the most
    letters in it, from the lines themselves. Not from the sheet's column
    rules: on the page this was written for the detector's edges were
    sub-rules (0.241, 0.262) that cut the names in half. Letters are
    spread over hundredths of the width; the densest hundredth and its
    neighbours holding at least a quarter as much are the column."""
    bins = [0.0] * 100
    for r in rows:
        for x0, x1, t in r["cells"]:
            n = _letters(t)
            lo, hi = max(0, int(x0 * 100)), min(99, int(x1 * 100))
            for i in range(lo, hi + 1):
                bins[i] += n / (hi - lo + 1)
    peak = max(range(100), key=lambda i: bins[i])
    if bins[peak] <= 0:
        return 0.0, 1.0
    a = b = peak
    while a > 0 and bins[a - 1] >= _NAME_FLOOR * bins[peak]:
        a -= 1
    while b < 99 and bins[b + 1] >= _NAME_FLOOR * bins[peak]:
        b += 1
    return a / 100, (b + 1) / 100


_AGE = re.compile(r"^\d{1,2}$")
_SEX = re.compile(r"^[mfMF]$")
_CIVIL = re.compile(r"^[scvSCV]$")
_NUMBER = re.compile(r"^\d{1,4}$")
_TOKEN = re.compile(r"[^\W\d_]+|\d+")


def _tokens(text: str) -> list[str]:
    """Words and numbers apart: the segmenter hands over `v49`, `„28 m-`,
    `35If:CI` as one cell each."""
    return _TOKEN.findall(text)


def _row_from_cells(line: dict, name: tuple[float, float]) -> dict:
    """One written row's cells put in their columns by content and place
    (Allan, 2026-10-17: "everything is being put under Nome"). The name
    is the cells in the name column. A number to its left is the list
    number. To its right, token by token: a word before the age is the
    kinship (chefe, filho, só), the first one- or two-digit number is the
    age, m/f the sex, s/c/v the civil state, and the words after the age
    are nationality then trade, the order every one of these forms
    prints them in. Stored as the engine stores its column readings, so
    the page shows them as readings; `columns_by: content` says how."""
    a, b = name
    cells = line.get("cells") or []

    def overlap(x0, x1):
        return max(0.0, min(x1, b) - max(x0, a)) / max(x1 - x0, 1e-6)
    in_name = [c for c in cells if overlap(c[0], c[1]) >= 0.5]
    if not in_name and cells:
        in_name = [max(cells, key=lambda c: _letters(c[2]))]
    left = [t for c in cells if c not in in_name and (c[0] + c[1]) / 2 < a for t in [c[2]]]
    right = [t for c in cells if c not in in_name and (c[0] + c[1]) / 2 >= a for t in [c[2]]]
    # the name is the words of its cells; a number in them is the age
    # and sex the segmenter joined on (`Agostis. " 28 M.`), and goes right
    name_words, spill = [], []
    for c in in_name:
        for tok in _tokens(c[2]):
            if spill or tok.isdigit():
                spill.append(tok)
            else:
                name_words.append(tok)
    got: dict[str, str] = {}
    for t in left:
        for tok in _tokens(t):
            if _NUMBER.match(tok) and "numero" not in got:
                got["numero"] = tok
    before_age, after_age = [], []
    for tok in spill + [tok for t in right for tok in _tokens(t)]:
        if _AGE.match(tok) and "idade" not in got:
            got["idade"] = tok
        elif _SEX.match(tok) and "sexo" not in got:
            got["sexo"] = tok
        elif _CIVIL.match(tok) and "estado" not in got:
            got["estado"] = tok
        elif _letters(tok) >= 2:
            (after_age if "idade" in got else before_age).append(tok)
    # one short word before the age is the kinship (chefe, filho, só);
    # anything longer there is not, and reads on as nationality and trade
    if before_age and len(before_age[0]) <= 7:
        got["parentesco"] = before_age.pop(0)
    after_age = before_age + after_age
    if after_age:
        got["nacionalidade"] = after_age[0]
    if len(after_age) > 1:
        got["profissao"] = " ".join(after_age[1:])
    return {"name_raw": " ".join(name_words).strip(), "line": line.get("text", ""),
            "columns_by": "content",
            **({"cells": {k: {"text": v} for k, v in got.items()}} if got else {})}


def rows_from_lines(rows: list[dict], lines: list[dict], geo: dict
                    ) -> tuple[list[dict], list[list[float]]]:
    """One row per written line in the name column, and the band of each.

    The engine's bands are cut by rule and on a cursive page a band often
    holds two or three written lines (7,530 of 58,915 bands on the corpus's
    cursive pages hold two or more; 1,339 lines fall on no band), so names
    vanished as rows of their own. kraken's segmenter finds the lines; this
    makes each one a row, in page order, numbered afresh.

    What each row carries: `name_raw` is the line's text clipped to the name
    column, `read_by` says which model; the band the line sat in gives its
    reading as `second_read` and, when it held this one line only, its other
    fields (confidence, ditto marks, cells) — a band shared by two lines
    cannot say which of them its nationality belongs to. A row a person
    typed stands for the first line of its band, unchanged. The printed
    heading's band keeps its row and its lines are not names. The returned
    bands are each row's own vertical extent, in row order, which is what
    the review page paints from.
    """
    from .batch import typed_by_a_person
    cols = geo.get("columns") or []
    x0, x1 = (cols[0], cols[1]) if len(cols) >= 2 else (0.05, 0.35)
    bands = [tuple(b) for b in geo.get("rows") or [] if b and len(b) == 2]
    by_band = {r.get("n"): r for r in rows}
    heading = {n for n, r in by_band.items() if r.get("header")}
    # the table is where the bands are: a line above the first band is the
    # printed header (`NOME`, `procedente de`), one below the last is the
    # foot of the sheet, and neither is a passenger. Half a band of slack.
    top, bottom = _table_extent(bands)
    # A grid that found a fraction of the writing is wrong, not a table:
    # the APESP list's faint purple rules gave 5 bands on a page of 33
    # written lines, in a column that was not the name's, and the page came
    # out as five empty rows (2026-10-16). Then every line on the page is a
    # row carrying its whole text, with no band and no column: a name in
    # a row with its age and trade beside it is found; a name in no row is
    # not. The row says so (`whole_line`).
    written = [ln for ln in lines if (ln.get("text") or "").strip()]
    weak = len(bands) * 2 < len(written)
    drawn = bands            # where the engine's bands were, for a person's row
    name_span = None
    if weak:
        x0, x1, top, bottom, bands, heading = 0.0, 1.0, 0.0, 1.0, [], set()
        lines = _written_rows(lines)
        name_span = _name_span(lines)
    placed: dict[int | None, list[dict]] = {}
    inside = []
    for line in lines:
        if line["x1"] < x0 or line["x0"] > x1:
            continue
        yc = (line["y0"] + line["y1"]) / 2
        if not (top <= yc <= bottom):
            continue
        b = _band_of(line, bands)
        if b in heading:
            continue
        # a line the recogniser read nothing off -- a stroke of the column
        # rule, a blot at the column's edge -- is not a row; a person's row
        # in that band is kept below either way
        if not clip(line, x0, x1).strip():
            continue
        inside.append((line, b))
        placed.setdefault(b, []).append(line)
    inside.sort(key=lambda lb: lb[0]["y0"])
    out, extents = [], []
    seen_band: set[int] = set()
    for line, b in inside:
        band = by_band.get(b) if b is not None else None
        alone = b is not None and len(placed.get(b, ())) == 1
        if band is not None and b not in seen_band and typed_by_a_person(band):
            row = {k: v for k, v in band.items() if k != "n"}
        else:
            row = {"name_raw": clip(line, x0, x1).strip(), "read_by": MODEL_TAG}
            if weak:
                row.update(_row_from_cells(line, name_span))
                row["whole_line"] = True
            if band is not None:
                said = (band.get("name_raw") or "").strip()
                if said:
                    row["second_read"] = {"model": BAND_TAG, "text": said}
                if alone:
                    for k, v in band.items():
                        if k not in ("n", "name_raw", "second_read", "read_by",
                                     "given", "surname", "name_alts", "indent"):
                            row[k] = v
                elif band.get("conf") is not None:
                    row["conf"] = band["conf"]
        if b is not None:
            row["band"] = b
            seen_band.add(b)
        out.append(row)
        extents.append([round(line["y0"], 4), round(line["y1"], 4)])
    # a heading row, a person's row, and a band the engine read a name off
    # that no line fell in (the segmenter missed it, or joined it to the
    # line above) are kept where their band is: a name on the page must not
    # vanish because the better reader did not see it. Blank bands go.
    for n, r in sorted(by_band.items(), key=lambda kv: kv[0] or 0):
        if n in seen_band or n is None:
            continue
        # a distrusted grid keeps nothing of the engine's but a person's word
        if weak and not typed_by_a_person(r):
            continue
        if r.get("header") or typed_by_a_person(r) or (r.get("name_raw") or "").strip():
            a, b_ = drawn[n - 1] if 0 < n <= len(drawn) else (0.0, 0.0)
            out.append({k: v for k, v in r.items() if k != "n"} | {"band": n})
            extents.append([a, b_])
    order = sorted(range(len(out)), key=lambda i: extents[i][0])
    out = [dict(out[i], n=k) for k, i in enumerate(order, start=1)]
    extents = [extents[i] for i in order]
    return out, extents


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
        return read_page(im.convert("L"), seg_model(), model, device=device)


def read_record(record: dict, images: dict[int, Path], read=None,
                model_path: Path = MODEL, device: str | None = None,
                log=None, rerow: bool = True) -> tuple[dict, int]:
    """The record with every handwritten page read a second time, and how
    many rows got a reading. `images` maps page number to its picture;
    `read` stands in for kraken in tests (page image -> lines). With `rerow`
    each handwritten page becomes one row per written line
    (`rows_from_lines`); without it the lines are read onto the engine's
    bands as `second_read`, as the corpus passes did.

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
        device = device or device_for()
        read = lambda image: _lines_of(image, model, device)   # noqa: E731
    geo = {int(p.get("n") or 0): p.get("geometry") or {}
           for p in record.get("pages") or () if isinstance(p, dict)}
    said: dict[int, dict[int, str]] = {}
    rerowed: dict[int, tuple[list[dict], list[list[float]]]] = {}
    from . import live
    for i, n in enumerate(wanted):
        # the page watching is told which page kraken is on, of how many:
        # on a CPU this phase is two thirds of the document and the box
        # showed nothing of it (Windows test, 2026-10-17)
        live.emit({"event": "second", "page": n, "done": i, "total": len(wanted)})
        t0 = time.time()
        try:
            lines = read(images[n])
        except Exception as e:      # one page must not cost the document
            note["failed"].append({"page": n, "error": f"{type(e).__name__}: {e}"})
            if log:
                log(f"second reading of page {n} failed: {e}")
            continue
        finally:
            live.emit({"event": "second_done", "page": n, "seconds": time.time() - t0})
        if rerow:
            on_page = [r for r in record.get("rows") or () if r.get("page") == n]
            rows, extents = rows_from_lines(on_page, lines, geo.get(n, {}))
            if rows:
                rerowed[n] = (rows, extents)
                note["pages"].append(n)
                continue
            # no line in the column: the engine's bands stay, read onto
        _by_line, by_col = onto_bands(lines, geo.get(n, {}))
        said[n] = {int(k): v for k, v in by_col.items()}
        note["pages"].append(n)
    out, landed = with_second_readings(record, said, MODEL_TAG)
    if rerowed:
        out = _with_pages_rerowed(out, rerowed)
        landed += sum(len(rows) for rows, _ in rerowed.values())
        note["rerowed"] = sorted(rerowed)
    return {**out, "second_reading": note}, landed


def _with_pages_rerowed(record: dict, rerowed: dict) -> dict:
    """The record with each re-rowed page's rows and bands replaced, the
    other pages untouched and in their order."""
    rows = []
    for r in record.get("rows") or ():
        pg = r.get("page")
        if pg in rerowed:
            continue
        rows.append(r)
    for pg, (new_rows, _ext) in rerowed.items():
        rows.extend(dict(r, page=pg) for r in new_rows)
    rows.sort(key=lambda r: (int(r.get("page") or 0), int(r.get("n") or 0)))
    pages = []
    for p in record.get("pages") or ():
        if isinstance(p, dict) and p.get("n") in rerowed:
            geo = dict(p.get("geometry") or {})
            geo["rows"] = rerowed[p["n"]][1]
            geo["rows_from"] = "lines"
            p = {**p, "geometry": geo}
        pages.append(p)
    return {**record, "rows": rows, "pages": pages}
