# Progress

Running checkpoint. Newest first. The design record is
[the spec](superpowers/specs/2026-07-23-desembarque-design.md); this file is state and
next actions.

## 2026-08-21 — evening (Allan present, working to 23:00)

### The corpus is not a test set

Allan asked why a change had to be checked by re-reading seven thousand pages,
and the answer is that it did not. **Nothing here is trained.** The recogniser's
weights are fixed; no amount of scanned paper moves them. A full re-index
refreshes what the app serves and proves nothing about a change — and I started
one three times today, each time to pick up a change, each restart throwing away
the work before it.

What a change is checked against now, in the order it runs:

| | what it answers | cost |
|---|---|---|
| `pytest` | 422 unit and pipeline tests | 30 s |
| `scripts/bench_search.py` | can these people be found by name? | 10 s |
| `scripts/bench_pages.py` | is the table measured right, across the printings? | 1 min |
| `scripts/bench_rec.py` | how well are the names read? | 1 min |
| `scripts/smoke_prototype.py` | does the page still work in two browsers? | 2 min |

`data/golden.json` names ten pages and why each is in the set: a typed list, a
dense cursive family list with dittos, a continuation page that prints no
headings, one passenger on a full ruled sheet, a page whose ordinals the scan
lost, faint pencil, a busy letterhead, a letterhead in two columns. A ten-second
bench caught a scoring change that cost seven findable names — the hours would
have said the same thing at ten thousand times the price.

### What the benches settled tonight

**Findable names went from 39 of 68 to 51 of 68**, measured by searching each
hand-read name exactly as a person would type it.

Every one of those came from the repetition mark. These lists are written by
family — the surname once, a ditto under it for each relative — and BS.ENT.013947
p3 lists forty-eight people under nine surnames. The mark rarely survives the
recogniser as its own token: it comes back glued to the name (`"Joze`,
`,Friancisca`), or not at all. So the mark is now matched wherever it is, a row
read as a single word no longer sets the family surname, and a lone given name
under a family inherits it. Each inheritance records **how** it was arrived at —
`mark`, `indent`, `position` — because a mark on the page and an inference from
position are different claims: the review UI dots an inferred surname in the
warning colour and says so on hover, and the CSV carries a `sobrenome_origem`
column. The reading itself is never touched.

Resolution runs at index time as well as at reading time, so improving the rule
reaches the whole corpus in a second rather than in hours.

### Four things that did not work, measured and dropped

Worth writing down, because each looked obviously right:

| | result | verdict |
|---|---|---|
| recogniser input 960 px and 1280 px wide | CER 0.515, 0.581 against **0.458** | 640 px stays |
| `PP-OCRv5_server_rec`, a bigger model | CER 0.516, 41/68 findable against 52 | current model stays |
| removing the printed rules from each crop | CER 0.461 against 0.458 | kept behind `DESEMBARQUE_DERULE=1` |
| matching word by word instead of whole-string | findable 44/68 against 51 | reverted |
| folding OCR-confusable letters together | 51/68, unchanged, and it broke the pool's guarantees | reverted |

Handwriting recognition is at its ceiling for what runs on this machine. That is
now a measured statement rather than an impression.

### The two pages the golden set carried as unsolved

Both are solved, and they failed differently. On BS.ENT.016574 three letterhead
lines sat above the table and took every candidate slot, so the heading was never
read — a heading is a row of short cells and a letterhead line is a sentence, so
candidate lines are now required to be made of short cells. On OL.PRJ.17851 the
writing is too faint for the detector to see at all — thirty boxes on a page of
twenty-three names — while the recogniser reads those names perfectly once a band
is cut for it; there the rules still supply the rows and the printing keeps the
column, recorded as `measured_by: printed columns, ruled rows`.

**Ten of ten golden pages now measure from the printing.**

### Also

An empty ruled row is no longer sent to the recogniser. A list is printed with
thirty rows and often carries three, and now that the bands cover the whole list
rather than a third of it, reading the blanks was most of the corpus's time.

### Names the archive knows, offered as guesses (Allan's suggestion)

Since recognition is at its ceiling, the remaining help for somebody reading
`Dantalarlraia Saliador` is a list of names these ships are known to have
carried. Built from the archive itself — `scripts/build_names.py` counts the
pages the clerks *typed*, which the recogniser reads at CER 0.01, and every row a
person has typed by hand: **760 names from 5,323 clean rows**, with the form's
printed vocabulary and the trades filtered out by the machinery that already
knows them. A general name dictionary would be somebody else's idea of which
names exist; these ships carried Italians, Spaniards, Portuguese and Syrians to
Santos between 1917 and 1925.

The line this must not cross is the one the whole tool rests on, so:

* a guess is never a value — it ranks what the engine read and may be offered
  beside it, and it is stored only when a person picks it, as that person's
  typing;
* the word menu keeps `outras leituras do motor` first; guesses appear under
  `palpites do acervo — não lidos da página`, in the warning colour, each with
  how close it is and how often the archive saw it;
* they are off until asked for (`≈ Prováveis`), and only then does `↑ primeiro`
  appear to put them above the readings;
* `/api/names` says in its own response that these are not readings.

The first thing it offered for `Saliador` was `TRABALHADOR`, which is a
profession that reached the name column on pages read before the column was
measured from its printing. Trades are filtered now, and **the list wants
rebuilding after the corpus refresh** — the builder says so in its own output.

`? Duvidosas` is the other half: the rows where nothing in the reading resembles
a name this archive carries, marked so a person checking four hundred rows knows
where to start. It says on hover — and in the endpoint's own answer — that a rare
name is unknown here and perfectly correct.

### How much of the corpus is inference, and how often it is right

The position rule fills in a surname for a row that carries none, and it is 41%
of the rows read tonight: **674 read, 521 by position, 65 off a mark, 10 off an
indent.** That is a large share of a record used as evidence, so it was measured
rather than assumed.

On the hand-read page, of forty inherited rows **thirty-six attach to the family
the page actually says**. The four that do not are one block: `Castiello Cosme`
came back as `CastiettoCoome`, the recogniser having lost the space, so no new
family started and four Castiellos were filed under Lorenzo. The failure mode is
therefore bounded and legible — a missed family head cascades to its members —
and every inherited surname says in the record and on screen that it was
inherited.

Splitting a joined word at its interior capital was tried, since that is exactly
where the lost space is. It costs two findable names of sixty-eight, measured
against the same index both ways, and was reverted: the mangled first half
becomes a family head and the rows below it inherit something worse than what
they had.

#### What the guesses are actually worth

Measured against the ninety-six hand-read names, with the list as it stands
tonight (760 names, built from a corpus that is still being re-read):

| | |
|---|---|
| rows where the archive list contains any word of the true name | 71 of 96 |
| rows where the right name is among the four offered | 23 |
| rows offered only wrong names | 67 |

So it helps on about a quarter of rows and shows plausible-but-wrong names on two
thirds. That is the argument for every constraint on it — off by default, in its
own section, in the warning colour, and never a stored value. Lowering the
threshold to 0.5 buys four more rows with the same amount of noise, which is not
enough to justify moving it.

The list is the limit rather than the matching: on a quarter of rows the archive
simply does not contain the name. It should get better as the refresh replaces
records read before the name column was measured properly — **rebuild it and
measure again then**.

### A dossier that silently emptied itself

BS.ENT.013942 came back from the run with **no rows at all**, an hour after it
had read `Ponticelli Giovanni`. Its page carries the oneDNN failure this machine
has thrown since July — `ConvertPirAttribute2RuntimeAttribute not support`. The
page pipeline has retried without oneDNN since then; the recogniser never did,
and the recogniser is what the new heading pass calls first.

The worse half: the record was stored at the current schema with no rows, so
every future run would have skipped it. That is the second time this shape of bug
has appeared here — the first was an empty manual note marking a document as done
forever — and it is the failure this tool exists to prevent. `is_indexed` now
refuses a record whose pages carry an engine error.

### Next, in order

1. **Rebuild `data/names.json` after the refresh.** The list is only as good as
   the pages it was counted from, and those are being re-read now.
2. **A dossier's later pages could skip the heading pass entirely** when the
   columns are already known from an earlier page — a recogniser batch per page,
   which is most of what the geometry now costs.
3. Handwriting recognition is the ceiling, and every cheap lever has been pulled.
   What is left is a model that can read cursive Portuguese and Spanish on a CPU,
   or a GPU.
4. The corpus refresh is running at about a dossier a minute; 660 of them is
   roughly ten hours, unattended, resumable.

### The refresh

Started once, at 19:41, on schema 18, and left alone: 660 dossiers, four workers,
resumable from the content-hash cache. Everything above is in it. Where it stops,
`curl 'http://127.0.0.1:8799/api/index'` says, and starting it again picks up
where it left off.

## 2026-08-21 — afternoon (branch `rows-from-writing`, merged)

Allan opened four dossiers and most of what came back was gibberish. He was
right, and the cause was not the recogniser.

**Every measurement on these pages came from rules the scan has often lost.**
The name column was the widest gap between the vertical rules that happened to
be detected: on BS.ENT.013947 p3 that is the *Procedencia* column, so the engine
read a column of ditto marks and filed it as names; on BS.ENT.013983 p2 it is two
thirds of the sheet. The horizontal rules are dotted, and the comb fitted to them
locked onto the empty ruled area *below* the typed list on 013983 — fourteen
perfectly legible names, none of them read — while on 013942 it sat half a row
out of phase and two rows late, so band 1 covered printed row 3 and every crop
carried the descenders of one row and the ascenders of the next.

`desembarque/tablegrid.py` measures the table from what is **printed** on it: the
column headings, and the ordinal printed on every ruled row whether anybody wrote
on it or not. Detection alone answers it — 3 s a page against the 55–80 s the
page costs to read — and only the heading line is recognised, to know which
column is which. The rules stay as the fallback for a page that prints no
heading.

| page | before | after |
|---|---|---|
| 013983 p2, typed | 26 rows, none of the 14 names | **14/14 verbatim** |
| 013947 p3, cursive | 33 rows of the Procedencia column | 49 rows, names, 15 s |
| 013942 p2, cursive | bands 2 rows late, the one name missed | the name, on row 1 |
| 015061 p6, cursive | 50 rows | 46 rows, names |

Surveyed over 40 random indexed pages: **32 measured from the printing**, mean
9.2 s a page; the other 8 fall back to the rules exactly as before. Three bugs
found in that survey and fixed with tests: the detector reports its boxes in its
own order and the pitch was measured over it; the heading row was picked as the
busiest line rather than the topmost full-width one, so a busy letterhead crowded
it out; and five stray ordinals outvoted forty-six written lines, giving sixteen
bands three rows tall.

**The corpus on disk does not have any of this yet.** Schema is at **16** and
every stored record is stale by design: this needs the page images again, so it
is a re-index, not a re-parse — the run described at the top of this file, about
four hours unattended.

### What is left, and it is one thing

The crop for 013942 row 1 now holds `Ponticelli Giovanni` whole and clean, and
the recogniser says `Pouticelli Sooai`. Geometry is no longer the limit;
**handwriting recognition is**, as this file has said since the first week, and
now nothing else is in the way of measuring it. `scripts/bench_rec.py` scores a
recogniser against the hand-read pages in `data/truth` — CER and, more to the
point, whether the reading is still *findable* by search — and two truth pages
were added for it: 013983 p2 (typed, the control) and 013947 p3 (48 cursive
names, read by eye and uncertain, for ranking variants against each other).
Nothing has been swept yet: the next session runs the input-width and model
sweep against that bench.

Also: the search scope control on the header is now a menu the page owns —
visible against the panel, an arrow at text size, and it closes on the same
click, on a click away, and on Escape.

## 2026-08-21 — night session (Allan away)

Nine commits, all pushed. The two things last night's checkpoint named as next
are done, and the corpus on disk carries both. **380 Python tests, 67/67 browser
assertions from disk and 77/77 served, in Chromium and Firefox** — including
`the scan band follows the hit`, which is the assertion the missing geometry had
been failing.

### The bands are back on every page, and nothing had to be read again

`transcribe_document()` now keeps `res.geometry` on the page it was measured
from, and `scripts/backfill_geometry.py` put it back on everything already
indexed, out of the page images still in `data/pagecache`.

| | |
|---|---|
| records that wanted geometry | 634 |
| pages measured | 2,446 |
| refused as disagreeing with the rows | **0** |
| time, three workers | 28 min (08:31–08:59) |
| records now carrying page geometry | 634 of 660 |

The remaining 26 are the two hand-measured records, which keep a
document-level measurement, and 24 dossiers the engine found no rows in.

The measurement is deterministic: on every page sampled before the run, the
recomputed band count equalled the number of rows stored against it exactly —
16 rows, 16 bands; 46 and 46. That is what makes the repair safe, and it is
checked per page rather than assumed: row `n` **is** its band's index, so a
band list shorter than the rows on disk would draw every row after the first
difference against somebody else's line. Such a page is refused and reported.
None occurred.

The bands were then unusable for a second reason. The corpus payload carries
one geometry per *document* and a dossier is read page by page, so a hit on
page 7 was painted from whatever single measurement the record happened to
hold. All the bands together are 3.5 MB and cannot ride along with the folder
list, so `/api/geometry?hash=` hands over one dossier's when it is opened and
the page strip picks the page's own. The file:// build has no API and keeps
what it was built with.

### A year now says where it was read, and the writing outranks the stamp

`year_source` is `printed` or `stamp`, and where a dossier's two forms disagree
the year the clerk wrote wins, whichever page was read first. Two stamps
disagreeing is the same claim twice and the first still stands.

Across the corpus: **96 years printed, 67 stamped.** All four 1928s — the
misreadings of 1923 that started this — are stamped, and now say so in the
record, in the document header (`1928 (carimbo)`) and in the hit list.

### One in eight shipping lines was the sheet talking about itself

`No. 461B` twelve times, `Repartição da Policia` five,
`BR.AN.RiO.O2.O.RPV.PRJ.1GGS.8` ten. The whole-string refusal that caught
`POLICIA DO PORTO` missed every way the recogniser breaks it, and the run of
digits that caught the archive's notation is not there once its zeros come back
as letters. Refused now a word at a time and fuzzily, the way a ship is; a
refused line no longer ends the search, because the company is often printed on
the line below it.

| of 660 records | before | after |
|---|---|---|
| naming a shipping line | 418 | 408 |
| lines that changed | — | **111** |
| junk among the commonest | `No. 461B` (12), `Repartição da Policia` (5) | none in the top twenty |

Coverage falls slightly and that is the right direction: the ten sheets that
lost a line had nothing on them but the form's own printing, and a hundred and
eleven now name the company that actually sailed.

`No. 461B` → `The Koyal Mail Steam Packet Company`; `Mod. bordo N. 133` →
`LLOYD SABAUDO`; `POLICIA MARITIMA DO PORTO` → `Nippon Yusen Kaisha`.

The same run showed the mirror of it: **the company was being filed as the
ship.** `The Koyal Mail Steam Packet Company` was a vessel in four dossiers and
their line in thirty-two — where the clerk left the vessel blank, the
letterhead above stands nearest to the label, and a ship read off a passenger
list was never compared against the line printed on the same sheet. Seven
dossiers lose a ship they never had.

The regression list is what keeps these filters honest: sixteen companies read
off real pages in the same run, `COMPANHIA NACIONAL DE NAVEGAÇÃO COSTEIRA`
among them, which must keep their names while `Repartição da Policia` loses
one. `HUGO STINNES LINIEN` is why the port names are matched whole rather than
by word — `STINNES` is within a hair of `santos`.

### Search: what actually runs out first is not memory

The progress log had assumed `data/transcriptions` wants SQLite before the full
archive. Measured, that is not the wall:

| | 660 dossiers | extrapolated to 7,679 |
|---|---|---|
| rows indexed | 19,308 | ~225,000 |
| index in memory | 22 MB | ~260 MB |
| cold load | 3.8 s | ~45 s |
| **per keystroke** | **~100 ms** | **~1.2 s** |

It is the per-keystroke scan that does not survive, and it does not need a
database. A row can only score above zero if it shares a trigram with the
query, and the floor is 0.10, so scoring only those rows returns *exactly* the
same hits with the same scores. A trigram posting list of row numbers now does
that: **~100 ms → ~20 ms**, the pool scored down from 19,373 rows to about
2,000, built in 0.13 s for 4 MB and kept across requests — `/api/search` loads
the index on every request, which is what makes a correction searchable the
moment it is typed.

Also out of the index: sixty-five rows that are not passengers. The tally at
the foot of the list (`Total 10412190`, `EM Tranzito em 1a 28 em 3a 9 total
37`) and the interpreter's prose where the row comb reached it. Three things
were letting them through — the tally's own words were not on the list of the
form's printing, the detector runs a word into its punctuation and into the
next (`registro,`, `com/8pessoas`), and digits are not evidence about a name.

### The green dot said the engine was right

`Brges. iuig` scored 0.86 and showed a green dot labelled *alta confiança*. The
number is Paddle's decode score: how firmly it committed to the characters it
emitted, which stays high on confident nonsense. It now says what it is —
`score do motor`, the name the CSV export already used instead of `precisão` —
and a high score is painted neutral. Green is kept for the one thing that earns
it: a value a person read off the scan and typed. The low end is unchanged,
because the asymmetry is real — a low score does mean the recogniser struggled.

Calibrating it properly still needs hand-read truth, and `data/truth` holds one
page.

### The browser suite had a way of reporting nothing as a pass

Two bugs of exactly the shape the stale-build refusal was written for. Firefox
waited a flat four seconds before reading the result, which is enough for the
file:// build and not for a served corpus of 660 dossiers; it polls now. And a
browser that ran and reported *nothing* printed `not available, skipped` —
identical to one that is not installed — so a served run said ALL PASS with
Firefox silently dropped. Absent is a skip; silence is a failure.

### Next, in order

1. **The corpus is a sample.** 660 dossiers of the 7,679 the catalogue lists.
   Nothing here is tuned to 660, and the search index was measured against the
   full number rather than the current one.
2. **Confidence is still uncalibrated**, and now honestly labelled instead. One
   hand-read page is not enough to calibrate against; a few dozen would be.
3. **The ship is still the weak field** — 26% of dossiers name one, and about
   one in eight of those is a stamp or letterhead (`RII IEVEL`, `vaporRANIA`).
   The archive's catalogue covers the ship for search regardless.
4. The candidate pool could be narrower still: it is padded trigrams that keep
   ~2,000 rows in it, and dropping the padding would change results on rows
   read as a single letter — a behaviour change, not an optimisation, so it was
   left alone.
5. `reparse_voyages.py` after any change to the way the forms are read; the
   schema is at **15** and every record on disk is current.

### Open, and Allan's to answer

* The full download is ~7,679 dossiers, and the measured cost is 65 s each —
  about five and a half days unattended on this laptop. That number decides
  whether the fast forms-only first pass gets built before the download, and it
  is unchanged by tonight's work: the geometry backfill is cheap only because
  the pages had already been read once.
* Whether a stamped year should be *searchable* at all, or only shown. It is
  searchable today and marked everywhere it appears.

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

### The year came from the stamp, not the writing

Not one dossier in the run resolved a year: the arrival date is handwritten in a
blank the clerk often left empty, and the year is the thing a searcher is most
likely to know. The port stamped every sheet on arrival, in ink — `JUN 23 1917`,
`JUL 5 1918`, `OUT 27 1917` — and those come through cleanly. In all ten pages
that had kept a stamp, its year matched the only year printed anywhere on the
page. **Year coverage went from 0% to 31%** on the dossiers read so far.

Only the year is taken. The stamp's date is when the police filed the sheet,
near the arrival and not the same claim — on BS.ENT.014037 the writing says
January and the stamp says June. And the year has to be the *end* of the stamp
rather than whatever in it looks like a year: hunting the digits reads `JUN 19
1918` as 1919, because the day and the century run together.

This was the first change tried on a branch and merged on a measurement rather
than on an argument, because the kept pages made it a one-second question.

### Search stopped being only a name

Three things the live index showed that the unit tests could not.

**The archive already knows every ship.** `data/catalog.jsonl` files all 7,679
dossiers under a typed ship's name; the tool reads one off the page in about a
fifth of them, mangled by the same hand and recogniser as the surnames. Both are
searchable now and they stay two claims — the page is the document and wins
where it said anything, the catalogue is somebody's note about it. Where they
differ the header carries both: *garonne*, then *lido "Jaronna"*. This needed no
re-reading at all; the catalogue is joined at query time from the manifest that
was already in the scans folder.

**A ship's name, or a year, typed on its own now lists who arrived.** "Show me
everyone on the Itapuca" is the other half of what this is for and it did not
work: a ship's name was compared against surnames and returned whatever happened
to look like it — `ITALIAS`, `Itabea Tevures` — while the dossier filed under
that exact name was nowhere in the results. A year was stripped out of the query
as a year should be, leaving nothing to search for.

**The voyage now multiplies the name match instead of being added to it.** A flat
bonus lifts every row on the named ship equally, and most rows on any ship
resemble nothing that was typed: `Contadore belvedere` put `CONGE NGLONE A`
above `Guudo Casrtadore`. Multiplied, the margin it moves is the thin one
between two spellings of a name, which is the margin it was meant for.

Also found live: an empty name query is not a query — trigrams are padded, so
the similarity of nothing against a row read as `B   B` comes out at 0.25, and
searching a year alone ranked a page of whitespace above the ship. And the row
comb catches the printed form as well as the names, so `toneladas` and `pessoas
de tripulação` were indexed as people; phrases of form words are dropped, single
words are not, because no threshold that catches `consigr` spares `gomes`
against `cognomes` or `romano` against `comando`.

### The ship's name, measured three ways

The ship is the field that would let somebody search *Valdivia 1924* and get one
dossier instead of three thousand rows, and it is the field the recogniser loses
most often. Measured on the first twenty-odd dossiers of each run:

| | dossiers naming a ship | junk among them |
|---|---|---|
| by reading order | 4% | — |
| paired by position | 41% | most of them |
| position + the form's own words refused | **26%** | 2 in 20 |

Pairing by reading order fails because reading order is not layout: a value
written a little above its printed baseline is reported *before* the label it
belongs to. On BS.ENT.013942 the ship `INDIANA` is two fragments away from the
word `vapor` by reading order and sits directly beside it on the page. The
engine now keeps each fragment's box and pairs the label with the nearest thing
to its right that shares its line.

That found something beside the label far more often, and most of what it found
was the form talking about itself — `Paguete`, `(2) papor hespanhol`,
`Repartição da Pette`, `de antos`. A wrong ship is worse than no ship: it
answers a search that should have found nothing, with the confidence of a
printed record. A candidate is now refused if any word of it belongs to the
form, the port stamps or the nationalities.

Two junk readings survive in twenty — `RI IVEO`, twice, which is a stamp. The
next filter is a minimum word length: ship names in this archive run to five
letters and up, and `iveo` does not. It is deliberately **not** being added at
the end of a session, because it would refuse a real four-letter vessel and
because every such change makes the whole corpus stale again.

### Checkpoint, 2026-08-20 midday

The re-index is **running unattended** and resumes from cache: 119 of 660
dossiers current, 0 failures, ~36 s each, roughly five hours left. Four workers
is the setting that fits this machine — five and six were both *slower*, and six
pushed it into swap.

On the 86 dossiers read so far: **91% state a voyage, 90% name the shipping
line, 41% give a year, 40% a port, 27% a ship, 13% a full date.** Years run
1917-1920 throughout. Three of the twenty-three ships read off pages are still
noise (`RII IEVEL`, a recurring stamp) — about one in eight, and the archive's
own catalogue covers the ship for search regardless.

When the run finishes: `scripts/reparse_voyages.py`, then
`scripts/voyages.py`. A server started before a schema bump goes on stamping
records with the number it started with, and the re-parse lifts them in a second.

### Where this leaves the corpus, and what is running

A full re-index is running as this is written — 660 dossiers, four workers,
around 35-40 s each. It resumes from the content-hash cache, so it can be
stopped and restarted at will and will skip whatever is already current:

```sh
.venv-ocr/bin/python scripts/serve.py --root data/scans     # then, in another shell
curl -X POST 'http://127.0.0.1:8799/api/index?dir='         # start / resume
curl      'http://127.0.0.1:8799/api/index'                 # progress
curl -X POST 'http://127.0.0.1:8799/api/index/stop'         # stop; workers finish the page
.venv/bin/python scripts/reparse_voyages.py                 # re-read the forms already on disk
.venv/bin/python scripts/voyages.py                         # what the corpus now knows
```

**Run `reparse_voyages.py` after the indexing run**, and after pulling any change
to the way the forms are read. A server that was started before a schema bump
goes on stamping records with the number it was started with; the re-parse lifts
them and costs a second. Only a change that needs the page *image* again — the
engine, the geometry — needs the corpus read a second time.

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

### Checkpoint, 2026-08-20 evening — the corpus was read, and two things it read are wrong

The re-index finished: **660 dossiers, 198 read and 462 already current, no
failures, 3 h 36 m** — about 65 s a dossier on the afternoon's larger files,
against 24 s on the first stretch. `reparse_voyages.py` changed nothing, which
is the right answer: the server was started after the last schema bump, so every
record already carried schema 14.

346 Python tests and 73 of 74 browser assertions pass. The one failure is not
cosmetic, and neither is what it led to.

#### What the whole corpus knows, against what twenty dossiers suggested

The midday figures came from the 86 dossiers read by then, and those are the
small early ones. On all 658 records at schema 14:

| | midday, n=86 | now, n=658 |
|---|---|---|
| states a voyage | 91% | 69.8% |
| names a shipping line | 90% | 63.5% |
| gives a year | 41% | 24.8% |
| gives a port | 40% | 26.3% |
| names a ship | 27% | 26.0% |
| gives a full date | 13% | 5.6% |

The ship holds; everything else roughly halves. 134 distinct ships are named.
The line list still carries the form talking about itself — `No. 461B` fifteen
times, `Repartição da Policia` eleven, `BR.AN.RiO.O2.O.RPV.PRJ.1GGS.8` ten —
about one in eight of the lines read is letterhead or the archive's own
notation.

#### The stamp is not a reliable year, and the record cannot be audited

Years came out spanning 1913-1928, which is wider than this corpus should be.
**1928 is a misreading of 1923.** In every case the port's stamp and the date
printed on the same page disagree, and the stamp wins because the stamp is where
the year is taken from:

| dossier | stamp, as read | the date printed on the same page |
|---|---|---|
| BS.ENT.016669 | `DEZ 29 1928` | `Dec.de 1923.` |
| BS.ENT.016672 | `DEZ 80 1928` | `de 19123` |
| BS.ENT.016331 | `JUN 19 1928` | `de 192.3` |

A `3` reads as an `8`, and `DEZ 80` is not a day this or any month has. The
morning's rule — the stamp's year matched the only year printed on the page, in
all ten pages that had kept a stamp — held at n=10 and has three counterexamples
at n=660. The lower bound, 1913, is one dossier (OL.PRJ.19068, `entrado em 23 de
Novenlo de 1913`) read off an interpreter's PARTE, and is plausible but
unconfirmed. What the corpus actually reads as is **1917-1925**.

The second half of this is worse than the first: **a record does not say where
its year came from.** The stamp and the printed date are two different claims —
the stamp is when the police filed the sheet — and only one number is kept.
Nothing on disk distinguishes a year read from a stamp from a year read from the
form, so these three could only be found by going back to the page text. A year
should carry its source, and where the two disagree the *printed* date should
win: a clerk's pen and a rubber stamp fail in different ways, and the stamp
fails on digits.

#### Every row was stored without the geometry it was cut from

The failing browser assertion is `the scan band follows the hit`: click a search
hit, the right row is selected, and no band is drawn on the scan beside it.
Across the corpus:

```
records 660 | rows and geometry 2 | rows, no geometry 634 | no rows 24
```

**658 of 660 records store an empty `geometry`.** The two that have it were
measured through `/api/grid`, one page at a time, by hand.

`transcribe_document()` in `scripts/serve.py` builds each page as `{"n", "kind",
"error"}` and a `form`, and never copies `res.geometry` — which the engine does
return (`engine.py:35`, set in `engine_paddle.py:672`) and which the review UI
already knows how to read (`serve_shapes.py:57` normalises per-page geometry for
exactly this). The measurement was taken, used to cut the rows, and dropped on
the way to disk.

What that costs: a search hit can say *which row* but cannot show *where on the
scan* — which is the one thing that makes a mangled reading usable as evidence,
because the person checks the image and not the transcription. It was reported
as a success for three and a half hours.

The repair does not need the engine. Row geometry is `page_geometry.analyze`, a
measurement on the page image, and `data/pagecache` still holds every extracted
image — so recomputing it for the one transcribed page of each dossier is
roughly half an hour, not another 3 h 36 m. **Do not start another full re-index
for this.**

#### Also today

Reading the voyage off both forms a dossier carries, pairing a printed label
with the handwriting beside it by box rather than by reading order, the ship and
the year as things a searcher can type on their own, CSV export, the second
reading offered as an alternative instead of a retype, and the browser test
stopped passing against a stale build. Forty-seven commits, all pushed.

#### Next, in order

1. **Keep the geometry** on every page a document is read from, and backfill the
   660 records already on disk from `data/pagecache`. Both halves matter: the
   fix stops the loss, the backfill is what makes the corpus usable.
2. **A year must record its source, and the printed date must outrank the
   stamp.** Then re-parse — this needs no page image, so it costs a second.
3. **The corpus is a sample, not the target.** 660 dossiers were downloaded from
   the eleven index PDFs in `indices/`; the catalogue extracted from those same
   PDFs lists **7,679**. Allan's instruction is that the full set is downloaded
   once the implementation is done, so nothing here should be tuned to 660.
4. The shipping line takes letterhead and archive notation as a company name,
   about one in eight.
5. Confidence is still Paddle's raw decode score, shown as if it meant
   trustworthiness.
6. `data/transcriptions/` is 660 files read into memory on every search. At
   7,679 it wants SQLite.

#### Open, and Allan's to answer

* The full download is ~7,679 dossiers. At the measured 65 s each that is
  **about five and a half days** of indexing on this laptop, unattended. That
  number, not the engine, is what decides whether the fast forms-only first pass
  gets built before the download.

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
