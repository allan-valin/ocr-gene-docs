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
* **Search across everything indexed** — matching is deliberately forgiving, because the
  names came out of a cursive hand through a recogniser. Someone typing "Guido Contadore"
  finds the row read as "Guudo Camtadore". Clicking a result opens the document at that row
  with the scan beside it, which is the only thing that makes a fuzzy match trustworthy.

Honest about the limits:

* **Handwriting is read badly**, and is most of the archive. `GUIDO CONTADORE` comes back
  as `Guudo Camtadore` — wrong as a transcription, and findable by search only while the
  pool is small. Measured at three pool sizes, typed pages hold (26/26 in the top five at
  3,430 rows) and handwritten ones erode: 5 of 6 names ranked first at a thousand rows,
  4 of 6 at three thousand, with one lost to an unrelated word printed on another page.
  A recogniser that reads handwriting is the next thing this needs.
* **Some documents still yield nothing.** Of eighty-nine benchmarked pages, ten come back
  without a row; on inspection most are not passenger lists at all but the interpreter's
  *PARTE* form, where no rows is the right answer — and that form names the ship, the port
  it sailed from and the arrival date, none of which is indexed yet. The five that *were*
  lists have been recovered: their rules print too faintly for the table's extent to be
  measured from them, so a page of thirty-seven passengers came back empty. Coverage across
  the benchmark went from 0.457 to 0.497 with no page regressing.
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

Tests:

```sh
.venv/bin/python -m pytest tests/ -q      # 122 library and pipeline tests
python3 scripts/smoke_prototype.py        # drives the real UI in Chromium and Firefox
```

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
