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
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

SEARCH_DEG = 1.5
COARSE_STEP = 0.05


def otsu(a: np.ndarray) -> float:
    """Otsu's threshold for a [0,1] image.

    A fixed 0.5 cut-off works on the bilevel mask inside these PDFs but not on a
    composited render, where aged paper sits around 0.7 and its texture crosses
    the line — that lifted the ink fraction from 0.05 to 0.20 and flattened the
    projections the rules have to stand out from.
    """
    hist, edges = np.histogram(a, bins=256, range=(0.0, 1.0))
    hist = hist.astype(np.float64)
    total = hist.sum()
    if total <= 0:
        return 0.5
    p = hist / total
    omega = np.cumsum(p)
    mu = np.cumsum(p * np.arange(256))
    mu_t = mu[-1]
    denom = omega * (1.0 - omega)
    denom[denom == 0] = 1e-12
    sigma_b = (mu_t * omega - mu) ** 2 / denom
    return float(edges[int(np.argmax(sigma_b))])


def ink_mask(im: Image.Image | np.ndarray, deskew: bool = False) -> np.ndarray:
    """Boolean array, True where there is ink.

    Accepts a normal page (dark ink on light paper) or an already inverted soft
    mask, and normalizes polarity: ink is always the minority.
    """
    if isinstance(im, Image.Image):
        a = np.asarray(im.convert("L"), dtype=np.float32) / 255.0
    else:
        a = np.asarray(im, dtype=np.float32)
        if a.max() > 1.0:
            a = a / 255.0
    levels = np.unique(a[:: max(1, a.shape[0] // 64)])
    th = 0.5 if levels.size <= 2 else otsu(a)
    m = a < th
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
    row_pitch: float | None = None
    table_box: tuple[float, float, float, float] | None = None

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


def rule_extent(mask: np.ndarray, x: int, halfw: int = 3, gap: int = 40
                ) -> tuple[int, int] | None:
    """Longest continuous vertical run of ink at column x.

    A printed table's vertical rules exist only inside the table, so this is
    what bounds it. Without that bound a row comb happily extends across the
    letterhead and the signature block, which is how the first attempt produced
    37 rows for a 26-row table.
    """
    lo = max(0, x - halfw)
    strip = mask[:, lo:x + halfw + 1].max(axis=1)
    ys = np.where(strip)[0]
    if not len(ys):
        return None
    runs: list[list[int]] = []
    cur = [int(ys[0])]
    for y in ys[1:]:
        if y - cur[-1] <= gap:
            cur.append(int(y))
        else:
            runs.append(cur)
            cur = [int(y)]
    runs.append(cur)
    best = max(runs, key=len)
    return best[0], best[-1]


def _text_lines(mask: np.ndarray, x0: int, x1: int, y0: int, y1: int,
                smooth: int = 9, min_width: int | None = None) -> list[int]:
    """Centres of the inked lines between y0 and y1 — the written rows.

    Detecting the *text* rather than the horizontal rules is what makes this
    work on real scans: the rules print faintly and break up, while a row of
    typing is the strongest horizontal signal on the page.
    """
    band = mask[y0:y1, x0:x1]
    if band.size == 0:
        return []
    prof = band.sum(axis=1) / max(1, x1 - x0)
    prof = np.convolve(prof, np.ones(smooth) / smooth, mode="same")
    if not prof.size or prof.max() <= 0:
        return []
    th = np.percentile(prof, 70)
    idx = np.where(prof > th)[0]
    groups: list[list[int]] = []
    for i in idx:
        if groups and i - groups[-1][-1] <= 6:
            groups[-1].append(int(i))
        else:
            groups.append([int(i)])
    # Horizontal rules also show up in this profile, and they would win the comb
    # fit while sitting *between* rows rather than on them. A rule is a narrow
    # peak a few pixels tall; a line of writing is several times wider, so width
    # separates them without depending on how darkly the rules printed.
    floor = min_width if min_width is not None else max(8, smooth * 2)
    return [int(np.mean(g)) + y0 for g in groups if len(g) >= floor]


def _best_pitch(centres: list[int], lo: float = 60, hi: float = 200
                ) -> tuple[float, float] | None:
    """Row pitch and phase that most of the detected lines agree with."""
    if len(centres) < 4:
        return None
    C = np.array(sorted(centres), dtype=float)
    best = None
    for pitch in np.arange(lo, hi, 0.5):
        for phase in C:
            idx = np.round((C - phase) / pitch)
            keep = np.abs(C - (phase + idx * pitch)) < pitch * 0.18
            n = int(keep.sum())
            if n < 4:
                continue
            span = idx[keep].max() - idx[keep].min() + 1
            score = n + 3 * (n / span if span else 0)
            if best is None or score > best[0]:
                sel, sidx = C[keep], idx[keep]
                slope, intercept = np.polyfit(sidx, sel, 1)
                best = (score, float(slope), float(intercept))
    return (best[1], best[2]) if best else None


def trim_border(mask: np.ndarray, margin: int = 4) -> tuple[int, int, int, int]:
    """Bounding box of the page inside the scanner's black surround.

    Renders composited by pdftoppm keep the dark frame around the sheet, and it
    is the strongest vertical line on the image — strong enough to be mistaken
    for a table rule and to dominate the skew estimate. The bilevel mask pulled
    straight out of the PDF has no such frame, which is why detection behaved
    differently on the two inputs for the same page.
    """
    h, w = mask.shape
    ink_rows = mask.mean(axis=1)
    ink_cols = mask.mean(axis=0)
    # the surround is almost solid ink; the sheet is mostly blank
    rows = np.where(ink_rows < 0.85)[0]
    cols = np.where(ink_cols < 0.85)[0]
    if not len(rows) or not len(cols):
        return 0, 0, w, h
    x0, x1 = int(cols[0]) + margin, int(cols[-1]) - margin
    y0, y1 = int(rows[0]) + margin, int(rows[-1]) - margin
    if x1 - x0 < w * 0.3 or y1 - y0 < h * 0.3:
        return 0, 0, w, h
    return x0, y0, x1, y1


def _columns(mask: np.ndarray, vth: float | None) -> list[int]:
    """Vertical rules, with a threshold that adapts to the page.

    An absolute cut-off does not transfer between inputs: the same page gives
    nine rules on the bilevel mask extracted from the PDF and three on a
    composited render, where the background layer lightens everything. Scaling
    to the strongest column present keeps both working.
    """
    h = mask.shape[0]
    prof = mask.sum(axis=0) / h
    if not prof.size or prof.max() <= 0:
        return []
    th = vth if vth is not None else max(0.10, 0.45 * float(np.percentile(prof, 99.8)))
    cols = _peaks(prof, th)
    if len(cols) < 3 and vth is None:
        cols = _peaks(prof, max(0.06, th * 0.6))
    return cols


def detect_rules(mask: np.ndarray, vth: float | None = None) -> Geometry:
    """Recover the table grid: column rules, table extent, and row bands."""
    h, w = mask.shape
    geo = Geometry(width=w, height=h, skew=0.0)

    bx0, by0, bx1, by1 = trim_border(mask)
    inner = mask[by0:by1, bx0:bx1]
    cols = [c + bx0 for c in _columns(inner, vth)]
    if len(cols) < 2:
        return geo
    geo.col_edges = [float(c) for c in cols]

    # the table's vertical extent, agreed across its rules
    extents = [e for e in (rule_extent(mask, c) for c in cols) if e]
    if not extents:
        return geo
    top = int(np.median([e[0] for e in extents]))
    bottom = int(np.median([e[1] for e in extents]))
    geo.table_box = (float(cols[0]), float(top), float(cols[-1]), float(bottom))
    if bottom - top < 20:
        return geo

    centres = _text_lines(mask, cols[0], cols[-1], top, bottom)
    fit = _best_pitch(centres)
    if not fit:
        return geo
    pitch, intercept = fit
    geo.row_pitch = pitch

    # The comb sits on the text centres, so shift it half a pitch to get the
    # boundaries *between* rows — a band has to bracket its line, not bisect it.
    first = int(np.ceil((top - intercept) / pitch))
    last = int(np.floor((bottom - intercept) / pitch))
    centres = [intercept + i * pitch for i in range(first, last + 1)]
    edges = [c - pitch / 2 for c in centres] + [centres[-1] + pitch / 2] if centres else []
    geo.row_edges = [e for e in edges if top - pitch <= e <= bottom + pitch]
    return geo


def analyze(path: Path) -> Geometry:
    """Full pass: binarize, trim the scanner surround, deskew, detect the grid.

    Trimming happens before the skew estimate: the dark frame around the sheet
    is axis-aligned and strong enough to pin the estimate at zero, hiding the
    half-degree of skew that actually matters to the content.
    """
    mask = ink_mask(Image.open(path))
    x0, y0, x1, y1 = trim_border(mask)
    inner = mask[y0:y1, x0:x1]
    skew = estimate_skew(inner)
    geo = detect_rules(rotate_mask(inner, skew))
    geo.skew = skew
    # report geometry in the coordinates of the image that was passed in
    geo.width, geo.height = mask.shape[1], mask.shape[0]
    geo.col_edges = [c + x0 for c in geo.col_edges]
    geo.row_edges = [r + y0 for r in geo.row_edges]
    if geo.table_box:
        a, b, c, d = geo.table_box
        geo.table_box = (a + x0, b + y0, c + x0, d + y0)
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
        "name_column": geo.name_column(0),
        "table_box": geo.table_box,
        "row_pitch": geo.row_pitch,
    }
    text = json.dumps(out, indent=2)
    if args.out:
        args.out.write_text(text)
    print(text[:600])
    print(f"\n{len(out['rows'])} rows, {len(out['columns'])} column rules, skew {geo.skew:+.2f}°")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def page_image(pdf: Path, n: int, workdir: Path, dpi: int = 300) -> Path | None:
    """Best image of page `n` for geometry work.

    These archive PDFs are MRC-compressed: each page carries a sharp bilevel
    mask alongside a blurry background layer. Detection on that mask is markedly
    better than on a composited render, where aged paper texture blurs the very
    projections the rules must stand out from — the same page yields nine column
    rules from the mask and two or three from a render. So prefer the embedded
    layer, and fall back to rendering for PDFs that have none.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    stem = workdir / f"{pdf.stem}-p{n}"
    subprocess.run(["pdfimages", "-f", str(n), "-l", str(n), "-png", str(pdf), str(stem)],
                   capture_output=True)
    best, best_px, best_bilevel = None, 0, False
    for cand in sorted(stem.parent.glob(f"{stem.name}-*.png")):
        try:
            with Image.open(cand) as im:
                px = im.width * im.height
                # getcolors returns None when the image has MORE colours than the
                # limit, so `or []` would score every rich image as bilevel.
                colours = im.getcolors(4)
                bilevel = im.mode == "1" or (colours is not None and len(colours) <= 2)
        except Exception:
            continue
        # prefer a bilevel layer; among those, the largest
        if (bilevel, px) > (best_bilevel, best_px):
            best, best_px, best_bilevel = cand, px, bilevel
    if best is not None and best_bilevel:
        return best

    out = workdir / f"{pdf.stem}-p{n}-render"
    subprocess.run(["pdftoppm", "-f", str(n), "-l", str(n), "-r", str(dpi), "-png",
                    str(pdf), str(out)], capture_output=True)
    made = sorted(out.parent.glob(f"{out.name}-*.png"))
    return made[0] if made else best


def analyze_pdf_page(pdf: Path, n: int, workdir: Path) -> Geometry | None:
    img = page_image(pdf, n, workdir)
    return analyze(img) if img else None
