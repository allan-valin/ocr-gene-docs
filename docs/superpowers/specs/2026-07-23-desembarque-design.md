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
| `page` | FK document, image ref, raw VLM output JSON, model id + prompt version (reproducibility), status |
| `person_record` | FK page, surname, given_names, age, sex, nationality/origin, occupation, family_group_id, per-field confidence, `verified` flag, edit history (editor, timestamp, original value) |
| `name_variant` | canonical ↔ variant pairs (e.g., Giovanni↔João), source (seed list vs. manual), growable |

Raw VLM JSON is stored verbatim on `page`; `person_record` rows are derived from it. Re-deriving after prompt/model changes is possible without re-calling the API.

## Transcription pipeline

1. Page image → light preprocessing only (resize, contrast normalization). VLMs are tolerant; no binarization/deskew complexity in v1.
2. Claude vision API call with schema-enforced structured output (tool use). Prompt requests per-field confidence self-report and explicit `null` for unreadable fields — never invented values.
3. Validation pass: dates parseable, ages numeric and plausible, required fields present; anomalies flagged.
4. Rows inserted as `unverified`, entering the review queue sorted by ascending confidence.

Engine decision: **VLM API only.** One path handles manuscript + typewriter + multilingual + degradation. Classical OCR (Tesseract) and local models (TrOCR/Kraken) rejected for v1: weaker on degraded manuscript, more moving parts. Cost is pennies per page.

## Review/correction UI (demo centerpiece)

- Split view: zoomable scan image left, extracted rows right.
- Click a row → row highlights (no image-region bounding boxes in v1).
- Inline cell editing; every edit recorded in edit history.
- "Mark verified" per row and per page.
- Review queue view: lowest-confidence-first ordering.
- Keyboard-driven flow (tab/enter through fields) — the friend's throughput matters.

## Search

- `pg_trgm` fuzzy matching (catches OCR typos)
- Phonetic matching (double-metaphone-style, tuned for pt/it/de spelling conventions)
- `name_variant` expansion: query "Giovanni Rossi" also matches "João Rossi", "Giov. Rosi", etc.
- Results display: matched record, scan snippet, verified badge, link into review UI.

This is the feature that serves the jus sanguinis use case and the strongest interview story.

## Access model / demo economics

- **Public (read-only, zero API cost):** browse processed corpus, search, view scans, export.
- **Invite code unlocks:** upload, transcribe, edit. For the friend and hand-picked interviewers.
- Claude API key lives server-side only. Spend cap via environment variable; transcription jobs refuse to run past it.

## Export

xlsx generation per search result set or per document. Columns: all person fields + per-field confidence + verified flag + source image URL. This file is the friend's working deliverable.

## Testing

- **Pipeline:** golden-file tests — a handful of sample pages with hand-checked expected JSON; assert extraction schema and validation behavior (VLM call mocked with recorded responses).
- **Search:** unit tests on variant expansion and fuzzy ranking.
- **API:** pytest against a test Postgres instance.
- **E2E:** Playwright smoke — browse → open review → edit a cell → export.

## v1 scope

**In:** everything above.

**Out (explicitly deferred):**

- Bounding-box overlays linking fields to image regions
- Multi-user accounts/auth beyond the invite code
- Family-tree linking between records
- Additional archives beyond the initial corpus
- Automatic name-variant learning from corrections

## Open items (pre-implementation)

- Confirm object storage choice (Railway volume vs. Cloudflare R2) once corpus size is known after manual download.
- Seed source for `name_variant` list (public genealogy variant tables).
