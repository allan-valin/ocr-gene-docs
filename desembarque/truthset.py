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
    by_n = {r.get("n"): r for r in rows if r.get("page") == truth.get("page")}
    # Two shapes, because pages come in two kinds. A page read straight down
    # gives `names` and the row its first one sits on; a page where somebody
    # was sure of eleven rows out of forty-one gives `rows`, keyed by row
    # number, and is scored on those.
    if truth.get("rows"):
        wanted = [(int(n), name) for n, name in truth["rows"].items()]
    else:
        wanted = [(int(truth.get("first_row", 1)) + k, name)
                  for k, name in enumerate(truth.get("names") or [])]
    out = []
    for n, name in sorted(wanted):
        row = by_n.get(n)
        if row is None or not (row.get("name_raw") or "").strip():
            continue
        out.append({"truth": name, "read": row["name_raw"], "row": row})
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
