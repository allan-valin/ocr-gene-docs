"""Spike (2026-10-10): a VLM on the lines kraken found, private branch only.

The whole-page pass stored every line with its box and, from 2026-10-09, its
polygon (`data/fullpage/<hash>-p<N>.json`). McFondue over those lines, clipped
to the name column, is the best shippable second reading (68 of 212 held-out
cursive names at five). CHURRO 3B read the engine's own crops better than
anything measured (85 of 110 on the tuned-on set) but is research-licence
only, so this reads it over the same lines, for Allan's own search and for
no release: the question is whether it beats McFondue on the held-out pages
by two digits, before any dossier is read by it.

Each line that crosses the name column and lands in a band is cut from the
chosen page image, clipped to the column with a little air, masked to its
polygon where one is stored, and sent to a llama-server one crop at a time
with CHURRO's row prompt. Writes `<out>-column.json` in the shape
`bench_search.py --held-out --second-opinion` scores, page by page, so a
killed run resumes.

    .venv/bin/python scripts/spike_vlm_on_lines.py --serve \\
        --pages data/heldout-pages.json --out data/fullpage-heldout15-churro
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from read_vlm import STYLES, Server, find  # noqa: E402
from spike_fullpage import chosen_image, onto_bands  # noqa: E402


def tag_for(model: Path) -> str:
    """What a sidecar read by these weights is named after: CHURRO's keeps the
    tag the earlier sidecars carry, anything else is its file's name."""
    return model.name.replace("churro-3B.", "churro-3B-").replace(".gguf", "")


def column_of(geo: dict) -> tuple[float, float]:
    cols = geo.get("columns") or []
    return (cols[0], cols[1]) if len(cols) >= 2 else (0.05, 0.35)


def in_a_band(line: dict, geo: dict) -> bool:
    """Whether `onto_bands` would give this line to a row at all."""
    x0, x1 = column_of(geo)
    if line["x1"] < x0 or line["x0"] > x1:
        return False
    yc = (line["y0"] + line["y1"]) / 2
    return any(a <= yc <= b for a, b in
               (tuple(r) for r in geo.get("rows") or [] if r and len(r) == 2))


def crop_line(im, line: dict, geo: dict, pad: float = 0.004):
    """The line's ink inside the name column, on white, as an RGB picture."""
    from PIL import Image, ImageDraw
    W, H = im.size
    cx0, cx1 = column_of(geo)
    x0 = max(0.0, max(line["x0"], cx0) - pad)
    x1 = min(1.0, min(line["x1"], cx1) + pad)
    y0 = max(0.0, line["y0"] - pad)
    y1 = min(1.0, line["y1"] + pad)
    box = (int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))
    if box[2] - box[0] < 8 or box[3] - box[1] < 8:
        return None
    piece = im.crop(box)
    if line.get("boundary"):
        mask = Image.new("L", piece.size, 0)
        pts = [(x * W - box[0], y * H - box[1]) for x, y in line["boundary"]]
        ImageDraw.Draw(mask).polygon(pts, fill=255)
        # a little air around the polygon so the strokes it touches survive
        from PIL import ImageFilter
        mask = mask.filter(ImageFilter.MaxFilter(7))
        white = Image.new("L", piece.size, 255)
        piece = Image.composite(piece, white, mask)
    return piece.convert("RGB")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pages", type=Path, default=ROOT / "data" / "heldout-pages.json",
                    help="a JSON list of {pdf, page}")
    ap.add_argument("--records", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--fullpage", type=Path, default=ROOT / "data" / "fullpage")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--model", type=Path, default=None)
    ap.add_argument("--mmproj", type=Path, default=None)
    ap.add_argument("--style", choices=sorted(STYLES), default="churro",
                    help="how the model is asked (see read_vlm.STYLES)")
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--port", type=int, default=8788)
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--out", type=Path, required=True, help="prefix for -column.json")
    a = ap.parse_args(argv)

    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    style = STYLES[a.style]
    model = a.model or (a.style == "churro" and find("churro-3B.Q4_K_M.gguf"))
    mmproj = a.mmproj or (a.style == "churro" and find("churro-3B.mmproj-f16.gguf"))
    if not model or not mmproj:
        print("no weights: --model and --mmproj, or CHURRO's in the hub cache")
        return 1
    tag = tag_for(model)
    row_prompt = style["row"]

    by_file = {}
    for f in a.records.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        by_file[d.get("file")] = d
    pages = json.loads(a.pages.read_text(encoding="utf-8"))
    out = a.out.with_name(a.out.name + "-column.json")
    col_side = (json.loads(out.read_text(encoding="utf-8")).get("read") or {}
                if out.exists() else {})

    def save():
        out.write_text(json.dumps({"model": f"{tag}-page-column", "by": "row",
                                   "variant": "column", "read": col_side},
                                  ensure_ascii=False))

    def run(server):
        began, rows = time.time(), 0
        for p in pages:
            rec = by_file.get(p["pdf"])
            page = int(p["page"])
            if rec is None:
                print(f"  {p['pdf']} p{page}: no record")
                continue
            doc = rec["hash"]
            if str(page) in (col_side.get(doc) or {}):
                continue
            lines_f = a.fullpage / f"{doc}-p{page}.json"
            img = chosen_image(a.work, p["pdf"], page)
            if not lines_f.exists() or img is None:
                print(f"  {p['pdf'][16:28]} p{page}: no lines or no image")
                continue
            geo = next((pg.get("geometry") for pg in rec.get("pages") or ()
                        if int(pg.get("n") or 0) == page), None) or {}
            lines = [l for l in json.loads(lines_f.read_text())["lines"]
                     if in_a_band(l, geo)]
            im = Image.open(img).convert("L")
            cx0, cx1 = column_of(geo)
            said, t0 = [], time.time()
            for i, line in enumerate(lines):
                piece = crop_line(im, line, geo)
                if piece is None:
                    continue
                tmp = a.work / f"{doc[:8]}-p{page}-l{i}-vlm.png"
                piece.save(tmp)
                try:
                    text, _ = server.read(tmp, row_prompt, predict=64)
                except Exception as e:  # llama-server says 500 on a crop it cannot see
                    print(f"    line {i} refused: {e}")
                    text = ""
                tmp.unlink(missing_ok=True)
                if text:
                    # clipped to the column already, so the band mapper keeps it
                    said.append({**line, "x0": max(line["x0"], cx0),
                                 "x1": min(line["x1"], cx1), "text": text.strip(),
                                 "cuts": []})
            _by_line, by_col = onto_bands(said, geo)
            col_side.setdefault(doc, {})[str(page)] = by_col
            save()
            rows += len(said)
            print(f"  {p['pdf'][16:28]} p{page} ({rec.get('hand') or '?'}): "
                  f"{len(lines)} lines, {len(by_col)} bands, {time.time() - t0:.0f}s",
                  flush=True)
        print(f"wrote {out}: {rows} lines in {time.time() - began:.0f}s")

    if a.serve:
        with Server.from_style(model, mmproj, a.port, a.threads, style) as server:
            run(server)
    else:
        server = Server.from_style(model, mmproj, a.port, a.threads, style)
        server.url = f"http://127.0.0.1:{a.port}"
        run(server)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
