"""Throwaway spike (2026-10-08): read the whole page, then find the column.

Allan's reading of the first held-out sheet showed that half the pages had
been cut at the ordinal strip, and asked whether the pipeline should instead
transcribe the entire page and sort the text into columns afterwards. This
measures the cheap version of that: kraken's page segmenter (blla) finds
every line on the page with its coordinates, McFondue reads each line with
per-character cut positions, and the name column is then taken off the page
by geometry alone -- the characters whose cuts fall inside the stored name
column -- with no language model in the loop. Two sidecars come out, keyed to
the engine's bands by vertical overlap so `bench_search.py --held-out
--second-opinion` scores them through the index like every other reading:

  * `line`   -- the whole segmented line that crosses the name column
  * `column` -- that line clipped to the name column by its cuts

    .venv-kraken/bin/python scripts/spike_fullpage.py --out data/fullpage-heldout
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]


def record_for(records: Path, pdf: str) -> dict | None:
    for f in records.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if d.get("file") == pdf:
            return d
    return None


def chosen_image(work: Path, pdf: str, page: int) -> Path | None:
    f = work / f"{Path(pdf).stem}-p{page}-chosen.txt"
    if not f.exists():
        return None
    p = Path(f.read_text(encoding="utf-8").strip())
    return p if p.exists() else None


def line_record(line, rec, width: int, height: int) -> dict:
    """One segmented line as the pass stores it: its box, its polygon and
    baseline (so another recogniser can read the same ink without the 12 s
    of segmenting again), and what this recogniser said, with where each
    character sits."""
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


def read_page(im, seg_model, rec_model, pad: int = 8, device: str = "cpu") -> list[dict]:
    """Every line on the page: its box, its polygon, its text and where each character is."""
    from kraken import blla, rpred
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        seg = (blla.segment(im, model=seg_model, device=device) if seg_model
               else blla.segment(im, device=device))
        if rec_model is None:
            return [line_record(line, None, im.width, im.height) for line in seg.lines]
        return [line_record(line, rec, im.width, im.height)
                for rec, line in zip(rpred.rpred(rec_model, im, seg, pad=pad), seg.lines)]


def clip(line: dict, x0: float, x1: float) -> str:
    """The characters of a line whose cuts fall inside the column."""
    text, cuts = line["text"], line["cuts"]
    if len(cuts) != len(text):
        # no per-character geometry: keep the whole line if it is mostly inside
        mid = (line["x0"] + line["x1"]) / 2
        return text if x0 <= mid <= x1 else ""
    return "".join(c for c, x in zip(text, cuts) if x0 <= x <= x1)


def onto_bands(lines: list[dict], geo: dict) -> tuple[dict, dict]:
    """Each band's text, two ways, from the lines that cross the name column."""
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--truth", type=Path, default=ROOT / "data" / "truth-heldout")
    ap.add_argument("--records", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--model", type=Path,
                    default=Path.home() / ".cache/kraken/ManuMcFondue.mlmodel")
    ap.add_argument("--out", type=Path, required=True,
                    help="prefix: writes <out>-line.json, <out>-column.json, "
                         "<out>-lines.json")
    a = ap.parse_args(argv)

    from PIL import Image
    from kraken.lib import models
    rec_model = models.load_any(str(a.model))

    pages = []
    for f in sorted(a.truth.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        pages.append((d["pdf"], int(d["page"])))

    line_side, col_side, raw = {}, {}, {}
    total = 0.0
    for pdf, page in pages:
        rec = record_for(a.records, pdf)
        img = chosen_image(a.work, pdf, page)
        if rec is None or img is None:
            print(f"  {pdf} p{page}: no record or no image, skipped")
            continue
        geo = next((p.get("geometry") for p in rec.get("pages") or ()
                    if int(p.get("n") or 0) == page), None) or {}
        began = time.time()
        im = Image.open(img).convert("L")
        lines = read_page(im, None, rec_model)
        secs = time.time() - began
        total += secs
        by_line, by_col = onto_bands(lines, geo)
        doc = rec["hash"]
        line_side.setdefault(doc, {})[str(page)] = by_line
        col_side.setdefault(doc, {})[str(page)] = by_col
        raw.setdefault(doc, {})[str(page)] = lines
        print(f"  {pdf[16:28]} p{page}: {len(lines)} lines, {len(by_col)} bands "
              f"with column text, {secs:.0f}s", flush=True)

    tag = a.model.stem
    for name, side in (("line", line_side), ("column", col_side)):
        p = a.out.with_name(a.out.name + f"-{name}.json")
        p.write_text(json.dumps({"model": f"{tag}-page-{name}", "by": "row",
                                 "variant": name, "read": side}, ensure_ascii=False))
        print(f"wrote {p}")
    p = a.out.with_name(a.out.name + "-lines.json")
    p.write_text(json.dumps(raw, ensure_ascii=False))
    print(f"wrote {p}\n{len(pages)} pages in {total:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
