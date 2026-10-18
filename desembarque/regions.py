"""Read only this area / column.

When the table's grid cannot be found — a form with no ruled lines, two
pages in one scan — the whole-page read returns the wrong neighbours
(APESP p.6: 5 bands for 33 lines) and the person has no recourse. Here
they draw the column(s) on the scan and only those are read: each region
is cropped and read as lines, the lines are put back in page coordinates,
and the regions' lines are aligned into rows by height, the first region
being the name. Kept under `custom[page]` beside the full reading, never
over it (Windows test report, 2026-10-17, §7).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

MIN_SIDE = 0.005   # a region thinner than half a percent of the page is a slip


def normalize(regions) -> list[dict]:
    """Regions as the page draws them, made sane: corners ordered,
    clamped to the page, the tiny dropped, anything else ignored."""
    out = []
    for r in regions or ():
        if not isinstance(r, dict):
            continue
        try:
            x0, y0, x1, y1 = (float(r[k]) for k in ("x0", "y0", "x1", "y1"))
        except (KeyError, TypeError, ValueError):
            continue
        x0, x1 = sorted((min(max(x0, 0.0), 1.0), min(max(x1, 0.0), 1.0)))
        y0, y1 = sorted((min(max(y0, 0.0), 1.0), min(max(y1, 0.0), 1.0)))
        if x1 - x0 < MIN_SIDE or y1 - y0 < MIN_SIDE:
            continue
        out.append({"x0": round(x0, 4), "y0": round(y0, 4), "x1": round(x1, 4), "y1": round(y1, 4)})
    return out


def _overlap(a: dict, b: dict) -> float:
    """How much of the shorter line's height the two share."""
    top, bottom = max(a["y0"], b["y0"]), min(a["y1"], b["y1"])
    short = min(a["y1"] - a["y0"], b["y1"] - b["y0"]) or 1e-9
    return max(0.0, bottom - top) / short


def rows_from_regions(lines_by_region: list[list[dict]], page: int | None = None) -> list[dict]:
    """The regions' lines as rows: a line joins the row whose lines it
    overlaps by half its height, one line per region per row; lines of
    one region never merge. Rows in page order, numbered from 1."""
    rows: list[dict] = []
    for i, lines in enumerate(lines_by_region):
        for ln in sorted(lines, key=lambda l: (l["y0"], l["x0"])):
            home = None
            for row in rows:
                if row["_cells"].get(i) is None and _overlap(row, ln) >= 0.5:
                    home = row
                    break
            if home is None:
                home = {"y0": ln["y0"], "y1": ln["y1"], "_cells": {}, "region": i}
                rows.append(home)
            home["_cells"][i] = ln.get("text") or ""
            home["y0"], home["y1"] = min(home["y0"], ln["y0"]), max(home["y1"], ln["y1"])
    rows.sort(key=lambda r: (r["y0"], r["region"]))
    n_regions = len(lines_by_region)
    out = []
    for k, r in enumerate(rows, 1):
        cells = [r["_cells"].get(i, "") for i in range(n_regions)]
        out.append({"n": k, "name_raw": cells[0] if cells else "", "cells": cells,
                    "y0": round(r["y0"], 4), "y1": round(r["y1"], 4),
                    "page_y": [round(r["y0"], 4), round(r["y1"], 4)],
                    "region": r["region"],
                    **({"page": page} if page else {})})
    return out


def read_regions(image: Path, regions: list[dict], read: Callable,
                 page: int | None = None) -> tuple[list[dict], list[list[dict]]]:
    """Crop each region out of the page image, read it with `read`
    (PIL image → lines in the crop's own 0–1 coordinates), put the lines
    back in page coordinates, and align them into rows. A region the
    reader fails on reads as nothing; the rest still come."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    regions = normalize(regions)
    lines_by_region: list[list[dict]] = []
    with Image.open(image) as im:
        im = im.convert("L")
        W, H = im.size
        for r in regions:
            box = (int(r["x0"] * W), int(r["y0"] * H), int(r["x1"] * W), int(r["y1"] * H))
            crop = im.crop(box)
            try:
                found = read(crop) or []
            except Exception:
                found = []
            w, h = r["x1"] - r["x0"], r["y1"] - r["y0"]
            lines_by_region.append([
                {**ln,
                 "x0": r["x0"] + float(ln["x0"]) * w, "x1": r["x0"] + float(ln["x1"]) * w,
                 "y0": r["y0"] + float(ln["y0"]) * h, "y1": r["y0"] + float(ln["y1"]) * h}
                for ln in found if ln.get("text")])
    return rows_from_regions(lines_by_region, page=page), lines_by_region
