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

## 1. The name is split into surname and given name, and that is not ours to decide

`split_name` (`desembarque/engine_paddle.py:282`) takes every token but the
last as the surname, on the stated assumption that these tables are written
surname first. Allan has said before and said again that the order cannot be
assumed: **one document carries both** — last-first as written on leaving
Germany, first-last as written on arrival in Brazil — and which is which is the
reader's call, not the tool's. Detecting the order per page, which an earlier
draft of this plan proposed, is the same mistake with more machinery.

What the split produces today on BS.ENT.013947: surname *Yosé* for `Yosé
Fernandes`, *Benito* for `Benito Mosso`, *Mania* for `Mania Danchez`, *Ant?
Alonmo* for `Ant? Alonmo foatz`. Those are given names, and the repetition mark
then carries them down the family block — four people filed under *Benito*,
four under *Pastre marco* — which is what "the dittos were not identified"
turned out to be.

* **Stop splitting.** The row's name is `name_raw`, as written. Nothing
  downstream should need a field that claims to know which part is the family
  name: search already indexes the whole reading and can index each token, the
  export can carry the name as read, and the UI can show one name cell.
* **A person may split it** if they want to, per row, and that is stored as
  their typing — the one place the distinction is knowledge rather than a guess.
* The repetition mark is different and stays: the mark is the clerk saying
  *the same as above*, so what it stands for is evidence off the page, not an
  inference about name order. It should inherit **the tokens actually written
  above it**, marked inherited as they are now, rather than a `surname` field
  computed by the assumption above.
* Acceptance: no field in a stored row asserts surname or given unless a person
  typed it; the five truth pages' rows read back exactly as written;
  `bench_search.py --matrix` does not fall.

## 2. A person's correction freezes the whole document against improvement

Both documents Allan looked at are stored `source: manual`. Precisely, because
the mechanism matters: such a record **is** read again when the schema is
raised — and then `preserve_human_work` (`desembarque/batch.py:65`) throws the
fresh rows away and puts the stored ones back, because the record carries a
mark saying a person was here. The mark is on the record, not on the rows, so
one corrected row protects forty uncorrected ones.

The rule was written to stop a re-read destroying somebody's typing, which is
right; the cost is that six records — 41 rows in BS.ENT.013947 among them —
are held at the quality of the day they were first read. Those are the pages
Allan opens, because they are the ones he has been correcting. Every
improvement in this plan is invisible on exactly those pages until this is
fixed, which is why it comes before the improvements.

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

## 5. The menu shows the engine's two readings and nothing else

**The suggestions are off until somebody finds the button.**
`prototype/review.html:1255` sets `GUESSES=false`, so the menu that opens on a
word lists only what the recogniser decoded — `fore`, `fose` — and the archive's
names are fetched only after `≈ Prováveis` is pressed. Allan clicked `Yosé` and
`fore` and was offered nothing useful, which is exactly right and is not what an
earlier draft of this plan claimed: that draft tested `Names.suggest()` as a
function and reported the result as though it were on screen.

*Done, 2026-08-28*: the archive's names are offered without hunting for a
switch, **every word opens its readings** rather than only the ones the engine
read two ways — `Yosé` had nothing to click at all, so no guess could ever
reach it — and the marks on the rows have a legend. What is left is the quality
of the candidates, which is what the measurement below is about.

And a limit worth stating before any of it: **the dictionary will always lack
names.** Allan: *"the dictionary will lack names because the way some are read,
even by a human, will not look like the correct version because of handwriting
wildly varying between humans."* A candidate list built by matching against
names the archive has already read cannot reach a name nobody has read
correctly yet — Guberti, Ponticelli, Alfieri, Morvetto. The dictionary is one
source of candidates, never the gate. What the ink could support is the
question; the archive's names are evidence about which of those readings is
plausible, and the person decides.

Measured against the words Allan pointed at, over the 1,081-name dictionary,
*with the toggle on*:

| reading | wanted | offered with `≈ Prováveis` on |
|---|---|---|
| `Yose`, `fose`, `Waria`, `Mania`, `Alonmo`, `Danchez` | JOSE, MARIA, ALONSO, SANCHEZ | yes, but only by edit distance, which is luck rather than a model |
| `fore` | JOSE | no — `FRE`, `FORD`, `JORGE` |
| `zabel` | IZABEL | no — not in the dictionary |
| `Gulerti`, `Pouticelli` | GUBERTI, PONTICELLI | no — not in the dictionary |
| `Sooai`, `foatz` | GIOVANNI, GONZALEZ | no — too far by edit distance |
| `Ant?`, `F'co` | ANTONIO, FRANCISCO | no — abbreviations are not expanded |

None of that was on screen for any of them.

Six things to do, and only the last is about the dictionary.

### The candidates come from the strokes, not from the word

Allan: *"look at the individual characters because they get confused, like
writing `num` could be read as `uuu nnn mmm unm mun` because they look alike."*
That is the model this has to be built on, and it is not a spelling-distance
model.

In this hand a run of **minims** — the plain vertical strokes that make `i`,
`u`, `n`, `m`, `r`, `w` — carries a reliable *number of strokes* and an
unreliable division into letters. `num` is seven strokes; so is `uuum`, `mnn`,
`unm`, `mun`. The recogniser picks one division, prints it with confidence,
and everything downstream treats that division as what the page says. The
strokes are the evidence; the letters are already an interpretation.

So the generator is: read a word as a stroke skeleton, enumerate the divisions
the skeleton supports, and offer those. Concretely:

* **Minim runs**, re-cut every way the stroke count allows: `i`,`r` one stroke,
  `u`,`n` two, `m`,`w` three. This one rule generates `Mania`→`Maria`,
  `Alonmo`→`Alonso` is *not* minim (see below), `Pouticelli`→`Ponticelli`,
  `borniingo`→`Domingo`.
* **Ascenders and descenders**, which are one stroke plus a direction: `f`↔`J`
  ↔`Y`↔`T`, `l`↔`b`↔`k`↔`h`, `g`↔`y`↔`j`↔`q`↔`z`. This is `Yosé`→`José` and
  `fore`→`Jose`, the two Allan pointed at first.
* **Round letters**: `c`↔`e`↔`o`↔`a`, `s`↔`r` (the long `s`), `S`↔`D`↔`G`.
* **A stroke lost at the start or the end**: `zabel`→`Izabel`.
* **Marks the recogniser has no glyph for**: the superscript of `Antº` and
  `F'cº` comes back as `?`, `'` or nothing.
* **A space that was there**: `MorvettoFianciico` is two words.

Ranked by how few stroke-level changes the candidate needs, then by whether
anything — the archive, the origin-language given-name lists, a person's own
typing — has ever seen that spelling. **A candidate that spells nothing known
is still shown**, because the archive has not read every name correctly yet;
that is the whole problem, and it is why the dictionary can never be the gate.

* Acceptance: `scripts/bench_menu.py` over the 142 hand-read rows — in how many
  is the true name among the candidates, and at what rank. Then each rule
  measured on its own, the way the search changes were: a rule that adds noise
  without adding names comes out again.

### And the marking is asking the wrong question

`doubtful` (`desembarque/gazetteer.py:115`) flags a row only when **nothing**
in it resembles a name the archive carries. `YOSE` resembles `JOSE`, so the row
passes as fine — and `fore Gulerti` likewise. The inference is backwards: a
reading that is *near* a known name but is not one is the strongest evidence of
a misread that this tool has. Not a name and not near one is a rare name; not a
name but one stroke from one is a mistake.

* Flag *near a name, not a name*, separately from *unknown to this archive*,
  and say which in the legend.
* Re-run the existing measurement — 139 hand-read rows of which 67 are badly
  read, where the three current reasons catch 81%, 46% and 4% — and keep the
  new reason only if it catches misreads the others miss.

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

1. ~~The dropdown toggle (§6)~~ — done 2026-08-28.
2. **Show the candidates without a toggle** (§5). The feature exists and is
   switched off; nothing else in this plan is visible to a reader until it is on.
3. `bench_menu.py` and the per-column truth (§5, §4) — the instruments. Neither
   number exists today.
4. Per-row provenance (§2), then clear the fossils (§3). Until this lands,
   nothing below shows up on the pages Allan actually reads.
5. Stop asserting surname and given name; inherit the mark's tokens literally
   (§1).
6. The candidate work (§5), each cause measured separately: confusable letters,
   abbreviations, merged words, dropped initials, candidates the dictionary
   cannot contain, then the dictionary itself.
7. Display: glued marks, capitalisation (§6), and the demo's honesty (§6b).
8. The other columns (§4), cheapest first.
9. The language prior (§7), which depends on §4.

Almost none of this is recognition work. The recogniser is at its ceiling and
five separate measurements say so; what is broken above it is a name split the
tool should never have made, a freeze that keeps corrections and improvements
apart, a menu that is switched off, and eight columns nobody reads.

Every step keeps the rule this repository is built on: the reading is never
silently rewritten, a guess is labelled a guess, and nothing ships without a
number beside it.
