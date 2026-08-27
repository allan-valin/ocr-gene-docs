"""Can somebody find these people by typing their names?

CER measures how wrong a reading is. This measures the only thing the tool is
for: type the name as a person would know it, and see whether the row it belongs
to comes back — and where in the list. A reading can be wrong in every character
and still be findable, and a reading can be nearly right and still be buried
under a thousand rows that resemble it.

    .venv/bin/python scripts/bench_search.py
    .venv/bin/python scripts/bench_search.py --at 5      # rank within the top five

The truth pages are the ones in data/truth. Each name is searched against the
whole index, exactly as the app searches it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque.identity import cached_hash        # noqa: E402
from desembarque.search import load_index, search   # noqa: E402


def catalogue_ships(scans: Path) -> dict[str, str]:
    """The archive's own index: filename -> the ship it filed the dossier under.

    The application passes this to `load_index` and the bench did not, so every
    number this file has printed was measured against a corpus with a ship on a
    third of its rows where the app has one on nearly all of them.
    """
    out: dict[str, str] = {}
    manifest = scans / "manifest.jsonl"
    if not manifest.exists():
        return out
    for line in manifest.open(encoding="utf-8"):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        for f in row.get("files") or []:
            if row.get("ship"):
                out[f] = row["ship"]
    return out


def truth_rows(cache: Path, scans: Path, with_line: bool = False,
               ships: dict[str, str] | None = None) -> list[dict]:
    """Every hand-read name, with the row it should be found on."""
    out = []
    for f in sorted((ROOT / "data" / "truth").glob("*.json")):
        t = json.loads(f.read_text(encoding="utf-8"))
        if not t.get("names"):
            continue
        pdf = scans / t["pdf"]
        if not pdf.exists():
            continue
        doc = cached_hash(pdf)
        record = json.loads((cache / f"{doc}.json").read_text(encoding="utf-8"))
        rows = [r for r in record.get("rows", []) if r.get("page") == t["page"]]
        if not rows:
            continue
        # the truth block sits somewhere among the page's rows; find where by
        # fit, the same way the recogniser bench does
        from bench_rec import align
        texts = [r.get("name_raw") or "" for r in rows]
        off = align(texts, t["names"])
        for i, name in enumerate(t["names"]):
            if off + i < len(rows):
                # what somebody who knows the crossing would add: the ship if
                # the dossier states one, otherwise the year
                voyage = record.get("voyage") or {}
                # a third of the corpus names a ship and two thirds name the
                # line printed on the letterhead, so for most dossiers the line
                # is the only crossing somebody could type
                extra = voyage.get("ship") or ""
                if not extra and ships:
                    # what the archive filed it under, typed and unmangled —
                    # and the name a person searching actually knows
                    extra = ships.get(t["pdf"], "")
                if with_line and not extra:
                    extra = voyage.get("line") or ""
                if not extra and voyage.get("year"):
                    extra = str(voyage["year"])
                out.append({"name": name, "doc": doc, "page": t["page"],
                            "row": rows[off + i].get("n"),
                            "read": rows[off + i].get("name_raw") or "",
                            "voyage": extra, "pdf": t["pdf"]})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--at", type=int, default=10, help="rank counted as found")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--voyage", action="store_true",
                    help="add the dossier's ship or year to each query, the way "
                         "somebody who knows the crossing would")
    ap.add_argument("--catalogue", action="store_true",
                    help="index the ship the archive filed each dossier under, "
                         "and hint with it — what the application does")
    ap.add_argument("--with-line", action="store_true",
                    help="where the dossier names no ship, hint with the "
                         "shipping line on its letterhead instead of the year")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT / "scripts"))

    ships = catalogue_ships(args.scans) if args.catalogue else {}
    rows = load_index(args.cache, engine_only=False, ships=ships or None)
    wanted = truth_rows(args.cache, args.scans, with_line=args.with_line,
                        ships=ships)
    print(f"{len(wanted)} hand-read names against {len(rows)} indexed rows")

    found, ranks, misses = 0, [], []
    per_page: dict[str, list[int]] = {}
    for w in wanted:
        query = w["name"]
        if args.voyage and w.get("voyage"):
            query = f"{query} {w['voyage']}"
        hits = search(rows, query, limit=args.limit)
        rank = next((i + 1 for i, h in enumerate(hits)
                     if h.get("doc") == w["doc"] and h.get("page") == w["page"]
                     and h.get("row") == w["row"]), None)
        hit = bool(rank and rank <= args.at)
        key = f"{w['pdf']}#{w['page']}"
        per_page.setdefault(key, [0, 0])
        per_page[key][1] += 1
        if hit:
            found += 1
            ranks.append(rank)
            per_page[key][0] += 1
        else:
            misses.append({**w, "rank": rank})
    n = len(wanted) or 1
    print(f"found in the top {args.at}: {found}/{len(wanted)} ({found / n:.0%})")
    # Per page, because a typed page is nearly free and a cursive one is the
    # whole difficulty: one average over both hides which way a change moved.
    for key, (ok, total) in sorted(per_page.items()):
        print(f"  {ok:3d}/{total:<3d} {key}")
    if ranks:
        print(f"median rank when found: {sorted(ranks)[len(ranks) // 2]}")
    print("\nnot found:")
    for m in misses[:20]:
        print(f"  {m['name']!r} read as {m['read']!r} — rank {m['rank']}")
    if args.out:
        args.out.write_text(json.dumps(
            {"at": args.at, "found": found, "total": len(wanted),
             "misses": misses}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
