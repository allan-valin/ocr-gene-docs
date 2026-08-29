"""The words a passenger list prints in the columns beside the name.

The name column has no closed vocabulary: whose names exist is the question the
archive is being read to answer, and `gazetteer.py` says at length why a name is
only ever a suggestion. Nationality, civil state and profession are the
opposite. A list prints the same forty words down a page — *ESPANHOLA*,
*BRASILEIRO*, *SOLT*, *CASADO*, *COMERCIO*, *LAVRADOR* — and the recogniser's
`SEAGNOLA`, `LASIERCL` and `conercio` are each one fuzzy match away from what
the clerk typed.

That does not make a snapped word a reading. The same two rules the gazetteer
runs on hold here:

* the reading is kept beside the snapped value and never replaced by it, so a
  person can always see what the page was read as;
* the list is what these printed forms use, not what this archive has been read
  to contain — a word here is a claim about the form, never about a passenger.
"""
from __future__ import annotations

import difflib
import json
import unicodedata
from pathlib import Path

# How close a reading has to be before it is snapped. Half the cells on these
# pages are blank and the rest are faint, so a column of forty words is not a
# licence to put one of them on every row.
FLOOR = 0.62


def fold(text) -> str:
    s = unicodedata.normalize("NFKD", str(text if text is not None else ""))
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


class Vocabulary:
    """The closed lists, by the field names the app already uses."""

    def __init__(self, words: dict[str, list[str]] | None = None,
                 floors: dict[str, float] | None = None):
        self.words = {f: list(ws) for f, ws in (words or {}).items()}
        # Per column, because they fail differently. Civil state and profession
        # are short lists of words that look like nothing else; nationality is
        # fifty long words sharing their endings, where `BIG` is as near INGLEZ
        # as it is to BELGICA. Measured in `scripts/bench_columns.py --floor`.
        self.floors = {f: float(v) for f, v in (floors or {}).items()}
        # the folded form is what is compared; the stored word keeps its accents
        self._folded = {f: [(fold(w), w) for w in ws]
                        for f, ws in self.words.items()}

    @classmethod
    def load(cls, path: Path | str) -> "Vocabulary":
        try:
            d = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls({})
        return cls(d.get("columns") or {}, d.get("floors") or {})

    def _similar(self, reading: str, folded: str) -> float:
        """How near a reading is to a word, allowing for the ends being lost.

        The clerks abbreviate — *SOLT* for solteiro, *CAS* for casado — and the
        recogniser drops the faint end of a word as often as it misreads the
        middle: `cau` for CASADO, `SOLT` for SOLT, `OENOSAI` for BUENOS AIRES.
        Against the whole word `cau` scores 0.44 and is thrown away; against
        the word's first three letters it scores 0.67 and is the right answer.
        So a reading of three letters or more is also compared with the head of
        the word, and the better of the two comparisons is the score.
        """
        whole = difflib.SequenceMatcher(None, reading, folded).ratio()
        if len(reading) < 3 or len(reading) >= len(folded):
            return whole
        head = difflib.SequenceMatcher(None, reading, folded[:len(reading)]).ratio()
        return max(whole, head)

    def snap(self, field: str, reading) -> dict | None:
        """The word this reading is nearest, or None when it is near nothing."""
        t = fold(reading)
        if not t:
            return None
        best, score = None, 0.0
        for folded, word in self._folded.get(field, ()):
            s = self._similar(t, folded)
            if s > score:
                best, score = word, s
        if best is None or score < self.floors.get(field, FLOOR):
            return None
        return {"value": best, "score": round(score, 3)}

    def snapped(self, cell: dict, field: str) -> dict:
        """The cell with the snapped word added beside what was read.

        `text` is what the recogniser said and is never touched. `value` is the
        word it was snapped to and `snap` how close it was, both absent when
        the reading is near nothing on the list.
        """
        out = dict(cell)
        got = self.snap(field, cell.get("text"))
        if got:
            out["value"] = got["value"]
            out["snap"] = got["score"]
        return out
