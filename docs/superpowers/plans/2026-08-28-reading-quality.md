# Reading quality: the plan for the next unattended session

Allan read BS.ENT.013947 and BS.ENT.013942 in the app on 2026-08-28 and wrote
down what he saw. This is that list, checked against what is actually stored on
disk, ordered by what it is worth, with the measurement that decides each one.

**The archive is not to be downloaded further until this is done.** Allan:
*"don't even dare think about downloading more until what we have has a decent
quality."* The 8.6% on disk is more than enough to work against, and every
number below is measured on it.

## What the stored rows actually say

BS.ENT.013947 p2, the first twenty-four rows as they sit in
`data/transcriptions`, against what is written on the scan:

| row | stored `name_raw` | stored `surname` | what the page says |
|---|---|---|---|
| 1 | `Yosé Fernandes` | `Yosé` | José Fernandes |
| 2 | `fore Gulerti` | `fore` | José Guberti |
| 3 | `Benito Mosso` | `Benito` | Benito Mosso |
| 4 | `MorvettoFianciico` | `Benito` (ditto) | Morvetto Francisco |
| 7 | `Ant? Alonmo foatz` | `Ant? Alonmo` | Antº Alonso Gonzalez |
| 9 | `Mania Danchez` | `Mania` | Maria Sanchez |
| 10 | `zabel` | `Mania` (ditto) | Izabel |
| 11 | `F'co alfieri` | `F'co` | F'cº Alfieri |
| 12 | `Maria` | `Maria` (ditto) | Maria |
| 19 | `"Maria` | `Pastre marco` (ditto) | Maria |
| 21–24 | `"angeta`, `"gose`, `"Elena`, `"Victoria` | `Eurini` (ditto) | Angela, José, Elena, Victoria |

Four separate faults are visible in that table, and only one of them is the
recogniser.

## 1. The name is split the wrong way round, and the mistake is inherited

`split_name` (`desembarque/engine_paddle.py:282`) documents its assumption:
these tables are written **surname first** (`ROCA REBULLIDA AMPARO`), so every
token but the last is the surname. BS.ENT.013947 is written **given name
first** — `Benito Mosso`, `Maria Sanchez`, `Antº Alonso Gonzalez` — so the
stored surname is *Benito*, *Mania*, *Ant? Alonmo*.

It does not stop at one row. The repetition mark inherits the surname down the
family block, so rows 4, 5 and 6 are all filed under *Benito* and rows 16–19
under *Pastre marco*. Allan read this as the dittos not being resolved; they
are resolved, and they are resolving to the given name. The search indexes it
that way too, which is why a family on a given-first page is unfindable by the
name the family actually has.

**The order is a fact about the page and can be measured from the page.** Three
signals, none of which needs a model: the token that *repeats* down a family
block is the surname (the dittos themselves say which end is which); the column
heading distinguishes `NOMES E COGNOMES` from the reverse; and the gazetteer
knows given names far better than surnames, because given names repeat across
the whole archive and surnames do not.

* Decide the order per page (fall back to per dossier, then to surname-first).
* Re-split every stored row from `name_raw`, which is untouched and lossless —
  no page needs re-reading for this.
* Acceptance: on the five truth pages, the surname stored for each hand-read
  row matches the hand-read surname; `bench_search.py --matrix` does not fall.

## 2. A person's correction freezes the whole document against improvement

Both documents Allan looked at are stored `source: manual`. `is_indexed`
(`desembarque/batch.py:21`) treats any record a person has touched as done
forever, and `preserve_human_work` keeps **all** of its rows, not the ones that
were typed. Six records are in that state, and every reading in them — 41 rows
in BS.ENT.013947 — is frozen at the quality of the day it was first read.

So the pages Allan is most likely to open are precisely the pages that never
get better. Every improvement below is invisible on them until this is fixed.

* Give each row its own provenance: a row a person typed carries the mark, the
  rest do not.
* `preserve_human_work` keeps the typed rows and lets the re-read replace the
  rest; a record is stale if any engine row is below the current schema.
* Acceptance: a record with one typed row and forty engine rows, re-read, keeps
  the typed row verbatim and updates the other forty. Tested at unit level —
  this is exactly the silent-loss shape the repository keeps finding, so it
  wants the test before the change.

## 3. Two values from an older pass are still on screen

BS.ENT.013942 shows `SIRVIENTA` as the profession of row 1 and `BELGA` as the
nationality of row 5, which is otherwise empty. Nothing in the pipeline writes
those fields today — the engine reads the name column and nothing else
(`engine_paddle.py:902`). They are fossils of an early pass, preserved by the
rule in §2. Corpus-wide: 27 nationalities, 23 professions, 26 origins and 22
ages sit on rows of six manual records.

* Clear them where they were not typed by a person, once §2 makes that
  distinguishable. Until then they are the engine's word in the user's eyes.

## 4. Nothing outside the name column is read at all

The grid is measured — `geo.normalized_cols()` gives every column rule and the
UI already has cells and labels for `numero, nome, nacionalidade, idade, sexo,
estado, profissao, procedencia, classe, observacoes`
(`scripts/serve.py:248`) — and then only the name column is handed to the
recogniser. Every other cell is null by construction.

This is the largest missing feature in the product, and two things make it
cheaper than it looks: the bands and the column edges are already measured, and
the columns other than the name are mostly short, closed vocabularies —
nationalities, professions, ports, a class of passage, a sex, an age in digits.
A closed vocabulary is worth far more than a general recogniser, because a
reading can be snapped to the nearest allowed value with a confidence that
means something.

* Read the remaining columns from the bands that already exist, one column at a
  time, cheapest first: age (digits), sex, class, then nationality, profession,
  port against gazetteers built from the archive's own typed pages.
* Never snap silently: store the reading and the snapped value, and mark the
  snap the way the ditto is marked.
* Acceptance: a new truth file for one typed page and one cursive page, scored
  per column, reported by `scripts/bench_columns.py`. Nothing ships without a
  first measurement, however bad.

## 5. The suggestion menu misses the names a person can see

Measured against the words Allan pointed at, over the 1,081-name dictionary:

| reading | wanted | offered today |
|---|---|---|
| `Yose`, `fose`, `Waria`, `Mania`, `Alonmo`, `Danchez` | JOSE, MARIA, ALONSO, SANCHEZ | yes |
| `fore` | JOSE | no — `FRE`, `FORD`, `JORGE` |
| `zabel` | IZABEL | no — not in the dictionary |
| `Gulerti`, `Pouticelli` | GUBERTI, PONTICELLI | no — not in the dictionary |
| `Sooai`, `foatz` | GIOVANNI, GONZALEZ | no — too far by edit distance |
| `Ant?`, `F'co` | ANTONIO, FRANCISCO | no — abbreviations are not expanded |

Five distinct causes, and each is cheap:

* **Confusable letters.** The hand's failures are systematic and few: `M`↔`W`
  (the third leg), `J`↔`f`↔`Y`, `I`↔`l`↔`z`, `n`↔`u`, `r`↔`i`, `c`↔`e`,
  `o`↔`a`, `S`↔`D`, `G`↔`f`. Generate the permutations of a reading under a
  confusion table and look each up in the dictionary, rather than trusting one
  edit-distance number. `Sooai` → `Sooni` → `Soani`… will not reach `Giovanni`;
  `foatz` → `Goatz` → `Goalz` will reach `Gonzalez` only with the length gate
  lifted, so lift it for permutation candidates.
* **Abbreviations.** `Antº`, `F'cº`, `Fco`, `Jozé`, `M.ª` are clerk shorthand
  with a fixed expansion table: Antonio, Francisco, Maria. The superscript
  comes back as `?`, `'` or nothing, so match on the stem plus a mark.
* **Merged words.** `MorvettoFianciico` is two names with the space lost.
  Split at an interior capital *as a suggestion* — it was measured and rejected
  as a silent rewrite of the reading, which is right; as an entry in the menu it
  costs nothing and is exactly what a person wants offered.
* **A dropped first letter.** `zabel` is `Izabel` minus the `I` the clerk tied
  into the `z`. Offer the dictionary names that this reading is a suffix or
  prefix of.
* **The dictionary is too small and too clean.** 1,081 names from typed pages
  seen twice or more. Guberti, Ponticelli, Alfieri and Morvetto are simply not
  in it. Widen it: names seen once, names from the catalogue's own index,
  names a person has typed in the app, and — since these are immigrant
  manifests — the given-name lists of the origin languages, which are small,
  free and open.
* Acceptance: a new bench, `scripts/bench_menu.py`, that asks *of the 142
  hand-read rows, in how many is the true name in the menu, at what rank*.
  That number does not exist today and everything above is guesswork without
  it. Build it first.

## 6. What the page says versus what the menu shows

* **The mark glued to the name.** Rows 19–24 store `"Maria`, `"angeta`. The
  record is right — that is what the page says — but the cell should show the
  name and the mark as what they are, the way an inherited surname is already
  shown as inherited.
* **Capitalisation.** `alfieri` should read *Alfieri*. Capitalise each part of a
  name, leaving the particles the archive actually uses lower case — `da`,
  `de`, `do`, `dos`, `del`, `della`, `di`, `van`, `von`, `vom`, `der`, `y`.
  Display only: the reading is not rewritten.
* **The dropdown does not close.** *Done, 2026-08-28.* Clicking the same word
  twice rebuilt the menu under the cursor instead of putting it away; it now
  toggles and changes nothing on the way out (`prototype/review.html`, and the
  browser self-test covers it). The static demo cannot exercise it — see below
  — so that coverage only runs against the served app.

## 6b. The demo shows columns the engine cannot fill

`prototype/sample_rows.json` is the one document the static demo carries, and
it is a **hand transcription**: nationality, age, sex, marital state,
profession, port, class and notes, all filled, with a confidence per field.
Every other document in the app shows names and nothing else, because names are
all the engine reads (§4). Somebody opening the demo and then a real dossier
sees a tool that stopped working.

Until §4 lands, the sample has to say what it is — a page typed by a person,
shown to demonstrate the shape of a finished record — in the interface and not
only in a file nobody opens. It is also why the browser self-test cannot cover
the readings menu: a hand transcription has no engine alternates, so the pill
that opens the menu never exists in the demo.

## 7. The language of the hand

The nationality column says *Italienne*, *Française*, and it changes from row
to row, so it is a per-row prior and not a per-page switch. Once §4 reads that
column, use it to order the suggestions: an Italian passenger's mangled given
name should be matched against Italian given names first. This is last on
purpose — it depends on §4, and the gain is a re-ranking of a menu that §5 has
to fill correctly first.

## Order of work

1. The dropdown toggle (§6) — ten minutes, already owed.
2. `bench_menu.py` and the per-column truth (§5, §4) — the instruments.
3. Per-row provenance (§2), then clear the fossils (§3).
4. The name order and re-split from `name_raw` (§1).
5. The suggestion work (§5), each cause measured separately.
6. Display: glued marks, capitalisation (§6).
7. The other columns (§4), cheapest first.
8. The language prior (§7).

Every step keeps the rule this repository is built on: the reading is never
silently rewritten, a guess is labelled a guess, and nothing ships without a
number beside it.
