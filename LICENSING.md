# Licensing

**Desembarque is licensed under the GNU Affero General Public License v3.0 or later
(AGPL-3.0-or-later).** The full text is in [`LICENSE`](LICENSE).

Copyright © 2026 Allan Valin.

## Why AGPL, given the plan might include selling access

The goal is to keep the option of both giving it away and selling it. AGPL supports both:

* **Anyone may use, study, modify and share it for free.** That is the default, and it is
  what a person tracing their own family should get.
* **Anyone who modifies it and offers it to others over a network must publish their
  changes.** This is the clause plain GPL lacks. It matters here specifically because a
  hosted version is on the table: under GPL a competitor could take this code, run it as a
  paid service, and publish nothing. Under AGPL they cannot.
* **The copyright holder is not bound by the AGPL.** As sole author, Allan can grant
  separate proprietary licences on whatever terms he likes — the standard "open core /
  dual licence" arrangement. Selling a commercial licence to a firm that does not want
  AGPL obligations is entirely compatible with this file.

### The one condition that keeps that possible

Dual licensing only works while **one party holds the copyright to all of it**. If outside
contributions are ever accepted, they must come with a Contributor Licence Agreement or a
copyright assignment; otherwise contributors hold rights to their parts and no proprietary
licence can be granted without their agreement. Worth setting up *before* the first pull
request, not after.

## Dependency licences

All runtime dependencies are permissively licensed and compatible with both AGPL
distribution and a commercial licence. Verified 2026-08-19:

| Dependency | Licence | Commercial use |
|---|---|---|
| Python | PSF | yes |
| NumPy | BSD-3-Clause | yes |
| Pillow | HPND | yes |
| pypdfium2 / PDFium | BSD-3-Clause, Apache-2.0 | yes |
| pdf.js (if vendored) | Apache-2.0 | yes |

### Removed: poppler

Earlier versions shelled out to `pdftoppm`, `pdfinfo` and `pdfimages` from **poppler-utils,
which is GPL**. Calling them as subprocesses is arm's-length, so this was aggregation
rather than derivation, but *shipping* those binaries inside a distributable would have
carried GPL obligations for that part — source availability, licence text, and no
restriction on redistributing it. They have been replaced by `pypdfium2` (PDFium,
BSD-3-Clause), which removes the obligation entirely and is easier to package, being a
Python wheel rather than per-OS native binaries.

### Model weights

An Apache-2.0 codebase does not imply Apache-2.0 **weights**. Some open-weight models ship
under non-commercial or acceptable-use terms that would prohibit selling access. The
licence of whichever model is adopted must be checked and recorded here before any revenue
depends on it.

| Weights | Licence | Commercial use | Status here |
|---|---|---|---|
| PaddleOCR PP-OCRv6 det/rec | Apache-2.0 | yes | **shipped** — the engine |
| TrOCR variants scored 2026-09-03 | MIT / Apache-2.0 | yes | measured, not adopted |
| `stanford-oval/churro-3B` | Qwen-Research | **no** | measured 2026-09-08, cannot ship |

CHURRO is open-*weight*, which is not open-*source*: it inherits Qwen-Research terms,
which permit research use and forbid commercial use. It was measured on 2026-09-08 because
what a page-level historical VLM can read is worth knowing either way, but it cannot be a
component of anything sold, and under Allan's open-source-only rule it is not a dependency
this project takes. If its numbers turn out to matter, the routes that stay open are a
permissively licensed VLM (Qwen2.5-VL-7B is Apache-2.0, unlike the 3B) or fine-tuning one
on CHURRO-DS, which is a dataset rather than weights.

`llama.cpp` (MIT) is what made the measurement possible on this machine at all: the
released weights are 7.5 GB in bfloat16, and quantised to Q4_K_M they are 1.9 GB.

## Archive material

The scans are public records held by the Arquivo Nacional. This project does **not**
redistribute them: it reads files the user already holds and links back to the archive.
Any commercial offering should confirm the archive's terms of use for bulk or commercial
access before charging for anything derived from them.
