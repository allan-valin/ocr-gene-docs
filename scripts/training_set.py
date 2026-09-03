"""Pair the ink the engine read with the name a person says it is.

No pretrained recogniser beats this engine on this hand (see
`docs/TASKS-reading-quality.md`), so the one lever left is a recogniser
trained on this archive's own writing. That needs labelled crops, and this
archive already has them: `export_bands.py` saves exactly the image the engine
read, and the hand-read truth pages say what each of those rows says.

Nothing here trains anything. It builds the set and says how big it is, which
is the honest first question -- 142 hand-read names is either enough to move
CER 0.205 or it is not, and that is measurable before anybody is asked to
label more.

    .venv-ocr/bin/python scripts/export_bands.py --records data/transcriptions --out data/bands
    .venv/bin/python scripts/training_set.py --bands data/bands --out data/trainset
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from bench_rec import align                           # noqa: E402
from desembarque.identity import cached_hash          # noqa: E402


def labels_for_page(band_rows: list[dict], truth) -> dict[int, str]:
    """Which band each hand-read name belongs to.

    A truth file says either `rows` — the row numbers a person wrote the names
    against, which need no guessing — or `names`, a run of them read straight
    down the page. For the run, the block sits somewhere among the page's rows
    and the engine's reading is beside it, so the offset is found the way the
    recogniser bench finds it, on what the engine said.
    """
    rows = sorted(band_rows, key=lambda r: r["n"])
    if isinstance(truth, dict):
        have = {r["n"] for r in rows}
        return {int(n): name for n, name in truth.items()
                if name and int(n) in have}
    off = align([r["engine"] for r in rows], list(truth))
    out: dict[int, str] = {}
    for i, name in enumerate(truth):
        if 0 <= off + i < len(rows):
            out[rows[off + i]["n"]] = name
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bands", type=Path, required=True)
    ap.add_argument("--truth", type=Path, default=ROOT / "data" / "truth")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    index = json.loads((args.bands / "bands.json").read_text(encoding="utf-8"))
    by_page = {}
    for key, rows in index.items():
        doc, page = key.split("/")
        by_page[(doc, page)] = rows

    args.out.mkdir(parents=True, exist_ok=True)
    images = args.out / "images"
    images.mkdir(exist_ok=True)

    pairs, missing = [], 0
    for tf in sorted(args.truth.glob("*.json")):
        d = json.loads(tf.read_text(encoding="utf-8"))
        pdf = args.scans / d["pdf"]
        if not pdf.exists():
            missing += 1
            continue
        doc = cached_hash(pdf)
        rows = by_page.get((doc, str(d["page"])))
        if not rows:
            missing += 1
            print(f"  {tf.name}: no crops exported for this page")
            continue
        at = {r["n"]: r for r in rows}
        truth = d.get("rows") or d.get("names") or []
        for n, name in labels_for_page(rows, truth).items():
            src = args.bands / at[n]["file"]
            if not src.exists():
                continue
            dst = images / f"{doc[:8]}_{d['page']}_{n}.png"
            shutil.copy(src, dst)
            pairs.append({"image": f"images/{dst.name}", "label": name,
                          "engine": at[n]["engine"], "source": tf.name})

    out = args.out / "labels.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for row in pairs:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    words = sum(len(p["label"].split()) for p in pairs)
    print(f"{len(pairs)} labelled crops, {words} words, "
          f"{len({p['source'] for p in pairs})} pages; {missing} pages skipped")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
