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
| `ship` | name (normalized) + known aliases, shipping line, line nationality, home port, typical route/origin, source of the classification, confidence |
| `name_variant` | canonical ↔ variant pairs (e.g., Giovanni↔João), source (seed list vs. manual), growable |

`document` carries an FK to `ship`. The catalog bears this out: **910 unique ship names
across 7,679 dossiers, with 7,199 of them repeat voyages** — a ship averages ~8.4
crossings in the 1919–1924 window. Classification is therefore paid once per ship, not
per dossier.

Raw VLM JSON is stored verbatim on `page`; `person_record` rows are derived from it. Re-deriving after prompt/model changes is possible without re-calling the API.

### Ship route and origin

Classifying ships by line, nationality and route is not decoration — it feeds three
things:

1. **A language and layout prior for extraction.** Form language tracks the operating
   line, and the sampled Santos dossier is exactly this: the *Gelria* sailed for
   Koninklijke Hollandsche Lloyd, and its form is Dutch-headed. The top of the corpus
   splits along visible lines — `principe di udine` and `tomaso di savoia` (Italian),
   the Royal Mail `andes`/`avon`/`arlanza`/`almanzora` and `deseado`/`darro`/`desna`/
   `demerara` classes (British), `ruy barbosa` (Lloyd Brasileiro). Knowing the line
   before the VLM call sets the expected form language and the plausible passenger
   nationalities, which is exactly the context that reduces mangled-name errors.
2. **A name-normalization prior.** Route origin narrows which `name_variant` expansions
   are likely, so an Italian-route passenger's "João" resolves toward Giovanni rather
   than being treated as equally likely across every immigration wave.
3. **A search facet, and the genealogical entry point.** Users often know the port or
   country an ancestor left from but not the ship or date; filtering by route turns an
   unusable full-corpus scan into a short list.

Classification source: ship name → line is largely a lookup against public maritime
records, done once for ~910 names and stored with its provenance and confidence. It is
reference data, hand-checkable, and must never silently override what a document says —
if a form's language contradicts the ship's expected line, the document wins and the
mismatch is flagged.

Also present in the index: **4,105 dossiers carry an `rv` number** (195–202 in the
sampled range), sequential like the main index and parsed into the catalog already.
Likely a *registro de vapores* volume; worth resolving, as it may group voyages usefully.

## Transcription pipeline

1. Page image → light preprocessing only (resize, contrast normalization). VLMs are tolerant; no binarization/deskew complexity in v1.
2. Claude vision API call with schema-enforced structured output (tool use). Prompt requests per-field confidence self-report and explicit `null` for unreadable fields — never invented values.
3. Validation pass: dates parseable, ages numeric and plausible, required fields present; anomalies flagged.
4. Rows inserted as `unverified`, entering the review queue sorted by ascending confidence.

### Engine decision — reversed 2026-08-18

**Open-weight models, run locally. The Claude vision API is proof-of-feasibility only.**

The original decision (2026-07-23) was VLM-API-only, on the grounds that one path handles
manuscript + typewriter + multilingual + degradation while Tesseract/TrOCR/Kraken were
weaker on degraded manuscript. The 2026-08-04 addendum reaffirmed it. Both are superseded,
for two independent reasons:

1. **It violated a standing constraint.** Allan's rule — open-source dependencies and
   tooling only, explicitly covering future projects — was stated 2026-08-03, a day
   *before* the addendum that reaffirmed the proprietary engine. A commercial API is
   ruled out as the engine regardless of its benchmark performance.
2. **The API is the wrong tool for the part that is actually hard.** Extraction here
   needs *layout*: row bands and column ranges, so the review UI can put a scan beside
   its transcription and scroll them together. A chat VLM does not return reliable pixel
   coordinates — the original spec worked around this by asking the model to self-report
   bands, then conceded that self-reported confidence is "poorly calibrated." Document
   parsing models emit layout natively, and open weights additionally expose token
   logprobs, giving real per-field confidence. For a legal-evidence corpus that is the
   difference between a number that means something and a number that does not.

**Revised pipeline shape — two stages, both local:**

| Stage | Job | Candidate |
|---|---|---|
| Layout + text | page → regions, lines, row/column geometry, per-token logprobs | PaddleOCR-VL 1.5 (0.9B, open weights, benchmarked on handwriting and historical archives) |
| Semantics | text + layout → person records, ditto resolution, name normalization | a local instruct model; the schema layer is ordinary structured extraction |

Classical CV still earns its place for the ruled forms (see "Row-band alignment"), as the
cheapest and most auditable source of geometry where the form has rules to measure.

**Hardware constraint (settled 2026-08-18):** the shipped product must run on almost any
PC; Allan's machine (~14 GB RAM, no discrete GPU assumed) is the *dev* target, not the
floor. That decides the shape: transcription is a **one-time offline batch ingest on
Allan's machine**, and only derived data — transcriptions, crops, search indexes — reaches
the deployed app, which stays light enough for commodity hardware. Nothing heavy sits in a
request path, and neither Vercel nor Railway needs a GPU because inference never runs
there. Model sizing follows from this: PaddleOCR-VL at 0.9B is undemanding, and the
semantic-stage model must be chosen to fit CPU inference rather than assuming a GPU.

**What the API is still good for:** a baseline in the evaluation below. Running the golden
pages through it measures whether the local stack is close enough, which is evidence, not
a dependency.

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
  transcribed name in search results and export previews, for authorised users working
  from locally held scans. The public tier substitutes a link to the archive's copy.

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

- **Public (read-only, zero API cost):** browse processed corpus, search, export
  transcriptions. Scans are **not served publicly** — each record links out to the
  dossier's own URL on the archive's image server, so the public tier redistributes
  nothing. This limits the public demo's side-by-side view to what the archive itself
  serves; see "No document hosting".
- **Invite code unlocks:** upload, transcribe, edit. For the friend and hand-picked interviewers.
- No third-party API key in the serving path. If the Claude baseline is run for
  evaluation, it runs offline during ingest, never from a request handler.

## Export

xlsx generation per search result set or per document. Columns: all person fields +
per-field confidence + verified flag + a link to the dossier on the archive's image
server + the page and row it came from, so every exported row can be checked against the
original by anyone holding the file. Row-band crops are embedded only in exports
generated for authorised users, who already hold the scans; public exports carry the
archive link and citation instead of image data. This file is the friend's working
deliverable.

## Testing

- **Pipeline:** golden-file tests — a handful of sample pages with hand-checked expected JSON; assert extraction schema and validation behavior (VLM call mocked with recorded responses).
- **Search:** unit tests on variant expansion and fuzzy ranking.
- **API:** pytest against a test Postgres instance.
- **E2E:** Playwright smoke — browse → open review → edit a cell → export.
- **Side-by-side invariant:** assert that review and search-result views render a scan
  image element alongside every transcribed name, including when row-band data is null.
- **No-redistribution invariant:** assert the public (unauthenticated) tier serves no
  scan bytes and no crops — only archive links — for both search results and exports.
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

*Added 2026-08-04, when these were filed as post-v1. Superseded 2026-08-18: the engine
decision above now makes open-weight models the v1 engine rather than a later upgrade.
The evaluation plan at the end of this section still stands, and is now a v1 gate.*

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

**Letter-suffixed indices are catalog stubs.** Of the 70 lettered dossiers, most carry an
archival note naming where the images actually live — "s. paulo. **ver br rjanrio
bs.0.rpv, ent. 20445**". The finding aid has a record; the scans sit under a different
notation. 59 such cross-references are parsed into the catalog as `see_also`.

**Never reach a dossier by stripping the letter.** An earlier version of the downloader
fell back from `14222A` to `014222`, which resolves — to a *different dossier with a
different ship*. That would have filed the wrong scans under the record, the one failure
mode a legal-evidence corpus cannot absorb. Resolution order is now: the lettered path,
then the stated cross-reference, then probing part totals. Anything still unresolved is
reported for manual lookup, never guessed at.

**Data quality in the index itself.** The archive's own records contain errors and
annotations bleeding into titles. Beyond the cross-references: chronology notes
("notação atribuída fora da ordem cronológica"), provenance notes, and level markers all
had to be split off the ship name, which cut 910 apparent ships to 828 real ones. The Rio
pages are additionally double-corrupted — pdftotext mangles UTF-8 continuation bytes into
look-alike ASCII (`ó` → `Ã3`), so a latin-1 round-trip cannot repair them; 35 names
(0.46%) keep unrecoverable spellings and rely on ASCII-folded search to be findable.

### Date scoping

Indices are **sequential**, so the index range *is* the date range — there is no date
field to filter on at catalog time. The saved index pages were chosen to bound the
corpus to roughly **1919–1924**, which is the window of interest. Any later expansion
means saving more index pages, not changing a query.

**Fetching conduct:** this is a public archive on modest infrastructure. Serial fetches
with a delay between requests, retry with backoff (the connection is flaky), resume via
`-C -`, and never re-fetch a dossier already on disk.

**No document hosting.** Downloaded scans are gitignored and are not redistributed —
not in the repo, not from the app. The public tier links back to the archive's own URL
for each dossier rather than serving a copy. The side-by-side verification requirement
is met with the locally held working copy for authorised users; it does not authorise
republishing the archive.

## Document structure

*Two dossiers sampled directly; the corrections below come from Allan, who has been
through hundreds of these files by hand.*

**There is no standard form.** Layout appears to vary with the ship's country of origin
and with the day of processing — some dossiers are typewritten on a ruled printed table,
others are entirely handwritten, and the two series differ again from each other. The
two samples below are illustrations, not a taxonomy, and the pipeline must not assume a
fixed template:

- **BS/ENT (Santos), sampled** — printed ruled table with a form model number in the
  footer (`Mod. No. 136. 5000-6-'23`). Columns: Número, Nome e Cognomes, Nacionalidade,
  Idade, Sexo, Estado, Profissão, Procedencia, Classe, Observações. ~26 rows/page.
- **OL/PRJ (Rio), sampled** — "PARTE do Interprete" narrative form (`MODELO N. 1`),
  handwritten, photographed as landscape book spreads. Page orientation varies *within*
  a single dossier.

Design consequence: page handling is **classification-driven, not series-driven**. The
pipeline inspects each page and routes it, rather than selecting a prompt from the
dossier's series. Where a printed form model number is legible it can key a template of
known column positions; where it is absent the page falls back to generic extraction.

Findings that change the pipeline:

1. **Page classification before extraction, and it must tolerate anything.** Many
   dossiers open with a cover/notation card carrying ship, date, procedência and sheet
   count — the source for `document` metadata, not passenger data. But this is a
   function of what survived: where conservation was poor, a dossier may begin straight
   at the passenger list with no cover at all. Classification must treat the cover as
   optional and never assume page 1 is metadata.
2. **The PDFs already carry an OCR text layer, and it is unusable.** Produced by "PDF
   Compressor 8.2.12.06"; the ship name GELRIA came out `GC- £R i' A` and the date as
   `0••-3.(-)?-`. This validates the VLM-only engine decision. Keep the layer as a weak
   signal for search fallback, never as a transcription source.
3. **Ditto marks.** Repeated values (nationality, procedência) are written as `"`. The
   extraction prompt must resolve them against the row above and record the resolved
   value, or every ditto row loses its nationality.
4. **Media is mixed per cell, not per page.** A typewritten table routinely has a
   handwritten row, and the Observações column is nearly all cursive.
5. **The archive's own illegibility flag is not trustworthy.** Some pages carry a
   printed sidebar "ORIGINAL ILEGÍVEL / Original difficult to read", but in practice
   many so-flagged pages read fine — the marking reflects an operator's judgement at
   scan time, applied inconsistently. Store it as provenance, never use it to skip a
   page, deprioritise it, or excuse a failed extraction. Real page quality has to be
   assessed from the image.
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

## Review UI prototype (built 2026-08-18)

`prototype/review.html`, generated by `scripts/make_prototype.py` from a downloaded
dossier. **Local file, opened from disk — never published.** It embeds an archive page,
and those are not redistributed, which rules out hosting it anywhere including as a
shareable artifact.

Implements the side-by-side requirement end to end: scan left, rows right, bidirectional
synchronized scrolling with a lock toggle, a name-column isolate mode that dims
everything but the band being verified, inline editing with edit history, per-row verify,
and Ctrl/Cmd+F intercepted for in-document find (Shift+Ctrl+F falls through to the
browser). Confidence is shown as underlining rather than numbers; unreadable fields
render as *ilegível* in red, never as a guess; ditto-resolved cells are marked as such on
hover.

Verified on the *Gelria* (BS.ENT.017397) page 2 with 26 hand-transcribed rows:

- **Band alignment checked visually**, not assumed — every one of the 26 bands brackets
  its own row, and the name-column x-range lands exactly on "Nome e Cognomes".
- **Search behaves as the spec claims:** `LUCHETI` finds `LUCCHETI`; `vasquez` finds both
  `VAZQUEZ` and `VASQUEZ` across the OCR variant; `joao` finds `JOHN SCHRADER` through
  variant expansion, which is the Brazilianization case the design exists for.
- **Row bands here are hand-fitted to an even pitch, not detected.** Column rules are
  real (deskew + projection); row detection still fails on this page. The prototype states
  this in a banner rather than implying the geometry is automatic.

## Post-v1: external genealogy data

Deferred, but shapes the data model now — records should carry stable enough identifiers
(ship, arrival date, name as transcribed *and* as normalized) to join against outside
sources later.

| Source | Access | Use |
|---|---|---|
| [FamilySearch API](https://www.familysearch.org/developers/) | Free, developer registration, nonprofit | Cross-reference a transcribed passenger against existing genealogical records; pull name-variant evidence to grow `name_variant` from real data rather than a seed list; give the jus sanguinis workflow a path from "found the manifest row" to "found the family". |
| Ancestry | Paid, no access | Not viable. Noted only so it is not re-investigated. |

FamilySearch is a free service rather than a commercial dependency, so it does not hit the
open-source constraint the way a paid API would — but it is still an external service, so
it belongs behind an interface with its results cached locally, and nothing in the core
pipeline may depend on it being reachable. The archive transcription must stand alone as
evidence.

## Open items (pre-implementation)

- Confirm object storage choice (Railway volume vs. Cloudflare R2) once corpus size is known after download. Sampled dossiers ran 0.9 MB (3 pages) and 6.9 MB (12 pages); a full 7,679-dossier pull is plausibly ~20–40 GB of originals.
- Seed source for `name_variant` list (public genealogy variant tables).
- Re-run the row-rule detection spike at 300 DPI before committing to VLM-reported bands.
- Resolve the ~70 letter-suffixed dossiers whose image paths do not follow the rule.
