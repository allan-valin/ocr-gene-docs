"""Take a reading sheet back in as the held-out truth set.

`scripts/make_reading_sheet.py` writes one HTML file somebody reads a manifest
into, on a machine with none of this installed, and it hands back a JSON array.
This is the gate between that array and `data/truth-heldout` — the random draw
of docs/TASKS-honest-measurement.md T5, which nothing is ever tuned against.

    .venv/bin/python scripts/import_reading_sheet.py ~/Downloads/reading-sheet.json

A page that does not say who read it, or which hand it is, is refused here
rather than quietly written: an unlabelled file is exactly how the last truth
set came to be quoted as if a person had read it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]

from desembarque.truthset import load_page             # noqa: E402

HANDS = ("typed", "cursive", "mixed")

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


def import_sheet(path: Path, out: Path, replace: bool = False) -> list[Path]:
    """Write one truth file per page the sheet carries. Returns what it wrote."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    pages = payload if isinstance(payload, list) else [payload]
    out.mkdir(parents=True, exist_ok=True)

    written = []
    for i, sheet in enumerate(pages):
        where = f"{Path(path).name}[{i}] {sheet.get('pdf', '?')}"
        check(sheet, where)
        target = out / page_name(sheet["pdf"], int(sheet["page"]))
        if target.exists() and not replace:
            raise FileExistsError(
                f"{target} is already read — pass --replace to overwrite it, "
                "and think about why the same page was read twice")
        record = {
            "source": f"read by hand on the reading sheet by "
                      f"{sheet['reader']}, held-out draw seed 20260907",
            "pdf": sheet["pdf"],
            "page": int(sheet["page"]),
            "hand": sheet["hand"],
            "reader": sheet["reader"],
            "read_on": sheet.get("read_on"),
            "complete": bool(sheet.get("complete")),
            "rows": {str(n): (v or "") for n, v in (sheet.get("rows") or {}).items()},
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
    a = ap.parse_args(argv)

    written = import_sheet(a.sheet, a.out, replace=a.replace)
    for p in written:
        page = load_page(p)
        print(f"  {p.name}: {len(page.read())} read, "
              f"{len(page.unreadable())} unreadable, {len(page.absent())} not rows"
              f"  [{page.hand}, by {page.reader}]")
    print(f"\n{len(written)} pages into {a.out}. Score them beside the tuned-on "
          "set:\n  .venv/bin/python scripts/bench_search.py --matrix --held-out")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
