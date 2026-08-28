# Desembarque

Transcription and verification of Brazilian ship passenger manifests — the arrival records
held by the [Arquivo Nacional](https://sian.an.gov.br/) for the ports of Santos and Rio de
Janeiro.

The records exist as scans and nothing more: no index, no search, no transcription. Finding
one passenger means reading hundreds of pages of degraded typescript and handwriting in
several languages. This turns them into structured, searchable records **without ever
asserting something the document does not say.**

## The rule everything follows

A transcription is only worth what it can be checked against. So every view that shows a
transcribed value shows the original scan beside it, and the two panes scroll together.
Unreadable fields are recorded as *ilegível* — never guessed. Repeated values written as
ditto marks are resolved and marked as resolved. Nothing is invented, because these records
are used as evidence in dual-citizenship claims where an invented name has consequences.

## Status

Working:

* **Corpus catalogue** — parses saved archive index pages into 7,679 dossiers with direct
  URLs, handling the archive's own cataloguing errors, cross-references and mangled encodings.
* **Downloader** — polite, resumable, and refuses to guess when a dossier will not resolve.
* **Review UI** — scan and transcription side by side, synchronised scrolling, in-document
  search scoped per column, inline editing, per-row verification.
* **Table structure without a model** — the grid of a ruled page is *measured* (deskew,
  rule detection, comb fitting), producing an empty table aligned to the scan that a person
  can fill in by hand.
* **Transcription**, with an open-weight recogniser run locally on CPU. The measured grid
  tells it where each row is, so it recognises the row bands directly instead of detecting
  text a second time. 168 dossiers — 865 pages — index in well under an hour on a
  laptop, with no failures.
* **Folder indexing** — point it at a folder and leave it. Progress with an estimate in
  hours, failures named rather than counted, and a run resumes from the cache having redone
  nothing. This is the flow the tool is for: nobody knows which dossier holds their
  ancestor, which is the whole problem.
* **Every dossier states its own voyage.** The ship, the port she sailed from, the
  arrival date and the headcount are printed on two forms — the interpreter's *PARTE*
  and the header above every passenger list — in seven companies' different wordings,
  and all of them are read. Nothing is completed from a partial reading: a day the
  recogniser made an `f` of leaves a month and a year and no date, `lista com H
  immigrantes` is not a headcount, and `vindos no paquete Inglez` is a flag rather than
  a ship.
* **Search across everything indexed** — matching is deliberately forgiving, because the
  names came out of a cursive hand through a recogniser. Someone typing "Guido Contadore"
  finds the row read as "Guudo Camtadore". Clicking a result opens the document at that row
  with the scan beside it, which is the only thing that makes a fuzzy match trustworthy.
  A ship's name, a shipping line or a year on its own lists who arrived, and any of them
  alongside a name reorders the thin margins a mangled surname competes in — without ever
  filtering, since a third of the corpus has no voyage indexed and hiding those dossiers is
  the failure this exists to prevent. Two thirds of the dossiers name the **shipping line**
  printed on the letterhead against a third that name a ship, so for most of them the line
  is the only crossing a person can give. A year can be a span — `1924-1926` is what
  somebody types who knows the decade and not the date.
* **Naming the crossing buys a second kind of matching.** Trigrams survive a letter dropped
  or doubled and collapse when the recogniser substitutes systematically: `EMILI MUESSO`
  read as `bmike Meesoo` shares not one trigram with what a person types, and is a 0.58
  match letter by letter. Comparing letters across 70,000 rows is neither affordable nor
  precise, but a searcher who names the ship, the line or the year has cut the pool to a few
  hundred rows — and there it is both. A hit found that way says so.
* **Export**, as a spreadsheet a registrar can read: the notation, the ship, where she
  sailed from and when she arrived, the page and line, the verbatim reading beside the
  split into surname and given name, and whether a person or an engine produced the row.

Honest about the limits:

* **Typescript is solved; cursive is four fifths findable, if you know the crossing.**
  Measured by searching each of 142 hand-read names exactly as a person would type it,
  against the whole index: **41 of 42 names on the typewritten pages** come back in the top
  ten either way, and on the cursive pages **49 of 100 typing only the name, 84 of 100 when
  the ship, the line or the year is named as well**. `Ponticelli Giovanni` is read as
  `Pouticelli Sooai` — wrong as a transcription, findable as a search. The recogniser is
  the ceiling and most of the 17 names still missing are below any matcher's floor: the
  row simply does not resemble the name, and four of them are rows the recogniser returned
  empty. A wider input, a bigger model, removing the printed
  rules and folding confusable letters were each measured and each was worse or no better,
  and pretrained handwriting models lost to the printed-text recogniser by a wide margin
  (CER 0.61 against 0.21, at 8 s a row). This needs training data of its own rather than
  somebody else's model.
* **A family list is mostly repetition marks, and they are resolved.** These lists write
  the surname once and a ditto under it for every relative: forty-eight people under nine
  surnames on one page. The surname is filled in from the row the mark points at and the
  reading is left exactly as it was, with the record saying how each was arrived at — a
  mark on the page, or the row's position under a family. Read as written, one of seven
  Martinezes was findable.
* **The table is measured from the page's own printing.** The column headings and the
  ordinal printed on every ruled row, rather than rules the scans have often lost — which
  is what used to put the name column over the *Procedencia* column, or over two thirds of
  the sheet. Ten pages chosen for how they differ are checked on every change
  (`data/golden.json`); all ten measure from the printing.
* **Some documents still yield nothing.** Most are not passenger lists at all but the
  interpreter's *PARTE* form, where no rows is the right answer — and that form names the
  ship, the port it sailed from and the arrival date, which are indexed from it. A page the
  geometry could not measure is a different matter: it is stored with nothing on it while
  the record stays current, so no future run looks at it again. `scripts/status.py` counts
  those pages and `scripts/retry_unknown.py` reads them again.
* **No engine installed is a supported state.** The application says so and writes nothing,
  rather than showing empty rows that could be mistaken for an empty page.

## Running it

Install once:

```sh
python3 -m venv .venv-ocr && .venv-ocr/bin/pip install -r requirements-ocr.txt
```

Start it, and open the address it prints:

```sh
.venv-ocr/bin/python scripts/serve.py --root data/scans
```

    http://127.0.0.1:8765          # --port to change it

The browser opens by itself unless you pass `--no-open`.

**Searching finds nothing until a folder has been indexed.** Indexing is what runs the
engine over every page and stores what it read; browsing a document does not do it. Press
*Indexar* in the sidebar, or:

```sh
curl -X POST 'http://127.0.0.1:8765/api/index?dir='
curl 'http://127.0.0.1:8765/api/index'        # progress, failures, estimate
```

It resumes: a document already read by the current engine is skipped, so stopping and
starting again costs nothing. When the engine improves, `SCHEMA` in `desembarque/search.py`
is raised and the next run re-reads everything — **until that happens the app shows what
was stored when the page was last read, not what the engine would say today.**

Without the engine venv the app still runs, browses, measures grids and accepts typing —
it just says plainly that no model is installed:

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/serve.py --root ~/Documents/manifestos
```

It binds `127.0.0.1` only and reads nothing outside the folder you point it at.

## Reading a mangled row

Handwriting recognition is at its ceiling for what runs on a CPU — five separate
measurements in `docs/PROGRESS.md` say so — so the review page offers two aids, both
off until asked for and both labelled as what they are:

* **`≈ Prováveis`** adds names this archive is known to carry to the menu of readings for
  a word, under `palpites do acervo — não lidos da página`. They are guesses: they are
  stored only if a person picks one, and then as that person's typing. `↑ primeiro` puts
  them above the engine's own readings. The list comes from this archive's typewritten
  pages and from rows people typed — `.venv/bin/python scripts/build_names.py` rebuilds
  it, and it should be rebuilt after a corpus refresh.
* **`? Conferir`** marks the rows worth a second look first, and says on hover which of
  three reasons applies: the recogniser decoded the line weakly, the surname was inferred
  from the row's position rather than read, or nothing in the reading resembles a name
  this archive carries. Measured against 139 hand-read rows of which 67 were badly read,
  those catch 81%, 46% and 4% of them respectively. `D` steps through the marked rows.
  About half the rows on a cursive page are marked, which is roughly how many are wrong.

## Finding somebody

Type a name. If it is a common one — Maria, José, Joaquim — it will be competing with
thousands of equally close readings, so say what else you know: the ship, or the year.
Measured against 142 hand-read names, that is the difference between 95 findable and 111.
Every search result carries the ship it sailed on and offers `só <navio>` to ask again
with it, and `↓ CSV` takes the whole list — notation, page and line — to the archive.

## Where it stands right now

```sh
.venv/bin/python scripts/status.py
```

Records and rows on disk, how many were written by an older engine, how much of the
corpus states its ship, year and port, how many surnames were inherited rather than read,
and whether an index run is going.

## Checking a change

Nothing here is trained. The recogniser's weights are fixed, so re-reading the archive
proves nothing about a change — it only refreshes what the app serves. A change is
checked against small fixed sets, in this order, and each one runs in seconds or
minutes:

```sh
.venv/bin/python -m pytest tests/ -q             # 535 library and pipeline tests, ~40 s
.venv/bin/python scripts/bench_search.py --matrix # can these people be found?      ~20 s
.venv-ocr/bin/python scripts/bench_pages.py      # ten pages, is the table measured right?  ~1 min
.venv-ocr/bin/python scripts/bench_rec.py        # three pages, how well are they read?     ~1 min
python3 scripts/smoke_prototype.py               # drives the real UI in Chromium and Firefox
```

`--matrix` asks the two questions a searcher asks — a name alone, and a name
with the crossing — at three cutoffs, on one load of the index: a scoring
change moves those six numbers in different directions, and one of them going
up is not the same as the change being good.

`data/golden.json` names the ten pages and why each is there — a typed list, a dense
cursive family list, a continuation page that prints no headings, faint pencil, a busy
letterhead. `data/truth/` holds the pages read by hand that the other two benches score
against. Re-reading the whole corpus is a data refresh; run it once, when a change has
settled, and leave it unattended.

## Documents

* [Design specification](docs/superpowers/specs/2026-07-23-desembarque-design.md) — the
  decisions, including the ones that were reversed and why.
* [Progress](docs/PROGRESS.md) — the running checkpoint: what was measured, and what the
  measurements do *not* show.
* [Hosting](docs/HOSTING.md) — what a hosted version would cost in privacy, and why local
  stays the default.
* [Licensing](LICENSING.md) — AGPL-3.0-or-later, and what that allows.

## Licence

[AGPL-3.0-or-later](LICENSE). See [LICENSING.md](LICENSING.md) for the reasoning and for
commercial licensing.
