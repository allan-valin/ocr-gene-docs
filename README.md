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

Not working yet:

* **Automatic transcription.** No engine is installed. The application says so and writes
  nothing, rather than showing empty rows that could be mistaken for an empty page.

## Running it

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/serve.py            # browse ./data/scans
.venv/bin/python scripts/serve.py --root ~/Documents/manifestos
```

Optional transcription engine (large, and the app works without it):

```sh
python3 -m venv .venv-ocr && .venv-ocr/bin/pip install -r requirements-ocr.txt
```

It binds `127.0.0.1` only and reads nothing outside the folder you point it at.

Tests:

```sh
.venv/bin/python -m pytest tests/ -q      # library and pipeline
python3 scripts/smoke_prototype.py        # drives the real UI in Chromium and Firefox
```

## Documents

* [Design specification](docs/superpowers/specs/2026-07-23-desembarque-design.md) — the
  decisions, including the ones that were reversed and why.
* [Licensing](LICENSING.md) — AGPL-3.0-or-later, and what that allows.

## Licence

[AGPL-3.0-or-later](LICENSE). See [LICENSING.md](LICENSING.md) for the reasoning and for
commercial licensing.
