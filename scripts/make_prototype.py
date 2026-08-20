"""Build the review-UI prototype from downloaded dossiers.

The prototype is a single local HTML file with its data embedded. It is
deliberately *not* published anywhere: it shows pages from the archive, and
those are not redistributed. Open it from disk.

A browser page loaded over file:// cannot list a directory or read arbitrary
files, so the document list is baked in at build time from the download
manifest. Page images are written as siblings and referenced normally, which
does work from disk.

Only the *Gelria* page carries a transcription — it was hand-made to exercise
the UI. Every other document is shown as untranscribed rather than filled with
invented rows.

Usage:
    python scripts/make_prototype.py                       # whole downloaded corpus
    python scripts/make_prototype.py --limit 8 --pages 2
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# run directly, this script is not inside the package, and the package imports
# below live inside functions — so without this the build died mid-corpus
# rather than at startup, and left the previous index.html in place.
sys.path.insert(0, str(ROOT))
BUILD = ROOT / "prototype" / "build"
PAGES = BUILD / "pages"

# the hand-transcribed sample belongs to this dossier
SAMPLE_INDEX = "017397"


def pdf_page_count(pdf: Path) -> int:
    from desembarque import pdf as pdflib
    return pdflib.page_count(pdf)


def render(pdf: Path, page: int, dpi: int, dest: Path) -> tuple[int, int] | None:
    from desembarque import pdf as pdflib
    return pdflib.render_page(pdf, page, dest, dpi=dpi)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--pdf", type=Path, help="build from a single PDF instead of the corpus")
    ap.add_argument("--limit", type=int, default=0, help="max dossiers (0 = all)")
    ap.add_argument("--pages", type=int, default=3, help="max pages rendered per dossier")
    ap.add_argument("--dpi", type=int, default=120)
    ap.add_argument("--rows", type=Path, default=ROOT / "prototype" / "sample_rows.json")
    args = ap.parse_args(argv)

    manifest = args.scans / "manifest.jsonl"
    if args.pdf:
        entries = [{"index": args.pdf.stem.split("_")[-2], "ship": args.pdf.stem,
                    "fundo": "?", "series": "?", "files": [args.pdf.name]}]
        scan_dir = args.pdf.parent
    elif manifest.exists():
        entries = [json.loads(l) for l in manifest.open(encoding="utf-8")]
        scan_dir = args.scans
    else:
        print(f"no manifest at {manifest} — run scripts/download.py first", file=sys.stderr)
        return 1

    if args.limit:
        # keep the transcribed sample in the list regardless of where it sorts
        keep = [e for e in entries if SAMPLE_INDEX in "".join(e["files"])]
        rest = [e for e in entries if e not in keep]
        entries = (keep + rest)[: args.limit]

    PAGES.mkdir(parents=True, exist_ok=True)
    sample = json.loads(args.rows.read_text(encoding="utf-8"))

    documents = []
    for e in entries:
        for fname in e["files"]:
            pdf = scan_dir / fname
            if not pdf.exists():
                continue
            total = pdf_page_count(pdf)
            is_sample = SAMPLE_INDEX in fname
            pages = []
            # page 1 is usually a cover card; render a few from the start
            for p in range(1, min(total, args.pages) + 1):
                dest = PAGES / f"{pdf.stem}-p{p}.jpg"
                size = render(pdf, p, args.dpi, dest) if not dest.exists() else None
                if size is None and dest.exists():
                    from PIL import Image
                    with Image.open(dest) as im:
                        size = im.size
                if size:
                    pages.append({"file": f"pages/{dest.name}", "w": size[0], "h": size[1], "n": p})
            if not pages:
                continue
            documents.append({
                "id": pdf.stem,
                "notation": f"{e.get('fundo','?')}.{e.get('series','?')}.{e.get('index','?')}",
                "ship": e.get("ship") or "—",
                "fundo": e.get("fundo"),
                "index": e.get("index"),
                "total_pages": total,
                "pages": pages,
                "rows": sample["rows"] if is_sample else None,
                "geometry": sample["geometry"] if is_sample else None,
                "meta": sample["document"] if is_sample else None,
                # the sample transcription is of page 2
                "transcribed_page": 2 if is_sample else None,
            })
            print(f"  {pdf.stem}: {len(pages)}/{total} pages"
                  f"{' (transcribed)' if is_sample else ''}", file=sys.stderr)

    if not documents:
        print("no documents built", file=sys.stderr)
        return 1

    payload = {"documents": documents,
               "active": next((i for i, d in enumerate(documents) if d["rows"]), 0)}
    (BUILD / "data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    html = (ROOT / "prototype" / "review.html").read_text(encoding="utf-8")
    if "__DATA__" not in html:
        raise SystemExit("review.html is missing the __DATA__ placeholder")
    html = html.replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"))
    (BUILD / "index.html").write_text(html, encoding="utf-8")

    total_pages = sum(len(d["pages"]) for d in documents)
    print(f"\n{len(documents)} documents, {total_pages} pages rendered")
    print(f"prototype ready: file://{BUILD / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
