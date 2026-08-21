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
SCHEMA = 17
MIN_QUERY = 3
MIN_SCORE = 0.10

# What the voyage is worth as a proportion of the name match it applies to. It
# is meant to break the tie a recogniser cannot, not to overrule the name.
VOYAGE_BONUS = 0.25
# A ship's name is one token, and trigrams are harsh on single tokens: changing
# the last letter of `Valdivia` to `Valdivin` — exactly what the recogniser does
# to it — costs a third of the trigram score. Edit distance is the right measure
# for one word, and it is the same one the month names use.
SHIP_FLOOR = 0.75
# Above this a name match is an answer; below it, it is a suggestion.
STRONG_NAME = 0.5
RE_YEAR = re.compile(r"\b(1[6-9]\d{2}|20[0-2]\d)\b")


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


# What a bag-of-words match is worth against a match on the whole string. A
# name matched word by word is a weaker claim — `Maria` scores 1.0 against
# `Martinez Maria` on one of its two words — so it ranks below a row that
# resembles the whole query.
TOKEN_WEIGHT = 0.85


def token_similarity(query: str, text: str) -> float:
    """How well the words of the query are answered by the words of the row.

    A family list writes one surname for eight people and the recogniser
    mangles it once: `Martinez Dolores` is read as `artinies Dotores`, and
    compared as one string the good half is dragged under by the bad half.
    Compared word by word, the given name still answers.
    """
    a = fold(query).split()
    b = fold(text).split()
    if not a or not b:
        return 0.0
    return sum(max(similarity(t, u) for u in b) for t in a) / len(a)


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
            **{k: voyage[k] for k in ("ship", "year", "year_source")
               if voyage.get(k)},
            "file": d.get("file"),
            "page": r.get("page"),
            "row": r.get("n"),
            "text": text,
            **({"alts": second} if second else {}),
            "conf": (r.get("conf") or {}).get("surname"),
        })
    return out


def split_year(query: str) -> tuple[str, int | None]:
    """The query with any year taken out of it, and the year.

    `Contadore 1924` is a name and a year, not a nine-character surname. Left in
    the string it competes with the spelling of the name it was meant to
    narrow.
    """
    m = RE_YEAR.search(query or "")
    if not m:
        return (query or "").strip(), None
    # The remainder may be nothing at all — a year typed on its own is a whole
    # question, and `search` answers it by listing that year's arrivals rather
    # than by comparing four digits against every surname in the corpus.
    return (query[:m.start()] + " " + query[m.end():]).strip(), int(m.group(1))


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


def voyage_bonus(row: dict, year: int | None, terms: list[str]) -> float:
    """How much the voyage a row belongs to agrees with what was typed.

    Never a filter. Most of the corpus has no voyage indexed yet, and a filter
    would make those dossiers unfindable — which is the exact failure this tool
    exists to prevent. A document that says nothing about its voyage is neither
    helped nor hurt; one that contradicts the query is ranked below the rest,
    not removed from them.
    """
    bonus = 0.0
    if year and row.get("year"):
        bonus += VOYAGE_BONUS if int(row["year"]) == year else -VOYAGE_BONUS
    ship = row.get("ship")
    if ship and terms:
        # the ship's name came off the page through the same recogniser as the
        # surnames, so it is matched as forgivingly as they are
        best = max(ship_similarity(t, ship) for t in terms)
        if best >= SHIP_FLOOR:
            bonus += VOYAGE_BONUS * best
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
    def postings(self) -> dict[str, "array"]:
        # The search endpoint loads the index on every request — that is what
        # makes a correction searchable the moment it is typed — so the
        # postings are kept beside the row cache and rebuilt only when the
        # rows themselves were re-read.
        global _POSTINGS
        key = (self.version, len(self))
        if self.version is not None and _POSTINGS and _POSTINGS[0] == key:
            return _POSTINGS[1]
        post: dict[str, array] = {}
        for i, r in enumerate(self):
            grams = set(trigrams(r.get("text") or ""))
            for alt in r.get("alts") or ():
                grams |= trigrams(alt)
            for g in grams:
                post.setdefault(g, array("i")).append(i)
        if self.version is not None:
            _POSTINGS = (key, post)
        return post


def candidates(rows: list[dict], query: str) -> list[dict]:
    """The rows worth scoring against this query.

    Everything, unless the rows carry a posting list. The union is taken over
    the query's trigrams: a row missing from all of them scores zero and would
    be dropped by the floor anyway.
    """
    post = getattr(rows, "postings", None)
    if post is None:
        return rows
    hit: set[int] = set()
    for g in trigrams(query):
        ids = post.get(g)
        if ids:
            hit.update(ids)
    return [rows[i] for i in sorted(hit)]


def search(rows: list[dict], query: str, limit: int = 50,
           min_score: float = MIN_SCORE) -> list[dict]:
    """Ranked matches, best first. An unrecognisable query returns nothing."""
    if len(fold(query)) < MIN_QUERY:
        return []
    name_q, year = split_year(query)
    name_q, ship_term = split_ship(name_q, rows)
    terms = [ship_term] if ship_term else []
    scored = []
    # An empty name query is not a query. Trigrams are padded, so `similarity`
    # of nothing against a row read as `B   B` comes out at 0.25 — a page of
    # whitespace ranked above the ship somebody actually typed.
    pool = candidates(rows, name_q) if len(fold(name_q)) >= MIN_QUERY else ()
    for r in pool:
        # the better of what the row was read as and what the second reading
        # said: the two differ only where the hand was hard, which is exactly
        # where a search fails
        readings = [r["text"], *(r.get("alts") or ())]
        s = max(similarity(name_q, t) for t in readings)
        # the floor is applied to the name alone: the voyage orders what was
        # found, it does not decide what counts as found
        if s >= min_score:
            # The voyage multiplies the name match rather than adding to it. A
            # flat bonus lifts every row on the named ship by the same amount,
            # and most rows on any ship resemble nothing that was typed — it
            # put `CONGE NGLONE A` above `Guudo Casrtadore` for a query naming
            # the Contadores' ship. What is wanted is to sharpen a match, not
            # to manufacture one.
            rank = max(0.0, min(1.0, s * (1 + voyage_bonus(r, year, terms))))
            scored.append({**r, "score": round(rank, 3), "name_score": round(s, 3)})
    scored.sort(key=lambda h: (-h["score"], h.get("file") or "", h["row"] or 0))

    # "Show me everyone on the Itapuca" is the other half of this tool, and a
    # ship's name typed on its own used to be compared against surnames — it
    # returned whatever happened to look like it while the dossier filed under
    # that exact name was nowhere in the results. The people aboard are added
    # after the name matches rather than instead of them: `Formosa` is a ship
    # and a surname, and somebody typing it means a person more often than not.
    seen = {(h["doc"], h["row"]) for h in scored}
    aboard = _aboard(rows, query, seen)
    if not aboard and year and len(fold(name_q)) < MIN_QUERY:
        # A year typed on its own is the same question as a ship typed on its
        # own, and it was stripped out of the query as a year should be —
        # leaving nothing at all to search for.
        aboard = _arrived(rows, year, seen)
    # A row scoring 0.15 against a surname is noise; the passengers of the ship
    # that was typed are a certainty. Strong name matches keep the top of the
    # list, the ship's own dossier follows, and the guesses come after it.
    strong = [h for h in scored if h["score"] >= STRONG_NAME]
    weak = [h for h in scored if h["score"] < STRONG_NAME]
    return (strong + aboard + weak)[:limit]


def _arrived(rows: list[dict], year: int, already: set) -> list[dict]:
    """Rows from every document that says it landed in this year."""
    out = [{**r, "score": 1.0, "matched": "year"} for r in rows
           if r.get("year") and int(r["year"]) == year
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
