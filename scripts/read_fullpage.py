"""Read the whole corpus the way the held-out sheet said to: every line on
the page, then the column.

`spike_fullpage.py` measured it on the fifteen held-out pages (2026-10-08):
kraken's page segmenter finds the rows the engine's grid cuts across, and a
second reading of those lines reaches names the index could not — cursive 56
to 68 of 212 in the top five with McFondue, typed 151 to 164 of 191 with the
engine's own recogniser on the same lines. This is that, over the corpus.

One segmentation per page (about 14 s of the 19 s a page costs on this CPU,
so the typed pages are not much cheaper than the cursive ones). A cursive or
unknown page is read by McFondue here, with the cut position of every
character, so the name column can be clipped out by geometry afterwards. A
typed page keeps only its lines: the engine reads them in its own venv,
`spike_engine_on_lines.py --lines <out>-typed-lines.json`.

Each page lands in its own file under `--out-dir` as it is read, so the pass
resumes from wherever it was stopped and never reads a page twice. Cursive
pages go first, because they are the point.

    .venv-ocr/bin/python scripts/read_fullpage.py            # read, resumable
    .venv-ocr/bin/python scripts/read_fullpage.py --collect  # then build sidecars

The sidecars are applied as second readings, reversibly:

    .venv/bin/python scripts/apply_second_opinion.py --write \\
        --sidecar data/fullpage-corpus-column.json --bands data/reread-index
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

from spike_fullpage import chosen_image, onto_bands, read_page  # noqa: E402

ORDER = ("cursive", "unknown", "typed")
MODEL_TAG = "ManuMcFondue-page-column"


def page_file(out_dir: Path, doc: str, page: int) -> Path:
    return out_dir / f"{doc}-p{page}.json"


def pages_wanted(hands: dict, out_dir: Path, only=None,
                 limit: int = 0) -> list[tuple[str, str, int, str]]:
    """(pdf, hash, page, hand) for every page still to read, cursive first."""
    got = []
    for hand in (tuple(only) if only else ORDER):
        for name, v in sorted(hands.items()):
            for page, h in sorted(v.get("pages", {}).items(), key=lambda kv: int(kv[0])):
                if h != hand:
                    continue
                if page_file(out_dir, v["hash"], int(page)).exists():
                    continue
                got.append((name, v["hash"], int(page), hand))
    return got[:limit] if limit else got


def shard(todo: list, spec: str | None) -> list:
    """This worker's share of the pages: `I/N` takes every Nth from the Ith.

    kraken's segmentation is CPU vectorisation, single-threaded, 12 s a page
    whatever the device; N workers on one GPU read N pages in that time.
    """
    if not spec:
        return todo
    i, _, n = spec.partition("/")
    return todo[int(i)::int(n)]


def read_with_fallback(im, rec_models: dict, device: str, read=None) -> list[dict]:
    """Read the page on `device`; a page the GPU cannot hold (one long line
    asks the LSTM for gigabytes) is read again on the CPU instead of killing
    the worker. `rec_models` maps device -> model, or {device: None} for a
    typed page that is only segmented."""
    read = read or read_page
    try:
        return read(im, None, rec_models.get(device), device=device)
    except RuntimeError as e:
        if device == "cpu" or "out of memory" not in str(e).lower():
            raise
        try:
            import torch
            torch.cuda.empty_cache()
        except ImportError:
            pass
        print(f"    out of GPU memory, reading this page on the CPU", flush=True)
        return read(im, None, rec_models.get("cpu"), device="cpu")


def collect(out_dir: Path, records: Path, tag: str = MODEL_TAG) -> tuple[dict, dict]:
    """The per-page files as two things: the recogniser's column reading, by
    row, for the pages it read (McFondue's unless `tag` says another model
    re-read them, see `reread_fullpage.py`); and the raw lines of the typed
    pages for the engine to read."""
    by_hash = {}
    for f in records.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        by_hash[d.get("hash")] = d
    column: dict[str, dict] = {}
    typed: dict[str, dict] = {}
    for f in sorted(out_dir.glob("*-p*.json")):
        doc, _, rest = f.stem.rpartition("-p")
        page = int(rest)
        d = json.loads(f.read_text(encoding="utf-8"))
        lines = d.get("lines") or []
        if d.get("hand") == "typed":
            typed.setdefault(doc, {})[str(page)] = lines
            continue
        rec = by_hash.get(doc)
        if rec is None:
            continue
        geo = next((p.get("geometry") for p in rec.get("pages") or ()
                    if int(p.get("n") or 0) == page), None) or {}
        _by_line, by_col = onto_bands(lines, geo)
        if by_col:
            column.setdefault(doc, {})[str(page)] = by_col
    sidecar = {"model": tag, "by": "row", "variant": "column", "read": column}
    return sidecar, typed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hands", type=Path, default=ROOT / "data" / "hands.json")
    ap.add_argument("--records", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "data" / "fullpage")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "fullpage-corpus",
                    help="prefix for --collect: <out>-column.json, <out>-typed-lines.json")
    ap.add_argument("--model", type=Path,
                    default=Path.home() / ".cache/kraken/ManuMcFondue.mlmodel")
    ap.add_argument("--hand", action="append", default=None,
                    help="only these hands (repeatable); default cursive, unknown, typed")
    ap.add_argument("--limit", type=int, default=0, help="pages to read this run")
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--device", default="cpu", help="cpu or cuda")
    ap.add_argument("--shard", default=None, help="I/N: this worker's share")
    ap.add_argument("--pid-file", type=Path, default=ROOT / "data" / "fullpage.pid")
    a = ap.parse_args(argv)

    a.out_dir.mkdir(parents=True, exist_ok=True)
    if a.collect:
        sidecar, typed = collect(a.out_dir, a.records)
        p = a.out.with_name(a.out.name + "-column.json")
        p.write_text(json.dumps(sidecar, ensure_ascii=False), encoding="utf-8")
        n = sum(len(rows) for pages in sidecar["read"].values() for rows in pages.values())
        print(f"wrote {p}: {n} rows on {sum(len(v) for v in sidecar['read'].values())} pages")
        p = a.out.with_name(a.out.name + "-typed-lines.json")
        p.write_text(json.dumps(typed, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {p}: {sum(len(v) for v in typed.values())} typed pages")
        return 0

    hands = json.loads(a.hands.read_text(encoding="utf-8"))
    todo = shard(pages_wanted(hands, a.out_dir, only=a.hand, limit=a.limit), a.shard)
    done = len(list(a.out_dir.glob("*-p*.json")))
    print(f"{done} pages on disk, {len(todo)} to read", flush=True)
    if not todo:
        return 0
    a.pid_file.write_text(str(os.getpid()))

    import warnings
    from PIL import Image
    from kraken.lib import models
    Image.MAX_IMAGE_PIXELS = None
    rec_model = models.load_any(str(a.model), device=a.device)
    rec_models = {a.device: rec_model}
    if a.device != "cpu":
        rec_models["cpu"] = models.load_any(str(a.model), device="cpu")

    began, read = time.time(), 0
    try:
        for name, doc, page, hand in todo:
            img = chosen_image(a.work, name, page)
            if img is None:
                print(f"  {name[16:28]} p{page}: no image, skipped", flush=True)
                continue
            t0 = time.time()
            im = Image.open(img).convert("L")
            lines = read_with_fallback(
                im, {} if hand == "typed" else rec_models, a.device)
            secs = time.time() - t0
            out = page_file(a.out_dir, doc, page)
            tmp = out.with_suffix(".tmp")
            tmp.write_text(json.dumps({"pdf": name, "page": page, "hand": hand,
                                       "lines": lines, "secs": round(secs, 1)},
                                      ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, out)
            read += 1
            rate = (time.time() - began) / read
            left = (len(todo) - read) * rate / 3600
            print(f"  {name[16:28]} p{page} {hand}: {len(lines)} lines, {secs:.0f}s "
                  f"[{read}/{len(todo)}, ~{left:.1f} h left]", flush=True)
    finally:
        if a.pid_file.exists():
            a.pid_file.unlink()
    print(f"{read} pages in {(time.time() - began) / 3600:.2f} h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
