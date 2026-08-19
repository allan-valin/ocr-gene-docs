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
  text a second time: about 4 s a page, and 57 dossiers indexed in 17 minutes.
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
  as `Guudo Camtadore` — wrong as a transcription, still findable by search. On a hand-read
  page, five of six names ranked first in a pool of a thousand rows; on a typed page,
  23 of 26. Those margins narrow as the pool grows, and that is the number to watch.
* **No engine installed is a supported state.** The application says so and writes nothing,
  rather than showing empty rows that could be mistaken for an empty page.

## Running it

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/serve.py            # browse ./data/scans
.venv/bin/python scripts/serve.py --root ~/Documents/manifestos
```

Optional transcription engine (large, and the app works without it):

```sh
python3 -m venv .venv-ocr && .venv-ocr/bin/pip install -r requirements-ocr.txt
.venv-ocr/bin/python scripts/serve.py        # same app, with transcription available
```

The engine venv runs the whole application, so it is the one to use for indexing a
folder. Without it the app still browses, measures grids and accepts typing — it just
says plainly that no model is installed.

It binds `127.0.0.1` only and reads nothing outside the folder you point it at.

Tests:

```sh
.venv/bin/python -m pytest tests/ -q      # 115 library and pipeline tests
python3 scripts/smoke_prototype.py        # 38 assertions, in Chromium and Firefox
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
