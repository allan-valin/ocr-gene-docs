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
    placed: dict[int | None, list[dict]] = {}
    inside = []
    for line in lines:
        if line["x1"] < x0 or line["x0"] > x1:
            continue
        b = _band_of(line, bands)
        if b in heading:
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
    # a heading row, and a person's row whose band no line fell in, are kept
    # where their band is
    for n, r in sorted(by_band.items(), key=lambda kv: kv[0] or 0):
        if n in seen_band or n is None:
            continue
        if r.get("header") or typed_by_a_person(r):
            a, b_ = bands[n - 1] if 0 < n <= len(bands) else (0.0, 0.0)
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
        return read_page(im.convert("L"), None, model, device=device)


def read_record(record: dict, images: dict[int, Path], read=None,
                model_path: Path = MODEL, device: str = "cpu",
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
        read = lambda image: _lines_of(image, model, device)   # noqa: E731
    geo = {int(p.get("n") or 0): p.get("geometry") or {}
           for p in record.get("pages") or () if isinstance(p, dict)}
    said: dict[int, dict[int, str]] = {}
    rerowed: dict[int, tuple[list[dict], list[list[float]]]] = {}
    for n in wanted:
        try:
            lines = read(images[n])
        except Exception as e:      # one page must not cost the document
            note["failed"].append({"page": n, "error": f"{type(e).__name__}: {e}"})
            if log:
                log(f"second reading of page {n} failed: {e}")
            continue
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
