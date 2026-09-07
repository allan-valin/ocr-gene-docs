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

from desembarque import truthset                    # noqa: E402
from desembarque.gazetteer import Names, fold, spoken_names  # noqa: E402
from desembarque.identity import cached_hash        # noqa: E402
from desembarque.recheck import flagged             # noqa: E402
from desembarque.secondopinion import same_row as _same_row  # noqa: E402
from desembarque.search import load_index, search   # noqa: E402


def known_names() -> dict[str, int]:
    """The names the index may spell a stroke reading as, and how often each
    was read.

    The same two sources the review menu ranks by, and for the same reason:
    the archive has read these names, or these languages carry them. A stroke
    reading that spells neither is not indexed. The counts decide which names
    are too common to be worth guessing into — see `search.COMMON_NAME`; a
    name from the language lists has never been read here and is counted once.
    """
    names = Names.load(ROOT / "data" / "names.json")
    spoken = spoken_names(ROOT / "data" / "language_names.json")
    out = {fold(n): int(c) for n, c in names.counts.items()}
    for n in spoken:
        out.setdefault(fold(n), 1)
    return out


def exported_readings(bands: Path) -> dict[tuple, str]:
    """What the engine said about each row on the day the crops were cut."""
    index = json.loads((bands / "bands.json").read_text(encoding="utf-8"))
    out = {}
    for key, got in index.items():
        doc, _, page = key.partition("/")
        for r in got or ():
            out[(doc, int(page), r["n"])] = r.get("engine") or ""
    return out


# The same question the write asks, and one place asks it: whether an exported
# reading and a stored row are the same ink. `desembarque.secondopinion`.
same_row = _same_row


def add_second_opinion(rows, path: Path, as_guess: bool = False,
                       bands: Path | None = None,
                       only: set[tuple] | None = None) -> str:
    """Put a second recogniser's reading of a row beside the engine's own.

    A reading, not a guess: another recogniser read it off the same crop, so it
    goes where the engine's own second reading goes and is scored the same way.
    Two shapes of sidecar reach this. `spike_second_opinion.py` cuts its own
    rows off the page, so its readings are keyed by a band's position and it
    carries a `map` saying which stored row each band became. `read_bands.py`
    reads the crops the engine itself exported, which are named by the row
    number the engine gave them, so its keys *are* row numbers and the map is
    the identity — pairing is engine against engine and needs no alignment at
    all, which is why its coverage is 82% against the other's 28%.

    `only`, when given, is the `(doc, page, row)` of the rows worth the second
    reading — `desembarque.recheck.flagged` over the same corpus. The second
    recogniser is about two seconds a row, so the whole corpus is days of it
    and the flagged rows are hours; this measures what the shorter run is
    worth before anybody spends the longer one.
    """
    d = json.loads(path.read_text(encoding="utf-8"))
    said, mapped = d.get("read") or {}, d.get("map") or {}
    # What the engine said when the crops were cut, if it is on hand. The
    # sidecar's row numbers are that reading's; the index's are from whenever
    # the dossier was last read, and on the subcorpus those agree on 100% of
    # the hand-read pages and 58% of the rest, because the engine has moved on
    # and the corpus has not. Pasting a reading onto a row that no longer holds
    # the same name is how a second opinion lands on a stranger, so a row whose
    # two readings disagree is refused rather than paired.
    exported = exported_readings(bands) if bands else {}
    used = missing = stale = skipped = 0
    at_row: dict[tuple, dict] = {}
    for r in rows:
        at_row[(r.get("doc"), r.get("page"), r.get("row"))] = r
    for doc, pages_of in (mapped or said).items():
        for page, bands in pages_of.items():
            for band, value in bands.items():
                row_n = value if mapped else int(band)
                if only is not None and (doc, int(page), row_n) not in only:
                    skipped += 1
                    continue
                r = at_row.get((doc, int(page), row_n))
                text = ((said.get(doc, {}).get(page, {}) or {}).get(band) or "").strip()
                if r is None or not text or text == r.get("text"):
                    missing += 1
                    continue
                was = exported.get((doc, int(page), row_n))
                if was is not None and not same_row(was, r.get("text") or ""):
                    stale += 1
                    continue
                r["alts"] = list(r.get("alts") or ())
                if as_guess:
                    # counted with the guesses, so it is weighted below every
                    # reading and kept out of the pass that runs when a
                    # crossing was named
                    r["alts"].append(text)
                    r["guessed"] = int(r.get("guessed") or 0) + 1
                else:
                    at = len(r["alts"]) - int(r.get("guessed") or 0)
                    r["alts"].insert(at, text)
                used += 1
    return (f"second opinion: {used} rows read twice, {missing} unpaired"
            + (f", {stale} refused as read from a stale row" if stale else "")
            + (f", {skipped} passed over as not worth a second look" if skipped
               else ""))


def flagged_rows(cache: Path) -> set[tuple]:
    """Every `(doc, page, row)` the review screen would mark for a second look.

    What the offline batch would hand a second recogniser if it paid for the
    flagged rows rather than for the corpus. Read off the stored records, which
    is where the batch stands when it has to decide — before an index exists.
    """
    names = Names.load(ROOT / "data" / "names.json")
    out: set[tuple] = set()
    for f in sorted(cache.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        doc = d.get("hash") or f.stem
        for page, row in flagged(d, names):
            out.add((doc, page, row))
    return out


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
        # the truth block sits somewhere among the page's rows; the pairing is
        # `desembarque.truthset`'s, which the menu bench and the training set
        # also use -- a single best-fit offset drifts past the first row that
        # carries no reading and scores every later name against somebody
        # else's row
        for pair in truthset.pairs(t, rows):
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
            out.append({"name": pair["truth"], "doc": doc,
                        "page": t["page"], "row": pair["row"].get("n"),
                        "read": pair["row"].get("name_raw") or "",
                        "voyage": extra, "pdf": t["pdf"]})
    return out


def rank_of(rows, w: dict, query: str, limit: int) -> int | None:
    hits = search(rows, query, limit=limit)
    return next((i + 1 for i, h in enumerate(hits)
                 if h.get("doc") == w["doc"] and h.get("page") == w["page"]
                 and h.get("row") == w["row"]), None)


def matrix(args) -> int:
    """The two questions a searcher asks, at three cutoffs, on one index.

    A scoring change moves these six numbers in different directions — the
    forgiveness that found seven more names typed alone cost ten when the
    crossing was named — and running the bench six times over paid the cold
    load six times to find that out.
    """
    ships = catalogue_ships(args.scans)
    rows = load_index(args.cache, engine_only=False, ships=ships or None,
                      known=known_names())
    if getattr(args, "second_opinion", None):
        only = (flagged_rows(args.cache)
                if getattr(args, "second_only_flagged", False) else None)
        if only is not None:
            print(f"{len(only)} rows flagged for a second look in {args.cache}")
        print(add_second_opinion(rows, args.second_opinion,
                                 getattr(args, "second_as_guess", False),
                                 bands=getattr(args, "second_bands", None),
                                 only=only))
        # a different index: the postings and the letter counts were built
        # before these readings existed, and both are cached by version
        rows.version = (rows.version or 0) + 1_000_000
    asked = {
        "by name alone": [(w, w["name"]) for w in
                          truth_rows(args.cache, args.scans, ships=ships)],
        "naming the crossing": [
            (w, f"{w['name']} {w['voyage']}".strip() if w.get("voyage") else w["name"])
            for w in truth_rows(args.cache, args.scans, with_line=True, ships=ships)],
    }
    total = len(next(iter(asked.values())))
    print(f"{total} hand-read names against {len(rows)} indexed rows\n")
    print(f"{'':22}{'top 5':>8}{'top 10':>8}{'top 20':>8}")
    for label, queries in asked.items():
        ranks = [rank_of(rows, w, q, 50) for w, q in queries]
        got = [sum(1 for r in ranks if r and r <= at) for at in (5, 10, 20)]
        print(f"{label:22}" + "".join(f"{n:>8}" for n in got))
    return 0


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
    ap.add_argument("--second-opinion", type=Path, default=None,
                    help="a sidecar of another recogniser's readings, put "
                         "beside the engine's own before searching")
    ap.add_argument("--second-bands", type=Path, default=None,
                    help="the `export_bands.py` directory the sidecar was read "
                         "from; a row whose index reading disagrees with what "
                         "the engine said when the crop was cut is refused "
                         "rather than paired")
    ap.add_argument("--second-as-guess", action="store_true",
                    help="count the second recogniser's readings with the "
                         "guesses: weighted below every reading, and kept out "
                         "of the pass that runs when a crossing was named")
    ap.add_argument("--second-only-flagged", action="store_true",
                    help="read only the rows the review check flags, which is "
                         "what the offline batch would pay for: the second "
                         "recogniser is ~2 s a row and the corpus is days of "
                         "it")
    ap.add_argument("--matrix", action="store_true",
                    help="both questions at three cutoffs, on one load of the "
                         "index — what a scoring change has to be judged by")
    args = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT / "scripts"))

    if args.matrix:
        return matrix(args)
    ships = catalogue_ships(args.scans) if args.catalogue else {}
    rows = load_index(args.cache, engine_only=False, ships=ships or None,
                      known=known_names())
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
