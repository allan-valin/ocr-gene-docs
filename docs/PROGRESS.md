# Progress

Running checkpoint. Newest first. The design record is
[the spec](superpowers/specs/2026-07-23-desembarque-design.md); this file is state and
next actions.

## 2026-08-20 — day session (Allan working)

### The browser test had been green against a two-day-old page  (30e1726)

`make_prototype.py` imports the package from inside its functions and the
repository root was never on `sys.path`, so the build died with a
`ModuleNotFoundError` the moment it reached a PDF — after argument parsing, in
the middle of real work. The previous `prototype/build/index.html` stayed where
it was, and the smoke run went on driving it: **35 assertions, all green,
against a page older than the code**. Behind it were nine genuine failures.

Fixed in two places, because they are two problems. Scripts that import the
package now put the root on the path. And the smoke test refuses to run when the
build is older than `review.html` — a stale artifact has to be an error, since
everything downstream believes it.

The assertions that need the API are now gated on the page being served: from
disk there is nothing to answer them, and counting them as failures buried the
ones that meant something. **44/44 from disk, 56/56 served, in Chromium and
Firefox.**

### A document can leave the tool as a spreadsheet  (3b4daa6)

`/api/export` returns one dossier's rows as CSV, offered as a download named for
its notation. Every row carries the notation, the page and line, the verbatim
reading beside the split into surname and given name, and **who produced it** —
a person or which engine. The recogniser's number is exported as `score_motor`,
not `precisao`: it is a decode score that stays high on confident nonsense.
Blank rows are kept, because a blank line on these forms is a fact about the
page and dropping it renumbers everyone below it.

Editing is now a mode rather than the default. Every cell was editable at all
times, including fields the engine never attempted, so the page invited typing
into places that had not been read. On a record meant as evidence, a stray
keystroke is worse than one more click.

### The tables whose rules print too faintly to be measured  (f0eed9f)

`BR_..._16456` page 2 is a clean list of **thirty-seven passengers** and geometry
returned nothing at all. The table's vertical extent is taken from its rules, and
on this sheet they printed so faintly that the longest unbroken run of ink at
each one is the blank paper below the last passenger. The extent came out as the
bottom six per cent of the page; no comb fits inside that; the run reported
success.

The comb fitted to the *writing* was already computed as a challenger, but it
could only win by overlapping the extent the rules reported — and that extent is
exactly what is wrong here. When there is no first comb at all there is nothing
to protect and the veto comes from the same broken measurement, so the challenger
is now judged on its own: it must start on the page, cover at least eight rows,
and account for at least half the writing detected. A comb explaining a third of
the writing is a letterhead as often as it is a list.

| | before | after |
|---|---|---|
| pages with no row at all | 15 of 89 | 10 of 89 |
| mean coverage | 0.457 | 0.497 |
| regressions | — | **0** |

The five recovered pages went from zero coverage to 0.50–0.79. The choice
between the two combs is now `choose_comb`, a function tested on the numbers real
pages produce, which is how its thresholds were set.

### The dossiers now state their own voyage  (bc354fe … 83dcdd1)

Every dossier says, in print, which ship it is about, where she sailed from and
when she arrived. None of it was in the index. Search had only the name to go
on, and the names come out of a cursive hand through a recogniser: the measured
winning margins are thin — some correct hits score 0.13 — and thin margins are
what a seventy-thousand-row pool destroys. A person looking for an ancestor
knows the ship, or the year, or the port far more reliably than they know how a
clerk spelled a surname.

Two forms carry it. The interpreter's **PARTE**, which is what most of the
"blank" pages turned out to be, and the printed **header above every passenger
list**. Seven different companies' printings appear in the corpus and no two are
worded alike — `Lista de entrada de passageiros no paquete`, `Relação dos
passageiros que desembarcaram neste porto vindo no vapor`, `Porto de`.

The division of trust is the design: the labels are printed and read well, the
values beside them are handwritten and do not, so the labels are matched and the
value is reported verbatim. The month is the one exception — it is one of a
couple of dozen known words, in Portuguese *and* French, since a Compagnie de
Navigation Sud Atlantique list is dated `Octobre`.

Nothing is completed from a partial reading:

| read | recorded |
|---|---|
| `entrado em 10 deDesembro de 1924` | `1924-12-10` |
| `entrado em f de Novemlro de 1923` | November 1923, no date — the day is a stroke |
| `Entregou 1 lista com H immigrantes` | no headcount — `H` is not a number |
| `Santos, / de / de 19` | no date at all — the clerk left it blank |
| `vindos no paquete Inglez` | a flag, not a ship |
| `2104`, `Facional`, `ri  ad` | refused — a page number and two pieces of letterhead |

Search uses it without ever filtering on it. A year is taken out of the query
rather than compared against surnames; which word is a ship is decided against
the index rather than guessed. It **reorders and does not decide**: an
exactly-spelled name stays first even when the year points elsewhere, because
the user may be wrong about the year. Most of the corpus has no voyage indexed
yet and a filter would make those dossiers unfindable, which is the failure this
tool exists to prevent.

### Two silent-loss bugs found on the way  (64204b5, 30e1726)

**A re-read would have destroyed every correction anybody had typed.** Saving a
corrected row writes the whole record, engine stamp included, so the next schema
bump marked it stale, the run read the document again, and storing is a
whole-record write. The schema stamp had just gone up. Both paths that store a
reading now keep the person's rows.

**The browser test had been green against a two-day-old page.** The prototype
build died on an import error and left the previous `index.html` in place; the
smoke run went on driving it and reporting 35 passing assertions. Behind it were
nine real failures. The build now puts the repository root on `sys.path`, and
the smoke test refuses to run against a build older than its source.

### Indexing the corpus had to be made possible

The first full run reported **twenty-two hours remaining**. The cost is not
recognition, it is detection over the whole sheet — these scans are 5300×3800,
and reading one whole page measured 74 s.

| | |
|---|---|
| full page, 5287 px | 74.3 s |
| 2400 px | 29.9 s |
| **2000 px (now)** | ~22 s |
| 1400 px | 14.3 s — loses the quotation marks that tell a ship from its flag |

Three changes together: read a whole page from a 2000 px copy; read only the
strip *above* the table on a page that has a grid, since that is where the
header is; and stop reading a dossier as prose once the notation and the voyage
are both in hand — page one is the archive's cover card and states no voyage at
all.

Scaling turned out to read *better*, not worse: the detector groups the lines
the way the form is printed, so the ship and its nationality come back on the
one line they share instead of three.

### Where this leaves the corpus, and what is running

A full re-index is running as this is written — 660 dossiers, four workers,
around 35-40 s each. It resumes from the content-hash cache, so it can be
stopped and restarted at will and will skip whatever is already current:

```sh
.venv-ocr/bin/python scripts/serve.py --root data/scans     # then, in another shell
curl -X POST 'http://127.0.0.1:8799/api/index?dir='         # start / resume
curl      'http://127.0.0.1:8799/api/index'                 # progress
curl -X POST 'http://127.0.0.1:8799/api/index/stop'         # stop; workers finish the page
.venv/bin/python scripts/voyages.py                         # what the corpus now knows
```

The schema stamp moved four times today (5 → 8) as the engine learned to read
these forms, and each move makes every earlier record stale by design. **A
person's corrections now survive that**, which they would not have this morning.

### Next, in order

1. **The ship's name is the weak field.** The letterhead is printed and comes
   back on nearly every list; the vessel's name beside `no paquete ___` is
   handwritten and mostly does not. Reading both forms of a dossier together is
   today's answer; the real one is to pair a printed label with the handwriting
   *beside* it using the detector's boxes, rather than by the order it reports
   its fragments. That is the one structural improvement left in this feature.
2. **Confidence is not calibrated** — `conf.surname` is Paddle's raw decode
   score, shown as if it meant trustworthiness. Allan saw a green label on
   `Brges. iuig`. Hide it or calibrate it against hand-read truth.
3. **Rows that are not passengers** — the `/36` line and the tally block are
   read as people. Same class of problem as the column heading flag.
4. **Ditto inheritance**, stored beside the verbatim text rather than replacing
   it. 013990 is the fixture.
5. **`data/transcriptions/` will outgrow memory.** Search loads every row; at
   7,000 dossiers that is roughly a million. It wants SQLite before then.
6. Handwriting recognition, still the ceiling, and still the thing pretrained
   models do not solve.

### Questions that are Allan's to answer

* **Is the ship's name worth the box work?** It is the field that would let
  somebody search "Valdivia 1924" and get one dossier instead of three thousand
  rows, and it is the field the recogniser loses most often.
* The corpus re-index takes hours on this machine. **Is unattended overnight
  indexing the intended flow**, or should the tool do a fast pass first — the
  forms only, no row recognition — so that a folder becomes searchable by ship
  and year within minutes and by name later?
* `port` and `origin` are exported and shown exactly as read: `Nio Sumalos` for
  Rio de Janeiro, `Beuenes crures` for Buenos Aires. Correcting them against a
  gazetteer would be a guess the scan cannot check. **Is verbatim right here**,
  or should a canonical name sit beside the reading?

### What the remaining blank pages actually are

Most of the ten are **not passenger lists**. They are the interpreter's *PARTE*
form, and no rows is the right answer for them:

> do Intérprete *Matheus H. Ferreira* / que visitou o paquete *Francez*
> "*Valdivia*" / procedente de *B. Aires e escalas* / entrado em *10* de
> *Dezembro* de 19*24* / Entregou *1* lista com *12* immigrantes

Ship, nationality, port of origin, arrival date, headcount — printed labels
around handwritten values, on a page currently thrown away. The same voyage is
printed again in the header of every passenger list. **None of it is indexed**,
which is why a search has nothing but the name to go on. That is the next piece
of work, and it is the one that answers "search ranking should use more than the
name".

## 2026-08-19 — night session (Allan away)

Four fixes, all committed and pushed. The corpus is downloading toward ~570
dossiers; ~525 on disk at the time of writing.

### The comb now finds the rows  (875087e, 43049eb)

BS_ENT_013990 p2 lists eighteen passengers. The engine read three. It now reads
**all eighteen**, in the right rows:

| row | engine | on the page |
|---|---|---|
| 1 | `Nayomgo Cassaudii` | Raymundo Cassaudi |
| 2 | `Alfiedo J. ravares` | Alfredo J. Tavares |
| 3 | `Jain E. Gil` | Jaim C. Gil |
| 8 | `Sctomio as dr Auida` | Victorio Dias de Almeida |
| 18 | `Eig Burges.` | Luiz Borges |

Wrong as transcription, findable as search, and — the point — *present at all*.
Rows 23-28 are the tally block at the foot, kept separate from the passengers.

Three things were wrong, each hiding the next.

**The table's top came from rule continuity.** `rule_extent` takes the longest
*unbroken* vertical run of ink at each column rule. Writing crosses the rules,
so where people are listed a rule survives only as short segments — 17 to 21 per
column here. The longest run is therefore always the emptiest stretch: the top
came out at 0.559 of the page and the comb was fitted to blank ruled paper below
the list.

**The line detector could not see the rows.** At the 70th percentile it reported
ten lines for about fifteen written rows. That hand is light. No choice of
bounds could have found rows the detector never reported.

**Rule support selects emptiness.** The obvious guard — "is this band inside the
table? do the column rules run through it?" — is backwards. Support is *highest*
where nobody has written. On 013990 it measures 0.00-0.09 across the whole
passenger block and 0.64-0.82 on the blank paper below. As a quality gate it cut
the comb back to the empty strip: the same failure, one level up.

What holds now: the old fit is computed unchanged and stays the default. A wider
fit is only *considered*, looks harder (55th percentile), and must beat the
default by a margin on how much writing it covers, be at least half writing
itself, and overlap the table the rules did find — so it extends that table
rather than relocating to another block of ruled lines, which is what it did on
BS_ENT_015953 before the constraint.

Measured on 89 pages with `scripts/bench_geometry.py`, which scores what share of
the name column's ink falls inside a band:

| attempt | improved | regressed | mean coverage |
|---|---|---|---|
| refit pitch over whole page | 17 | 54 | 0.379 → 0.284 |
| score by lines per band | 16 | 39 | 0.379 → 0.316 |
| score by count, with floor | 18 | 15 | 0.379 → 0.376 |
| + margin, floor on challenger only | 12 | 1 | 0.379 → 0.402 |
| + overlap constraint (875087e) | 7 | 0 | 0.379 → 0.393 |
| + looser detection, unified scoring (43049eb) | **21** | **0** | **0.379 → 0.457** |

`BR_RJANRIO_OL_0_RPV_PRJ_15992` — recorded in the last checkpoint as a layout
geometry could not read at all, zero rows — now comes back at 0.285.

The known limit is in its test: a letterhead butted directly against the first
row *and* sharing the ruling's pitch is not separable by anything measured here.
Real forms leave a gap; 013990's comb starts below its header block.

### Every cover card was being lost  (22ce7b8)

167 of 168 documents failed page 1 with `NotImplementedError: (Unimplemented)
ConvertPirAttribute2RuntimeAttribute`, and the run reported success. oneDNN
refuses the detection pipeline — which builds fine and dies on use, so the retry
has to wrap the call, not the construction. That path produces the cover text
`identify()` reads, which is why every record fell back to filename identity.
oneDNN is kept for the row recogniser, which is happy with it.

### Corpus properties from Allan, to design around

* **Ditto marks are real** — confirmed on 013990's Nação column. My sample
  surfaced none, which was a sampling limit, not evidence of absence.
* **Blank means "unknown"**, not "the engine failed". This is why the density
  floor is never applied to the default comb: a correct comb over thirty rows
  may hold only fifteen detected lines.
* **Do not assume fixed geometry** — scans are misaligned and faulty. Every
  bound above is derived from the page in front of it.
* White-on-black pages are first or last and carry nothing needed.

### Next, in order

1. **Re-index and re-measure.** Every number about blank rows predates the comb
   fix and means little now.
2. **Ditto inheritance**, stored beside the verbatim text rather than replacing
   it. 013990 is the fixture.
3. **Confidence is not calibrated** — `conf.surname` is Paddle's raw decode
   score, shown as if it meant trustworthiness. Allan saw a green label on
   `Brges. iuig`. Hide it or calibrate it against hand-read truth.
4. **Rows that are not passengers** — the `/36` line and the tally block are
   read as people. Same class of problem as the column heading flag.
5. Handwriting recognition, still the ceiling, and still the thing pretrained
   models do not solve (see the daytime entry).

## 2026-08-19 — evening session

Three fixes committed and one large defect found and not yet fixed. The corpus
was re-indexed once (167 done, 1 skipped, 0 failed, 44.7 min).

### Pretrained handwriting models are not the answer

Allan's question was reasonable: handwriting recognition is the first example in
every ML course, so why build anything? Measured on the cursive Gelria page,
against the recogniser that ships (CER 0.205, ~0.06 s/row):

| model | CER | s/row |
|---|---|---|
| PP-OCRv6_medium_rec (ships) | **0.205** | **0.06** |
| microsoft/trocr-base-handwritten | 0.785 | 7.74 |
| microsoft/trocr-large-handwritten | 0.607 | 8.09 |

Three times worse and ~130x slower. The failure mode is the whole argument:
TrOCR read `EMMA CONTADORE` as `VERSION Constadvice`, `EMILI MUESSO` as
`Israeli Meteor`, `A. VIEIRA MIRANDA` as `A.P. Disufflements`. Its decoder is a
RoBERTa language model, and a language prior is *harmful* when every target is a
proper noun it has never seen: it reads the strokes, then corrects them into
English words. The recogniser that ships is CTC with no language model, which is
exactly why it wins here. Allan: "using a language model is asking for errors."
Scale is not the issue — the large model fails the same way. `scripts/spike_htr.py`.

### The ink mask was destroying faint pages  (fixed, 8b56f65)

`page_image` prefers the PDF's embedded MRC mask because geometry needs it
(nine column rules against three from a render). The mask is one bit deep, so
faint strokes fall below its threshold and are gone before recognition runs. On
BS_ENT_015741 p2 the recogniser read 7 of 39 bands from the mask and 26 from a
grayscale render — an entire family (BLOCH ALEXANDRE, HENRIETTE, LINE,
JACQUELINE, MADELON, FRANÇOISE) was missing from the index and is legible to the
eye.

Not a blanket win, which is why it is a fallback: over ten pages the mask read
63.3% of bands and the render 68.2% — seven pages unchanged, one gained
nineteen rows, and BS_ENT_017053 *lost* five. A page is read from the mask; only
if that comes back under half-read is it read again from a render, and the
second reading is kept only if it found more names. Corpus-wide the re-index
moved rows-with-text from 60.0% to **61.7%**, well below the sample's +4.9
points because the sample was chosen partly *because* those pages failed.

### Re-indexing could not reach the corpus  (fixed, 258a69a)

Any record an engine had written counted as finished, so no engine improvement
could ever be applied: a re-run skipped all 168 documents and reported success.
`is_indexed` now requires the current schema stamp for engine-written records,
still never redoes a record a person typed, and still refuses to treat an empty
manual note as an index. SCHEMA is 2.

### Rows are cut along the paper now  (fixed, d67b8d4)

Allan, reading ITAPEMA 013990: the leg of the `y` in row 1 "Raymundo Cassaudi"
lands inside row 2 "Alfredo C. Tavares", between the `l` and the `f`. A straight
cut corrupts both rows, and `refine()` made it worse, since trimming to ink
*expands* a crop toward whatever intruded. Boundaries are now found as paths of
least ink across the column (`desembarque/rowcut.py`), shared between
neighbours so a stroke lands on exactly one side. The same seam does columns —
Allan reports names bleeding sideways past the rule too. The limit is tested,
not hidden: a tail reaching further than the seam's margin needs the stroke
traced, which is a different technique.

Measured on 013990 it changed eight rows and improved none of them, because
that page fails for a much larger reason (below).

### THE BIG ONE, NOT FIXED: the row comb fits the wrong half of the page

BS_ENT_013990 p2 has **18 numbered passengers**. The engine produced text for 9
rows, and the three real names among them were passengers 16, 17 and 18. Rows
1–15 were never looked at, and what looked like mangled names (`Crallleeros NM`,
`1rEreeeteei vr 2`) were the tally block at the foot of the page.

`detect_rules` bounds the table with `rule_extent`, the longest *continuous*
vertical run of ink per column, tolerating gaps of 40 px. Where passengers are
written, the handwriting shatters each rule into 17–21 short runs, none longer
than 5% of the page. Where the table is empty the rules print cleanly. So the
longest run is always the blank region, the table top comes out at **0.559** of
the page, and the comb fits the empty ruled area below the list.

This is very likely a large share of the corpus-wide 38.3% blank rows — not
clerks skipping lines, not ditto marks, not faint ink, but geometry measuring
the wrong half of the page.

Raising the gap tolerance is not the fix, measured:

| page | gap 40 | gap 80 | gap 150 | gap 250 |
|---|---|---|---|---|
| 013990 (broken) | 0.559 | 0.559 | 0.559 | **0.083** |
| 016739 (working) | 0.208 | 0.194 | 0.135 | **0.030** |
| 015106 (working) | 0.257 | 0.226 | 0.207 | **0.065** |

013990 only recovers at 250, which overshoots into the letterhead on the pages
that currently work. The table's top has to stop being derived from rule
continuity alone: find text lines across the full page between the outer column
rules, fit the pitch to those, and use the rules for the bottom bound only. The
risk is the failure already recorded in the code — letterhead and signature
lines giving "37 rows for a 26-row table" — so the pitch fit has to reject
outliers, and it needs testing across many pages.

### Also found, not fixed

* **`enable_mkldnn=True` crashes the full-page OCR path.** 167 of 168 documents
  (99%) failed page 1 with `NotImplementedError: (Unimplemented)
  ConvertPirAttribute2RuntimeAttribute`. With mkldnn off the same page reads
  fine. That path produces the cover text `identify()` uses, which is why every
  record fell back to filename identity. One-line fix, high value, untested yet.
* **Confidence is not calibrated.** `conf.surname` is Paddle's raw decode score,
  shown in the UI as if it meant trustworthiness; Allan saw a green label on
  `Brges. iuig`. For an evidence tool it should be hidden or calibrated against
  hand-read truth.
* **Ditto marks are real**, confirmed by Allan on 013990's Nação column. My
  168-dossier sample surfaced none, which was a sampling limit and not evidence
  of absence. 013990 is the fixture when this is built.
* **Blank means "unknown"**, per Allan: clerks leave a cell blank when the
  information is not known. Blanks must not be counted as recognition failures.
* **The name column is picked by rule index, not width**, and lands on the
  Numero strip when the divider is detected. Measured at ~7% of pages, so real
  but small. `scripts/spike_columns.py`.
* **German-line ships are ~3.7% of the catalog** and their forms are Portuguese
  Brazilian port documents, so Kurrent/Sütterlin risk is lower than feared —
  n=2, unconfirmed.

### Next, in order

1. **The row comb fitting the wrong half of the page.** Everything else is
   smaller than this.
2. **mkldnn off for the full-page path** — 99% of documents, one line.
3. Re-index and re-measure; the 38.3% blank figure means little until 1 is done.
4. Ditto inheritance, stored beside the verbatim text rather than replacing it.
5. Confidence: hide or calibrate.

## 2026-08-19 — daytime session (Allan at work)

Everything below is committed and pushed to https://github.com/allan-valin/ocr-gene-docs — nothing is running, no background
jobs, no servers left up. The local corpus in `data/scans` is fully indexed, so
search works the moment the server starts.

### The headline

**The corpus is 168 dossiers now — 865 pages — and all of it is indexed, with no
failures.** 110 more dossiers were downloaded this afternoon to answer the question
the morning's numbers could not: does search still work when the pool gets bigger?

It does for typed pages. **It is starting to fail for handwritten ones**, exactly as
the margins predicted.

| pool | typed page: ranked first | typed: top five | handwritten: ranked first | handwritten margin |
|---|---|---|---|---|
| 147 rows | 26/26 | 26/26 | — | — |
| 1,081 rows | 23/26 | 26/26 | 5/6 | +0.114 |
| **3,430 rows** | **20/26** | **26/26** | **4/6** | **+0.043** |

"CEZARIO SAMMAMED" is now lost entirely: at 3,494 rows the word "SUMMARIO", printed
on some other page, outranks the row it belongs to. A twentyfold larger pool is
coming, and this is what it will do.

So the ranking is clear: **handwriting recognition is the thing worth money now.**
Speed is solved, indexing is solved, search is solved for typescript.

### Throughput, re-measured on the harder half

The morning's "35 hours for 7,000 dossiers" came from the first 57 dossiers, which
are small. The dossiers downloaded this afternoon are two to five times larger, and
on those the rate collapsed to about one dossier a minute — until profiling found the
cost was not recognition at all:

| step, per page | before | after |
|---|---|---|
| extract the page image | 11.6 s | 4.8 s first time, then free |
| geometry | 2.3 s | 2.3 s |
| recognise the rows | 2.6 s | 2.6 s |

`pdfimages` re-parses the whole PDF on every call, so a five-page dossier was five
full parses, and the chosen image was recomputed every time the page was touched.
Extracting each document once and recording the result **roughly quadrupled indexing
throughput**: the final pass did 90 dossiers in 26.6 minutes, ~17.7 s each.

At that rate 7,000 dossiers is **about 34 hours** on this laptop — the earlier figure
survives, but for a different reason than it was first arrived at.

### What made it ten times faster

The name column was being detected and then recognised. But the grid already knows
where every row is, so detection is redundant: crop the row bands, recognise them
directly. That was 21× faster and, at first, much worse — CER 0.418 against 0.205.

The cause was not the model. **The recogniser's input is 320 px wide, and a manifest
name is wider**, so every long name was silently truncated: "JOHN SCHRADER" came back
as "JOHN". At 640 px the accuracy is *identical* to the detection pipeline (CER 0.205)
at a tenth of the cost. Measurements in `scripts/spike_speed.py`, and the mobile
recogniser was rejected there too (CER 0.508 at any width).

### Two bugs that were invisible until the corpus was run

* **Fourteen of the first twenty dossiers were stored as negatives** — white ink on
  black paper, because the PDFs keep an MRC ink mask with 1 = ink. Geometry never
  minded, since a projection does not care which way contrast runs, which is why a
  night of grid work never noticed. Fixed in `page_geometry.positive()`. Honest note:
  **fixing it did not measurably improve recognition** — the recogniser was already
  coping — but it makes every crop legible to a human, which the review UI depends on.
* **An empty manual note marked a document as indexed forever.** Someone opens a
  dossier, types nothing, and it silently drops out of every future run. For an
  archive index that is the worst failure mode: nobody is told, and the person is
  simply never found.

### PaddleOCR-VL: not viable on this machine

Loaded fine (`vl_rec_backend="native"`, no torch needed) in 14 s, then spent **22
minutes on a single name column without finishing**, against 2.4 s for the
recogniser. Even as an on-demand "read this one page properly" action that is
unusable without a GPU. `scripts/spike_vl.py` is kept for when there is one.

So the answer to "if it is still too bad, jump to PaddleOCR-VL" is: **the small
engine is not too bad** — 5/6 on cursive — and VL is not reachable on this hardware
anyway.

### Where the handwriting actually stands

Engine, on a cursive page: `GUIDO CONTADORE` → `Guudo Camtadore`, `CEZARIO SAMMAMED`
→ `Besaruir Sormamed`. Wrong as transcription, findable as search. That is the whole
argument for measuring retrieval rather than CER — but the winning margins are thin
(some hits score 0.13), and thin margins are what a 70,000-row pool destroys. **This
is the number to re-check as the pool grows.**

The first hand-read ground truth for a handwritten page is now in
`data/truth/`, versioned. Until today the only truth in the repository was a *typed*
page, which is why none of this was visible.

### Also fixed, after the corpus run showed them

* **Search hits now land on the row**, at the right page, with the band drawn on
  the scan. A hit that only opened the document left the user hunting the page for
  the name they searched for.
* **The printed column heading was indexed as a passenger.** "Nomes e Cognomes"
  scored 1.0 against anyone searching a name containing "nome". Exact matching
  caught almost none of them, because the recogniser reads the caption differently
  on every page, so multi-word captions are matched loosely. 24 rows left the index,
  no real name did.
* **Filenames are resolved from the content hash at query time.** Transcriptions are
  keyed by hash so a renamed dossier keeps its work, which means a hit knows what it
  found and not where — and the 57 records indexed this morning have no filename in
  them at all.

### Built today

* `/api/index` — folder indexing: start, progress with a plain-language estimate,
  stop, resume from the content-hash cache, failures named. Four documents at a time.
* `/api/search` + a sidebar search box — **searches every indexed document**, not the
  open one. Trigram matching, an explicit floor below which nothing is returned.
* `desembarque/engine_paddle.py` — the real engine, replacing `NullEngine`.
* `desembarque/search.py`, `scripts/spike_speed.py`, `scripts/spike_retrieval.py`,
  `scripts/spike_vl.py`, `docs/HOSTING.md`.
* Rows now follow the page being read; fields the engine never attempted are blank
  rather than "ilegível".
* **113 Python tests, 35 browser assertions, all passing in Chromium and Firefox.**

### The layout the geometry cannot read

`BR_RJANRIO_OL_0_RPV_PRJ_15992` page 2 is a clean passenger list — 24 handwritten
rows, printed column captions, a wide "Nome" column — and geometry returns **zero
rows** on it, then picks the 1.4%-wide "No. de ordem" strip as the name column. The
row comb is fitted to the written lines, and on this layout it finds none.

Across the corpus this is a minority: **8% of indexed documents come back with no
readable row at all.** But a dossier that yields nothing is a ship nobody can search,
and the failure is silent — the run reports success. It is the most valuable thing
left to fix, and it is deliberately *not* being attempted in a rush at the end of a
session, because the geometry currently works on the other 92%.

### Next, in order

1. **Handwriting recognition.** This is now the only thing standing between the tool
   and its purpose. The printed-text recogniser reads `GUIDO CONTADORE` as
   `Guudo Camtadore`, which fuzzy search rescues at three thousand rows and will not
   rescue at seventy thousand. Options, cheapest first: a recogniser trained on
   handwriting; fine-tuning this one on a few hundred hand-read rows from this
   archive; a vision-language model on a machine with a GPU.
2. **The layout the geometry cannot read** (above). 8% of documents yield nothing,
   silently.
3. **Search ranking should use more than the name.** A person searching knows the
   ship, or the year, or the port. Nothing in the index is used for that yet, and it
   is the cheapest way to cut the pool a name is compared against — which is exactly
   the problem the table above describes.
4. **Re-index to pick up the header flag and the schema stamp.** Records written this
   morning have neither; search compensates by matching heading text instead.
5. **Geometry is the floor on speed** at 2.3 s of a ~10 s page, now that extraction is
   cached. Untouched.
6. **`data/transcriptions/` will outgrow memory.** Search loads every row; at 7,000
   dossiers that is roughly a million rows. It wants SQLite before then, not a bigger
   dictionary.

### Open questions for Allan

* **How much does handwriting matter to you?** For the jus sanguinis work, an ancestor
  on a handwritten list is currently findable only if you already know roughly which
  dossier to look in. That is the decision that shapes the next stretch of work.
* Is ~34 h for 7,000 dossiers acceptable? Four workers use ~7 GB and leave the laptop
  usable; more workers would cut the wall clock and make it unpleasant to use.
* `docs/HOSTING.md` recommends local-only as the shipped default, with hosting as a
  separate deployment. You said hosted is fine "as long as it is intuitive" — that
  document is where I wrote down what intuitive has to mean if scans are uploaded.
* The hand-read ground truth in `data/truth/` is my reading of a cursive hand. If any
  of those six names are wrong, the handwriting numbers above are wrong too.
* 110 dossiers were downloaded from the archive this afternoon (serial, 1.5 s apart,
  the repo's own polite downloader) to get these numbers. Say if you would rather that
  did not happen unattended.

### Running it

```sh
# the engine venv runs the app too, and is the one to use for indexing
.venv-ocr/bin/python scripts/serve.py --root data/scans
.venv/bin/python scripts/serve.py          # app only; engine reads "não instalado"
.venv/bin/python -m pytest tests/ -q       # 113 tests
python3 scripts/smoke_prototype.py --url http://127.0.0.1:8799/selftest   # 35 assertions

# measurements
.venv-ocr/bin/python scripts/spike_speed.py            # per-variant speed and CER
.venv/bin/python scripts/spike_retrieval.py            # retrieval over the real index
```
