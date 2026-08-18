"""PDF access via pypdfium2, replacing the poppler command-line tools.

Poppler is GPL. Calling `pdftoppm` and friends as subprocesses was arm's-length
aggregation rather than derivation, but shipping those binaries inside a
distributable would have carried GPL obligations for that part — source
availability, licence text, and no restriction on redistributing it — which
sits badly with keeping a commercial licence possible. PDFium is BSD-3-Clause,
so this removes the obligation entirely.

It is also better for packaging: a Python wheel with a bundled native library,
rather than per-OS poppler binaries that have to be located at runtime.

Replaces: pdfinfo (page_count), pdftoppm (render_page), pdfimages
(extract_images), pdftotext (extract_text).
"""
from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium

IMAGE_OBJ = 3  # FPDF_PAGEOBJ_IMAGE


def _doc(pdf: Path) -> pdfium.PdfDocument:
    return pdfium.PdfDocument(str(pdf))


def page_count(pdf: Path) -> int:
    try:
        doc = _doc(pdf)
    except Exception:
        return 0
    try:
        return len(doc)
    finally:
        doc.close()


def render_page(pdf: Path, n: int, dest: Path, dpi: int = 120,
                quality: int = 78, grayscale: bool = False) -> tuple[int, int] | None:
    """Render 1-based page `n` to `dest`. Returns (width, height), or None."""
    doc = _doc(pdf)
    try:
        if not (1 <= n <= len(doc)):
            return None
        page = doc[n - 1]
        pil = page.render(scale=dpi / 72).to_pil()
        if grayscale:
            pil = pil.convert("L")
        elif pil.mode not in ("RGB", "L"):
            pil = pil.convert("RGB")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.suffix.lower() in (".jpg", ".jpeg"):
            pil.convert("RGB").save(dest, quality=quality, optimize=True)
        else:
            pil.save(dest)
        return pil.size
    finally:
        doc.close()


def extract_images(pdf: Path, n: int, out_dir: Path, prefix: str | None = None) -> list[Path]:
    """Write page `n`'s embedded image objects, largest first.

    These archive PDFs are MRC-compressed, so a page carries a sharp bilevel
    mask beside a blurry background. Geometry detection wants that mask, and it
    is markedly better than a composited render.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = prefix or f"{pdf.stem}-p{n}"
    doc = _doc(pdf)
    made: list[tuple[int, Path]] = []
    try:
        if not (1 <= n <= len(doc)):
            return []
        page = doc[n - 1]
        for i, obj in enumerate(o for o in page.get_objects() if o.type == IMAGE_OBJ):
            try:
                pil = obj.get_bitmap(render=False).to_pil()
            except Exception:
                continue
            path = out_dir / f"{prefix}-{i:03d}.png"
            pil.save(path)
            made.append((pil.width * pil.height, path))
    finally:
        doc.close()
    return [p for _, p in sorted(made, key=lambda t: -t[0])]


def extract_text(pdf: Path, pages: range | None = None) -> str:
    """Text layer, page by page.

    Note this is the *archive's* OCR, which is unusable for transcription — the
    ship GELRIA comes out as "GC- £R i' A". It is kept only as a weak signal.
    """
    doc = _doc(pdf)
    try:
        rng = pages or range(1, len(doc) + 1)
        out = []
        for n in rng:
            if not (1 <= n <= len(doc)):
                continue
            tp = doc[n - 1].get_textpage()
            out.append(tp.get_text_range() or "")
        return "\n".join(out)
    finally:
        doc.close()
