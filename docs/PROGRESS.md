# Progress

Running checkpoint. Newest first. The design record is
[the spec](superpowers/specs/2026-07-23-desembarque-design.md); this file is state and
next actions.

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
