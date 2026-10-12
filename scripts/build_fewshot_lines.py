"""Few-shot training lines for a kraken recogniser, cut from the held-out
pages Allan read by hand (2026-10-12).

Kiessling's paper (arXiv 2609.20064) says 40–80 lines of a hand lift the
PP-OCRv6 base models further. The 436 names of `data/truth-heldout/` are
that budget for the clerks' hands: each name sits on a band of a page whose
kraken lines are stored with their polygons in
`data/fullpage-heldout15-lines-poly.json`. For every name on a cursive or
mixed page, the one line crossing the name column on that band is cut to
the column (`<out>/<doc>-p<page>-r<row>.png`) and Allan's reading is its
ground truth (`.gt.txt`) — kraken's `path` format.

The pages are split into two folds by page, so a model trained on fold A is
measured on fold B's names and the other way round; the two readings joined
give one number for all the cursive names, none of them read by a model that
saw its own page. `ketos` trains; `spike_lines_model.py` reads with the
result; `bench_search.py --held-out --second-opinion` scores it.

    .venv/bin/python scripts/build_fewshot_lines.py --out data/fewshot
    .venv-kraken/bin/ketos -d cuda:0 train --arch ppocrv6 \\
        -i ~/.cache/kraken/ppocrv6-hist/medium.safetensors --resize union \\
        -f path -t data/fewshot/train-A.txt -o data/fewshot/model-A ...
"""
from __future__ import annotations

import argparse
import difflib
import json
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from desembarque.search import fold  # noqa: E402
from spike_fullpage import chosen_image  # noqa: E402

HANDS = ("cursive", "mixed")


def lines_by_band(lines: list[dict], geo: dict) -> dict[int, list[dict]]:
    """The lines crossing the name column, by the band each one sits on —
    the same choice `spike_fullpage.onto_bands` makes for the readings."""
    cols = geo.get("columns") or []
    x0, x1 = (cols[0], cols[1]) if len(cols) >= 2 else (0.05, 0.35)
    bands = [tuple(b) for b in geo.get("rows") or [] if b and len(b) == 2]
    out: dict[int, list[dict]] = {}
    for line in lines:
        if line["x1"] < x0 or line["x0"] > x1:
            continue
        yc = (line["y0"] + line["y1"]) / 2
        best, best_ov = None, 0.0
        for n, (a, b) in enumerate(bands, start=1):
            ov = min(b, line["y1"]) - max(a, line["y0"])
            if ov > best_ov and a <= yc <= b:
                best, best_ov = n, ov
        if best is not None:
            out.setdefault(best, []).append(line)
    return out


def crop_box(line: dict, geo: dict, margin: float = 0.01) -> tuple[float, float, float, float]:
    """The line's box clipped to the name column, a little margin either
    side so the first and last letters are not cut, in page fractions."""
    cols = geo.get("columns") or []
    x0, x1 = (cols[0], cols[1]) if len(cols) >= 2 else (0.05, 0.35)
    return (max(line["x0"], x0 - margin), line["y0"],
            min(line["x1"], x1 + margin), line["y1"])


def usable(truth: str, read: str) -> bool:
    """A band whose ink the base model read as something far shorter than
    the name is a ditto mark or a bad cut, not the name: training on it
    would teach the model to invent."""
    letters = lambda t: sum(c.isalpha() for c in t)  # noqa: E731
    first = (read.split() or [""])[0]
    return letters(read) * 2 >= letters(truth) and letters(first) >= 2


def align_page(names: list[tuple[int, str]], bands: dict, reach: int = 2,
               floor: float = 0.6, margin: float = 0.25) -> dict[int, int | None]:
    """Which band each hand-read name is really on, in page order.

    A reading sheet whose row numbers drifted past a band nobody could read
    puts every later name a band too early (OL_PRJ_19266 p4: 20 of 28). The
    base model's reading of the bands says where the ink is. Names are
    walked top to bottom and a band once taken is not given again, so two
    family members with near-identical names keep their own rows; a name
    the readings place nowhere keeps the sheet's row when that row is still
    free and in order, else None."""
    def sim(a, b):
        return difflib.SequenceMatcher(None, fold(a), fold(b)).ratio()
    out: dict[int, int | None] = {}
    last = 0
    for row, name in sorted(names):
        here = sim(name, bands.get(str(row), "")) if row > last else -1.0
        best, best_s = None, -1.0
        for b in range(max(last + 1, row - reach), row + reach + 1):
            if str(b) not in bands:
                continue
            sc = sim(name, bands[str(b)])
            if sc > best_s:
                best, best_s = b, sc
        if best is not None and best_s >= floor and best_s - here >= margin:
            out[row] = best
        elif row > last:
            out[row] = row
        else:
            out[row] = None
        if out[row] is not None:
            last = out[row]
    return out


def side_by_side(lines: list[dict], geo: dict | None = None,
                 edge: float = 0.03) -> list[dict] | None:
    """Lines on one band that share their height — a name the segmenter cut
    at a gap between words — in reading order; None when they are stacked,
    because then the band holds two rows of ink and one name. A piece that
    starts within `edge` of the column's right rule is the next column's
    ink crossing it, not part of the name, and is left out."""
    cols = (geo or {}).get("columns") or []
    if len(cols) >= 2 and len(lines) > 1:
        lines = [l for l in lines if l["x0"] < cols[1] - edge] or lines[:1]
    ordered = sorted(lines, key=lambda l: l["x0"])
    for a, b in zip(ordered, ordered[1:]):
        overlap = min(a["y1"], b["y1"]) - max(a["y0"], b["y0"])
        if overlap < 0.5 * min(a["y1"] - a["y0"], b["y1"] - b["y0"]):
            return None
        if b["x0"] < a["x0"] + 0.5 * (a["x1"] - a["x0"]):
            return None
    return ordered


def crop_band(im, lines: list[dict], geo: dict, margin: float, gap: int = 12):
    """The band's ink as one line image: each line clipped to the column,
    pasted left to right on a white strip of the tallest line's height."""
    crops = []
    for l in lines:
        bx0, by0, bx1, by1 = crop_box(l, geo, margin)
        crops.append(im.crop((int(bx0 * im.width), int(by0 * im.height),
                              int(bx1 * im.width), int(by1 * im.height))))
    if len(crops) == 1:
        return crops[0]
    from PIL import Image
    h = max(c.height for c in crops)
    strip = Image.new("L", (sum(c.width for c in crops) + gap * (len(crops) - 1), h), 255)
    x = 0
    for c in crops:
        strip.paste(c, (x, (h - c.height) // 2))
        x += c.width + gap
    return strip


def write_pairs(rows: list[dict], lines_file: Path, by_hash: dict, work: Path,
                out: Path, margin: float = 0.01, hands=HANDS,
                readings: dict | None = None) -> list[dict]:
    """Cut one training line per usable name; returns what was written.
    `readings` is the base model's column sidecar (`read` → doc → page →
    band → text): it puts a drifted name on its band and tells a ditto mark
    from a name, better than the engine's reading the truth rows carry."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    raw = json.loads(lines_file.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    written, images, aligned = [], {}, {}
    for r in rows:
        if r["hand"] not in hands:
            continue
        rec = by_hash.get(r["doc"])
        lines = (raw.get(r["doc"]) or {}).get(str(r["page"]))
        if not rec or not lines:
            continue
        geo = next((p.get("geometry") for p in rec.get("pages") or ()
                    if int(p.get("n") or 0) == r["page"]), None) or {}
        bands = (readings or {}).get(r["doc"], {}).get(str(r["page"]), {})
        if bands:
            key = (r["doc"], r["page"])
            if key not in aligned:
                aligned[key] = align_page([(x["row"], x["name"]) for x in rows
                                           if (x["doc"], x["page"]) == key
                                           and x["hand"] in hands], bands)
            row = aligned[key].get(r["row"])
            if row is None:
                continue
            read = bands.get(str(row))
        else:
            row, read = r["row"], r.get("read")
        on_band = lines_by_band(lines, geo).get(row, [])
        if not usable(r["name"], read or ""):
            continue
        on_band = side_by_side(on_band, geo) if on_band else None
        if not on_band:
            continue
        key = (r["pdf"], r["page"])
        if key not in images:
            img = chosen_image(work, r["pdf"], r["page"])
            images[key] = Image.open(img).convert("L") if img else None
        im = images[key]
        if im is None:
            continue
        crop = crop_band(im, on_band, geo, margin)
        stem = f"{r['doc'][:8]}-p{r['page']}-r{row}"
        crop.save(out / f"{stem}.png")
        (out / f"{stem}.gt.txt").write_text(r["name"].strip() + "\n", encoding="utf-8")
        written.append({"image": str(out / f"{stem}.png"), "text": r["name"],
                        "doc": r["doc"], "page": r["page"], "hand": r["hand"],
                        "pdf": r["pdf"], "row": row, "sheet_row": r["row"],
                        "lines": len(on_band)})
    return written


def folds(written: list[dict], k: int = 2) -> list[list[tuple[str, int]]]:
    """Pages dealt into `k` folds, largest page first, each to the fold with
    the fewest lines so far — the folds come out near equal."""
    sizes: dict[tuple[str, int], int] = {}
    for w in written:
        sizes[(w["doc"], w["page"])] = sizes.get((w["doc"], w["page"]), 0) + 1
    out: list[list[tuple[str, int]]] = [[] for _ in range(k)]
    load = [0] * k
    for page, n in sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0])):
        i = load.index(min(load))
        out[i].append(page)
        load[i] += n
    return out


def merge_folds(sidecars: list[dict], folds: list[list[tuple[str, int]]],
                base: dict, tag: str) -> dict:
    """One sidecar from the fold models: each held-out page read by the
    model that never saw it, every other page by the base model, so the
    bench's number for the whole set is honest and comparable."""
    read = {doc: dict(pages) for doc, pages in base["read"].items()}
    for side, pages in zip(sidecars, folds):
        for doc, page in pages:
            got = side["read"].get(doc, {}).get(str(page))
            if got is not None:
                read.setdefault(doc, {})[str(page)] = got
    return {"model": tag, "by": "row", "variant": "column", "read": read}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lines", type=Path, default=ROOT / "data" / "fullpage-heldout15-lines-poly.json")
    ap.add_argument("--truth", type=Path, default=ROOT / "data" / "truth-heldout")
    ap.add_argument("--records", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "fewshot")
    ap.add_argument("--readings", type=Path,
                    default=ROOT / "data" / "fullpage-heldout15-ppocrv6-medium-column.json",
                    help="the base model's column sidecar, for realigning and ditto marks")
    ap.add_argument("--margin", type=float, default=0.01)
    ap.add_argument("--folds", type=int, default=2)
    ap.add_argument("--merge", nargs="*", type=Path, default=None,
                    help="fold sidecars (A, B, ...) to join into <out>/fewshot-column.json, "
                         "the other pages read by --readings")
    a = ap.parse_args(argv)

    if a.merge is not None:
        sides = [json.loads(p.read_text(encoding="utf-8")) for p in a.merge]
        parts = [[tuple(x.values()) for x in json.loads(
                  (a.out / f"pages-{chr(ord('A') + i)}.json").read_text())]
                 for i in range(len(sides))]
        base = json.loads(a.readings.read_text(encoding="utf-8"))
        merged = merge_folds(sides, parts, base, "PP-OCRv6-hist-medium-fewshot-page-column")
        p = a.out / "fewshot-column.json"
        p.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {p}: {sum(len(v) for v in parts)} pages from the fold models")
        return 0

    bench = runpy.run_path(str(ROOT / "scripts" / "bench_search.py"))
    rows = bench["truth_rows"](a.records, a.scans, truth_dir=a.truth)
    by_hash = {}
    for f in a.records.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        by_hash[d.get("hash")] = d
    readings = json.loads(a.readings.read_text(encoding="utf-8"))["read"] if a.readings.exists() else None
    written = write_pairs(rows, a.lines, by_hash, a.work, a.out / "lines", a.margin,
                          readings=readings)
    wanted = [r for r in rows if r["hand"] in HANDS]
    moved = sum(1 for w in written if w["row"] != w["sheet_row"])
    stitched = sum(1 for w in written if w["lines"] > 1)
    print(f"{len(written)} lines cut of {len(wanted)} {'/'.join(HANDS)} names "
          f"({len(wanted) - len(written)} skipped: ditto, no line, stacked lines; "
          f"{moved} realigned, {stitched} stitched from two lines)")
    parts = folds(written, a.folds)
    for i, pages in enumerate(parts):
        tag = chr(ord("A") + i)
        mine = [w for w in written if (w["doc"], w["page"]) in pages]
        others = [w for w in written if (w["doc"], w["page"]) not in pages]
        (a.out / f"eval-{tag}.txt").write_text("".join(w["image"] + "\n" for w in mine))
        (a.out / f"train-{tag}.txt").write_text("".join(w["image"] + "\n" for w in others))
        (a.out / f"pages-{tag}.json").write_text(json.dumps(
            [{"doc": d, "page": p} for d, p in pages]))
        print(f"  fold {tag}: {len(mine)} lines on {len(pages)} pages held out, "
              f"train-{tag}.txt has the other {len(others)}")
    (a.out / "lines.json").write_text(json.dumps(written, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
