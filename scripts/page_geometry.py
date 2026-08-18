"""Deskew a scanned manifest page and recover its table geometry.

Row bands drive the review UI's synchronized scrolling and the name-column
crops, so they need to be better calibrated than a VLM's self-reported guess.
On a ruled printed form they can be measured instead.

Two things make this work on this corpus:

* These PDFs are MRC-compressed, so each page carries a soft mask holding the
  sharp bilevel text and rules, separate from the blurry background layer.
  The mask is the right input for geometry (the base layer is not).
* Pages are scanned with a fraction of a degree of skew, which is enough to
  smear a vertical rule across ~26px and erase it from a column projection.
  Deskewing first took the projection peak from 0.26 to 0.66 on the sample.

Not every document in the corpus is a ruled table, so this is a fast path, not
the only path: callers fall back to VLM-reported bands when `detect_rules`
comes back empty.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

SEARCH_DEG = 1.5
COARSE_STEP = 0.05


def ink_mask(im: Image.Image | np.ndarray, deskew: bool = False) -> np.ndarray:
    """Boolean array, True where there is ink.

    Accepts either a normal page (dark ink on light paper) or an already
    inverted soft mask, and normalizes polarity: ink is always the minority.
    """
    if isinstance(im, Image.Image):
        a = np.asarray(im.convert("L"), dtype=np.float32) / 255.0
    else:
        a = np.asarray(im, dtype=np.float32)
        if a.max() > 1.0:
            a = a / 255.0
    m = a < 0.5
    if m.mean() > 0.5:  # inverted soft mask
        m = ~m
    if deskew:
        ang = estimate_skew(m)
        m = rotate_mask(m, ang)
    return m


def rotate_mask(mask: np.ndarray, angle: float) -> np.ndarray:
    im = Image.fromarray((mask * 255).astype(np.uint8))
    r = im.rotate(angle, resample=Image.BICUBIC, fillcolor=0)
    return np.asarray(r, dtype=np.float32) / 255.0 > 0.5


def _sharpness(mask: np.ndarray) -> float:
    """How concentrated the projections are; maximal when rules are axis-aligned."""
    return float(mask.sum(axis=0).max() + mask.sum(axis=1).max())


def estimate_skew(mask: np.ndarray, search: float = SEARCH_DEG) -> float:
    """Rotation in degrees that best aligns the page's rules with the axes."""
    h, w = mask.shape
    scale = max(1, int(max(h, w) / 900))
    small = mask
    if scale > 1:
        im = Image.fromarray((mask * 255).astype(np.uint8))
        small = (
            np.asarray(im.resize((w // scale, h // scale), Image.BILINEAR), dtype=np.float32)
            / 255.0
            > 0.5
        )

    def best_over(lo: float, hi: float, step: float) -> float:
        angles = np.arange(lo, hi + step / 2, step)
        scores = [_sharpness(rotate_mask(small, a)) for a in angles]
        return float(angles[int(np.argmax(scores))])

    coarse = best_over(-search, search, COARSE_STEP)
    return round(best_over(coarse - COARSE_STEP, coarse + COARSE_STEP, 0.01), 3)


def _peaks(profile: np.ndarray, threshold: float, tol: int = 10) -> list[int]:
    idx = np.where(profile > threshold)[0]
    if not len(idx):
        return []
    groups: list[list[int]] = []
    for i in idx:
        if groups and i - groups[-1][-1] <= tol:
            groups[-1].append(int(i))
        else:
            groups.append([int(i)])
    return [int(np.mean(g)) for g in groups]


def comb_fit(observed: list[int], max_missing_ratio: float = 0.5) -> list[float] | None:
    """Fill rules dropped by faint ink, assuming an evenly pitched table.

    Returns the complete evenly spaced sequence spanning the observed range, or
    None when the spacing is not periodic enough to justify the assumption.
    """
    if len(observed) < 3:
        return None
    ys = sorted(observed)
    gaps = np.diff(ys)
    pitch = float(np.median(gaps))
    if pitch <= 0:
        return None
    # every gap should be a near-integer multiple of the pitch
    mult = gaps / pitch
    err = np.abs(mult - np.round(mult))
    if np.median(err) > 0.15 or np.max(np.round(mult)) > 6:
        return None
    n = int(round((ys[-1] - ys[0]) / pitch))
    if n <= 0 or (n + 1 - len(ys)) / (n + 1) > max_missing_ratio:
        return None
    # least-squares line through (index, y) using each rule's inferred index
    idxs = np.round((np.array(ys) - ys[0]) / pitch)
    slope, intercept = np.polyfit(idxs, ys, 1)
    return [float(intercept + slope * i) for i in range(n + 1)]


@dataclass
class Geometry:
    width: int
    height: int
    skew: float
    col_edges: list[float] = field(default_factory=list)
    row_edges: list[float] = field(default_factory=list)

    @property
    def rows(self) -> list[tuple[float, float]]:
        return [(self.row_edges[i], self.row_edges[i + 1]) for i in range(len(self.row_edges) - 1)]

    def normalized_rows(self) -> list[tuple[float, float]]:
        return [(t / self.height, b / self.height) for t, b in self.rows]

    def normalized_cols(self) -> list[float]:
        return [x / self.width for x in self.col_edges]

    def name_column(self, index: int = 1) -> tuple[float, float] | None:
        """Normalized x-range of the name column, by rule index."""
        cols = self.normalized_cols()
        if len(cols) < index + 2:
            return None
        return cols[index], cols[index + 1]


def detect_rules(mask: np.ndarray, vth: float = 0.55, hth: float = 0.65) -> Geometry:
    h, w = mask.shape
    geo = Geometry(width=w, height=h, skew=0.0)

    rowink = mask.sum(axis=1) / w
    inked = np.where(rowink > 0.05)[0]
    if not len(inked):
        return geo
    y0, y1 = int(inked[0]), int(inked[-1])

    colprof = mask[y0:y1].sum(axis=0) / max(1, y1 - y0)
    cols = _peaks(colprof, vth)
    if len(cols) < 2:
        return geo
    geo.col_edges = [float(c) for c in cols]

    x0, x1 = cols[0], cols[-1]
    rowprof = mask[:, x0:x1].sum(axis=1) / max(1, x1 - x0)
    rules = _peaks(rowprof, hth)
    if len(rules) < 3:
        return geo

    filled = comb_fit(rules)
    geo.row_edges = filled if filled else [float(r) for r in rules]
    return geo


def analyze(path: Path) -> Geometry:
    mask = ink_mask(Image.open(path))
    skew = estimate_skew(mask)
    geo = detect_rules(rotate_mask(mask, skew))
    geo.skew = skew
    return geo


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    args = ap.parse_args(argv)

    geo = analyze(args.image)
    out = {
        "width": geo.width,
        "height": geo.height,
        "skew_deg": geo.skew,
        "columns": geo.normalized_cols(),
        "rows": geo.normalized_rows(),
        "name_column": geo.name_column(),
    }
    text = json.dumps(out, indent=2)
    if args.out:
        args.out.write_text(text)
    print(text[:600])
    print(f"\n{len(out['rows'])} rows, {len(out['columns'])} column rules, skew {geo.skew:+.2f}°")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
