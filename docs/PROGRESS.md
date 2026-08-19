# Progress

Running checkpoint. Newest first. The design record is
[the spec](superpowers/specs/2026-07-23-desembarque-design.md); this file is state and
next actions.

## 2026-08-19 — daytime session (Allan at work)

### Retrieval at scale: the number is good

Rerun with the fixed script: **26/26 correct rows ranked #1**, and 26/26 in the top 5,
against a pool of **147 rows from 12 dossiers** — not the 25 distractors of the
single-page result. The small recogniser is accurate enough for search. The earlier
0/26 stays discredited (the ground-truth dossier was never in the pool).

So **accuracy is no longer the blocker. Speed is.**

### Why speed became the whole problem

Allan's own use case is on the order of **7,000 dossiers of ~10 pages** — roughly 70,000
pages. At the measured 37 s/page that is **~720 CPU-hours**, single-threaded. The scale
run confirms the shape: 13 pages in 534 s, and per-page cost swinging 2 s → 63 s with the
row count.

### Done

* `/api/index` — folder indexing over HTTP: start, progress, stop, resume from the
  content-hash cache. It **refuses to start when no engine is installed**, because
  otherwise every one of 7,000 documents fails identically.
* **The sidebar now leads with "Indexar esta pasta"**, with a plain-language estimate
  ("faltam cerca de 2 h"), named failures, and a stop button. Per-document transcription
  asked the user to already know which dossier held their ancestor.
* **`desembarque/engine_paddle.py`** — a real engine at last, replacing `NullEngine`
  when paddleocr is importable. It crops each row band and recognises it directly, with
  no detection pass, and takes confidence from the recogniser instead of inventing it.
* 88 Python tests, 33 browser assertions, all passing.

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
.venv/bin/python scripts/serve.py          # app venv: pypdfium2, Pillow, numpy
.venv-ocr/bin/python scripts/spike_guided.py   # optional engine venv
.venv/bin/python -m pytest tests/ -q       # 69 tests
python3 scripts/smoke_prototype.py --url http://127.0.0.1:8795/selftest
```
