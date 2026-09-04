"""Pair the ink the engine read with the name a person says it is.

No pretrained recogniser beats this engine on this hand (see
`docs/TASKS-reading-quality.md`), so the one lever left is a recogniser
trained on this archive's own writing. That needs labelled crops, and this
archive already has them: `export_bands.py` saves exactly the image the engine
read, and the hand-read truth pages say what each of those rows says.

The other source is every row somebody has retyped on the review screen, and
that is the one that grows: the truth pages are a fixed six and a correction
is made every time anybody uses the tool. Those crops were never
kept, but since T4 each page stores the geometry its rows were cut from, so
the same ink can be cut again from the record -- retroactively, for
corrections made months ago, and without a recogniser. See
`desembarque.bandcrops`.

Nothing here trains anything. It builds the set and says how big it is, which
was the honest first question -- and it has been answered: 155 crops is not
enough. Three epochs on them take a held-out page from CER 0.340 to 0.451,
because what a set that size teaches is the archive's vocabulary rather than
its hands (docs/TASKS-reading-quality.md, 2026-09-04). So the number this
prints is the one to grow.

    .venv-ocr/bin/python scripts/export_bands.py --records data/transcriptions --out data/bands
    .venv/bin/python scripts/training_set.py --bands data/bands \
        --records data/transcriptions --out data/trainset
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from desembarque import bandcrops, truthset           # noqa: E402
from desembarque.identity import cached_hash          # noqa: E402
from page_geometry import page_image                  # noqa: E402


NAME_FIELDS = ("name", "surname", "given")


def measured_pages(record: dict) -> dict[int, dict]:
    """The geometry of each page that was measured, by page number."""
    return {p["n"]: p["geometry"] for p in (record.get("pages") or [])
            if isinstance(p, dict) and p.get("n") and p.get("geometry")}


def corrections_in(record: dict, verified: bool = False) -> list[dict]:
    """Every row of a record whose name a person has settled, in order.

    A retyped name is the strongest label there is: somebody looked at the ink
    and said what it says. Choosing one of the offered readings is the same
    word from the same person and is kept apart only so it can be counted
    separately. A row merely marked verified is weaker -- the person may have
    been checking another column -- so it is not counted with the typing
    unless it is asked for.

    A page the engine never measured cannot have a crop cut from it, so its
    rows are not offered as labels rather than being labelled against a
    picture nobody can produce.
    """
    have = measured_pages(record)
    out = []
    for row in record.get("rows") or ():
        page = row.get("page")
        if page not in have or not row.get("n"):
            continue
        edits = [e for e in (row.get("edits") or ())
                 if e.get("field") in NAME_FIELDS and (e.get("to") or "").strip()]
        if edits:
            last = max(edits, key=lambda e: str(e.get("at") or ""))
            how = ("chosen" if "alternativa" in str(last.get("from") or "")
                   else "typed")
            label = last["to"].strip()
        elif verified and row.get("verified") and (row.get("name_raw") or "").strip():
            how, label = "verified", row["name_raw"].strip()
        else:
            continue
        out.append({"page": page, "n": row["n"], "label": label, "how": how,
                    "engine": (row.get("name_raw") or "").strip()})
    return out


def band_rows_of(record: dict, page: int) -> list[dict]:
    """A page's read rows in the shape an exported band index has them in."""
    return sorted(({"n": r["n"], "engine": (r.get("name_raw") or "").strip()}
                   for r in record.get("rows") or ()
                   if r.get("page") == page and r.get("n")
                   and (r.get("name_raw") or "").strip()),
                  key=lambda r: r["n"])


def labels_for_page(band_rows: list[dict], truth: dict) -> dict[int, str]:
    """Which row each hand-read name belongs to, by row number.

    Two shapes, because the pages come in two kinds. `rows` is keyed by the row
    numbers somebody wrote the names against and is taken as it stands. `names`
    is a run read straight down the page, and it is aligned to the rows rather
    than counted from `first_row` or from a single best-fit offset: the stored
    first row goes stale, and one offset drifts past the first row that carries
    no reading. Both were happening, and on BS_ENT_015061-p6 the drift put 42
    rows at CER above 1 for the engine and the second recogniser alike — the
    signature of a mislabelled set, not of a bad recogniser. See
    `desembarque.truthset.aligned`.
    """
    rows = sorted(band_rows, key=lambda r: r["n"])
    if truth.get("rows"):
        have = {r["n"] for r in rows}
        return {int(n): name for n, name in truth["rows"].items()
                if name and str(name).strip() and int(n) in have}
    names = [n for n in (truth.get("names") or ()) if n and str(n).strip()]
    placed = truthset.aligned([r["engine"] for r in rows], names)
    return {rows[i]["n"]: name for i, name in placed.items()}



def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bands", type=Path, default=None,
                    help="an `export_bands.py` directory, for the hand-read "
                         "truth pages; the corrections need none")
    ap.add_argument("--records", type=Path, default=None,
                    help="take a label from every row somebody has retyped in "
                         "these records, cutting its crop from the geometry "
                         "the page stores")
    ap.add_argument("--variant", choices=("carved", "strip"), default="strip",
                    help="which picture of the row to keep: the engine's own "
                         "carved crop, or the plain rectangle of the band. "
                         "TrOCR reads the carved crop of a cursive name at "
                         "CER 0.609 and the band at 0.567, so a set built for "
                         "a pretrained model wants the band")
    ap.add_argument("--verified", action="store_true",
                    help="count a row merely marked verified as a label too, "
                         "which is weaker evidence: the person may have been "
                         "checking another column")
    ap.add_argument("--truth", type=Path, default=ROOT / "data" / "truth")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    by_page = {}
    if args.bands:
        index = json.loads((args.bands / "bands.json").read_text(encoding="utf-8"))
        for key, rows in index.items():
            doc, page = key.split("/")
            by_page[(doc, page)] = rows

    args.out.mkdir(parents=True, exist_ok=True)
    images = args.out / "images"
    images.mkdir(exist_ok=True)

    # keyed by the file the crop is written to, so a row that is both a truth
    # row and a correction is one pair and the correction wins: it is the later
    # word, from somebody sitting in front of the ink
    pairs: dict[str, dict] = {}
    missing = 0
    for tf in sorted(args.truth.glob("*.json")) if by_page else ():
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
        for n, name in labels_for_page(rows, d).items():
            key = "strip" if args.variant == "strip" else "file"
            named = at[n].get(key) or at[n].get("file")
            src = args.bands / named
            if not src.exists():
                continue
            dst = images / f"{doc[:8]}_{d['page']}_{n}.png"
            shutil.copy(src, dst)
            pairs[dst.name] = {"image": f"images/{dst.name}", "label": name,
                               "engine": at[n]["engine"], "how": "hand-read",
                               "doc": doc, "page": d["page"], "n": n,
                               "source": tf.name}

    uncut = 0
    for rf in sorted(args.records.glob("*.json")) if args.records else ():
        rec = json.loads(rf.read_text(encoding="utf-8"))
        found = corrections_in(rec, verified=args.verified)
        if not found:
            continue
        pdf = args.scans / (rec.get("file") or "")
        if not pdf.exists():
            missing += 1
            continue
        doc = cached_hash(pdf)
        geo = measured_pages(rec)
        wanted: dict[int, list[dict]] = {}
        for c in found:
            wanted.setdefault(c["page"], []).append(c)
        for page, rows in sorted(wanted.items()):
            img = page_image(pdf, page, args.work)
            if img is None:
                uncut += len(rows)
                continue
            cut = bandcrops.crops_for(img, geo.get(page),
                                      rows=[c["n"] for c in rows])
            for c in rows:
                band = cut.get(c["n"])
                if not band:
                    uncut += 1
                    continue
                dst = images / f"{doc[:8]}_{page}_{c['n']}.png"
                band[args.variant].convert("RGB").save(dst)
                pairs[dst.name] = {"image": f"images/{dst.name}",
                                   "label": c["label"], "engine": c["engine"],
                                   "how": c["how"], "doc": doc, "page": page,
                                   "n": c["n"], "source": rf.name,
                                   # how the page was measured, because a
                                   # geometry put back by `backfill_geometry.py`
                                   # is a fresh measurement of the page rather
                                   # than the one its rows were cut from, and a
                                   # crop cut from it is only as good as that
                                   # agreement
                                   "geometry": (geo.get(page) or {}).get(
                                       "measured_by")}

    out = args.out / "labels.jsonl"
    rows = sorted(pairs.values(), key=lambda p: p["image"])
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    words = sum(len(p["label"].split()) for p in rows)
    print(f"the {args.variant} crop of each row")
    by_how = Counter(p["how"] for p in rows)
    print(f"{len(rows)} labelled crops, {words} words, "
          f"{len({p['source'] for p in rows})} sources; {missing} skipped"
          + (f", {uncut} rows with no crop" if uncut else ""))
    print("  " + ", ".join(f"{n} {how}" for how, n in by_how.most_common()))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
