"""Search every row that has been indexed, forgivingly.

The premise of the product is that the user does not know which dossier holds
their ancestor, so search runs across the whole index rather than the open
document. And the text it searches did not come from a keyboard: it came out
of a cursive hand, through a recogniser that reads "Guudo Camtadore" for GUIDO
CONTADORE. Exact matching would return nothing on almost every real query.

So matching is by character trigram overlap on an accent-folded string, which
survives that kind of damage — the measured behaviour is in docs/PROGRESS.md.
Below a floor the result is dropped entirely: for a corpus that will be used as
evidence, a confident wrong row is worse than an empty list.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

# The row comb is fitted to the written lines, and the printed column heading is
# one of them. Left alone it is indexed as a passenger and scores 1.0 against
# anyone searching for "nome".
COLUMN_HEADINGS = ("NOMES E COGNOMES", "NOME E COGNOME", "NOMES", "COGNOMES",
                   "NOME", "NOMES E SOBRENOMES")
# Stored transcriptions carry a schema number from now on. Records written
# before this have none, and are read as version 1 — the first schema change
# must not silently drop everything already indexed.
SCHEMA = 3
MIN_QUERY = 3
MIN_SCORE = 0.10


def fold(s: str) -> str:
    """Upper case, no diacritics — how two spellings of a name are compared."""
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


def is_heading(text: str) -> bool:
    """The printed caption of the name column, not a person.

    The caption is recognised differently on every page — "Nome e Cognomes",
    "Nomes e Cognome" — so exact matching caught almost none of them. Multi-word
    captions are matched loosely, which is safe because no passenger's name is
    half-way similar to "NOMES E COGNOMES"; the one-word ones stay exact, since
    at four letters a loose match starts catching real names.
    """
    t = fold(" ".join((text or "").split()))
    if not t:
        return False
    if t in COLUMN_HEADINGS:
        return True
    return any(similarity(t, h) >= 0.55 for h in COLUMN_HEADINGS if " " in h)


def trigrams(s: str) -> set[str]:
    p = "  " + fold(s) + " "
    return {p[i:i + 3] for i in range(len(p) - 2)}


def similarity(a: str, b: str) -> float:
    A, B = trigrams(a), trigrams(b)
    if not A or not B:
        return 0.0
    shared = len(A & B)
    return shared / (len(A) + len(B) - shared)


def row_text(row: dict) -> str:
    raw = row.get("name_raw")
    if raw:
        return raw
    return " ".join(x for x in (row.get("given"), row.get("surname")) if x)


# Parsed rows per file, keyed by path, invalidated by mtime and size. At seven
# thousand dossiers the cache on disk is around 100 MB, and re-reading all of it
# on every keystroke would make search unusable exactly where it is needed. This
# holds until the corpus outgrows memory, at which point it wants a database
# rather than a bigger dictionary.
_ROWS: dict[str, tuple[tuple[int, int], list[dict]]] = {}


def _rows_of(f: Path, engine_only: bool) -> list[dict]:
    try:
        st = f.stat()
    except OSError:
        return []
    stamp = (st.st_mtime_ns, st.st_size)
    key = f"{f}|{int(engine_only)}"
    hit = _ROWS.get(key)
    if hit is not None and hit[0] == stamp:
        return hit[1]
    rows = _parse(f, engine_only)
    _ROWS[key] = (stamp, rows)
    return rows


def load_index(cache: Path, engine_only: bool = True) -> list[dict]:
    """Flatten the transcription cache into rows that can be searched.

    Manually typed rows are excluded by default when measuring, because they
    are perfect by construction and would flatter the engine; the application
    passes engine_only=False, since a person's own typing is exactly what they
    most want to find again.

    Files already read are not read again unless they changed, so an index that
    grows all afternoon does not re-cost the whole afternoon on every query.
    """
    out: list[dict] = []
    present = set()
    for f in sorted(Path(cache).glob("*.json")):
        present.add(f"{f}|{int(engine_only)}")
        out.extend(_rows_of(f, engine_only))
    for gone in [k for k in _ROWS if k.endswith(f"|{int(engine_only)}")
                 and k not in present]:
        del _ROWS[gone]        # a deleted transcription leaves the index
    return out


def _parse(f: Path, engine_only: bool) -> list[dict]:
    """One stored transcription, flattened into searchable rows."""
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if int(d.get("schema", 1)) > SCHEMA:
        return []             # written by a newer version than this one reads
    if engine_only and not d.get("engine"):
        return []
    out = []
    for r in d.get("rows", []):
        text = row_text(r)
        # the flag covers documents indexed since headings were noticed; the
        # text check covers everything indexed before that
        if r.get("header") or is_heading(text):
            continue
        if len(fold(text)) < 4:
            continue
        out.append({
            "doc": d.get("hash", f.stem),
            "notation": d.get("notation"),
            "file": d.get("file"),
            "page": r.get("page"),
            "row": r.get("n"),
            "text": text,
            "conf": (r.get("conf") or {}).get("surname"),
        })
    return out


def search(rows: list[dict], query: str, limit: int = 50,
           min_score: float = MIN_SCORE) -> list[dict]:
    """Ranked matches, best first. An unrecognisable query returns nothing."""
    if len(fold(query)) < MIN_QUERY:
        return []
    scored = []
    for r in rows:
        s = similarity(query, r["text"])
        if s >= min_score:
            scored.append({**r, "score": round(s, 3)})
    scored.sort(key=lambda h: (-h["score"], h.get("file") or "", h["row"] or 0))
    return scored[:limit]
