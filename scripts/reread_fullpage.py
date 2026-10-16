"""Re-read the whole-page pass's lines with another recogniser.

`read_fullpage.py` left every cursive and unknown page's lines on disk with
their polygons (`data/fullpage/<hash>-p<N>.json`), read by McFondue. On the
held-out pages Kiessling's generalized PP-OCRv6 medium for kraken (Apache-2.0,
Zenodo 21788410) reads the same lines far better -- cursive 64 to 113 of 212
in the top five by name, 2026-10-12 -- so this reads them again with it, no
segmentation, 0.014 s a line on the GPU. One file a page under `--out-dir`,
written as it is read, so the pass resumes and never reads a page twice;
typed pages are the engine's and are not touched.

    .venv-ocr/bin/python scripts/reread_fullpage.py --device cuda:0
    .venv-ocr/bin/python scripts/reread_fullpage.py --collect

The 1923 window's lines (`read_hospedaria.py`, polygons stored, no cached
images) are re-read the same way, rendering each page from its PDF, two
workers on the one GPU:

    .venv-ocr/bin/python scripts/reread_fullpage.py --device cuda:0 --shard 0/2 \\
        --in-dir data/dossiers-1923/lines --out-dir data/dossiers-1923/lines-ppocrv6
    .venv/bin/python scripts/search_lines.py --dir data/dossiers-1923/lines-ppocrv6 "Kubach August"
    .venv/bin/python scripts/apply_second_opinion.py --write \\
        --sidecar data/fullpage-ppocrv6-corpus-column.json --bands data/reread-index

The sidecar lands in McFondue's `second_read` slot on those rows; McFondue's
own reading stays in `data/fullpage/` and `data/fullpage-corpus-column.json`,
so the write is reversible by applying that sidecar again.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from read_fullpage import collect, shard  # noqa: E402
from read_hospedaria import render  # noqa: E402
from spike_fullpage import chosen_image  # noqa: E402
from spike_lines_model import load_recogniser, reread  # noqa: E402

DEFAULT_MODEL = Path.home() / ".cache/kraken/ppocrv6-hist/medium.safetensors"


def pages_due(src: Path, out: Path) -> list[Path]:
    """The cursive and unknown page files not yet re-read, in name order."""
    due = []
    for f in sorted(src.glob("*-p*.json")):
        if (out / f.name).exists():
            continue
        try:
            hand = json.loads(f.read_text(encoding="utf-8")).get("hand")
        except ValueError:
            continue
        if hand != "typed":
            due.append(f)
    return due


def page_image(work: Path, pdf: str, page: int, scans: Path, dpi: int, tmp: Path):
    """The page's picture: the cached one the corpus pass used, or, for a
    window read straight off its PDFs (the 1923 dossiers), rendered now at
    the resolution those lines were found at -- the stored coordinates are
    fractions of the page, so any resolution puts them on the same ink."""
    img = chosen_image(work, pdf, page)
    if img is not None:
        return img
    scan = scans / pdf
    if not scan.exists():
        return None
    return render(scan, page, dpi, tmp)


def render_ahead(files: list[Path], work: Path, scans: Path, dpi: int, tmp: Path,
                 workers: int = 3):
    """(file, its JSON, its page image) in order, the images made `workers`
    pages ahead in threads. pdftoppm is a subprocess, so threads overlap it;
    with one thread the recogniser idles for the seconds a render takes."""
    from concurrent.futures import ThreadPoolExecutor
    def job(f):
        d = json.loads(f.read_text(encoding="utf-8"))
        return d, page_image(work, d["pdf"], int(d["page"]), scans, dpi, tmp)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = []
        it = iter(files)
        for f in it:
            pending.append((f, pool.submit(job, f)))
            if len(pending) >= workers:
                break
        while pending:
            f, fut = pending.pop(0)
            nxt = next(it, None)
            if nxt is not None:
                pending.append((nxt, pool.submit(job, nxt)))
            d, img = fut.result()
            yield f, d, img


def write_page(out: Path, src_file: Path, lines: list[dict], model: str, secs: float) -> Path:
    """The re-read page under the original's name, every key of the original
    kept (`search_lines.py` wants the book), whole or not at all."""
    out.mkdir(parents=True, exist_ok=True)
    d = json.loads(src_file.read_text(encoding="utf-8"))
    target = out / src_file.name
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps({**d, "model": model, "lines": lines, "secs": round(secs, 1)},
                              ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, target)
    return target


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in-dir", type=Path, default=ROOT / "data" / "fullpage")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "data" / "fullpage-ppocrv6")
    ap.add_argument("--records", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--tag", default="PP-OCRv6-hist-medium-page-column")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans",
                    help="where to render a page from when no cached image exists")
    ap.add_argument("--dpi", type=int, default=200,
                    help="render resolution for pages without a cached image "
                         "(read_hospedaria.py read the 1923 window at 200)")
    ap.add_argument("--shard", default=None, help="I/N: this worker's share")
    ap.add_argument("--render-workers", type=int, default=3,
                    help="pages rendered ahead in threads while one is read")
    ap.add_argument("--limit", type=int, default=0, help="pages to read this run")
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "fullpage-ppocrv6-corpus",
                    help="prefix for --collect: <out>-column.json")
    a = ap.parse_args(argv)

    if a.collect:
        sidecar, _typed = collect(a.out_dir, a.records, tag=a.tag)
        p = a.out.with_name(a.out.name + "-column.json")
        p.write_text(json.dumps(sidecar, ensure_ascii=False), encoding="utf-8")
        n = sum(len(rows) for pages in sidecar["read"].values() for rows in pages.values())
        print(f"wrote {p}: {n} rows on {sum(len(v) for v in sidecar['read'].values())} pages")
        return 0

    todo = shard(pages_due(a.in_dir, a.out_dir), a.shard)
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(list(a.out_dir.glob('*-p*.json'))) if a.out_dir.exists() else 0} pages on disk, "
          f"{len(todo)} to read", flush=True)
    if not todo:
        return 0

    import tempfile
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    model = load_recogniser(a.model, a.device)
    began, read = time.time(), 0
    tmpdir = tempfile.TemporaryDirectory()
    for f, d, img in render_ahead(todo, a.work, a.scans, a.dpi, Path(tmpdir.name),
                                  workers=max(1, a.render_workers)):
        t0 = time.time()
        if img is None:
            print(f"  {d['pdf'][16:28]} p{d['page']}: no image, skipped", flush=True)
            continue
        try:
            im = img if isinstance(img, Image.Image) else Image.open(img).convert("L")
            said = reread(im, d.get("lines") or [], model, device=a.device)
        except Exception as e:  # a page the GPU cannot hold is retried next run
            print(f"  {d['pdf'][16:28]} p{d['page']}: failed, {e}", flush=True)
            continue
        secs = time.time() - t0
        write_page(a.out_dir, f, said, a.model.stem, secs)
        read += 1
        rate = (time.time() - began) / read
        print(f"  {d['pdf'][16:28]} p{d['page']} {d.get('hand')}: {len(said)} lines, "
              f"{secs:.1f}s [{read}/{len(todo)}, ~{(len(todo) - read) * rate / 60:.0f} min left]",
              flush=True)
    tmpdir.cleanup()
    print(f"{read} pages in {(time.time() - began) / 60:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
