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
