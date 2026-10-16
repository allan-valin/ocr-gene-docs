"""Read the Hospedaria da Ilha das Flores registers, every line of every page.

The archive's orientation page says: not found in the OL lists, look in the
hospedaria registers (Favoritos → Hospedaria dos Imigrantes). Books HIF.109,
110 and 111 cover January 1920 to December 1925, ~1,470 pages, one clerk's
neat hand: date, ship, port of origin, ordinal, NAMES, sex, family, age,
status, nationality. A man found here is found with his ship and date, and
the OL list follows by number.

Layout (Allan, 2026-10-09): an open book. Left page (odd in the PDF):
Data (anno, mez, dia); Entrada: vapor em que veio, procedência; número de
ordem; NOMES; Sexo: masculino, feminino (vertical); Famílias: número (de
famílias, de pessoas por família — vertical), parentesco; immigrantes sem
família; idade; estado; nacionalidade. Right page (even) continues the same
rows: profissão; espontâneos (vertical); Sahidas: data (anno, mez, dia); meio
de transporte; destino; observações. So a hit on page N has its exit and
destination on page N+1 at the same height.

Same reader as the corpus pass (kraken blla + McFondue, polygons kept), one
JSON per page under --out-dir, resumable, `--shard I/N` for workers.
`search_lines.py` then asks the files for a name.

    .venv-ocr/bin/python scripts/read_hospedaria.py --device cuda
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from read_fullpage import read_with_fallback, shard  # noqa: E402


def page_count(pdf: Path) -> int:
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    return 0


def page_file(out_dir: Path, book: str, page: int) -> Path:
    return out_dir / f"{book}-p{page:04d}.json"


def pages_wanted(books: list[Path], out_dir: Path, parity: str | None = None,
                 count=None) -> list[tuple[Path, str, int]]:
    """Every page not yet read; `parity="odd"` keeps the left-hand pages,
    which carry the names (the even pages are the departures)."""
    todo = []
    for pdf in books:
        book = pdf.stem.split("_HIF_")[-1].split("_")[0] if "_HIF_" in pdf.stem else pdf.stem
        for n in range(1, (count or page_count)(pdf) + 1):
            if parity == "odd" and n % 2 == 0 or parity == "even" and n % 2 == 1:
                continue
            if not page_file(out_dir, book, n).exists():
                todo.append((pdf, book, n))
    return todo


def render(pdf: Path, page: int, dpi: int, tmp: Path):
    from PIL import Image
    prefix = tmp / f"{pdf.stem}-{page}"
    subprocess.run(["pdftoppm", "-r", str(dpi), "-f", str(page), "-l", str(page),
                    "-gray", "-png", str(pdf), str(prefix)], check=True)
    out = next(tmp.glob(f"{prefix.name}*.png"))
    im = Image.open(out).convert("L")
    im.load()
    out.unlink()
    return im


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--books", type=Path, nargs="*", default=None)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "data" / "hospedaria" / "lines")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--model", type=Path,
                    default=Path.home() / ".cache/kraken/ManuMcFondue.mlmodel")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--shard", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--pages", choices=["odd", "even", "all"], default="odd",
                    help="odd = the name pages (default)")
    ap.add_argument("--pid-file", type=Path, default=None)
    a = ap.parse_args(argv)
    books = a.books or sorted((ROOT / "data" / "hospedaria").glob("*.pdf"))
    a.out_dir.mkdir(parents=True, exist_ok=True)
    todo = shard(pages_wanted(books, a.out_dir, None if a.pages == "all" else a.pages), a.shard)
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(todo)} pages to read", flush=True)
    if not todo:
        return 0
    if a.pid_file:
        a.pid_file.write_text(str(os.getpid()))
    from PIL import Image
    from kraken.lib import models
    Image.MAX_IMAGE_PIXELS = None
    rec_models = {a.device: models.load_any(str(a.model), device=a.device)}
    if a.device != "cpu":
        rec_models["cpu"] = models.load_any(str(a.model), device="cpu")
    began, read = time.time(), 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        try:
            for pdf, book, n in todo:
                t0 = time.time()
                im = render(pdf, n, a.dpi, tmp)
                lines = read_with_fallback(im, rec_models, a.device)
                out = page_file(a.out_dir, book, n)
                tmp_out = out.with_suffix(".tmp")
                tmp_out.write_text(json.dumps({"book": book, "page": n, "pdf": pdf.name,
                                               "lines": lines,
                                               "secs": round(time.time() - t0, 1)},
                                              ensure_ascii=False), encoding="utf-8")
                os.replace(tmp_out, out)
                read += 1
                left = (len(todo) - read) * (time.time() - began) / read / 3600
                print(f"  HIF.{book} p{n}: {len(lines)} lines, {time.time() - t0:.0f}s "
                      f"[{read}/{len(todo)}, ~{left:.1f} h left]", flush=True)
        finally:
            if a.pid_file and a.pid_file.exists():
                a.pid_file.unlink()
    print(f"{read} pages in {(time.time() - began) / 60:.0f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
