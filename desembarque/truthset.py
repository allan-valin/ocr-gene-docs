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
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# What a reader can say about a band on the page, and they are three answers
# and not two. A reading is a name. An unreadable row is the reader saying so,
# which is the class the old six files had no way to write down and the reason
# every number taken from them flatters: the illegible rows were simply absent,
# so a recogniser was never charged for inventing a name on one. A band that is
# not a row at all -- a rule, a struck-through space -- is neither.
READ = "read"
UNREADABLE = "unreadable"
ABSENT = "absent"

def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


def with_ditto_resolved(wanted: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """A hand-read cell written as the clerk wrote it, with the mark filled in.

    Allan reads `Viola "` under `Julia Hunt Jones` because that is what the
    page says, and a person looking for Viola would type *Viola Hunt Jones*.
    Scored as written, the query is one given name against the whole archive
    — rank 15 on the held-out sheet for a row the engine had read right. So
    the mark inherits from the nearest read row above it exactly as the
    index's own rows do (`desembarque.ditto`): the words that row wrote and
    this one does not, counted from the left. `" Maria` and `Viola "` both
    come out as the name a searcher would type; what was typed on the sheet
    is untouched.
    """
    from desembarque import ditto
    out: list[tuple[int, str]] = []
    above: list[str] = []
    for n, text in sorted(wanted):
        raw = (text or "").strip()
        has_mark = ditto.is_mark(raw) or any(ditto.is_mark(w) for w in raw.split())
        # the sheet writes the mark as its own token; the engine glues it
        words = ditto.written(" ".join(w for w in raw.split() if not ditto.is_mark(w)))
        if has_mark and above:
            # the mark stands where the repeated words stand: after what the
            # row wrote, the family name is the end of the name above; before
            # it, the start. A mark alone repeats the whole name.
            if not words:
                words = list(above)
            elif ditto.is_mark(raw.split()[0]):
                words = above[:max(0, len(above) - len(words))] + words
            else:
                words = words + above[min(len(words), len(above) - 1):]
        resolved = " ".join(words) if words else raw
        out.append((n, resolved))
        if words:
            above = words
    return out


def pairs(truth: dict, rows: list[dict]) -> list[dict]:
    """Each hand-read name beside the row the engine stored for it.

    Paired by row number, not by order: a page whose bands the engine cut
    differently has rows missing in the middle, and pairing by position would
    then compare every later name with somebody else's.
    """
    on_page = sorted((r for r in rows if r.get("page") == truth.get("page")),
                     key=lambda r: r.get("n") or 0)
    by_n = {r.get("n"): r for r in on_page}
    # Two shapes, because pages come in two kinds. A page where somebody was
    # sure of eleven rows out of forty-one gives `rows`, keyed by the row
    # numbers they wrote against, and those are taken as they stand. A page
    # read straight down gives `names`, a run, and the run is aligned to the
    # readings rather than counted from `first_row`: that number goes stale
    # when a page is cut differently, and a run counted from anywhere drifts
    # past the first row that carries no reading. See `aligned`.
    if truth.get("rows"):
        # the shorthand of the new format lives here too: a row nobody could
        # read and a band that is no row are not names to search for, and the
        # marker on an uncertain reading is not part of the name
        cells = [parse_cell(cell, n=int(n)) for n, cell in truth["rows"].items()]
        # a reader who types the printed heading into its band has read the
        # page faithfully, and it is not a person to search for
        from desembarque.sheetbands import is_heading
        wanted = [(c.n, c.text) for c in cells
                  if c.kind == READ and not is_heading(c.text)]
        wanted = with_ditto_resolved(wanted)
        sure = {c.n: c.certain for c in cells}
    else:
        sure = {}
        placed = aligned([r.get("name_raw") or "" for r in on_page],
                         [n for n in (truth.get("names") or []) if n])
        wanted = [(on_page[i].get("n"), name) for i, name in placed.items()]
    out = []
    for n, name in sorted(wanted):
        row = by_n.get(n)
        if row is None or not (row.get("name_raw") or "").strip():
            continue
        # the page a pair came from travels with it: a bench that wants
        # anything else about the row — its nationality, for the language
        # prior — has to be able to find the row again
        out.append({"truth": name, "read": row["name_raw"], "row": row,
                    "pdf": truth.get("pdf"), "page": truth.get("page"),
                    "certain": sure.get(n, True)})
    return out


def aligned(readings: list[str], names: list[str]) -> dict[int, str]:
    """Which reading each hand-read name belongs to, allowing skipped rows.

    A run of names read straight down a page has to be put against the rows the
    page was cut into, and two things go wrong at once. The stored `first_row`
    goes stale — `data/truth/BS_ENT_014541-p2.json` says 4 because the comb
    that read it in July counted the header bands, and measured from the
    printing those passengers are rows one to six — so a stored offset labels
    every row with the name three above it. And a page whose middle rows carry
    no reading has gaps, so a single best-fit offset drifts past the first gap
    and labels everything after it with the name above.

    So the two lists are aligned the way two sequences are: monotonically, name
    by name, paying for the mismatch and allowed to skip a row that nobody
    wrote a name against. Skipping a row is free, since a page is mostly rows
    the truth says nothing about; skipping a *name* costs a whole name, since
    every name in the run is on the page somewhere.
    """
    if not readings or not names:
        return {}
    R, N = len(readings), len(names)
    folded = [fold(r) for r in readings]
    want = [fold(n) for n in names]

    def cost(i: int, j: int) -> float:
        if not folded[i]:
            return 1.0
        return 1.0 - difflib.SequenceMatcher(None, folded[i], want[j]).ratio()

    # best[i][j]: the cheapest way to place the first j names among the first
    # i rows. A name costs 1.0 unplaced, which is dearer than any mismatch.
    big = float(N + R + 1)
    best = [[big] * (N + 1) for _ in range(R + 1)]
    back = [[None] * (N + 1) for _ in range(R + 1)]
    for i in range(R + 1):
        best[i][0] = 0.0
    for i in range(1, R + 1):
        for j in range(1, N + 1):
            skip_row = best[i - 1][j]
            take = best[i - 1][j - 1] + cost(i - 1, j - 1)
            drop_name = best[i][j - 1] + 1.0
            best[i][j] = min(skip_row, take, drop_name)
            back[i][j] = ("row" if best[i][j] == skip_row else
                          "take" if best[i][j] == take else "name")

    out: dict[int, str] = {}
    i, j = R, N
    while i > 0 and j > 0:
        step = back[i][j]
        if step == "row":
            i -= 1
        elif step == "take":
            out[i - 1] = names[j - 1]
            i -= 1
            j -= 1
        else:
            j -= 1
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


@dataclass(frozen=True)
class TruthCell:
    """One band of the page as the reader wrote it down.

    `text` is the name with the row's uncertainty marker taken off, so it can
    be compared with a reading; `certain` keeps what the marker said. A word
    the reader could not make out stays in the text as a bare `?` -- it is part
    of what the page says, and dropping it would silently turn a half-read row
    into a whole one.
    """
    n: int
    kind: str
    text: str
    certain: bool


def parse_cell(cell: str | None, n: int = 0) -> TruthCell:
    """The shorthand of docs/TASKS-honest-measurement.md T1, read.

    | written        | meant                                    |
    |----------------|------------------------------------------|
    | `José Fernandes` | read it, sure of it                    |
    | `?José Guberti`  | read it, not sure                      |
    | `?Lorenzo ?`     | sure of one word, the other unreadable |
    | `""`             | cannot read it, and that is the answer  |
    | `-`              | no row there                            |

    The shorthand is written by a person in a hurry, so the reading of it is
    forgiving of surrounding space and of nothing else.
    """
    raw = (cell or "").strip()
    if raw == "-":
        return TruthCell(n=n, kind=ABSENT, text="", certain=False)
    if not raw:
        return TruthCell(n=n, kind=UNREADABLE, text="", certain=False)
    if raw.startswith("?"):
        return TruthCell(n=n, kind=READ, text=raw[1:].strip(), certain=False)
    return TruthCell(n=n, kind=READ, text=raw, certain=True)


@dataclass(frozen=True)
class TruthPage:
    """One page somebody read, and who they were.

    `reader` is required and unforgiving, because the lesson that produced this
    format is that five of the six files this repository scored everything
    against were written by the assistant in wording that implied a person. A
    file that does not say who read it is not evidence.

    Two shapes load: this format, keyed by row number, and the old run of
    `names` down the page, which keeps its run because the alignment that puts
    it against the engine's cut lives in `pairs` and is not this loader's job.
    """
    pdf: str
    page: int
    reader: str
    hand: str = "unknown"
    read_on: str | None = None
    complete: bool = False
    rows: dict[int, TruthCell] = field(default_factory=dict)
    names: tuple[str, ...] = ()
    path: Path | None = None
    raw: dict = field(default_factory=dict)

    def cells(self) -> list[TruthCell]:
        return [self.rows[n] for n in sorted(self.rows)]

    def read(self) -> list[TruthCell]:
        """The rows carrying a name, certain or not."""
        return [c for c in self.cells() if c.kind == READ]

    def unreadable(self) -> list[TruthCell]:
        """The rows the reader could not read. Not gaps -- answers."""
        return [c for c in self.cells() if c.kind == UNREADABLE]

    def absent(self) -> list[TruthCell]:
        """The bands that are not rows."""
        return [c for c in self.cells() if c.kind == ABSENT]


def load_page(path: Path | str | dict) -> TruthPage:
    """Read one truth file. Refuses a file that does not say who read it."""
    if isinstance(path, dict):
        d, where = path, None
    else:
        where = Path(path)
        d = json.loads(where.read_text(encoding="utf-8"))

    reader = (d.get("reader") or "").strip()
    if not reader:
        raise ValueError(
            f"{where or 'truth page'}: no reader, so it is not evidence "
            "(docs/TASKS-honest-measurement.md T1)")

    rows = {}
    if isinstance(d.get("rows"), dict):
        for n, cell in d["rows"].items():
            rows[int(n)] = parse_cell(cell, n=int(n))
    names = tuple(d.get("names") or ())

    return TruthPage(
        pdf=d.get("pdf") or "",
        page=int(d.get("page") or 0),
        reader=reader,
        hand=(d.get("hand") or "unknown"),
        read_on=d.get("read_on"),
        complete=bool(d.get("complete")),
        rows=rows,
        names=names,
        path=where,
        raw=d,
    )


def load_pages(directory: Path | str = ROOT / "data" / "truth") -> list[TruthPage]:
    """Every truth file in a directory, in name order.

    One unlabelled file stops the lot on purpose: a half-labelled truth set is
    how the last one came to be quoted as if it were all hand-read.
    """
    return [load_page(f) for f in sorted(Path(directory).glob("*.json"))]
