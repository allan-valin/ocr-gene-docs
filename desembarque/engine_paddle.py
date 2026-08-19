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
from pathlib import Path
from typing import Callable

from .engine import PageResult

# Recogniser choice and threading are set by measurement, not taste — see
# scripts/spike_speed.py and docs/PROGRESS.md for the numbers behind these.
DEFAULT_REC = os.environ.get("DESEMBARQUE_REC_MODEL", "PP-OCRv5_mobile_rec")
DEFAULT_DET = os.environ.get("DESEMBARQUE_DET_MODEL", "PP-OCRv5_mobile_det")
DEFAULT_THREADS = int(os.environ.get("DESEMBARQUE_CPU_THREADS", "0")) or None
PAD_PX = 6
MIN_ROW_PX = 12


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


def rows_from_bands(geo, size: tuple[int, int],
                    recognize: Callable[[list], list[tuple[str, float]]],
                    crop: Callable[[tuple[int, int, int, int]], object],
                    ) -> list[dict]:
    """One row per detected band, in page order.

    `recognize` is injected so the row-building can be tested without the
    model. A short result from the recogniser pads with nulls rather than
    shifting later names up a row, which would be a silent corruption.
    """
    W, H = size
    bands = geo.normalized_rows()
    nx0, nx1 = geo.name_column(0)
    x0 = max(0, int((nx0 - 0.004) * W))
    x1 = min(W, int((nx1 + 0.004) * W))

    boxes, keep = [], []
    for i, (bt, bb) in enumerate(bands):
        a = max(0, int(bt * H) - PAD_PX)
        b = min(H, int(bb * H) + PAD_PX)
        if b - a < MIN_ROW_PX:
            continue
        boxes.append((x0, a, x1, b))
        keep.append(i)

    said = list(recognize([crop(box) for box in boxes])) if boxes else []
    said += [("", 0.0)] * (len(boxes) - len(said))
    by_band = dict(zip(keep, said))

    rows = []
    for i in range(len(bands)):
        text, score = by_band.get(i, ("", 0.0))
        surname, given = split_name(text)
        rows.append({
            "n": i + 1,
            "surname": surname,
            "given": given,
            "name_raw": text or "",
            "conf": {"surname": round(float(score), 3)},
        })
    return rows


class PaddleEngine:
    """PaddleOCR (Apache-2.0 code, open weights), run locally on CPU."""

    name = "paddle"

    def __init__(self, rec_model: str = DEFAULT_REC, det_model: str = DEFAULT_DET,
                 mkldnn: bool = True, threads: int | None = DEFAULT_THREADS) -> None:
        self.rec_model = rec_model
        self.det_model = det_model
        self.mkldnn = mkldnn
        self.threads = threads
        self._rec = None
        self._page = None

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

    def _recogniser(self):
        if self._rec is None:
            from paddleocr import TextRecognition
            kw = {"model_name": self.rec_model, "enable_mkldnn": self.mkldnn}
            if self.threads:
                kw["cpu_threads"] = self.threads
            self._rec = TextRecognition(**kw)
        return self._rec

    def _full_page(self):
        if self._page is None:
            from paddleocr import PaddleOCR
            kw = dict(use_doc_orientation_classify=False, use_doc_unwarping=False,
                      use_textline_orientation=False, enable_mkldnn=self.mkldnn,
                      lang="pt", text_detection_model_name=self.det_model,
                      text_recognition_model_name=self.rec_model)
            if self.threads:
                kw["cpu_threads"] = self.threads
            self._page = PaddleOCR(**kw)
        return self._page

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
        res = self._full_page().predict(str(image))
        parts = []
        for r in res:
            d = r.json.get("res", r.json) if hasattr(r, "json") else {}
            parts.extend(t for t in (d.get("rec_texts") or []) if t)
        return "\n".join(parts)

    def transcribe_page(self, image: Path, kind: str = "unknown") -> PageResult:
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
            rows = rows_from_bands(geo, im.size, self._recognize, im.crop)
            return PageResult(
                kind="list", engine=self.name, rows=rows,
                geometry={"rows": geo.normalized_rows(),
                          "columns": geo.normalized_cols(),
                          "skew": geo.skew},
            )
        except Exception as e:
            return PageResult(kind=kind, engine=self.name,
                              error=f"{type(e).__name__}: {e}")
