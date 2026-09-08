# The VLM second reading: what to do next, in order

Written 2026-09-08, after the measurements in `docs/TASKS-honest-measurement.md`
T6. This is the plan those numbers argue for, and the order matters more than
any of the steps — the first one costs nothing and can cancel the rest.

## What is already decided, and does not need revisiting

* **The model is `Qwen2.5-VL-7B-Instruct`, Apache-2.0.** Not CHURRO, which
  reads cursive marginally better and is research-licence only, so it cannot
  ship under `LICENSING.md` or the open-source-only rule. The gap between them
  is about seven names in a hundred and ten.
* **Q4_K_M under llama.cpp**, on per-row carved crops. Q8_0 buys nothing and is
  40% slower; the name column read in one look reads worse, not cheaper.
* **The pass exists and is resumable**: `scripts/read_vlm.py --documents`,
  choosing documents by the hand `data/hands.json` gave them, writing the
  sidecar `scripts/apply_second_opinion.py --write` already applies.
* **Nothing has been applied to the corpus.** The engine's readings are
  untouched, and that stays true until step 3 below says otherwise.

## The cost, measured, so no step is agreed to blind

| | seconds a row | a 40-row page | the whole corpus (71k rows) |
|---|---|---|---|
| the engine as it ships | 4.33 | 3 min | 86 h |
| Qwen2.5-VL-7B, Q4_K_M | 8.5 | 6 min | 170 h |

170 hours is not a thing to start casually, which is why the plan below spends
one hour before it spends a hundred.

## 1. Allan reads the held-out pages (blocked on a person, costs no machine)

`~/Downloads/desembarque-reading-sheet.html`, then:

```sh
.venv/bin/python scripts/import_reading_sheet.py ~/Downloads/reading-sheet.json
.venv/bin/python scripts/bench_search.py --matrix --held-out
```

That second command is the engine's honest baseline on pages nothing was ever
tuned against. Three pages is already a real sample.

## 2. The cheapest decisive experiment: the VLM on those same pages only

**Already done, 2026-09-08 — `data/vlm-heldout.json` holds it.** All ten pages
of the draw, 357 rows, read by Qwen2.5-VL-7B, the same pages the sheet puts in
front of a person and no others. So when the sheet comes back, step 2 is one
command and no machine time:

```sh
.venv/bin/python scripts/bench_search.py --matrix --held-out \
    --second-opinion data/vlm-heldout.json
```

The original recipe follows, for when it has to be run again.


Ten pages is about 360 rows — **under an hour of machine**, against 170 hours
for the corpus:

```sh
Q=~/.cache/huggingface/hub/models--ggml-org--Qwen2.5-VL-7B-Instruct-GGUF/snapshots/*/Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf
M=~/.cache/huggingface/hub/models--ggml-org--Qwen2.5-VL-7B-Instruct-GGUF/snapshots/*/mmproj-Qwen2.5-VL-7B-Instruct-f16.gguf
# data/heldout-pages.json names the exact ten pages the sheet shows,
# so the model and the person read the same ink
.venv/bin/python scripts/read_vlm.py --serve --threads 10 --model $Q --mmproj $M \
    --documents --pages-json data/heldout-pages.json --out data/vlm-heldout.json
.venv/bin/python scripts/bench_search.py --matrix --held-out \
    --second-opinion data/vlm-heldout.json
```

*(`data/heldout-pages.json` is written by the same `pick_page` the sheet uses,
so it stays in step with whatever the sheet showed.)*

**This is the number the whole project turns on.** On the tuned-on set the VLM
took cursive names found by name alone in the top five from 52 of 110 to 78. If
something like that survives on pages nobody has ever tuned against, the rest
of the plan is worth its hours. If it does not, the gain was overfitting and
this document ends here — which is exactly what the held-out set was built for.

## 3. Only then, decide how the reading is used

Two shapes, and the index answers which:

* **As an alternate** (`second_read`, what `apply_second_opinion.py` already
  does): the engine's reading stays the row's text and the VLM's is one more
  spelling the search can match. Safe, reversible, and already proven end to
  end on 2026-09-07.
* **As the reading** on cursive rows: better if the VLM is simply better there,
  and a bigger change — it is what somebody sees on the screen. It should not
  happen without the held-out number and a way back.

Either way a row a person typed, chose, or ticked is theirs and is never
overwritten. That rule is older than this plan and holds.

## 4. Rollout, if it earns it

Cursive first — 83% of pages, and where the margin is. Resumable, one document
at a time, overnight rather than in the request path (`target hardware: any PC`
means heavy work is batch work). Re-measure the index after every few hundred
documents rather than at the end, so a regression is caught while it is small.

## What would change this plan

* **A fine-tune of a permissive base on CHURRO-DS** would likely beat both rows
  of the table above; check the dataset's licence before spending anything.
* **PyLaia or Kraken** are untried, permissive, and built for historical
  cursive. Either could be cheaper per row by an order of magnitude.
* **A better crop.** Everything measured so far was the engine's own carved
  row. The engine's row-cutting is itself a source of error, and a VLM given
  a slightly generous band might read better for free.
