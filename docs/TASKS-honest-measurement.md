# Honest measurement: tasks

Written 2026-09-07, after Allan took the metric apart. The conclusion is
uncomfortable and it comes first, because everything below follows from it.

## What is wrong with every number this repository has quoted

**The 138-name benchmark is mostly not ground truth.** Six pages in `data/truth`
carry 156 hand-read names. Exactly one file — `BS_ENT_013947-p2.json`, 14 names
— records who read it, and it is Allan, on 2026-08-28, written down in
`docs/superpowers/plans/2026-08-28-reading-quality.md`. The other five say
*"hand-read from the scan by eye"* and name nobody. They were written on the
19th and 21st of August inside working sessions, their cautions hedge in the
first person about the reader's own uncertainty, and Allan's recollection is
that he supplied *about ten names, once*.

The honest reading is that **142 of the 156 labels are the assistant's own
reading of the scan images**, presented in wording that implies a human. That
cannot be proved from this repository — `data/` is not versioned and no
document records a reader — but the balance of evidence says it, and nothing
downstream should be trusted as if it were settled otherwise.

Three consequences, and they are not small:

1. **The labels' errors correlate with the engine's.** Both fail on the same
   illegible rows, so a hard row that both get wrong the same way scores as
   correct. The bias runs in the flattering direction, and hardest exactly on
   the cursive pages, which are the point (see
   `docs/TASKS-reading-quality.md`, T11 and the 2026-09-03 section).
2. **Selection bias on top of it.** The one genuinely human page records only
   *"the ones he was sure of"* — 14 rows of 41. The illegible rows are absent
   from the measure by construction.
3. **Every threshold in the system was tuned against this set**, with no
   held-out data anywhere. So the small deltas this repository is built on —
   +1, +3, +4 names of 138, 1% to 3% — are inside the noise of a set that the
   thing being measured helped write. **They should be treated as unproven, not
   as gains.** The re-read is the exception: +166% in findable rows is measured
   over all 71,000 rows of the corpus and needs no truth set at all.

**So the first job is not to improve the reading. It is to be able to tell
whether the reading improved.**

---

## T1 — The truth file format, and it must exist before Allan reads anything

**Done 2026-09-08.** `desembarque.truthset` loads it: `load_page`, `load_pages`,
`parse_cell`, the three classes kept apart, a file with no `reader` refused.
The old six load unchanged. `pairs` reads the shorthand too, so an unreadable
row never goes to the index as an empty query.


Allan is preparing a ground-"truth" file. The quotes are his and they are the
design requirement: *"when the handwriting is bad, I can't tell myself what they
mean."* A row he cannot read is **data, not a gap** — it is the most interesting
class in the set, because a recogniser that produces confident text there is
either better than a person or hallucinating, and the current format cannot tell
those apart.

**Every row on the page is recorded, including the ones nobody can read.** That
is what fixes consequence (2) above, and it is the only part of this that Allan
has to do by hand.

```json
{
  "pdf": "BR_RJANRIO_BS_0_RPV_ENT_016429_d0001de0001.pdf",
  "page": 2,
  "hand": "cursive",
  "reader": "Allan",
  "read_on": "2026-09-08",
  "complete": true,
  "rows": {
    "1": "José Fernandes",
    "2": "?José Guberti",
    "3": "",
    "4": "?Lorenzo ?",
    "5": "-"
  }
}
```

Shorthand, so the reading is not slower than it has to be:

| what is written | what it means |
|---|---|
| `José Fernandes` | read it, sure of it |
| `?José Guberti` | read it, **not** sure — a leading `?` marks the whole row uncertain |
| `?Lorenzo ?` | sure of one word, the other is unreadable |
| `""` (empty) | **cannot read it**, and that is the answer |
| `-` | no row there — a rule, a blank line, a struck-through space |

* `hand` is `typed`, `cursive` or `mixed`, per page not per document.
* `complete: true` asserts every band on the page is accounted for, which is
  what lets an unreadable row count against a recogniser that invents one.
* `reader` is required. Any file without it is not evidence — that is the whole
  lesson above.

**Acceptance:** a loader in `desembarque/truthset.py` that reads this shape,
keeps the three classes apart, and refuses a file with no `reader`. Tests for
each shorthand. The old six files load unchanged, with `reader` filled in as
what it actually was.

## T2 — Say who read the old six files

**Done 2026-09-08.** Five say `assistant` and carry the warning in their own
caution field; one says `Allan`. Each also carries the hand its caution
described, which is what T3 needed.


Rewrite the `source` field of each of the six existing truth files to state
plainly who read it, and mark the five that were not Allan's as
`reader: "assistant"`. Then every number quoted from them carries its own
warning wherever it is read next. No measurement, no code — an honest label.

## T3 — Split every reported number by hand

**Done 2026-09-08.** `--matrix` prints per hand and blended, and the header
says who read what. It also found that the rows form — Allan's page, the only
one a person read — was being skipped entirely: 152 names, not 138. Measured
that day: cursive 52/67/75 of 110, typed 41/41/41 of 42, at the top 5/10/20.
Restated in `docs/PROGRESS.md`.


The 138 is one blended figure over pages of unlike difficulty, and it flatters
badly:

| | found in the top 5 |
|---|---|
| typed pages (2 of 6) | 41/42 — **98%** |
| cursive pages (4 of 6) | 46/96 — **48%** |
| blended, as quoted all along | 87/138 — 63% |

The typed pages are 30% of the set and effectively solved, so they have been
inflating every score in `docs/PROGRESS.md`. `bench_search.py --matrix` prints
two rows from now on, or it prints nothing.

**Acceptance:** the matrix reports typed and cursive separately, and
`docs/PROGRESS.md`'s headline numbers are restated as a pair.

## T4 — Classify all 660 documents typed or cursive

**Done 2026-09-08.** `desembarque.hands` + `scripts/classify_hands.py`, writing
`data/hands.json`. Cut at 0.91 median surname confidence, which is the middle
of the gap the six known pages leave (cursive 0.640–0.869, typed 0.952–0.989);
6 of 6 right. **658 documents, 2,543 pages: 83% of the pages it can call are
cursive.** 163 pages sit within 0.03 of the cut and `--check` reports them.


Needed to draw a stratified sample, and useful on its own — the tool should
know which of its documents are the hard ones. The engine's own confidence
separates the two nearly perfectly on the six pages we have (typed pages read
back as `Eliza da Costa Guimaraes`, cursive as `Jogriey elborgues`), so this is
a threshold on a number already stored, not new reading.

**Acceptance:** a per-page label on disk, and its accuracy measured against the
six pages whose hand we know.

## T5 — The held-out set, drawn at random and never tuned on

**Built 2026-09-08, waiting on a reader.** `scripts/make_reading_sheet.py`
writes the sheet (10 pages, 361 rows, 4 MB, self-contained, asks who is
reading), `scripts/import_reading_sheet.py` takes it back into
`data/truth-heldout` refusing anything unlabelled, and `bench_search.py
--matrix --held-out` scores it. Nothing else is blocked on code here.


Allan's design, which is better than measuring corpus-wide: keep improving
against the existing set, and **estimate honestly on a random draw from the
other 655 documents**.

The draw is already made, so that neither of us can pick the easy ones. Seed
`20260907`, the five documents already in the truth set excluded, recorded here
so it can be audited and not re-rolled:

1. `BR_RJANRIO_BS_0_RPV_ENT_016429_d0001de0001.pdf`
2. `BR_RJANRIO_BS_0_RPV_ENT_016079_d0001de0001.pdf`
3. `BR_RJANRIO_OL_0_RPV_PRJ_17318_d0001de0001.pdf`
4. `BR_RJANRIO_BS_0_RPV_ENT_016317_d0001de0001.pdf`
5. `BR_RJANRIO_OL_0_RPV_PRJ_19747_d0001de0001.pdf`
6. `BR_RJANRIO_BS_0_RPV_ENT_016762_d0001de0001.pdf`
7. `BR_RJANRIO_OL_0_RPV_PRJ_17627_d0001de0001.pdf`
8. `BR_RJANRIO_BS_0_RPV_ENT_016890_d0001de0001.pdf`
9. `BR_RJANRIO_OL_0_RPV_PRJ_18396_d0001de0001.pdf`
10. `BR_RJANRIO_BS_0_RPV_ENT_015306_d0001de0001.pdf`

**Take them in this order and stop whenever you like** — a prefix of a random
list is still a random sample, so the estimate stays honest at three pages or
at ten. One page from each document is enough.

**The rule this set exists for: nothing is ever tuned against it.** It is read
once per real change, and if a change that gained on the old set gains nothing
here, the gain was overfitting and comes out.

**Acceptance:** `bench_search.py --held-out` scores this set separately, and
`docs/PROGRESS.md` reports both numbers side by side, always.

## T6 — Try CHURRO before building anything else

**Measured 2026-09-08, and it is the biggest result this project has had.**

It runs here: quantised to Q4_K_M (1.9 GB of weights, 1.3 GB vision projector)
under llama.cpp, **4.4 to 5.1 seconds a row** on eight CPU threads, which is
the same order as the engine's own 4.33 s. `scripts/read_churro.py`.

Against the 155 labelled rows of `data/trainset-fair`, and split by the hand
each page is written in — which is the only way to read this table:

| page | hand | CHURRO CER | engine CER |
|---|---|---|---|
| BS_ENT_013947-p2 | cursive | **0.073** | 0.200 |
| BS_ENT_013947-p3 | cursive | **0.529** | 0.601 |
| BS_ENT_014541-p2 | cursive | **0.304** | 0.371 |
| BS_ENT_015061-p6 | cursive | **0.237** | 0.349 |
| BS_ENT_013981-p2 | typed | 0.293 | **0.252** |
| BS_ENT_013983-p2 | typed | 0.160 | **0.010** |
| all 155 rows | mixed | 0.327 mean / 0.200 median | 0.369 / 0.300 |

**It wins on every cursive page and loses on both typed ones.** The previous
best second opinion managed 0.560. It spells a name the archive's own gazetteer
knows, where the engine's reading spells none, on **76 of 155 rows**.

And through the index — `bench_search.py --matrix --second-opinion
data/churro-rows.json`, the number that decides things:

| cursive, by name alone | top 5 | top 10 | top 20 |
|---|---|---|---|
| engine as it ships | 52 | 67 | 75 |
| with CHURRO's reading | **85** | **93** | **103** |

of 110 names. **+63% at the top five**, far past the two-digit bar, on the
hand that is the entire point.

Two biases pull in opposite directions and neither is small: the labels are
mostly the assistant's own reading and their errors correlate with the
*engine's*, which flatters the engine; and CHURRO here read only the rows the
queries ask for, so the other 30,000 indexed rows did not get better readings
that might compete for rank. The held-out set (T5) is what settles it.

**What was also tried and is settled:**

* **The name column in one look** — one inference for forty rows instead of
  forty. It reads *worse*: every `Maria` on the page came back `Elbria`, and
  it returned forty lines for fifty bands, which is the row-pairing problem
  again. Per-row crops cost the same and read what is there.
* **Q8_0 instead of Q4_K_M** — 0.339 against 0.327, so no better, and 40%
  slower. The quantisation is not what limits it.

**The blocker, and it is not technical.** CHURRO inherits **Qwen-Research**
terms: open weights, research use, no commercial use. `LICENSING.md` plans a
commercial licence beside the AGPL, and Allan's standing rule is open source
only. So this result is *evidence about a class of model*, not a component
that ships. The routes that stay open, in order of how much they are worth:

1. **A permissively licensed VLM of the same shape.** Qwen2.5-VL-7B-Instruct
   is Apache-2.0 where the 3B is not. Bigger and slower, and not trained on
   historical hands — CHURRO's own paper puts the best untuned open-weight VLM
   at 54.5% against its 70.1% — so measure before believing.
2. **Fine-tune a permissive base on CHURRO-DS**, checking the dataset's own
   licence first.
3. **PyLaia and Kraken**, still untried, both permissive and both built for
   historical cursive.

**Route by hand, whatever wins.** T4 labels every page typed or cursive off
confidence already stored, and this table is the argument for using it: the
engine is far better on typed pages, a historical VLM is far better on cursive
ones, and 83% of the corpus is cursive. Neither reads everything.

**Cost, honestly.** 5 s a row is 85 hours for the whole corpus — the same order
as the re-read, and not a thing to run casually. Per document it is 3–4 minutes
for a 40-row page, which is a reasonable "read this one properly" button and an
unreasonable batch.

---

### The original task, as written 2026-09-07


A 3B-parameter **open-weight** vision-language model specialised for historical
text: [arXiv 2509.19768](https://arxiv.org/pdf/2509.19768),
`github.com/stanford-oval/Churro`. Trained on 99,491 pages across 46 language
clusters including Portuguese, Spanish and Italian. **70.1%** normalised
Levenshtein similarity on handwritten material against Gemini 2.5 Pro's 63.6%,
and the best open-weight VLM otherwise tested managed 54.5%.

This repository has scored five pretrained recognisers (2026-09-03) and every
one was a TrOCR variant. This is a different class of model and was never tried.
It is plausibly worth more than everything measured on 2026-09-07 put together.

**T1–T5 are done as of 2026-09-08, so this is now the next work.**

**In order, and stop at the first failure:**
1. **Does it run here at all?** 3B on a 14 GB CPU box with no GPU. Measure
   seconds per page before anything else; if it is minutes, it is a
   non-starter for 660 documents and that is the answer.
2. Score it on `data/bands-fair` + `data/trainset-fair` with
   `scripts/score_crops.py`, against the engine's CER 0.365 and the second
   opinion's 0.560. It is a *page*-level model, so it may want the page rather
   than the row crop — which would also skip the row-cutting the engine's
   errors partly come from.
3. Only then the index: `bench_search.py --matrix`, on the old set **and** T5's.

Also untried and open source, if CHURRO does not run: **PyLaia** with a
language model, and **Kraken**, both built for historical cursive.
**Transkribus Titan** reaches 8.0% CER and has table models for exactly this
manifest shape — it is proprietary, so it is out under the open-source rule,
but it is the honest ceiling to compare against.

## T7 — Characters and strokes, not whole names

Allan, 2026-09-07: *"maybe focusing on getting the singular letters and strokes
right could lead to some improvements."* The literature agrees, and it says two
things this repository has been doing the opposite of:

* Post-correction has to be **character-level**, because over- and
  under-segmentation are invisible at word level. The ICDAR 2026
  **HIPE-OCRepair** competition names the four classes to target — over-
  segmentation, under-segmentation, misrecognised characters, missing
  characters — and a competing pipeline reports a **27% CER improvement**
  ([arXiv 2607.08143](https://arxiv.org/html/2607.08143)). That is an order of
  magnitude above any change made here.
* **Lexicon methods break on out-of-vocabulary terms**, and this corpus is rare
  immigrant surnames — the worst case. `desembarque/gazetteer.py` *is* a
  lexicon, built from the corpus itself, so the stroke rules can only ever
  reach a name the archive already knows. The circularity in the metric is the
  same circularity in the design.

**Not started until T1–T5 are done**, because it is precisely the kind of work
whose 1–3% claims cannot currently be told from noise.

## T8 — Finish the corpus re-read when the machine is free

Stopped 2026-09-07 at 172 of 660 documents, ~10 hours left, resumable — a page
already in `data/reread-index` is skipped:

```sh
.venv-ocr/bin/python scripts/export_bands.py --records data/transcriptions \
    --out data/reread-index --write-records data/reread --no-crops
```

Then `scripts/compare_corpora.py`. This is the one result on the table that
does not depend on the truth set: **+166% findable rows on the documents it has
reached**, 8,045 → 21,393, every human-typed row verbatim. It is also the only
thing measured today that clears Allan's bar of a two-digit percentage.

## What is now closed, and is not to be raised again

* **The second recogniser.** Built, measured, priced: 26.3 h of machine for
  three more names in the top five of 138 — about 2%, below the bar, and inside
  the noise of a truth set the assistant partly wrote. `second_read` stays in
  the schema and `apply_second_opinion.py` stays on disk; neither is run.
* **Gating the second reading on the review check.** Measured: the check flags
  88.5% of the corpus, so there is nothing to gate.
* **Tuning search against the 138 for gains of one to four names.** Every such
  change is unproven until T5 exists.
