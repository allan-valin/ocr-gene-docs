# The one document this repository is allowed to carry

`philadelphia-1800-schooner-phebe-manifest.jpg`

* **What it is.** The inward cargo and passenger manifest of the schooner
  *Phebe*, Abraham Golden master, arriving at Philadelphia from Port-de-Paix
  on 28 April 1800.
* **Where it came from.** Internet Archive item
  [`passengerlistsof0001unit`](https://archive.org/details/passengerlistsof0001unit),
  page `n121`, fetched 2026-09-07 from
  `https://archive.org/download/passengerlistsof0001unit/page/n121_w1600.jpg`.
  It is reel 1 (Jan 1 – Dec 30, 1800) of NARA microfilm publication M425,
  *Passenger lists of vessels arriving at Philadelphia, 1800–1882*, Records of
  the Bureau of Customs, Record Group 36; digitised by the Allen County Public
  Library Genealogy Center and filed under archive.org's
  `USGovernmentDocuments` collection.
* **Why it is safe to version, which is the whole point of it.** It is a work
  of the United States federal government, so it carries no copyright, and it
  was written 226 years ago: every person named on it has been dead for well
  over a century, and so has everyone who knew them. Nothing here can harm
  anybody. (Not legal advice — but the two grounds are independent, and either
  alone would do.)
* **Why this one and not any old page.** It is the same genus of document as
  the corpus this tool is for, and it carries, on one sheet, nearly every
  feature the code has been written against:
  * ruled columns under printed headings — `Marks`, `Numbers`, `Packages &
    Contents`, `by whom Shipped`, `to whom consigned`, `place of consignee's
    Residence`, `Port of Destination` — for `tablegrid` and `page_geometry`;
  * **repetition marks in three notations at once**: the word `Ditto`, the
    abbreviation `Do`, and the `"` mark running down four columns, which is
    exactly what `desembarque/ditto.py` resolves;
  * **a family sharing a surname down consecutive rows**, braced as *"above
    family"* — Jacob, Isabella, Rebecca and Peter Perere — which is the
    inheritance case the ditto rules exist for;
  * a cursive hand, because that is the only case that matters
    (`docs/TASKS-reading-quality.md`).

## What it is for, and what it is not for

It is a **fixture**: something the tests can open so they do not depend on a
corpus that lives on one machine and may not be copied off it.

It is **not a benchmark**, and `truth.json` beside it is not ground truth. That
file was transcribed by the assistant, and it says so in its own `reader`
field, because the mistake this directory exists partly to correct was labels
read by the assistant and written up as though a person had read them (see
`docs/TASKS-honest-measurement.md`). **No claim about reading quality may be
made from this page.** It is here to prove that code runs, not that it works.

Allan's own reading, when it exists, stays on his machine and out of this
history. `data/*` is ignored; this directory is the single exception, and the
reason it is allowed is the paragraph above about 1800.
