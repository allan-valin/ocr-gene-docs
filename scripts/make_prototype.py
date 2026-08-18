"""Build the review-UI prototype from a downloaded dossier.

The prototype is a single local HTML file. It is deliberately *not* published
anywhere: it embeds a page from the archive, and those are not redistributed.
Open it from disk.

The generated page and its transcription live in prototype/build/, which is
gitignored. Only the template and this script are versioned.

Usage:
    python scripts/make_prototype.py data/scans/BR_..._d0001de0001.pdf --page 2
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "prototype" / "build"


def render_page(pdf: Path, page: int, dpi: int, dest: Path) -> tuple[int, int]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    stem = dest.with_suffix("")
    subprocess.run(
        ["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(dpi), "-jpeg",
         "-jpegopt", "quality=82", str(pdf), str(stem)],
        check=True, capture_output=True,
    )
    produced = sorted(stem.parent.glob(f"{stem.name}-*.jpg"))
    if not produced:
        raise SystemExit(f"pdftoppm produced nothing for page {page} of {pdf}")
    produced[0].replace(dest)
    try:
        out = subprocess.run(["identify", "-format", "%w %h", str(dest)],
                             capture_output=True, text=True)
        if out.returncode == 0 and out.stdout.strip():
            w, h = out.stdout.split()
            return int(w), int(h)
    except FileNotFoundError:
        pass  # ImageMagick is optional; Pillow is already a dependency
    from PIL import Image
    with Image.open(dest) as im:
        return im.size


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--page", type=int, default=2)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--rows", type=Path, default=ROOT / "prototype" / "sample_rows.json")
    args = ap.parse_args(argv)

    if not args.pdf.exists():
        print(f"no such pdf: {args.pdf}", file=sys.stderr)
        return 1

    BUILD.mkdir(parents=True, exist_ok=True)
    img = BUILD / "page.jpg"
    w, h = render_page(args.pdf, args.page, args.dpi, img)
    print(f"rendered page {args.page} -> {img} ({w}x{h})")

    data = json.loads(args.rows.read_text(encoding="utf-8"))
    data["image"] = img.name
    data["image_width"] = w
    data["image_height"] = h
    data["source_pdf"] = args.pdf.name
    (BUILD / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))

    shutil.copy(ROOT / "prototype" / "review.html", BUILD / "index.html")
    print(f"prototype ready: file://{BUILD / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
