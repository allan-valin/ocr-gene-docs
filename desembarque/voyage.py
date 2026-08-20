"""What a dossier says about the voyage, taken from its printed forms.

Every dossier carries a page that names the ship, where it sailed from and when
it arrived: either the interpreter's *PARTE* form or the printed header above
the passenger list. None of it reaches the index today, so a search has nothing
to narrow a name against — and a name read out of a cursive hand needs every
bit of narrowing it can get.

The division of trust here is the whole design. The labels are printed and come
through the recogniser well; the values beside them are handwritten and come
through mangled. So the labels are matched, and whatever sits next to them is
reported verbatim, unjudged. The one exception is the month, because a month is
one of twelve known words rather than an open set — a near miss there can be
resolved without guessing.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

# The forms are Brazilian; the shipping companies printing them are not. A list
# from the Compagnie de Navigation Sud Atlantique has its date written in French,
# and reading only Portuguese loses the year of every French line in the corpus.
MONTHS = [
    ("janeiro", "janvier"), ("fevereiro", "fevrier"), ("marco", "mars"),
    ("abril", "avril"), ("maio", "mai"), ("junho", "juin"),
    ("julho", "juillet"), ("agosto", "aout"), ("setembro", "septembre"),
    ("outubro", "octobre"), ("novembro", "novembre"), ("dezembro", "decembre"),
]

# How close a mangled word has to be to a month name before it counts as one.
# Measured rather than picked: over the labels and values that appear on these
# forms, real months score 0.80 and up (`Oatubro` 0.86, `Fevereire` 0.89) while
# the nearest thing that is not a month scores 0.53 (`entrado`). The floor sits
# in the gap, not near either edge.
MONTH_FLOOR = 0.75


def fold(s: str) -> str:
    """Lower case, unaccented, letters only — the form the labels are matched in."""
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c for c in s if c.isalnum() or c.isspace()).strip()


def month_number(text: str) -> int | None:
    """1-12 for a Portuguese month name, or None when the word is not one."""
    word = fold(text)
    if not word:
        return None
    best, won, score = None, "", 0.0
    for i, names in enumerate(MONTHS, start=1):
        for name in names:
            s = difflib.SequenceMatcher(None, word, name).ratio()
            if s > score:
                best, won, score = i, name, s
    if score < MONTH_FLOOR:
        return None
    # A three-letter name is a third of a word, and the threshold means almost
    # nothing on one: `mai` is within a letter of a great many things that are
    # not months. Short spellings have to be exact; the long spelling of the
    # same month still absorbs a bad hand.
    if len(won) <= 3 and word != won:
        return None
    return best


# The printed labels on the two forms. They are what the recogniser reads well,
# so they are the anchors; everything between them is handwriting and is
# reported as read. `de` before the month is written `deDesembro` about as often
# as `de Desembro` — the recogniser loses the space between a printed word and
# the writing that follows it.
RE_PAQUETE = re.compile(r"paquete\b(.*)", re.I)
RE_QUOTED = re.compile(r"[\"“”]\s*([^\"“”]{2,40}?)\s*[\"“”]")
RE_ORIGIN = re.compile(r"procedente\s+d[eo]\b(.*)", re.I)
# The day is whatever was written where the day goes -- often a stroke the
# recogniser makes an `f` or an `Hp` of. It is captured as read and only
# becomes part of a date when it is a number.
RE_ENTERED = re.compile(
    r"entrado\s+em\s*(\S{1,3})\s*de\s*([A-Za-zÀ-ÿ]{3,12})\s*de\s*(\d{2}\s*\d{0,2})", re.I)
RE_LANDED = re.compile(r"lista\s+com\s+(\S{1,4})\s+i?mm?igrantes", re.I)

# Enough of the PARTE form has to be present to call a page one. Any single line
# can come through wrong, so no one line is allowed to decide it.
PARTE_MARKS = ["parte", "interprete", "que visitou o paquete",
               "servico de povoamento", "saude dos passageiros",
               "mortalidade", "nascimentos", "observacoes"]

# The printed header above a passenger list says the same things in different
# words, and it is on every list — where the PARTE form is only on the dossiers
# that kept theirs. The two are told apart because they mean different things by
# the word beside `paquete`: the PARTE form writes the ship's nationality there,
# this one writes the ship.
# Each shipping line had its own forms printed, and the recogniser mangles each
# of them differently: one sheet reads `consignado meste porte`, and the whole
# phrase never matches. So the marks are the shortest wording that is still
# particular to this form — `consignado` appears nowhere else on these pages,
# and `porto de` is the label above the port, not the `Porto do Rio de Janeiro`
# in the other form's letterhead.
LISTA_MARKS = ["lista de entra", "de passageiros no", "toneladas de registro",
               "pessoas de tripulacao", "sob o commando de", "consignado",
               "policia do porto", "porto de"]

# The letterhead is the first thing printed on the sheet, above everything the
# clerk filled in. These two lines come before it and are not it.
NOT_LETTERHEAD = ["policia do porto", "modelo n"]
# The archival notation is stamped at the top of most sheets, above the printed
# letterhead. It is the one line up there that carries a long run of digits.
RE_NOTATION = re.compile(r"\d{4,}")


@dataclass
class Voyage:
    """One arrival, as the paperwork states it.

    Every field is optional and every one of them may be wrong in the way
    handwriting is wrong; what the record promises is only that the value was
    written next to that printed label on that page.
    """
    source: str
    ship: str | None = None
    flag: str | None = None
    origin: str | None = None
    line: str | None = None
    port: str | None = None
    arrival: str | None = None
    arrival_raw: str | None = None
    year: int | None = None
    month: int | None = None
    passengers: int | None = None

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


def _clean(value: str) -> str:
    return value.strip().strip(" .,;:-_—\"“”").strip()


def _label_line(pattern: re.Pattern, lines: list[str]) -> int:
    for i, line in enumerate(lines):
        if pattern.search(line):
            return i
    return -1


def _is_label(line: str) -> bool:
    folded = fold(line)
    return any(mark in folded for mark in PARTE_MARKS + LISTA_MARKS)


def _above(pattern: re.Pattern, lines: list[str], skip: str | None) -> str | None:
    """The ship: the first line above the label that belongs to nothing else.

    Where the nationality follows `paquete` on the label's own line, the line
    directly above carries the *interpreter's* name against the interpreter's
    label, and taking it would file the voyage under a clerk. Where nothing
    follows the label, the line directly above is the nationality and has
    already been read as such. So the search climbs past both.
    """
    i = _label_line(pattern, lines)
    if i < 0:
        return None
    for j in range(i - 1, -1, -1):
        value = _clean(lines[j])
        if not value or _is_label(lines[j]) or (skip and value == skip):
            continue
        return value
    return None


def _beside(pattern: re.Pattern, lines: list[str], above: int = 1) -> str | None:
    """The value written against a printed label.

    On some sheets it follows the label on the same line; on others nothing
    does, because the handwriting sits a little above the printed baseline and
    the detector reports it first. Both readings are the same physical line of
    the form, so the value above the label is as much "beside" it as the value
    after it. Which one it is varies from clerk to clerk within one dossier.
    """
    i = _label_line(pattern, lines)
    if i < 0:
        return None
    trailing = _clean(pattern.search(lines[i]).group(1))
    if trailing:
        return trailing
    # Nothing follows the label, so the value is on one of its neighbours. The
    # line above is the usual one — the handwriting sits a little high and the
    # detector reports it first — but where the label ends a printed line the
    # value begins the next one. Whichever of the two is not itself a label.
    for j in (i - 1, i + 1):
        if 0 <= j < len(lines) and not _is_label(lines[j]):
            value = _clean(lines[j])
            if value:
                return value
    return None


def _marks(lines: list[str], marks: list[str]) -> int:
    folded = [fold(l) for l in lines]
    return sum(1 for mark in marks if any(mark in f for f in folded))


def _letterhead(lines: list[str]) -> str | None:
    """The shipping line, printed at the top of a passenger list.

    It survives a scan that the handwriting does not, and it is what a person
    means when they say "the Lloyd ship" — so it is worth having even though it
    is the one field nobody writes.
    """
    for line in lines[:4]:
        folded = fold(line)
        if not folded or any(mark in folded for mark in NOT_LETTERHEAD):
            continue
        if _is_label(line) or len(folded) < 8 or RE_NOTATION.search(line):
            continue
        return _clean(line)
    return None


def _read_date(v: Voyage, lines: list[str]) -> None:
    """The arrival, from `entrado em __ de ______ de 19__`.

    The three parts are read separately because they fail separately. The month
    is one of twelve words and survives a bad hand; the day is a single stroke
    and often does not; the century is printed and the year written beside it,
    so the detector reports `19 25`. A date is only asserted when all three are
    certain — the alternative is a plausible wrong date on a record used as
    evidence, which is the worst kind.
    """
    # `entrado em 4 de Novembro` and `de 1923` are one printed line the detector
    # split in two, so each line is read together with the one after it.
    for a, b in zip(lines, lines[1:] + [""]):
        m = RE_ENTERED.search(f"{a} {b}")
        if not m:
            continue
        day, month_word, year = m.group(1), m.group(2), m.group(3)
        v.arrival_raw = _clean(m.group(0)[m.group(0).lower().index("em") + 2:])
        v.month = month_number(month_word)
        digits = re.sub(r"\s+", "", year)
        v.year = int(digits) if len(digits) == 4 else None
        if v.month and v.year and day.isdigit() and 1 <= int(day) <= 31:
            v.arrival = f"{v.year:04d}-{v.month:02d}-{int(day):02d}"
        return


RE_YEAR_TAIL = re.compile(r"\bde\s*(\d{2}\s*\d{0,2})\b", re.I)
RE_PORT = re.compile(r"^(.{3,24}?)\s*,\s*$")


def _read_port(lines: list[str]) -> str | None:
    """The port, written where the letterhead leaves room for it.

    The form prints `_______, ___ de ______ de 19__` under the company name, so
    the port is the short line ending in the form's own comma. It is reported as
    read: `Nio Sumalos` is what the page gives for Rio de Janeiro, and correcting
    it here would be inventing a reading nobody can check against the scan.
    """
    for line in lines[:8]:
        m = RE_PORT.match(line.strip())
        if m and not month_number(m.group(1)) and not m.group(1).strip().isdigit():
            return _clean(m.group(1))
    return None


def _read_dateline(v: Voyage, lines: list[str]) -> None:
    """The date on a list header, which has no `entrado em` to anchor on.

    It sits under the letterhead as `port, day de month de 19yy`, and the
    detector usually reports it in pieces. The month is the anchor: it is one of
    a couple of dozen known words, in Portuguese or French, and nothing else on
    this part of the page looks like one.
    """
    for i, line in enumerate(lines[:10]):
        month = next((month_number(w) for w in line.split()
                      if month_number(w)), None)
        if not month:
            continue
        v.month = month
        # the day is the token before the month, where there is one that reads
        # as a number; `em 19 de Marco` is the common shape
        words = line.split()
        at = next(i for i, w in enumerate(words) if month_number(w))
        prev = words[at - 1] if at else ""
        if fold(prev) in ("de", "do") and at >= 2:
            prev = words[at - 2]        # `19 de Marco`, not `de Marco`
        prev = "".join(c for c in prev if c.isdigit())
        day = int(prev) if prev and 1 <= int(prev) <= 31 else None
        window = " ".join(lines[i:i + 3])
        m = RE_YEAR_TAIL.search(window)
        if m:
            digits = re.sub(r"\s+", "", m.group(1))
            v.year = int(digits) if len(digits) == 4 else None
        if day and v.year and v.month:
            v.arrival = f"{v.year:04d}-{v.month:02d}-{day:02d}"
        v.arrival_raw = _clean(window[:60])
        return


def parse_voyage(text: str) -> Voyage | None:
    """The voyage a page states, or None when the page is not one of the forms."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    if not lines:
        return None
    parte, lista = _marks(lines, PARTE_MARKS), _marks(lines, LISTA_MARKS)
    # The PARTE form is recognised by short words — `parte`, `mortalidade` —
    # which turn up elsewhere, so it takes three of them. The list header is
    # recognised by whole printed phrases that appear nowhere else on a page,
    # and two of those are already more evidence. Neither form is made to fit:
    # a page that is neither is left alone.
    if parte < 3 and lista < 2:
        return None
    v = Voyage(source="parte" if parte >= lista else "lista")
    if v.source == "lista":
        v.line = _letterhead(lines)

    # Two things are written against `paquete`: the ship, and the nationality of
    # the line that owned it. On one sheet the nationality follows the label and
    # the ship is quoted two lines up; on another neither shares the label's
    # line and the ship sits above the nationality. The nationality is the value
    # immediately beside the label in both, and the ship is the one beyond it.
    if v.source == "lista":
        # No nationality field on this form: the name beside `paquete` is the
        # ship. Reading it the PARTE way would file every voyage under the
        # wrong word.
        v.ship = _beside(RE_PAQUETE, lines)
        v.origin = _beside(RE_ORIGIN, lines)
        v.port = _read_port(lines)
        _read_date(v, lines)
        if v.year is None:
            _read_dateline(v, lines)
        return v

    v.flag = _beside(RE_PAQUETE, lines)
    quoted = None
    for line in lines:
        m = RE_QUOTED.search(line)
        if m and not month_number(m.group(1)):
            quoted = _clean(m.group(1))
            break
    if quoted and v.flag and quoted in v.flag:
        # The whole printed line came back at once, so the words beside
        # `paquete` are the nationality *and* the ship it belongs to. The
        # nationality is written first, before the quotation mark opens.
        v.flag = _clean(v.flag[:v.flag.index(quoted)]) or None
    v.ship = quoted or _above(RE_PAQUETE, lines, skip=v.flag)

    v.origin = _beside(RE_ORIGIN, lines)

    _read_date(v, lines)

    for a, b in zip(lines, lines[1:] + [""]):
        m = RE_LANDED.search(f"{a} {b}")
        if m:
            if m.group(1).isdigit():
                v.passengers = int(m.group(1))
            break
    return v
