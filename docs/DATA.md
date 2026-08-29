# Rebuilding `data/` on another machine

Nothing under `data/` is in git and nothing under it ever will be. It holds
scans of passenger lists and names read off them — real people, some of them
babies on those sheets and possibly alive, which makes it personal data under
the GDPR whatever its age. The repository on GitHub is a record of the work,
not a copy of the archive.

So this file is the recovery plan. If this machine dies, everything below can
be rebuilt from the archive and from these instructions. What cannot be rebuilt
is anybody's *typing* — corrections made at the review screen — and that is
said plainly where it applies.

## What lives there, and how each part comes back

| path | what it is | how to rebuild | lost if the disk dies? |
|---|---|---|---|
| `data/catalog.jsonl` | the corpus manifest: fundo, series, index, ship, URL | **in git** — the one exception, because it names ships and notations and no passenger | no |
| `data/scans/` | the dossier PDFs | `scripts/download.py`, from `catalog.jsonl`, 1.5 s apart | no, but it is a long download |
| `data/pagecache/` | page images extracted from those PDFs | rebuilt on demand by `page_geometry.page_image` | no |
| `data/transcriptions/` | one JSON per dossier: rows, geometry, voyage | re-index the folder through the app | **the corrections do** — see below |
| `data/names.json` | the dictionary, counted off what the archive has read | `scripts/build_names.py` over `data/transcriptions/` | no |
| `data/truth/*.json` | names read by hand off six pages, to score recognisers against | **by hand, off the scans** — a day's work with the pages open | yes |
| `data/truth_nationalities.json` | the nationality column of those pages, as read | `scripts/read_nationalities.py` | no |
| `data/language_names.json` | names the languages these ships carried use, by language | **by hand** — see below | yes |
| `data/column_vocab.json` | the words these printed forms use in each column | **by hand** — see below | yes |
| `data/refset.json` | one page per failure shape, by notation and page | **by hand**, and `docs/PROGRESS.md` names all seven shapes and why each is there | recoverable from PROGRESS |
| `data/bench-*.json`, `data/spike_*.json`, `data/golden.json` | measurements already taken | re-run the bench that wrote them | no |

## The three files written by hand, and what they claim

These are the ones worth copying to a second disk, because rewriting them is
judgement rather than compute. None of them contains a passenger: they are
claims about *languages* and about *printed forms*, never about this archive's
contents. That distinction is the whole reason they are separate files, and it
is repeated in each one's own `source` and `why` fields — read those first if
they ever have to be rewritten.

* **`data/language_names.json`** — 259 names these ships' languages use, in two
  bags (given, family) and again by language (`by_language`, for T11). Written
  without looking at the hand-read pages, deliberately: a list containing the
  answers would make `bench_menu.py` measure the file instead of the rules.
* **`data/column_vocab.json`** — the words these forms print in the
  nationality, civil-state, profession, port and class columns, plus the
  per-column snapping floors, each measured by `bench_columns.py --floor`.
* **`data/truth/*.json`** — the only one holding real names. Six pages read by
  eye. If it is gone, the benches that depend on it cannot run until somebody
  reads six pages again: `bench_menu.py`, `bench_check.py`, `bench_search.py
  --matrix`, `bench_columns.py`.

## What no rebuild recovers

Corrections typed at the review screen. They live only in
`data/transcriptions/*.json`, on the rows a person edited, and re-indexing the
folder produces the engine's readings again and not anybody's typing.
`batch.preserve_human_work` protects them from a re-read; it cannot protect
them from a dead disk. **A backup of `data/transcriptions/` is the only thing
in this project that is genuinely irreplaceable**, and it is also the file that
must never leave the machine.

## If the names ever did reach a public history

They did once: `data/truth/*.json` was tracked and pushed before 2026-08-29.
Untracking them stops the bleeding and does not remove them from earlier
commits — that needs the history rewritten and force-pushed, or the repository
made private, and both are decisions for Allan rather than for a tool.
