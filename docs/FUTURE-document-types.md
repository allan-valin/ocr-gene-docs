# Knowing what kind of document is on the screen

*Allan, 2026-08-29, while the name-column measurement was being fixed. A future
task, written down now because it changes how geometry is chosen and that is
easier to build in early than to retrofit.*

Everything the reader does today assumes one shape of document: a Brazilian
passenger list of 1917–1925, printed as a table, filled in by hand or by
typewriter. Every measurement in `tablegrid.py` is written against that shape,
and the two failures found today — a heading printed away from its column, a
name column measured as the ordinal strip — are both what happens when one
shape's assumptions meet another printing.

The corpus that is coming is not one shape:

* **FamilySearch** (free developer API, already noted as the cross-referencing
  source): birth, marriage and death certificates. The older ones are entirely
  handwritten; the newer ones are printed forms with handwriting in the gaps.
* **Notary books** — 100% handwritten, no ruling to speak of, running text
  rather than a table.
* **German records from the 1700s** and similar: another hand, another
  alphabet's habits, another century's abbreviations.

## What to build

1. **Identify the document type before measuring it.** The geometry to use is a
   consequence of the type, not something to guess per page. Candidate types,
   from what the corpus and the API actually hold — the list is to be filled in
   by looking, not by assuming:
   * a ruled table with printed column headings (what the reader handles today)
   * a list with rules but no headings
   * ruled lines only, no columns
   * printed body text with the important parts written in by hand
   * entirely handwritten, no ruling — the notary books
2. **A geometry profile per type**, so `tablegrid` stops being one set of rules
   with special cases bolted on. A type says which measurements even apply: a
   notary book has no name column to find, and asking for one is how a page
   comes back with nonsense on it.
3. **A document-type control in the file list**, on the left, with an icon per
   structure. The reader should be able to see what the tool thinks a document
   is, and correct it — the same rule the rest of the app follows, that a
   machine's guess is visible and a person's answer wins.

## Why it is not being done now

The reader has to work on the corpus it has before it is widened, and the
current corpus is one type. But every constant that assumes that type is a
future bug in another one — which is the argument Allan has made twice today,
and which both of today's fixes bear out: the page's own ink is the measurement,
and the printing is only a hint about where to look.

## 2026-10-09 — dynamic layout from the page's own captions (Allan's ask, deferred)

The hospedaria registers (`data/hospedaria/`) are an open-book form unlike
the passenger lists. Allan asked whether a model could tell the columns from
the OCR output and redesign the HTML layout per document. Shape agreed, not
started, after accuracy and Kubach:

1. Column schema from geometry: printed captions (engine CER 0.01) plus
   vertical rules give (caption, x0, x1) per page; vertical captions read
   after rotating the header strip.
2. Caption → canonical field through a template library, one template per
   archive form, matched by caption fingerprint; unknown form flagged and
   still read whole.
3. A local model (Qwen 7B on disk) only offline, once per new form, to
   propose a template a person confirms. Nothing in the request path.
4. The review page renders columns from `schema` on the record instead of
   fixed fields; a template may say "row continues on the next page at the
   same height", so one row shows from two scans.

## 2026-10-18 — the person draws the columns (`desembarque/regions.py`)

Before any document-type detection exists, the person can say where the
columns are: "＋ Coluna a ler" on the scan, one region per column, "Ler as
áreas". Each region is cropped and read as kraken lines, the lines put back
in page coordinates and aligned into rows by height, the first region the
name; the result lives under `custom[page]` of the record, in its own tab,
and every name-like cell is searchable. Measured on the bisavo folder:

* **Certidão de casamento 1** (ruleless double-page index: nome do marido,
  nome da mulher, ano, livro, folhas, twice): ten regions, 39 rows × 10
  cells in 29 s; Kubach's marriage on the right page's row 4, "Augusts
  Friederich Kubach | Edaliza Grillo Cordiin", found by search. The year
  headings ("1918", "1920") come out as rows of their own.
* **Certidão de casamento 2** (prose, two pages per scan): one region per
  page, 39 rows of two prose lines each in 21 s — readable lines, not a
  parsed record; prose search over them is the open item above.

This is the manual override; the detector that would find these layouts by
itself is still the work this file describes.
