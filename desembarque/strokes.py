"""What else the ink could say: candidates built from strokes, not spellings.

A recogniser prints one reading of a word and prints it with confidence. In
these hands that confidence is misplaced in a particular way: a run of
**minims** — the plain vertical strokes that make `i`, `u`, `n`, `m`, `r`, `w`
— carries a reliable number of strokes and an unreliable division into
letters. `ri` and `ni` are three strokes either way, and the recogniser has to
choose. What it chose is then treated downstream as what the page says.

So the candidates offered to a person are generated from the ink: re-cut the
minim runs every way the stroke count allows, read a tall stroke the other way
(`f`/`J`/`Y`/`T`), read a round letter as its neighbour, expand the marks the
clerks used as abbreviations, and — where a source of names supports it — put
back a stroke lost at an edge or a space that was never read.

A candidate that spells nothing anybody has read before is still offered. The
archive has not read every name correctly yet, which is the whole problem;
names known to it are ranked first, but they are never the gate.

Nothing here rewrites a reading. It only says what else the same ink supports.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

# How many strokes each minim letter is worth. `r` is two — the stem and the
# shoulder — which is why `ri` and `ni` are the same ink and `Mania` is `Maria`.
MINIMS = {"I": 1, "U": 2, "N": 2, "R": 2, "M": 3, "W": 3}

# One stroke and a direction: which way the tall part goes, and whether it goes
# above the line or below it.
ASCENDERS = [{"B", "D", "F", "H", "K", "L", "T", "J", "Y", "P"},
             {"G", "J", "Y", "Q", "Z", "P", "F"}]

# The round hands: an open `c` closes into an `e`, an `o` or an `a`; the long
# `s` is a stem and reads as an `r` or, before a round letter, as an `m`.
ROUND = [{"C", "E", "O", "A"}, {"S", "R"}, {"S", "D", "G"}, {"S", "M"}]

# The clerks' shorthand, as the recogniser brings it back: the superscript it
# has no glyph for comes through as `?`, `'`, `.` or nothing at all.
ABBREVIATIONS = {
    "ANT": "ANTONIO", "ANTO": "ANTONIO", "FCO": "FRANCISCO", "FRCO": "FRANCISCO",
    "JOA": "JOAO", "JOAO": "JOAO", "MA": "MARIA", "MMA": "MARIA",
    "JOSE": "JOSE", "JOS": "JOSE", "MAN": "MANUEL", "MANL": "MANUEL",
    "DOM": "DOMINGOS", "DOMOS": "DOMINGOS", "FERDO": "FERNANDO",
    "GMO": "GUILHERMO", "JNO": "JOAO", "PDRO": "PEDRO", "VTE": "VICENTE",
}

MARKS = "?'`.,\"º°*:;-_"
LIMIT = 20
MAX_RUN_STROKES = 6          # a longer run explodes and says nothing useful
MIN_LENGTH = 3


@dataclass(frozen=True)
class Candidate:
    word: str
    cost: int
    rule: str


def clean(word: str) -> str:
    return "".join(c for c in (word or "").upper() if c.isalpha())


def stroke_count(word: str) -> int:
    """The strokes a word's minims are worth. Other letters count nothing —
    they are not what the division is uncertain about."""
    return sum(MINIMS.get(c, 0) for c in (word or "").upper())


@lru_cache(maxsize=None)
def _compositions(n: int) -> tuple[str, ...]:
    """Every string of minim letters worth exactly `n` strokes."""
    if n <= 0:
        return ("",)
    out = []
    for letter, cost in MINIMS.items():
        if cost <= n:
            out.extend(letter + rest for rest in _compositions(n - cost))
    return tuple(out)


def _minim_runs(word: str) -> list[tuple[int, int]]:
    runs, start = [], None
    for i, c in enumerate(word):
        if c in MINIMS:
            start = i if start is None else start
        elif start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(word)))
    return runs


def _recuts(word: str) -> list[Candidate]:
    out = []
    for a, b in _minim_runs(word):
        run = word[a:b]
        n = stroke_count(run)
        if n > MAX_RUN_STROKES:
            continue
        for alt in _compositions(n):
            if alt != run:
                out.append(Candidate(word[:a] + alt + word[b:], 1, "minims"))
    return out


def _swaps(word: str, groups: list[set[str]], rule: str) -> list[Candidate]:
    out = []
    for i, c in enumerate(word):
        for g in groups:
            if c in g:
                for other in sorted(g - {c}):
                    out.append(Candidate(word[:i] + other + word[i + 1:], 1, rule))
    return out


def _expansions(word: str) -> list[Candidate]:
    letters = clean(word)
    full = ABBREVIATIONS.get(letters)
    if full and full != word:
        return [Candidate(full, 1, "abbreviation")]
    return []


EDGE_MAX = 3


def _edges(word: str, known: set[str]) -> list[Candidate]:
    """Ink at an edge that is not part of the name.

    Two things look the same from here. A stroke the pen lost — `zabel` for
    *Izabel* — and, far more often on these pages, the next column bleeding
    into the name strip: `SANTONIBRA`, `SANTOSPOR`, `GUIMARAESBRA` are a
    surname with the first letters of *brasileiro* or *portuguez* stuck to it,
    because the crop is cut on a measured rule and the clerk wrote across it.

    Only spoken for when a source of names has heard of the result: offering
    every letter of the alphabet at both ends of every word would bury the menu
    in nothing.
    """
    out = []
    for k in range(1, EDGE_MAX + 1):
        for w in (word[k:], word[:-k]):
            if len(w) >= MIN_LENGTH and w in known:
                out.append(Candidate(w, k, "edge"))
    for letter in sorted({k[0] for k in known}):
        for w in (letter + word, word + letter):
            if w in known:
                out.append(Candidate(w, 1, "edge"))
    # A long word with a tail nobody has read is still worth trimming: the
    # names this archive has read correctly are 1,081, and *Santoni*, *Santos*
    # and *Rossendal* are none of them, which is the whole reason the
    # dictionary cannot be the gate. Ranked below anything known, by cost.
    if len(word) >= MIN_LENGTH + 4:
        for k in range(1, EDGE_MAX + 1):
            w = word[:-k]
            if w not in known:
                out.append(Candidate(w, k + 1, "edge"))
    return out


CAPITAL_MAX = 3


def _capitals(word: str, known: set[str]) -> list[Candidate]:
    """A looped capital cut into two or three letters.

    A capital written in one run of the pen — `M`, `N`, `W` in these hands —
    comes back from the recogniser as the letters its loops resemble:
    `ELBARIA`, `EFBARIA`, `CFBARIA` and `ETBARIO` are all *MARIA* with the M
    read as three. The rule is the general one — the first two or three letters
    are one capital — and not a table of what this hand happens to do, so it is
    gated on a name somebody has read before.
    """
    out = []
    for k in range(2, CAPITAL_MAX + 1):
        if len(word) - k < MIN_LENGTH - 1:
            continue
        for letter in sorted({n[0] for n in known}):
            w = letter + word[k:]
            if w in known:
                out.append(Candidate(w, 1, "capital"))
    return out


def _spaces(word: str, known: set[str]) -> list[Candidate]:
    """A space the recogniser never saw: `MorvettoFianciico` is two people's
    worth of name in one token. Split where one side is a name somebody has
    read before, since any split is possible and only some mean anything."""
    out = []
    for i in range(MIN_LENGTH, len(word) - MIN_LENGTH + 1):
        head, tail = word[:i], word[i:]
        if head in known or tail in known:
            out.append(Candidate(f"{head} {tail}", 1, "space"))
            # And each half alone, because a person correcting the row types
            # one name into one cell: the menu has to be able to offer *Jose*
            # on its own, not only `JOSE CLUNES`.
            for half in (head, tail):
                if half in known:
                    out.append(Candidate(half, 1, "space"))
    return out


def variants(word: str, known: set[str] | None = None,
             limit: int = LIMIT, rules: set[str] | None = None) -> list[Candidate]:
    """What else this ink could say, cheapest first, known names first.

    `known` is a source of names — the archive, the origin-language given-name
    lists, a person's own typing. It ranks candidates and it lets the rules
    that would otherwise generate noise (a lost edge stroke, a missing space)
    speak at all. It never decides what the ink supports.
    """
    w = clean(word)
    if len(w) < MIN_LENGTH:
        return []
    known = {k.upper() for k in (known or set())}

    made: list[Candidate] = []
    made += _recuts(w)
    made += _swaps(w, ASCENDERS, "ascender")
    made += _swaps(w, ROUND, "round")
    made += _expansions(word)
    made += _edges(w, known)
    made += _capitals(w, known)
    made += _spaces(w, known)

    # Two changes at once — `fore` is `Jose` with the tall stroke read the
    # other way *and* the long `s` read as an `r` — but only where a name
    # somebody has read comes out of it. Unpruned, two changes is thousands of
    # readings per word and the person stops looking.
    if known:
        seen_once = {c.word for c in made}
        for first in list(made):
            if first.rule in ("edge", "space", "abbreviation"):
                continue
            for second in (_recuts(first.word)
                           + _swaps(first.word, ASCENDERS, "ascender")
                           + _swaps(first.word, ROUND, "round")):
                if second.word in known and second.word not in seen_once:
                    made.append(Candidate(second.word, 2, "two changes"))
                    seen_once.add(second.word)

    best: dict[str, Candidate] = {}
    for c in made:
        if c.word == w:
            continue
        if c.word not in best or c.cost < best[c.word].cost:
            best[c.word] = c
    if rules is not None:
        best = {k: c for k, c in best.items() if c.rule in rules}

    out = sorted(best.values(),
                 key=lambda c: (c.cost, 0 if c.word.replace(" ", "") in known
                                or c.word in known else 1, c.word))
    return out[:limit]
