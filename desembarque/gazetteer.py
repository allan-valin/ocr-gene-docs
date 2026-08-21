"""Names this archive is known to carry, offered as guesses and never as readings.

Handwriting recognition is at its ceiling for what runs on this machine — the
input width, a bigger model, removing the printed rules and folding confusable
letters were all measured and none of them moved it. What is left to help a
person reading `Dantalarlraia` is a list of the names these ships actually
carried, so the tool can say *this looks like Santabarbara* while being explicit
that nobody read that off the page.

Two rules hold this in place:

* A suggestion is never a value. It ranks what the engine read and it can be
  offered beside it, labelled; it is stored only when a person picks it, and
  then it is stored as that person's typing.
* The list is built from this archive rather than from a general name
  dictionary — `scripts/build_names.py` counts the pages the clerks typed, which
  the recogniser reads almost perfectly, and the rows people typed by hand.
  These ships carried Italians, Spaniards, Portuguese and Syrians to Santos
  between 1917 and 1925; whose names exist is not a question to answer from
  elsewhere.
"""
from __future__ import annotations

import difflib
import json
import unicodedata
from pathlib import Path

# How close a dictionary name has to be to a reading before it is worth showing.
# Measured against the hand-read pages: below this the list fills with names
# that share three letters and nothing else.
FLOOR = 0.62
# How many to offer for one word. A list somebody has to read is not help.
LIMIT = 4


def fold(text: str) -> str:
    s = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


class Names:
    """The dictionary, with how often each name occurs in the clean pages."""

    def __init__(self, counts: dict[str, int] | None = None):
        self.counts = {fold(k): int(v) for k, v in (counts or {}).items()}

    @classmethod
    def load(cls, path: Path) -> "Names":
        try:
            d = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls({})
        return cls(d.get("names") or {})

    def __len__(self) -> int:
        return len(self.counts)

    def score(self, word: str) -> float:
        """How much of a name this reading already is: 1.0 when it is one."""
        w = fold(word)
        if not w:
            return 0.0
        if w in self.counts:
            return 1.0
        best = self.suggest(w, limit=1)
        return best[0]["score"] if best else 0.0

    def suggest(self, word: str, limit: int = LIMIT,
                floor: float = FLOOR) -> list[dict]:
        """Names close to this reading, best first.

        Ties are broken by how common the name is in the archive, because
        between two names equally close to a mangled word, the one that sailed
        forty times is the better guess than the one that sailed once.
        """
        w = fold(word)
        if len(w) < 3:
            return []
        out = []
        for name, n in self.counts.items():
            if abs(len(name) - len(w)) > 3:
                continue
            r = difflib.SequenceMatcher(None, w, name).ratio()
            if r >= floor:
                out.append({"name": name, "score": round(r, 3), "seen": n})
        out.sort(key=lambda c: (-c["score"], -c["seen"], c["name"]))
        return [c for c in out if c["name"] != w][:limit]

    def rank(self, readings: list[str]) -> list[dict]:
        """The engine's own readings of one word, ordered by how name-like they are.

        This changes nothing about what was read. It puts the reading that is a
        name in this archive above the one that is not, which is the question a
        person is answering when they open that menu.
        """
        scored = [{"word": r, "score": round(self.score(r), 3)} for r in readings if r]
        scored.sort(key=lambda c: -c["score"])
        return scored
