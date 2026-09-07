"""Write a second recogniser's sidecar into the corpus it was read from.

`read_bands.py` reads the crops the engine exported and writes what another
model said into a sidecar. Until now only `bench_search.py` could read that
file, so a reading worth three more names in the top five was worth nothing to
anybody using the tool. This puts it on the row, where `desembarque.search`
spells the row by it and counts it with the guesses.

    .venv/bin/python scripts/apply_second_opinion.py \
        --sidecar data/side-fair.json --records data/transcriptions \
        --bands data/bands-fair

`--bands` is the export the sidecar was read from, and it is what keeps a
reading on its own row: those row numbers age, a re-read renumbers a page, and
a reading pasted onto row 14 after that names a stranger. Give it whenever the
records may have been read again since the crops were cut — 21 of 1,787 rows
were refused that way on the fifteen-dossier subcorpus.

Nothing is written until `--write` is given: the default is a count of what
would land, per document, which is the number to look at before touching a
corpus. A row somebody typed is never given a machine's reading, a reading for
a row that is not there is refused rather than invented, and a second run over
the same sidecar writes nothing at all.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque.secondopinion import with_second_readings  # noqa: E402


def exported_readings(bands: Path) -> dict[str, dict[tuple[int, int], str]]:
    """What the engine said about each row on the day the crops were cut."""
    index = json.loads((bands / "bands.json").read_text(encoding="utf-8"))
    out: dict[str, dict[tuple[int, int], str]] = {}
    for key, got in index.items():
        doc, _, page = key.partition("/")
        for r in got or ():
            out.setdefault(doc, {})[(int(page), r["n"])] = r.get("engine") or ""
    return out


def numbered(pages: dict) -> dict[int, dict[int, str]]:
    """The sidecar's string keys as the row numbers they are."""
    out: dict[int, dict[int, str]] = {}
    for page, rows in (pages or {}).items():
        try:
            out[int(page)] = {int(n): t for n, t in (rows or {}).items()}
        except (TypeError, ValueError):
            continue
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sidecar", type=Path, required=True)
    ap.add_argument("--records", type=Path,
                    default=ROOT / "data" / "transcriptions")
    ap.add_argument("--bands", type=Path, default=None,
                    help="the `export_bands.py` directory the sidecar was read "
                         "from; a row the engine now reads differently is "
                         "refused rather than given somebody else's name")
    ap.add_argument("--write", action="store_true",
                    help="save the records; without it nothing is written and "
                         "the count is what would land")
    a = ap.parse_args(argv)

    d = json.loads(a.sidecar.read_text(encoding="utf-8"))
    model, said = d.get("model") or "", d.get("read") or {}
    if d.get("by") != "row":
        # a sidecar keyed by a band's position needs its map to say which row
        # each band became, and pairing blindly hands a name somebody else's ink
        print(f"{a.sidecar} is not keyed by row; refusing to pair it")
        return 2

    exported = exported_readings(a.bands) if a.bands else {}
    total = docs = missing = 0
    for doc, pages in said.items():
        f = a.records / f"{doc}.json"
        if not f.exists():
            missing += 1
            continue
        record = json.loads(f.read_text(encoding="utf-8"))
        got, n = with_second_readings(record, numbered(pages), model,
                                      was=exported.get(doc))
        if not n:
            continue
        docs += 1
        total += n
        print(f"  {doc[:8]}: {n} rows")
        if a.write:
            f.write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
    verb = "written" if a.write else "would be written"
    print(f"{total} rows {verb} across {docs} documents, read by {model}"
          + (f"; {missing} documents in the sidecar are not in {a.records}"
             if missing else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
