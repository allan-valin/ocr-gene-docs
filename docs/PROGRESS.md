# Progress

Running checkpoint. Newest first. The design record is
[the spec](superpowers/specs/2026-07-23-desembarque-design.md); this file is state and
next actions.

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

1. **Retrieval at scale.** The 26/26 result is a closed set with 25 distractors. Rerun the
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
