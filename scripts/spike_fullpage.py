"""Throwaway spike (2026-10-08): read the whole page, then find the column.

Allan's reading of the first held-out sheet showed that half the pages had
been cut at the ordinal strip, and asked whether the pipeline should instead
transcribe the entire page and sort the text into columns afterwards. This
measures the cheap version of that: kraken's page segmenter (blla) finds
every line on the page with its coordinates, McFondue reads each line with
per-character cut positions, and the name column is then taken off the page
by geometry alone -- the characters whose cuts fall inside the stored name
column -- with no language model in the loop. Two sidecars come out, keyed to
the engine's bands by vertical overlap so `bench_search.py --held-out
--second-opinion` scores them through the index like every other reading:

  * `line`   -- the whole segmented line that crosses the name column
  * `column` -- that line clipped to the name column by its cuts

    .venv-ocr/bin/python scripts/spike_fullpage.py --out data/fullpage-heldout
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]


def record_for(records: Path, pdf: str) -> dict | None:
    for f in records.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if d.get("file") == pdf:
            return d
    return None


def chosen_image(work: Path, pdf: str, page: int) -> Path | None:
    f = work / f"{Path(pdf).stem}-p{page}-chosen.txt"
    if not f.exists():
        return None
    p = Path(f.read_text(encoding="utf-8").strip())
    return p if p.exists() else None


from desembarque.secondreading import (  # noqa: E402,F401
    clip, line_record, onto_bands, read_page)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--truth", type=Path, default=ROOT / "data" / "truth-heldout")
    ap.add_argument("--records", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--model", type=Path,
                    default=Path.home() / ".cache/kraken/ManuMcFondue.mlmodel")
    ap.add_argument("--out", type=Path, required=True,
                    help="prefix: writes <out>-line.json, <out>-column.json, "
                         "<out>-lines.json")
    a = ap.parse_args(argv)

    from PIL import Image
    from kraken.lib import models
    rec_model = models.load_any(str(a.model))

    pages = []
    for f in sorted(a.truth.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        pages.append((d["pdf"], int(d["page"])))

    line_side, col_side, raw = {}, {}, {}
    total = 0.0
    for pdf, page in pages:
        rec = record_for(a.records, pdf)
        img = chosen_image(a.work, pdf, page)
        if rec is None or img is None:
            print(f"  {pdf} p{page}: no record or no image, skipped")
            continue
        geo = next((p.get("geometry") for p in rec.get("pages") or ()
                    if int(p.get("n") or 0) == page), None) or {}
        began = time.time()
        im = Image.open(img).convert("L")
        lines = read_page(im, None, rec_model)
        secs = time.time() - began
        total += secs
        by_line, by_col = onto_bands(lines, geo)
        doc = rec["hash"]
        line_side.setdefault(doc, {})[str(page)] = by_line
        col_side.setdefault(doc, {})[str(page)] = by_col
        raw.setdefault(doc, {})[str(page)] = lines
        print(f"  {pdf[16:28]} p{page}: {len(lines)} lines, {len(by_col)} bands "
              f"with column text, {secs:.0f}s", flush=True)

    tag = a.model.stem
    for name, side in (("line", line_side), ("column", col_side)):
        p = a.out.with_name(a.out.name + f"-{name}.json")
        p.write_text(json.dumps({"model": f"{tag}-page-{name}", "by": "row",
                                 "variant": name, "read": side}, ensure_ascii=False))
        print(f"wrote {p}")
    p = a.out.with_name(a.out.name + "-lines.json")
    p.write_text(json.dumps(raw, ensure_ascii=False))
    print(f"wrote {p}\n{len(pages)} pages in {total:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
