"""How well is a column other than the name read, against a page typed by hand.

The engine reads the name column and nothing else, so every other field in the
corpus is null by construction. Before any of them ships, this says how well
each one is read — per column, because they fail differently: age is digits,
sex is one letter, nationality and profession are short closed vocabularies,
and the notes are free text nobody can score.

The truth is BS.ENT.017397, a typewritten page somebody transcribed by hand:
26 rows with a nationality, an age, a sex, a civil state, a profession, a port
and a class against every one. It is the typed half of the answer. A cursive
page needs its own truth file and does not have one yet, and a number measured
on typescript must never be quoted as if it covered the hand.

    .venv-ocr/bin/python scripts/bench_columns.py
    .venv-ocr/bin/python scripts/bench_columns.py --column idade

Reading a page costs about twenty seconds a column, so this is a minute, not
the eleven hours a corpus pass costs.
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from desembarque.engine_paddle import (CELL_INSET_X, PaddleEngine,  # noqa: E402
                                       cells_from_bands)
from desembarque.vocab import Vocabulary                              # noqa: E402
from page_geometry import page_image                                  # noqa: E402

# Which stored field each measured column holds, for the columns worth scoring.
# `observacoes` is free text — an address, a hotel, a name — and a character
# error rate over it says nothing anybody can act on.
SCORED = {"nacionalidade": "nationality", "idade": "age", "sexo": "sex",
          "estado": "status", "profissao": "occupation",
          "procedencia": "origin", "classe": "class"}

TRUTH = {"notation": "BS.ENT.017397", "page": 2, "first_row": 1}


def fold(s) -> str:
    s = unicodedata.normalize("NFKD", str(s if s is not None else ""))
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


def cer(truth: str, got: str) -> float:
    t, g = fold(truth), fold(got)
    if not t:
        return 0.0 if not g else 1.0
    same = sum(b.size for b in difflib.SequenceMatcher(None, t, g).get_matching_blocks())
    return max(0.0, min(1.0, 1 - same / max(len(t), len(g))))


def hand_transcription(cache: Path) -> tuple[dict, list[dict]]:
    """The record somebody typed by hand, and its rows in page order."""
    for f in sorted(cache.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if d.get("notation") == TRUTH["notation"] and d.get("rows"):
            return d, sorted(d["rows"], key=lambda r: r.get("n") or 0)
    raise SystemExit(f"no hand transcription of {TRUTH['notation']} on disk")


def prepared(recognize, how: str):
    """The recogniser with every cell put through `how` first.

    A cell is a tenth the width of a name and holds two digits or one letter,
    which is a different picture from the one the recogniser was measured on.
    `upscale2` is the cheap thing to try — it is what moved nothing on the name
    column and might move this one, which is the point of asking separately.
    """
    from PIL import Image, ImageOps
    if how == "none":
        return recognize

    def prep(im):
        if how == "upscale2":
            return im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
        if how == "upscale4":
            return im.resize((im.width * 4, im.height * 4), Image.LANCZOS)
        if how == "autocontrast":
            return ImageOps.autocontrast(im.convert("L"), cutoff=1)
        return im

    return lambda crops: recognize([prep(c) for c in crops])


def read_columns(pdf: Path, page: int, pagecache: Path,
                 wanted: list[str], how: str = "none",
                 inset: float = CELL_INSET_X) -> tuple[dict, dict]:
    """Each wanted column of one page, as the engine reads it today."""
    from PIL import Image
    img = page_image(pdf, page, pagecache)
    eng = PaddleEngine()
    eng._import()
    geo = eng._printed_table(img)
    if geo is None:
        raise SystemExit("no printed table on that page")
    measured = geo.normalized_columns()
    im = Image.open(img).convert("L").rotate(geo.skew, resample=Image.BICUBIC,
                                             fillcolor=255)
    out = {}
    for field in wanted:
        if field not in measured:
            continue
        out[field] = cells_from_bands(geo, im.size, field,
                                      prepared(eng._recognize, how),
                                      lambda i, box: im.crop(box),
                                      inset=(inset, inset))
    return measured, out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--column", default=None, help="one column instead of all")
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--pagecache", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--prep", default="none",
                    choices=["none", "upscale2", "upscale4", "autocontrast"],
                    help="what to do to a cell before reading it")
    ap.add_argument("--inset", type=float, default=CELL_INSET_X,
                    help="how much of each edge of a cell to leave behind, so "
                         "the printed rules are not read as strokes")
    ap.add_argument("--vocab", type=Path,
                    default=ROOT / "data" / "column_vocab.json",
                    help="the closed lists each column is snapped to")
    ap.add_argument("--floor", type=float, default=None,
                    help="how near a reading has to be before it is snapped")
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)

    record, rows = hand_transcription(a.cache)
    # The hand transcription predates the field that names its file, so the
    # scan is found by the notation the record is filed under.
    stem = TRUTH["notation"].replace("BS.ENT.", "")
    pdf = next((p for p in a.scans.rglob("*.pdf") if stem in p.name), None)
    if pdf is None:
        raise SystemExit(f"the scan of {TRUTH['notation']} is not in {a.scans}")

    wanted = [a.column] if a.column else list(SCORED)
    measured, read = read_columns(pdf, TRUTH["page"], a.pagecache, wanted,
                                  a.prep, a.inset)

    print(f"{TRUTH['notation']} p{TRUTH['page']}, {len(rows)} rows typed by hand")
    print("columns measured:", ", ".join(sorted(measured)))
    missing = [c for c in wanted if c not in measured]
    if missing:
        print("not measured on this page:", ", ".join(missing))

    from desembarque import vocab as vocab_mod
    voc = Vocabulary.load(a.vocab)
    if a.floor is not None:
        # one floor for every column, which is what a sweep asks
        vocab_mod.FLOOR = a.floor
        voc.floors = {f: a.floor for f in voc.floors}

    report = {"page": TRUTH, "rows": len(rows), "prep": a.prep,
              "inset": a.inset, "floor": vocab_mod.FLOOR, "columns": {}}
    # `snapped` is of the rows a value was snapped on: how often it is the word
    # the clerk typed. `offered` is how many rows were snapped at all, because a
    # column that snaps three rows of twenty-six is not a column that reads.
    print("column         rows  exact  mean CER  offered  snapped right")
    for field in wanted:
        cells = read.get(field)
        if not cells:
            continue
        by_n = {c["n"]: c["text"] for c in cells}
        pairs = [(r.get(SCORED[field]), by_n.get(int(TRUTH["first_row"]) + k, ""))
                 for k, r in enumerate(rows)]
        pairs = [(t, g) for t, g in pairs if t not in (None, "")]
        if not pairs:
            continue
        exact = sum(1 for t, g in pairs if fold(t) == fold(g)) / len(pairs)
        mean = sum(cer(t, g) for t, g in pairs) / len(pairs)
        snaps = [(t, (voc.snap(field, g) or {}).get("value")) for t, g in pairs]
        offered = [(t, v) for t, v in snaps if v]
        right = sum(1 for t, v in offered if fold(t) == fold(v))
        report["columns"][field] = {
            "rows": len(pairs), "exact": round(exact, 3), "cer": round(mean, 3),
            "offered": len(offered), "snapped_right": right,
            "snapped_exact": round(right / len(pairs), 3),
            "sample": [[str(t), g, (voc.snap(field, g) or {}).get("value")]
                       for t, g in pairs[:5]]}
        print(f"{field:<13}  {len(pairs):<4}  {exact:<5.3f}  {mean:<8.3f}  "
              f"{len(offered):<7}  {right}")
    if a.json:
        a.json.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                          encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
