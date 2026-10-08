"""Take a reading sheet back in as the held-out truth set.

`scripts/make_reading_sheet.py` writes one HTML file somebody reads a manifest
into, on a machine with none of this installed, and it hands back a JSON array.
This is the gate between that array and `data/truth-heldout` — the random draw
of docs/TASKS-honest-measurement.md T5, which nothing is ever tuned against.

    .venv/bin/python scripts/import_reading_sheet.py ~/Downloads/reading-sheet.json

A page that does not say who read it, or which hand it is, is refused here
rather than quietly written: an unlabelled file is exactly how the last truth
set came to be quoted as if a person had read it.

The first sheet came back on 2026-10-07 typed the way a person reads a page:
box 1 was the first name, not the engine's heading band, and a sliver the
engine cut under a neighbour was not a row. `--positional` maps that typing
back onto the engine's band numbers through `desembarque.sheetbands`, against
the reading the sheet was cut from (`--records`). A page the reader could only
fill with the ordinal column — the sheet had shown the wrong strip — is set
aside with a note rather than imported as evidence.

    .venv/bin/python scripts/import_reading_sheet.py ~/Downloads/reading-sheet.json \\
        --positional --records data/transcriptions
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]

from desembarque.sheetbands import align_by_text, positional_map   # noqa: E402
from desembarque.truthset import load_page              # noqa: E402

HANDS = ("typed", "cursive", "mixed")
NAME_LIKE = re.compile(r"[A-Za-zÀ-ÿ]{3}")
ORDINAL = re.compile(r"^\d+(\s+\S{1,4})?$")   # "12", "12 asc": a number with scraps


class Unusable(ValueError):
    """The page as the sheet showed it could not be read into names."""


def usable(rows: dict) -> None:
    """Raise `Unusable` when what was typed is the ordinal column or a cover.

    Two name-like cells is the floor, and a page typed mostly as numbers is
    the ordinal strip however many cells it has.
    """
    cells = [(v or "").strip().lstrip("?").strip() for v in rows.values()]
    cells = [c for c in cells if c and c != "-"]
    names = sum(1 for c in cells if NAME_LIKE.search(c))
    numbers = sum(1 for c in cells if ORDINAL.match(c))
    if names < 2:
        raise Unusable(f"{names} name-like rows typed: a cover note, not a list")
    if numbers > len(cells) / 2:
        raise Unusable(f"{numbers} of {len(cells)} rows are numbers: the sheet "
                       "showed the ordinal column, not the names")


def find_record(records: Path | None, pdf: str) -> dict | None:
    """The stored reading of a scan, found by the file name it carries."""
    if not records or not records.exists():
        return None
    for f in records.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if d.get("file") == pdf:
            return d
    return None


def remap(sheet: dict, record: dict) -> tuple[dict, list[str]]:
    """The sheet's positional boxes put onto the engine's band numbers.

    On a typed page the engine's reading is good enough to say which band
    each typed row belongs to, and that catches the rows the engine never
    cut (`align_by_text`); on a cursive page the reading says nothing and
    the boxes are taken in the order the reader counted them
    (`positional_map`).
    """
    page = int(sheet["page"])
    geo = next((p.get("geometry") for p in record.get("pages") or ()
                if int(p.get("n") or 0) == page), None) or {}
    texts = {int(r["n"]): r.get("name_raw") or "" for r in record.get("rows") or ()
             if r.get("page") == page and r.get("n") is not None}
    keys = sorted(int(k) for k in sheet["rows"])
    if sheet.get("hand") in ("typed", "mixed"):
        mine = [(k, (sheet["rows"][str(k)] or "").strip().lstrip("?").strip())
                for k in keys]
        where = align_by_text(mine, sorted(texts.items()))
    else:
        where = positional_map(keys, geo.get("rows") or [], texts)
    rows, lost = {}, []
    for k in keys:
        value = sheet["rows"][str(k)]
        if where.get(k) is None:
            if (value or "").strip():
                lost.append(value)
            continue
        rows[str(where[k])] = value
    return rows, lost

# BR_RJANRIO_BS_0_RPV_ENT_016429_d0001de0001.pdf -> BS_ENT_016429
NOTATION = re.compile(r"_(?P<fundo>[A-Z]{2})_\d+_[A-Z]+_(?P<series>[A-Z]{3})_"
                      r"(?P<index>\d+)")


def page_name(pdf: str, page: int) -> str:
    """The file name the existing truth set already uses, so both look alike."""
    m = NOTATION.search(pdf)
    stem = (f"{m['fundo']}_{m['series']}_{m['index']}" if m
            else Path(pdf).stem)
    return f"{stem}-p{page}.json"


def check(sheet: dict, where: str) -> None:
    if not (sheet.get("reader") or "").strip():
        raise ValueError(f"{where}: no reader, so it is not evidence "
                         "(docs/TASKS-honest-measurement.md T1)")
    if (sheet.get("hand") or "") not in HANDS:
        raise ValueError(f"{where}: no hand — say {', '.join(HANDS)}; the "
                         "typed/cursive split is the number that matters")
    if not any((v or "").strip() for v in (sheet.get("rows") or {}).values()):
        raise ValueError(f"{where}: nothing read on this page")


def import_sheet(path: Path, out: Path, replace: bool = False,
                 records: Path | None = None, positional: bool = False,
                 note=print) -> list[Path]:
    """Write one truth file per page the sheet carries. Returns what it wrote.

    A page the sheet showed wrong (`usable`) is set aside and said so, not
    written and not fatal: the other pages of the sheet are still evidence.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    pages = payload if isinstance(payload, list) else [payload]
    out.mkdir(parents=True, exist_ok=True)

    written = []
    for i, sheet in enumerate(pages):
        where = f"{Path(path).name}[{i}] {sheet.get('pdf', '?')}"
        check(sheet, where)
        try:
            usable(sheet.get("rows") or {})
        except Unusable as why:
            note(f"  {sheet.get('pdf', '?')} p{sheet.get('page')}: set aside — {why}")
            continue
        target = out / page_name(sheet["pdf"], int(sheet["page"]))
        if target.exists() and not replace:
            raise FileExistsError(
                f"{target} is already read — pass --replace to overwrite it, "
                "and think about why the same page was read twice")
        rows = {str(n): (v or "") for n, v in (sheet.get("rows") or {}).items()}
        mapping, lost = "by band number", []
        if positional:
            stored = find_record(records, sheet["pdf"])
            if stored is None:
                raise FileNotFoundError(
                    f"{where}: --positional needs the reading the sheet was cut "
                    f"from, and {records} holds no record of this scan")
            rows, lost = remap({**sheet, "rows": rows}, stored)
            mapping = "positional"
        record = {
            "source": f"read by hand on the reading sheet by "
                      f"{sheet['reader']}, held-out draw seed 20260907",
            "pdf": sheet["pdf"],
            "page": int(sheet["page"]),
            "hand": sheet["hand"],
            "reader": sheet["reader"],
            "read_on": sheet.get("read_on"),
            "complete": bool(sheet.get("complete")),
            # which reading the band numbers belong to, and how the typing
            # was put onto them; a held-out score is only honest against the
            # same reading
            "cut_from": sheet.get("cut_from") or (records.name if records else None),
            "mapping": mapping,
            "lost": lost,
            "rows": rows,
        }
        target.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")
        load_page(target)                 # it has to load as what it claims
        written.append(target)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sheet", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "truth-heldout")
    ap.add_argument("--replace", action="store_true",
                    help="overwrite a page already read")
    ap.add_argument("--records", type=Path,
                    default=ROOT / "data" / "transcriptions",
                    help="the reading the sheet's bands were cut from")
    ap.add_argument("--positional", action="store_true",
                    help="the boxes were typed by counting rows down the page "
                         "(the first sheet), not against the band numbers")
    a = ap.parse_args(argv)

    written = import_sheet(a.sheet, a.out, replace=a.replace,
                           records=a.records, positional=a.positional)
    for p in written:
        page = load_page(p)
        lost = page.raw.get("lost") or []
        print(f"  {p.name}: {len(page.read())} read, "
              f"{len(page.unreadable())} unreadable, {len(page.absent())} not rows"
              f"  [{page.hand}, by {page.reader}, {page.raw.get('mapping')}]"
              + (f"  lost {lost}" if lost else ""))
    print(f"\n{len(written)} pages into {a.out}. Score them beside the tuned-on "
          "set:\n  .venv/bin/python scripts/bench_search.py --matrix --held-out")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
