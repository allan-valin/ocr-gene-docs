"""Build the public demo: a folder of PDFs the server has read, as one
static page with its page images beside it, for GitHub Pages.

The archive's pages are not redistributed (see make_prototype.py), so the
demo is built from a folder of Allan's own: photos of exam notes, typed
and handwritten, read by the real pipeline — the full read and the
"read only this area" lines — and shown in the same review page, with
nothing a browser alone cannot do (no transcribing, no corpus search).

Usage:
    .venv-ocr/bin/python scripts/make_demo.py samples/pdf --out demo/
    # then copy demo/ into the site: allan-valin.github.io/desembarque/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque.pdf import page_count, render_page  # noqa: E402


def doc_hash(pdf: Path) -> str:
    from desembarque.identity import identify
    return identify(pdf).doc_hash


def image_size(path: Path) -> tuple[int, int]:
    from PIL import Image
    with Image.open(path) as im:
        return im.size


def build(folder: Path, out: Path, review: Path = ROOT / "prototype" / "review.html",
          dpi: int = 120, store: Path | None = None) -> int:
    store = store or folder / "transcriptions"
    pages_dir = out / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    documents = []
    for pdf in sorted(folder.glob("*.pdf")):
        total = page_count(pdf)
        h = doc_hash(pdf)
        rec_path = store / f"{h}.json"
        rec = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.exists() else {}
        pages = []
        for n in range(1, total + 1):
            dest = pages_dir / f"{pdf.stem}-p{n}.jpg"
            if not render_page(pdf, n, dest, dpi=dpi):
                continue
            w, hh = image_size(dest)
            pages.append({"n": n, "file": f"pages/{dest.name}", "w": w, "h": hh})
        texts = {str(p["n"]): p["form"]["text"] for p in rec.get("pages") or []
                 if isinstance(p, dict) and (p.get("form") or {}).get("text")}
        documents.append({
            "id": h[:16], "hash": h, "file": pdf.name,
            "notation": pdf.stem.replace("_", " "),
            "ship": pdf.stem.replace("_", " "),
            "total_pages": total, "pages": pages,
            "rows": rec.get("rows") or None,
            "geometry": rec.get("geometry"),
            "custom": rec.get("custom"),
            "texts": texts,
            "pageTexts": texts,     # what the page reads when it is not served
            "meta": None,
            "transcribed": bool(rec),
            "transcribed_by": "motor" if rec else None,
            "partial": bool(rec.get("partial")),
            "read_pages": [int(p["n"]) for p in rec.get("pages") or [] if isinstance(p, dict) and p.get("n")],
        })
        print(f"  {pdf.name}: {len(pages)} page(s), "
              f"{len(rec.get('rows') or [])} rows, custom {sorted((rec.get('custom') or {}).keys())}",
              file=sys.stderr)
    if not documents:
        print("no PDFs in", folder, file=sys.stderr)
        return 1
    payload = {"documents": documents, "active": 0, "demo": True}
    (out / "data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    html = review.read_text(encoding="utf-8")
    if "__DATA__" not in html:
        raise SystemExit("review.html is missing the __DATA__ placeholder")
    html = html.replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"))
    (out / "index.html").write_text(html, encoding="utf-8")
    print(f"demo: {len(documents)} documents → {out / 'index.html'}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", type=Path, help="the PDFs, with their transcriptions/ beside them")
    ap.add_argument("--out", type=Path, default=ROOT / "demo")
    ap.add_argument("--dpi", type=int, default=120)
    args = ap.parse_args(argv)
    return build(args.folder.resolve(), args.out.resolve(), dpi=args.dpi)


if __name__ == "__main__":
    raise SystemExit(main())
