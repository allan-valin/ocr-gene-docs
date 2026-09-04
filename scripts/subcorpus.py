"""The subcorpus a second reading is measured over, chosen the same way twice.

A second opinion has to be measured over a slice of the corpus read twice in
full — targets *and* the rows competing with them — or the measurement says
only that the rows being searched for were read more often (see
`docs/TASKS-reading-quality.md`). Which slice was never written down, so it
was rebuilt by hand and the numbers of two runs were not strictly comparable.

The rule: every dossier that carries a hand-read truth page, because those hold
the rows the bench searches for, then the rest in hash order until there are
`--dossiers` of them. Hash order is arbitrary and stable, which is what is
wanted -- no dossier is chosen for being easy.

    .venv/bin/python scripts/subcorpus.py --out data/subcache
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from desembarque.identity import cached_hash          # noqa: E402


def chosen(records: list[dict], targets: set[str], want: int) -> list[dict]:
    """The dossiers holding a truth page, then the rest in the order given."""
    picked = [r for r in records if r["file"] in targets]
    for r in records:
        if len(picked) >= want:
            break
        if r not in picked:
            picked.append(r)
    return picked[:want]


def read_pages(path: Path) -> tuple[str | None, list[int]]:
    rec = json.loads(path.read_text(encoding="utf-8"))
    pages = sorted({r.get("page") for r in rec.get("rows") or ()
                    if r.get("page")})
    return rec.get("file"), pages


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--truth", type=Path, default=ROOT / "data" / "truth")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--dossiers", type=int, default=15)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    targets = set()
    for tf in sorted(args.truth.glob("*.json")):
        targets.add(json.loads(tf.read_text(encoding="utf-8"))["pdf"])

    records = []
    for rf in sorted(args.cache.glob("*.json")):
        name, pages = read_pages(rf)
        if pages:
            records.append({"path": rf, "file": name, "pages": pages})

    picked = chosen(records, targets, args.dossiers)
    args.out.mkdir(parents=True, exist_ok=True)
    for old in args.out.glob("*.json"):
        old.unlink()
    for r in picked:
        os.symlink(r["path"].resolve(), args.out / r["path"].name)

    pages = sum(len(r["pages"]) for r in picked)
    held = sum(1 for r in picked if r["file"] in targets)
    print(f"{len(picked)} dossiers, {pages} pages, {held} of them hand-read")
    for r in picked:
        print(f"  {r['file']}  {len(r['pages'])} pages")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
