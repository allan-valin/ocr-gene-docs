# Progress

Running checkpoint. **Newest section first, and it is where to start**: it says
what is on disk, how to resume a run, what to do next in order, and what has
already been measured and rejected so it is not tried twice. The design record is
[the spec](superpowers/specs/2026-07-23-desembarque-design.md); this file is state
and next actions.

## 2026-10-17, small hours — one venv, on the GPU

Allan: "how the fuck are you able to test everything then if this is
missing? ... why should I have to waste limited disk space bc you can't
manage environments?" — right. The machine held five venvs, all mine:
`.venv` (pytest), `.venv-ocr` (the launcher's server, no kraken),
`.venv-kraken` (6 GB, CUDA torch, corpus passes), `.venv-htr` (1.2 GB,
dead TrOCR spike) and a 6.7 GB scratch `venv-all` built to verify the
rows-from-lines fix. The server read every page on the CPU of a laptop
with an RTX 4050 while kraken ran on its GPU in another venv.

Now **one venv, `.venv-ocr`** (8.6 GB): engine, kraken, CUDA torch
2.14.0+cu130 and `paddlepaddle-gpu` 3.4.0 (cu130; numpy pinned <2.4
for paddlex; cuDNN 9.24 and cuda-toolkit 13.0.3 as torch wants — paddle
declares 9.20/13.0.2 and runs on the newer). The other four are gone
(−14 GB; disk 45 → 51 GB free). Every wheel came from pip's cache. The
code picks the device by what the install can see, never by a flag:
`engine_paddle.device_for()` → `gpu:0` when paddle is a CUDA build with
a card, else `cpu`; `secondreading.device_for()` → `cuda:0` (kraken's
recogniser splits on the colon; bare `cuda` broke it) when torch sees
one, else `cpu`. A friend's install (CPU wheels from the launcher) never
looks for a card. Script usage lines point at `.venv-ocr`;
`requirements-kraken.txt` says how the GPU builds go in.

Checked through the launcher's own venv and server on the APESP page 6
via `/api/transcribe?page=6`: CPU 96 s → GPU 34 s, 46 rows, the Kubach
row, second reading on page 6. kraken alone on that page 42 s → 22 s
(its vectorising is CPU work). Tests: 1057 pass.

## 2026-10-17 — the launcher checks the install in three tiers

Allan: "why is Completar a instalação even an option for me right now? I
supposedly already have everything" — he has kraken in `.venv-kraken`,
not in `.venv-ocr`, which is the venv the launcher's server runs in; and
nothing on screen said what was where. Replaced the install button with
a check (`core.readiness`, read off site-packages, instant): three tiers,
each with what it is for and what it costs — **Leitura** (pypdfium2,
numpy, Pillow: open, see, search what is transcribed; the server is
standard library otherwise), **Motor de transcrição** (paddleocr),
**Leitor de letra manuscrita** (kraken + the model file). Something
missing → a check window opens first, by itself, with ✓/✗ per tier,
*Instalar o que falta* (only the missing tiers: `install_command(tiers=…)`
never remakes the venv or redoes a tier) and *Continuar assim* (disabled
when not even Leitura is there), the limits said in words. All there →
the main window alone; *Verificar a instalação* in its corner reopens
the check. The pendrive case is the first tier alone.

On this machine: the CPU torch wheel is in pip's cache (196 MB, "Using
cached") and the model file is in ~/.cache/kraken, so *Instalar o que
falta* here downloads kraken's small dependencies and little else; it
puts about 1 GB into `.venv-ocr`. Not clicked for Allan.

Checked by instantiating the window on the real repo (root withdrawn):
the check window opened with the three rows as above and both buttons.
Tests: 1055 pass.

## 2026-10-16, last — the APESP page: a distrusted grid, and no kraken in the server venv

Allan read page 6 of the APESP list alone (the Kubach page): "from about
30 lines only 5 were identified and they come up empty". Two causes,
both found on disk:

* **The server venv has no kraken.** `.venv-ocr` on this machine was made
  before the handwriting reader shipped with the launcher; the record
  says `second_reading: {skipped: "kraken is not installed"}` where
  nobody looks. So every cursive page he has read today was PaddleOCR
  alone. Now: `/api/engine` carries `second_reading`, the page says so in
  the warn bar and the log, and the launcher's install button turns into
  *Completar a instalação (leitor de manuscritos)* when the venv exists
  without kraken (`core.second_reading_installed`, `install_command(…,
  complete=True)` = the two kraken steps). **Allan has to click it** (a
  2 GB download; not done for him).
* **The grid was wrong, not weak.** The page's rules are faint purple;
  the detector found 5 bands of pitch 0.075 on a page of 33 written
  lines, in a column that is not the name's (`columns[0..1]` is the port
  column on this form). `rows_from_lines` trusted them: lines outside
  the 5 bands' extent and outside that column were dropped. Now, when the
  bands are fewer than half the written lines, the grid is distrusted:
  every line on the page becomes a row carrying its whole text
  (`whole_line: true`; the page says so on hover), no band, no column;
  only a person's rows are kept from the engine's. A name with its age
  and trade beside it is found; a name in no row is not.
* The earlier note that this list is "859 px, unreadable" was wrong:
  that is the JPX layer; the JBIG2 mask is 2577×2307 and the page is
  legible at 120 dpi (looked at it).

Verified on the real page with `.venv-kraken` (one page, 42 s, capped
scope): kraken finds 201 lines — one per *cell* (number, name, age,
trade), so the first cut gave 150 rows; grouping lines whose centre
falls in the first line's span (`_written_rows`; the row's union span
swallowed the next row) gives 46 rows for 33 written ones plus the
heading, e.g. row 39 `NR. E · 92 · Kuboch August · 18 m · fota.` On this
machine it runs only once kraken is in `.venv-ocr`.

**Double-checked after finishing** (Allan: "the tests don't seem to be
doing much if they don't catch this stuff" — right; they handed made-up
lines to the function). Two checks that are now how it is done: the
real server (`venv-all`, engine + kraken) read page 6 through
`/api/transcribe?page=6` into a scratch store in 98 s: 46 rows, row 39
`NR. E · 92 · Kuboch August · 18 m`, `rows_from: lines`, `partial`. And
the segmenter's 201 lines off that page are a fixture
(`tests/fixtures/apesp_p6_lines.json`) with a test that asks what a
person asks: the row with Kubach on it, with his number, his neighbours
on their own rows, 36–60 rows in all. Tests: 1054 pass.

## 2026-10-16, latest — stop at the end of the page, one page alone, zoom on the scan

Allan's third round. What he asked and what is on disk:

* **Stop means stop.** Parar waited for the whole document (minutes).
  Now `_transcribe_document` asks `should_stop()` before every page and
  breaks at the end of the one it is on; the record is stored with
  `partial: true` and the pages it has, `is_indexed` says it is not done,
  and the next reading (folder index, or *Continuar a leitura* on the
  page) carries on from the pages on disk (`_pages_kept`; voyage and
  notation come back from the record). **Abortar** (with a confirm)
  throws away the document in hand instead; pages and documents already
  saved stay. Both for the folder (`/api/index/stop?abort=`) and for one
  document (`/api/job/stop?id=&abort=`); both in the progress box, and
  *Parar ao fim da página* on the launcher.
* **One page alone**: `/api/transcribe?pdf=&page=N` reads that page and
  leaves the rest; the record says the rest is still to read; the page
  strip dims unread pages; the doc list says "parcial". Header buttons
  are contextual: *Transcrever* / *Continuar a leitura* / *Transcrever
  de novo*, and *Só esta página* beside them, so the way to read is
  always on screen (it vanished behind the empty grid before).
* **The box shows at the click**, before the request is answered.
  Where no names are cut on the page, the page bar is a clock against
  the usual twenty seconds (`page_s` from `live`), not an endless bar.
* **Zoom on the scan**: Ctrl + wheel over the scan (and − / + / 100%)
  zooms the scan alone, anchored at the pointer; past 1.7× the image is
  fetched at 240 dpi. Bands follow, being fractions of the image.
* Launcher: *Ler os PDFs da pasta ao ligar* off by default.

**Not done, said plainly.** Certidão de casamento 2 reads as gibberish:
the engine's prose reading is PaddleOCR on cursive, which is what it is.
The kraken PP-OCRv6-hist model that beats it on cursive names runs only
on pages with a table (lines onto bands, or rows from lines). Running it
on prose pages, with columns and a double page kept apart, is the
document-types work (docs/FUTURE-document-types.md), not an evening.
Certidão 1 is a table without rules (nome do marido, nome da mulher,
ano, livro, folhas; two pages per scan): same bucket — rows from kraken
lines with columns clustered by x would be the path.

Tests: 1050 pass. Headless load clean. Not seen by Allan yet.

## 2026-10-16, later — a progress box with numbers; the index polled all the time

Allan's second round on his folder (22:39–22:45): five minutes with no
sign of progress until a document finished; the "o servidor demora"
line every 30 s; no way to stop the reading from the page or the
launcher; a certidão read while he watched stayed "ainda não lido"; and
the help window's "esta é só a ajuda" line was itself the confusing
part once the window had its own size and button.

* **Progress is a box over the faded panes** (`renderProgress`): the
  folder (documents done of total, ETA), each document being read (page
  of pages, four at a time, from `reading` on `/api/index`, which
  `live.summary()` fills; `_transcribe_document` now emits a `page` event
  at the start of every page, so a page with no table moves the bar too),
  and the open document's page (names read of names cut). *Parar a
  leitura* and *Esconder* (to a corner; it goes there by itself when the
  open document is the one being read, since its rows arriving are the
  progress). The top bar is gone.
* **The index is polled all the time** (2.5 s, one in flight): the
  launcher starts the index right after opening the browser, and a page
  that asked once, heard idle and stopped never showed it. A document
  finishing refreshes the folder list, and the open document comes in
  if it was the one.
* **Parar a leitura on the launcher** (`core.stop_index`), live while
  the index runs.
* **"demora a responder" once per busy spell**, not every 30 s.
* The certidões read fine: 503 and 3,132 characters of prose on their
  first pages, stored under `form.text`, shown as "texto lido pelo motor
  — não há tabela nesta página". Not searched yet.

Not seen by Allan yet; his launcher and server are old code until
restarted. Headless load on the running server: no script error, the
box shows while the folder is read.

## 2026-10-16, late — the page answers every click; the launcher is two buttons

Allan tried the program on his own folder (one APESP list, two AN
dossiers, two certidões, twenty JPEGs) and could not make sense of it:
"nothing seems to do anything". Each thing he hit, and what changed:

* **Transcrever documento did nothing.** The documents were already read
  (by the test server earlier that day), the pages he opened had no table
  rows (a certidão is prose; the APESP list is 859 px wide and unreadable),
  so the page said "Documento não transcrito" with a button whose answer
  was "already done", in silence. Now a page the engine read and found no
  table on says so, shows the prose the engine read off it (`/api/geometry`
  carries `texts` per page), and points at ↻ Reler for a second reading.
  Reler itself drew its progress into a hidden element when rows were on
  screen; it is shown now.
* **Gerar tabela vazia showed "ilegível" in every cell.** `build_grid`
  wrote `None` into the columns, which is the record's word for "read, not
  legible". The empty grid now carries only the measured fields; absent
  paints blank.
* **No feedback after a click, so actions pile up.** A log under the panes,
  "O que está acontecendo", one line per action and its outcome (folder
  loaded, document opened with its row count, reading asked for / already
  on disk / in progress page by page / finished with counts, grid measured,
  index progress per document, saves that fail, the engine's live page
  cut), plus a bar across the top while any request is unanswered and a
  line after 4 s saying the machine is busy. The empty grid he was filling
  vanished under a finished re-read: the log says so when it happens.
* **Transcriptions went to data/transcriptions in the repo**, where a new
  user does not look and a one-file build has no repo. They go to a
  `transcriptions` folder inside the folder of PDFs now (`store_for`;
  `--store` overrides; the repo's own `data/scans` keeps
  `data/transcriptions` so nothing here moved). The walk and the folder
  picker skip that folder. His bisavo folder therefore starts empty next
  time — the new-user experience he wanted to see.
* **Launcher: Ligar opened the browser, Abrir a página opened a second
  one.** One button: Ligar starts and opens. Closing the browser tab stops
  the server: the page says hello every 4 s (`/api/ping`) and goodbye on
  `pagehide` (`/api/bye`); the launcher asks `/api/clients` and
  `browser_gone` decides (goodbye with no hello for 15 s, or silence for
  3 min — a background tab is throttled to a beat a minute). Desligar
  cannot close a tab (a browser lets no program close a tab it did not
  open): it tells the server first (`/api/shutdown`), the page's next
  hello hears `closing` and shows "O servidor foi desligado. Pode fechar
  esta aba." before the process is killed. Same when the server dies
  unasked (two failed hellos).
* **F1 opened a window the size of the main one**, which read as the
  program. The help is 520×540, offset 70 px, titled "Ajuda — Desembarque",
  with a "Fechar a ajuda" button and a line saying closing it stops
  nothing.

Tests: 1041 pass. Checked headless on the running server: the page loads
with no script error, the log fills, rows paint. Not yet seen by Allan in
his browser; his launcher and server are the old code until restarted.

Left alone: the live view's outline lands on the last band of a batch of
16, which can be mid-page ("reler places the highlight in the middle of
the page") — it is the band the engine finished, not the one it is on;
a per-band report would cost the batch. The APESP list stays unreadable
at that scan size.

## 2026-10-16, night — one row per written line; watching the engine read

Coding only, by Allan's word, while he needed the machine. Three things
built, tested, pushed; nothing run over the corpus.

**One row per written line on handwritten pages** (d0a88b5, 9219554).
`secondreading.rows_from_lines`: every line kraken finds in the name column
is a row, numbered afresh in page order; `name_raw` is the line clipped to
the column, `read_by` the model; the band it sat in gives its reading as
`second_read` and, when it held that one line only, its other columns.
A person's row stands for the first line of its band; the printed heading
keeps its row; lines above the first band or below the last are the
sheet's printing; a line the recogniser read nothing off is not a row; a
band the engine named that no line fell in keeps its row (the segmenter
misses one now and then: OL.PRJ.17347 p14, 28 named bands, 26 lines).
The page's bands become the rows' own extents (`geometry.rows_from:
lines`), so the review page paints them unchanged. Runs at index time
through `read_record`; `truthset.pairs` sends a sheet's band numbers to
the rows the bands became, so the held-out bench still scores.
`scripts/rerow_from_lines.py` does the same to the stored corpus from the
line files under `data/fullpage-ppocrv6` in seconds — dry run on ten
documents: 41 pages, rows 1187 → 1129, named rows kept or gained on every
page, blank bands gone. **`--write` over the corpus waits for Allan.**

**Watching the engine read** (64543ab). `desembarque.live`: the engine
reports the bands as soon as a page's grid is cut and each batch of
sixteen names as it is read (its own batch size, so watching costs
nothing), keyed by thread because four reader threads share one engine.
`/api/live?pdf=` serves it; the review page polls it while a transcription
or the folder index runs on the open document, shows every band as an
empty row, fills the names in, outlines the band just read. Not yet seen
in a browser: the self-test build takes eight minutes of CPU and a real
read needs the engine — first thing when the machine is free.

**Resolution, corrected.** The evening entry said the engine renders at
300 dpi. For the archive's MRC PDFs it does not: `page_geometry.page_image`
takes the embedded bilevel mask at the scan's own resolution (AN: 200 ppi,
2088×3224) and renders only when there is none; detection already runs on
a copy capped at 2000 px a side (`TEXT_MAX_SIDE`), recognition on crops
resized to 48 px high. So "lower resolution for typed pages" has little
left to take; where the twenty seconds a page go — extraction (11.6 s the
first time, cached), the mask reading, the render fallback, the loose
second reading, the header read — wants one profiled page, not a guess.

**Allan's questions, answered 2026-10-16:** typed-or-not probe before
reading (cheap, moot per above); interactive reading (built); one-file
install (PyInstaller one-folder + Inno Setup ≈ 2 GB, 2–3 days, needs a
Windows machine; a true one-file exe unpacks 3 GB per start, no); the 341
dossiers (keep, the lines-first rebuild supersedes them).

## 2026-10-16, evening — the apply was stopped and measured; the second reading ships with the launcher

**Allan stopped the edge re-read at 341 of 496 dossiers** ("idk why you keep
doing full corpus passes... we already talked about this"). The rule, again
and absolute: a change is checked on about ten dossiers; nothing runs over
the corpus without his word in that session; pending tweaks go into one pass
he approves. `data/edges-survey.applied.json` lists the 341; the other 155
keep the old edge. Glued-digit post-pass ran on what was there
(`scripts/strip_glued_ordinals.py --write`: 1948 names in 267 dossiers).

**What the 341 did, old copy (`data/reread`) against now, typed pages only
(258 pages re-read):** the nationality and hotel tails are gone as intended,
and 277 of 17,197 names lost their inner spaces (`ELISABETH ILLES` →
`ELISABETHILLES`; OL.PRJ.17318 p5 alone 32), rows 8642 → 8594, and
OL.PRJ.18644 p4 — a held-out page — lost its last two names (THOMAS and
THEREZA PLEYTE) and renumbered from row 9 when a garbage band vanished.
Held-out bench (`bench_search.py --matrix --held-out`): typed top-5
162 → 155, cursive 107 → 105, blended 290 → 281; naming the crossing
312 → 306. Gains inside that: Erna Werner 40 → 2, Louise Werner 46 → 1,
Francisc Bagi 42 → 1. Net, not a win, and the ten-dossier eye check before
the pass looked only at the tails. Second readings survived on the re-read
pages (24,505 rows). Whether to revert the 341 to the 2026-10-08 copy is
Allan's; the lines-first rebuild below makes band re-reading moot.

**The second reading runs per document, at index time** (commit 8149e9a).
Allan's test folder showed why: the AN list BR_RJANRIO…015033, indexed from
the launcher, came back with 294 names of noise (`Taurte`, `escaleebatuo`)
because kraken lived in `.venv-kraken` on this machine only.
`desembarque/secondreading.py` reads the pages `hands.label_page` calls
cursive or unknown by lines (kraken segmenter, PP-OCRv6-hist medium,
Apache-2.0, Zenodo 21788410), clips each line to the name column, writes
`second_read` on the row; `scripts/serve.py` calls it on every document;
without kraken the record says so under `second_reading`. The launcher's
install puts kraken on a CPU-only torch into `.venv-ocr` in one pip command
(two commands let pip bring the 7 GB CUDA torch back) and fetches the 61 MB
weights to `~/.cache/kraken/ppocrv6-hist/`; a fresh venv is about 3 GB. The
review page shows the line reading before the band reading. Measured on
the same AN list from a merged venv: 299 of 328 rows got a reading
(`Schaefer Emilo`, `Spilmann Paolo`, `del Soldato bito` where the bands
said `Sehaer Cuuuti`, `Shihnaun. Taoto`, `Wl Soliato brito`); 11 pages of
two documents took 842 s on four threads. Not yet tried on Windows.

**Two bugs found by the test folder.** `Certidão de casamento 1.pdf` p1 was
stored as an error: the server's four reader threads met the oneDNN
failure at once, one rebuilt the page pipeline and the other three raised
(commit 31707fb, lock and one retry; the same error sat on 3 corpus pages).
And the launcher's status read "nada para indexar" for minutes while five
documents were being read: `/api/index` takes 2–20 s to answer under load
and the 2 s poll gave up (commit aa461a2, polled off the UI thread, 20 s).
Launcher strings are pt-BR now (bb1f248). What the folder's other files
did: the APESP copy of the Principe di Udine list is 859×769 px a page and
unreadable by anything; `Certidão de casamento 2.pdf` p1 (Registro Civil
prose) was read whole — "Cidade Blaulenlack, Provincia de Baden", "Augarts
Fredericl Kuhach", "Kubach e Edaliza Grille bordecro" — and stored as page
text that nothing searches or shows yet. The engine renders every page at
300 dpi whatever the scan carries, so a 6.6 MB 300-ppi file costs what a
200-ppi one does; a lower render would be faster and lose cursive strokes.

**Next, in order:** Allan's word on the 341; lines first, table second
(`docs/FUTURE-document-types.md`), which also puts the ~9k cursive names
now merged into shared bands on rows of their own; search and show page
text for pages with no table; try the launcher on Windows.

## 2026-10-16 — the name column reached into the nationality; the menu composes; a launcher to double-click

**Allan looked at the first dossiers in the browser and saw names carrying
the start of the nationality — on typed pages, with a finger of blank paper
between the two — and `Yosé`/`Yosi` with no *José* among the guesses.**

**The bleed, found and fixed.** `tablegrid.columns` ended the name column
at the left edge of the heading printed beside it. That heading is narrower
than its column and printed in the middle of it, while the values are typed
from its left rule: on BS.ENT.013981 p2 `Nação` starts at 0.453 of the sheet
and *Brazileiro* at 0.421, so every row read `Enzo SantoniBra`, `José dos
SantosPor`. On OL.PRJ.16548 p2 (cursive) the old edge at 0.475 sat in the
*middle* of the nationality column — `Reidar Birkeland. hor` is *Noruego*
cut in two. Two faults: `Nação` was not in the heading vocabulary (the column
was folded into *Profissão*), and the right edge was never measured from the
writing the way the left edge has been since OL.PRJ.18109. Now
`_right_from_writing`: the rows under the next heading, those starting
nearer that heading than the name's (one detector box merging name and
nationality must not move it), 0.1-quantile, less 0.006 of air — not more,
because on 013947 p4 the nationality is written from the printed rule at
0.355 and *Fernando* ends at 0.35. Fixtures `frags-013981-2`, `-013994-2`,
`-013947-4`; `bench_pages.py` moved 013981 p2 0.452 → 0.419 and 013947 p4
0.363 → 0.348, both intended, baseline re-recorded. A first survey of four
dossiers: all four move, by 0.03–0.06 of the sheet.

**What is on disk was read with the old edge**, and the app shows what is on
disk. `scripts/remeasure_edges.py survey data/edges-survey.json` measures
every list page again with the detector only (no recognition, a few seconds
a page, 3 workers in a `systemd-run --scope -p MemoryMax=8G`) and lists the
pages whose edge moves by more than 0.004; `… apply data/edges-survey.json`
reads those pages again in page order per dossier (so a continuation page
inherits the heading page's columns), through `retry.with_page_remeasured`,
which keeps every row a person typed and — new today — each row's kraken
`second_read`, which on a typed page was the clean reading. Both passes
resume.

*Survey, 224 min, 3 workers:* 1316 of the corpus's list pages, in 496 of
658 dossiers, have an edge that moves. All but four moves shrink the
column; the median move is 0.017 of the page width (a letter or two), the
largest is OL.PRJ.16897, whose stored edges were nonsense (0.03, 0.97,
0.86 on consecutive pages) and now sit at 0.29 on every page. The four
pages whose column grows had an edge cut into the names. The apply pass on
those 1316 pages runs at about 20 s a page; its numbers go below when it
is in.

**The menu.** `Yosi A. Olnerra` (BS.ENT.013990 p2) is *José*. The archive's
spelling neighbours of `YOSI` are *Yoshiko*, *Yoshino*, *Rossi*; the
ascender rule reads `Y` as `J` and gives `JOSI`, which nobody has read, so it
sat at the tail among `BOSI`, `DOSI`, `FOSI`. `gazetteer._composed`: a stroke
reading that spells nothing but is itself ≥ 0.74 similar to an archive name
offers that name, as `traço≈arquivo`, at most two per menu, after the
stroke readings the archive has read. `bench_menu.py` shipped: 88 → 91 of
220 badly-read words found, @1 0.168 = 0.168, @3 0.359 → 0.368, @5 0.391 =
0.391, @10 0.400 → 0.414. (For `Yosé` itself the menu already had *JOSE* at
rank two; the complaint was most likely the `Yosi` row.)

**The launcher.** `launcher/core.py` (tested without a window, against
`tests/stub_server.py`): finds the venv's Python per platform, builds the
serve command with `--no-open`, starts the server and waits for the port,
reports a process that dies at once with its output, stops it, starts the
index and says how far it is in hours. `launcher/desembarque_launcher.py` is
the Tk window — *Instalar (uma vez)* makes the venv and pip-installs both
requirements files with the log on screen; *Iniciar* starts on the chosen
folder, opens the browser and (checkbox, default on) starts indexing;
*Abrir no navegador*; *Parar*; closing the window stops the server.
`Desembarque.bat` / `.command` / `.sh` at the root are what gets
double-clicked; `launcher/README.md` is the page for the friend, in
Portuguese. Standard library only, so it runs on the Python a person
installs from python.org before anything else exists. Not yet tried on
Windows: paddlepaddle 3.3.1 and paddleocr 3.7.0 publish Windows wheels, and
the `.bat` prefers `pyw`/`pythonw` so no console window stays open.

## 2026-10-12, 19:00 — few-shot on the clerks' hands: +1%, closed; the held-out sheet for OL_PRJ_19266 p4 drifted

**Few-shot adaptation of PP-OCRv6 medium (step 3), measured, not worth
shipping.** `scripts/build_fewshot_lines.py` cuts one training line per
hand-read cursive or mixed name of `data/truth-heldout/` from the kraken
lines (`data/fullpage-heldout15-lines-poly.json`), clipped to the name
column, Allan's reading as ground truth, kraken `path` format in
`data/fewshot/lines/`: **222 lines of 245 names** (23 skipped: ditto marks,
stacked lines, no line; 63 stitched from two side-by-side segments, slivers
of the next column dropped; 26 names moved to the band medium's reading
matches, see below). Pages dealt into two folds (A: 4 pages/107 lines, B:
4/115), so each model is scored only on pages it never saw; `--merge`
joins the fold readings with medium's for the typed pages into one
sidecar. Training: `ketos -d cuda:0 --precision bf16-mixed train --arch
ppocrv6 -i ~/.cache/kraken/ppocrv6-hist/medium.safetensors --resize union
-f path -t data/fewshot/train-A.txt -p 0.9 -q fixed -N 20 -B 4 --lrate
1e-4` (batch 8 is CUDA OOM on the 6 GB card; `-q early` crashes the
PP-OCRv6 scheduler with `OverflowError: cannot convert float infinity to
integer`; 4 min a fold at 20 epochs, 12 at 60). Validation on the 10 %
split of the training pages climbs (0.68/0.79 at 20 epochs, 0.76/0.91 at
60) — that is the training hands being learnt. On the fold-out pages:

| held-out, top five by name | medium | few-shot 20 ep. | few-shot 60 ep. |
|---|---|---|---|
| cursive (212), truth as written | 113 | 109 | 108 |
| cursive (212), OL_PRJ_19266 p4 renumbered | 123 | 126 | 125 |
| mixed (33) | 22 | 23 | 22 |
| crossing, cursive, renumbered | 161 | 166 | 166 |

+2 to +3 of 212 (about 1 %) with the truth right, −4 with it as written:
under the two-digit rule by an order of magnitude. The paper's 40–80 lines
lift *one hand*; these are a dozen clerks' hands and the pages the model is
scored on are other clerks again. **Closed; medium stays as it is.** The
fold models and sidecars sit in `data/fewshot/` (gitignored) and must not
ship anyway — they were trained on the held-out set.

**The sheet for OL_PRJ_19266 p4 is off by one band from row 5 and by two
from row 23** (24 of its 28 names), found while pairing names with ink: the
crop labelled "jose ribeiro" showed *Vandestraeten Marie*. Measured on a
scratch copy of the truth with that page renumbered by similarity to
medium's band readings, in page order (`align_page` in the script), the
bench as written goes cursive **107 → 122** by name, 143 → 160 on the
crossing, blended 290 → 305; with medium's bench-time sidecar 113 → 123.
The truth file is Allan's and was not touched; the renumbering is a
one-line apply once he says so. Every other page lines up (the stray ±1s
are family members with near-identical names).

**The 1923 window, searched (see 17:30 above): no Kubach.** Allan corrected
the route note: he was never let off the ship in Canada or the USA, so the
boarding port on any manifest is European.

**Off-corpus, for the citizenship file (Allan's question, answered in
chat):** the one document that ties the German birth to the Brazilian life
is his Arquivo Nacional prontuário (RNE W039916-0, ficha 1.138 SRE Paraná
23 Feb 1939, index card BR_RJANRIO_BN_0_FIN_49_02_17, ref. 26.374, processo
310): its modelo-19 sheet carries date/port/ship of entry and the passport
data. A request text in Portuguese was written for Allan's mother, who has
a contact there; it also asks for a carta negativa de naturalização
(1823–1959) and a certidão de desembarque. Free databases named and
linked: FamilySearch **Brazil, Foreigner Files 1653–2022** (the AN
registration files, 3.5 M persons, arrival date as a field), Canada Form
30A 1919–24 (refused passengers are still listed), Ellis Island 1892–1924,
Canada→USA border lists, Hamburg lists 1920–34 (images locked to
FamilySearch Centers; Ancestry has them, index partial after 1914 — browse
the 1923 Namensverzeichnis), Bremen 1920–39 (Die Maus, free: **searched
today with Soundex, 1,126 hits, no August Kubach** — the Kubachs there are
Karl of Kochendorf 1925 and four in 1933–37; a third of the 1920s lists
are lost), LEO-BW Baden emigration, Generallandesarchiv Karlsruhe,
Politisches Archiv AA (consulate Curitiba Matrikel).

**Next, in order.** (1) Allan's word on renumbering the drifted page.
(2) Pool-competition tuning / `second_read` as a list keyed by model (the
10-10 structural fix): typed gave back two names when medium went on the
cursive rows. (3) The remaining 1919–24 dossiers not on disk, when he
downloads them: `reread_fullpage.py` reads a window at 1.3 s a page on the
GPU, then `search_lines.py`.

## 2026-10-12, 17:30 — the 1923 window re-read with PP-OCRv6 medium: no Kubach

**Done.** Both shards finished: **6,823 of 6,823 pages**, 0 failures, 143 min
on the RTX 4050 (two workers, three render threads each), in
`data/dossiers-1923/lines-ppocrv6/` beside McFondue's
`data/dossiers-1923/lines/`. Same line geometry, so a page's row reads the
same way in both and `search_lines.py` works on either directory.

**Searched.** The thirty spellings in `data/kubach-queries.txt` through
`search_lines.py --dir data/dossiers-1923/lines-ppocrv6 --limit 5` (about a
minute a spelling, one core; hits kept in `data/kubach-1923-ppocrv6-hits.txt`).
Nothing is him. Every surname-shaped hit was cut from the PDF and read by eye:

| hit | score | ink says | row |
|---|---|---|---|
| `kumbach 2on 69f`, PRJ_18860 p6 | 0.92 | **Grumbach**, in the origin column (Böhringen, Bühl around it — Baden towns) | Zuchetti, chauffeur |
| `Rubach`, ENT_016690 p7 | 1.00 on "Rubach" | Rubach, correct | Rubach **Franz**, married carpenter, with Anna |
| `Dubach Jahob`, PRJ_18804 p5/p11 | 0.83 | Dubach Jakob | not him |
| `Stefan / Karol Kubiak`, PRJ_18730 | 0.91 | Kubiak, Polish family | not him |
| `Trumbach Herm.`, `Grumbach Lévie`, `Suzanna Grumbach` | 0.86 | as read | not him |

The given-name spellings (`August Kubach`, `Fritz Kubach`, …) rank bare
given names at 0.90 — the scorer's first-word rule — and their surnames are
Wandsberg, Kleinschmidt, Indrad, Martines: none near Kubach. McFondue's
reading of the same window had found "Rubache"/"Rubiak" for the same rows;
medium's reading is cleaner (`Sültenfuss, Wilhelm / Rubach Franz / Anna`
where McFondue had `ultenjurs / Rubache / Taang`), so the negative is firmer
than before, not merely repeated.

**What this means.** The 1923 window on disk — 2,016 dossiers, Rio (OL) and
Santos (BS) — holds no August Kubach under a reading either recogniser can
make, and the hostel registers 1911 and Oct 1922 – Dec 1925 were negative
earlier. What remains open is what the window does not contain: dossiers not
yet downloaded, a page the segmenter cut badly, or a hand neither model
reads (the few-shot step below is the test of that last one). Allan
corrected one thing here: he was never let off the ship in Canada or the
USA, so whatever the route, the manifest's boarding port is European — the
US-origin lists are not where to look, a European-port list of a ship that
may have called at North America first is.

**Next, in order.** (3) Few-shot adaptation of medium on Allan's 436
hand-read held-out names (the paper: 40–80 lines of a hand lift it); measure
on a held-out split of those pages, not on the training lines. Then, if it
clears the ten-percent bar, the 1923 window again — at 1.3 s a page it is
2.4 h on the GPU, resumable. The pool-competition tuning (typed 164 → 162)
stays after that.

## 2026-10-12, 14:30 — PP-OCRv6 medium is on the rows: held-out cursive 64 → 107

**Applied corpus-wide.** `reread_fullpage.py --device cuda:0` re-read the
1,871 cursive and unknown pages of `data/fullpage/` (220,811 lines, polygons
stored, no segmentation) with Kiessling's PP-OCRv6 medium into
`data/fullpage-ppocrv6/` — 70.7 min on the RTX 4050 while two other GPU jobs
ran beside it, no page failed. `--collect` gave 39,869 column rows on 1,716
pages (`data/fullpage-ppocrv6-corpus-column.json`); `apply_second_opinion.py
--write --bands data/reread-index` put **39,578 of them on 540 documents**, in
McFondue's `second_read` slot (model `PP-OCRv6-hist-medium-page-column`).
Reversible: McFondue's reading stays in `data/fullpage/` and
`data/fullpage-corpus-column.json`; applying that sidecar again restores it.
Typed pages keep the engine's second reading (`PP-OCRv6-on-kraken-lines`),
because medium's 171 vs 164 on typed is under the ten-percent rule.

`bench_search.py --matrix --held-out` on the records as written:

| held-out, top five | by name, before | **by name, now** | crossing, before | **crossing, now** |
|---|---|---|---|---|
| cursive (212) | 64 | **107** | 128 | **143** |
| mixed (33) | 19 | 21 | 16 | 21 |
| typed (191) | 164 | 162 | 154 | 148 |
| blended (436) | 247 (57%) | **290 (67%)** | 298 | **312** |

The bench-time sidecar said 113 on cursive; written, it is 107 — the same
pool-competition gap McFondue showed on 10-10 (68 → 65), every cursive row
now carrying a stronger second spelling. Typed gives back two names and six
on the crossing to the same competition; that is the next thing to look at
if the ranking is tuned (the 10-10 structural fix, `second_read` as a list
keyed by model, is still the right shape for it). The application reads the
records at search time, so the search already sees this.

**Ran (finished 17:00, see the entry above):** the 1923 window re-read,
`reread_fullpage.py --shard I/2 --render-workers 3 --in-dir
data/dossiers-1923/lines --out-dir data/dossiers-1923/lines-ppocrv6` (scopes
`ppocrv6-1923-0/1`, logs `data/ppocrv6-1923-*.log`).

**Why the GPU sat at 5% (Allan asked twice).** Measured on the held-out
pages under the same load: `batch_size` 8 → 62 s and 32 → CUDA out of memory
against 46 s at 1 (lines pad to the widest, CTC gains nothing); kraken's
`num_line_workers` 4 → 123 s (the pool pickles the page per line). The cost
was **pdftoppm**: one 1923 page at 200 dpi took up to 13 s under load, inside
the 5.5 s a page the shards logged, while recognition is a fraction of a
second. `render_ahead` now renders the next three pages in threads while one
is read: 2.5 → 1.3 s a page across both shards, GPU 5 → 66%. The corpus pass
had cached images and no such cost. Then the thirty spellings in
`data/kubach-queries.txt` through `search_lines.py --dir
data/dossiers-1923/lines-ppocrv6`.

## 2026-10-12, afternoon — a shippable recogniser beats CHURRO: kraken's PP-OCRv6 medium

**Allan asked for a search of the field.** The find: Benjamin Kiessling
(kraken's author), "A Free Lunch? Adapting PP-OCRv6 for Historical Text
Recognition" (arXiv 2609.20064, 17 Sep 2026). He adapts the engine's own
architecture (PP-OCRv6, CTC, no language model, so no hallucination) for
historical lines and releases generalized base models **for kraken, Apache-2.0,
on Zenodo** (tiny 2.8 MB / small 13 MB / medium 64 MB; records 21788403 /
21788405 / 21788410): 44 languages, 10 scripts, handwritten and printed,
Portuguese, Spanish, Italian, German, French among them. kraken 7.1 (installed
here, 7.1.1) loads them. Weights now in `~/.cache/kraken/ppocrv6-hist/`.

**Measured the same afternoon, on the held-out kraken lines** (the 15 pages,
2,486 lines, polygons on 9 pages, `data/fullpage-heldout15-lines-poly.json`
built from `data/fullpage/`), through `spike_lines_model.py` — which gained a
7.1 loader (`kraken.models.load_models` → `prepare_for_inference` →
`predict`) beside the CoreML one. Medium: 217 s on CPU, **0.09 s a line**;
**35 s on the RTX 4050 (`--device cuda:0`), 0.014 s a line** — `.venv-kraken`
carries CUDA torch (2.14+cu130), so the 2026-10-09 note that the venvs were
CPU builds is stale for recognition; only kraken's segmenter is CPU-bound,
and these passes re-read stored lines without segmenting.
`bench_search.py --matrix --held-out --second-opinion`, top five:

| held-out, by name | on disk (engine + McFondue) | CHURRO (research) | **PP-OCRv6 medium** | PP-OCRv6 small |
|---|---|---|---|---|
| cursive (212) | 64 | 107 | **113** | — |
| mixed (33) | 19 | 22 | 22 | 23 |
| typed (191) | 164 | 171 | **171** | 171 |
| blended (436) | 247 | 300 | **306** | 289 |
| naming the crossing, blended | 298 | 329 | **333** | — |

Sidecars: `data/fullpage-heldout15-ppocrv6-{medium,small}-column.json`.
Cursive readings on ENT_0163 p4 are names, not noise: `Franco Gino`,
`Chidora Antonina`, `Luciano Anela`, `Lynardi Giordano` where McFondue had
`9 20`, `Chudora Butouina`, `uciarns Augeta`, `Lgnard Jontand`.

**What this means.** Cursive by name alone goes 64 → 113 at five, +77% over
what is on disk, past CHURRO, with a licence that ships and a cost that is
McFondue's order (0.05 → 0.09 s a line), inside the pipeline as it stands:
it takes McFondue's slot over kraken's lines. It also matches CHURRO on typed
pages, above the engine's 164. The VLM question is closed for now — a CTC
line recogniser trained on the right corpus wins on this ink.

**Next, in order, on the GPU (`--device cuda:0`, own scope).** (1) Corpus
pass: medium over every line in `data/fullpage/` (the McFondue readings'
lines, polygons stored), written with `apply_second_opinion.py --write` in
McFondue's place — at 0.014 s a line the 40,475-row sidecar is about ten
minutes; re-measure held-out after. (2) The 1923 window:
`data/dossiers-1923/lines/` holds 616k McFondue lines; re-read with medium
(~2.5 h on the GPU, 15 h on CPU; resumable) and run the thirty Kubach
spellings through `search_lines.py` again — the reading that found nothing
was McFondue's. (3) Few-shot: the paper says 40–80 lines of a hand lift it
further; Allan's 436 hand-read names are that budget for the clerks' hands.

**Also found, lower priority:** MEDUSA 0.1/0.2 (ENC-PSL, Qwen3.5-based
line recognisers, CC-BY-4.0, medieval-trained, 4B/9B — Kiessling's paper
beats them with fine-tuned PP-OCRv6 and they are 45× slower); Qwen3-VL and
Qwen3.5 (all sizes Apache-2.0) — Qwen3-VL-8B leads in-context HTR on 5 of 6
historical collections (arXiv 2609.37195), an option if a VLM is ever wanted;
`wjbmattingly/nara-qwen-3.5-2b`, Qwen3.5-2B tuned on 18th–19th c. American
cursive, Apache-2.0, page-level. No CHURRO 2.

## 2026-10-12 — DeepSeek-OCR-2 cannot read this ink: rejected

**Allan asked** whether DeepSeek-OCR (the "Contexts Optical Compression"
paper, Oct 2025; DeepSeek-OCR-2 "Visual Causal Flow", Jan 2026) was worth a
test. It was the one VLM of CHURRO's shape with a licence this project can
ship — **Apache-2.0 weights, 3B MoE, 570M active** — so the question was
whether it reads cursive like CHURRO (research-only) rather than like the
shippable stack. It was cheap to ask: the llama.cpp here already carries
`PROJECTOR_TYPE_DEEPSEEKOCR2`, the GGUF is 3.6 GB (`sabafallah/DeepSeek-OCR-2-GGUF`,
q8_0 decoder + q8_0 mmproj, in the hub cache), and `spike_vlm_on_lines.py`
reads any llama.cpp VLM over kraken's held-out lines.

**Plumbing** (`read_vlm.py`, tested): a `deepseek-ocr` style — no persona,
the picture before the words, row prompt `"\nFree OCR."` as its card has it,
and llama-server started `--no-jinja --chat-template deepseek-ocr` because
the GGUF carries no template and the server's default jinja engine drops the
image marker from a built-in name (`number of media markers in text (0)`,
HTTP 400). The spike takes `--style`, `--model`, `--mmproj`; the sidecar tag is
the weights' file name.

**Cursive, the page it was for** (ENT_0163 p4, 75 lines, 40 bands, 672 s on
8 CPU threads = 9 s a line): **0 of 40 readings are name-shaped.** 20 are
LaTeX integrals, 14 HTML tables, 2 token loops, 1 refusal ("I am sorry, but
the image provided"), 3 other junk. CHURRO read 40 names on the identical
crops; McFondue reads about a third of them. The model's training is printed
documents, charts and formulae, and shown a cursive line it emits the thing it
was trained on. Allan's reading of the paper was right: the OCR is the test
bed for compressing context into vision tokens, not a handwriting model.

**Typed** (ENT_0167 p2, 44 bands, 6.7 s a line): the right alphabet, below
CHURRO on the same crops (`DETECT LEOPOLD` for `DEJEL LEOPOLD`, `SOUND
LEONHARD` for `SCHMIDT LEONHARD`, `BADER` for `RADER`), and the engine on
kraken's lines is already 164 of 191 at 0.1 s a line. The pass was stopped
there; the partial sidecar is `data/fullpage-heldout15-deepseek-ocr2-column.json`
(two pages), the page lists `data/heldout-pages-{cursive-first,typed}.json`.

**Against the other branch, held-out at five by name:** shippable stack
(engine + McFondue on kraken's lines) cursive 64 / typed 164; CHURRO 107 /
171; DeepSeek-OCR-2 adds nothing on cursive and reads typed worse than both,
at 150× McFondue's cost a line and 3× CHURRO's. Rejected; nothing applied.
The licence gap CHURRO leaves is still open: the next candidates stay a
permissive fine-tune on CHURRO-DS, or Qwen2.5-VL-7B measured again on
kraken's lines rather than the engine's crops.

## 2026-10-10, afternoon — CHURRO on kraken's lines reads half the cursive names; 1923 is on disk

**The gate, and it is not close.** `spike_vlm_on_lines.py` cuts every line
kraken found across the name column out of the chosen page image (polygon-
masked where the polygon is stored, box where the 2026-10-08 pages have only
boxes), sends it to CHURRO 3B through llama-server with the row prompt, and
writes the same `-column.json` shape the kraken spikes write. The 15 held-out
pages, 678 column lines, 32 min on six CPU threads (the llama.cpp here is a
CPU build; no `nvcc` on the machine). `bench_search.py --matrix --held-out
--second-opinion` on top of the records as they stand:

| held-out, top five | by name, on disk now | + CHURRO | crossing, on disk | + CHURRO |
|---|---|---|---|---|
| cursive (212) | 64 | **107** | 128 | 144 |
| typed (191) | 164 | 171 | 154 | 162 |
| mixed (33) | 19 | 22 | 16 | 23 |
| blended (436) | 247 (57%) | **300 (69%)** | 298 | 329 |

Research licence, so none of it ships (`LICENSING.md`); it reads for Allan's
own search and under its model tag, which `apply_second_opinion.py` can strip.
Note the spike is measurement code beside `read_vlm.py`; the readings live in
`data/`, which is not versioned, so a branch would isolate nothing.

**1923 is on disk.** `download.py --workers 8` (new: a thread pool with the
per-request delay kept, exponential backoff on 429/5xx/dead connections, a
per-file lock because a lettered dossier cross-references another's PDF and
two workers once raced on it — one resumed the other's half file, got a 206,
and deleted the finished copy). BS 16030–16690 and OL 18380–19175: 1,361
dossiers, 6.5 GB, 36 min at 13:00 on a Saturday, no refusals from the
archive. `data/scans` holds 2,016 PDFs.

**What Allan told about the man** (in memory too): born 20 Sep 1902, so
underage until 20 Sep 1923; the ship went to Canada, landing refused, then
the USA, refused despite a sister there, then Rio — so the Rio list may be a
New York departure (Lamport & Holt, Munson), not a German port, which his
hand search did not cover. Three single young Germans in a row on that list.
Name forms to search together: Kubach/Kuback/Kubak/Kubasch/Cubach, the K→R
confusion Rubach, and Augusto/August/Friedrich/Friederich/Frederico/Fritz.

**The engine index was started and stopped.** `serve.py` over `data/scans`
(four workers, 9 GB cap) indexed 12 of the new dossiers in 14 min: 84 s a
dossier, 10 GB resident, 32–42 h for the window, and nothing else fits in
memory beside it. The app needs it eventually (records, geometry, the review
screen); the search does not. It resumes from the hash cache whenever it is
started again (`POST /api/index?dir=.` on a running server; `/api/index/stop`
only sets a flag the workers do not honour, so the scope was killed).

**Done 2026-10-11 09:40, the Kubach path, McFondue reading negative:** all
6,823 pages of the 1923 window are in `data/dossiers-1923/lines/` (616k lines,
698 MB, 15.5 h a worker). The thirty spellings in `data/kubach-queries.txt`
through `search_lines.py` found no Kubach: the only surname-shaped hits were
"Rubache" (BS 016690 p7, cropped: Rubach, Franz, 32, married, carpenter, with
wife Anne — not him) and "Rubiak" (OL 18730, a Slavic list). Everything else
was a given name alone at 0.90. What remains is the CHURRO reading of the
cursive name-column lines, which needs the rented GPU; `spike_vlm_on_lines.py`
needs a no-record mode for these lines first (crop every name-column line,
write a lines JSON, search with `search_lines.py`).

**How the pass ran:** `read_hospedaria.py --pages all --dpi 200`
over the 1,338 new PDFs (`data/dossiers-1923/lines/`, scopes `kraken-1923-0`
and `-1`, 6 GB each, shard `I/2`) — kraken's segmenter and McFondue, one JSON a
page with polygons, resumable, no records needed. Stop with `systemctl --user
stop kraken-1923-0.scope kraken-1923-1.scope`; resume both together with the
same `systemd-run` lines, the book list being `data/dossiers-1923/books.txt`
and the logs anywhere; the list was reordered Rio (OL) first at 18:05 and the
workers restarted, so the Rio pages land by about 01:00 and the Santos ones
after. At 18:00, 1,484 pages (all Santos) were done and the thirty Kubach
spellings over them found nothing (best hits were given names alone, 0.90).
**6,823 pages** (the 1923
dossiers run five pages, not four), ~25 s a page a worker, about 24 h from
14:20. `search_lines.py --dir data/dossiers-1923/lines "<name>"` works on
what has landed, and `scripts/find_person.py --queries data/kubach-queries.txt`
asks the application's index for all thirty spellings at once (today, over
the 59k rows already indexed: nothing; best surname "Kubaschek Josef" 0.64).

**After the lines land, in order:** the thirty spellings through
`search_lines.py`; CHURRO over the cursive column lines, which needs a GPU
(no `nvcc` here: Allan installs the CUDA toolkit and llama.cpp is rebuilt with
`-DGGML_CUDA=ON`, or a rented 4090 for a few dollars — 175k crops is 140 h
on this CPU); then the engine index for the app, on nights, and the two
shippable sidecars through `apply_second_opinion.py`.

## 2026-10-10 — the 68 → 62 gap was the application's weighting, not the pool

**Separated.** The bench and the application scored the same second reading
differently. `bench_search.py --second-opinion` puts a sidecar's reading in
`alts` *before* the guesses, at full weight and inside the crossing pass; the
application's `search.spellings` put the stored `second_read` *with* the
guesses (0.95, out of the crossing pass) — a trade measured on 2026-09-08 with
a weaker recogniser over the engine's own crops. One bench told both suspects
apart: the written records plus the corpus sidecar injected as a reading score
65 / 128, so the weighting is most of the gap and the pool is the rest:

| held-out cursive (212), top five | by name | naming the crossing |
|---|---|---|
| written `second_read` counted as a guess (app, 10-09) | 62 | 110 |
| the same readings counted as readings (app, now) | **65** | **128** |
| bench-time sidecar on the 15 held-out pages only | 68 | 131 |

`spellings` now counts `_other_recogniser` with the readings; test flipped
with the numbers in its docstring; 952 green. Typed naming the crossing moves
152 → 149 (McFondue's typed-page readings now enter that pass); blended
crossing 277 → 293. The remaining three names (65 vs 68) are pool
competition — every row carries a second spelling, so the true row faces
twice the near-misses — and at +4.6% are below the ten-percent rule, so no
tie-break weight is tuned for them.

**What this taught about the shape.** Readings are mutated into the record
across four fields (`name_alts`, `alts`, `second_read`, `guessed`) by three
code paths, and the bench has an injection path the application does not.
That is how a measured 68 shipped as 62. The structural fix, in order, when
the work is between runs: `second_read` becomes a list keyed by model (one
slot cannot hold McFondue and the engine-on-lines on a mixed page); the
kraken-lines reader moves from `scripts/` into the package as the primary
reader, the grid engine becoming its typed-line recogniser; the bench reads
records only and the injection path goes.

**The engine's sidecar is written, and typed is 164 of 191.** The pass ran
11:38–12:13 (672 pages, 35 min, 8 GB scope, no errors); 20,580 rows across
252 documents, model `PP-OCRv6-on-kraken-lines`, none of them a row McFondue
had read (it read the cursive and unknown pages only, so one `second_read`
slot was enough this once). The written state and the injected bench agree
exactly, which is what step 1 bought. Held-out, top five:

| | by name | naming the crossing |
|---|---|---|
| cursive (212) | 64 | 128 |
| mixed (33) | 19 | 16 |
| typed (191) | **164** (was 151) | **154** (was 149) |
| blended (436) | **247** (was 232 on 10-09) | **298** (was 277) |

Cursive gives back one (65 → 64) to pool competition from the new rows.
Both sidecars are on the rows; the day's work took the held-out set from
53% to 57% at five by name alone.

**Next, in order.** `second_read` as a list keyed by model (the next
recogniser lands on rows that already carry one); the kraken-lines reader
into the package; bench reads records only. Then the window download when
Allan starts it, read once by each pipeline, never re-run per tweak.

## 2026-10-09, night — one worker's OOM took the terminal down; book 110's Augusts are not him

**What killed the session.** At 21:03 the kernel OOM-killed one of the three
hospedaria workers (6.7 GB resident; the three together ~11 GB of 14, swap
full). systemd's `DefaultOOMPolicy=stop` then failed the whole Konsole scope the
workers had been `nohup`ed into, so the terminal, the Claude session and the two
surviving workers died together. Evidence: `journalctl -k | grep -i oom` and
`journalctl --user | grep oom-kill`. **Rule from now on:** every heavy job gets
its own transient scope with a cap, so an OOM kills that job alone and the
readers resume:

    systemd-run --user --scope --unit=hosp-w0 -p MemoryMax=5G -p OOMPolicy=continue --quiet \
      bash -c ".venv-kraken/bin/python scripts/read_hospedaria.py --books <0101.pdf> <0102.pdf> \
               --device cuda --shard 0/3 --pid-file <scratch>/w0.pid > <scratch>/w0.log 2>&1" &

GPU worker 5G, CPU workers 3500M each (`--shard 1/3`, `2/3`); caps must stay
under ~12 GB in total. Relaunched 23:17 on the 1911 books only (HIF.100 was
complete at 423 odd pages; HIF.101 had its first 34 odd pages plus every sixth;
HIF.102 nothing) — 296 odd pages, ~1.4 h.

**Book 110, the August check: negative.** 150 rows whose name reads like
August/Augusto (fuzzy ≥ 0.75 over `lines/0110-p*.json`) were cut from the PDF
into six review strips and read by eye. No surname resembles Kubach; the K-names
among them are Koch (p39, p291), Köhler, Kühn, Kolb, Kaminski, Küffer, Kneip.
Three rows were a bare "August" aged 19–25 under a family head cut out of the
strip; cropped with their head rows they are Oestreich August 21 (p17 l28), Busch
August 21 (p23 l52), Schramm August 25 (p447 l38). So in HIF.110 (Oct 1922 –
Jul 1924) no August Kubach entered the hostel under a readable name.

**The 1911 books are read, and no Kubach is in them.** HIF.100 (423 odd
pages), 101 (186), 102 (171), all in `data/hospedaria/lines/` by 01:10.
`search_lines.py` for Kubach Wilhelm / August / Frida / Guilherme / Kubach over
the three books: nothing above 0.70, and the ten weak hits cropped with their
head rows are Burach Józef (100 p811), Pachna (100 p813), Banach Marcin (101
p157), Konieczny Wojciech (102 p285), a child Rafael (101 p23), two children
named Wilhelm under other heads (100 p251, 101 p73), and ink in other columns.
These books are mostly Polish families via Bremen. So the hostel registers
on disk — 1911 and Oct 1922 – Dec 1925 — do not hold him under a readable name;
HIF.109 (1920–22) Allan read by hand. The engine's own recogniser is now running
over the typed lines of the corpus pass (`spike_engine_on_lines.py --lines
data/fullpage-corpus-typed-lines.json`, scope `engine-typed`, cap 6 GB, log in
the scratchpad) and writes `fullpage-corpus-typed-engine.json` — **only at
the end** (~55 min for 672 pages, ~12 a minute), so a killed run is rerun whole:

    systemd-run --user --scope --unit=engine-typed -p MemoryMax=8G -p OOMPolicy=continue --quiet \
      bash -c ".venv-ocr/bin/python scripts/spike_engine_on_lines.py --lines data/fullpage-corpus-typed-lines.json > <log> 2>&1" &

Started 01:08 on 2026-10-10 and **stopped at 01:13 for the night** (nothing
written; rerun it whole with the command above). After it: `apply_second_opinion.py --sidecar
data/fullpage-corpus-typed-engine.json --records data/transcriptions --bands
data/reread-index` as a dry run, `bench_search.py --matrix --held-out
--second-opinion <that file>`, and `--write` only if typed (151/191) does not drop.

**What the caps taught.** CPU worker RSS is not a leak: a page spikes (HIF.101
p193 peaked at 5.4 GB for one page, then 0.7 GB) and a 3.5 GB or 4.5 GB cap
kills the worker on that page; 6 GB holds. The GPU worker dies faster: when
CUDA runs out it falls back to the CPU with both models loaded and passes 5 GB
within a minute. With two CPU workers at 6 GB each the 1911 remainder (87
pages) took 25 min; the GPU buys nothing here (segmentation is CPU-bound). Also:
a worker's `--shard I/N` is taken over the pages *still missing at launch*, so
halves started at different times do not tile — the last five pages needed one
unsharded pass.

**Next, in order.** Engine pass finishes → `apply_second_opinion.py` for the
typed sidecar → `bench_search.py --matrix --held-out` → commit. Then the window
download when Allan starts it.

## 2026-10-09 — the corpus is read whole, on three workers; the GPU was there all along

**The pass is running.** `scripts/read_fullpage.py` reads every page of the
corpus the way the sheet said to: kraken's page segmenter finds the lines,
McFondue reads them on cursive and unknown pages, typed pages keep their lines
for the engine's recogniser (`spike_engine_on_lines.py`). One file per page in
`data/fullpage/`, so it resumes from wherever it stops and never reads a page
twice; cursive pages first. `--collect` turns the page files into the two
sidecars `apply_second_opinion.py --write --bands data/reread-index` takes.
Three workers (`--shard I/N`), each with its own pid file; the call-time pauser
`data/pause-for-call.sh` SIGSTOPs them 14:55–16:05. Started 11:05, 2,541 pages.

**The laptop has an RTX 4050 (6 GB), and every venv was a CPU build.** Months
of "or a GPU" in this file without checking the machine. `.venv-kraken` now has
torch 2.14.0+cu130 (kraken pins torch ≤ 2.14). Measured on one cursive page:
recognition 4.6 s → 2.4 s, **segmentation 14 s → 13 s** — `blla.segment`'s cost
is CPU vectorisation (`vec_lines`: Sato ridge filter, per-line ROI, reading order
with half a million shapely calls), single-threaded, the same at any image scale
because kraken rescales internally. So the GPU is not the lever on this pass;
parallel workers are. Two workers fit in VRAM until the allocator grows past
3 GB, then one; the rest run on CPU at 20–40 s a page under contention.
`paddlepaddle-gpu` 3.4.0 (cu129) exists for the engine and is untried.

**Every line is stored with its polygon and baseline** (`line_record` in
`spike_fullpage.py`), not only its box, because reading the same lines with
another model through axis-aligned boxes gave garbage (`atvot raca` where the
polygon read a name) — the box takes the neighbours' ink. With the polygon on
disk any recogniser can re-read the corpus for the 2 s of recognition instead of
the 12 s of segmentation. The 165 pages read before this change have boxes only.

**Models trained on the clerks' own hands, on the 212 held-out cursive names,
top five by name alone** — Allan's question, whether a model trained on German
or Dutch or Italian hands reads what McFondue cannot (`spike_lines_model.py`,
same kraken lines, polygons, `bench_search.py --matrix --held-out
--second-opinion`):

| recogniser on kraken's lines, clipped to the column | at 5 | at 10 | at 20 |
|---|---|---|---|
| **ManuMcFondue** (French 17th–20th c.) | **68** | 75 | 89 |
| McCATMuS (multilingual 16th–21st c.) | 61 | 67 | 84 |
| UB Mannheim German handwriting | 58 | 60 | 73 |
| Bohemian 19th c. (German-language registers) | 57 | 59 | 71 |

McFondue stays. The lines on these lists are the pursers' Portuguese-Italian-
French-Dutch office hands, not Kurrent; the German-trained models lose.
Loghi (Dutch national archives, Royal Holland Lloyd is the corpus's biggest
line) is a Docker/TensorFlow stack and was not tried.

**Kubach.** The app exists to find August Friedrich Kubach, arrived 1919–24,
most likely 1923, settled in Morretes (Paraná), married there 20 Dec 1924.
Allan has read by hand every 1919–24 list of a ship that called at a German
port or any port within ~400 km of Karlsruhe and did not find him. What the
pass changes: a second machine reading of those same pages, and the ships via
Amsterdam, Antwerp, Bordeaux and Genoa he did not read. What it cannot change:
the 661 dossiers on disk are 9% of the 7,679 in the catalog, and a man who
settled in Paraná may have landed at Paranaguá, which these two fundos do not
cover. `download.py --window FUNDO:lo-hi` now fetches whole number ranges
(dossier numbers are chronological; BS 16030–16690 and OL 18380–19175 are
1923); the 1919–24 window is 6,663 dossiers, 561 on disk. Also fixed: the
manifest skipped dossiers by number alone, and BS and OL share 15938–17398.
The strongest lead is off this corpus: his RNE W039916-0 names a foreigner's
file at the Arquivo Nacional that states the arrival.

**Evening: the pass landed, and the corpus-wide number is below the held-out
one.** 2,541 pages read (three workers, 11:05–19:00 with the call pause),
`--collect`: 40,783 McFondue column readings on 1,726 pages, 40,475 written
as second readings across 542 documents (`apply_second_opinion.py --bands
data/reread-index --write`). `bench_search.py --matrix --held-out` after:

| held-out, top five by name alone | before | sidecar at bench time (10-08) | written on the rows |
|---|---|---|---|
| cursive (212) | 56 | **68** | **62** |
| typed (191) | 151 | 151 | 151 |
| cursive, naming the crossing | 111 | 131 | **110** |

Same recogniser, same lines, same pages — the difference is that the bench
sidecar covered the fifteen held-out pages only, and the write covers every
page. Two candidates, not yet separated: every row in the pool now carries
a second spelling, so the true row competes against twice the near-misses
(would show at five and ten, less at twenty: 84 vs 89 at twenty, so partly);
or `desembarque.search` counts a written `second_read` differently from a
bench-time sidecar, which the crossing number (131 → 110, below the engine
alone) suggests. **Separate these before the engine sidecar is written:**
bench with `--second-opinion data/fullpage-corpus-column.json` against the
pre-apply records (`data/transcriptions-before-reread-2026-10-08` is the
wrong baseline; the apply is reversible by model tag).

**Hospedaria da Ilha das Flores.** The archive's orientation page
(`consulta.an.gov.br/orientacaoDesembarque/1`) sends a searcher who found
nothing in OL to the hostel registers, 1877–1932. Fund OB.0.EPE, series HIF,
image URL `derivadas/BR_RJANRIO_OB/0/EPE/HIF/0110/BR_RJANRIO_OB_0_EPE_HIF_0110_d0001de0001.pdf`
(four-digit folder, one part each). Books and their dates: HIF.108 to May
1917, nothing until HIF.109 (19 Jan 1920 – Oct 1922), HIF.110 (27 Oct 1922 –
17 Jul 1924), HIF.111 (Jul 1924 – Dec 1925); 1911 is HIF.100–102. Six books
on disk in `data/hospedaria/`. Open-book layout: odd PDF pages carry date,
ship, origin port, ordinal, NAMES, sex, family, age, status, nationality;
even pages continue the same rows with profession, exit date, transport,
destination, observations. One clerk's neat hand; McFondue on kraken's lines
reads "Kuhlmann Wilhelm" as "Rublnann Wilheln" and `search_lines.py` still
ranks it first (0.75). Allan read HIF.109 by hand: no Kubach. Machine order:
110, 111, then the 1911 books (his 1939 foreigner's file declares residence
"desde 1911", which Allan reads as stretched, not true).

**Next, in order.** Let the pass finish; `--collect`; engine on the typed
lines; apply both sidecars; `--matrix --held-out`; search for Kubach; commit.
Then the window download when Allan starts it (the auto-mode classifier
refused to let this session start it), engine read of the new dossiers, kraken
second reading of those — one pass each, never re-run per tweak.

## 2026-10-08, afternoon — sheet 2 came back: 436 names, cursive 26%, and the whole page helps after all

Allan read the second sheet the same day (ten pages, cut from the re-read,
the engine's reading greyed in every box) and it came in by band number with
no alignment at all. **The held-out set is 15 pages and 436 names now**, all
by Allan: 212 cursive, 191 typed, 33 on two pages he called mixed. Found in
the top five by name alone, `bench_search.py --matrix --held-out`:

| second reading beside the engine's | cursive (212) | typed (191) | mixed (33) |
|---|---|---|---|
| none — the corpus as it stands | 56 (26%) | 151 (79%) | 17 |
| McFondue on the engine's own crops | 60 | 151 | 18 |
| **McFondue on kraken's whole-page lines, clipped to the column** | **68 (+21%)** | 151 | 19 |
| the engine's recogniser on kraken's lines | 63 | **164 (+9%)** | 18 |

At 10/20 the whole-page McFondue reading is 75/89 against the engine's 58/71.
Naming the crossing, cursive is 111 of 212 with the engine alone. The pages
vary enormously: OL.PRJ.18396 p4 reads 17 of 25 and BS.ENT.015796 p3 reads 1
of 44, and the four pages the first sheet had shown as the ordinal strip now
read 18/20, 28/44, 5/11 and 17/25 through the re-read's column.

And the same lines read by the engine's own recogniser take typed from 151
to 164 of 191 (86%), because a segmenter's line follows the ink and does not
straddle two rows or catch the next column. One segmentation pass, two cheap
recognisers: McFondue for the cursive pages, the engine for the typed ones.

So **Allan's proposal from the morning — transcribe the whole page, then
find the column — is the right one after all**, measured on 212
names where the morning's 33 could not tell: not because the lines read
better one by one, but because the segmenter finds the rows the engine's
grid cuts across, and a second reading that is wrong differently reaches
names the fuzzy index could not. The price: kraken segments and reads a
page in 16 s on this CPU, so the whole corpus is about 10 hours of machine
(the ~1,900 cursive pages 8.5 of them), resumable, with the geometry doing
the columns and no language model anywhere. **That is the next pass**, run with the machine free and
applied as second readings (the reversible shape), and it was not run today
because the day ended at the hand-back.

Three things the sheets taught about the measure itself, fixed: a heading
typed into its band (`nome e cognomes name in full`) is not a name to search
for; on the two mixed pages Allan typed what the bands hold below the names
— nationalities, *para America*, *Brasileiros* — and those nine cells are
counted as misses, which is right (they are on the page) and worth knowing
when reading the mixed row; and `data/heldout-pages.json` lists the 15 pages,
so every sidecar of the held-out set is cut by the same list.

## 2026-10-08 — the sheet came back, and the first honest number is 87% typed, 9% cursive

**Where things stand.** Allan read the first held-out sheet on 2026-10-07.
Five of its ten pages were unusable — four showed the *Nº de ordem* strip and
one the "IMMIGRATION" cover note — and on the usable five the typing drifted
off the band numbers. Both were this repository's doing, not the reader's,
and both are fixed below. The five usable pages are in `data/truth-heldout`
(127 names, all by Allan), the second sheet is in his Downloads cut from the
re-read, and the corpus re-read (T8) is running again from 2,012 pages with a
watchdog. Tests: 928 green, 13 skipped.

**Why half the sheet was the ordinal column.** The sheet was cut on
2026-09-08 from the geometry in `data/transcriptions` — which this file said
on 2026-08-29 was the ordinal strip on 946 of 2,543 pages and the whole
sheet on 394 more, 52% of the corpus. The re-read corrects exactly that
(`measured_by: printing`), and had already re-cut four of the five bad pages
by the time Allan opened the sheet: in `data/reread`, OL.PRJ.18396 p4 reads
*Polzer Erich, Le Guiny Pauline, Kutchera de Fys…* through a column at
0.151–0.316 where the old record had 0.011–0.053. Counted today: plausible
name columns on 1,231 of 2,543 pages in the old corpus, **2,073 in the
half-finished re-read**. So the crop detector is not "wrong and useless"; the
sheet was cut from the reading the detector had already been fixed on. The
cover note won its document because `pick_page` took the page with the most
*bands* and a blank page cuts into 48 of them.

**Why the numbers drifted.** A reader counts the rows he can see. The engine
numbers the printed heading and the blank under it as bands 1 and 2, so box 1
got the first name; and on BS.ENT.016317 p4 three of 42 bands are slivers
almost entirely under the band below them — the gutter box of the next band
hides their number — so the count ran ahead by three by the bottom of the
page. On BS.ENT.016429 p3 the engine's bands are a uniform 0.0206 grid that
misses three of the page's 44 rows, so the count ran ahead there too, for the
opposite reason.

**Fixed, with tests.** `desembarque/sheetbands.py`: `visible_bands` (a band
whose part above the next one is under 40% of the median height is not a
row anybody can type against), `representative_bands` (when a visible band
read as nothing and the sliver under it carries the reading, the row is
numbered by the band that can be scored), `heading_offset`, `positional_map`
for cursive pages and `align_by_text` for typed ones — a monotone alignment
where skipping a band the engine read costs more than dropping a typed row,
because the families on these lists share a surname down twenty rows and a
shifted chain of pairs looks half right by text. `import_reading_sheet.py
--positional --records` maps the first sheet through it, writes `cut_from`,
`mapping` and `lost` into each truth file, and sets aside a page typed as
numbers or as one word instead of refusing the sheet. `make_reading_sheet.py`
offers the page with the most *names* through a column the width of a name,
draws and boxes only the visible bands, pre-fills every box with the engine's
own reading in grey so the reader can tell which row a box is, carries the
reading it was cut from, and draws from the seeded sample itself (the
recorded ten are asserted to be its prefix; it is `random.Random(20260907)
.sample` over the scans in name order, tuned-on documents out).

**The held-out numbers, and what moved them.** Found in the top five by
name alone, `bench_search.py --matrix --held-out`:

| | cursive (33) | typed (93) |
|---|---|---|
| tuned-on set said | 47% | 98% |
| held-out, as first imported (shift-aligned, scratch) | 1 | 68 of 94 |
| held-out, positional/text alignment, ditto resolved, all-caps glue cut | **3** | **81** |
| + McFondue on the engine's crops (`kraken-fondue-heldout.json`) | 4 | 82 |
| + McFondue on the whole page, kraken blla lines clipped to the column | 4 | 82 |

Three things moved typed from 68 to 81, and they are measurement, not
tuning: (1) a cell Allan wrote as the clerk did — `Viola "` under *Julia
Hunt Jones* — is now scored as *Viola Hunt Jones*, the name a searcher types
(`truthset.with_ditto_resolved`, the mark's position saying whether the
family name is the end or the start of the name above); (2) the typed page
whose bands miss three rows is aligned by text, so a right reading is no
longer charged for the row above it; (3) `search.unglued_by_names`: a
typewritten page in capitals glues the names — `FRANZPOPERL`, `KARLFRENK`,
`MARIALANG`, 14% of the ten-letter rows on the typed documents have no space
— and `unglued` cannot cut where there is no inner capital, so the cut is
taken after a given name the archive has read. This last one is a search
change found on the held-out set; the tuned-on matrix is unmoved by it
(52/67/75, 41/41/41), and the second sheet is where it gets confirmed or
not. **Cursive at 9% is the number.** The tuned-on set's 47% was a reading of
four pages whose column was right, by the assistant, and it was never going
to survive a random page.

**The spike Allan asked for: transcribe the whole page, then find the
columns.** Measured on the five held-out pages (`scripts/spike_fullpage.py`,
sidecars `data/fullpage-heldout-{line,column,lines}.json`):

* **kraken blla + McFondue over the whole page**: 150–200 lines a page with
  coordinates in 16 s a page on this CPU (18 s segmenting, 5 s reading; the
  five pages in 81 s). Every truth row of every page gets a line; the lines
  cross the printed column rules, so a row comes back as `t Hambaurg Poleer
  Tric`, and McFondue's per-character cuts clip it to the stored name column
  with no language model in the loop. Through the index: cursive 4 of 33 at
  five against the engine's 3, typed 82 against 81; clipping to the column
  and leaving the line whole score the same. **It finds the rows without any
  band geometry, and it does not read them better.** On typed pages McFondue
  is the wrong model (`NAIR 82430` for *Maria Szabo*); the engine's own
  recogniser on kraken's lines is the untested half.
* **PaddleOCR-VL-1.6 over the whole page** (llama.cpp, Q8_0): at 1400 px
  with `Table Recognition:` and at 1600 px with `OCR:` it collapses into one
  repeated token for 72 s; at 1000 px with `OCR:` it reads the heading and
  then one numbered list in 56 s that mixes the port column and the name
  column — `3. Rigo, 4. Liabonne, … 16. Juan Lantos Oundi, 17. Cadiimiro
  Fraga Fraga` for *Vigo, Lisbonne, Juan Santos Conde, Casimiro Fraga Fraga*
  — and then repeats that list five times to the token limit. The cursive
  names in it are better than McFondue's, the structure is not usable, and
  it is 56 s a page for a list that has to be put back on rows by counting.
  Not the path; row crops at 2.7 s remain the way to ask this model.
* **A language model to sort the text into columns** was not needed: the
  lines carry coordinates and the page carries its rules. It is still the
  open option for *reading* — a model that knows names could turn `JULLA
  NUNT SORES` into *Julia Hunt Jones* — but that is the fuzzy index's job
  already, and the DeepSeek API is a hosted service with the passengers'
  names leaving the machine, which the standing rule excludes.

**The re-read finished at 10:45 and is the corpus.** 2,543 of 2,543 pages
(07:40–10:45 today, about 3 a minute with the machine to itself; the
watchdog never fired). `compare_corpora.py`: 644 of 660 documents changed,
rows 71,449 → 86,766, **rows carrying a name 29,718 → 59,285 (+29,567)**,
every row a person typed survived verbatim, 52 documents lost a few names
(worst −21 on 88a50c3a). Pages with a plausible name column 1,231 → 2,272;
**271 still measure as the ordinal strip or the whole sheet**, 214 of them
cursive pages the re-read's own rules measured (1,855 named rows on 5,382
bands, mostly not names). Promoted at 11:00: `data/transcriptions` is the
re-read, the reading it replaced is whole at
`data/transcriptions-before-reread-2026-10-08`, and `data/reread` is the
identical copy today's sidecars are keyed to. One `mv` reverts it.

**The matrix fell, and that was expected.** Tuned-on cursive 52/67/75 →
**46/55/67** at 5/10/20 by name alone (typed 41 unchanged; naming the
crossing 89/94/100 unchanged); held-out typed 81 → **74** of 93, cursive 3 of
33. Two causes. Twice the rows now compete for every name — the cursive
page's hits moved from ranks 9, 10, 16 to 19, 12, 35 with the same readings.
And OL.PRJ.17318 p5 was cut into 45 bands instead of 46 with a column 0.01
wider that catches the first letter of the next column (`DOMINGOS MARQUESB`,
`MARTINEZORTEGAV`, `MARTHAFUCHSS`) — six names on one page. That overshoot is
**not** corpus-wide: over the 440 typed pages whose band count did not
change, 5,602 rows read the same and 3 gained a trailing letter. The 29,567
people made searchable are invisible to a matrix over eleven pages that were
readable already; both numbers are the truth and both get quoted.

**Sidecars cut before today are keyed to the old bands** —
`kraken-fondue-heldout.json`, `vlm-heldout.json`, `paddleocrvl-heldout.json`
and the rest — and must be re-cut before being applied. The held-out truth
files were re-imported against the new bands (`cut_from: transcriptions`,
2026-10-08, positional with text alignment on the typed pages).

**The engine's own recogniser on kraken's lines** — the half the whole-page
spike had not tested (`scripts/spike_engine_on_lines.py`, sidecars
`data/fullpage-{heldout,tunedon}-engine.json`): cursive unchanged, 3 of 33
and 46 of 110; **typed held-out 74 → 84 of 93**, because a segmenter's line
follows the ink and does not overshoot into the next column. So the row cut
is a lever on typed pages and not on cursive ones, where every model and
every cut reads the same three names. Cursive is the recogniser, full stop.

**The 271 pages the re-read measures wrong, read through their siblings'
column.** The same printed form runs the length of a dossier, and 225 of
the 271 have a sibling page with a plausible name column.
`scripts/sibling_column_reread.py` keeps each page's own row bands, borrows
the median column of its siblings, and has the engine's recogniser read the
crops that makes — 225 pages in 9 minutes. Counted by rows whose reading
contains a name the archive has read (four letters or more): **138 → 177 on
those pages** (+28%), 48 pages gaining; by the looser "searchable" rule
1,628 → 1,644, because the whole-sheet readings they replace are long runs
of letters that are not names. Applied as second readings
(`apply_second_opinion.py --write --bands data/reread-index`): 2,181 rows
across 117 documents, nothing overwritten, reversible. Modest, because
these pages are 88% cursive and the recogniser reads cursive badly through
any column; the 46 pages with no plausible sibling are left as they are.

**Two things the promotion broke, fixed.** `desembarque.hands` read the
confidence under `surname`, the key T6 renamed to `name` in August; the
re-read writes only the new one, so `classify_hands.py` called 652 of 658
documents unknown. It reads both now, and `data/hands.json` is re-labelled
on the promoted corpus (the old labels kept beside it): 97 documents moved,
74 of them cursive → typed, because better crops read with more confidence;
434 cursive, 197 typed, 27 unknown; 6 of 6 tuned-on pages still right, and
of the five held-out pages Allan labelled, four agree and BS.ENT.016079 p2
(three typed names on an otherwise empty page) is called cursive by both the
old and the new labels. And the README quoted the tuned-on numbers as if
they were the reading's; it quotes the held-out ones now.

**Measured and rejected today, two more.** *A name-column finder on
kraken's lines* (the left edge where the most letters begin, the right edge
where those lines end): right on six of the eleven pages whose column is
known and wrong on the rest, because a segmenter's line crosses the column
rules — on BS.ENT.013947 p2 one line runs from 0.05 to 0.77 of the sheet —
and on a surname-then-given-name page the given names make the taller
cluster. Not reliable enough to run blind on 271 pages; the dossier's own
sibling pages are the column finder instead (below). *Restoring pages the old
reading read better*: by known-name rows, 16 pages are better in the old
reading by five or more (112 rows) and 619 are better in the new; not worth a
page-level merge.

**Measured and rejected today.** A mark *after* the name inheriting the end
of the name above in the index, as the truth set now does — `VIOLA"` under
*JULIA HUNT JONES* as Viola Hunt Jones. Held-out typed 81 → 83 at five;
tuned-on cursive 52/67/75 → 50/64/73, because on BS.ENT.013947 p3 the
recogniser puts the clerk's leading mark at the *end* of `Maratuai"` and
the rule then took the given name above for the family. The quote's
position is evidence on a typed page and noise on a cursive one, and the
cursive pages are the point. Out, and not worth a per-hand rule for two
typed names.

**Next, in order.**

1. ~~Let the re-read finish~~ — done and promoted, above.
2. **Allan reads sheet 2** (`~/Downloads/desembarque-reading-sheet-2.html`,
   ten pages: the four re-cut ones and the next six of the draw). Import
   with `--records data/reread` and no `--positional`. That is the fresh
   held-out for the glue cut and for the McFondue question: one or two names
   of 33 is not a decision, and the sidecar over the corpus waits for it.
3. **kraken's lines as the row and column finder** for the 271 pages the
   re-read still measures wrong: the lines' x-ranges cluster into columns,
   and the engine's own recogniser reads the lines (84 of 93 typed above).
   Validate the finder on the eleven pages whose column is known, then run
   it on the 271, never on the corpus.

## 2026-09-30 — a 16 MB model at 0.05 s a row finds a third more cursive names

**Where things stand.** The reading sheet has not come back, so every number
below is still measured on the tuned-on set and is unproven in the same way
every number before it was. What changed today is the *price* of the second
reading: it was 170 hours of machine for the corpus and it is now about one.
The corpus re-read (T8) is running again from 368 of 662 — see the end of
this section for why it had stopped. 889 Python tests green, 12 skipped.

**The question asked.** Two things were on the plan's "what would change
this" list — PyLaia/Kraken, and a better crop — and one model was sitting in
the hub cache unmeasured. All of it costs minutes a row or less, so all of it
was measured the same way, on the same 155 labelled crops, through the same
index, as CHURRO and Qwen were on 2026-09-08.

**Through the index, cursive names found by name alone, of 110:**

| second reading beside the engine's | licence | s / row | top 5 | top 10 | top 20 | corpus |
|---|---|---|---|---|---|---|
| none — the engine as it ships | — | — | 52 | 67 | 75 | — |
| CHURRO 3B (2026-09-08) | research only | 4.4 | 85 | 93 | 103 | 85 h |
| Qwen2.5-VL-7B Q4_K_M (2026-09-08, 109 cursive rows) | Apache-2.0 | 8.5 | 78 | 86 | 98 | 170 h |
| **kraken, Manu McFondue** | CC-BY-4.0 | **0.05** | **71** | **81** | **91** | **~1 h** |
| PaddleOCR-VL-1.6 Q8_0 | Apache-2.0 | 2.7 | 67 | 78 | 86 | 53 h |
| kraken, McCATMuS | CC-BY-4.0 | 0.11 | 59 | 73 | 84 | 2 h |
| kraken, Manu McFrench V3 | CC-BY-4.0 | 0.03 | 64 | 76 | 84 | 0.6 h |

Naming the crossing, which no second reading had ever moved: engine 89/94/100,
McFondue **94/100/108**, PaddleOCR-VL 93/99/102, McCATMuS 95/99/102, Qwen-7B
95/101/106 (re-run today on its 2026-09-08 sidecar).

**Manu McFondue** — kraken's model of French manuscripts 17th–21st century,
with some Spanish letters, 16 MB, [Zenodo 10886224](https://zenodo.org/records/10886224)
— takes cursive names in the top five from 52 to 71, **+37%**, for a twentieth
of a second a row on this CPU. That is seven names short of Qwen-7B at 170× the
cost, and past the two-digit bar by a wide margin. Whole cursive corpus:
about an hour of recognition plus the page cutting, against a week for Qwen.

**And character error says the opposite, again.** On the 155 rows kraken is
*worse* than the engine by CER — McFondue 0.549 mean against 0.369 — and much
worse on typed pages (1.017 on `BS_ENT_013981` p2, so it reads cursive pages
only, which `data/hands.json` already decides). On the cursive pages it is
better on three of four: `BS_ENT_015061` p6 0.323 against 0.349,
`BS_ENT_013947` p3 0.551 against 0.601, `BS_ENT_014541` p2 0.300 against 0.371,
and worse on Allan's page, 0.488 against 0.200. What the index rewards is not
a lower error but a *different* one: a row the engine spells unfindably,
kraken spells wrongly in a way a fuzzy search still reaches. This repository
saw the same thing on 2026-09-03 and it is why the index, not the CER, decides.

**PaddleOCR-VL-1.6** — the model the design spec named in July and rejected in
August at 22 minutes a column — runs under llama.cpp on row crops at **2.7 s a
row**, faster than the engine's own 4.33. Engine-level on cursive by CER (0.470
against 0.444 over the 108 cursive rows), worse on typed, and +29% at the top
five through the index. A real option, and McFondue beats it at a fiftieth of
the price. It needed one thing: asked with its card's own `OCR:` and no
persona (`read_vlm.py --style paddleocr`), because a model measured with
another model's prompt is a measurement of the prompt.

**Settled today, so it is not tried twice:**

* **A better crop does not exist, for these models.** The band with 25% of its
  own height added above and below (`training_set.py --variant grown`, kept
  only where the plain band inside it is byte-for-byte the exported one)
  makes PaddleOCR-VL read the neighbour's ascenders as text: 0.435 → 0.698.
  Kraken too: 0.529 → 0.637, and 0 px or 24 px of white air instead of 8 are
  both worse. The band as the engine cuts it is the right picture. *Not*
  measured on Qwen-7B: the Android emulator holds 4 GB today and the 7B does
  not fit beside it safely; given the two models above, the expectation is
  the same.
* **`Kansallisarkisto/multicentury-htr-model`** (4.2 GB in the hub cache since
  September, never scored because of a processor bug since fixed) reads this
  ink as **Finnish**: CER 1.0, 13 s a row. Dead.
* **The other models on disk.** `~/uni/mpr/repo/models` holds a Piper voice and
  a Vosk German speech model — the robotics practical, nothing to do with
  ink. `PP-OCRv5_server_rec` was measured and rejected on 2026-08 (CER 0.516).
  The hub cache's PaddleOCR-VL weights are in Paddle's own format; the GGUF
  that runs here is `SanjeevSOLANKI/PaddleOCR-VL-1.6-GGUF`, 1.3 GB.

**A bug, fixed, that would have hit any long pass.** PaddleOCR-VL emitted half
a multibyte character on row 132 of 155, llama-server answered 500, and the
reader died with the 131 readings before it never written. `read_vlm.py` now
writes the sidecar after every row, records a refused row as nothing read, and
resumes a sidecar of the same model — tests first, in `tests/test_read_vlm.py`.

**The literature, on the way past.** [arXiv 2609.20064](https://arxiv.org/abs/2609.20064)
(September 2026, *A Free Lunch? Adapting PP-OCRv6 for Historical Text
Recognition*) finds a **fine-tuned PP-OCRv6 beats a large VLM tailored to
historical Latin-script HTR**. PP-OCRv6 is the engine that ships here. What
this repository lacks is not the model but the labels — 155 crops, measured on
2026-09-05 as too few — so the paper is one more reason the review screen's
corrections are the long game, and one more reason not to swap the engine.

**The held-out comparison is pre-read for four models now.** The same ten
pages the sheet shows, cut from the same geometry, one sidecar each:
`data/vlm-heldout.json` (Qwen-7B, 357 rows), `data/kraken-heldout.json`
(McCATMuS, 351), `data/kraken-fondue-heldout.json` (McFondue, 325 — it reads 26 more rows as nothing),
`data/paddleocrvl-heldout.json` (PaddleOCR-VL, 345). `spike_kraken.py --documents`
drives kraken through `read_vlm.whole_documents`, so it is the same pass.
When the sheet comes back, each is one command:

```sh
.venv/bin/python scripts/import_reading_sheet.py ~/Downloads/reading-sheet.json
.venv/bin/python scripts/bench_search.py --matrix --held-out
.venv/bin/python scripts/bench_search.py --matrix --held-out --second-opinion data/kraken-fondue-heldout.json
```

**Next, in order.**

1. **Allan reads the sheet.** Unchanged; still the only thing between here
   and a number anyone can quote.
2. **Finish the corpus re-read (T8)** — it rewrites the rows a sidecar is keyed
   to, so any corpus-wide second reading has to come after it, not before.
3. **Then McFondue over every cursive document into a sidecar**, applied as an
   alternate (`apply_second_opinion.py --write`, the reversible shape) only
   once the held-out number says so. `spike_kraken.py --documents --hand
   cursive --documents-limit 0`, resumable; about an hour of recognition.
**The re-read had not stopped on purpose.** The 2026-09-08 section below says
it was stopped at hand-back; `data/reread.log` says it crashed, on the first
record after 368 that carries no file name — two do — because `scans / ""`
is the scans directory, which exists, and `cached_hash` opened it.
`export_bands.py` now skips a record whose scan is not a file
(`scan_of`, tested), and the re-read resumed at 13:55 today with the machine
otherwise free. **Stopped at 14:11 at 378 of 662 documents, 1,521 pages** in
`data/reread-index`, because a Gradle build (5 GB, two JVMs) started beside
the re-read's own 5 GB with 1.8 GB left on the machine — the pattern that
froze it once before. Sixteen minutes bought ten documents, two of them
enormous (`97e0c269` p6 alone is 382 bands). One line restarts it and it
skips every page already indexed; give it the machine to itself:

**Resumed 2026-10-02 09:35–12:21** by the morning session, with the machine otherwise idle
(no Gradle, no emulator; 6–7 GB available, a watchdog ready to SIGTERM it under 1.5 GB — it
never fired). Stopped by hand at the hand-back time: **501 of 662 documents touched, 2012
pages** in `data/reread-index` (from 1,521 pages at 09:35: 491 pages in 2 h 46 min, about 3 a
minute on this CPU). Same restart line, same skip-what-is-indexed behaviour; roughly half the
corpus is now re-read.

```sh
.venv-ocr/bin/python scripts/export_bands.py --records data/transcriptions \
    --out data/reread-index --write-records data/reread --no-crops
```

4. **Two alternates on a row — measured crudely, and not worth building.**
   Both readings joined into one string per row and run through the same
   matrix: McFondue + Qwen-7B **80/90/98** (Qwen alone 78 at five, McFondue
   71/81/91), McFondue + PaddleOCR-VL 71/81/89 — no better than McFondue
   alone — and McFondue + McCATMuS 68/81/88, worse. Every pairing *loses*
   the crossing column (94/100/108 → 91/97/105 at best), because a longer
   text dilutes the match. Two names at five for Qwen's 170 hours on top of
   kraken's one is not a schema change; one reading a row, and it is
   McFondue's.

## 2026-09-08 — the measurement gets a reader's name, and the score splits in two

**Where things stand.** The five tasks that had to come before any reading
work are done (`docs/TASKS-honest-measurement.md` T1–T5, T4 measured, T5
waiting on one thing only: somebody reading pages). 877 Python assertions
green, the app's own 126 in-browser assertions green, nothing pushed.

**The corpus re-read is stopped and resumable at 368 of 662 documents** —
1,501 pages, 37,281 rows, up from 254 documents at the start of the day. It was
stopped on purpose at hand-back so the machine is free. One line restarts it
and it skips every page already in the index:

```sh
.venv-ocr/bin/python scripts/export_bands.py --records data/transcriptions \
    --out data/reread-index --write-records data/reread --no-crops
```

**The headline numbers, restated as the pair they should always have been.**
`bench_search.py --matrix` prints typed and cursive apart from now on, because
blended they say nothing — the typed pages are effectively solved and the
cursive ones are the entire point:

| found in the top | 5 | 10 | 20 |
|---|---|---|---|
| **cursive** (110 names) | 52 | 67 | 75 |
| **typed** (42 names) | 41 | 41 | 41 |
| blended (152), as quoted until today | 93 | 108 | 116 |

Typed is 98% at the top five and cursive is 47%. Naming the crossing as well
as the name takes cursive to 89 of 110, which is the number worth keeping in
mind: **what a searcher knows about the voyage is worth more than anything
done to the reading so far.**

It is 152 names now and not 138. The rows form — Allan's page, the only one a
person read — carried no `names` list, and `truth_rows` skipped it, so the
single human-read page was outside every figure this repository has ever
quoted. It is in.

**Shipped.**

* **Every truth file says who read it.** Five of the six now say `assistant`,
  which is what they were, and carry the warning in their own caution field.
  One says `Allan`. Nothing downstream can quote them innocently again.
* **A page can now say what nobody could read.** `desembarque.truthset` loads
  the format of T1 — `?` for an uncertain row, empty for a row nobody can read,
  `-` for a band that is not a row — and keeps the three apart. A file with no
  reader raises rather than loads. This is the class the old files had no way
  to write down, and its absence is why every previous number flattered: an
  illegible row was left out rather than counted, so a recogniser was never
  charged for inventing a name on one.
* **Every page of the corpus is labelled typed or cursive.**
  `scripts/classify_hands.py`, off the confidence already stored beside each
  reading — no OCR, one pass. It gets all six pages of known hand right, and
  the gap it sits in is wide: cursive tops out at 0.869, typed starts at 0.952.
  **Of the pages it can call, 83% are cursive.** 163 pages sit within 0.03 of
  the cut, where the label is the threshold guessing, and `--check` says so.
* **The held-out set can be read and taken back in.**
  `scripts/make_reading_sheet.py` writes one self-contained HTML file — the
  page images, the engine's own row numbering drawn on them, a box per row —
  and `scripts/import_reading_sheet.py` turns what comes back into
  `data/truth-heldout`, refusing any page that does not say who read it and
  which hand it is. `bench_search.py --matrix --held-out` scores it.

**CHURRO reads this corpus's cursive better than the engine does, by a lot.**

The full table is in `docs/TASKS-honest-measurement.md` T6. The short of it:
a 3B open-weight historical-document VLM, quantised to fit beside a browser on
this laptop, at 4–5 seconds a row — the same order as the engine's own 4.33 s.
It beats the engine on **every** cursive page and loses on both typed ones, and
through the index it takes cursive names found by name alone in the top five
from **52 to 85 of 110** — +63%, on the hand this project exists for.

Also settled: reading the whole name column in one look is worse, not cheaper
(every `Maria` came back `Elbria`), and Q8_0 weights are no better than Q4_K_M
and 40% slower.

**CHURRO's licence blocks it from shipping — and that turned out not to
matter.** It is research-use-only, so the same afternoon the obvious question
was put to a model that *is* shippable: `Qwen2.5-VL-7B-Instruct`, Apache-2.0.

| CER, mean | cursive (109 rows) | typed (42 rows) | s/row |
|---|---|---|---|
| the engine as it ships | 0.443 | 0.171 | 4.33 |
| CHURRO 3B — research licence | **0.350** | 0.249 | 4.4 |
| **Qwen2.5-VL-7B — Apache-2.0** | 0.356 | **0.114** | 8.5 |

The permissively licensed model matches CHURRO on cursive and beats both it and
the engine on typed. Cursive names found by name alone in the top five: engine
52, Qwen-7B **78**, CHURRO 85, of 110. **So there is a model this project may
actually use that reads this archive better than what is in it now, on both
hands, for twice the machine time a row.**

And on the one page a **person** actually read — Allan's own 14 rows of
`BS_ENT_013947` p2, the only human labels in the repository — the same model
halves the error: **engine 0.186, Qwen-7B 0.084**, closer on 9 rows of 14. That
number is free of the bias that taints every other one here.

The pass that produced it is on disk and resumable: `read_vlm.py --documents`
reads whole documents out of the corpus, cuts each row from the geometry the
record already stores, picks documents by the hand T4 labelled them with, and
writes the sidecar `apply_second_opinion.py --write` already knows how to apply.
41 rows of a real page in 4.7 minutes. **Nothing has been applied to the corpus.**

`LICENSING.md` now carries the table of which weights may be used at all.
**Nothing about the shipped engine changed today** — and none of this is proven
until the held-out pages are read, because every number here is scored against
labels whose errors correlate with the engine's.

**A bug found by accident, and it is bigger than it looks.** Six of the ten
held-out pages came back from the VLM pass with no rows read at all. The cause:
a page's stored `columns` has two shapes — the name column alone on a page
measured off the rules, and *every* boundary on a page that printed its
headings — and `desembarque.bandcrops` accepted only the first, calling the
second unusable. **1,509 of the 2,543 pages that have bands, 59%, could not be
cut into row crops at all.** Everything downstream of a crop was quietly
working on the other 41%: the labelled training set, the review screen's
picture of a row, every second-opinion pass. `make_reading_sheet` had always
read both shapes, which is why the sheet could render pages the reading pass
then skipped. Fixed, with the two shapes tested.

**The decisive experiment is already half-run.** All ten held-out pages have
been read by the VLM — 357 rows, `data/vlm-heldout.json`, the same pages the
sheet puts in front of a person. When the sheet comes back the comparison costs
one command and no machine time. (The six truth pages all store the name column
as a pair, so nothing measured today was touched by the crop bug above: it hit
the corpus, not the benchmark — which is part of why it went unseen.)

**The plan those numbers argue for is written down**:
[`docs/PLAN-vlm-second-reading.md`](PLAN-vlm-second-reading.md). Its first step
costs no machine at all and can cancel the rest, and its second — the VLM over
the ten held-out pages, under an hour — is the experiment the whole thing turns
on. 170 hours of corpus reading is not started before that hour is spent.

**What is waiting on Allan, and it is the only thing blocking honest numbers.**

`~/Downloads/desembarque-reading-sheet.html` — 10 pages, 361 rows, 4 MB, opens
in any browser on any machine, keeps your work as you type. Take them in order
and stop whenever you like; three pages is already a real sample. Then:

```sh
.venv/bin/python scripts/import_reading_sheet.py ~/Downloads/reading-sheet.json
.venv/bin/python scripts/bench_search.py --matrix --held-out
```

Until that exists, **every delta this repository has ever reported is unproven**
— the set they were measured on was partly written by the thing being measured.
The one exception stays the re-read: +166% findable rows, measured over the
whole corpus, needing no truth set at all.

## 2026-09-07 — the second reading ships, and it costs a day and a half

**Where things stand.** The corpus re-read is running (see below) and nothing
else is. 770 Python assertions green, the tree pushed. The second opinion is
now something the application has rather than something the bench measured,
and the open question about it — how to pay for it — has an answer that is
worth having and is not the one the plan expected.

**Shipped.**

* **One place to ask which rows are worth a second look.** The reasons were
  written twice, in `scripts/serve.py` and again in `scripts/bench_check.py`,
  and the copies had drifted: the bench asked the spoken-name lists as well as
  the archive's own names and the screen did not, so the yellow bar was being
  measured on a rule it was not running. Both now call
  `desembarque.recheck.why_check`, and `bench_check.py --json` is byte-for-byte
  what it was before the change. The screen keeps its present behaviour —
  handing it the language lists adds a flag to the bar and is a decision, not a
  refactor. `recheck.flagged` is the third caller the consolidation was for:
  the offline batch, which has to pick rows from a stored record before any
  index exists.
* **The other recogniser's reading, on the row.** A row carries `second_read`
  — the model and what it said — and `desembarque.search` spells the row by
  it, counted with the guesses: below every reading, and out of the pass that
  runs when a crossing was named. `scripts/apply_second_opinion.py` writes a
  `read_bands.py` sidecar into the corpus, refusing a sidecar keyed by a band's
  position, never giving a machine's reading to a row a person typed, and
  writing nothing at all on a second run over the same sidecar.
* **And it was proved end to end.** `data/freshcache` copied to
  `data/sidecache`, `data/side-fair.json` written into it — 1,864 rows over
  fifteen documents — and then the plain matrix over that corpus with no
  sidecar and no bench flag: **91/104/111 by name alone, 118/123/129 naming
  the crossing**, which is exactly what the sidecar measured through the bench.
  Every number the second opinion had earned is now a number the application
  has.

**Measured, and it settles the sizing question.**

* **The check is not a filter.** The plan's guess was to pay for the second
  reading only on the rows the review check flags. Over the whole corpus the
  check flags **62,976 of 71,147 rows, 88.5%**, so the saving is a tenth. On
  the subcorpus, gating it that way reads 1,602 rows instead of 1,787 and the
  index goes **91/104/111 → 90/103/110** — a name lost at every cutoff to save
  a tenth of the time. Run it on everything or not at all.
* **Nor is the score.** `score < 0.85` is 78% of rows, and even `score < 0.5`
  is 44% — 31,320 rows. There is no cheap subset because there is no small bad
  half: the check flags 88.5% of the corpus and the hand-read pages say 82% of
  rows really are misread. The bar is not lying, the reading is bad.
* **The row costs 4.33 s, not the 2 s the plan carried.** Measured off the
  fair run's own log: 1,865 crops in 8,068 s. So the corpus at the shipped
  setting is **85.6 h**, and gating on the check only takes it to 75.7 h.
  Every hours figure written before today was half of the true one.
* **And the whole cost is the beam width.** 91 labelled crops, the machine to
  itself, the re-read paused:

  | setting | per crop | corpus | CER on 56 labelled rows |
  |---|---|---|---|
  | `--beams 4 --batch 3` (shipped) | 4.40 s | 85.6 h | 0.627 |
  | `--beams 1 --batch 3` | **1.33 s** | **26.3 h** | 0.634 |
  | `--beams 1 --batch 8` | 1.51 s | 29.8 h | 0.634 |

  Greedy decoding is **3.3× faster for seven thousandths of character error**,
  and batch size is not a lever at all — 8 is slower than 3, on a CPU with no
  room to widen. So the number to decide on is a day of machine, not three and
  a half.
* **And it was then read the whole way and searched, which is the only test
  that counts.** `data/side-fair-b1.json` is all 1,865 crops read greedily;
  over the 152 labelled rows it is **CER 0.560 against the beam search's
  0.567** — not worse, slightly better. In the index, both written into a copy
  of the same corpus and searched on the same 31,272 rows:

  | | per crop | corpus | top 5 / 10 / 20, name alone |
  |---|---|---|---|
  | no second reading | — | — | 87 / 97 / 105 |
  | `--beams 4`, the shipped setting | 4.40 s | 85.6 h | 91 / 104 / 111 |
  | `--beams 1` | **1.33 s** | **26.3 h** | 90 / 101 / 112 |

  Naming the crossing, all three are 118/123/129 — the second reading has
  never moved that column and does not now. So the beam search buys one more
  name at five and three at ten for **sixty extra hours**, and character error
  and findability disagree about which reading is better, which this
  repository has seen before. **If it is run, it is run greedily.**
* **It does not rescue the unreadable rows, which was the other hope.** Of the
  1,864 rows read twice, 1,748 are searchable either way; the second reading
  makes 43 searchable that the engine's does not, and the engine's makes 54
  searchable that the second reading does not. Five of the 43 spell a name the
  archive knows. The second opinion is worth its three or four names in the
  top five and nothing else.
* **A sidecar belongs to the reading its crops were cut from, and the write now
  knows it.** `apply_second_opinion.py --bands` refuses a row the engine no
  longer reads the same way, which is what stops a reading landing on a
  stranger when a page has been renumbered. Of the 1,865 rows
  `data/side-fair.json` offers:

  | records | rows that land |
  |---|---|
  | `data/transcriptions`, the live corpus | 1,149 — 38% refused |
  | `data/freshcache`, the reading it was cut from | 1,843 |
  | `data/reread`, today's pass | 1,818 |

  So the order is settled: **do not spend the second reading before the
  re-read lands.** Applied to the corpus as it stands, a third of it is thrown
  away; applied after, 97% of it survives, because the re-read reproduces the
  reading the crops were cut from. One dossier makes the case on its own —
  05edf625 lands 18 rows on the live corpus and 599 on the re-read.
* **An interim reading on the re-read itself.** `scripts/compare_corpora.py`
  is the verdict in one command — rows carrying a name per document, and
  underneath it the property no gain buys back: every row a person typed still
  saying what they typed. Fifty-three documents in, at 11:00:

  ```
  rows              71449 -> 79888
  carrying a name   29718 -> 43066  (+13348)
  23 documents came back with fewer names, 46 rows between them
  every row a person typed survived verbatim
  ```

  **Stated as the percentage it is**, which is the number that decides whether
  the pass is worth the machine: on the 172 documents it actually re-read,
  findable rows go **8,045 → 21,393, +166%**. Across the whole corpus with a
  quarter of it done it is already **+45%**. Reporting this as "+3,062 rows"
  earlier in the day hid the size of it and nearly got the pass cancelled.

  Held over 660 documents that is the corpus more than doubling in findable
  rows. 05edf625 makes the case on its own: 543 rows to 933, and 89 carrying a
  name to 602.

  Both counts here are lower than the first ones taken this morning, and the
  difference is the point: the first version counted `22222222` and the column
  caption as names, put the corpus at 37,341, and read a dossier where the
  re-read *threw that junk away* as four names lost. Counting what the index
  indexes — `search.searchable`, now the only copy of the rule — the base is
  29,718 and the worst document loses two.


**Stopped, a quarter done, and resumable.** The corpus re-read ran 09:23-16:20
on 2026-09-07 and was stopped because the machine goes back to Allan at the end
of a stated window. 172 of 660 documents are re-read and their gains are on
disk in `data/reread`; re-running the same command continues from where it
stopped, because a page already in `data/reread-index` is skipped:

```sh
.venv-ocr/bin/python scripts/export_bands.py --records data/transcriptions \
    --out data/reread-index --write-records data/reread --no-crops
```

It writes into `data/reread` (a copy of `data/transcriptions`, never a
hardlink) and touches nothing that is there. Seven hours bought a quarter of
the corpus; the rest is roughly ten more with the machine to itself, and it is
the sort of thing to start when nobody needs the machine.

Nothing is lost by stopping: the 172 documents already done keep their gains,
and `scripts/compare_corpora.py` scores whatever has been reached at any time.
When it does finish: run that comparison, run `bench_search.py --matrix --cache
data/reread`, and if it holds up that copy becomes the corpus.

### Start here next time, in order

1. **Whether the re-read is worth keeping** — the comparison above. Nothing
   else on this list is worth as much as the engine reading the pages better.
2. **The decision on the second reading**, and it is only a decision now:
   **26.3 h of machine at `--beams 1`, for three more names in the top five
   and four at ten, per 138** — and only after (1), because a third of a
   sidecar is refused by a corpus it was not read from. The pass is

   ```sh
   .venv-ocr/bin/python scripts/export_bands.py --records <corpus> --out <bands>
   .venv-htr/bin/python scripts/read_bands.py --bands <bands> --out side.json \
       --variant strip --refine 64 --beams 1 --batch 3
   .venv/bin/python scripts/apply_second_opinion.py --sidecar side.json \
       --records <corpus> --bands <bands> --write
   ```

   and nothing about it is unmeasured except one lever: a **smaller model**.
   Greedy took the crop from 4.33 s to 1.33 and the encoder is the floor under
   that; no base-vs-small trade has been scored. `data/bands-fair`,
   `data/trainset-fair` and `score_crops.py` are what that measurement needs,
   and it wants the machine to itself.
4. **Grow the labelled set**, unchanged from the last section and still the
   only thing between here and an archive-trained recogniser: 151 hand-read
   rows and four corrections, and fine-tuning on that many is measured and
   does not work.
5. Still open and untouched: T3's `bench_columns.py` and per-column truth, and
   T10's other columns. Both want a cursive page whose columns read at all,
   which T11 measured and found they do not.

**On disk from today.** `data/sidecache` is `data/freshcache` with the second
reading written in — the end-to-end proof, keep it or delete it, nothing
depends on it. `data/reread` and `data/reread-index` are the run above.

## 2026-09-04 — the labels were wrong, and that came first

**Where things stand at the end of the day.** Tree clean, 742 Python
assertions green, 23 commits, nothing pushed. Nothing is running: the engine
pass and the second reading both finished (`data/bands-fair`,
`data/side-fair.json`, `data/freshcache`, and their logs `data/export-fair.log`
and `data/read-fair.log`). The second opinion is answered and worth shipping as
a guess; the biggest thing on the list is a decision, not a measurement — see
*Start here next time*.

The day's list was the three steps left on the second opinion and the training
set. Doing the first one turned up something that had to be fixed before any
of the rest meant anything: **the labelled set was partly mislabelled**, and so
was the bench's idea of which row each hand-read name sits on.

**Shipped.**

* **Both pictures of every row.** The engine's crop function keeps the carved
  crop *and* the plain band rectangle when a caller asks, keyed by band index
  rather than collected in order — a page is read more than once (the render
  fallback, the looser second reading) and pairing by position across those
  passes hands a name somebody else's ink. `export_bands.py` writes both,
  `read_bands.py` takes `--variant strip --refine 64`, and `bench_search.py`
  now understands a sidecar keyed by row number, which is what `read_bands.py`
  has always written and what its 82% coverage depends on.
* **The corrections, without keeping anything.** The plan was to save the crop
  when somebody retypes a row. Not needed: since T4 every page stores the
  geometry its rows were cut from, so `desembarque.bandcrops` cuts the same
  ink again — byte-for-byte the engine's own crop, held to it by a test — and
  `training_set.py --records` harvests every correction in the corpus,
  including ones made months ago. There are four today, all made by choosing
  an offered reading rather than typing, and cutting their crops immediately
  earned its keep: one of them labels ink that reads *Raymundo Cassaudii* as
  *Nayomgo Cassaudi*. A person's word is not always right, so the set records
  how each label was made.
* **Each name on the row it was written on.** Two faults, and each cure was the
  other's poison. `first_row` goes stale — BS_ENT_014541-p2 records 4 because
  the comb that read it in July counted the header bands — so counting from it
  labels every crop with the name three rows above. A single best-fit offset
  fixes that and then drifts past the first row carrying no reading:
  BS_ENT_015061-p6 had 42 rows scoring CER above 1 for the engine's own
  reading, which is the signature of a mislabelled set and not of a bad
  recogniser. `truthset.aligned` places a run monotonically, paying for each
  mismatch and free to skip a row nobody wrote a name against. That page now
  reads 0.506 against the engine's 0.349. **Every number taken on the training
  set before today was taken on labels that were partly somebody else's.**
* **One pairing in the repository rather than three.** The menu bench, the
  search bench and the training set now pair through `truthset.pairs`. The
  matrix is unmoved — 87/97/105 by name alone, 118/123/129 with the crossing
  named — over 138 hand-read names rather than 142: four sit on no row the
  engine read, and counting them against a neighbour's row was the only way
  they were ever counted.
* **An instrument for the reading itself.** `score_crops.py` joins a sidecar to
  the labelled set by document, page and row and reports character error for
  both readings of the same rows, the second recogniser's beside the engine's.
  `bench_search.py --matrix` says whether a second opinion makes anybody
  findable; it never said whether the second recogniser read the ink at all,
  which is exactly what went wrong last week.

**Measured.**

* **The second opinion, finally asked with the right pictures.** The subcorpus
  was cut and read again on the plain band crop: CER 0.567 against the carved
  crop's 0.609 and the engine's 0.365 on the same 152 labelled rows. Last week
  that gap was quoted as 0.892 against 0.338 and it was mostly the mislabelling
  above. In the index, counted with the guesses, the second reading is worth
  **87/97/105 → 90/103/110** by name alone and costs nothing when the crossing
  is named. It reaches a name the archive knows, where the engine's reading
  reaches none, on 30 of 152 rows.
* **It was measured unfairly first, then fairly, and the answer did not move.**
  The sidecar is keyed to the reading taken when the crops were cut; the index
  held whatever each dossier was last read as, and today's reading agrees with
  the stored one on **100% of the hand-read pages and 58% of the rest** — the
  targets read twice more reliably than their competitors, the 28% bias wearing
  another hat, and running in favour of the gain. So the subcorpus was read
  again with `--write-records`, which writes the reading beside the crops
  (`data/freshcache`), and the whole thing was run over that: 1,787 of 1,865
  rows paired, 21 refused where the stale index refused 42%, and **the same
  three rows to the name**. `--second-bands` is what refuses a row whose two
  readings disagree; it compares the reading against the tail of the indexed
  text as well, since a row written with a repetition mark is indexed as the
  words above it followed by its own, and without that it refused 486 instead
  of 97. `export_bands.py --write-records` closes it in one pass next time.

* **155 labelled crops are not enough to train on, and that is now measured.**
  With the crops right and the labels right, `spike_finetune.py` was asked the
  question the set was built for. Three epochs on 149 crops take the held-out
  page from CER 0.340 to **0.451** — the training loss falls 1.708 → 0.314 and
  what the model learns is the archive's vocabulary, not its hands: `GUIDO
  CONTADORE` reads as `Gaudi Santos` after training and `A. VIEIRA MIRANDA`
  collapses to `Santa`. One epoch at a lower rate, scored on a 48-row page
  instead of a 6-row one, moves nothing: 0.606 → 0.605. The direction stands
  and the price of it is now known: labels in the hundreds, from people using
  the review screen, not another afternoon of spikes.

* **Re-reading is worth more than anything measured today.** The fifteen
  dossiers were read again with today's engine: 1,327 rows carrying a name
  became **1,865**, so 565 rows now hold a name where the record had none —
  and the matrix over the refreshed cache is unmoved at 87/97/105 and
  118/123/129 against an index 577 rows bigger, so the extra competition costs
  nothing. A third of that slice was already fresh, so the corpus-wide figure
  is likely larger. The second opinion, for comparison, is worth four to seven
  names of 138.
* **The corpus is a fortnight behind the reader, and no stamp can see it.**
  Today's reading agrees with the stored one on 58% of the subcorpus's
  non-hand-read rows, and where they differ it is usually better now — 431 of
  660 records were read on 08-21, 162 on 08-28, and the reader has had 27
  commits since 08-20. `read_schema: 18` is current on every record because
  that stamp moves when the *parse* changes, not when the crop or the geometry
  does. So the search is worse than the engine is, and every measurement that
  pairs a fresh reading with the stored corpus is biased by which pages happen
  to have been re-read. Options are written up in the tasks file; a re-read is
  34 hours of background pass and is Allan's call.

### Start here next time, in order

0. **Read the corpus again — this is the biggest thing on the list and it is
   Allan's to say yes to.** Fifteen dossiers read again gained 565 rows
   carrying a name, and it costs half an hour of engine per fifteen, so the
   whole corpus is somewhere around eleven hours of background pass. It writes
   into a copy and cannot touch what is there:

   ```sh
   cp -r data/transcriptions data/reread          # copy, never hardlink
   .venv-ocr/bin/python scripts/export_bands.py --records data/transcriptions \
       --out data/reread-index --write-records data/reread --no-crops
   ```

   Then compare `data/reread` with `data/transcriptions` — rows carrying a
   name, and `bench_search.py --matrix --cache data/reread` — and if it holds
   up, that copy becomes the corpus. Rows anybody typed, chose or ticked come
   through untouched (T4), and the schema stamps are unchanged, so nothing
   downstream thinks it happened by itself.

1. **Ship the second reading as a guess.** The fair run finished at 13:55 and
   answered it: over `data/freshcache`, where the sidecar and the index are the
   same reading (1,787 of 1,865 rows paired, 21 refused against the stale
   index's 42%), a second reading counted with the guesses is worth
   **87/97/105 → 91/104/111** by name alone and costs nothing when the crossing
   is named — the same three rows as the biased run, to the name. Counted as a
   *reading* it is 93/105/113 and loses three when the crossing is named, which
   is the stroke spellings' trade and not worth making.

   What is left is not the measurement, it is the plumbing: the second reading
   is ~2 s a row (`Riksarkivet/trocr-base-handwritten-hist-swe-2`, plain band
   crop, `--refine 64`), so it belongs in the offline batch and probably only
   on the rows the check flags. Sizing that is the open question. Everything
   needed to redo the numbers is on disk: `data/bands-fair` (crops),
   `data/side-fair.json` (the second reading), `data/freshcache` (the corpus
   with those fifteen dossiers as they were read), and

   ```sh
   .venv/bin/python scripts/bench_search.py --matrix --cache data/freshcache \
       --second-opinion data/side-fair.json --second-bands data/bands-fair \
       [--second-as-guess]
   ```

   One caveat about that copy: it was written before `--write-records` learned
   to refresh a page's geometry as well as its rows, so its grids are August's
   beside this morning's readings. The bench never looks at geometry — but do
   not cut a crop from `data/freshcache`, and a re-run of the export now writes
   both correctly.
2. **Grow the labelled set**, which is the only thing standing between here
   and an archive-trained recogniser. `training_set.py --records` harvests
   every correction in the corpus and there are four; the set is otherwise the
   151 hand-read rows. Fine-tuning on that many is measured and it does not
   work, so what is wanted is people at the review screen, or another page or
   two read by hand.
3. **Then fine-tune again and score it like everything else**: `read_bands.py`
   puts any model in front of the same ink, `score_crops.py` says what it
   read, and `bench_search.py --matrix` says whether anybody is easier to
   find.
4. Still open and untouched by any of this: T3's `bench_columns.py` and
   per-column truth, and T10's other columns. Both want a cursive page whose
   columns read at all, which T11 measured and found they do not.

## 2026-09-03 — the day handwriting became the only question

Allan settled the open question at the top of the day — handwriting is the
point of this tool, typed pages need no help — so everything below is ranked
by what it does for a cursive page.

**Shipped.**

* **The faint hand (T13).** The stroke rules knew the way from `Tuan` to Juan
  and only ever offered it to a person with the row open. They are indexed
  now, gated four ways, each gate measured. By name alone, of 142 hand-read
  names: 87/95/100 → 87/97/105 at five, ten and twenty; a searcher naming the
  crossing loses nothing. On the page it was written for, 10 of 36 read rows
  are reachable by typing a real name where none were.
* **A minim slip.** A re-cut keeps the stroke count, so it reaches `Maria`
  from `Mania` and can never reach `Gerolamo` from `Gerolano`. One minim more
  or fewer, costed at two, made only where a known name comes out.
* **The menu's first line (T7).** The archive's top suggestion held it and is
  a spelling neighbour that knows nothing about the ink. Where it is distant
  and one stroke rule reaches a name somebody has read, the ink takes the
  line: 0.235 → 0.267 right at rank one, nothing lost deeper.

**Measured and not shipped, which is the more useful half.**

* **No pretrained recogniser beats the engine.** Five were scored on the same
  crops and truth. The best, a French historical hand at CER 0.257, still
  loses to the engine's 0.205; the English IAM models are at 0.607 and 0.785.
  An archive's hand is worth a third of the character error over IAM, and it
  is not enough.
* **A second recogniser's reading, indexed beside the engine's — still
  unanswered, and both of today's numbers are unfair.** It looked worth five
  names at 28% pairing, and that was a selection rather than a sample: the
  pages that paired were the hand-read ones holding every row the bench looks
  for. Fixing coverage to 82% took the gain away — but that run fed the second
  model the engine's *carved* crops, which it reads at CER 0.892 where it
  reads the deskewed strip at 0.338. So the second question was asked with the
  wrong pictures. Nothing was shipped on either number. The fix is one step:
  export the strip crop beside the carved one and measure again.

**Asked, and half answered.** Allan's Cyrillic hypothesis — that a clerk who
learned to write in Cyrillic carried its shapes into these Latin names.

* **The evidence that stands:** over the hand-read truth, the substitutions
  those shapes predict are 4 of 210, no dossier above 4%. This reads the
  engine's stored readings against the truth and is untouched by the crop
  problem below.
* **The evidence that does not:** two Cyrillic recognisers put in front of the
  engine's crops named 0 and 2 rows against the engine's 313, collapsing to
  short common Russian words — but those are the same *carved* crops that made
  the second-opinion run unfair, so this half has to be run again after the
  fix. Both halves also miss the page he was actually looking at.

So: no support in what can be seen, and naming the dossier would settle it
faster than any of this. See `docs/TASKS-reading-quality.md`.

### Where the old list stood, before today



1. **Give `export_bands.py` the strip crop as well as the carved one.** This is
   the one thing blocking a real answer on the second opinion, and it is
   plumbing rather than research. The engine's carved crop cuts a band to its
   own ink and TrOCR reads it at CER 0.892; the deskewed strip crop of the same
   row reads at 0.338. Both come out of the same `analyze(page)`, so the row
   number is available on both sides. Then run
   `bench_search.py --matrix --second-opinion … --second-as-guess` again over
   the subcorpus and the 82%-coverage number finally means something.
2. **Keep the crops for rows a person corrects.** `training_set.py` builds 152
   labelled pairs out of the truth pages today. Every correction on the review
   screen is another one, and nothing on this list is possible without a bigger
   set. It costs nothing to start and it compounds.
3. **Then measure whether 152 is enough**, with `spike_finetune.py` — but only
   after (1), because its `before` number was taken on the carved crops and is
   meaningless until they are readable.
4. Still open from before and untouched by any of this: T3's
   `bench_columns.py` and per-column truth, and T10's other columns. Both want
   a cursive page whose columns read at all, which T11 measured and found they
   do not.

### How to resume the runs

The scratch data lives outside the repo and is gone when `/tmp` is cleared;
everything below is cheap to rebuild and all of it checkpoints and resumes.

```sh
# the 15-dossier subcorpus, chosen the same way every time: the dossiers with a
# hand-read page, then the rest in hash order until there are fifteen
.venv/bin/python scripts/subcorpus.py --out data/subcache
.venv-ocr/bin/python scripts/export_bands.py --records data/subcache --out <bands> \
    --write-records <freshcache>       # ~30 min: crops, and what was read
.venv-htr/bin/python scripts/read_bands.py --bands <bands> --out <sidecar> \
    --variant strip --refine 64        # ~2.5 h, and the long pole of the day
.venv/bin/python scripts/training_set.py --bands <bands> \
    --records data/transcriptions --out <trainset> --variant strip
.venv/bin/python scripts/score_crops.py --sidecar <sidecar> --trainset <trainset>
.venv/bin/python scripts/bench_search.py --matrix --cache <freshcache-or-corpus> \
    --second-opinion <sidecar> --second-bands <bands> [--second-as-guess]
```

`<freshcache>` has to be a **copy of the whole corpus cache** with the fifteen
refreshed records written over it — `cp -r data/transcriptions <freshcache>`
first, and copy rather than hardlink, or the write lands on the original — so
the rows competing with the targets are still there. Point the bench at that,
or the sidecar is pasted onto a reading taken weeks earlier: without it,
`--second-bands` refuses every row whose two readings disagree, which is 42%
of the subcorpus and almost none of the pages being searched for.

`read_bands.py` and `spike_second_opinion.py` write after every page and skip
what is already done, so a killed run loses one page. Two things took a run
down silently before that was true: `name_strip` raises
`SystemExit("no grid detected")` on a page with no ruled table, which
`except Exception` does not catch, and a page whose crop step allocates enough
to be killed outright. Both are handled; the marking happens *before* the page
is read so a fatal page is skipped on the next run rather than retried.

### Two traps worth not rediscovering

* `pgrep -f "spike_x"` matches the waiting shell's own command line, so
  `until ! pgrep -f …; do sleep; done` never exits. Wait on a PID file or on
  the output file instead.
* `nohup … | tail -30 &` shows nothing until the job ends, so a long run looks
  hung. Redirect to a log and read the log.

## 2026-08-29, evening — two names in one word

Tests green: **681 Python assertions, 9 skipped; 126 browser assertions in both
browsers.**

The reference-set baseline said two of its six tables read essentially no word
this archive has ever seen, and both were looked at rather than guessed about.
Neither is a geometry failure. On **OL.PRJ.17347 p16** the rows are cut, 28 of
29 read, and the names are there under the damage — the commonest fault is two
names run into one word: `MattenceSuireppe`, `MarcelloNittoms`,
`MerleltaForlunato`. A person searching *Giuseppe* shares no whole word with
any of them, so the dossier is a ship nobody can find a name in.

**The cut is taken where a capital stands inside a word.** The recogniser
dropped the space the clerk wrote and kept the capital that followed it, so the
cut is evidence off the page and not a guess about it. It is indexed in `alts`,
beside the reading, where a row's second reading already goes and is already
scored — a new candidate, not a new mechanism — and what is stored is
untouched.

**And a hit says which spelling found it.** `matched` names the *kind* of
match — year, ship, line, letters — and never said which of a row's spellings
won, so a search for *Giuseppe* could land on a row whose stored reading holds
no such word with nothing on screen to explain it. `search.name_the_spelling`
runs over the hits that will be shown, not inside the scoring pass, and the hit
list prints *encontrado como “…”* under the reading — only where another
spelling reads the query better than the reading does, because a hit that
explains itself when it did not need to is noise.

Tried first and rejected, so nobody tries it twice: cut where **both halves are
names the archive has read**. On the page it was written for it splits nothing,
because the glue and the misreading come together and `Suireppe` is no more in
the dictionary than `MattenceSuireppe` is. A list cannot carry this cut.

`bench_search.py --matrix` moves for the first time in this session — 86→87 of
142 in the top five by name alone, 99→100 in the top twenty, 122→123 with the
crossing named, nothing lost. The hand-read pages are not the pages this was
written for; across the corpus **1,361 of 37,617 stored readings** carry a word
a capital cuts in two, and each was unfindable by either of its names.

The reader is sent there too: `colado` is a fifth reason in the check, catching
0.041 of the badly-read rows and **stopping nobody on a row that was right** —
the only reason in that table with no cost. It adds nothing to what the four
existing reasons catch together, and is kept for what it says rather than what
it finds: *two names in one word, retype it* is different advice from *the
engine was unsure*.

**What is left of that page's neighbour.** OL.PRJ.16030 p3, the faint hand,
reads 36 of 37 rows one or two letters from a name — `Nose` for José, `Tuan`
for Juan, `Gerolano` for Gerolamo. Search will not reach those: a four-letter
word shares almost no trigram with another, and the edit-distance pass that
would catch it runs only inside a crossing somebody named — over the whole
corpus it was measured in July and is worth nothing. That one is not a search
fix, and what remains of it is the recogniser.

## 2026-08-29, evening — the plan's last two tasks, and a wall worth naming

Tests green: **673 Python assertions, 9 skipped; 126 browser assertions in both
browsers.** `bench_search.py --matrix` measured before and after every commit
of T6 and unmoved every time: 86/95/99 of 142 by name alone, 118/122/129 with
the crossing named.

**T6 — the name split is gone.** `split_name` took the last word of a reading
as the given name, which is the convention these clerks mostly used and one a
dossier breaks: the same passengers appear twice, once in German with the
surname first, and there the split filed four people under *Benito*. The engine
writes `name_raw` and the score; `ditto.resolve` writes `inherited` and marks
the field `name`; `ditto.written` is the row's own words with the mark dropped;
the review screen no longer splits what a person types. `conf` is keyed `name`,
because that number was always the score of the name strip. The spreadsheet
carries `repete_de_cima` and `nome_completo` where it carried *sobrenome* and
*nome*.

Nothing on disk was rewritten and nothing was re-read: 660 records carry the
old fields, `desembarque/rowfields.py` and `search.row_text` understand both
shapes, and only the new one is written.

**T11 — the language prior ships, and cannot yet be measured as it is used.**
The nationality column says which language a row's names are written in, so the
menu compares a badly-read word with that language's names first. All 259 names
in `data/language_names.json` are now grouped by language, a name belonging to
every language that uses it. It orders and never filters.

Then `scripts/read_nationalities.py` read that column on the six hand-read
pages, and **none of the 48 cells with ink snapped to a word these forms
print** — `tiuin`, `geil`, `Bueclibme`. The column is legible on typescript and
not in this cursive hand, the same wall idade and sexo hit. So the prior was
scored at its ceiling instead, with the language *given*: 0.235 → **0.263** at
rank one over 217 badly-read words, the same 82 names found in a better order,
and nothing past rank three. Six words. It ships because it costs nothing and
fires wherever the column reads; the number is a ceiling and is written down as
one.

**The reference set has a check now**, `scripts/bench_refset.py`, which the
methodology described in the last checkpoint and nothing implemented. It reads
the seven pages and says what each comes back as — kind, rows cut, rows with a
reading, words the archive has read before, cells and snapped cells. Nothing is
scored against a truth file, because five of the seven have none: the question
it answers is *did this page stop being empty*.

| shape | kind | rows | read | dict | cells | snap | s |
|---|---|---|---|---|---|---|---|
| typewritten, headings over columns | list | 31 | 27 | 14 | 59 | 26 | 25.9 |
| cursive, headings printed, truth exists | list | 48 | 48 | 8 | 45 | 0 | 24.9 |
| heading printed away from its column | list | 18 | 17 | 5 | 2 | 1 | 8.7 |
| name column stored as the ordinal strip | list | 29 | 28 | **0** | 24 | 0 | 14.9 |
| faint, low confidence, cursive | list | 37 | 36 | **1** | 35 | 0 | 19.5 |
| continuation page, no heading line | list | 41 | 40 | 4 | 50 | 3 | 30.1 |
| not a table at all | unknown | 0 | 0 | 0 | 0 | 0 | 43.1 |

Read as a baseline: the geometry finds rows on all six tables and the cover
card still comes back as no table, which is what it must do. What the table
says is where the reading stands rather than the cutting — **two of the six
pages read essentially no word this archive has ever seen**: the page whose
name column was the ordinal strip reads 28 rows and not one known word, and the
faint cursive page reads 36 rows and one. Those are the two shapes to work on,
and they are the shape of the 8% that yield nothing.

Two smaller things the table shows: the cover card costs 43 s to decide it is
not a table, which is the most expensive page in the set and the one with
nothing on it; and the cursive pages return cells that never snap, which is the
same finding T11 ran into.

**What this leaves.** The reading-quality plan has no open task. What is left
is the wall both of these ran into: a cursive hand the recogniser cannot read
in a narrow column. The refset is where that gets worked on — one page per
failure shape — and the next thing worth doing is the eight per cent of
documents that come back with no readable row at all, because a dossier that
yields nothing is a ship nobody can search and the run reports success.

## 2026-08-29, evening — the columns are read, and three things were writing into the demo record

Tests green: **651 Python assertions, 9 skipped; 126 browser assertions passing
in both Chromium and Firefox.** The six browser failures the last checkpoint
listed are gone, and four of the assertions are new.

**The column reading is reachable.** `cells_from_bands` and the closed
vocabularies have been built, tested and benchmarked since August, and no page
the app read ever came back with a cell: `PaddleEngine.columns` defaults to
none and `register_engines` never passed anything. `serve.columns_wanted` now
asks for `READABLE_COLUMNS` — nationality, civil state, profession — and
refuses idade and sexo rather than paying for them, since they measured 0 of 22
and 0 of 26. `DESEMBARQUE_COLUMNS=none` turns it off; a named list is taken as
written.

Measured through `transcribe_page` on BS.ENT.017397 p2, the typewritten page
transcribed by hand: **16.9 s a page becomes 22.9 s** — a third more, not the
double the crop count suggested, because a blank cell is no longer read at all.
59 cells read across 31 rows, 26 of them snapped to a printed word:
`SEAGNOLA` → ESPANHOLA, `conercio` and `OWEFCIC` → COMERCIO, `cau` → CASADO.

**And it is on screen.** A cell the engine read is shown as read and never as
somebody's typing; where the vocabulary carried the reading to a printed word
the cell is tinted, marked `⌇`, and says on hover what was read and how close
it was. The reading is never replaced by the guess, which is the gazetteer's
rule about names applied to a column.

**Three faults, all the same shape: something automatic writing into a record
that says a person was here.**

* The dedup that followed the duplication bug was incomplete. It collapsed rows
  that were *equal*, and a row saved twice carries a different `edits` list each
  time — so fourteen copies of row 1 survived as distinct rows and the demo
  document showed 41 rows for 26 passengers. `batch.dedupe_rows` uses the
  identity that holds: two rows of one page cannot both be row 1. It keeps the
  fullest copy and merges every copy's edits.
  **`scripts/dedupe_corpus.py --dry-run` checks the whole corpus** — one record
  was affected, and it is repaired.
* The browser self-test was writing an edit into that record on every run: it
  types `SIRVIENTA` into a cell that already says SIRVIENTA, and each run
  recorded another act by a person. Sixty-six entries, four acts.
  `batch.tidy_edits` collapses a run of the same word into the same field,
  applied where the rows are stored rather than trusted to the client.
* A save was moving `transcribed_page`. It is how a record whose rows carry no
  page number finds its scan, so a save posted while the demo sat on page 1
  showed the 26 typed rows beside the wrong page. What the client is looking at
  is not a claim about where the transcription is.

`transcribed_by` is now derived from the rows rather than stored, because the
stored flag was lost by exactly such a save: a record holding a value in a
column the engine has never written was typed by a person.

**Next, in order.** T6's second half — `surname`/`given` come out, 108 test
references and a session of its own, and it is what the plan says is next. Then
T11, the language prior, which T10 no longer blocks. The cursive per-column
truth page (T3) still needs a hand reading before any column number can be
quoted for handwriting.

## 2026-08-29, afternoon — the name column was measured wrong on half the corpus

Tests green: 630 Python assertions, 9 skipped (the nine are one parametrised
check over `scripts/*.py`, skipped where a script does not import the package).
Browser self-test: 116 of 122 in both browsers; the six failures are older than
this session's work and are listed below.

**The finding.** Allan looked for his great-grandfather across 1919–1925 and did
not find him, and asked whether contrast could recover the barely legible pages.
Contrast is not what was wrong. On OL.PRJ.18109 p20 the page is typewritten and
perfectly legible to a person — *Julio Augusto da Costa*, *Seraphim Gomes
Saraiva* — and the engine read `ete do Coeto`, because the name column was
measured from 0.128 of the sheet while the names begin at 0.014. It was reading
the right rows through the wrong window.

Two causes, both now fixed:

* Where the heading line prints nothing to the left of the name — no *Ordem*,
  no rule the detector finds — the left edge fell back to **two per cent of the
  sheet left of the printed heading**, a constant. It is now taken from the
  page's own rows: the 20th percentile of where the boxes under that heading
  start, and only where at least four rows agree. The five hand-read truth
  pages are unmoved (CER 0.362, 25 exact, 79 findable of 142) and OL.PRJ.18109
  p20 goes from 13 readings and no dictionary words to 17 and five.
* **Half the stored corpus was measured before any of this.** Of 2,543 stored
  pages, 946 carry a name column narrower than a name — 0.017 to 0.06 of the
  sheet is the ordinal strip — 394 carry most of the sheet, and 43 start past
  the middle. `scripts/remeasure.py` reads those pages again, selecting them by
  how unlike their own dossier they measure rather than by any fixed number,
  since the same printed sheet runs the length of a list. **Dry run over eight
  pages: 36 names before, 211 after.** 702 pages are selected in all, so the
  order of magnitude is fifteen thousand passengers who cannot currently be
  found by name.

**The pass has not been run.** It was started, stopped after seventeen records,
and the seventeen it wrote are intact. It should be run to completion — six to
twelve hours — and the index rebuilt after it.

**A row that carried no page number was duplicating the record on every save.**
`merge_page_rows` keeps the rows of other pages and replaces the page being
saved; a row with `page: null` is not another page's, but by the letter of the
rule it was kept, and the posted copy was added beside it. BS.ENT.017397 — the
demo document, transcribed before rows carried a page — had doubled ten times
into 26,624 rows, 1,024 copies of twenty-six. Found while checking whether the
re-measure pass had damaged anything; it had not, this was older and is what
the six browser failures are about. The rule now says a row must *say* which
page it is on before it can be treated as another page's, and the record has
been deduplicated back to its 41 rows. No other record on disk holds a
duplicate row.

**Also this afternoon.** Preprocessing was measured properly and does not help
the engine: background division, CLAHE, adaptive thresholding and their
combinations move the truth pages from CER 0.362 to 0.358 at best, and on four
faint pages they move nothing. What did come out of it is `union findable
124/142 against 118 for the best single variant` — reading a row several ways
finds people no single reading finds — and a **contrast control in the review
screen**, because the recogniser is at its ceiling on a hundred-year-old hand
and a person is not: Original / Realce / Alto contraste / Negativo, applied in
the browser to the image already downloaded, remembered between pages, `\` to
cycle.

**How this is checked, from now on.** `data/refset.json` — outside git, since
it names records — holds one page per failure shape: a typewritten table with
its headings over its columns, a cursive table with hand-read truth, a heading
printed away from its column, a page whose stored name column is the ordinal
strip, a faint cursive page, a continuation page that prints no headings, and a
cover card that must keep coming back as no table. Seven pages. A fix is proved
on the shape it was written for and the corpus is not a test set: re-reading 700
pages to see whether a change worked is hours spent learning what eight pages
already said.

The corpus is not being re-read. `remeasure.py` exists and is proved — 8 pages,
26 names to 133 — and running it over the other 690 produces data, not
knowledge. It is a one-time production step for whenever the reading is good
enough to be worth freezing, and it is not the next thing to do.

**Next, in order.** Make the reading work on the seven shapes. Then the column vocabulary applied to the
cells as Allan asked: the corrected word shown with the reading kept and the
cell's background saying it was corrected automatically. Then the six browser
assertions, which are about the demo document and want re-checking now that it
is repaired.

## 2026-08-29 — the cells were cut right, and three things were wrong instead

Tests green: 606 Python assertions, 9 skipped. One task, T10a in
`docs/TASKS-reading-quality.md`: the column benchmark said four columns read
*nothing* and the checkpoint before this one called that a crop problem —
a heading narrower than its column putting the edge in the wrong place.

**It is not a crop problem.** The columns were drawn over BS.ENT.017397 p2 and
looked at. *Idade* is measured 0.388–0.415 of the sheet and its figures sit at
0.388–0.413; *Sexo* is measured 0.415–0.444 against ink at 0.417–0.442. The
crops hold their writing. The four columns fail for three different reasons:

* **idade and sexo** — the recogniser's floor on a cell of one or two
  characters. The same figures read back `二`, `7`, `1二` off the detector's own
  tight boxes, so no cutting rescues them. A different reader, as a spike.
* **procedencia and classe** — mostly blank on the page. The clerk wrote
  *BUENOS AIRES* once and left the column empty; the hand transcription writes
  it against all 26 rows because that is what the page means. Scoring a blank
  cell against an expanded truth measures the transcriber. Those two want the
  repetition rule the names already have (T6) before a number about them means
  anything.
* **nacionalidade, estado, profissao** read something wrong — `SEAGNOLA`,
  `LASIERCL`, `conercio` — which is a closed vocabulary away from being useful,
  and is the next work.

**What did move.** A cell is now cut at its band and its column exactly, where
it used to be padded out by `PAD_PX` like a name: a name is 300 px wide and
carries the rules at its edges, a cell of 98 px hands the recogniser three
printed lines around two digits. Swept over 0.0 / 0.08 / 0.12 / 0.20 of each
edge trimmed, cutting at the band is best in every column and every trim past
it is worse.

| column | padded out, as it was | cut at the band |
|---|---|---|
| nacionalidade | 0.730 | **0.716** |
| estado | 0.593 | **0.577** |
| profissao | 0.710 | **0.661** |
| procedencia | 0.974 | 0.969 |
| classe | 0.885 | 0.904 |
| idade / sexo | 0.977 / 1.000 | unmoved |

Tried and rejected, so nobody tries them twice: **snapping the column edges to
the gutters between the columns of ink** — the detector merges neighbouring
cells often enough that the body has no white column left to find between 0.29
and 0.68 of the sheet, and the one edge it did move read worse; and
**tightening each cell to its own ink and scaling it to a standard height**,
the usual answer to a small crop, which moved idade 0/22 → 0/22 and sexo
0/26 → 1/26.

**The closed vocabularies, done and measured.** `desembarque/vocab.py` and
`data/column_vocab.json`: the words these forms print in each column, written
by hand, making the language-name file's claim — *these forms print this word*,
never *this archive contains it*. A snapped word is stored as `value` beside
the untouched `text`, which is the gazetteer's rule about suggestions applied
to a column. On the same 26 hand-read rows:

| column | rows | right as read | snapped | of those, right |
|---|---|---|---|---|
| estado | 26 | 1 | 13 | **12** |
| profissao | 22 | 0 | 8 | **7** |
| nacionalidade | 26 | 0 | 5 | **3** |

The floor is per column and swept (0.55 / 0.62 / 0.70): civil state and
profession are short lists of unmistakable words and want 0.55, nationality is
fifty long words sharing their endings and wants 0.70. Listing an abbreviation
as its own word was tried and taken out — `CAS` won `cau` away from CASADO —
and a short reading is compared with the head of the word instead.

**And an empty cell is no longer read at all.** `has_ink` was written for a
name strip 300 px wide, where the printed rules at the edges are lost; on a
cell 98 px wide those rules are four columns of solid ink, so every blank cell
passed as written and came back as `一` or `1`. It now ignores the outer 12% of
a cell. On this dense page — 26 of 31 rows carry a passenger — 243 cells were
read where 216 are now, and *Procedencia*, written once at the top of the sheet
and blank below, went from 29 cells read to 10.

**A faint page is equalised before it is given up on** — Allan's question, and
it has a measurable answer. `scripts/spike_faint.py` puts four ways of lifting a
page in front of the detector on the pages that read nothing at all. Two of them
do nothing: autocontrast and a 2nd/98th-percentile stretch each move the box
count by one, because these scans already use their range end to end — grey ink
on grey paper with the black point already black. Equalising is the one that
moves.

| OL.PRJ.17851 p2 | boxes | name column | rows |
|---|---|---|---|
| as it is | 32 | found | **0** |
| autocontrast | 32 | found | 0 |
| stretch | 32 | found | 0 |
| **equalised** | 71 | found | **29** |

**And then it turned out there is no page here that wants it.** The lift was
wired in as a last resort, and measured again with a counter on it: on
OL.PRJ.17851 p2 it never fires, because that page already comes back with 45
bands and 23 names — the ruled fallback catches it, which the box count alone
does not show. The twelve records on disk holding no rows were then read one by
one with the engine: all twelve still come back `unknown`, and they print no
heading line at all, because they are covers and interpreters' PARTEs rather
than lists.

So `lift` is written, tested and documented, and deliberately **not called**.
On a page where it did fire it would turn paper grain into rows — the same page
whose seven clean printed headings become `oshdepaxdnley` when equalised — and
there is no page in this corpus it would rescue. The comment in
`_printed_table` says where it would go and what would have to be true first.

What is worth having from this: `retry_unknown.py --again` now exists, and a
page stored as a `list` with no rows on it counts as wanting a reading, which
it did not before — the same failure as an `unknown` page wearing the other
label. Both are how the next thing the engine learns reaches the pages that
read nothing, without the eleven-hour re-read a schema bump costs.

Next, in order: wire `cells_from_bands` into `transcribe_page` and take the
cost decision with it (31 bands × 8 columns is 216 crops against the name
column's 31; the three columns worth reading are 90); the repetition rule for
procedencia and classe (T6); then a reader for one- and two-character cells.

## 2026-08-28, evening — the reading, not the retrieval

Allan away 21:00–23:00. Everything below is committed and pushed, tests green
(591 Python assertions, 93 in each of Chromium and Firefox). Work order and the
measurement beside each step: `docs/TASKS-reading-quality.md`; the argument is
in `docs/superpowers/plans/2026-08-28-reading-quality.md`.

**Two instruments exist that did not, and every claim below is one of their
numbers.** `scripts/bench_menu.py` asks whether the name a page carries is in
the menu a person opens on a badly-read word, and at what rank; it pairs the
hand-read pages in `data/truth` against the readings already stored, so no
recogniser runs. `scripts/bench_check.py` asks which reasons for a second look
actually find the badly-read rows, and how often each stops somebody on a row
that was right. The pairing both share is `desembarque/truthset.py`.

### The menu now reaches the right name twice as often as the archive alone

| the menu the server returns | true name offered | @1 | @3 | @5 | @10 |
|---|---|---|---|---|---|
| the archive's names, as it shipped this morning | 77 of 217 | 0.157 | 0.309 | 0.355 | 0.355 |
| + candidates built from the strokes | 83 of 217 | 0.161 | 0.323 | 0.378 | 0.382 |
| + a hand-written list of names these languages use | 87 of 217 | 0.161 | 0.359 | 0.392 | 0.401 |

`desembarque/strokes.py` generates what else the same ink supports: minim runs
re-cut every way the stroke count allows, a tall stroke read the other way, a
round letter read as its neighbour, the clerks' abbreviations, ink trimmed at an
edge — which on these pages is mostly the next column bleeding into the name
strip, `SANTOSPOR` for *Santos* — a looped capital read back from the two or
three letters it was cut into, and a word the clerk wrote as two. Per rule,
alone, over 217 badly-read words: ascender 21, edge 9, two changes 9, round 8,
capital 7, space 5, minims 1, abbreviation 0. The minim re-cut is the model the
plan is built on and has found one name so far; it is ranked last among the
readings nothing backs, and it stays until the pages its examples live on are
scorable.

`data/language_names.json` is 259 names written by hand from the languages these
ships carried. It is a different claim from `data/names.json` and kept apart
from it: *these languages use this name*, never *this archive has read it*. It
ranks below everything the archive has read, is capped at four per menu, and the
names that appear only on the hand-read pages were left out so the bench
measures the rules and not the file. A twelve-name menu is what ships; sixteen
buys 0.005 and costs a person the scan.

### The marking was asking the opposite question

`doubtful` flagged a row when *nothing* in it resembled a name this archive
carries. A reading nobody here has read is usually a rare name — this archive is
full of them and they are correct. A reading one re-cut minim from a name read
ninety times is the strongest evidence of a misread the tool has, and it was
the case the flag let straight through: `YOSE` resembles `JOSE`, so the row
passed.

| reason | catches the badly-read rows | stops on a good one |
|---|---|---|
| score (engine unsure) | 0.595 | 0.036 |
| inferido (the mark's words inherited) | 0.314 | 0.036 |
| desconhecido (nothing here is like a name) | 0.000 | 0.000 |
| **quase (one stroke from a name)** | **0.587** | **0.214** |
| the three there were | 0.702 | 0.071 |
| all four | 0.868 | 0.250 |

The language list adds 0.008 to that and is not used for the flag.

### A correction no longer freezes the rows beside it

The mark saying a person was here sat on the *record*, so one corrected row
held forty untouched ones at the quality of the day they were first read — on
exactly the documents being worked through. It is asked per row now: a row
somebody typed into, chose a reading for, or ticked is theirs and survives a
re-read verbatim, and everything else is the engine's.

Underneath it was a second loss. The review screen posts the page in front of
the reader and the save wrote that list as the record's whole `rows`, so
correcting page 2 of BS.ENT.013947 deleted pages 3 to 11. Only the saved page is
replaced now. **The four frozen records were read again to prove it**, and
the pages the old save had dropped came back: BS.ENT.013947 406 rows on pages 3
to 11, BS.ENT.016331 207 rows on pages 2, 3, 4, 6, 7 and 8, BS.ENT.013990 two
more, and the typed rows kept verbatim in every one. BS.ENT.013942 came back
with 31 rows where 33 were stored — the geometry cuts that page into two fewer
bands than it did in August, and both rows Allan typed survived. That re-read is
also why the benches score 149 rows instead of 87. The two hand-typed records,
BS.ENT.017397 and BS.ENT.015368, were left alone: they have no engine rows to
refresh.

The two values Allan saw on BS.ENT.013942 — `SIRVIENTA`, `BELGA` — are not
fossils of an early pass. Both carry `edits` stamped at the review screen on
2026-08-21, and the engine has never written those columns in any of 660
records. Nothing was deleted; a value a person typed now says so on screen.

### The other columns are measured now, and one has been read once

The plan said §4's column edges were already there. They were not: the
geometry measured the name column and the ordinal beside it and dropped the
rest of the heading line, so nationality, age, civil state, profession, port,
class and the notes had no edges anywhere in the corpus — a cell nobody could
crop, let alone read. They come off the same fragments the name column's edges
come from, at no extra cost, and they travel with it to the pages of a dossier
that print no headings. Stored under `all_columns`; `columns` keeps meaning the
name column, which is what every record on disk means by it.

Two things had to be got right for a real page rather than a fixture. The
boxes that carry the geometry mostly carry no text — only the heading line is
read, because detection is three seconds against eighty for a whole page — so
the naming looks the text up in that reading. And the boxes for *Edade* and
*Sexo* on BS.ENT.017397 come back empty, two narrow words on a printing read
cleanly everywhere else, so an unread heading between two read ones is named
by its place in an order these forms all print, and says it was named that way.
BS.ENT.017397 p2 measures ten columns.

`cells_from_bands` cuts a column's cells the way the name column is cut — the
recogniser injected so it is testable without the model, a short answer padded
with nulls, and a column the page never measured returning nothing rather than
a guessed edge. Run once with the real recogniser on that page: nationality
comes back `ISPAGNIA`, `ESPANOIY`, `SEANOL`, `RASIERAL` against *ESPANHOLA*
and *BRASILEIRA*, which is the shape of a column that can be read and snapped
to a closed vocabulary. Age comes back `_` and `1`: its heading is 2.8% of the
sheet wide and the figures are not under it, so the edge halfway to the next
heading is the wrong rule for a narrow heading over a wide column. `scripts/bench_columns.py` now scores exactly that,
against the 26 rows of that page somebody typed by hand:

| column | rows | exact | mean CER |
|---|---|---|---|
| nacionalidade | 26 | 0.000 | 0.730 |
| idade | 22 | 0.000 | 0.977 |
| sexo | 26 | 0.000 | 1.000 |
| estado | 26 | 0.077 | 0.593 |
| profissao | 22 | 0.000 | 0.710 |
| procedencia | 26 | 0.000 | 0.974 |
| classe | 26 | 0.115 | 0.885 |

Bad, and usefully bad: it separates two faults. The columns that read
*something* wrong — nationality, civil state, profession — are a recogniser and
vocabulary problem, and a closed vocabulary is worth a great deal there. The
ones that read *nothing* — age, sex, class, port — are a crop problem, their
headings being narrow over wide columns. The crop comes first: snapping to the
nearest allowed value cannot rescue a cell that was never cut. **No column
reading ships until those numbers move**, and the cursive half still has no
truth file — a number measured on typescript is not a number about the hand.

### What is next, in order

1. **Stop asserting surname and given** (§1), the half that is left. The
   repetition mark now inherits the words written above it, from the left,
   counting only the words its own row does not write — no claim about which
   word is the family name, and `bench_search.py --matrix` unmoved at 86/95/99
   of 142. But the engine still calls `split_name`, and `surname`/`given` are
   still written and read by search, export, the voyages report and the review
   screen. 108 test references sit on those two fields; it is a session of its
   own.
2. **The other columns** (§4). The edges are measured and the cutting is
   built; what is missing is `scripts/bench_columns.py`, a per-column truth
   page, a column edge that does not assume the heading is as wide as its
   column, and the decision about cost — a page is forty bands by eight
   columns against twenty seconds a page for the one column read today.
3. **Re-read the corpus** once §1 lands, and re-run both benches: five of the
   six truth pages are read by an engine whose rows predate every change above.
4. The language prior (§7), which depends on 2.

## 2026-08-28 — the whole archive, measured instead of extrapolated

Allan away until 13:00. Everything below is committed and pushed. **Start here.**

### What the index costs at 7,679 dossiers, now that it has been stood up

Every number this log has printed about the corpus past 660 dossiers was an
extrapolation from an eleventh of it, and the two structures that grow worst —
the trigram postings and the folded readings — were both written after the last
one. `scripts/bench_scale.py` stands the transcriptions on disk up two, four
and twelve times over as symlinks (no disk, no reading) and measures each size
in a child process with an address-space cap, so a size the laptop cannot hold
kills the child rather than the desktop.

Twelve times is 7,920 dossiers, which is the archive with room to spare.

| at 7,920 dossiers, 372,816 rows | this morning | now |
|---|---|---|
| cold load, one process | 96 s | **15 s** |
| the keystroke's own overhead, before a row is scored | 258 ms | **64 ms** |
| `Contadore` — trigrams only | 105 ms | **7 ms** |
| `Manoel da Cruz Valdivia` — letter pass, ship named | 365 ms | **47 ms** |
| `Maria Silva Gelria 1924` — letter pass over a year | 486 ms | **202 ms** |
| the index in memory | 295 MB | 297 MB |

**Memory is not the wall and this log can stop saying it is.** The whole
archive's rows, postings, crossings and folded readings together are under
300 MB — a third of what the November note assumed wanted a database. What did
not survive the size was everything asked *per keystroke*, and four things were
paying for it:

* **The keystroke spent its time in `pathlib`.** A `Path` built per file and a
  sort that compares them part by part: 200 ms of the 258 that `/api/search`
  spent finding out that nothing had changed. `os.scandir` hands back the name
  and the stat together and the sort is over strings. The flattening itself is
  kept now too — copying 370,000 row references to discover the corpus is as it
  was — and dropped as soon as *this* load reads something, which is not the
  same as the global count of readings: a bench pointed at its own directory
  bumps that without touching a row of the application's index. For the same
  reason the eviction sweep is confined to the directory being loaded, so the
  bench and the application stop emptying each other's caches.
* **A cold load spent 21 of its 25 seconds on the form's own printing.** Every
  word of every row was matched letter by letter against forty printed words.
  A ratio is twice the matching letters over the two lengths together and the
  matches cannot outnumber the shorter word, so a word too short against a
  printed one is ruled out without being matched at all, and `quick_ratio`
  bounds it again by the letters they share in any order; the answer is then
  remembered per word, and the corpus repeats its words endlessly. A test holds
  the fast path to what the plain measure returns on the words this corpus
  trips on — `gomes` against `cognomes`, `romano` against `comando`.
* **Counting the trigram overlap was a Python loop over every posting.** Five
  million dictionary lookups for `Maria Silva` over the whole archive. The
  postings are arrays of machine integers, so the count, the arithmetic and the
  best-of-two-readings are done over the lot at once with numpy — a dependency
  the page geometry has had from the start. Two thirds of what came back was
  waste: `search` drops a row whose name score is under the floor before asking
  it anything else, and 67,000 of the 103,000 rows that query returned were
  under it, sharing the padding trigrams of a name and nothing else. The floor
  is the caller's, so a caller that lowers it still gets what the higher one
  hid.
* **Three places asked the corpus what ships it holds by walking every row.**
  Which ships and lines the index names is a fact about the corpus, not the
  query, and the rows have carried an index by ship, line and year since
  yesterday. The passengers of a named ship, line or year now come out of it by
  row number instead of by filtering the corpus.

Nothing above moves a result, and the point of the exercise was to be sure of
that: findable is 122 of 142 with the crossing named and 89 without, the same
as at the start of the morning, and the suite is at 527 with new tests pinning
the bulk count to what scanning every row returns, score for score, and the
indexed answers for ship, line and year queries to the scanned ones.

The one that nearly went wrong is worth writing down. The flattened index was
first stamped with the global count of readings, which is bumped by *any* load;
two loads of two directories then invalidated each other on every request and
the cache would have been dead weight. The test that caught it is two caches in
one process, which is exactly what a bench beside the application is.

### What a row holds besides the name was being held against it

The open problem in this log for a week has been a common name in a large
pool, and the lever that worked was the crossing. This is the first thing that
moves the other case — somebody who types a name and knows nothing else.

A row is not only a name. It carries a title, a class of passage, a surname
resolved from the repetition mark above it, and whatever the recogniser made of
the ink beside it. The score was the overlap of the query's trigrams with the
row's over the *union* of the two, so every one of those extra words counted
against the row — and it buried exactly the rows that hold everything somebody
typed. `Lorenzo Maria`, read as `Maria` with the rest of the line around it,
sat below a thousand rows that read as nothing else.

A reading is now forgiven material beyond the query up to three quarters of
what was typed, and charged for the rest:

| typed by name alone, 142 hand-read names | before | now |
|---|---|---|
| findable in the top five | 79 | **86** |
| findable in the top ten | 89 | **95** |
| findable in the top twenty | 99 | 100 |

Measured the way the application searches — with the archive's own catalogue of
ships indexed, which is what `scripts/bench_search.py --matrix` now does in one
load of the index rather than six. Without the catalogue the same change reads
81 → 88 and 89 → 96, and it was worth finding out that the two configurations
do not agree to the name.

The forgiveness is asked only of a searcher who cannot name the crossing.
Inside a named ship, line or year the pool is already a few hundred rows, and
what orders them is how much of the *row* is the name rather than how much of
the name is in the row: forgiving the rest there promotes the long noisy rows
of the same dossier and costs ten of the 118 that come back in the top five.
So the strict question is asked when the crossing has narrowed the pool and the
forgiving one when nothing has, and the crossing numbers are unchanged —
118 / 122 / 130 at five, ten and twenty.

Two consequences, both handled rather than left to be found later. The two
questions do not put their scores on one scale, so the tests that compared a
row's score across two queries now compare where it lands in the list, which is
the property the product has and the person sees. And the page's *"nothing
convincing — name the ship"* advice reads an absolute score: the server now
says whether the query named a crossing and what the bar is for the scale it
used, and the advice is only shown to somebody who did not name one. Below 0.7
the search had failed 62% of the times it failed, and the bar is wrong about a
search that worked 39% of the time, against 57% and 33% for the old bar on the
old scale.

### Measured and rejected, with the numbers

| | result | verdict |
|---|---|---|
| **weighting a trigram by how rare it is** — `MAR` occurs in a tenth of the corpus and `LCZ` in five rows, so the surname a searcher actually knows is outvoted by the given name beside it | with the crossing named it is worth **+6** (122 → 128 in the top ten); by name alone it costs **−3** (89 → 86), at every strength from 0.25 to 3 | not taken. The rare trigrams of a badly read row are the recogniser's own mistakes, so rarity punishes the rows this tool exists to find |
| the same, scoring only how much of the **query** is present and not charging for the rest at all | by name alone 93 in the top ten, with the crossing 124 — better than rarity, worse than the slack that replaced it | superseded |
| **breaking the ties** the forgiveness creates by the unforgiving score, so the row that *is* the name comes before the row that merely contains it | 83 / 94 / 99 against 88 / 96 / 101 | not taken. The true row usually *does* hold more than the name — a surname resolved from a mark, a class of passage — so preferring the pure row demotes it |
| raising the score floor's neighbours: `MIN_SCORE` at 0.05 and 0.02 under rarity weighting | 121 and 111 with the crossing named, against 128 at 0.10 | 0.10 stands |
| `STRONG_NAME` at 0.6, 0.7 and 0.8 | no change to any of the eight numbers | the cut is not what orders these results |
| forgiving a **fixed** number of trigrams rather than a fraction of the query, so a one-word surname is forgiven as much as a full name | 6, 10 and 14 trigrams give 79 / 93, 82 / 95 and 87 / 92 in the top five and ten by name alone, against 86 / 95 for three quarters of the query | not taken; the proportional allowance is as good at five and better at ten |
| raising the floor for the forgiving scale, since it lets far more rows past 0.10 | 0.25 costs one name in each of the three cutoffs, 0.35 costs two or three, 0.45 collapses it | not taken — and unnecessary once only the rows that can be shown are built |
| widening the letter pass's bulk bound from 32 buckets to 64, which stops `P` sharing a bucket with `0` on pages full of digits | 3,888 cheap refusals against 3,960, and the same 22,896 real comparisons | not taken; it doubles the table to 25 MB to refuse 72 more rows |

### The 226 pages, read again: 828 names that were not there this morning

The retry pass finished. 157 records had unread pages; **30 of them gave up 828
names in 1,323 rows**, and 180 pages were read again and genuinely hold nothing
the engine can see. Those are now stamped as read-and-empty, so `status.py` no
longer lists them and no future run spends an hour on them again — which is the
point of the pass: a page that reads nothing must say so, or it is indexed
forever as a page nobody has looked at.

```
660 records for 660 dossiers, schema 18
   71,286 rows, 37,243 with a reading      (69,963 and 36,415 this morning)
   voyage: ship 201 (30%), year 162 (25%), port 168 (25%), line 388 (59%)
   surnames inherited: position 4,977, mark 474, indent 205
```

`scripts/reparse_voyages.py` and `scripts/build_names.py --min 2` were run
afterwards, as they must be: the name list stands at 1,081 names from 7,300
clean rows.

The corpus grew by 1,323 rows of distractors and the search held: 86 / 95 / 99
by name alone and 118 / 122 / 130 with the crossing named, at five, ten and
twenty. The engine benches did not move either — CER 0.362 over the 142
hand-read rows, and no golden page's geometry changed.

Where the two kinds of page now stand, over the same 142 names in the top ten:

| | typed alone | naming the crossing |
|---|---|---|
| the two typewritten pages, 42 names | **41** | 40 |
| the three cursive pages, 100 names | **54** (was 49) | 82 |

BS.ENT.015061 p6 — 46 Marias and Joses on a dossier that names no ship — goes
from 20 findable by name alone to 37 when the crossing is named.

### What the whole archive costs, at the end of the day

Twelve times the corpus on disk, which is 7,920 dossiers and 382,332 rows:

| | this morning | now |
|---|---|---|
| cold load | 96 s | **16 s** |
| the keystroke's own overhead | 258 ms | **62 ms** |
| `Contadore` | 105 ms | **7 ms** |
| `Manoel da Cruz Valdivia` | 365 ms | **46 ms** |
| `Maria Silva Gelria 1924` | 486 ms | **170 ms** |
| the index in memory | 295 MB | 307 MB |

Over the 660 dossiers actually on disk those three queries are 1, 3 and 12 ms.

### Twice today a heavy job was started twice

The second launch of the same command left six OCR workers on a fourteen-
gigabyte laptop and took the free memory to two gigabytes. `S=... && nohup cmd
> $S/log &` backgrounds the whole chain, so the `echo $! > $S/x.pid` that
follows fails while the job it was meant to record is already running — and the
error reads like a launch that did not happen. Check `ps` for the job before
starting it, not only afterwards. To measure anything while such a run is going,
`kill -STOP` its PIDs, measure, `kill -CONT`: under contention the scale bench
read twice as slow as the truth and would have condemned a change that was fine.

```sh
.venv-ocr/bin/python scripts/retry_unknown.py            # resumes; writes as it goes
.venv/bin/python scripts/status.py                       # says how many are left
```

### Next, in order — the reading, not the search

Allan read BS.ENT.013947 and BS.ENT.013942 in the app at the end of the day and
the verdict is that the **reading** is where the work goes now, not retrieval:
*"don't even dare think about downloading more until what we have has a decent
quality."* The plan is
[docs/superpowers/plans/2026-08-28-reading-quality.md](superpowers/plans/2026-08-28-reading-quality.md),
written against what is actually stored on disk. The four things it found that
were not in the report:

1. **The name is split the wrong way round on given-first pages**, and the
   repetition mark inherits the mistake down the family block: BS.ENT.013947
   files four people under *Benito* and four under *Pastre marco*, which are
   given names. `split_name` assumes surname-first. The order can be measured
   from the page — the token that repeats down a block is the surname.
2. **A person's correction freezes the whole document.** Six records are
   `source: manual`, and every row in them is held at the quality of the day it
   was first read. The pages Allan opens are the pages that never improve.
   Provenance has to be per row.
3. **Two values from an old pass are still on screen** — `SIRVIENTA` and
   `BELGA` in BS.ENT.013942 — kept alive by the same rule. Nothing writes those
   fields today.
4. **Nothing outside the name column is read at all.** The grid is measured and
   the UI has the cells; the recogniser is only ever given the name column.

The download question is answered for now: **no**. Not until the pages on disk
read decently.

## 2026-08-27 — the crossing, and the pages nobody was told about

Allan away for the day; the laptop worked through it. Everything below is
committed and pushed. **Start here.**

### What a searcher can now say, and what it is worth

Measured on the 142 hand-read names, each searched the way somebody who knows
the crossing would type it:

| | findable in the top ten |
|---|---|
| the name alone | 90 of 142 (63%) |
| naming the ship, as of yesterday | 110 (77%) |
| naming the **shipping line** where no ship is stated | 119 (84%) |
| plus **comparing letters inside the named crossing** | **125 (88%)** |

The hard page — BS.ENT.015061 p6, 46 Marias and Joses on a dossier that names
no ship — goes from 23 findable to 37.

* **The line is indexed and searchable.** Two thirds of the dossiers state the
  shipping line printed on the letterhead against a third that state a ship, so
  for most of the corpus it is the only crossing a person can name. It is taken
  out of the name query the way a ship is, it is worth the same bonus when it
  agrees, and typed on its own it lists everyone who sailed with that company —
  provided enough of the letterhead was named to make that the question.
* **A year can be a span.** `1924-1926` is what somebody types who knows the
  decade and not the date, however it is punctuated. A single year is now a
  span of one year, so nothing downstream has two things to reason about.
* **Letter by letter, inside the crossing.** Of the 23 names still unfound, 18
  score *below the search floor* against their own row: no ranking change can
  reach them. Trigrams survive a letter dropped or doubled and collapse when
  the recogniser substitutes systematically — `EMILI MUESSO` read as `bmike
  Meesoo` shares no trigram with what a person types and stands at 0.58 by edit
  distance; `Manoel da Cruz` read as `Manvil' Dar Cuy` is 0.69. Naming the
  crossing cuts the pool to a few hundred rows, and there the comparison is
  affordable, and a row keeps the better of the two measures rather than being
  scored twice — `Manvil' Dar Cuy` shares just enough trigrams with *Manoel da
  Cruz* to score 0.15, which used to put it in the results at rank forty with a
  0.69 reading of itself never looked at. Floor swept: 125 findable at 0.55,
  0.6 and 0.65, 119 at 0.7 where the pass stops adding anything.

### 301 pages the corpus had given up on, and nobody was told

A page whose geometry found no table is stored as `unknown` with nothing on it,
and the record around it keeps the current schema stamp — so every future index
run skips the document and reports success. 301 pages of the corpus were in that
state. They are not blank paper: today's engine reads 28 names off one of them
and 19 off another in the same dossier.

This is the third time this exact shape has appeared here — the empty manual
note, the errored page stored as current, and now the unmeasured page. It is
what `scripts/status.py` now counts, in the line that begins *"N pages in M
records read nothing"*, so the next one is visible without being looked for.

`scripts/retry_unknown.py` reads those pages again and merges what they give:
half an hour of machine time against the eleven hours a full re-read costs. The
choice is measured — a dossier with **no** unknown pages was re-read and gave
exactly what is already on disk (36 and 48 rows, unchanged), so the rest of the
corpus has nothing to gain from being read again.

### The retry run, and how to carry it on

```sh
.venv-ocr/bin/python scripts/retry_unknown.py            # resumes; writes as it goes
.venv/bin/python scripts/status.py                       # says how many pages are left
```

It is resumable in the only way that matters: a page it repairs leaves the list,
so starting it again picks up where it stopped. Each record is written the
moment its pages are read, so an interrupted run keeps everything it finished.

It is slower than it looks — about five minutes a record, three workers, because
these are by definition the pages the geometry finds hardest and most of them
end up rendered at 300 dpi and read twice. 283 pages were left when this was
written; that is most of a day of machine time, and nothing else depends on it.

### What finishing the corpus actually costs

| | |
|---|---|
| dossiers catalogued | 7,679 |
| downloaded so far | 660 (8.6%) |
| the whole archive on disk, at 2.6 MB a dossier | ~20 GB |
| downloading the rest, at the polite 1.5 s a dossier | ~3 hours |
| **indexing the rest, at a dossier a minute** | **~5 days of machine time** |

The download is not the constraint and never was. If the whole archive is the
goal, the number to attack is the minute a dossier costs to read — and today's
measurements say most of that minute is the geometry's second detection pass and
the recogniser reading each row twice, both of which are there for good reasons
that were measured. **Allan's call**: whether to download the rest unattended,
and whether five days of the laptop's evenings is a price worth paying for the
other 91% of the archive.

### Measured and rejected today

| | result | verdict |
|---|---|---|
| skipping the table search on pages after the first, using the columns carried forward | 20% faster, **a quarter of the names lost** on OL.PRJ.16326 — those pages do print their own headings, and the rules under the carried columns account for 14 rows of a page whose printing accounts for 164 | reverted; two tests now hold the order in place |
| comparing letters over the **whole** corpus when the trigrams find nothing | 91 findable of 142 against 90 at a floor of 0.65, and 66 at 0.55 — in isolation it recovers 29 of 52, but merged with the trigram hits it displaces more than it finds | reverted; the numbers are in the comment beside `EDIT_FLOOR` |
| keeping the loose second reading when it splits into a different number of words (1,241 rows of 30,540 carry one and lose it) | 121 findable against 122 with the crossing named, 90 against 90 without | left as it was |
| doing something to each crop before it is recognised — autocontrast, 2× upscale, unsharp mask, and **deslanting** the writing, which every classical handwriting pipeline does and this one does not | CER 0.362 as it stands, against 0.361, 0.358, 0.360 and 0.366; findable 115 against 115, 117, 115, 117 | none of them moved it; `scripts/spike_prep.py` keeps the measurement |

The last of those is the one worth writing down twice, because it looked like the
obvious missing step: the recogniser was trained on print and this hand leans.
Correcting the lean changes nothing measurable. The *union* of all five readings
finds 122 of 142 against 117 for the best single one — five people — at five
times the recogniser's time per page, which would take the corpus refresh from
eleven hours to a day and a half. Not taken, and now measured rather than
assumed.

### Search got four times faster, and the same answers

A query over 300,000 rows spent half a second calling `trigrams` a hundred
thousand times — once per candidate reading, on every keystroke — rebuilding
what the posting list already knew. A posting is now a *reading* rather than a
row, with the number of trigrams in it beside it, so the overlap counted off
the postings **is** the score: shared over the union. Nothing is rebuilt.

| | before | now |
|---|---|---|
| `Contadore`, 30,000 rows | 80 ms | 25 ms |
| the worst query measured, 30,000 rows | 266 ms | 67 ms |
| `Contadore`, 306,000 rows | 750 ms | 135 ms |

Same hits and same scores: 33 real queries compared against the scanning path,
zero differences. The rows are indexed by ship, line and year as well, so the
letter pass takes its pool instead of walking the corpus for it — a wash on a
ship, a fifth off a year, and at a million rows the difference between a set
lookup and a million of them.

The first of those was next on yesterday's list. The saving it was after was
already in the code: a page that finds no table of its own falls back to the
carried columns *before* it pays for the 2000 px detection.

### Search got twice as fast again, by measuring before optimising

The letter-by-letter pass folds every row it compares, and was folding them
again on every keystroke, so the postings now keep each reading folded once at
build time. On its own that changed almost nothing — 570 ms to 516 ms — which
was the useful result: a profile of the slow query put **half its time in
`ship_similarity`**, not in the pass being tuned. The voyage bonus asks how
close each row's ship is to what was typed, once per row, against a query
holding two or three terms and an archive naming a hundred-odd ships. It is a
pure function of two strings, so it is now asked once per distinct pair.

With the ship comparison out of the way the folded cache is worth what it
looked like it should be: 391 ms to 283 ms, a quarter off.

| minimum of 15, 310,680 rows | committed | now |
|---|---|---|
| `Maria Silva Gelria 1924` — letter pass and a year | 570 ms | 283 ms |
| `Manoel da Cruz Valdivia` — letter pass, ship named | 328 ms | 155 ms |
| `Contadore` — trigrams only, no ship to compare | 83 ms | 66 ms |

Over the 31,000 rows actually indexed today those are 80 → 28 ms, 49 → 14 ms
and 16 → 6 ms. The folded readings cost 5 MB there and 50 MB at ten times the
size. Same hits and same scores throughout: the letter pass is pinned to what
folding on the spot returned, including for the readings the trigram loop skips
because they hold nothing to index.

The lesson is the cheap one and it was nearly missed: the pass that *looks*
expensive is not always the one that is. The first fix was written, measured at
4%, and would have been committed as a win.

### Next, in order

1. **Handwriting recognition, still the ceiling, and now every cheap lever has
   been pulled twice.** 18 of the 23 remaining misses are unreachable by any
   matcher: the row does not resemble the name. Input width, a bigger model,
   removing the printed rules, a pretrained handwriting model, folding
   confusable letters, and now contrast, resolution and the lean of the writing
   have each been measured. What is left is a model trained on this archive's
   own hand — which means hand-read rows, of which there are 142 — or a GPU.
2. **The letter pass wants an index at scale.** It filters by a set lookup and
   two cheap ratios, which is 20 ms of a query at 30,000 rows and a scan of
   every row at a million. An index by ship, line and year is what it wants.
3. **`data/transcriptions/` will outgrow memory** — unchanged from yesterday.
   Search loads every row; at 7,000 dossiers that is roughly a million.
4. **Rebuild `data/names.json` after each refresh** (`--min 2`); it was rebuilt
   this morning and stands at 1,033 names.

## 2026-08-22 — checkpoint, machine idle

Everything is committed and pushed, nothing is running, and the laptop is quiet.
**Start here when picking this up.**

### Where the corpus is

```
660 records for 660 dossiers, schema 18
   69,257 rows, 35,957 with a reading
   22 were read by an older engine — an index run redoes them
   1 carries a page the engine failed on — it will be read again
   voyage: ship 217 (33%), year 167 (25%), port 177 (27%), origin 247 (37%), line 407 (62%)
   surnames inherited: position 4,585, mark 448, indent 189
```

`.venv/bin/python scripts/status.py` prints that, and says whether a run is going.

The evening's index run was stopped at **235 of 660** by hand — the machine was
loud and the night was not for it. Nothing was lost: it resumes from the
content-hash cache and skips what is current. The re-parse and the name-list
rebuild were run afterwards, so the ship coverage above (33%, up from 25%) and
the 1,026-name dictionary are already in what is on disk.

### To resume

```sh
.venv-ocr/bin/python scripts/serve.py --root data/scans     # then, in another shell
curl -X POST 'http://127.0.0.1:8799/api/index?dir='         # start / resume
curl      'http://127.0.0.1:8799/api/index'                 # progress
curl -X POST 'http://127.0.0.1:8799/api/index/stop'         # stop; workers finish the page
```

It will read the 22 dossiers marked for re-reading and the ~400 that were never
reached, at roughly a dossier a minute, four workers, and it leaves the machine
usable but audible. Afterwards: `scripts/reparse_voyages.py`, then
`scripts/build_names.py --min 2`.

### Next, in order

1. **Finish the refresh** — about seven hours of machine time, in whatever
   stretches suit. Nothing else depends on it; the app works on what is there.
2. **A common name in a large pool is the open problem.** BS.ENT.015061 p6 reads
   at CER 0.08 in places and 18 of its 46 names are findable, because they are
   Marias and Joses. Three scoring changes were tried and all three lost names;
   the crossing is the lever that works, and it is now weighted as far as it can
   go without deciding. What is left to try: narrowing by *shipping line* (62% of
   dossiers state one, against 33% for the ship), and letting a searcher say a
   year *range* rather than a year.
3. **A dossier's later pages could skip the heading pass** when the columns are
   already known from an earlier page — a recogniser batch per page, which is
   most of what the geometry costs now.
4. **The name list should be rebuilt after every refresh**; it is only as good as
   the pages it was counted from, and 1,026 names came from a corpus that is
   still two thirds old.
5. **Handwriting recognition is the ceiling** — five things were measured against
   it tonight and none moved it. What is left is a model that reads cursive
   Portuguese and Spanish on a CPU, or a GPU, or training data of this
   archive's own.

### What not to redo

* The corpus is not a test set. Nothing is trained; a re-index refreshes what the
  app serves and proves nothing about a change. Use `pytest`,
  `scripts/bench_search.py`, `scripts/bench_pages.py`, `scripts/bench_rec.py` —
  between them about two minutes.
* Measured and rejected tonight, with numbers in the entries below: recogniser
  input at 960 and 1280 px, `PP-OCRv5_server_rec`, removing the printed rules
  from each crop, word-by-word query matching, folding OCR-confusable letters,
  splitting a joined name at its interior capital, and a wider ditto gap.

## 2026-08-21 — evening (Allan present, working to 23:00)

### The corpus is not a test set

Allan asked why a change had to be checked by re-reading seven thousand pages,
and the answer is that it did not. **Nothing here is trained.** The recogniser's
weights are fixed; no amount of scanned paper moves them. A full re-index
refreshes what the app serves and proves nothing about a change — and I started
one three times today, each time to pick up a change, each restart throwing away
the work before it.

What a change is checked against now, in the order it runs:

| | what it answers | cost |
|---|---|---|
| `pytest` | 422 unit and pipeline tests | 30 s |
| `scripts/bench_search.py` | can these people be found by name? | 10 s |
| `scripts/bench_pages.py` | is the table measured right, across the printings? | 1 min |
| `scripts/bench_rec.py` | how well are the names read? | 1 min |
| `scripts/smoke_prototype.py` | does the page still work in two browsers? | 2 min |

`data/golden.json` names ten pages and why each is in the set: a typed list, a
dense cursive family list with dittos, a continuation page that prints no
headings, one passenger on a full ruled sheet, a page whose ordinals the scan
lost, faint pencil, a busy letterhead, a letterhead in two columns. A ten-second
bench caught a scoring change that cost seven findable names — the hours would
have said the same thing at ten thousand times the price.

### What the benches settled tonight

**Findable names went from 39 of 68 to 51 of 68**, measured by searching each
hand-read name exactly as a person would type it.

Every one of those came from the repetition mark. These lists are written by
family — the surname once, a ditto under it for each relative — and BS.ENT.013947
p3 lists forty-eight people under nine surnames. The mark rarely survives the
recogniser as its own token: it comes back glued to the name (`"Joze`,
`,Friancisca`), or not at all. So the mark is now matched wherever it is, a row
read as a single word no longer sets the family surname, and a lone given name
under a family inherits it. Each inheritance records **how** it was arrived at —
`mark`, `indent`, `position` — because a mark on the page and an inference from
position are different claims: the review UI dots an inferred surname in the
warning colour and says so on hover, and the CSV carries a `sobrenome_origem`
column. The reading itself is never touched.

Resolution runs at index time as well as at reading time, so improving the rule
reaches the whole corpus in a second rather than in hours.

### Four things that did not work, measured and dropped

Worth writing down, because each looked obviously right:

| | result | verdict |
|---|---|---|
| recogniser input 960 px and 1280 px wide | CER 0.515, 0.581 against **0.458** | 640 px stays |
| `PP-OCRv5_server_rec`, a bigger model | CER 0.516, 41/68 findable against 52 | current model stays |
| removing the printed rules from each crop | CER 0.461 against 0.458 | kept behind `DESEMBARQUE_DERULE=1` |
| matching word by word instead of whole-string | findable 44/68 against 51 | reverted |
| folding OCR-confusable letters together | 51/68, unchanged, and it broke the pool's guarantees | reverted |

Handwriting recognition is at its ceiling for what runs on this machine. That is
now a measured statement rather than an impression.

### The two pages the golden set carried as unsolved

Both are solved, and they failed differently. On BS.ENT.016574 three letterhead
lines sat above the table and took every candidate slot, so the heading was never
read — a heading is a row of short cells and a letterhead line is a sentence, so
candidate lines are now required to be made of short cells. On OL.PRJ.17851 the
writing is too faint for the detector to see at all — thirty boxes on a page of
twenty-three names — while the recogniser reads those names perfectly once a band
is cut for it; there the rules still supply the rows and the printing keeps the
column, recorded as `measured_by: printed columns, ruled rows`.

**Ten of ten golden pages now measure from the printing.**

### Also

An empty ruled row is no longer sent to the recogniser. A list is printed with
thirty rows and often carries three, and now that the bands cover the whole list
rather than a third of it, reading the blanks was most of the corpus's time.

### Names the archive knows, offered as guesses (Allan's suggestion)

Since recognition is at its ceiling, the remaining help for somebody reading
`Dantalarlraia Saliador` is a list of names these ships are known to have
carried. Built from the archive itself — `scripts/build_names.py` counts the
pages the clerks *typed*, which the recogniser reads at CER 0.01, and every row a
person has typed by hand: **793 names from 5,514 clean rows** as of the last
rebuild, with the form's
printed vocabulary and the trades filtered out by the machinery that already
knows them. A general name dictionary would be somebody else's idea of which
names exist; these ships carried Italians, Spaniards, Portuguese and Syrians to
Santos between 1917 and 1925.

The line this must not cross is the one the whole tool rests on, so:

* a guess is never a value — it ranks what the engine read and may be offered
  beside it, and it is stored only when a person picks it, as that person's
  typing;
* the word menu keeps `outras leituras do motor` first; guesses appear under
  `palpites do acervo — não lidos da página`, in the warning colour, each with
  how close it is and how often the archive saw it;
* they are off until asked for (`≈ Prováveis`), and only then does `↑ primeiro`
  appear to put them above the readings;
* `/api/names` says in its own response that these are not readings.

The first thing it offered for `Saliador` was `TRABALHADOR`, which is a
profession that reached the name column on pages read before the column was
measured from its printing. Trades are filtered now, and **the list wants
rebuilding after the corpus refresh** — the builder says so in its own output.

`? Duvidosas` is the other half: the rows where nothing in the reading resembles
a name this archive carries, marked so a person checking four hundred rows knows
where to start. It says on hover — and in the endpoint's own answer — that a rare
name is unknown here and perfectly correct.

### How much of the corpus is inference, and how often it is right

The position rule fills in a surname for a row that carries none, and it is 41%
of the rows read tonight: **674 read, 521 by position, 65 off a mark, 10 off an
indent.** That is a large share of a record used as evidence, so it was measured
rather than assumed.

On the hand-read page, of forty inherited rows **thirty-six attach to the family
the page actually says**. The four that do not are one block: `Castiello Cosme`
came back as `CastiettoCoome`, the recogniser having lost the space, so no new
family started and four Castiellos were filed under Lorenzo. The failure mode is
therefore bounded and legible — a missed family head cascades to its members —
and every inherited surname says in the record and on screen that it was
inherited.

Splitting a joined word at its interior capital was tried, since that is exactly
where the lost space is. It costs two findable names of sixty-eight, measured
against the same index both ways, and was reverted: the mangled first half
becomes a family head and the rows below it inherit something worse than what
they had.

#### A second cursive page, and what it says

`data/truth/` now holds five hand-read pages, 142 names. Measured by searching
each name as a person would type it:

| page | | |
|---|---|---|
| BS.ENT.013981 p2 | typed | **28/28** |
| BS.ENT.013983 p2 | typed | **14/14** |
| BS.ENT.013947 p3 | cursive, Italian-Spanish | 32/48 |
| BS.ENT.014541 p2 | cursive | 4/6 |
| BS.ENT.015061 p6 | cursive, Portuguese | **14/46** |

The last page is the one to look at. Its readings are *good* — `Antonio Augusto
Fonseca` comes back as `Antonio Ougus-to Fonseca`, CER 0.08 — and two thirds of
them still cannot be found. The names are `Maria`, `Jose`, `Joaquim`, `Manoel`:
a search for `Maria Rosa Carrana` competes with every Maria in twenty-two
thousand rows, all equally close. The other cursive page carries `Santabarbara`,
`Arquentiri`, `Calzagari` — rare, and therefore easy.

Weighting each word of the query by how rare it is in the index — so `Carrana`
carries the match and `Maria` does not — was the obvious answer and it is worse:
**81 of 142 against 92**, and both cursive pages fell. It is the third scoring
change tonight to lose names, after word-by-word matching and folding confusable
letters, and the reason is the same each time: any scheme that lets one word
carry a match floods the top ten with rows that share that word and nothing else.

Common names in a large pool are the open problem, and the tool's own answer to
it is already built — the ship and the year. `Maria Rosa Carrana` is hopeless;
`Maria Rosa Carrana 1922` should not be, and whether it is now is the first thing
to measure next.

#### The blank-row skip, checked against the hand-read pages

Skipping a row with no ink is a performance change that could quietly lose a
faint name, so it was checked rather than assumed: of 142 hand-read names, **three
have no reading at all**, and all three are rows the clerk struck through on
BS.ENT.015061 — Jacintha, Olivia, Albertina, cancelled passengers with a line
drawn across them. On that page the ink test judges **none** of the forty-six
bands blank, so the skip did not drop them; the recogniser returns nothing for a
name with a line through it, which is a different problem and a small one.

#### Which rows are worth a person's time, measured

The first version of this flagged a reading that resembles no name in the
archive. Measured against the five hand-read pages — 139 rows with a reading, 67
of them badly read — that catches **4%** of the bad ones. Three signals were
compared instead:

| signal | rows flagged | of those, badly read | of all badly read, caught |
|---|---|---|---|
| resembles no name here | 3 | 100% | 4% |
| surname inferred from position | 33 | **94%** | 46% |
| recogniser's score below 0.85 | 76 | 71% | **81%** |
| score below 0.7 | 18 | 89% | 24% |

So `? Conferir` marks a row for any of the three and says on hover which it was:
the motor decoded it weakly, the surname was inferred rather than read, or
nothing in it resembles a name this archive carries. About half the rows on a
cursive page are marked, which is honest — about half of them are badly read.

#### What the guesses are actually worth

Measured against the ninety-six hand-read names, with the list as it stands
tonight (760 names at the time of the measurement, built from a corpus that is
still being re-read):

| | |
|---|---|
| rows where the archive list contains any word of the true name | 71 of 96 |
| rows where the right name is among the four offered | 23 |
| rows offered only wrong names | 67 |

So it helps on about a quarter of rows and shows plausible-but-wrong names on two
thirds. That is the argument for every constraint on it — off by default, in its
own section, in the warning colour, and never a stored value. Lowering the
threshold to 0.5 buys four more rows with the same amount of noise, which is not
enough to justify moving it.

The list is the limit rather than the matching: on a quarter of rows the archive
simply does not contain the name. It should get better as the refresh replaces
records read before the name column was measured properly — **rebuild it and
measure again then**.

### A dossier that silently emptied itself

BS.ENT.013942 came back from the run with **no rows at all**, an hour after it
had read `Ponticelli Giovanni`. Its page carries the oneDNN failure this machine
has thrown since July — `ConvertPirAttribute2RuntimeAttribute not support`. The
page pipeline has retried without oneDNN since then; the recogniser never did,
and the recogniser is what the new heading pass calls first.

The worse half: the record was stored at the current schema with no rows, so
every future run would have skipped it. That is the second time this shape of bug
has appeared here — the first was an empty manual note marking a document as done
forever — and it is the failure this tool exists to prevent. `is_indexed` now
refuses a record whose pages carry an engine error.

### Next, in order

1. **Rebuild `data/names.json` after the refresh.** The list is only as good as
   the pages it was counted from, and those are being re-read now.
2. **A dossier's later pages could skip the heading pass entirely** when the
   columns are already known from an earlier page — a recogniser batch per page,
   which is most of what the geometry now costs.
3. Handwriting recognition is the ceiling, and every cheap lever has been pulled.
   What is left is a model that can read cursive Portuguese and Spanish on a CPU,
   or a GPU.
4. The corpus refresh is running at about a dossier a minute; 660 of them is
   roughly ten hours, unattended, resumable.

#### The four dossiers Allan opened, at the end of the evening

Searched live, against the index as it stands:

| typed | result |
|---|---|
| `Oswaldo de Mello Mattos` | **rank 1**, score 1.0 — BS.ENT.013983 p2 line 1 |
| `Enzo Santoni` | **rank 1** — BS.ENT.013981 p2 line 1, read `Enzo SantoniBra` |
| `Ponticelli Giovanni` | not in the top three |
| `Ponticelli Giovanni Indiana` | **rank 1** — BS.ENT.013942 p2 line 1, read `Pouticelli Sooai` |
| `Santabarbara Salvador` | not in the top three |
| `Santabarbara Salvador Jaronna` | **rank 1** — BS.ENT.013947 p3 line 1, read `Dantalarlraia Saliador` |

Which is the whole of where this stands in six lines. A typed page is solved. A
cursive name on its own is still lost among twenty-five thousand rows. A cursive
name with the ship beside it comes back first, mangled beyond recognition and
pointing at the right line of the right page — which is what the tool is for.

### Voyage parsing: the evening's largest gain, and none of it re-reads a page

Naming the crossing is what rescues a common name, so the fields that carry it
are worth more than they cost. Measured by re-parsing what is already on disk —
seconds, no page images:

| | |
|---|---|
| dossiers that gain a ship | **58** |
| dossiers that lose one | 1 (a German printed sentence) |
| ships corrected | 12 |
| dossiers that gain a year | 5 |

What was wrong, in the order it was found:

* **The ship written on its own line in an open quote.** BS.ENT.013983 is
  typewritten, legible, and stated no ship: its label reads `passageios no
  Pague......` and the vessel sits below it as `"Itabera`, the closing quote lost
  to the scan.
* **The nationality glued to the vessel.** `na vapor español Valbanera` is one
  line; taken whole it is refused for carrying a nationality, and the ship went
  with it. Same for the footnote marker these forms print above the blank —
  `(2) Duca degli Abruzzi` — and for the brackets when the scan loses their
  number.
* **A printed sentence as a vessel.** `Yerzeichnis der Perfonen, kefördert durch
  den deutschen Dampfer` was a ship. A real one here is under thirty characters.
* **The date the detector broke.** `Santos,deMaio` is a port, a comma and a
  month with no space; read whole it contains no month at all. And `de 19.18` is
  a year with a stop inside it.
* **A bound that was exactly wrong.** Allowing a separator inside the year first
  made `de 19.40` into 1940 — on a page whose own stamp reads `ABR 8 1920` —
  because the upper bound was 1940. Every year this corpus has produced falls
  between 1913 and 1928, so the bound is 1935.

What it comes to, across all 660 dossiers, once the re-parse runs:

| field | now | after |
|---|---|---|
| names a ship | 163 (24.7%) | **220 (33.3%)** |
| gives a year | 163 (24.7%) | 168 (25.5%) |
| gives a port it sailed from | 250 (37.9%) | 249, forty-three of them cleaned |
| names a shipping line | 411 (62.3%) | 409 |

A dossier is searchable by ship regardless — the archive's own catalogue names
every one of them, and search joins it — so what this adds is the page's own
claim beside the catalogue's, which is what a person checks a mangled reading
against.

None of this is in the running refresh: the server was started before these
changes. **When the run finishes, `scripts/reparse_voyages.py` applies all of it
in a second** — and it now refuses to run while an index job is writing the same
records, which tonight was managed by hand.

### Where it all stands at the end of the evening

| measurement | |
|---|---|
| tests | 458 |
| golden pages measured from the printing | 10 of 10 |
| reading, 5 hand-read pages, 142 names | CER 0.362 |
| findable by name | 92 of 142 |
| findable when the crossing is named too | **111 of 142** |
| typed pages | 42 of 42 |
| cursive pages | 50 of 100 |

The refresh is running and unattended: a little over a hundred of 660 dossiers
current at 21:40, about a dossier a minute, resumable, no failures.

One thing the evening measured by accident, because the index grew under the
bench: **findable names fell from 92 to 90 of 142 as the pool went from 22,485
rows to 25,246.** That is the erosion this file predicted in July, happening in
real time — and the archive is eleven times larger than what is indexed now. It
is the strongest argument for the crossing as a search key, which is why the
voyage parsing was worth the evening.

#### To pick up tomorrow

1. **When the refresh finishes**: `scripts/reparse_voyages.py`, then
   `scripts/build_names.py --min 2` — the name list is only as good as the pages
   it was counted from, and those are being re-read now.
2. **A common name in a large pool is the open problem**, not recognition:
   BS.ENT.015061 p6 reads at CER 0.08 in places and 14 of its 46 names are
   findable, because they are Marias and Joses. Three scoring changes were tried
   tonight and all three lost names. The lever that does work is the crossing.
3. **The voyage now counts for more.** Weighted at 0.6 rather than 0.25 and
   matched against a strict ship floor of 0.85 rather than a forgiving 0.75, a
   searcher who names the ship or the year finds **111 of 142** rather than 96.
   Both were pushed until they broke: at a voyage weight of 0.7 a weak name on
   the named ship outranks a good name elsewhere, and at a ship floor of 0.6 the
   wrong ships match and lift everybody aboard them. The penalty for contradicting the query is now
   its own, much smaller constant: sharing one meant that rewarding a right year
   punished a wrong one just as hard, and a person misremembering a date is not
   someone to hide a record from.
4. **A dossier's later pages could skip the heading pass** when the columns are
   already known — a recogniser batch per page.
5. Handwriting recognition is the ceiling and every cheap lever has been pulled.

### The refresh

Started once, at 19:41, on schema 18, and left alone: 660 dossiers, four workers,
resumable from the content-hash cache. Everything above is in it. Where it stops,
`curl 'http://127.0.0.1:8799/api/index'` says, and starting it again picks up
where it left off.

## 2026-08-21 — afternoon (branch `rows-from-writing`, merged)

Allan opened four dossiers and most of what came back was gibberish. He was
right, and the cause was not the recogniser.

**Every measurement on these pages came from rules the scan has often lost.**
The name column was the widest gap between the vertical rules that happened to
be detected: on BS.ENT.013947 p3 that is the *Procedencia* column, so the engine
read a column of ditto marks and filed it as names; on BS.ENT.013983 p2 it is two
thirds of the sheet. The horizontal rules are dotted, and the comb fitted to them
locked onto the empty ruled area *below* the typed list on 013983 — fourteen
perfectly legible names, none of them read — while on 013942 it sat half a row
out of phase and two rows late, so band 1 covered printed row 3 and every crop
carried the descenders of one row and the ascenders of the next.

`desembarque/tablegrid.py` measures the table from what is **printed** on it: the
column headings, and the ordinal printed on every ruled row whether anybody wrote
on it or not. Detection alone answers it — 3 s a page against the 55–80 s the
page costs to read — and only the heading line is recognised, to know which
column is which. The rules stay as the fallback for a page that prints no
heading.

| page | before | after |
|---|---|---|
| 013983 p2, typed | 26 rows, none of the 14 names | **14/14 verbatim** |
| 013947 p3, cursive | 33 rows of the Procedencia column | 49 rows, names, 15 s |
| 013942 p2, cursive | bands 2 rows late, the one name missed | the name, on row 1 |
| 015061 p6, cursive | 50 rows | 46 rows, names |

Surveyed over 40 random indexed pages: **32 measured from the printing**, mean
9.2 s a page; the other 8 fall back to the rules exactly as before. Three bugs
found in that survey and fixed with tests: the detector reports its boxes in its
own order and the pitch was measured over it; the heading row was picked as the
busiest line rather than the topmost full-width one, so a busy letterhead crowded
it out; and five stray ordinals outvoted forty-six written lines, giving sixteen
bands three rows tall.

**The corpus on disk does not have any of this yet.** Schema is at **16** and
every stored record is stale by design: this needs the page images again, so it
is a re-index, not a re-parse — the run described at the top of this file, about
four hours unattended.

### What is left, and it is one thing

The crop for 013942 row 1 now holds `Ponticelli Giovanni` whole and clean, and
the recogniser says `Pouticelli Sooai`. Geometry is no longer the limit;
**handwriting recognition is**, as this file has said since the first week, and
now nothing else is in the way of measuring it. `scripts/bench_rec.py` scores a
recogniser against the hand-read pages in `data/truth` — CER and, more to the
point, whether the reading is still *findable* by search — and two truth pages
were added for it: 013983 p2 (typed, the control) and 013947 p3 (48 cursive
names, read by eye and uncertain, for ranking variants against each other).
Nothing has been swept yet: the next session runs the input-width and model
sweep against that bench.

Also: the search scope control on the header is now a menu the page owns —
visible against the panel, an arrow at text size, and it closes on the same
click, on a click away, and on Escape.

## 2026-08-21 — night session (Allan away)

Nine commits, all pushed. The two things last night's checkpoint named as next
are done, and the corpus on disk carries both. **380 Python tests, 67/67 browser
assertions from disk and 77/77 served, in Chromium and Firefox** — including
`the scan band follows the hit`, which is the assertion the missing geometry had
been failing.

### The bands are back on every page, and nothing had to be read again

`transcribe_document()` now keeps `res.geometry` on the page it was measured
from, and `scripts/backfill_geometry.py` put it back on everything already
indexed, out of the page images still in `data/pagecache`.

| | |
|---|---|
| records that wanted geometry | 634 |
| pages measured | 2,446 |
| refused as disagreeing with the rows | **0** |
| time, three workers | 28 min (08:31–08:59) |
| records now carrying page geometry | 634 of 660 |

The remaining 26 are the two hand-measured records, which keep a
document-level measurement, and 24 dossiers the engine found no rows in.

The measurement is deterministic: on every page sampled before the run, the
recomputed band count equalled the number of rows stored against it exactly —
16 rows, 16 bands; 46 and 46. That is what makes the repair safe, and it is
checked per page rather than assumed: row `n` **is** its band's index, so a
band list shorter than the rows on disk would draw every row after the first
difference against somebody else's line. Such a page is refused and reported.
None occurred.

The bands were then unusable for a second reason. The corpus payload carries
one geometry per *document* and a dossier is read page by page, so a hit on
page 7 was painted from whatever single measurement the record happened to
hold. All the bands together are 3.5 MB and cannot ride along with the folder
list, so `/api/geometry?hash=` hands over one dossier's when it is opened and
the page strip picks the page's own. The file:// build has no API and keeps
what it was built with.

### A year now says where it was read, and the writing outranks the stamp

`year_source` is `printed` or `stamp`, and where a dossier's two forms disagree
the year the clerk wrote wins, whichever page was read first. Two stamps
disagreeing is the same claim twice and the first still stands.

Across the corpus: **96 years printed, 67 stamped.** All four 1928s — the
misreadings of 1923 that started this — are stamped, and now say so in the
record, in the document header (`1928 (carimbo)`) and in the hit list.

### One in eight shipping lines was the sheet talking about itself

`No. 461B` twelve times, `Repartição da Policia` five,
`BR.AN.RiO.O2.O.RPV.PRJ.1GGS.8` ten. The whole-string refusal that caught
`POLICIA DO PORTO` missed every way the recogniser breaks it, and the run of
digits that caught the archive's notation is not there once its zeros come back
as letters. Refused now a word at a time and fuzzily, the way a ship is; a
refused line no longer ends the search, because the company is often printed on
the line below it.

| of 660 records | before | after |
|---|---|---|
| naming a shipping line | 418 | 408 |
| lines that changed | — | **111** |
| junk among the commonest | `No. 461B` (12), `Repartição da Policia` (5) | none in the top twenty |

Coverage falls slightly and that is the right direction: the ten sheets that
lost a line had nothing on them but the form's own printing, and a hundred and
eleven now name the company that actually sailed.

`No. 461B` → `The Koyal Mail Steam Packet Company`; `Mod. bordo N. 133` →
`LLOYD SABAUDO`; `POLICIA MARITIMA DO PORTO` → `Nippon Yusen Kaisha`.

The same run showed the mirror of it: **the company was being filed as the
ship.** `The Koyal Mail Steam Packet Company` was a vessel in four dossiers and
their line in thirty-two — where the clerk left the vessel blank, the
letterhead above stands nearest to the label, and a ship read off a passenger
list was never compared against the line printed on the same sheet. Seven
dossiers lose a ship they never had.

The regression list is what keeps these filters honest: sixteen companies read
off real pages in the same run, `COMPANHIA NACIONAL DE NAVEGAÇÃO COSTEIRA`
among them, which must keep their names while `Repartição da Policia` loses
one. `HUGO STINNES LINIEN` is why the port names are matched whole rather than
by word — `STINNES` is within a hair of `santos`.

### Search: what actually runs out first is not memory

The progress log had assumed `data/transcriptions` wants SQLite before the full
archive. Measured, that is not the wall:

| | 660 dossiers | extrapolated to 7,679 |
|---|---|---|
| rows indexed | 19,308 | ~225,000 |
| index in memory | 22 MB | ~260 MB |
| cold load | 3.8 s | ~45 s |
| **per keystroke** | **~100 ms** | **~1.2 s** |

It is the per-keystroke scan that does not survive, and it does not need a
database. A row can only score above zero if it shares a trigram with the
query, and the floor is 0.10, so scoring only those rows returns *exactly* the
same hits with the same scores. A trigram posting list of row numbers now does
that: **~100 ms → ~20 ms**, the pool scored down from 19,373 rows to about
2,000, built in 0.13 s for 4 MB and kept across requests — `/api/search` loads
the index on every request, which is what makes a correction searchable the
moment it is typed.

Also out of the index: sixty-five rows that are not passengers. The tally at
the foot of the list (`Total 10412190`, `EM Tranzito em 1a 28 em 3a 9 total
37`) and the interpreter's prose where the row comb reached it. Three things
were letting them through — the tally's own words were not on the list of the
form's printing, the detector runs a word into its punctuation and into the
next (`registro,`, `com/8pessoas`), and digits are not evidence about a name.

### The green dot said the engine was right

`Brges. iuig` scored 0.86 and showed a green dot labelled *alta confiança*. The
number is Paddle's decode score: how firmly it committed to the characters it
emitted, which stays high on confident nonsense. It now says what it is —
`score do motor`, the name the CSV export already used instead of `precisão` —
and a high score is painted neutral. Green is kept for the one thing that earns
it: a value a person read off the scan and typed. The low end is unchanged,
because the asymmetry is real — a low score does mean the recogniser struggled.

Calibrating it properly still needs hand-read truth, and `data/truth` holds one
page.

### The browser suite had a way of reporting nothing as a pass

Two bugs of exactly the shape the stale-build refusal was written for. Firefox
waited a flat four seconds before reading the result, which is enough for the
file:// build and not for a served corpus of 660 dossiers; it polls now. And a
browser that ran and reported *nothing* printed `not available, skipped` —
identical to one that is not installed — so a served run said ALL PASS with
Firefox silently dropped. Absent is a skip; silence is a failure.

### Next, in order

1. **The corpus is a sample.** 660 dossiers of the 7,679 the catalogue lists.
   Nothing here is tuned to 660, and the search index was measured against the
   full number rather than the current one.
2. **Confidence is still uncalibrated**, and now honestly labelled instead. One
   hand-read page is not enough to calibrate against; a few dozen would be.
3. **The ship is still the weak field** — 26% of dossiers name one, and about
   one in eight of those is a stamp or letterhead (`RII IEVEL`, `vaporRANIA`).
   The archive's catalogue covers the ship for search regardless.
4. The candidate pool could be narrower still: it is padded trigrams that keep
   ~2,000 rows in it, and dropping the padding would change results on rows
   read as a single letter — a behaviour change, not an optimisation, so it was
   left alone.
5. `reparse_voyages.py` after any change to the way the forms are read; the
   schema is at **15** and every record on disk is current.

### Open, and Allan's to answer

* The full download is ~7,679 dossiers, and the measured cost is 65 s each —
  about five and a half days unattended on this laptop. That number decides
  whether the fast forms-only first pass gets built before the download, and it
  is unchanged by tonight's work: the geometry backfill is cheap only because
  the pages had already been read once.
* Whether a stamped year should be *searchable* at all, or only shown. It is
  searchable today and marked everywhere it appears.

## 2026-08-20 — day session (Allan working)

### The browser test had been green against a two-day-old page  (30e1726)

`make_prototype.py` imports the package from inside its functions and the
repository root was never on `sys.path`, so the build died with a
`ModuleNotFoundError` the moment it reached a PDF — after argument parsing, in
the middle of real work. The previous `prototype/build/index.html` stayed where
it was, and the smoke run went on driving it: **35 assertions, all green,
against a page older than the code**. Behind it were nine genuine failures.

Fixed in two places, because they are two problems. Scripts that import the
package now put the root on the path. And the smoke test refuses to run when the
build is older than `review.html` — a stale artifact has to be an error, since
everything downstream believes it.

The assertions that need the API are now gated on the page being served: from
disk there is nothing to answer them, and counting them as failures buried the
ones that meant something. **44/44 from disk, 56/56 served, in Chromium and
Firefox.**

### A document can leave the tool as a spreadsheet  (3b4daa6)

`/api/export` returns one dossier's rows as CSV, offered as a download named for
its notation. Every row carries the notation, the page and line, the verbatim
reading beside the split into surname and given name, and **who produced it** —
a person or which engine. The recogniser's number is exported as `score_motor`,
not `precisao`: it is a decode score that stays high on confident nonsense.
Blank rows are kept, because a blank line on these forms is a fact about the
page and dropping it renumbers everyone below it.

Editing is now a mode rather than the default. Every cell was editable at all
times, including fields the engine never attempted, so the page invited typing
into places that had not been read. On a record meant as evidence, a stray
keystroke is worse than one more click.

### The tables whose rules print too faintly to be measured  (f0eed9f)

`BR_..._16456` page 2 is a clean list of **thirty-seven passengers** and geometry
returned nothing at all. The table's vertical extent is taken from its rules, and
on this sheet they printed so faintly that the longest unbroken run of ink at
each one is the blank paper below the last passenger. The extent came out as the
bottom six per cent of the page; no comb fits inside that; the run reported
success.

The comb fitted to the *writing* was already computed as a challenger, but it
could only win by overlapping the extent the rules reported — and that extent is
exactly what is wrong here. When there is no first comb at all there is nothing
to protect and the veto comes from the same broken measurement, so the challenger
is now judged on its own: it must start on the page, cover at least eight rows,
and account for at least half the writing detected. A comb explaining a third of
the writing is a letterhead as often as it is a list.

| | before | after |
|---|---|---|
| pages with no row at all | 15 of 89 | 10 of 89 |
| mean coverage | 0.457 | 0.497 |
| regressions | — | **0** |

The five recovered pages went from zero coverage to 0.50–0.79. The choice
between the two combs is now `choose_comb`, a function tested on the numbers real
pages produce, which is how its thresholds were set.

### The dossiers now state their own voyage  (bc354fe … 83dcdd1)

Every dossier says, in print, which ship it is about, where she sailed from and
when she arrived. None of it was in the index. Search had only the name to go
on, and the names come out of a cursive hand through a recogniser: the measured
winning margins are thin — some correct hits score 0.13 — and thin margins are
what a seventy-thousand-row pool destroys. A person looking for an ancestor
knows the ship, or the year, or the port far more reliably than they know how a
clerk spelled a surname.

Two forms carry it. The interpreter's **PARTE**, which is what most of the
"blank" pages turned out to be, and the printed **header above every passenger
list**. Seven different companies' printings appear in the corpus and no two are
worded alike — `Lista de entrada de passageiros no paquete`, `Relação dos
passageiros que desembarcaram neste porto vindo no vapor`, `Porto de`.

The division of trust is the design: the labels are printed and read well, the
values beside them are handwritten and do not, so the labels are matched and the
value is reported verbatim. The month is the one exception — it is one of a
couple of dozen known words, in Portuguese *and* French, since a Compagnie de
Navigation Sud Atlantique list is dated `Octobre`.

Nothing is completed from a partial reading:

| read | recorded |
|---|---|
| `entrado em 10 deDesembro de 1924` | `1924-12-10` |
| `entrado em f de Novemlro de 1923` | November 1923, no date — the day is a stroke |
| `Entregou 1 lista com H immigrantes` | no headcount — `H` is not a number |
| `Santos, / de / de 19` | no date at all — the clerk left it blank |
| `vindos no paquete Inglez` | a flag, not a ship |
| `2104`, `Facional`, `ri  ad` | refused — a page number and two pieces of letterhead |

Search uses it without ever filtering on it. A year is taken out of the query
rather than compared against surnames; which word is a ship is decided against
the index rather than guessed. It **reorders and does not decide**: an
exactly-spelled name stays first even when the year points elsewhere, because
the user may be wrong about the year. Most of the corpus has no voyage indexed
yet and a filter would make those dossiers unfindable, which is the failure this
tool exists to prevent.

### Two silent-loss bugs found on the way  (64204b5, 30e1726)

**A re-read would have destroyed every correction anybody had typed.** Saving a
corrected row writes the whole record, engine stamp included, so the next schema
bump marked it stale, the run read the document again, and storing is a
whole-record write. The schema stamp had just gone up. Both paths that store a
reading now keep the person's rows.

**The browser test had been green against a two-day-old page.** The prototype
build died on an import error and left the previous `index.html` in place; the
smoke run went on driving it and reporting 35 passing assertions. Behind it were
nine real failures. The build now puts the repository root on `sys.path`, and
the smoke test refuses to run against a build older than its source.

### Indexing the corpus had to be made possible

The first full run reported **twenty-two hours remaining**. The cost is not
recognition, it is detection over the whole sheet — these scans are 5300×3800,
and reading one whole page measured 74 s.

| | |
|---|---|
| full page, 5287 px | 74.3 s |
| 2400 px | 29.9 s |
| **2000 px (now)** | ~22 s |
| 1400 px | 14.3 s — loses the quotation marks that tell a ship from its flag |

Three changes together: read a whole page from a 2000 px copy; read only the
strip *above* the table on a page that has a grid, since that is where the
header is; and stop reading a dossier as prose once the notation and the voyage
are both in hand — page one is the archive's cover card and states no voyage at
all.

Scaling turned out to read *better*, not worse: the detector groups the lines
the way the form is printed, so the ship and its nationality come back on the
one line they share instead of three.

### The year came from the stamp, not the writing

Not one dossier in the run resolved a year: the arrival date is handwritten in a
blank the clerk often left empty, and the year is the thing a searcher is most
likely to know. The port stamped every sheet on arrival, in ink — `JUN 23 1917`,
`JUL 5 1918`, `OUT 27 1917` — and those come through cleanly. In all ten pages
that had kept a stamp, its year matched the only year printed anywhere on the
page. **Year coverage went from 0% to 31%** on the dossiers read so far.

Only the year is taken. The stamp's date is when the police filed the sheet,
near the arrival and not the same claim — on BS.ENT.014037 the writing says
January and the stamp says June. And the year has to be the *end* of the stamp
rather than whatever in it looks like a year: hunting the digits reads `JUN 19
1918` as 1919, because the day and the century run together.

This was the first change tried on a branch and merged on a measurement rather
than on an argument, because the kept pages made it a one-second question.

### Search stopped being only a name

Three things the live index showed that the unit tests could not.

**The archive already knows every ship.** `data/catalog.jsonl` files all 7,679
dossiers under a typed ship's name; the tool reads one off the page in about a
fifth of them, mangled by the same hand and recogniser as the surnames. Both are
searchable now and they stay two claims — the page is the document and wins
where it said anything, the catalogue is somebody's note about it. Where they
differ the header carries both: *garonne*, then *lido "Jaronna"*. This needed no
re-reading at all; the catalogue is joined at query time from the manifest that
was already in the scans folder.

**A ship's name, or a year, typed on its own now lists who arrived.** "Show me
everyone on the Itapuca" is the other half of what this is for and it did not
work: a ship's name was compared against surnames and returned whatever happened
to look like it — `ITALIAS`, `Itabea Tevures` — while the dossier filed under
that exact name was nowhere in the results. A year was stripped out of the query
as a year should be, leaving nothing to search for.

**The voyage now multiplies the name match instead of being added to it.** A flat
bonus lifts every row on the named ship equally, and most rows on any ship
resemble nothing that was typed: `Contadore belvedere` put `CONGE NGLONE A`
above `Guudo Casrtadore`. Multiplied, the margin it moves is the thin one
between two spellings of a name, which is the margin it was meant for.

Also found live: an empty name query is not a query — trigrams are padded, so
the similarity of nothing against a row read as `B   B` comes out at 0.25, and
searching a year alone ranked a page of whitespace above the ship. And the row
comb catches the printed form as well as the names, so `toneladas` and `pessoas
de tripulação` were indexed as people; phrases of form words are dropped, single
words are not, because no threshold that catches `consigr` spares `gomes`
against `cognomes` or `romano` against `comando`.

### The ship's name, measured three ways

The ship is the field that would let somebody search *Valdivia 1924* and get one
dossier instead of three thousand rows, and it is the field the recogniser loses
most often. Measured on the first twenty-odd dossiers of each run:

| | dossiers naming a ship | junk among them |
|---|---|---|
| by reading order | 4% | — |
| paired by position | 41% | most of them |
| position + the form's own words refused | **26%** | 2 in 20 |

Pairing by reading order fails because reading order is not layout: a value
written a little above its printed baseline is reported *before* the label it
belongs to. On BS.ENT.013942 the ship `INDIANA` is two fragments away from the
word `vapor` by reading order and sits directly beside it on the page. The
engine now keeps each fragment's box and pairs the label with the nearest thing
to its right that shares its line.

That found something beside the label far more often, and most of what it found
was the form talking about itself — `Paguete`, `(2) papor hespanhol`,
`Repartição da Pette`, `de antos`. A wrong ship is worse than no ship: it
answers a search that should have found nothing, with the confidence of a
printed record. A candidate is now refused if any word of it belongs to the
form, the port stamps or the nationalities.

Two junk readings survive in twenty — `RI IVEO`, twice, which is a stamp. The
next filter is a minimum word length: ship names in this archive run to five
letters and up, and `iveo` does not. It is deliberately **not** being added at
the end of a session, because it would refuse a real four-letter vessel and
because every such change makes the whole corpus stale again.

### Checkpoint, 2026-08-20 midday

The re-index is **running unattended** and resumes from cache: 119 of 660
dossiers current, 0 failures, ~36 s each, roughly five hours left. Four workers
is the setting that fits this machine — five and six were both *slower*, and six
pushed it into swap.

On the 86 dossiers read so far: **91% state a voyage, 90% name the shipping
line, 41% give a year, 40% a port, 27% a ship, 13% a full date.** Years run
1917-1920 throughout. Three of the twenty-three ships read off pages are still
noise (`RII IEVEL`, a recurring stamp) — about one in eight, and the archive's
own catalogue covers the ship for search regardless.

When the run finishes: `scripts/reparse_voyages.py`, then
`scripts/voyages.py`. A server started before a schema bump goes on stamping
records with the number it started with, and the re-parse lifts them in a second.

### Where this leaves the corpus, and what is running

A full re-index is running as this is written — 660 dossiers, four workers,
around 35-40 s each. It resumes from the content-hash cache, so it can be
stopped and restarted at will and will skip whatever is already current:

```sh
.venv-ocr/bin/python scripts/serve.py --root data/scans     # then, in another shell
curl -X POST 'http://127.0.0.1:8799/api/index?dir='         # start / resume
curl      'http://127.0.0.1:8799/api/index'                 # progress
curl -X POST 'http://127.0.0.1:8799/api/index/stop'         # stop; workers finish the page
.venv/bin/python scripts/reparse_voyages.py                 # re-read the forms already on disk
.venv/bin/python scripts/voyages.py                         # what the corpus now knows
```

**Run `reparse_voyages.py` after the indexing run**, and after pulling any change
to the way the forms are read. A server that was started before a schema bump
goes on stamping records with the number it was started with; the re-parse lifts
them and costs a second. Only a change that needs the page *image* again — the
engine, the geometry — needs the corpus read a second time.

The schema stamp moved four times today (5 → 8) as the engine learned to read
these forms, and each move makes every earlier record stale by design. **A
person's corrections now survive that**, which they would not have this morning.

### Next, in order

1. **The ship's name is the weak field.** The letterhead is printed and comes
   back on nearly every list; the vessel's name beside `no paquete ___` is
   handwritten and mostly does not. Reading both forms of a dossier together is
   today's answer; the real one is to pair a printed label with the handwriting
   *beside* it using the detector's boxes, rather than by the order it reports
   its fragments. That is the one structural improvement left in this feature.
2. **Confidence is not calibrated** — `conf.surname` is Paddle's raw decode
   score, shown as if it meant trustworthiness. Allan saw a green label on
   `Brges. iuig`. Hide it or calibrate it against hand-read truth.
3. **Rows that are not passengers** — the `/36` line and the tally block are
   read as people. Same class of problem as the column heading flag.
4. **Ditto inheritance**, stored beside the verbatim text rather than replacing
   it. 013990 is the fixture.
5. **`data/transcriptions/` will outgrow memory.** Search loads every row; at
   7,000 dossiers that is roughly a million. It wants SQLite before then.
6. Handwriting recognition, still the ceiling, and still the thing pretrained
   models do not solve.

### Questions that are Allan's to answer

* **Is the ship's name worth the box work?** It is the field that would let
  somebody search "Valdivia 1924" and get one dossier instead of three thousand
  rows, and it is the field the recogniser loses most often.
* The corpus re-index takes hours on this machine. **Is unattended overnight
  indexing the intended flow**, or should the tool do a fast pass first — the
  forms only, no row recognition — so that a folder becomes searchable by ship
  and year within minutes and by name later?
* `port` and `origin` are exported and shown exactly as read: `Nio Sumalos` for
  Rio de Janeiro, `Beuenes crures` for Buenos Aires. Correcting them against a
  gazetteer would be a guess the scan cannot check. **Is verbatim right here**,
  or should a canonical name sit beside the reading?

### What the remaining blank pages actually are

Most of the ten are **not passenger lists**. They are the interpreter's *PARTE*
form, and no rows is the right answer for them:

> do Intérprete *Matheus H. Ferreira* / que visitou o paquete *Francez*
> "*Valdivia*" / procedente de *B. Aires e escalas* / entrado em *10* de
> *Dezembro* de 19*24* / Entregou *1* lista com *12* immigrantes

Ship, nationality, port of origin, arrival date, headcount — printed labels
around handwritten values, on a page currently thrown away. The same voyage is
printed again in the header of every passenger list. **None of it is indexed**,
which is why a search has nothing but the name to go on. That is the next piece
of work, and it is the one that answers "search ranking should use more than the
name".

### Checkpoint, 2026-08-20 evening — the corpus was read, and two things it read are wrong

The re-index finished: **660 dossiers, 198 read and 462 already current, no
failures, 3 h 36 m** — about 65 s a dossier on the afternoon's larger files,
against 24 s on the first stretch. `reparse_voyages.py` changed nothing, which
is the right answer: the server was started after the last schema bump, so every
record already carried schema 14.

346 Python tests and 73 of 74 browser assertions pass. The one failure is not
cosmetic, and neither is what it led to.

#### What the whole corpus knows, against what twenty dossiers suggested

The midday figures came from the 86 dossiers read by then, and those are the
small early ones. On all 658 records at schema 14:

| | midday, n=86 | now, n=658 |
|---|---|---|
| states a voyage | 91% | 69.8% |
| names a shipping line | 90% | 63.5% |
| gives a year | 41% | 24.8% |
| gives a port | 40% | 26.3% |
| names a ship | 27% | 26.0% |
| gives a full date | 13% | 5.6% |

The ship holds; everything else roughly halves. 134 distinct ships are named.
The line list still carries the form talking about itself — `No. 461B` fifteen
times, `Repartição da Policia` eleven, `BR.AN.RiO.O2.O.RPV.PRJ.1GGS.8` ten —
about one in eight of the lines read is letterhead or the archive's own
notation.

#### The stamp is not a reliable year, and the record cannot be audited

Years came out spanning 1913-1928, which is wider than this corpus should be.
**1928 is a misreading of 1923.** In every case the port's stamp and the date
printed on the same page disagree, and the stamp wins because the stamp is where
the year is taken from:

| dossier | stamp, as read | the date printed on the same page |
|---|---|---|
| BS.ENT.016669 | `DEZ 29 1928` | `Dec.de 1923.` |
| BS.ENT.016672 | `DEZ 80 1928` | `de 19123` |
| BS.ENT.016331 | `JUN 19 1928` | `de 192.3` |

A `3` reads as an `8`, and `DEZ 80` is not a day this or any month has. The
morning's rule — the stamp's year matched the only year printed on the page, in
all ten pages that had kept a stamp — held at n=10 and has three counterexamples
at n=660. The lower bound, 1913, is one dossier (OL.PRJ.19068, `entrado em 23 de
Novenlo de 1913`) read off an interpreter's PARTE, and is plausible but
unconfirmed. What the corpus actually reads as is **1917-1925**.

The second half of this is worse than the first: **a record does not say where
its year came from.** The stamp and the printed date are two different claims —
the stamp is when the police filed the sheet — and only one number is kept.
Nothing on disk distinguishes a year read from a stamp from a year read from the
form, so these three could only be found by going back to the page text. A year
should carry its source, and where the two disagree the *printed* date should
win: a clerk's pen and a rubber stamp fail in different ways, and the stamp
fails on digits.

#### Every row was stored without the geometry it was cut from

The failing browser assertion is `the scan band follows the hit`: click a search
hit, the right row is selected, and no band is drawn on the scan beside it.
Across the corpus:

```
records 660 | rows and geometry 2 | rows, no geometry 634 | no rows 24
```

**658 of 660 records store an empty `geometry`.** The two that have it were
measured through `/api/grid`, one page at a time, by hand.

`transcribe_document()` in `scripts/serve.py` builds each page as `{"n", "kind",
"error"}` and a `form`, and never copies `res.geometry` — which the engine does
return (`engine.py:35`, set in `engine_paddle.py:672`) and which the review UI
already knows how to read (`serve_shapes.py:57` normalises per-page geometry for
exactly this). The measurement was taken, used to cut the rows, and dropped on
the way to disk.

What that costs: a search hit can say *which row* but cannot show *where on the
scan* — which is the one thing that makes a mangled reading usable as evidence,
because the person checks the image and not the transcription. It was reported
as a success for three and a half hours.

The repair does not need the engine. Row geometry is `page_geometry.analyze`, a
measurement on the page image, and `data/pagecache` still holds every extracted
image — so recomputing it for the one transcribed page of each dossier is
roughly half an hour, not another 3 h 36 m. **Do not start another full re-index
for this.**

#### Also today

Reading the voyage off both forms a dossier carries, pairing a printed label
with the handwriting beside it by box rather than by reading order, the ship and
the year as things a searcher can type on their own, CSV export, the second
reading offered as an alternative instead of a retype, and the browser test
stopped passing against a stale build. Forty-seven commits, all pushed.

#### Next, in order

1. **Keep the geometry** on every page a document is read from, and backfill the
   660 records already on disk from `data/pagecache`. Both halves matter: the
   fix stops the loss, the backfill is what makes the corpus usable.
2. **A year must record its source, and the printed date must outrank the
   stamp.** Then re-parse — this needs no page image, so it costs a second.
3. **The corpus is a sample, not the target.** 660 dossiers were downloaded from
   the eleven index PDFs in `indices/`; the catalogue extracted from those same
   PDFs lists **7,679**. Allan's instruction is that the full set is downloaded
   once the implementation is done, so nothing here should be tuned to 660.
4. The shipping line takes letterhead and archive notation as a company name,
   about one in eight.
5. Confidence is still Paddle's raw decode score, shown as if it meant
   trustworthiness.
6. `data/transcriptions/` is 660 files read into memory on every search. At
   7,679 it wants SQLite.

#### Open, and Allan's to answer

* The full download is ~7,679 dossiers. At the measured 65 s each that is
  **about five and a half days** of indexing on this laptop, unattended. That
  number, not the engine, is what decides whether the fast forms-only first pass
  gets built before the download.

## 2026-08-19 — night session (Allan away)

Four fixes, all committed and pushed. The corpus is downloading toward ~570
dossiers; ~525 on disk at the time of writing.

### The comb now finds the rows  (875087e, 43049eb)

BS_ENT_013990 p2 lists eighteen passengers. The engine read three. It now reads
**all eighteen**, in the right rows:

| row | engine | on the page |
|---|---|---|
| 1 | `Nayomgo Cassaudii` | Raymundo Cassaudi |
| 2 | `Alfiedo J. ravares` | Alfredo J. Tavares |
| 3 | `Jain E. Gil` | Jaim C. Gil |
| 8 | `Sctomio as dr Auida` | Victorio Dias de Almeida |
| 18 | `Eig Burges.` | Luiz Borges |

Wrong as transcription, findable as search, and — the point — *present at all*.
Rows 23-28 are the tally block at the foot, kept separate from the passengers.

Three things were wrong, each hiding the next.

**The table's top came from rule continuity.** `rule_extent` takes the longest
*unbroken* vertical run of ink at each column rule. Writing crosses the rules,
so where people are listed a rule survives only as short segments — 17 to 21 per
column here. The longest run is therefore always the emptiest stretch: the top
came out at 0.559 of the page and the comb was fitted to blank ruled paper below
the list.

**The line detector could not see the rows.** At the 70th percentile it reported
ten lines for about fifteen written rows. That hand is light. No choice of
bounds could have found rows the detector never reported.

**Rule support selects emptiness.** The obvious guard — "is this band inside the
table? do the column rules run through it?" — is backwards. Support is *highest*
where nobody has written. On 013990 it measures 0.00-0.09 across the whole
passenger block and 0.64-0.82 on the blank paper below. As a quality gate it cut
the comb back to the empty strip: the same failure, one level up.

What holds now: the old fit is computed unchanged and stays the default. A wider
fit is only *considered*, looks harder (55th percentile), and must beat the
default by a margin on how much writing it covers, be at least half writing
itself, and overlap the table the rules did find — so it extends that table
rather than relocating to another block of ruled lines, which is what it did on
BS_ENT_015953 before the constraint.

Measured on 89 pages with `scripts/bench_geometry.py`, which scores what share of
the name column's ink falls inside a band:

| attempt | improved | regressed | mean coverage |
|---|---|---|---|
| refit pitch over whole page | 17 | 54 | 0.379 → 0.284 |
| score by lines per band | 16 | 39 | 0.379 → 0.316 |
| score by count, with floor | 18 | 15 | 0.379 → 0.376 |
| + margin, floor on challenger only | 12 | 1 | 0.379 → 0.402 |
| + overlap constraint (875087e) | 7 | 0 | 0.379 → 0.393 |
| + looser detection, unified scoring (43049eb) | **21** | **0** | **0.379 → 0.457** |

`BR_RJANRIO_OL_0_RPV_PRJ_15992` — recorded in the last checkpoint as a layout
geometry could not read at all, zero rows — now comes back at 0.285.

The known limit is in its test: a letterhead butted directly against the first
row *and* sharing the ruling's pitch is not separable by anything measured here.
Real forms leave a gap; 013990's comb starts below its header block.

### Every cover card was being lost  (22ce7b8)

167 of 168 documents failed page 1 with `NotImplementedError: (Unimplemented)
ConvertPirAttribute2RuntimeAttribute`, and the run reported success. oneDNN
refuses the detection pipeline — which builds fine and dies on use, so the retry
has to wrap the call, not the construction. That path produces the cover text
`identify()` reads, which is why every record fell back to filename identity.
oneDNN is kept for the row recogniser, which is happy with it.

### Corpus properties from Allan, to design around

* **Ditto marks are real** — confirmed on 013990's Nação column. My sample
  surfaced none, which was a sampling limit, not evidence of absence.
* **Blank means "unknown"**, not "the engine failed". This is why the density
  floor is never applied to the default comb: a correct comb over thirty rows
  may hold only fifteen detected lines.
* **Do not assume fixed geometry** — scans are misaligned and faulty. Every
  bound above is derived from the page in front of it.
* White-on-black pages are first or last and carry nothing needed.

### Next, in order

1. **Re-index and re-measure.** Every number about blank rows predates the comb
   fix and means little now.
2. **Ditto inheritance**, stored beside the verbatim text rather than replacing
   it. 013990 is the fixture.
3. **Confidence is not calibrated** — `conf.surname` is Paddle's raw decode
   score, shown as if it meant trustworthiness. Allan saw a green label on
   `Brges. iuig`. Hide it or calibrate it against hand-read truth.
4. **Rows that are not passengers** — the `/36` line and the tally block are
   read as people. Same class of problem as the column heading flag.
5. Handwriting recognition, still the ceiling, and still the thing pretrained
   models do not solve (see the daytime entry).

## 2026-08-19 — evening session

Three fixes committed and one large defect found and not yet fixed. The corpus
was re-indexed once (167 done, 1 skipped, 0 failed, 44.7 min).

### Pretrained handwriting models are not the answer

Allan's question was reasonable: handwriting recognition is the first example in
every ML course, so why build anything? Measured on the cursive Gelria page,
against the recogniser that ships (CER 0.205, ~0.06 s/row):

| model | CER | s/row |
|---|---|---|
| PP-OCRv6_medium_rec (ships) | **0.205** | **0.06** |
| microsoft/trocr-base-handwritten | 0.785 | 7.74 |
| microsoft/trocr-large-handwritten | 0.607 | 8.09 |

Three times worse and ~130x slower. The failure mode is the whole argument:
TrOCR read `EMMA CONTADORE` as `VERSION Constadvice`, `EMILI MUESSO` as
`Israeli Meteor`, `A. VIEIRA MIRANDA` as `A.P. Disufflements`. Its decoder is a
RoBERTa language model, and a language prior is *harmful* when every target is a
proper noun it has never seen: it reads the strokes, then corrects them into
English words. The recogniser that ships is CTC with no language model, which is
exactly why it wins here. Allan: "using a language model is asking for errors."
Scale is not the issue — the large model fails the same way. `scripts/spike_htr.py`.

### The ink mask was destroying faint pages  (fixed, 8b56f65)

`page_image` prefers the PDF's embedded MRC mask because geometry needs it
(nine column rules against three from a render). The mask is one bit deep, so
faint strokes fall below its threshold and are gone before recognition runs. On
BS_ENT_015741 p2 the recogniser read 7 of 39 bands from the mask and 26 from a
grayscale render — an entire family (BLOCH ALEXANDRE, HENRIETTE, LINE,
JACQUELINE, MADELON, FRANÇOISE) was missing from the index and is legible to the
eye.

Not a blanket win, which is why it is a fallback: over ten pages the mask read
63.3% of bands and the render 68.2% — seven pages unchanged, one gained
nineteen rows, and BS_ENT_017053 *lost* five. A page is read from the mask; only
if that comes back under half-read is it read again from a render, and the
second reading is kept only if it found more names. Corpus-wide the re-index
moved rows-with-text from 60.0% to **61.7%**, well below the sample's +4.9
points because the sample was chosen partly *because* those pages failed.

### Re-indexing could not reach the corpus  (fixed, 258a69a)

Any record an engine had written counted as finished, so no engine improvement
could ever be applied: a re-run skipped all 168 documents and reported success.
`is_indexed` now requires the current schema stamp for engine-written records,
still never redoes a record a person typed, and still refuses to treat an empty
manual note as an index. SCHEMA is 2.

### Rows are cut along the paper now  (fixed, d67b8d4)

Allan, reading ITAPEMA 013990: the leg of the `y` in row 1 "Raymundo Cassaudi"
lands inside row 2 "Alfredo C. Tavares", between the `l` and the `f`. A straight
cut corrupts both rows, and `refine()` made it worse, since trimming to ink
*expands* a crop toward whatever intruded. Boundaries are now found as paths of
least ink across the column (`desembarque/rowcut.py`), shared between
neighbours so a stroke lands on exactly one side. The same seam does columns —
Allan reports names bleeding sideways past the rule too. The limit is tested,
not hidden: a tail reaching further than the seam's margin needs the stroke
traced, which is a different technique.

Measured on 013990 it changed eight rows and improved none of them, because
that page fails for a much larger reason (below).

### THE BIG ONE, NOT FIXED: the row comb fits the wrong half of the page

BS_ENT_013990 p2 has **18 numbered passengers**. The engine produced text for 9
rows, and the three real names among them were passengers 16, 17 and 18. Rows
1–15 were never looked at, and what looked like mangled names (`Crallleeros NM`,
`1rEreeeteei vr 2`) were the tally block at the foot of the page.

`detect_rules` bounds the table with `rule_extent`, the longest *continuous*
vertical run of ink per column, tolerating gaps of 40 px. Where passengers are
written, the handwriting shatters each rule into 17–21 short runs, none longer
than 5% of the page. Where the table is empty the rules print cleanly. So the
longest run is always the blank region, the table top comes out at **0.559** of
the page, and the comb fits the empty ruled area below the list.

This is very likely a large share of the corpus-wide 38.3% blank rows — not
clerks skipping lines, not ditto marks, not faint ink, but geometry measuring
the wrong half of the page.

Raising the gap tolerance is not the fix, measured:

| page | gap 40 | gap 80 | gap 150 | gap 250 |
|---|---|---|---|---|
| 013990 (broken) | 0.559 | 0.559 | 0.559 | **0.083** |
| 016739 (working) | 0.208 | 0.194 | 0.135 | **0.030** |
| 015106 (working) | 0.257 | 0.226 | 0.207 | **0.065** |

013990 only recovers at 250, which overshoots into the letterhead on the pages
that currently work. The table's top has to stop being derived from rule
continuity alone: find text lines across the full page between the outer column
rules, fit the pitch to those, and use the rules for the bottom bound only. The
risk is the failure already recorded in the code — letterhead and signature
lines giving "37 rows for a 26-row table" — so the pitch fit has to reject
outliers, and it needs testing across many pages.

### Also found, not fixed

* **`enable_mkldnn=True` crashes the full-page OCR path.** 167 of 168 documents
  (99%) failed page 1 with `NotImplementedError: (Unimplemented)
  ConvertPirAttribute2RuntimeAttribute`. With mkldnn off the same page reads
  fine. That path produces the cover text `identify()` uses, which is why every
  record fell back to filename identity. One-line fix, high value, untested yet.
* **Confidence is not calibrated.** `conf.surname` is Paddle's raw decode score,
  shown in the UI as if it meant trustworthiness; Allan saw a green label on
  `Brges. iuig`. For an evidence tool it should be hidden or calibrated against
  hand-read truth.
* **Ditto marks are real**, confirmed by Allan on 013990's Nação column. My
  168-dossier sample surfaced none, which was a sampling limit and not evidence
  of absence. 013990 is the fixture when this is built.
* **Blank means "unknown"**, per Allan: clerks leave a cell blank when the
  information is not known. Blanks must not be counted as recognition failures.
* **The name column is picked by rule index, not width**, and lands on the
  Numero strip when the divider is detected. Measured at ~7% of pages, so real
  but small. `scripts/spike_columns.py`.
* **German-line ships are ~3.7% of the catalog** and their forms are Portuguese
  Brazilian port documents, so Kurrent/Sütterlin risk is lower than feared —
  n=2, unconfirmed.

### Next, in order

1. **The row comb fitting the wrong half of the page.** Everything else is
   smaller than this.
2. **mkldnn off for the full-page path** — 99% of documents, one line.
3. Re-index and re-measure; the 38.3% blank figure means little until 1 is done.
4. Ditto inheritance, stored beside the verbatim text rather than replacing it.
5. Confidence: hide or calibrate.

## 2026-08-19 — daytime session (Allan at work)

Everything below is committed and pushed to https://github.com/allan-valin/ocr-gene-docs — nothing is running, no background
jobs, no servers left up. The local corpus in `data/scans` is fully indexed, so
search works the moment the server starts.

### The headline

**The corpus is 168 dossiers now — 865 pages — and all of it is indexed, with no
failures.** 110 more dossiers were downloaded this afternoon to answer the question
the morning's numbers could not: does search still work when the pool gets bigger?

It does for typed pages. **It is starting to fail for handwritten ones**, exactly as
the margins predicted.

| pool | typed page: ranked first | typed: top five | handwritten: ranked first | handwritten margin |
|---|---|---|---|---|
| 147 rows | 26/26 | 26/26 | — | — |
| 1,081 rows | 23/26 | 26/26 | 5/6 | +0.114 |
| **3,430 rows** | **20/26** | **26/26** | **4/6** | **+0.043** |

"CEZARIO SAMMAMED" is now lost entirely: at 3,494 rows the word "SUMMARIO", printed
on some other page, outranks the row it belongs to. A twentyfold larger pool is
coming, and this is what it will do.

So the ranking is clear: **handwriting recognition is the thing worth money now.**
Speed is solved, indexing is solved, search is solved for typescript.

### Throughput, re-measured on the harder half

The morning's "35 hours for 7,000 dossiers" came from the first 57 dossiers, which
are small. The dossiers downloaded this afternoon are two to five times larger, and
on those the rate collapsed to about one dossier a minute — until profiling found the
cost was not recognition at all:

| step, per page | before | after |
|---|---|---|
| extract the page image | 11.6 s | 4.8 s first time, then free |
| geometry | 2.3 s | 2.3 s |
| recognise the rows | 2.6 s | 2.6 s |

`pdfimages` re-parses the whole PDF on every call, so a five-page dossier was five
full parses, and the chosen image was recomputed every time the page was touched.
Extracting each document once and recording the result **roughly quadrupled indexing
throughput**: the final pass did 90 dossiers in 26.6 minutes, ~17.7 s each.

At that rate 7,000 dossiers is **about 34 hours** on this laptop — the earlier figure
survives, but for a different reason than it was first arrived at.

### What made it ten times faster

The name column was being detected and then recognised. But the grid already knows
where every row is, so detection is redundant: crop the row bands, recognise them
directly. That was 21× faster and, at first, much worse — CER 0.418 against 0.205.

The cause was not the model. **The recogniser's input is 320 px wide, and a manifest
name is wider**, so every long name was silently truncated: "JOHN SCHRADER" came back
as "JOHN". At 640 px the accuracy is *identical* to the detection pipeline (CER 0.205)
at a tenth of the cost. Measurements in `scripts/spike_speed.py`, and the mobile
recogniser was rejected there too (CER 0.508 at any width).

### Two bugs that were invisible until the corpus was run

* **Fourteen of the first twenty dossiers were stored as negatives** — white ink on
  black paper, because the PDFs keep an MRC ink mask with 1 = ink. Geometry never
  minded, since a projection does not care which way contrast runs, which is why a
  night of grid work never noticed. Fixed in `page_geometry.positive()`. Honest note:
  **fixing it did not measurably improve recognition** — the recogniser was already
  coping — but it makes every crop legible to a human, which the review UI depends on.
* **An empty manual note marked a document as indexed forever.** Someone opens a
  dossier, types nothing, and it silently drops out of every future run. For an
  archive index that is the worst failure mode: nobody is told, and the person is
  simply never found.

### PaddleOCR-VL: not viable on this machine

Loaded fine (`vl_rec_backend="native"`, no torch needed) in 14 s, then spent **22
minutes on a single name column without finishing**, against 2.4 s for the
recogniser. Even as an on-demand "read this one page properly" action that is
unusable without a GPU. `scripts/spike_vl.py` is kept for when there is one.

So the answer to "if it is still too bad, jump to PaddleOCR-VL" is: **the small
engine is not too bad** — 5/6 on cursive — and VL is not reachable on this hardware
anyway.

### Where the handwriting actually stands

Engine, on a cursive page: `GUIDO CONTADORE` → `Guudo Camtadore`, `CEZARIO SAMMAMED`
→ `Besaruir Sormamed`. Wrong as transcription, findable as search. That is the whole
argument for measuring retrieval rather than CER — but the winning margins are thin
(some hits score 0.13), and thin margins are what a 70,000-row pool destroys. **This
is the number to re-check as the pool grows.**

The first hand-read ground truth for a handwritten page is now in
`data/truth/`, versioned. Until today the only truth in the repository was a *typed*
page, which is why none of this was visible.

### Also fixed, after the corpus run showed them

* **Search hits now land on the row**, at the right page, with the band drawn on
  the scan. A hit that only opened the document left the user hunting the page for
  the name they searched for.
* **The printed column heading was indexed as a passenger.** "Nomes e Cognomes"
  scored 1.0 against anyone searching a name containing "nome". Exact matching
  caught almost none of them, because the recogniser reads the caption differently
  on every page, so multi-word captions are matched loosely. 24 rows left the index,
  no real name did.
* **Filenames are resolved from the content hash at query time.** Transcriptions are
  keyed by hash so a renamed dossier keeps its work, which means a hit knows what it
  found and not where — and the 57 records indexed this morning have no filename in
  them at all.

### Built today

* `/api/index` — folder indexing: start, progress with a plain-language estimate,
  stop, resume from the content-hash cache, failures named. Four documents at a time.
* `/api/search` + a sidebar search box — **searches every indexed document**, not the
  open one. Trigram matching, an explicit floor below which nothing is returned.
* `desembarque/engine_paddle.py` — the real engine, replacing `NullEngine`.
* `desembarque/search.py`, `scripts/spike_speed.py`, `scripts/spike_retrieval.py`,
  `scripts/spike_vl.py`, `docs/HOSTING.md`.
* Rows now follow the page being read; fields the engine never attempted are blank
  rather than "ilegível".
* **113 Python tests, 35 browser assertions, all passing in Chromium and Firefox.**

### The layout the geometry cannot read

`BR_RJANRIO_OL_0_RPV_PRJ_15992` page 2 is a clean passenger list — 24 handwritten
rows, printed column captions, a wide "Nome" column — and geometry returns **zero
rows** on it, then picks the 1.4%-wide "No. de ordem" strip as the name column. The
row comb is fitted to the written lines, and on this layout it finds none.

Across the corpus this is a minority: **8% of indexed documents come back with no
readable row at all.** But a dossier that yields nothing is a ship nobody can search,
and the failure is silent — the run reports success. It is the most valuable thing
left to fix, and it is deliberately *not* being attempted in a rush at the end of a
session, because the geometry currently works on the other 92%.

### Next, in order

1. **Handwriting recognition.** This is now the only thing standing between the tool
   and its purpose. The printed-text recogniser reads `GUIDO CONTADORE` as
   `Guudo Camtadore`, which fuzzy search rescues at three thousand rows and will not
   rescue at seventy thousand. Options, cheapest first: a recogniser trained on
   handwriting; fine-tuning this one on a few hundred hand-read rows from this
   archive; a vision-language model on a machine with a GPU.
2. **The layout the geometry cannot read** (above). 8% of documents yield nothing,
   silently.
3. **Search ranking should use more than the name.** A person searching knows the
   ship, or the year, or the port. Nothing in the index is used for that yet, and it
   is the cheapest way to cut the pool a name is compared against — which is exactly
   the problem the table above describes.
4. **Re-index to pick up the header flag and the schema stamp.** Records written this
   morning have neither; search compensates by matching heading text instead.
5. **Geometry is the floor on speed** at 2.3 s of a ~10 s page, now that extraction is
   cached. Untouched.
6. **`data/transcriptions/` will outgrow memory.** Search loads every row; at 7,000
   dossiers that is roughly a million rows. It wants SQLite before then, not a bigger
   dictionary.

### Future work, written down when it was asked for

* **Knowing what kind of document is on the screen** — `docs/FUTURE-document-types.md`.
  Certificates, notary books and German records from the 1700s are coming through
  the FamilySearch API, and they are not the shape this reader assumes. Identify
  the type, choose the geometry from the type, and show the type in the file list
  with an icon a person can correct.

### Open questions for Allan

* ~~**How much does handwriting matter to you?**~~ **Answered 2026-09-03:** it is
  the whole point — "typed stuff I don't need help with". Work is ranked by what it
  does for a cursive page from here. The first of it shipped the same day (T13, the
  faint hand): a searcher with only a name now reaches five more of the 142 hand-read
  names in the top twenty, and the page the work was written for has 10 of its 36 read
  rows reachable by typing a real name where it had none.
* Is ~34 h for 7,000 dossiers acceptable? Four workers use ~7 GB and leave the laptop
  usable; more workers would cut the wall clock and make it unpleasant to use.
* `docs/HOSTING.md` recommends local-only as the shipped default, with hosting as a
  separate deployment. You said hosted is fine "as long as it is intuitive" — that
  document is where I wrote down what intuitive has to mean if scans are uploaded.
* The hand-read ground truth in `data/truth/` is my reading of a cursive hand. If any
  of those six names are wrong, the handwriting numbers above are wrong too.
* 110 dossiers were downloaded from the archive this afternoon (serial, 1.5 s apart,
  the repo's own polite downloader) to get these numbers. Say if you would rather that
  did not happen unattended.

### Running it

```sh
# the engine venv runs the app too, and is the one to use for indexing
.venv-ocr/bin/python scripts/serve.py --root data/scans
.venv/bin/python scripts/serve.py          # app only; engine reads "não instalado"
.venv/bin/python -m pytest tests/ -q       # 113 tests
python3 scripts/smoke_prototype.py --url http://127.0.0.1:8799/selftest   # 35 assertions

# measurements
.venv-ocr/bin/python scripts/spike_speed.py            # per-variant speed and CER
.venv/bin/python scripts/spike_retrieval.py            # retrieval over the real index
```
