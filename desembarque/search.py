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

import difflib
import json
from array import array
import re
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
SCHEMA = 18
MIN_QUERY = 3
MIN_SCORE = 0.10

# What the voyage is worth as a proportion of the name match it applies to. It
# breaks the tie a recogniser cannot; it does not overrule the name.
#
# Measured against the hand-read pages, searching each name with the crossing
# named the way somebody who knows it would: findable names go from 96 of 142 at
# 0.25 to 109 at 0.6. Higher is better on that measure and wrong twice over. At
# 0.7 a weak name on the named ship outranks a good name elsewhere — `CONGE
# NGLONE A` above `Guudo Casrtadore`, the failure this repository hit in July,
# guarded by a test. And a reward past 1.0 would, if the penalty matched it, take
# a contradicted row's score to zero: the person would disappear because the
# searcher misremembered a date, which is the failure the tool exists to prevent.
#
# So the reward for agreeing is large, the penalty for contradicting is small,
# and neither can remove a row from the results.
VOYAGE_BONUS = 0.6
VOYAGE_PENALTY = 0.15
# A ship's name is one token, and trigrams are harsh on single tokens: changing
# the last letter of `Valdivia` to `Valdivin` — exactly what the recogniser does
# to it — costs a third of the trigram score. Edit distance is the right measure
# for one word, and it is the same one the month names use.
#
# How close is close enough was set by taste at 0.75 and by measurement at 0.85:
# with the crossing named, findable names are 88 of 142 at a floor of 0.6, 109 at
# 0.75 and 112 at 0.85. A forgiving floor does not find more ships, it finds the
# wrong ones and lifts everybody aboard them. Above 0.9 a genuinely mangled name
# stops matching, and a test says so.
SHIP_FLOOR = 0.85
# Above this a name match is an answer; below it, it is a suggestion. Swept
# against the hand-read pages and flat: 0.35 and 0.5 both find 112 of 142, 0.65
# finds 111. The same is true of MIN_SCORE at 0.05, 0.10 and 0.15 — all 95. Both
# are recorded as measured rather than left to be re-tuned by taste.
STRONG_NAME = 0.5
# How close a reading has to be letter by letter, inside a crossing the searcher
# named, before it is offered. Trigrams survive a letter dropped or doubled and
# collapse when the recogniser substitutes systematically — `EMILI MUESSO` read
# as `bmike Meesoo` shares no trigram with what a person types and stands at
# 0.58 by edit distance. The floor is set where the hand-read pages put it, and
# it is high because the pool is small: every row of the named crossing is
# compared, and most of them are somebody else.
#
# Swept against the hand-read pages, with the crossing named the way somebody
# who knows it would: 86 findable at 0.45, 112 at 0.5, **122 at 0.55**, 121 at
# 0.6 and 0.65, 119 at 0.7 — which is where the pass stops finding anything the
# trigrams did not. The collapse below 0.5 is the point: a forgiving floor does
# not find more people, it fills the top ten with other people's names.
EDIT_FLOOR = 0.55
#
# Running the same comparison over the *whole* corpus, as a second attempt when
# the trigrams found nothing, was measured and dropped. In isolation it looks
# strong — 29 of the 52 hand-read names the trigrams miss come back in the top
# ten of its own list, from a median pool of 53 rows out of 30,000. Merged with
# the trigram hits it is worth nothing: 91 findable of 142 against 90 at a floor
# of 0.65, and 66 at 0.55, because an edit score and a trigram score are not the
# same measure and the rows it pulls displace the ones that were already right.
# The crossing is what makes this pass work, by cutting the pool before it runs
# rather than by scoring harder afterwards.
RE_YEAR = re.compile(r"\b(1[6-9]\d{2}|20[0-2]\d)\b")
# The year a person knows is usually a decade, not a date: "he came out some
# time after the war". Two years with anything or nothing between them are read
# as the span they obviously are.
RE_RANGE = re.compile(
    r"\b(1[6-9]\d{2}|20[0-2]\d)\s*(?:-|–|—|/|a|to|até|ate|until)?\s*"
    r"(1[6-9]\d{2}|20[0-2]\d)\b")
# A shipping line is a printed phrase, not a hand-written word, so it is matched
# token by token — each token as forgivingly as a ship's name, because the
# letterhead came through the same recogniser.
LINE_FLOOR = 0.85
# One word is only a line when it is too long to be somebody's surname. `Lloyd`
# and `Nelson` are shipping lines and they are also people, and a person is what
# a searcher usually means.
LINE_SOLO = 7
# How much of a line has to be named before "everyone who sailed with it" is the
# question being asked rather than a name search that mentions it.
LINE_COVERAGE = 0.5
LINE_TERMS = 5


def fold(s: str) -> str:
    """Upper case, no diacritics — how two spellings of a name are compared."""
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


# What these sheets print around the names. Deliberately narrower than the list
# the voyage parser uses: that one refuses port names and nationalities, and
# `Santos` is on the letterhead of half this corpus *and* one of the commonest
# surnames in Brazil. Dropping it here would lose real people.
PRINTED_WORDS = """consignado consignada tripulacao toneladas registro
    passageiros passageiro observacoes profissao nacionalidade procedencia
    cognomes sobrenomes commando comando desembarcaram entrados immigrantes
    imigrantes reparticao policia intendencia povoamento ministerio
    documentos numero ordem estado civil destino classe pessoas
    total transporte transito tranzito""".split()
PRINTED_FLOOR = 0.8


def _is_printed_word(word: str) -> bool:
    return max(difflib.SequenceMatcher(None, word, w).ratio()
               for w in PRINTED_WORDS) >= PRINTED_FLOOR


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
    if any(similarity(t, h) >= 0.55 for h in COLUMN_HEADINGS if " " in h):
        return True
    # The rest of the printing gets caught by the row comb too. A live search
    # for `Contadore` returned `consigr` and `consign` — the word `consignado`
    # broken in two and filed as two people, scoring against anything beginning
    # `con` and belonging to no ship. A row made only of the form's own words is
    # the form, not a passenger.
    # The detector runs words into their punctuation and into each other —
    # `registro,`, `com/8pessoas` — and a comma was enough to make a line of the
    # form's own prose look like a name.
    # Digits carry no evidence about a name — the line number has its own
    # column, and `Total34` is the tally with the count run into the word — so
    # they are removed before the words are weighed. What is left has to be a
    # word to count at all.
    words = [re.sub(r"\d+", "", w)
             for w in re.sub(r"[^\w\s]+", " ", t.lower()).split()]
    words = [w for w in words if len(w) > 3]
    if not words:
        return False
    if len(words) == 1:
        # One word has to be the printed word exactly. Measured against real
        # surnames from this corpus, a loose match at any usable threshold also
        # drops `gomes` (against `cognomes`) and `romano` (against `comando`),
        # and losing a passenger is the failure this whole tool exists to
        # prevent. So `consigr` — `consignado` broken in two by the row comb —
        # stays in the index, and telling it from a name wants the geometry
        # that knows it sits above the table, not a string distance.
        return words[0] in PRINTED_WORDS
    return all(_is_printed_word(w) for w in words)


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
    """What this row is searched by.

    Normally the verbatim reading, because the split into surname and given
    name is a derivation and the reading is not. The exception is the
    repetition mark: `" Maria` is what the page says and *Martinez Maria* is
    who the row is about, and a search for the surname has to find her — she is
    one of seven Martinezes on that page written with a mark.
    """
    if row.get("ditto"):
        joined = " ".join(x for x in (row.get("surname"), row.get("given")) if x)
        if joined:
            return joined
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
# Bumped whenever a stored transcription is read or drops out of the cache, so
# the posting list can be kept across requests and rebuilt only when the corpus
# it describes has actually changed.
_VERSION = 0
_POSTINGS: tuple[tuple[int, int], dict] | None = None
# The words of the shipping lines, and what each word typed was worth against
# them. Both are answers about the corpus rather than about a query, so they
# outlive the request and are thrown away when the corpus changes.
_VOCAB: tuple[tuple[int, int], dict[str, set[str]]] | None = None
_TERMS: dict[tuple[int, str], dict[str, float]] = {}
_CROSSINGS: tuple[tuple[int, int], dict[str, dict]] | None = None


def _rows_of(f: Path, engine_only: bool,
             ships: dict[str, str] | None = None, token: int = 0) -> list[dict]:
    try:
        st = f.stat()
    except OSError:
        return []
    # the catalogue is part of what a row says it is, so a different catalogue
    # is a different reading and must not come out of the cache. The token is
    # computed once per load rather than once per file.
    stamp = (st.st_mtime_ns, st.st_size, token)
    key = f"{f}|{int(engine_only)}"
    hit = _ROWS.get(key)
    if hit is not None and hit[0] == stamp:
        return hit[1]
    global _VERSION
    rows = _parse(f, engine_only, ships)
    _ROWS[key] = (stamp, rows)
    _VERSION += 1
    return rows


def load_index(cache: Path, engine_only: bool = True,
               ships: dict[str, str] | None = None) -> list[dict]:
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
    token = hash(frozenset((ships or {}).items()))
    for f in sorted(Path(cache).glob("*.json")):
        present.add(f"{f}|{int(engine_only)}")
        out.extend(_rows_of(f, engine_only, ships, token))
    global _VERSION
    for gone in [k for k in _ROWS if k.endswith(f"|{int(engine_only)}")
                 and k not in present]:
        del _ROWS[gone]        # a deleted transcription leaves the index
        _VERSION += 1
    return RowIndex(out, version=_VERSION)


def _second_reading(row: dict, text: str) -> list[str]:
    """The other reading of this row, as whole names rather than loose words.

    Every row is read twice — the band trimmed to the ink, and again with room
    around it — and the two disagree exactly where the hand is hard: `Waria` and
    `Maria` are one word on one page. The loser was kept for the person
    correcting the row and was never searched, so a row the engine had already
    read correctly on the second attempt stayed unfindable.
    """
    alts = row.get("name_alts")
    if not alts:
        return []
    words = text.split()
    if len(alts) != len(words):
        return []
    swapped = " ".join(a[0] if a else w for w, a in zip(words, alts))
    return [swapped] if swapped and swapped != text else []


def _resolved(rows: list[dict]) -> list[dict]:
    """The rows with repetition marks resolved, page by page."""
    from .ditto import resolve
    out, page, block = [], None, []
    for r in rows:
        if r.get("page") != page and block:
            out.extend(resolve(block))
            block = []
        page = r.get("page")
        block.append(r)
    out.extend(resolve(block))
    return out


def _parse(f: Path, engine_only: bool,
           ships: dict[str, str] | None = None) -> list[dict]:
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
    voyage = dict(d.get("voyage") or {})
    # The archive catalogues every dossier under a typed ship's name. The tool
    # reads one off the page in about a fifth of them, mangled by the same hand
    # and the same recogniser as the surnames. Both are worth searching, and
    # they are different claims — the page is the document, the catalogue is
    # somebody's note about it — so the page wins where it said anything.
    if not voyage.get("ship") and ships:
        catalogued = ships.get(d.get("file") or "")
        if catalogued:
            voyage["ship"] = catalogued
    # A record written before the repetition mark was understood still has
    # rows saying `"` where a surname belongs, and re-reading the pages to fix
    # that would cost hours. Resolved here as well as at reading time, per
    # page, so an improvement to the rule reaches the corpus at once.
    for r in _resolved(d.get("rows", [])):
        text = row_text(r)
        # the flag covers documents indexed since headings were noticed; the
        # text check covers everything indexed before that
        if r.get("header") or is_heading(text):
            continue
        if len(fold(text)) < 4:
            continue
        second = _second_reading(r, text)
        out.append({
            "doc": d.get("hash", f.stem),
            "notation": d.get("notation"),
            # the year travels with where it was read: a stamped year is a
            # weaker claim than one the clerk wrote, and the hit list says so
            **{k: voyage[k] for k in ("ship", "year", "year_source", "line")
               if voyage.get(k)},
            "file": d.get("file"),
            "page": r.get("page"),
            "row": r.get("n"),
            "text": text,
            **({"alts": second} if second else {}),
            "conf": (r.get("conf") or {}).get("surname"),
        })
    return out


def split_year(query: str) -> tuple[str, tuple[int, int] | None]:
    """The query with any year taken out of it, and the span it named.

    `Contadore 1924` is a name and a year, not a nine-character surname. Left in
    the string it competes with the spelling of the name it was meant to
    narrow. A single year is the span of one year, so everything downstream has
    one thing to reason about; `1924-1926` is the span somebody types when they
    know the decade and not the date, and typed as two loose numbers it was
    matched against surnames.
    """
    query = query or ""
    m = RE_RANGE.search(query)
    if m:
        lo, hi = sorted((int(m.group(1)), int(m.group(2))))
    else:
        m = RE_YEAR.search(query)
        if not m:
            return query.strip(), None
        lo = hi = int(m.group(1))
    # The remainder may be nothing at all — a year typed on its own is a whole
    # question, and `search` answers it by listing that year's arrivals rather
    # than by comparing four digits against every surname in the corpus.
    return (query[:m.start()] + " " + query[m.end():]).strip(), (lo, hi)


def ship_similarity(a: str, b: str) -> float:
    """How close two spellings of one ship's name are."""
    return difflib.SequenceMatcher(None, fold(a), fold(b)).ratio()


def split_ship(query: str, rows: list[dict]) -> tuple[str, str | None]:
    """The query with a ship's name taken out of it, and the ship.

    Which word is a ship cannot be decided from the query alone, so it is
    decided against the index: a term is a ship when it matches one that is
    actually there. Left in the string, `Valdivia` is compared against every
    surname on every page and dilutes the name it was typed to narrow.

    A term is only removed when what remains is still a name. Somebody looking
    for a passenger called Baden aboard the *Baden* must not be left searching
    for nothing.
    """
    ships = {r["ship"] for r in rows if r.get("ship")}
    if not ships:
        return query, None
    terms = query.split()
    for i, term in enumerate(terms):
        if len(term) < 4:
            continue
        best = max(ships, key=lambda sh: ship_similarity(term, sh))
        if ship_similarity(term, best) >= SHIP_FLOOR:
            rest = " ".join(terms[:i] + terms[i + 1:]).strip()
            if len(fold(rest)) >= MIN_QUERY:
                return rest, term
    return query, None


def line_tokens(s: str) -> list[str]:
    """The words of a shipping line worth matching on.

    `de`, `e`, `&` and the punctuation between them carry nothing: every second
    line in the corpus contains them.
    """
    return [t for t in re.split(r"[^\w]+", fold(s)) if len(t) >= 3]


def line_similarity(terms: list[str], line: str) -> float:
    """How well a typed phrase accounts for a shipping line's name.

    Zero unless *every* typed term is in the line — a phrase that is half a
    letterhead and half a surname is not a letterhead. What is returned is how
    close the terms that did match came, so a line read `Comnpanhia` is worth
    slightly less than one read correctly and both are worth having.
    """
    known = line_tokens(line)
    if not known or not terms:
        return 0.0
    total = 0.0
    for t in terms:
        best = max(difflib.SequenceMatcher(None, t, k).ratio() for k in known)
        if best < LINE_FLOOR:
            return 0.0
        total += best
    return total / len(terms)


def line_scores(rows: list[dict], terms: list[str]) -> dict[str, float]:
    """What each shipping line in the index is worth against these terms.

    Two hundred lines against a million rows: the comparison is done once per
    line, not once per passenger — the same reason the ship match is. And once
    per *word* rather than once per line, because the words of the letterheads
    are indexed: a query of four words against 237 lines is 20,000 string
    comparisons done the obvious way, which is half the cost of a keystroke.
    """
    if not terms:
        return {}
    per_term = [_term_lines(rows, t) for t in terms]
    common = set(per_term[0])
    for d in per_term[1:]:
        common &= set(d)
    return {ln: sum(d[ln] for d in per_term) / len(per_term) for ln in common}


def _lines(rows: list[dict]) -> set[str]:
    return {r["line"] for r in rows if r.get("line")}


def _vocab(rows: list[dict]) -> dict[str, set[str]]:
    """Every word of every shipping line, and the lines it appears in."""
    global _VOCAB
    key = (getattr(rows, "version", None), len(rows))
    if key[0] is not None and _VOCAB and _VOCAB[0] == key:
        return _VOCAB[1]
    vocab: dict[str, set[str]] = {}
    for ln in _lines(rows):
        for tok in line_tokens(ln):
            vocab.setdefault(tok, set()).add(ln)
    if key[0] is not None:
        _VOCAB = (key, vocab)
        _TERMS.clear()
    return vocab


def _term_lines(rows: list[dict], term: str) -> dict[str, float]:
    """Which lines contain this word, and how close the spelling came.

    Memoised per word: a searcher types the same letterhead for every ancestor
    on the same crossing, and the answer only changes when the corpus does.
    """
    key = (getattr(rows, "version", None), term)
    if key[0] is not None and key in _TERMS:
        return _TERMS[key]
    out: dict[str, float] = {}
    for tok, lines in _vocab(rows).items():
        # a word two letters longer or shorter than the one typed cannot come
        # within the floor, and the cheap ratios refuse most of the rest
        if abs(len(tok) - len(term)) > 2:
            continue
        m = difflib.SequenceMatcher(None, term, tok)
        if m.real_quick_ratio() < LINE_FLOOR or m.quick_ratio() < LINE_FLOOR:
            continue
        sc = m.ratio()
        if sc < LINE_FLOOR:
            continue
        for ln in lines:
            if sc > out.get(ln, 0.0):
                out[ln] = sc
    if key[0] is not None:
        _TERMS[key] = out
    return out


def split_line(query: str, rows: list[dict]) -> tuple[str, list[str]]:
    """The query with a shipping line taken out of it, and its words.

    A third of the corpus states a ship and two thirds state the line printed on
    the letterhead, so for most dossiers the line is the only crossing a
    searcher can name. It is decided against the index for the same reason the
    ship is — no query says which of its words is a company — and taken out for
    the same reason: left in, `Hollandsche Lloyd` is compared against every
    surname on every page and dilutes the name it was typed to narrow.

    The longest run of words that names one line wins, and only if what remains
    is still a name.
    """
    if not _vocab(rows):
        return query, []
    words = query.split()
    for size in range(min(LINE_TERMS, len(words)), 0, -1):
        for i in range(len(words) - size + 1):
            terms = [t for t in (fold(w) for w in words[i:i + size])
                     if len(t) >= 3]
            if not terms:
                continue
            if len(terms) == 1 and len(terms[0]) < LINE_SOLO:
                continue
            if not line_scores(rows, terms):
                continue
            rest = " ".join(words[:i] + words[i + size:]).strip()
            if len(fold(rest)) < MIN_QUERY:
                continue          # what is left has to still be a name
            return rest, terms
    return query, []


def voyage_bonus(row: dict, years: tuple[int, int] | None, terms: list[str],
                 lines: dict[str, float] | None = None) -> float:
    """How much the voyage a row belongs to agrees with what was typed.

    Never a filter. Most of the corpus has no voyage indexed yet, and a filter
    would make those dossiers unfindable — which is the exact failure this tool
    exists to prevent. A document that says nothing about its voyage is neither
    helped nor hurt; one that contradicts the query is ranked below the rest,
    not removed from them.
    """
    bonus = 0.0
    if years and row.get("year"):
        bonus += (VOYAGE_BONUS if years[0] <= int(row["year"]) <= years[1]
                  else -VOYAGE_PENALTY)
    ship = row.get("ship")
    if ship and terms:
        # the ship's name came off the page through the same recogniser as the
        # surnames, so it is matched as forgivingly as they are
        best = max(ship_similarity(t, ship) for t in terms)
        if best >= SHIP_FLOOR:
            bonus += VOYAGE_BONUS * best
    if lines and row.get("line"):
        bonus += VOYAGE_BONUS * lines.get(row["line"], 0.0)
    return bonus


class RowIndex(list):
    """The searchable rows, with a trigram posting list built beside them.

    Every keystroke scored the query against every row: 100 ms over the 660
    dossiers indexed so far, and the archive holds 7,679 — the same work eleven
    times over, on every letter. Memory is not what runs out first, which is
    what the note about SQLite in the progress log assumed: 19,373 rows load in
    3.8 s and cost 22 MB.

    A row can only score above zero if it shares a trigram with the query, and
    the floor is 0.10, so scoring only the rows that share one returns exactly
    the same hits with the same scores. The postings are arrays of row indices —
    four bytes each rather than a Python int apiece, which is what makes this
    affordable at a million rows.

    It is a `list`, so everything that already takes the index as a list of rows
    keeps working, and a plain list handed to `search` is still scanned whole.
    """

    def __init__(self, rows=(), version: int | None = None):
        super().__init__(rows)
        self.version = version

    @property
    def crossings(self) -> dict[str, dict]:
        """Rows by the ship, line and year they belong to.

        Kept beside the rows for the same reason the trigram postings are: the
        search endpoint loads the index on every request, and this describes the
        corpus rather than the query.
        """
        global _CROSSINGS
        key = (self.version, len(self))
        if self.version is not None and _CROSSINGS and _CROSSINGS[0] == key:
            return _CROSSINGS[1]
        by: dict[str, dict] = {"ship": {}, "line": {}, "year": {}}
        for i, r in enumerate(self):
            for field in ("ship", "line", "year"):
                v = r.get(field)
                if v is None:
                    continue
                if field == "year":
                    try:
                        v = int(v)
                    except (TypeError, ValueError):
                        continue
                by[field].setdefault(v, array("i")).append(i)
        if self.version is not None:
            _CROSSINGS = (key, by)
        return by

    @property
    def postings(self) -> tuple[dict[str, "array"], "array", "array"]:
        """Where each trigram occurs, and how big each reading is.

        A posting is a *reading* rather than a row: a row read twice is two of
        them, and the score of a row is the better of the two — which is what
        the scan did by recomputing both readings' trigrams on every query.
        That recomputation was the whole cost of a search at scale: 100,000
        calls to `trigrams` for one query over 300,000 rows, half a second of
        rebuilding what the postings already knew.

        With the size of each reading kept beside it, the overlap counted off
        the postings is exactly the score `similarity` computes — shared over
        the union — and no candidate's trigrams are built again.

        The search endpoint loads the index on every request, which is what
        makes a correction searchable the moment it is typed, so this is kept
        beside the row cache and rebuilt only when the rows were re-read.
        """
        global _POSTINGS
        key = (self.version, len(self))
        if self.version is not None and _POSTINGS and _POSTINGS[0] == key:
            return _POSTINGS[1]
        post: dict[str, array] = {}
        owner, size = array("i"), array("i")
        for i, r in enumerate(self):
            for text in (r.get("text") or "", *(r.get("alts") or ())):
                grams = trigrams(text) if text else set()
                if not grams:
                    continue
                rid = len(owner)
                owner.append(i)
                size.append(len(grams))
                for g in grams:
                    post.setdefault(g, array("i")).append(rid)
        built = (post, owner, size)
        if self.version is not None:
            _POSTINGS = (key, built)
        return built


def edit_similarity(a: str, b: str) -> float:
    """How close two spellings are letter by letter."""
    return difflib.SequenceMatcher(None, fold(a), fold(b)).ratio()


def named_ships(rows: list[dict], terms: list[str]) -> set[str]:
    """The ships in the index that the query named.

    Once per ship rather than once per passenger: a hundred and twenty-eight
    spellings against a million rows.
    """
    if not terms:
        return set()
    return {sh for sh in {r["ship"] for r in rows if r.get("ship")}
            if max(ship_similarity(t, sh) for t in terms) >= SHIP_FLOOR}


def on_crossing(row: dict, years: tuple[int, int] | None, ships: set[str],
                lines: dict[str, float] | None) -> bool:
    """Whether this row belongs to the crossing the query named.

    The same agreement the voyage bonus rewards, asked as a yes or no: this is
    what decides which rows are cheap enough to compare letter by letter.
    """
    if years and row.get("year") and years[0] <= int(row["year"]) <= years[1]:
        return True
    if ships and row.get("ship") in ships:
        return True
    return bool(lines and row.get("line") in lines)


def crossing_pool(rows: list[dict], years: tuple[int, int] | None,
                  ships: set[str], lines: dict[str, float] | None) -> list[dict]:
    """The rows of the crossing the query named.

    Walking every row to ask each one costs nothing at 30,000 and is a scan of
    the whole corpus at a million, which is what this pass exists to avoid. The
    rows carry an index by ship, line and year once they come out of
    `load_index`; a plain list is still walked.
    """
    by = getattr(rows, "crossings", None)
    if by is None:
        return [r for r in rows if on_crossing(r, years, ships, lines)]
    hit: set[int] = set()
    for sh in ships:
        hit.update(by["ship"].get(sh, ()))
    for ln in (lines or ()):
        hit.update(by["line"].get(ln, ()))
    if years:
        for y in range(years[0], years[1] + 1):
            hit.update(by["year"].get(y, ()))
    return [rows[i] for i in sorted(hit)]


def candidates(rows: list[dict], query: str) -> list[tuple[dict, float]]:
    """The rows worth scoring against this query, with their name score.

    Without a posting list every row is compared, the way it always was. With
    one, the overlap is counted off the postings and the score comes out of the
    arithmetic — the same number `similarity` returns, without rebuilding any
    row's trigrams. A row missing from every posting of the query scores zero
    and would be dropped by the floor anyway.
    """
    index = getattr(rows, "postings", None)
    if index is None:
        return [(r, max(similarity(query, t)
                        for t in (r["text"], *(r.get("alts") or ()))))
                for r in rows]
    post, owner, size = index
    grams = trigrams(query)
    shared: dict[int, int] = {}
    for g in grams:
        ids = post.get(g)
        if not ids:
            continue
        for rid in ids:
            shared[rid] = shared.get(rid, 0) + 1
    best: dict[int, float] = {}
    n = len(grams)
    for rid, common in shared.items():
        s = common / (n + size[rid] - common)
        i = owner[rid]
        if s > best.get(i, 0.0):
            best[i] = s
    return [(rows[i], best[i]) for i in sorted(best)]


def search(rows: list[dict], query: str, limit: int = 50,
           min_score: float = MIN_SCORE) -> list[dict]:
    """Ranked matches, best first. An unrecognisable query returns nothing."""
    if len(fold(query)) < MIN_QUERY:
        return []
    name_q, years = split_year(query)
    name_q, ship_term = split_ship(name_q, rows)
    name_q, line_terms = split_line(name_q, rows)
    terms = [ship_term] if ship_term else []
    lines = line_scores(rows, line_terms)
    scored = []
    # Each candidate comes with its name score: the better of what the row was
    # read as and what the second reading said, which differ only where the
    # hand was hard — exactly where a search fails.
    #
    # An empty name query is not a query, and is not asked. Trigrams are
    # padded, so the score of nothing against a row read as `B   B` comes out
    # at 0.25 — a page of whitespace ranked above the ship somebody typed.
    pool = candidates(rows, name_q) if len(fold(name_q)) >= MIN_QUERY else ()
    for r, s in pool:
        # the floor is applied to the name alone: the voyage orders what was
        # found, it does not decide what counts as found
        if s >= min_score:
            # The voyage multiplies the name match rather than adding to it. A
            # flat bonus lifts every row on the named ship by the same amount,
            # and most rows on any ship resemble nothing that was typed — it
            # put `CONGE NGLONE A` above `Guudo Casrtadore` for a query naming
            # the Contadores' ship. What is wanted is to sharpen a match, not
            # to manufacture one.
            bonus = voyage_bonus(r, years, terms, lines)
            rank = max(0.0, min(1.0, s * (1 + bonus)))
            scored.append({**r, "score": round(rank, 3), "name_score": round(s, 3)})
    if years or terms or lines:
        scored.extend(_letter_by_letter(rows, name_q, years, terms, lines,
                                        {(h["doc"], h["row"]) for h in scored}))
    scored.sort(key=lambda h: (-h["score"], h.get("file") or "", h["row"] or 0))

    # "Show me everyone on the Itapuca" is the other half of this tool, and a
    # ship's name typed on its own used to be compared against surnames — it
    # returned whatever happened to look like it while the dossier filed under
    # that exact name was nowhere in the results. The people aboard are added
    # after the name matches rather than instead of them: `Formosa` is a ship
    # and a surname, and somebody typing it means a person more often than not.
    seen = {(h["doc"], h["row"]) for h in scored}
    aboard = _aboard(rows, query, seen)
    if not aboard:
        # The line is asked the same way the ship is, and for the dossiers that
        # name no ship it is the only way to ask: two thirds of the corpus
        # states a line, a third a ship.
        aboard = _sailed(rows, query, seen)
    if not aboard and years and len(fold(name_q)) < MIN_QUERY:
        # A year typed on its own is the same question as a ship typed on its
        # own, and it was stripped out of the query as a year should be —
        # leaving nothing at all to search for.
        aboard = _arrived(rows, years, seen)
    # A row scoring 0.15 against a surname is noise; the passengers of the ship
    # that was typed are a certainty. Strong name matches keep the top of the
    # list, the ship's own dossier follows, and the guesses come after it.
    strong = [h for h in scored if h["score"] >= STRONG_NAME]
    weak = [h for h in scored if h["score"] < STRONG_NAME]
    return (strong + aboard + weak)[:limit]


def _arrived(rows: list[dict], years: tuple[int, int], already: set) -> list[dict]:
    """Rows from every document that says it landed in these years."""
    out = [{**r, "score": 1.0, "matched": "year"} for r in rows
           if r.get("year") and years[0] <= int(r["year"]) <= years[1]
           and (r["doc"], r["row"]) not in already]
    out.sort(key=lambda h: (h.get("file") or "", h.get("page") or 0, h["row"] or 0))
    return out


def _aboard(rows: list[dict], query: str, already: set) -> list[dict]:
    """Rows from every document filed under the ship that was typed."""
    ships = {r["ship"] for r in rows if r.get("ship")}
    if not ships:
        return []
    # A hundred and twenty-eight ships against a million rows: the comparison
    # is done once per ship, not once per passenger.
    close = {sh: round(ship_similarity(query, sh), 3) for sh in ships}
    close = {sh: sc for sh, sc in close.items() if sc >= SHIP_FLOOR}
    if not close:
        return []
    out = [{**r, "score": close[r["ship"]], "matched": "ship"}
           for r in rows
           if r.get("ship") in close and (r["doc"], r["row"]) not in already]
    out.sort(key=lambda h: (h.get("file") or "", h.get("page") or 0, h["row"] or 0))
    return out


def _sailed(rows: list[dict], query: str, already: set) -> list[dict]:
    """Rows from every document printed on the letterhead that was typed.

    Naming most of a line is a different question from mentioning it beside a
    surname: `Muesso Hollandsche Lloyd` is a search for Muesso, and
    `Koninklijke Hollandsche Lloyd` is a search for the line. The two are told
    apart by how much of the letterhead the query accounts for.
    """
    terms = line_tokens(query)
    if not terms:
        return []
    close = {}
    for ln, sc in line_scores(rows, terms).items():
        # every word typed is in the line; enough of the line was typed
        if len(terms) / len(line_tokens(ln)) >= LINE_COVERAGE:
            close[ln] = round(sc, 3)
    if not close:
        return []
    out = [{**r, "score": close[r["line"]], "matched": "line"}
           for r in rows
           if r.get("line") in close and (r["doc"], r["row"]) not in already]
    out.sort(key=lambda h: (h.get("file") or "", h.get("page") or 0, h["row"] or 0))
    return out


def _letter_by_letter(rows: list[dict], name_q: str,
                      years: tuple[int, int] | None, terms: list[str],
                      lines: dict[str, float] | None,
                      already: set) -> list[dict]:
    """Rows of the named crossing that read like the name, letter by letter.

    The trigram pass has already had its say; this is the second chance the
    recogniser's systematic substitutions need — `Manvil' Dar Cuy` for *Manoel
    da Cruz*, which shares no trigram with it and stands at 0.69 by edit
    distance. It is affordable only because the crossing cut the pool: a
    dossier is a few hundred rows, and a name compared against 70,000 of them
    letter by letter would be both slow and full of Marias.

    The score is the edit distance, ranked by the same voyage bonus as
    everything else, so a row argued for this way sits below a row that plainly
    reads what was typed.
    """
    q = fold(name_q)
    if len(q) < MIN_QUERY:
        return []
    ships = named_ships(rows, terms)
    pool = crossing_pool(rows, years, ships, lines)
    # One matcher for the whole scan, with the query loaded once: it keeps the
    # index of the query's characters between comparisons, and the two cheap
    # ratios refuse most rows before the real one is computed. The length test
    # in front of them is cheaper still — two strings that differ enough in
    # length cannot reach the floor whatever their letters are.
    m = difflib.SequenceMatcher(autojunk=False)
    m.set_seq2(q)
    out = []
    for r in pool:
        if (r["doc"], r["row"]) in already:
            continue
        s = 0.0
        for text in (r["text"], *(r.get("alts") or ())):
            t = fold(text)
            if not t or 2 * min(len(q), len(t)) < EDIT_FLOOR * (len(q) + len(t)):
                continue
            m.set_seq1(t)
            # both cheap ratios are upper bounds on the real one and both are
            # symmetric — lengths, and letters in common — so they refuse rows
            # for either orientation. The score itself is taken the way
            # `edit_similarity` takes it, because which string is which changes
            # the third decimal and the third decimal decides two names.
            if (m.real_quick_ratio() < EDIT_FLOOR
                    or m.quick_ratio() < EDIT_FLOOR):
                continue
            s = max(s, edit_similarity(name_q, text))
        if s < EDIT_FLOOR:
            continue
        rank = max(0.0, min(1.0, s * (1 + voyage_bonus(r, years, terms, lines))))
        out.append({**r, "score": round(rank, 3), "name_score": round(s, 3),
                    # how it was found, because a row that shares no trigram
                    # with the query looks like a broken search otherwise
                    "matched": "letters"})
    return out
