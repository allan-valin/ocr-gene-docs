"""An open-weight recogniser, driven by the grid rather than by detection.

The page geometry already knows where every row of the table is (see
`scripts/page_geometry.py`). That is worth more than it first appears:

* text detection can be skipped entirely, which is most of the per-page cost;
* row attribution holds by construction, so a name can never be scored against
  the row above it — the failure that makes a transcription worse than useless
  for someone checking whether their ancestor is on the page.

So a page is transcribed by cropping each row band out of the name column and
handing those crops to the recogniser as what they are: single lines of text.

Nothing here invents a value. A band the recogniser cannot read comes back as
null with a confidence of zero, and stays a numbered row, so the count of rows
on the page still matches the page.
"""
from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Callable

from .engine import PageResult
from .search import is_heading

# Recogniser choice and threading are set by measurement, not taste — see
# scripts/spike_speed.py and docs/PROGRESS.md for the numbers behind these.
# Measured on the Gelria page (scripts/spike_speed.py):
#   detect+recognise the name column   25.2 s   CER 0.205
#   recognise the row bands, 320 wide   1.1 s   CER 0.418  (names clipped)
#   recognise the row bands, 640 wide   2.4 s   CER 0.205  <- this
# The clipping is the whole story: a manifest name is far wider than the
# recogniser's default input, so at 320 it lost the surname. At 640 it matches
# the detection pipeline exactly, ten times faster. The mobile recogniser stays
# poor at any width (CER 0.508), so the medium one is kept.
DEFAULT_REC = os.environ.get("DESEMBARQUE_REC_MODEL", "PP-OCRv6_medium_rec")
DEFAULT_DET = os.environ.get("DESEMBARQUE_DET_MODEL", "PP-OCRv6_medium_det")
DEFAULT_THREADS = int(os.environ.get("DESEMBARQUE_CPU_THREADS", "0")) or None
REC_INPUT_SHAPE = (3, 48, 640)
PAD_PX = 6
MIN_ROW_PX = 12
INK_MARGIN = 4

# Below this share of rows read, try the page again from a grayscale render.
# See `with_fallback` for why the render is a fallback and not the default.
RETRY_FLOOR = 0.5
RENDER_DPI = 300


def refine(im, margin: int = INK_MARGIN):
    """Trim a row band down to the writing inside it.

    Skipping detection also skipped the tight box it used to draw. A band cut
    from the row comb spans the whole column and reaches into the ruled lines,
    so the recogniser is handed blank paper and the tips of the neighbouring
    row's descenders. Trimming to the ink restores what detection contributed,
    without a model. A band with no ink is returned untouched — an empty row is
    a real answer.
    """
    import numpy as np
    a = np.asarray(im.convert("L"), dtype=np.uint8)
    if a.size == 0:
        return im
    thr = max(60, int(a.mean()) - 35)
    ink = a < thr
    ys = np.flatnonzero(ink.sum(axis=1) > max(1, int(0.02 * a.shape[1])))
    xs = np.flatnonzero(ink.sum(axis=0) > max(1, int(0.02 * a.shape[0])))
    if ys.size == 0 or xs.size == 0:
        return im
    return im.crop((max(0, int(xs[0]) - margin), max(0, int(ys[0]) - margin),
                    min(a.shape[1], int(xs[-1]) + 1 + margin),
                    min(a.shape[0], int(ys[-1]) + 1 + margin)))


# A line number on these forms runs to three digits, and arrives with whatever
# punctuation the clerk used or the recogniser invented: ".9", "1I", "12.", "10".
_ORDINAL = re.compile(r"^[\s.,;:'`\-]*\d{1,3}[\s.,;:'`\-]+")
_ONLY_ORDINAL = re.compile(r"^[\s.,;:'`\-]*\d{1,3}[\s.,;:'`\-]*$")


def strip_ordinal(text: str) -> str:
    """The name without the line number the crop swept up with it.

    Where the Numero divider does not print clearly enough to be detected as a
    column, the ordinal sits inside the name crop: 28.2% of indexed rows begin
    with a digit, and the split then files ".9" as part of a surname.

    A cell holding *only* a number has no name in it, and comes back empty
    rather than filing a passenger called "14". Letters are never touched, and a
    run of more than three digits is not a line number, so it is left alone.
    """
    t = (text or "").strip()
    if not t:
        return ""
    if _ONLY_ORDINAL.match(t):
        return ""
    return _ORDINAL.sub("", t, count=1).strip()


def list_breaks(ordinals: list[str], lookback: int = 3) -> list[int]:
    """Row indices where the numbering restarts, i.e. where a new list begins.

    A dossier can carry more than one list — Allan reports the same passengers
    written twice, once in German with the surname first and again in pt-BR with
    it last — and the numbering restarts between them. Rows either side of a
    restart are not one list, and the surname order may differ across it.

    Two things make this less simple than comparing neighbours. The numbering is
    clerk shorthand: 1-9, 10, 1-9, 20, 1-9, 30, with only the tens written in
    full, so a drop from 9 to 1 is ordinary counting. And most ordinals read
    badly or not at all, so a gap is silence, not a boundary.

    So a break is only called when a number is lower than the recent run *and*
    the count continues from the lower number afterwards. A single stray low
    reading between two rows that carry on counting is a misread.
    """
    seen: list[tuple[int, int]] = []          # (row index, value)
    for i, raw in enumerate(ordinals):
        digits = "".join(c for c in (raw or "") if c.isdigit())
        if not digits or len(digits) > 3:
            continue
        seen.append((i, int(digits)))

    breaks: list[int] = []
    run: list[int] = []                       # values since the last break only
    for k, (i, v) in enumerate(seen):
        recent = run[-lookback:]
        if recent and v < max(recent) and not (v % 10 == 0 or max(recent) % 10 == 0):
            nxt = [w for _, w in seen[k + 1:k + 1 + lookback]]
            carries_on = nxt and all(w > v for w in nxt) and nxt[0] - v <= lookback
            if carries_on or not nxt:
                # a new list starts here, and the rows before it are no longer
                # anything to compare against
                breaks.append(i)
                run = [v]
                continue
        run.append(v)
    return breaks


def split_name(text: str) -> tuple[str | None, str | None]:
    """Split a manifest name into surname and given name.

    These tables are written surname-first, with compound surnames spelled out
    in full and the given name last ("ROCA REBULLIDA AMPARO"). Taking the last
    token as the given name follows the convention the clerks actually used.
    The raw string is kept alongside, so a wrong split loses nothing.
    """
    t = " ".join((text or "").split())
    if not t:
        return None, None
    parts = t.split(" ")
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def name_strip_box(geo, size: tuple[int, int]) -> tuple[int, int]:
    """The name column's x-range in pixels, with a little air either side."""
    W, _H = size
    nx0, nx1 = geo.name_column(0)
    return max(0, int((nx0 - 0.004) * W)), min(W, int((nx1 + 0.004) * W))


def rows_from_bands(geo, size: tuple[int, int],
                    recognize: Callable[[list], list[tuple[str, float]]],
                    crop: Callable[[int, tuple[int, int, int, int]], object],
                    ) -> list[dict]:
    """One row per detected band, in page order.

    `recognize` is injected so the row-building can be tested without the
    model. A short result from the recogniser pads with nulls rather than
    shifting later names up a row, which would be a silent corruption.
    """
    W, H = size
    bands = geo.normalized_rows()
    x0, x1 = name_strip_box(geo, size)

    boxes, keep = [], []
    for i, (bt, bb) in enumerate(bands):
        a = max(0, int(bt * H) - PAD_PX)
        b = min(H, int(bb * H) + PAD_PX)
        if b - a < MIN_ROW_PX:
            continue
        boxes.append((x0, a, x1, b))
        keep.append(i)

    said = list(recognize([crop(i, box) for i, box in zip(keep, boxes)])) if boxes else []
    said += [("", 0.0)] * (len(boxes) - len(said))
    by_band = dict(zip(keep, said))

    rows = []
    for i in range(len(bands)):
        text, score = by_band.get(i, ("", 0.0))
        # the line number belongs to the Numero column, not to anybody's surname
        text = strip_ordinal(text)
        surname, given = split_name(text)
        row = {
            "n": i + 1,
            "surname": surname,
            "given": given,
            "name_raw": text or "",
            "conf": {"surname": round(float(score), 3)},
        }
        if is_heading(text):
            # kept in the transcription, since it is genuinely on the page, but
            # marked so it is not offered as a person
            row["header"] = True
        rows.append(row)
    return rows


def read_ratio(rows: list[dict]) -> float:
    """Share of the page's rows that produced any text.

    The printed column caption does not count. A page whose only legible line
    is its own heading has read nothing, and scoring that 1/1 would hide
    exactly the failure this number exists to catch.
    """
    people = [r for r in rows if not r.get("header")]
    if not people:
        return 0.0
    return sum(1 for r in people if (r.get("name_raw") or "").strip()) / len(people)


def wants_retry(rows: list[dict], floor: float = RETRY_FLOOR) -> bool:
    """Whether this page is worth reading a second time.

    No rows means no grid, and a render cannot conjure one -- retrying there
    would buy a second recognition pass and the same empty answer.
    """
    if not rows:
        return False
    return read_ratio(rows) < floor


def richer(mask_rows: list[dict], alt_rows: list[dict]) -> list[dict]:
    """Whichever reading found more names.

    The mask keeps a tie. It is the default path and the better-tested one, so
    a fallback has to earn the swap by reading *more*, not by reading as much.
    On BS_ENT_017053 the render read five rows fewer than the mask; taking the
    render on faith there would have lost five people.
    """
    n_mask = sum(1 for r in mask_rows if (r.get("name_raw") or "").strip())
    n_alt = sum(1 for r in alt_rows if (r.get("name_raw") or "").strip())
    return alt_rows if n_alt > n_mask else mask_rows


def with_fallback(mask_rows: list[dict], make_alt: Callable[[], list[dict] | None],
                  floor: float = RETRY_FLOOR) -> tuple[list[dict], bool]:
    """The better of the mask reading and a second attempt, and which was used.

    `page_image` hands recognition the PDF's embedded MRC ink mask, because
    geometry needs it -- the mask yields nine column rules where a composited
    render yields three. But the mask is one bit deep, so on a faint page the
    strokes fall below its threshold and are simply gone: on BS_ENT_015741 p2
    the recogniser read 7 of 39 bands from the mask and 26 from a render, and
    an entire family was missing from the index.

    Across ten pages the mask read 63.3% of bands and the render 68.2% -- seven
    pages unchanged, one far better, one worse. So the render is not an
    improvement to adopt wholesale; it is a second opinion, asked for only when
    the first one came back nearly empty, and kept only when it reads more.
    """
    if not wants_retry(mask_rows, floor):
        return mask_rows, False
    alt = make_alt()
    if not alt:
        return mask_rows, False
    chosen = richer(mask_rows, alt)
    return chosen, chosen is alt


class PaddleEngine:
    """PaddleOCR (Apache-2.0 code, open weights), run locally on CPU."""

    name = "paddle"

    def __init__(self, rec_model: str = DEFAULT_REC, det_model: str = DEFAULT_DET,
                 mkldnn: bool = True, threads: int | None = DEFAULT_THREADS) -> None:
        self.rec_model = rec_model
        self.det_model = det_model
        self.mkldnn = mkldnn
        self.threads = threads
        self._local = threading.local()
        self._page = None
        self._page_plain = False

    # ---- model loading ------------------------------------------------------
    def _import(self):
        import paddleocr  # noqa: F401
        return paddleocr

    def available(self) -> bool:
        try:
            self._import()
        except Exception:
            return False
        return True

    def _make_recogniser(self):
        from paddleocr import TextRecognition
        kw = {"model_name": self.rec_model, "enable_mkldnn": self.mkldnn,
              "input_shape": REC_INPUT_SHAPE}
        if self.threads:
            kw["cpu_threads"] = self.threads
        return TextRecognition(**kw)

    def _recogniser(self):
        """One predictor per thread: the indexer runs documents in parallel and
        paddle's predictor is not safe to share between them."""
        rec = getattr(self._local, "rec", None)
        if rec is None:
            rec = self._local.rec = self._make_recogniser()
        return rec

    def _build_page(self, mkldnn: bool):
        from paddleocr import PaddleOCR
        kw = dict(use_doc_orientation_classify=False, use_doc_unwarping=False,
                  use_textline_orientation=False, enable_mkldnn=mkldnn,
                  lang="pt", text_detection_model_name=self.det_model,
                  text_recognition_model_name=self.rec_model)
        if self.threads:
            kw["cpu_threads"] = self.threads
        return PaddleOCR(**kw)

    def _full_page(self):
        if self._page is None:
            self._page = self._build_page(self.mkldnn and not self._page_plain)
        return self._page

    def _predict_page(self, image: Path):
        """Run the detection pipeline, dropping oneDNN if oneDNN refuses.

        This path reads the archive cover card, and `identify()` reads that, so
        when it fails a document loses the notation it should be filed under.
        It was failing on 167 of 168 indexed documents with

            NotImplementedError: (Unimplemented)
            ConvertPirAttribute2RuntimeAttribute not support
            [pir::ArrayAttribute<pir::DoubleAttribute>]

        and the run reported success regardless. The pipeline *builds* fine
        either way -- it dies on use -- so the retry has to wrap the call, not
        the construction.

        The row recogniser is happy with oneDNN and keeps it; the flag is
        dropped here and only here, and the choice is remembered, since
        rebuilding costs seconds and every page would otherwise pay it.
        """
        try:
            return self._full_page().predict(str(image))
        except Exception:
            if not self.mkldnn or self._page_plain:
                raise
            self._page_plain = True
            self._page = self._build_page(False)
            return self._page.predict(str(image))

    # ---- recognition --------------------------------------------------------
    def _recognize(self, crops: list) -> list[tuple[str, float]]:
        if not crops:
            return []
        import numpy as np
        rec = self._recogniser()
        arrs = [np.array(c.convert("RGB")) for c in crops]
        out = []
        for r in rec.predict(arrs, batch_size=16):
            d = r.json.get("res", r.json) if hasattr(r, "json") else {}
            out.append(((d.get("rec_text") or "").strip(),
                        float(d.get("rec_score") or 0.0)))
        return out

    def _page_text(self, image: Path) -> str:
        res = self._predict_page(image)
        parts = []
        for r in res:
            d = r.json.get("res", r.json) if hasattr(r, "json") else {}
            parts.extend(t for t in (d.get("rec_texts") or []) if t)
        return "\n".join(parts)

    def _render_rows(self, source: Path | None, page: int | None, geo,
                     size: tuple[int, int], workdir: Path) -> list[dict] | None:
        """The same bands, read from a grayscale render instead of the mask.

        Geometry stays measured on the mask, which is what it is good for; only
        the pixels handed to the recogniser change. The render is resized to
        the mask's dimensions so the row bands still land where geometry put
        them, and cached, since a page that needed it once will need it again.
        """
        if source is None or page is None:
            return None
        from PIL import Image
        from . import pdf as pdflib

        out = workdir / f"{source.stem}-p{page}-render-gray.png"
        try:
            if not out.exists() or not out.stat().st_size:
                if not pdflib.render_page(source, page, out, dpi=RENDER_DPI,
                                          grayscale=True):
                    return None
            im = Image.open(out).convert("L")
            if im.size != size:
                im = im.resize(size, Image.LANCZOS)
            im = im.rotate(geo.skew, resample=Image.BICUBIC, fillcolor=255)
        except Exception:
            # a fallback that cannot be produced is not an error: the mask
            # reading still stands, and the page is still reported
            return None
        return rows_from_bands(geo, im.size, self._recognize,
                               self._carved_crops(im, geo))

    def _carved_crops(self, im, geo) -> Callable[[int, tuple], object]:
        """A crop function that hands each band its own ink and nobody else's.

        The page is carved once: the name column is cut into rows along paths
        of least ink rather than along the ruled line, so the tail of a `y`
        stays with the row it was written on instead of landing inside the name
        below it. See `desembarque.rowcut`.

        Falls back to the plain rectangle if carving cannot be done, because a
        rectangular crop is the old behaviour and still a usable one.
        """
        import numpy as np
        from PIL import Image
        from .rowcut import carve

        W, H = im.size
        bands = geo.normalized_rows()
        x0, x1 = name_strip_box(geo, im.size)
        try:
            top = max(0, int(bands[0][0] * H) - PAD_PX)
            bottom = min(H, int(bands[-1][1] * H) + PAD_PX)
            strip = np.asarray(im.crop((x0, top, x1, bottom)).convert("L"))
            edges = [(max(0, int(bt * H) - PAD_PX - top),
                      min(bottom - top, int(bb * H) + PAD_PX - top))
                     for bt, bb in bands]
            cuts = carve(strip, edges)
        except Exception:
            cuts = []

        def crop(i: int, box: tuple) -> object:
            if i < len(cuts) and cuts[i].size:
                return refine(Image.fromarray(cuts[i]))
            return refine(im.crop(box))
        return crop

    def transcribe_page(self, image: Path, kind: str = "unknown",
                        source: Path | None = None,
                        page: int | None = None) -> PageResult:
        try:
            self._import()
        except Exception as e:
            return PageResult(kind=kind, engine=self.name,
                              error=f"motor indisponível: {type(e).__name__}: {e}")
        try:
            # the cover card carries the archival notation, and has no grid
            if kind == "cover":
                return PageResult(kind="cover", engine=self.name,
                                  text=self._page_text(image))

            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
            from PIL import Image
            from page_geometry import analyze
            Image.MAX_IMAGE_PIXELS = None

            geo = analyze(image)
            if not geo.rows or not geo.name_column(0):
                # no grid is a legitimate answer: many pages are not tables
                return PageResult(kind="unknown", engine=self.name,
                                  text=self._page_text(image))

            im = Image.open(image).convert("L")
            im = im.rotate(geo.skew, resample=Image.BICUBIC, fillcolor=255)
            rows = rows_from_bands(geo, im.size, self._recognize,
                                   self._carved_crops(im, geo))
            rows, from_render = with_fallback(
                rows,
                lambda: self._render_rows(source, page, geo, im.size, image.parent),
            )
            return PageResult(
                kind="list", engine=self.name, rows=rows,
                geometry={"rows": geo.normalized_rows(),
                          "columns": geo.normalized_cols(),
                          "skew": geo.skew,
                          "read_from": "render" if from_render else "mask"},
            )
        except Exception as e:
            return PageResult(kind=kind, engine=self.name,
                              error=f"{type(e).__name__}: {e}")
