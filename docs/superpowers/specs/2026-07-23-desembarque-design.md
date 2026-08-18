# Desembarque — Design Spec

**Date:** 2026-07-23
**Status:** Approved (brainstorm session with Allan)
**Working name:** Desembarque (ship-manifest transcription + search)

## Purpose

Transcribe scanned historical documents (last 100–200 years) from ships arriving at Brazilian ports into structured, searchable passenger records, with a human verification workflow and Excel export.

Dual goal:

1. **Portfolio piece for interviews** — hosted, demoable in 30 seconds, code demonstrates full-stack + data-pipeline engineering. Not domain-specific signaling; "shows that I do stuff."
2. **Real user** — Allan's friend works with dual-nationality acquisition through bloodline (jus sanguinis). They need verified passenger records: find an ancestor by name, confirm against the original scan, export evidence.

Origin: existing archive indexes (Arquivo Nacional, APESP, FamilySearch) did not contain the information Allan needed — hence building rather than reusing.

## Corpus properties

- Mixed media: typewriter fonts and manuscript (handwritten) pages
- Heavy degradation — many pages barely readable
- Multilingual: pt-BR plus ship-origin languages (it/de/es/pl/ja and others, per Brazilian immigration waves)
- Names mangled twice: clerks Brazilianized them at entry (Giovanni→João, Wilhelm→Guilherme), then OCR mangles again
- Legal-evidence use → transcription fidelity matters; no silent guesses. Every extracted row carries confidence and traces back to its source image.

## Architecture

```
Next.js (Vercel)  ──►  FastAPI (Railway)  ──►  Postgres (+pg_trgm)
      │                     │
      │                     └──► Claude vision API (transcription)
      └── serves: gallery, review UI, search, xlsx export
Scans: object storage (Railway volume or Cloudflare R2) + web-optimized derivatives
```

- **Frontend:** Next.js (App Router) on Vercel free tier. Pages: corpus browser, document review (side-by-side), search, about/methodology.
- **Backend:** FastAPI on Railway (~$5/mo) with Postgres. Endpoints: ingest, transcribe, documents CRUD, search, export.
- **Job queue:** Postgres-backed task table polled by a worker loop inside the FastAPI service. No Redis/Celery — deliberately simple.
- **Ingestion:** CLI script in the repo. Points at a folder of scans (Allan downloads archive scans manually, once), uploads originals to object storage, generates web-optimized derivatives, queues transcription jobs.
- **Stack rationale:** React + Python covers the widest interview surface (JS ecosystem + Python data work). Allan's existing portfolio (workout app, zbor translator) is mobile; this is the web/backend piece.

## Data model

| Table | Fields (essentials) |
|---|---|
| `document` | scan image ref, port, ship name, arrival_date, source archive reference, language guess, processing status |
| `page` | FK document, image ref, raw VLM output JSON, model id + prompt version (reproducibility), name-column x-range (advisory, nullable), status |
| `person_record` | FK page, surname, given_names, age, sex, nationality/origin, occupation, family_group_id, per-field confidence, row y-band (advisory, nullable), `verified` flag, edit history (editor, timestamp, original value) |
| `name_variant` | canonical ↔ variant pairs (e.g., Giovanni↔João), source (seed list vs. manual), growable |

Raw VLM JSON is stored verbatim on `page`; `person_record` rows are derived from it. Re-deriving after prompt/model changes is possible without re-calling the API.

## Transcription pipeline

1. Page image → light preprocessing only (resize, contrast normalization). VLMs are tolerant; no binarization/deskew complexity in v1.
2. Claude vision API call with schema-enforced structured output (tool use). Prompt requests per-field confidence self-report and explicit `null` for unreadable fields — never invented values.
3. Validation pass: dates parseable, ages numeric and plausible, required fields present; anomalies flagged.
4. Rows inserted as `unverified`, entering the review queue sorted by ascending confidence.

Engine decision: **VLM API only.** One path handles manuscript + typewriter + multilingual + degradation. Classical OCR (Tesseract) and local models (TrOCR/Kraken) rejected for v1: weaker on degraded manuscript, more moving parts. Cost is pennies per page.

## Review/correction UI (demo centerpiece)

**Core requirement — side-by-side human verification.** Any view where a transcribed
value is presented for verification MUST show the original scan and the transcription
together on screen, so a human can read one against the other without navigating away.
At minimum the name column of the original document must be legible next to the
transcribed name. Verification is the product's trust anchor (legal-evidence use);
a transcription shown without its source is not verifiable.

- Split view: zoomable scan image left, extracted rows right.
- **Synchronized scrolling.** The two panes are locked to each other: scrolling either
  one moves the other so the row under the cursor on the right sits at the same vertical
  position as its band on the scan. Driven by the row y-bands (see "Row-band alignment").
  Bidirectional, and debounced so the follow-scroll never fights the user's own scroll.
  A lock toggle lets the user break the coupling when they want to read one side freely;
  the toggle state persists per session.
- Click a row → row highlights, and the image pane scrolls/zooms to that row's
  horizontal band on the scan.
- Inline cell editing; every edit recorded in edit history.
- "Mark verified" per row and per page.
- Review queue view: lowest-confidence-first ordering.
- Keyboard-driven flow (tab/enter through fields) — the friend's throughput matters.

### In-document find

- Persistent search field in the review UI header, also bound to **Ctrl/Cmd+F**. The app
  intercepts the shortcut and opens its own find widget rather than the browser's —
  native find only sees rendered DOM, which misses rows scrolled out of a virtualized
  list and cannot reach the scan at all.
- Searches the transcribed fields of the current document (all pages, not just the
  visible one). Same matching as global search — fuzzy + phonetic + `name_variant`
  expansion — so a hunted name is found despite OCR mangling.
- Matches: highlighted in the rows pane, count + next/prev (Enter / Shift+Enter),
  Escape closes. Jumping to a match scrolls both panes together via the sync above,
  so the scan lands on the matched row.
- Escape hatch: a "use browser find" hint, since Ctrl+F interception is a shortcut the
  user did not ask for. Interception applies only inside the review view.

### Row-band alignment (v1)

Full bounding boxes per field stay deferred, but "at least the name column" needs
*some* image→row correspondence. v1 approach:

- Transcription prompt additionally requests, per person row, the vertical extent of
  that row on the page as a normalized `y_top`/`y_bottom` pair (0–1). Coarse is fine —
  a horizontal band, not a box.
- Also requested once per page: the normalized `x_left`/`x_right` of the name column.
- Both are stored on `page`/`person_record` and are **advisory**: if the model returns
  null or implausible values, the UI falls back to the whole-page image. Selection and
  verification never depend on them being correct.
- Derived crop = name-column x-range × row y-band → the thumbnail shown beside the
  transcribed name in search results and export previews.

This keeps v1 free of a layout-detection stage while making the side-by-side
requirement satisfiable everywhere a single row is shown out of page context.

Row bands are also what makes scroll sync possible. Where bands are null for a page,
sync degrades to proportional scrolling (fraction of rows ↔ fraction of page height) —
approximate but still useful, and never wrong enough to mislead, since the user reads
the scan itself.

## Search

- `pg_trgm` fuzzy matching (catches OCR typos)
- Phonetic matching (double-metaphone-style, tuned for pt/it/de spelling conventions)
- `name_variant` expansion: query "Giovanni Rossi" also matches "João Rossi", "Giov. Rosi", etc.
- Results display: matched record beside its scan snippet (the name-column crop for
  that row, falling back to the page thumbnail), verified badge, link into review UI.
  A search hit is never shown as transcribed text alone.

This is the feature that serves the jus sanguinis use case and the strongest interview story.

## Access model / demo economics

- **Public (read-only, zero API cost):** browse processed corpus, search, view scans, export.
- **Invite code unlocks:** upload, transcribe, edit. For the friend and hand-picked interviewers.
- Claude API key lives server-side only. Spend cap via environment variable; transcription jobs refuse to run past it.

## Export

xlsx generation per search result set or per document. Columns: all person fields + per-field confidence + verified flag + source image URL + row-crop URL (the name-column band), so the exported file stays independently verifiable against the scans. This file is the friend's working deliverable.

## Testing

- **Pipeline:** golden-file tests — a handful of sample pages with hand-checked expected JSON; assert extraction schema and validation behavior (VLM call mocked with recorded responses).
- **Search:** unit tests on variant expansion and fuzzy ranking.
- **API:** pytest against a test Postgres instance.
- **E2E:** Playwright smoke — browse → open review → edit a cell → export.
- **Side-by-side invariant:** assert that review and search-result views render a scan
  image element alongside every transcribed name, including when row-band data is null.
- **Scroll sync:** unit test the row-band → scroll-offset mapping (incl. null bands and
  the unlocked state); Playwright check that scrolling one pane moves the other.
- **Find:** Ctrl/Cmd+F opens the in-app widget, matches across non-visible pages, and
  jumping to a match moves both panes.

## v1 scope

**In:** everything above.

**Out (explicitly deferred):**

- Per-field bounding-box overlays (v1 has coarse row bands only, see "Row-band alignment")
- Multi-user accounts/auth beyond the invite code
- Family-tree linking between records
- Additional archives beyond the initial corpus
- Automatic name-variant learning from corrections
- Open-weight local transcription models (see "Post-v1: open-weight OCR models" below)

## Post-v1: open-weight OCR models

*Added 2026-08-04. Does not change the v1 engine decision above (Claude vision API only).*

Two Baidu open-weight document models are worth revisiting after v1 ships:

| Model | Released | License | Angle |
|---|---|---|---|
| [Unlimited-OCR](https://github.com/baidu/Unlimited-OCR) | 2026-06-22 | MIT | One-shot parsing of long multi-page documents; sliding-window attention keeps the KV cache flat across dozens of pages in a 32K context. SOTA on OmniDocBench v1.5/v1.6 (~93%). Published size is reported inconsistently (3B dense vs. 30B-A5B MoE) — verify before sizing hardware. |
| [PaddleOCR-VL 1.5](https://arxiv.org/pdf/2601.21957) | 2025-10 (1.5 in 2026) | Open weights | 0.9B, 100+ languages, explicitly benchmarked on handwriting and historical archives. Runs on far less hardware; closer to this corpus than Unlimited-OCR's long-PDF angle. |

**Why they are not v1:** both are document *parsing* models (layout → structured text), not the semantic field extraction this pipeline needs — the person-record schema layer still requires an LLM on top. Their headline benchmark (OmniDocBench) is modern printed and scanned material and says nothing about 19th-century manuscript pt-BR. Neither Vercel nor Railway offers a GPU, so self-hosting reintroduces exactly the infrastructure the v1 engine decision removed, for no v1 benefit.

**Why they matter later:**

1. **Calibrated confidence.** Pipeline step 2 currently relies on the model's *self-reported* per-field confidence, which is poorly calibrated. Open weights expose token logprobs, giving real per-field confidence — the strongest argument for a local model given the legal-evidence use case.
2. **Bulk ingestion cost ceiling.** Pennies per page is fine for a demo corpus, not for a whole archive. Local batch inference removes the marginal cost.
3. **Fine-tuning flywheel.** The review UI produces hand-verified rows, i.e. exactly the ground truth needed to fine-tune on Brazilian manifest layouts. A closed API cannot use this.
4. **Cross-page context.** Family groups split across page breaks; whole-manifest one-shot parsing could resolve them.

**How to evaluate cheaply:** the golden-file sample pages built for pipeline tests (see Testing) are already hand-checked ground truth. Run ~5 of them through Claude, Unlimited-OCR, and PaddleOCR-VL 1.5 and compare word error rate on name fields specifically. This is a spike, not v1 work.

## Corpus acquisition (verified 2026-08-18)

The SIAN search UI sits behind a login, but the derived image files are served
unauthenticated from `imagem.sian.an.gov.br`. Corpus listing therefore works in two
steps: save the search result pages as PDF (done — `indices/`), parse them into a
catalog, then fetch each dossier by constructed URL.

`scripts/parse_index.py` does the parsing. Over the 11 saved index pages it yields
**7,679 unique dossiers** (0 duplicates — the saved pages are disjoint), 8 without a
parseable ship name, 70 with a letter-suffixed index.

### URL scheme

```
https://imagem.sian.an.gov.br/acervo/derivadas/BR_RJANRIO_{FUNDO}/0/RPV/{SERIES}/{FOLDER}/BR_RJANRIO_{FUNDO}_0_RPV_{SERIES}_{FOLDER}_d{NNNN}de{TOTAL}.pdf
```

| Rule | Detail |
|---|---|
| Santos | fundo `BS`, series `ENT`; folder is the index **zero-padded to 6** (`17397` → `017397`) |
| Rio | fundo `OL`, series `PRJ`; folder is the index **unpadded** (`17322`) |
| Letter suffix | pad the digits only, keep the letter: `14091A` → `014091A`. Server is case-insensitive. The lettered dossier is *distinct* from the unlettered one of the same number — both can exist. |
| Multi-file | `d{part}de{total}`; `total` is the dossier's file count and is not in the index. Unknown until fetched. |

**Construction is a guess, not a fact.** Spot checks: plain indices resolved in both
series, but of three lettered ones tested, `014091A` returned 200 while `014222A` and
`014744A` 404'd at every `de000N` — though plain `014222` exists. So a letter in the
catalog does not guarantee a lettered file path. The downloader needs a fallback ladder
(lettered → unlettered → probe increasing `total`) and must record unresolved dossiers
for manual lookup rather than silently skipping. Affects ~70/7,679 (0.9%).

**Fetching conduct:** this is a public archive on modest infrastructure. Serial or
low-concurrency fetches, retry with backoff (the connection to it is flaky), resume via
`-C -`, and cache aggressively — never re-fetch a dossier already on disk. Before the
scans are rehosted on a public demo, check Arquivo Nacional's terms of use and attribute
the source; linking back rather than rehosting is the safer default for the public tier.

## Document structure (from two sampled dossiers)

The two series are **different document types**, not variants of one:

- **BS/ENT (Santos)** — printed ruled table, form model number in the footer
  (e.g. `Mod. No. 136. 5000-6-'23`). Columns: Número, Nome e Cognomes, Nacionalidade,
  Idade, Sexo, Estado, Profissão, Procedencia, Classe, Observações. ~26 rows/page,
  entries mostly typewritten.
- **OL/PRJ (Rio)** — "PARTE do Interprete" narrative form (`MODELO N. 1`), fully
  handwritten, photographed as landscape book spreads; passenger lists are separate
  attached pages. Page orientation varies *within* a dossier.

Findings that change the pipeline:

1. **Page classification is required before extraction.** Every dossier opens with a
   cover/notation card carrying ship, date, procedência and sheet count — that is the
   source for `document` metadata, and it is not passenger data. Pages must be typed
   (cover / passenger table / narrative / blank) and routed to different prompts.
2. **The PDFs already carry an OCR text layer, and it is unusable.** Produced by "PDF
   Compressor 8.2.12.06"; the ship name GELRIA came out `GC- £R i' A` and the date as
   `0••-3.(-)?-`. This validates the VLM-only engine decision. Keep the layer as a weak
   signal for search fallback, never as a transcription source.
3. **Ditto marks.** Repeated values (nationality, procedência) are written as `"`. The
   extraction prompt must resolve them against the row above and record the resolved
   value, or every ditto row loses its nationality.
4. **Media is mixed per cell, not per page.** A typewritten table routinely has a
   handwritten row, and the Observações column is nearly all cursive.
5. **The archive flags its own bad scans.** Some pages carry a printed sidebar
   "ORIGINAL ILEGÍVEL / Original difficult to read" — worth detecting and storing as a
   page-level quality flag feeding the review queue ordering.
6. **Image specs:** 300 DPI, ~3600×5000, grayscale or RGB, JPX/JPEG with a JBIG2 soft
   mask. Extract with `pdfimages` rather than re-rasterizing.

### Row-band alignment — status

The v1 plan assumed the VLM would report row y-bands. The sampled Santos form is a
*ruled printed table*, which suggests a cheaper and better-calibrated route: detect the
rules geometrically and derive bands from them, with column x-ranges as per-template
constants keyed by the printed form model number rather than per-page model output.

A first projection-profile attempt at 90 DPI failed — it found only the scan's black
border, because the table rules are too faint at that resolution. Not disproven, just
untested: retry at 300 DPI with the border cropped first. Until that spike passes, the
VLM-reported bands remain the plan, with proportional fallback as specified.

## Open items (pre-implementation)

- Confirm object storage choice (Railway volume vs. Cloudflare R2) once corpus size is known after download. Sampled dossiers ran 0.9 MB (3 pages) and 6.9 MB (12 pages); a full 7,679-dossier pull is plausibly ~20–40 GB of originals.
- Seed source for `name_variant` list (public genealogy variant tables).
- Re-run the row-rule detection spike at 300 DPI before committing to VLM-reported bands.
- Resolve the ~70 letter-suffixed dossiers whose image paths do not follow the rule.
