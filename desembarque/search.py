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

MIN_QUERY = 3
MIN_SCORE = 0.10


def fold(s: str) -> str:
    """Upper case, no diacritics — how two spellings of a name are compared."""
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


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


def load_index(cache: Path, engine_only: bool = True) -> list[dict]:
    """Flatten the transcription cache into rows that can be searched.

    Manually typed rows are excluded by default when measuring, because they
    are perfect by construction and would flatter the engine; the application
    passes engine_only=False, since a person's own typing is exactly what they
    most want to find again.
    """
    out: list[dict] = []
    for f in sorted(Path(cache).glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if engine_only and not d.get("engine"):
            continue
        for r in d.get("rows", []):
            text = row_text(r)
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
