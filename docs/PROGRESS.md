# Progress

Running checkpoint. Newest first. The design record is
[the spec](superpowers/specs/2026-07-23-desembarque-design.md); this file is state and
next actions.

## 2026-08-19 — daytime session (Allan at work)

Everything below is committed and pushed to https://github.com/allan-valin/ocr-gene-docs — nothing is running, no background
jobs, no servers left up. The local corpus in `data/scans` is fully indexed, so
search works the moment the server starts.

### The headline

**The whole local corpus — 57 dossiers — now indexes in 17 minutes with no failures,
and search finds people in it.** Before today a single page took 37 s and there was no
folder flow at all.

### The numbers, and what they are worth

| | before | after |
|---|---|---|
| one page | 37 s | **4 s** (1.8 s geometry + 2.4 s recognition) |
| 57 dossiers | never run | **17.3 min, 0 failures, 50 transcribed + 7 already cached** |
| 7,000 dossiers (Allan's real case) | ~720 CPU-hours | **~35 h on this laptop**, four workers |

Retrieval, which is the measure that matters — can a person find their ancestor:

* **typed page, 1,081-row pool: 23/26 ranked first, 26/26 in the top five.**
  (The same queries scored 26/26 first against a 147-row pool, so the loss is the
  pool growing, exactly as expected. A 70,000-row pool will be worse again.)
* **handwritten page, 1,081-row pool: 5/6 ranked first, 5/6 in the top five.**
  The sixth, "A. VIEIRA MIRANDA", was beaten to first place by a real "Joaquim
  Miranda" in another dossier — a fair loss, not a broken index.

Caveat worth keeping: the typed check counts *any* row of the right dossier as
correct, so it is slightly generous. The handwritten check is against known row
numbers and is not.

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

### Next, in order

1. **Re-check retrieval as the pool grows.** The margins above are thin. The cheapest
   real test is Allan's own folder, if it is larger than 57 dossiers.
2. **Row-level accuracy on handwriting.** Per-row upscaling did nothing once the
   width bug was fixed; the remaining lever is a recogniser trained on handwriting,
   or fine-tuning one on this hand.
3. **Re-index to pick up the header flag.** The 57 documents were transcribed
   before headings were marked, so search filters them by text instead. Harmless,
   but the flag is the cleaner path once anything else forces a re-run.
5. **Geometry is now the floor on speed** at 1.8 s of the 4 s page. Untouched so far.
6. **`data/transcriptions/` has no schema version.** It will need one before the row
   shape changes again.

### Open questions for Allan

* Is 35 h for 7,000 dossiers acceptable, or should this run on something bigger?
  Four workers on this laptop use ~7 GB and leave it usable; more workers would cut
  the wall clock and make the machine unpleasant.
* The hosting note (`docs/HOSTING.md`) recommends keeping local-only as the shipped
  default and treating hosting as a separate deployment. Worth reading and arguing with.
* The hand-read truth in `data/truth/` is my reading of a cursive hand. If any of
  those six names are wrong, the retrieval number is wrong too.

## 2026-08-19 — session ended deliberately (laptop noise; Allan sleeping)

Heavy work stopped on request. Nothing is running. **Resume from "Next, in order" below.**

### State of the machine

* No background processes left (`spike_*`, `serve.py` all stopped; load back to ~1.0).
* Two virtualenvs: `.venv` (app: pypdfium2, Pillow, numpy) and `.venv-ocr` (optional
  engine: paddlepaddle, paddleocr). Model weights cached in `~/.paddlex/official_models/`.
* Everything committed and pushed to https://github.com/allan-valin/ocr-gene-docs
* 76 Python tests, 29 browser assertions, all passing at the last run.

### The one result that is NOT valid

`scripts/spike_scale.py` reported **0/26 retrieval at scale. Ignore that number.** The
script took the first fourteen dossiers by filename, which stop at `015652A`, so the
ground-truth dossier `017397` was never in the pool — every query searched for names that
were not indexed at all. The script now refuses to run unless the ground-truth dossier is
present, but **the measurement has not been redone**.

What the run does legitimately show: **13 pages OCR'd in 484 s, so ~37 s per page**
including geometry, on CPU. And per-page cost is very uneven — 2 s to 61 s — because the
cropped strip tracks the row count.

So the honest position on accuracy is still the single-page result: **26/26 ranked first
with 25 distractors**, and *no* evidence yet about behaviour against a large pool.

### Also built tonight, not yet wired up

`desembarque/batch.py` — folder indexer with per-document isolation, resume from the
content-hash cache, stop, and a surfaced failure list. Seven tests, all on failure paths.
**Not connected to an endpoint and never run against the corpus.**

## 2026-08-19 — overnight session

### Done

* **Engine benchmarked, twice.** PaddleOCR's lightweight recogniser on CPU: full page
  110.7 s / mean name CER 0.31; geometry-guided (crop the name column, assign boxes to row
  bands) **27.0 s / CER 0.205**. The measure that matters for a search product is
  retrieval, and there it is **26/26 correct row ranked first** on that page.
* **Table structure without a model.** Grid detection works — deskew, adaptive column
  rules, table extent from the vertical rules, row comb fitted to the *written lines*.
  33 bands, 9 columns on Gelria p2, verified by drawing it back onto the scan. Exposed as
  `/api/grid` and a "Gerar tabela vazia" button.
* **Poppler removed.** `desembarque/pdf.py` on pypdfium2 (BSD-3). Clears the only GPL
  dependency from anything that would ship.
* **Confidence as semaphore dots.** Replaced the wavy underline, which read as a
  spellchecker complaint rather than a statement about trust.
* **Identity by content hash**, so renaming a dossier keeps its transcription.
* **Licensing settled**: AGPL-3.0-or-later, keeping commercial dual-licensing open.
  Published at https://github.com/allan-valin/ocr-gene-docs

### Next, in order

0. **Redo retrieval at scale** with the fixed script (`.venv-ocr/bin/python
   scripts/spike_scale.py`). ~10 min of loud CPU. This is the number that decides whether
   the small recogniser is enough or a larger model is needed. Everything else is
   downstream of it.
1. **Wire `batch.py` to an endpoint and the UI** — background folder indexing with
   progress, which is now the product's main flow rather than per-document transcription.
2. **Retrieval at scale (old item, superseded by 0).** The 26/26 result is a closed set with 25 distractors. Rerun the
   same queries against the whole catalogue, where near-misses are far more numerous. This
   is the number that decides whether the small recogniser is enough.
2. **Per-row crops and 2× upscaling.** Residual errors are on small degraded type
   (`FRAICISCA A2D`). Cheap to test, likely the largest remaining accuracy win.
3. **Wire the engine in properly** behind `desembarque/engine.py`, replacing `NullEngine`,
   with per-field confidence from the recogniser rather than invented numbers.
4. **Manual transcription UX** on the generated grid: keyboard-first entry, autosave,
   export. Valuable even if no engine ever ships.
5. **Local thresholding on the render path**, to close the geometry gap on machines
   without poppler.
6. **Hosted deployment note** — the shape, the costs, and the privacy consequences of
   users uploading scans to a server.
7. **PaddleOCR-VL comparison**, only if 1 and 2 leave the small model short.

### Open questions for Allan

* Is ~27 s/page tolerable, given it should fall further with per-row crops?
* For a hosted version: are users uploading their scans to your server acceptable, and
  should that be written up with the privacy implications spelled out?

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
