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

from desembarque import strokes

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
        self.path: Path | None = None
        self.stamp = 0

    @classmethod
    def load(cls, path: Path) -> "Names":
        try:
            d = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls({})
        out = cls(d.get("names") or {})
        out.path = Path(path)
        try:
            out.stamp = out.path.stat().st_mtime_ns
        except OSError:
            out.stamp = 0
        return out

    def fresh(self) -> "Names":
        """This dictionary, or a newly built one if the file has changed.

        The list is rebuilt whenever the corpus is re-read — the pages read
        before the table was measured from its printing put professions in the
        name column — and a server that only reads it at startup keeps offering
        the old ones for as long as it is up.
        """
        path = getattr(self, "path", None)
        if path is None:
            return self
        try:
            stamp = path.stat().st_mtime_ns
        except OSError:
            return self
        return self if stamp == getattr(self, "stamp", 0) else Names.load(path)

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

    def doubtful(self, text: str) -> bool:
        """Whether nothing in this reading resembles a name the archive carries.

        For deciding which rows a person should look at first, not for deciding
        anything about the rows themselves. A rare name that sailed once is
        flagged by this and is perfectly correct — which is why the flag says
        *unknown to this archive* rather than *wrong*.
        """
        words = [w for w in fold(text).split() if len(w) >= 3]
        if not words:
            return False
        return all(self.score(w) < 1.0 and not self.suggest(w, limit=1)
                   for w in words)

    def near_miss(self, text: str, spoken: set[str] | None = None) -> bool:
        """Whether some word here is not a name but is one stroke from one.

        `doubtful` asks the opposite question — whether *nothing* in the row
        resembles a name — and that inference runs backwards. A reading the
        archive has never seen is usually a rare name, and rare names are what
        this archive is full of. A reading that is one re-cut minim or one
        re-read ascender away from a name somebody has read ninety times is the
        strongest evidence of a misread the tool has, and it is exactly the
        case the old flag let through: `YOSE` resembles `JOSE`, so the row
        passed.

        Said with the stroke rules rather than with edit distance, because the
        question is what the ink supports and not which words are spelled
        alike.
        """
        known = {fold(n) for n in self.counts} | {fold(n) for n in (spoken or ())}
        for w in fold(text).split():
            if len(w) < 3 or w in known:
                continue
            for c in strokes.variants(w, known=known, limit=strokes.LIMIT):
                if c.cost <= 1 and c.word.replace(" ", "") in known:
                    return True
        return False

    def rank(self, readings: list[str]) -> list[dict]:
        """The engine's own readings of one word, ordered by how name-like they are.

        This changes nothing about what was read. It puts the reading that is a
        name in this archive above the one that is not, which is the question a
        person is answering when they open that menu.
        """
        scored = [{"word": r, "score": round(self.score(r), 3)} for r in readings if r]
        scored.sort(key=lambda c: -c["score"])
        return scored


# What each stroke rule means, said the way the person reading it would say it.
# The menu shows a guess and has to say where the guess came from, or it is
# indistinguishable from a reading.
WHY = {
    "minims": "os mesmos traços, divididos de outro modo",
    "ascender": "haste alta lida ao contrário",
    "round": "letra redonda parecida",
    "capital": "maiúscula de laço lida como duas ou três letras",
    "edge": "traço a mais ou a menos na ponta",
    "space": "duas palavras coladas",
    "abbreviation": "abreviatura do escrivão",
    "two changes": "duas trocas de traço",
}

# Which rules are worth reading first when nothing in the name list backs any
# of them. A minim re-cut changes no strokes at all — it is the same ink,
# divided differently — while reading a tall stroke the other way claims the
# recogniser mistook a direction. So the tail is ordered by how little each
# rule assumes.
RULE_ORDER = {"ascender": 0, "edge": 1, "capital": 1, "round": 2,
              "space": 2, "two changes": 3, "abbreviation": 3, "minims": 4}

MENU_LIMIT = 12
# How many readings backed only by the language list may sit in one menu. They
# are a weaker claim than a name this archive has read, and a menu that is
# mostly them is a general name dictionary wearing the archive's clothes.
SPOKEN_LIMIT = 4
# How many readings that spell nothing anybody has read may sit in one menu.
# They are the point — the archive has not read every name correctly — but a
# person scanning twenty of them stops scanning, so they are the tail and not
# the list.
UNKNOWN_LIMIT = 5


def spoken_names(path: Path) -> set[str]:
    """Names the languages these ships carried are known to use.

    A different claim from `Names`, and kept apart from it on purpose: this
    archive's list is a count of what it has *read*, and a name it has never
    read correctly — Guberti, Alfieri, Ponticelli — cannot be in it. This one
    says only that somebody in Italian, Spanish or Portuguese is called this,
    which is enough for the rules that need a name to speak for and not enough
    to outrank a page.
    """
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    out: set[str] = set()
    for group in (d.get("names") or {}).values():
        out |= {fold(n) for n in group if n}
    return out


def menu_for(word: str, names: "Names", limit: int = MENU_LIMIT,
             spoken: set[str] | None = None) -> list[dict]:
    """Everything worth offering for one word, in the order that was measured.

    Two sources, and they answer different questions. The archive says *this
    reading is close in spelling to a name these ships carried*, which is the
    single best first guess there is — `bench_menu.py` puts its top suggestion
    right for 23% of badly-read words, ahead of anything else at rank one. The
    strokes say *this ink also supports that reading*, which is what finds the
    names the archive has never read correctly, and what takes the menu from 77
    of 217 badly-read words to 83.

    So: the archive's first guess, then the ink's readings that are names
    somebody has read before, then the rest of the archive's, then the ink's
    readings that spell nothing anyone has read yet — because the archive has
    not read every name correctly, and a dictionary can never be the gate on
    what the page could say.
    """
    w = fold(word)
    read_here = {fold(n) for n in names.counts}
    spoken = {fold(n) for n in (spoken or set())}
    known = read_here | spoken
    near = [dict(g, how="arquivo",
                 why="parecido com a leitura, nome deste acervo")
            for g in names.suggest(word, limit=limit)]
    ink = []
    for c in strokes.variants(word, known=known, limit=limit * 3):
        plain = c.word.replace(" ", "")
        from_list = plain not in read_here and plain in spoken
        ink.append({"name": c.word,
                    "how": "traço+lista" if from_list else "traço",
                    "rule": c.rule, "cost": c.cost,
                    "why": (WHY.get(c.rule, "outra leitura do mesmo traço")
                            + ("; nome corrente nas línguas destas listas — "
                               "este acervo ainda não o leu" if from_list else "")),
                    "seen": names.counts.get(c.word, 0),
                    "score": None})
    # Among the ink's readings that are names this archive has read, the one it
    # has read most often goes first: same candidates, and 0.359 of badly-read
    # words answered by rank three against 0.327 in alphabetical order.
    seen_names = sorted((g for g in ink if g["name"].replace(" ", "") in read_here),
                        key=lambda g: (g["cost"], -g["seen"]))
    from_list = [g for g in ink if g["how"] == "traço+lista"][:SPOKEN_LIMIT]
    unknown = sorted((g for g in ink if g["name"].replace(" ", "") not in known
                      and g["how"] != "traço+lista"),
                     key=lambda g: (RULE_ORDER.get(g["rule"], 9), g["cost"],
                                    g["name"]))
    if w in known:
        # The reading is already a name this archive carries. Other divisions of
        # the same strokes exist, but offering five spellings nobody has ever
        # read under a word that is right is noise, and noise is what makes a
        # person stop reading the menu.
        unknown = []

    out: list[dict] = []
    at: dict[str, dict] = {}
    for g in near[:1] + seen_names + near[1:] + from_list + unknown[:UNKNOWN_LIMIT]:
        was = at.get(g["name"])
        if was is not None:
            # Both sources arriving at the same name is the strongest thing
            # this tool can say about a reading, so it is said, in the place
            # the first of them earned.
            if g["how"] == "traço" and was["how"] == "arquivo":
                was["why"] = f"{was['why']}; {g['why']}"
                was["rule"] = g["rule"]
                was["cost"] = g["cost"]
                was["how"] = "arquivo+traço"
            continue
        if g["name"] == w:
            continue
        at[g["name"]] = g
        out.append(g)
        if len(out) >= limit:
            break
    return out
