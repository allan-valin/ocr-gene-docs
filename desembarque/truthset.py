"""The hand-read pages, paired with what the engine stored for them.

`data/truth` holds five pages somebody read off the scan by eye. Everything
this repository claims about reading quality is scored against them, and the
pairing is the part that decides whether a number means anything: a page the
engine cut into fewer bands has rows missing in the middle, and pairing by
position would compare every later name with somebody else's.

Kept here rather than in one bench script because two of them need it — the
menu bench and the check bench — and a second copy of this would eventually
disagree with the first.
"""
from __future__ import annotations

import difflib
import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


def pairs(truth: dict, rows: list[dict]) -> list[dict]:
    """Each hand-read name beside the row the engine stored for it.

    Paired by row number, not by order: a page whose bands the engine cut
    differently has rows missing in the middle, and pairing by position would
    then compare every later name with somebody else's.
    """
    on_page = sorted((r for r in rows if r.get("page") == truth.get("page")),
                     key=lambda r: r.get("n") or 0)
    by_n = {r.get("n"): r for r in on_page}
    # Two shapes, because pages come in two kinds. A page where somebody was
    # sure of eleven rows out of forty-one gives `rows`, keyed by the row
    # numbers they wrote against, and those are taken as they stand. A page
    # read straight down gives `names`, a run, and the run is aligned to the
    # readings rather than counted from `first_row`: that number goes stale
    # when a page is cut differently, and a run counted from anywhere drifts
    # past the first row that carries no reading. See `aligned`.
    if truth.get("rows"):
        wanted = [(int(n), name) for n, name in truth["rows"].items()]
    else:
        placed = aligned([r.get("name_raw") or "" for r in on_page],
                         [n for n in (truth.get("names") or []) if n])
        wanted = [(on_page[i].get("n"), name) for i, name in placed.items()]
    out = []
    for n, name in sorted(wanted):
        row = by_n.get(n)
        if row is None or not (row.get("name_raw") or "").strip():
            continue
        # the page a pair came from travels with it: a bench that wants
        # anything else about the row — its nationality, for the language
        # prior — has to be able to find the row again
        out.append({"truth": name, "read": row["name_raw"], "row": row,
                    "pdf": truth.get("pdf"), "page": truth.get("page")})
    return out


def aligned(readings: list[str], names: list[str]) -> dict[int, str]:
    """Which reading each hand-read name belongs to, allowing skipped rows.

    A run of names read straight down a page has to be put against the rows the
    page was cut into, and two things go wrong at once. The stored `first_row`
    goes stale — `data/truth/BS_ENT_014541-p2.json` says 4 because the comb
    that read it in July counted the header bands, and measured from the
    printing those passengers are rows one to six — so a stored offset labels
    every row with the name three above it. And a page whose middle rows carry
    no reading has gaps, so a single best-fit offset drifts past the first gap
    and labels everything after it with the name above.

    So the two lists are aligned the way two sequences are: monotonically, name
    by name, paying for the mismatch and allowed to skip a row that nobody
    wrote a name against. Skipping a row is free, since a page is mostly rows
    the truth says nothing about; skipping a *name* costs a whole name, since
    every name in the run is on the page somewhere.
    """
    if not readings or not names:
        return {}
    R, N = len(readings), len(names)
    folded = [fold(r) for r in readings]
    want = [fold(n) for n in names]

    def cost(i: int, j: int) -> float:
        if not folded[i]:
            return 1.0
        return 1.0 - difflib.SequenceMatcher(None, folded[i], want[j]).ratio()

    # best[i][j]: the cheapest way to place the first j names among the first
    # i rows. A name costs 1.0 unplaced, which is dearer than any mismatch.
    big = float(N + R + 1)
    best = [[big] * (N + 1) for _ in range(R + 1)]
    back = [[None] * (N + 1) for _ in range(R + 1)]
    for i in range(R + 1):
        best[i][0] = 0.0
    for i in range(1, R + 1):
        for j in range(1, N + 1):
            skip_row = best[i - 1][j]
            take = best[i - 1][j - 1] + cost(i - 1, j - 1)
            drop_name = best[i][j - 1] + 1.0
            best[i][j] = min(skip_row, take, drop_name)
            back[i][j] = ("row" if best[i][j] == skip_row else
                          "take" if best[i][j] == take else "name")

    out: dict[int, str] = {}
    i, j = R, N
    while i > 0 and j > 0:
        step = back[i][j]
        if step == "row":
            i -= 1
        elif step == "take":
            out[i - 1] = names[j - 1]
            i -= 1
            j -= 1
        else:
            j -= 1
    return out


def word_pairs(truth: str, read: str) -> list[dict]:
    """The words of a truth name beside the words of the reading.

    Position when the counts agree, which is the ordinary case. When they do
    not — a word the recogniser merged or split — each truth word is matched
    to the reading word that resembles it most, so a merged reading is
    measured against both names it swallowed rather than dropped.
    """
    t = [fold(w) for w in (truth or "").split()]
    r = [fold(w) for w in (read or "").split()]
    if not t or not r:
        return []
    if len(t) == len(r):
        return [{"truth": a, "read": b, "i": i} for i, (a, b) in enumerate(zip(t, r))]
    out = []
    for a in t:
        i = max(range(len(r)),
                key=lambda j: difflib.SequenceMatcher(None, a, r[j]).ratio())
        out.append({"truth": a, "read": r[i], "i": i})
    return out


def rank_of(target: str, candidates: list[str]) -> int | None:
    """Where the true name sits in a menu, counting from one; None if absent."""
    want = fold(target)
    for k, c in enumerate(candidates, start=1):
        if fold(c) == want:
            return k
    return None


def rows_from_disk() -> tuple[list[dict], dict]:
    """Every hand-read row, beside the row the engine stored for it."""
    records = {}
    for f in sorted((ROOT / "data" / "transcriptions").glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if d.get("file"):
            records[d["file"]] = d

    out, seen = [], {"pages": 0, "truth_rows": 0, "paired_rows": 0, "unpaired": []}
    for f in sorted((ROOT / "data" / "truth").glob("*.json")):
        t = json.loads(f.read_text(encoding="utf-8"))
        wanted = len(t.get("names") or t.get("rows") or ())
        if not wanted:
            continue
        seen["pages"] += 1
        seen["truth_rows"] += wanted
        rec = records.get(t.get("pdf"))
        got = pairs(t, rec.get("rows") or []) if rec else []
        seen["paired_rows"] += len(got)
        if len(got) < wanted:
            seen["unpaired"].append({"page": f.name, "missing": wanted - len(got)})
        out += got
    return out, seen


def words_from_disk() -> tuple[list[dict], dict]:
    """The same, word by word: what the page says beside what was read."""
    rows, seen = rows_from_disk()
    cases = []
    for p in rows:
        for w in word_pairs(p["truth"], p["read"]):
            cases.append({**w, "row": p["row"]})
    return cases, seen
