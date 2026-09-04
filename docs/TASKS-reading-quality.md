# Reading quality: tasks

One task per goal in `docs/superpowers/plans/2026-08-28-reading-quality.md`,
in that plan's order of work. A task is done when its measurement exists and
is written down beside it, not when the code runs.

- [x] **T1 — Dropdown toggle** (§6). Done 2026-08-28, commit a1f6cea.
- [x] **T2 — Candidates on screen without a toggle** (§5). Done 2026-08-28, commit 0ab97fd.
- [ ] **T3 — The instruments** (§5, §4).
  - [x] `scripts/bench_menu.py`: over the hand-read truth pages, is the true
        name among the candidates offered for a badly-read row, and at what
        rank? Baseline number for today's menu, per source (engine alternates,
        archive names), recall@1/3/5/10.

        Measured 2026-08-28 over the five hand-read pages: 87 of 142 rows have
        a stored reading at all — 48 of the missing 55 are BS.ENT.013947 p3,
        held by the freeze in T4 — and of the 224 paired words the engine read
        112 wrong. In those 112:

        | source | true name offered | @1 | @3 | @5 | @10 |
        |---|---|---|---|---|---|
        | engine alternates | 5 | 0.045 | 0.045 | 0.045 | 0.045 |
        | archive names | 43 | 0.241 | 0.339 | 0.384 | 0.384 |
        | the menu as it ships | 47 | 0.170 | 0.330 | 0.420 | 0.420 |

        So the menu reaches the right name for two badly-read words in five,
        and the engine's own alternates carry almost none of that.
  - [x] `scripts/bench_check.py`: which reasons for a second look actually
        find the badly-read rows, and how often each stops somebody on a row
        that was right. See T8.
  - [ ] `scripts/bench_columns.py` + per-column truth for one typed and one
        cursive page (blocked on §4 having anything to score).
- [x] **T4 — Per-row provenance** (§2), done 2026-08-28 and proved on the
      documents it was written for: the four frozen records were read again,
      613 rows came back on pages the old whole-record save had dropped, and
      every row a person had typed survived verbatim. A search for
      *Santabarbara* now reaches page 3 of BS.ENT.013947 at all, which it could
      not before — how well it reads there is the recogniser's business and is
      what `bench_menu.py` measures. `preserve_human_work` keeps the rows a
      person typed and lets the re-read replace the rest. Unit test first:
      one typed row + forty engine rows, re-read, typed row verbatim and the
      forty updated.
- [x] **T5 — Clear the fossils** (§3) — *measured, and there are none to clear.*
      With T4's per-row question answerable, every non-name value in the corpus
      turns out to have been typed by a person, not left by an engine pass:
      26 rows of BS.ENT.017397, which is a whole page hand-transcribed (the
      document the demo carries), and the two Allan saw on BS.ENT.013942 —
      `occupation: SIRVIENTA` on row 1 and `nationality: BELGA` on row 5, both
      carrying `edits` stamped 2026-08-21T18:08 and 19:28, from a session at
      the review screen. Nothing else in 660 records has a value in those
      columns, because the engine has never written one (§4).
      So they are not deleted: they are somebody's typing. What was wrong is
      that the screen shows a typed value exactly like a read one — moved to
      T9, where the display work is.
- [x] **T6 — Stop asserting surname and given** (§1). *Done.*
      - [x] The repetition mark now inherits **the words written above it**,
            from the left, counting only the words its own row does not write:
            `Ant Alonso Gonzalez` above `" Maria` gives *Ant Alonso*, and a
            mark with nothing beside it repeats the whole name. It is no longer
            read off a stored `surname`, which was `split_name`'s assumption
            wearing another hat. `resolve` also no longer needs the engine to
            have split a row to know what a mark below it repeats.
            `bench_search.py --matrix` is unmoved — 86/95/99 of 142 by name
            alone, before and after — which is what was wanted: the same
            findability without the claim.
      - [x] **Done 2026-08-29 evening.** `split_name` is gone, and so is the
            review screen's `splitName`, which split a person's correction the
            same way on the way in. The engine writes `name_raw` and the score;
            `ditto.resolve` writes `inherited` and marks the field `name`;
            `ditto.written` is the row's own words with the mark dropped, and a
            row means the first followed by the second.
            `conf` is keyed `name`, because that number was always the score of
            the name strip and never the surname's.
            The spreadsheet carries `repete_de_cima` and `nome_completo` where
            it carried *sobrenome* and *nome*, and `repeticao_origem` says
            whether the repetition came from the clerk's mark, the indent under
            it, or the row's position.
            **Nothing on disk was rewritten and the corpus was not re-read.**
            660 records carry the old fields; `desembarque/rowfields.py` and
            `search.row_text` understand both shapes and only the new one is
            written — re-reading 700 pages to pick up a rename produces data,
            not knowledge (see PROGRESS, the reference-set methodology).
            `bench_search.py --matrix` measured before and after each of the
            three commits and unmoved every time: 86/95/99 of 142 by name
            alone, 118/122/129 with the crossing named.
            Left deliberately: the spikes read `given`/`surname` out of truth
            files, and those are measurements already taken.
            Every place that has to change, so the next session does not have
            to find them again:
            * `desembarque/engine_paddle.py:282` `split_name`, and its one
              caller at :343 — the row it builds keeps `name_raw` and the
              recogniser's score, and stops carrying `surname`/`given`.
              `conf` is keyed `surname` too, and that key is the score of the
              *name strip*, so it wants renaming with the field.
            * `desembarque/ditto.py` — `inherited` is already the true output;
              the three places that also write `surname`/`given` for
              compatibility come out, and `ditto` names `name` rather than
              `surname`.
            * `desembarque/search.py:230` `row_text` — the ditto branch reads
              `surname` + `given`; it becomes `inherited` + what the row wrote.
              :450 carries the score into a hit.
            * `desembarque/export.py:94` — two columns, *sobrenome* and *nome*.
              The export should carry the name as read plus what the mark
              repeats, and say which is which.
            * `scripts/serve.py:84` (the check's score), :286 (the empty rows a
              page starts with).
            * `scripts/build_names.py:81` — the dictionary is counted off
              `conf.surname`.
            * `prototype/review.html` — `nameText`, `splitName` (which splits a
              typed correction the same way and would then be pointless), and
              the name cell.
            * The spikes (`spike_ocr`, `spike_scale`, `spike_speed`,
              `spike_guided`) read `given`/`surname` out of truth files; they
              are measurements already taken and can stay as they are. `name_raw` is the row's
      name; the repetition mark inherits the tokens written above it. Nothing
      claims a name order unless a person typed it. `bench_search.py --matrix`
      must not fall.
- [x] **T7 — Candidates from the strokes** (§5), first pass, measured. `desembarque/strokes.py`:
      `desembarque/strokes.py` re-cuts minim runs, reads a tall stroke the
      other way, swaps round letters, expands the clerks' abbreviations, trims
      ink at an edge, reads a looped capital as the two or three letters it was
      cut into, and splits a word the clerk wrote as two. `gazetteer.menu_for`
      puts them in the order that measured best and `/api/names` serves it, so
      the number below is what a reader gets — the menu is 12 long, of which at
      most 5 are readings nobody has read before, and none of those when the
      word is already a name.

      | menu | true name offered | @1 | @3 | @5 | @10 |
      |---|---|---|---|---|---|
      | before (archive names only) | 47 of 112 | 0.170 | 0.330 | 0.420 | 0.420 |
      | with the strokes | 51 of 112 | 0.179 | 0.375 | 0.455 | 0.455 |

      Per rule, alone, over the same 112 words: ascender 12, edge 8, capital 7,
      two changes 5, space 4, round 3, minims 0, abbreviation 0. The last two
      score nothing *on these four pages* and stay for now: they are the rules
      the plan's own examples turn on — `Mania`/`Maria`, `Ant?`/`Antonio` — and
      those examples are on BS.ENT.013947 p3, which has no stored reading to
      score against until T4's fix is re-run over the archive.
      **A second name list, 2026-08-28.** The rules that need a name to speak
      for — trimming a neighbouring column out of the name strip, reading a
      looped capital back, splitting two names written as one — had nothing to
      speak for on most words, because the archive's own list is 1,081 names
      and *Santos*, *Sorio* and *Rossendal* are not among them.
      `data/language_names.json` is 259 names written by hand from the
      languages these ships carried, kept apart from the archive's count
      because it is a different claim: *these languages use this name*, never
      *this archive has read it*. It is ranked below everything the archive has
      read, capped at four per menu, marked `⌇·` on screen, and the names that
      appear only on the hand-read pages were deliberately left out so the
      bench measures the rules and not the file.

      | menu | true name offered | @1 | @3 | @5 | @10 |
      |---|---|---|---|---|---|
      | archive names only | 77 of 217 | 0.157 | 0.309 | 0.355 | 0.355 |
      | with the strokes | 83 of 217 | 0.161 | 0.323 | 0.378 | 0.382 |
      | and the language list | 87 of 217 | 0.161 | 0.327 | 0.392 | 0.401 |

      **The guesses are the top of the menu now.** Measured on the block
      alone — the engine's own readings are a separate section on screen, so a
      rank that mixes them answers neither question — the first line of the
      guesses is the right name for 51 of 217 badly-read words (0.235 at rank
      one, 0.355 by three, 83 found), while the engine's second reading of a
      word is right for 6. The word the engine read is already on screen; it is
      the cell the menu opened from. The toggle stays for a reader comparing
      the engine's two readings.

      **The ordering, settled 2026-09-03.** The archive's top suggestion held
      the first line and was the best single thing in the menu — 0.230 at rank
      one on its own. It is a string neighbour: it says a reading is *spelled
      like* a name these ships carried and knows nothing about the ink. Where
      it is only distantly similar and one stroke rule reaches a name the
      archive has read, the stroke reading now takes the line, because it
      accounts for the marks on the page. Swept over the 217 badly-read words:

      | archive's guess keeps the line above | @1 |
      |---|---|
      | (as it shipped) | 0.235 |
      | 0.70 | 0.240 |
      | 0.75 | 0.249 |
      | **0.80** | **0.267** |
      | 0.90 | 0.240 |

      Seven more words right on the first line, and @3, @5 and @10 unmoved —
      the same names found, in a better order, which is what a re-ranking
      should look like. Past 0.80 it starts displacing suggestions that were
      right. `gazetteer.PROMOTE`.

      Still to do: drop the rules that keep scoring nothing once the pages
      their examples live on are scorable — measured again 2026-09-03,
      `only:abbreviation` is still 0 of 217 and `only:minims` is 1.
- [x] **T8 — Ask the right question when marking** (§5, `doubtful`), measured
      by the new `scripts/bench_check.py` over 149 rows paired with a hand
      reading, 121 of them read wrong:

      | reason | catches the bad rows | stops on a good one |
      |---|---|---|
      | score (engine unsure) | 0.595 | 0.036 |
      | inferido (mark inherited) | 0.314 | 0.036 |
      | desconhecido (nothing like a name here) | 0.000 | 0.000 |
      | **quase (one stroke from a name)** | **0.587** | **0.214** |
      | the three there were | 0.702 | 0.071 |
      | all four | 0.868 | 0.250 |

      So the new reason is worth seventeen points of the badly-read rows and
      costs stopping a person on one correctly-read row in five — which the
      legend now says, because the bar means *look here first* and never
      *this is wrong*. `desconhecido` catches nothing on these pages and is
      kept: it is the reason that fires on a name the archive has never seen,
      and these six pages are ones it mostly has.
- [x] **T9 — Display** (§6, §6b), done 2026-08-28, four assertions in the
      browser self-test (91 now pass in both browsers).
      - The repetition mark is shown as a mark: `"Maria` is a mark and a name,
        not a name beginning with a quote. The record is untouched — that is
        what the page says.
      - Names are shown capitalised, particles kept lower case (`da`, `de`,
        `dos`, `della`, `van`, `von`, `y`…). Display only: `nameText` still
        returns `alfieri`, and what is stored is what was read.
      - The demo document says, in the interface, that its nationality, age,
        profession and other columns were typed by a person. It is the only
        document in the app with them filled, and without the note the next
        dossier reads as a tool that stopped working.
      - A value a person typed into one of the other columns now says so — a
        dotted underline and *digitado por uma pessoa* — which is what the two
        rows of BS.ENT.013942 needed. The engine has never written those
        columns, so anything in them is somebody's typing.
- [ ] **T10 — The other columns** (§4), cheapest first: age, sex, class, then
      nationality, profession, port against gazetteers.
      - [x] **The columns are measured.** The plan said the column edges were
            already there; they were not — `columns()` measured the name and
            the ordinal beside it and dropped the rest of the heading line on
            the floor. It now measures every column the page prints a heading
            for, off the same fragments at no extra cost:
            *Nacionalidade, Idade, Estado civil, Profissão, Procedencia,
            Destino, Classe, Observações* on BS.ENT.013947 p3. An edge runs
            halfway to the next heading, because a heading is narrower than its
            column. `TableGeometry.normalized_columns()` offers them by the
            field names the app already uses, and they are stored under
            `all_columns` — `columns` keeps meaning the name column, as every
            record on disk already does. A page whose heading line has nothing
            but the name stores no `all_columns` at all, which is the honest
            answer, and the columns travel with the name column to the pages of
            a dossier that print no headings.
            Run against a real page rather than a fixture — BS.ENT.017397 p2,
            the typewritten one — it measures eight: *nome, numero,
            nacionalidade, estado, profissao, procedencia, classe,
            observacoes*. **Not `idade`**, on a printing that spells it
            *Edade*. The boxes for *Edade* and *Sexo* are found and come back
            **empty** — two narrow words on a printing the recogniser reads
            everywhere else — so they are named by their place in the line,
            which these forms print in one order, and marked `named_by:
            "ordem"` against `"impresso"` for the ones that were read. Only
            where the order leaves exactly as many names as there are unread
            boxes: three boxes where two names fit is not a column anybody can
            name. That page now measures ten.
      - [x] **A first look at reading one.** `cells_from_bands` over
            BS.ENT.017397 p2 with the real recogniser: the nationality column
            comes back as `ISPAGNIA`, `ESPANOIY`, `SEANOL`, `RASIERAL` against
            *ESPANHOLA*, *BRASILEIRA* — the shape of a column that can be read
            and snapped to a closed vocabulary. The age column comes back as
            `_`, `1`, `一`: its heading is 2.8% of the sheet wide and the
            figures are not under it, so the edge halfway to the next heading
            is the wrong rule for a narrow heading over a wide column. **No
            column reading ships on this**: `scripts/bench_columns.py` and a
            per-column truth page come first, and the hand transcription of
            this very page is the truth for the typed half of it.
      - [ ] Read them: crop each band × column, recognise, and store the
            reading beside the snapped value, never instead of it.
            `engine_paddle.cells_from_bands` is the cutting half, built and
            tested the way `rows_from_bands` was — the recogniser injected, so
            it is testable without the model, a short answer padded with nulls
            rather than shifting later rows up one, and a column the page never
            measured returning nothing at all rather than a guessed edge. What
            is left is calling it from `transcribe_page` and deciding what a
            cell costs: a page is 40 bands × 8 columns, and the recogniser is
            twenty seconds a page for one column.
      - [x] `scripts/bench_columns.py`, scored against BS.ENT.017397 p2 — the
            typewritten page somebody transcribed by hand, 26 rows with a value
            in every column. The first numbers, and they are bad, which is the
            point of having them:

            | column | rows | exact | mean CER | what it reads |
            |---|---|---|---|---|
            | nacionalidade | 26 | 0.000 | 0.730 | `ISPAGNIA` for *ESPANHOLA* |
            | idade | 22 | 0.000 | 0.977 | `` and `一` for *23*, *37* |
            | sexo | 26 | 0.000 | 1.000 | `十`, `二I` for *F*, *M* |
            | estado | 26 | 0.077 | 0.593 | `SOLT`, `SOTC` for *SOLT* |
            | profissao | 22 | 0.000 | 0.710 | `onncio` for *comercio* |
            | procedencia | 26 | 0.000 | 0.974 | `POENOS AI` for *BUENOS AIRES* |
            | classe | 26 | 0.115 | 0.885 | `1`, then nothing |

            Two separate faults, and the bench separates them: the columns that
            read *something* wrong (nacionalidade, estado, profissao) are a
            recogniser and vocabulary problem, and the ones that read *nothing*
            (idade, sexo, classe, procedencia) are a crop problem — a narrow
            heading over a wide column, so halfway-to-the-next-heading puts the
            edge in the wrong place. The crop comes first: a snapped value from
            a closed vocabulary cannot rescue a cell that was never cut.
            Tried and rejected, so nobody tries it twice: `--prep upscale2`,
            doubling every cell before reading it. Nationality 0.730 → 0.723,
            civil state 0.593 → 0.569, profession 0.710 → 0.691, age and sex
            unmoved, class slightly worse. The same answer the name column gave
            to the same idea — the picture is not what is wrong.
            A cursive page still needs its own truth file; a number measured on
            typescript must never be quoted as if it covered the hand.
      - [x] **The crop was not what was wrong.** The line above says the four
            columns that read *nothing* are a crop problem — a narrow heading
            putting the edge in the wrong place. Measured, they are not, and
            the four fail for three different reasons.
            The columns were drawn over the page and looked at:
            *Idade* is measured 0.388–0.415 of the sheet and the figures the
            detector finds sit at 0.388–0.413; *Sexo* is measured 0.415–0.444
            against ink at 0.417–0.442. Both crops hold their writing, and the
            same digits read back as `二`, `7`, `1二` off the detector's own
            tight boxes. **Idade and sexo are the recogniser's floor on a cell
            of one or two characters**, not a crop: at 98 px wide and 26 rows
            deep, nothing read right under any cutting tried.
            **Procedencia and classe are mostly blank on the page.** The clerk
            wrote *BUENOS AIRES* on the first row of the sheet and left the
            rest of the column empty; the hand transcription writes it against
            all 26 rows, because that is what the page means. Scoring a blank
            cell against an expanded truth measures the transcriber, not the
            engine — those two want the repetition rule the names already have
            (T6) before any number about them means anything.
            Tried and rejected, so nobody tries them twice:
            *snapping the column edges to the gutters between the columns of
            ink* — the detector merges neighbouring cells into one box often
            enough that the body has no white column left to find between
            0.29 and 0.68 of the sheet, and the one edge it did move (classe)
            read worse; and *tightening each cell to its own ink and scaling it
            to a standard height*, the usual answer to a small crop, which
            moved idade 0/22 → 0/22 and sexo 0/26 → 1/26.
            What did move: **a cell is cut at its band and its column exactly**,
            where it used to be padded out by `PAD_PX` like a name. A name is
            300 px wide and carries the rules at its edges; a cell of 98 px
            hands the recogniser three printed lines around two digits. Swept
            over 0.0 / 0.08 / 0.12 / 0.20 of the cell trimmed off each edge,
            cutting at the band is best in every column and every trim past it
            is worse — the rules cost less than the writing a trim takes with
            them. `scripts/bench_columns.py --inset` is the knob that measured
            it and stays for the cursive page.

            | column | padded out, as it was | cut at the band |
            |---|---|---|
            | nacionalidade | 0.730 | **0.716** |
            | idade | 0.977 | 0.977 |
            | sexo | 1.000 | 1.000 |
            | estado | 0.593 | **0.577** |
            | profissao | 0.710 | **0.661** |
            | procedencia | 0.974 | 0.969 |
            | classe | 0.885 | 0.904 |

            So the order of the work changes. The three columns that read
            something wrong — nacionalidade 0.716, estado 0.577, profissao
            0.661 — are a closed vocabulary away from being useful
            (`SEAGNOLA`, `ISPAGNOLA`, `LASIERCL` all reach *ESPANHOLA* and
            *BRASILEIRO* by a fuzzy match), and that is the next piece of work.
            Idade and sexo need a different reader, which is a spike and not a
            crop. Procedencia and classe need the repetition rule first.
      - [x] **The closed vocabularies**, `desembarque/vocab.py` and
            `data/column_vocab.json` — the words these forms print in each
            column, written by hand and making the same claim the language-name
            file makes: *these forms print this word*, never *this archive has
            been read to contain it*. A snapped word is kept beside the reading
            as `value` and `snap`, and `text` is never touched, which is the
            gazetteer's rule about suggestions applied to a column.
            Measured on BS.ENT.017397 p2, against the 26 rows read by hand:

            | column | rows | with ink | right as read | snapped | of those, right |
            |---|---|---|---|---|---|
            | estado | 26 | 25 | 1 | 13 | **12** |
            | profissao | 22 | 15 | 0 | 8 | **7** |
            | nacionalidade | 26 | 19 | 0 | 5 | **3** |
            | procedencia | 26 | **3** | 0 | 1 | 1 |
            | classe | 26 | 18 | 2 | 6 | 2 |

            *With ink* is the column the bench gained today, and it is the one
            that stops a number being misread: the clerk wrote the port on
            three rows of twenty-six and the hand transcription writes it on
            all of them, so *procedencia 0.969* is a fact about the
            transcriber's expansion. Blank is not a repetition on these forms —
            blank means unknown and a ditto mark means the value above — so
            nothing is inherited down a column.

            So the civil state goes from one row right in twenty-six to twelve,
            and the profession from none in twenty-two to seven. Nothing is
            invented on a blank cell: an empty reading snaps to nothing, and
            the columns that read nothing at all (idade, sexo) snap nothing.
            The floor is per column, and measured — 0.55 / 0.62 / 0.70 swept
            with `bench_columns.py --floor`. Civil state and profession are
            short lists of words that look like nothing else and want 0.55;
            nationality is fifty long words sharing their endings, where `BIG`
            reaches INGLEZ as easily as BELGICA, and at 0.55 it snaps ten rows
            to get four right against five snapped for three at 0.70. Also
            measured and taken out: listing an abbreviation as a word of its
            own (`CAS`) won `cau` away from CASADO, which is what the page
            says; a short reading is compared with the head of the word
            instead, so `cau` reaches CASADO and `SOLT` reaches SOLT.
      - [x] **An empty cell is not read.** The name column has skipped its
            empty bands since the rows were cut from the comb, and a cell is
            smaller, emptier and eight times as numerous — but `has_ink` was
            written for a strip 300 px wide, where the printed rules at the
            edges are lost. On a cell 98 px wide those two rules are four
            columns of solid ink and every blank cell on the page passed as
            written, which is where `一`, `1` and `十` in an empty cell come
            from. `has_ink(im, margin)` now ignores the outer 12% of a cell.
            Measured on BS.ENT.017397 p2, a dense page — 26 of its 31 rows
            carry a passenger — 243 cells were read where 216 are now, and the
            column it changes is the one that was blank all along:
            *Procedencia*, written once at the top of the sheet, went from 29
            cells read to 10. On a sheet printed with thirty rows and carrying
            three, which is the commoner page, the saving is most of the page.
            Tried and rejected, measured on the same readings without running
            the recogniser again: **the stroke rules on the way in**, running
            each reading through `strokes.variants` and matching every variant
            against the list. It buys recall with precision, which is the wrong
            trade for a value shown beside a name — civil state 12 right / 1
            wrong becomes 14 / 3, profession 7 / 1 becomes 9 / 6, and
            nationality gets no more right answers and twice the wrong ones.
            And **a floor of 0.50**: civil state 15 / 3 and profession 9 / 3,
            more right answers than 0.55 buys and three times the wrong ones.
            The stroke rules stay where they belong, in the menu a person opens
            on a word, where a wrong guess costs a line of a list and not a
            value on a record.
      - [x] **The wiring**, done 2026-08-29 evening. `transcribe_page` called
            `cells_from_bands` behind `self.columns`, which defaults to none,
            and nothing ever passed a column: the measurement existed and no
            page the app read came back with a cell. `serve.columns_wanted`
            asks for `READABLE_COLUMNS` and refuses idade and sexo rather than
            paying for them; `DESEMBARQUE_COLUMNS=none` turns it off.
            **What a cell costs, measured end to end** on BS.ENT.017397 p2
            rather than estimated from the crop count: 16.9 s a page becomes
            22.9 s, a third more and not the double 216 crops suggested,
            because a blank cell is not read. 59 cells read on 31 rows, 26
            snapped: `SEAGNOLA` → ESPANHOLA, `conercio` → COMERCIO, `cau` →
            CASADO.
      - [x] **On screen** (§6b, and what Allan asked for). A cell the engine
            read is shown as read and never as somebody's typing; a reading
            carried to a printed word is tinted, marked `⌇`, and says on hover
            what was read and how close. Four browser assertions.
- [x] **T12 — Contrast on a faint page** (asked 2026-08-29). *Measured, and
      not wired.* `scripts/spike_faint.py` puts four liftings in front of the
      detector on the pages that read nothing. Autocontrast and a 2nd/98th
      percentile stretch each move the box count by one — these scans already
      use their range end to end, grey ink on grey paper with the black point
      already black. Equalising moves: OL.PRJ.17851 p2 goes from 32 boxes and
      no rows to 71 and 29. But counted with the engine actually running, it
      never fires — that page already comes back with 45 bands and 23 names
      from the ruled fallback — and the twelve records holding no rows all
      still read `unknown` and print no heading line, because they are covers
      and PARTEs and not lists. `engine_paddle.lift` is written and tested and
      deliberately not called; the comment in `_printed_table` says what would
      have to be true first. Kept from it: `retry_unknown.py --again`, and a
      page stored as a `list` with no rows now counts as wanting a reading.
      Separately, and already known: contrast does nothing for *reading* a crop
      once it is cut — `data/spike_prep.json`, 0.362 against 0.361.
- [x] **T11 — The language prior** (§7), built and measured 2026-08-29.
      `data/language_names.json` gains `by_language`: all 259 names placed, a
      name in every language that uses it, and the overlap kept — MARIA is all
      three, COSTA is Portuguese and Italian. `vocab.language_for` reads a
      nationality as a language and only where there is a list behind it: the
      Spanish-speaking republics are Spanish, *Suisso* is deliberately absent,
      and a Japanese or Polish passenger gets the menu the rules already build.
      Asked of the snapped word, never of the reading. `menu_for` stably
      partitions the menu it had already ordered, so every measurement behind
      that order survives inside each half; it orders and never filters,
      because half these families carry a Spanish surname on an Italian
      passport. The review screen sends the row's nationality with the word.

      **It cannot be measured as it will be used, and that is the finding.**
      `scripts/read_nationalities.py` reads the nationality column of the six
      hand-read pages: 48 cells carry ink, they come back `tiuin`, `geil`,
      `Bueclibme`, `一`, and **none of the 48 snaps to a word these forms
      print**. The column is legible on typescript and is not legible in this
      cursive hand, which is the same wall idade and sexo hit. So the prior has
      no input on the pages the menu is scored over.

      What is measurable is its **ceiling**: score the menu with the language
      *given* rather than read. If knowing it for certain buys nothing, reading
      it off a cursive column buys less.

      | menu | words | found | @1 | @3 | @5 | @10 |
      |---|---|---|---|---|---|---|
      | guesses, as they ship | 217 | 82 | 0.235 | 0.350 | 0.369 | 0.378 |
      | with Italian given | 217 | 82 | **0.263** | 0.355 | 0.369 | 0.378 |
      | with Spanish given | 217 | 82 | **0.263** | 0.350 | 0.369 | 0.378 |
      | with both given | 217 | 82 | **0.263** | 0.350 | 0.369 | 0.378 |

      Six more words right at the first line, of 217, and nothing past rank
      three — which is what a re-ranking should look like: the same 82 names
      found, in a better order. Italian, Spanish and both give the same number,
      because the names the prior lifts are mostly in more than one of the
      lists.
      So it ships — it costs nothing at query time and fires wherever the
      column reads, which today means typewritten pages — and the number above
      is a ceiling, not a claim about a cursive page.
      **Still to do:** a truth page that has both hand-read names and a legible
      nationality column, which is the only way to measure this as used. The
      hand transcription of BS.ENT.017397 p2 is one half of it and has no
      stored engine reading of its names to pair against.


---

## Is the recogniser replaceable? (2026-09-03)

`spike_htr.py` asked this in August, tried the two Microsoft IAM models, and
answered no. It never tried a model trained on an *archive's* hand, which is a
different prior entirely — IAM is modern English on lined paper. Over the same
crops, the same truth and the same CER:

| recogniser | CER | seconds a row |
|---|---|---|
| **the engine that ships (PaddleOCR)** | **0.205** | fast |
| agomberto/trocr-large-handwritten-fr | 0.257 | 6.6 |
| Riksarkivet/trocr-base-handwritten-hist-swe-2 | 0.338 | 2.0 |
| microsoft/trocr-large-handwritten | 0.607 | 8.1 |
| microsoft/trocr-base-handwritten | 0.785 | 7.7 |

So the archival prior is worth a third of the character error against the
English one, and **the engine still wins.** Nothing here replaces it.

`Kansallisarkisto/multicentury-htr-model` ships a processor cut for line
images beside an encoder that wants squares and threw
`Input image size (192*1024) doesn't match model (384*384)`; `spike_htr.py`
now takes the size from the encoder, so it can be scored next time.

**But an average hides the shape.** The engine reads `Guudo Camtadore` where
the French model reads `Guiso Cantadore`; both are wrong and they are wrong
differently, and a searcher needs only one of them to be reachable. That is
the question `spike_second_opinion.py` and `bench_search.py --second-opinion`
ask: put the second recogniser's reading in `alts`, beside the engine's own
second reading, as a reading and not a guess.

**First result, and why it is not the answer.** Reading the six hand-read
pages a second time moved the matrix a long way — 87/97/105 to 101/110/119 by
name alone, 118/123/129 to 122/127/133 with the crossing named, on 78 rows of
142. It is inflated and must not be quoted: only the rows being searched for
were read twice, and none of the 32,000 rows competing with them were. The
competition is diffuse — 588 pages hold the rows that outrank the truth rows,
and the top 14 of them only 17% — so patching the competitors is not
available either.

**The fair measurement** is a subcorpus read twice in full, targets and
competitors alike: 15 dossiers, 1,038 indexed rows, read again by the Swedish
model (2 s a row against the French one's 6.6). 62 of its 65 pages read; 294
rows paired to a band, which is 28% of the corpus and the number to improve
next — the sidecar is cut by `name_strip` and the index by the engine's own
row cutting, and where those disagree the row keeps only one reading.

| | top 5 | top 10 | top 20 |
|---|---|---|---|
| by name alone | 121 → **126** | 125 → **129** | 127 → **129** |
| naming the crossing | 122 → 122 | 130 → 130 | 133 → 133 |

**Counted with the guesses**, which is the finding. Put in as a reading it
gained the same five names and cost three of the top five to a searcher who
named the crossing — the same regression, through the same edit-distance
pass, as the stroke spellings. A recogniser did read it off the page, but it
is a recogniser that is worse on average than the one that ships (0.338
against 0.205), so it is weaker evidence, and weighting it below every
reading and keeping it out of the crossing pass costs nothing and returns
those three rows.

**And then the coverage was fixed, and the gain went away.** 28% is not a
sample, it is a selection: the pages that paired were the hand-read ones,
which are cut cleanly, and those are the pages holding every row the bench
searches for. So the rows being looked for were still being read twice more
often than the rows competing with them.

`export_bands.py` takes the crops from the engine itself, through the
recogniser hook, named by the row number the engine gave them; `read_bands.py`
reads those same images with the second model. Pairing is then engine against
engine — median similarity 1.00 over 848 rows, mean 0.86 — and coverage goes
from 28% to **82%**:

| | top 5 | top 10 | top 20 |
|---|---|---|---|
| by name alone | 121 → **120** | 125 → **123** | 127 → **128** |
| naming the crossing | 122 → 122 | 130 → 130 | 133 → 133 |

Nothing. The five names were an artefact of who was being read twice.

It is not that the second reading says nothing: it differs from the engine on
every one of the 848 rows, and on **69 of them (8%) it spells a name from the
archive or the language lists that the engine's reading missed**. That is a
real reading of real ink. It does not make anybody easier to find, because
every row competing with them gained the same thing, and a name that 8% more
of the corpus now matches is a name that returns 8% more rows.

**And then the null turned out to be unfair too, later the same day.**
`spike_finetune.py` scored the same Swedish model on the same six rows before
training anything and got **CER 0.892**, where `spike_htr.py` had measured
**0.338** on that page. Same model, same page, same truth — different crops.

`spike_htr` cuts its rows out of `name_strip`: the deskewed name column, rows
taken off it, each upscaled. `export_bands` hands over the engine's own
*carved* crops, which cut each band to its own ink and nobody else's. TrOCR
reads the carved ones far worse, and it is not the scale — upscaling them to
height 64 moves 0.892 to 0.868 and no further.

So the 82%-coverage measurement fed the second model input it reads at CER
~0.87 rather than 0.257–0.338, and **it is not a fair test of the second
opinion**. Neither number stands: the 28% one was biased by which rows paired,
and the 82% one by what the crops look like.

**Nothing was shipped on the strength of either**, which is the one piece of
luck here. What is true and stands:

* No pretrained recogniser beats the engine on the strip crops, where they
  were all scored fairly (0.257 at best against 0.205).
* `export_bands.py` and `read_bands.py` do key a second reading to the rows
  already in the index, at 82% coverage, which is the plumbing the question
  needs — they are just feeding it the wrong pictures.

**What would settle it**, and is the first thing to do next: give
`export_bands.py` the strip crop for each row as well as the carved one — both
come from the same `analyze(page)`, so the row number is available on both
sides — and run the 82%-coverage measurement again on those. Until then the
second opinion is unanswered, not refused, and the 18 hours are still not
spent.

The fine-tune spike stands on the same bad crops and its `before` number
should be ignored for the same reason.


---

## The corpus is a fortnight behind the reader, and the stamp cannot see it
(found 2026-09-04)

Measuring the second opinion turned this up sideways. Over the 15-dossier
subcorpus, what the engine reads **today** agrees with what the record holds on
**100% of the hand-read pages and 58% of the rest**. Whole dossiers now read as
names where the record holds `''`, `w`, `D10` — and it is not a numbering
drift, it is a better reading: `05edf625` p5 comes back with 42 named rows
where the record has 46 rows of noise.

The record dates say why. 431 of the 660 records were read on 2026-08-21 and
162 more on 08-28, and since 08-20 there have been **27 commits to
`engine_paddle`, `rowcut` and `tablegrid`** — the carving, the printed-table
geometry, the column measurement, the derule pass. Every record carries
`read_schema: 18`, which is current, because that stamp is bumped when the
*parse* changes and the reader's improvements do not touch it. So the corpus
looks fresh and is not, and nothing in the system says so.

What this costs:

* **The search is worse than the engine is.** The names those dossiers now read
  are not in the index, so nobody can find them; the improvements shipped in
  the last fortnight reach only documents opened since.
* **Every measurement pairing a fresh reading to the stored corpus is
  biased**, in the direction of whichever pages happen to have been re-read —
  which is exactly the second-opinion fault, twice over now.

Three ways out, cheapest first:

1. **Re-read the corpus.** Measured at 34 hours in August, and it is a
   background pass that resumes. It is the only thing that makes the index
   agree with the engine.
2. **Stamp the read.** A version for the reading path, bumped when the crop or
   the geometry changes, so `batch.py` knows which records are behind and can
   re-read them in the background instead of all of them. This is the same
   guard `read_schema` was introduced to be, pointed at the half of the
   pipeline that actually moved.
3. **Measure the drift rather than assume it.** `export_bands.py
   --write-records` now reads a slice and writes what it read; comparing that
   with the stored rows is the number above, and it can be taken over any
   slice at any time.

Not decided here: (1) is Allan's call, since it is a day of the machine and
the corpus is his.

---

## 155 crops are not enough, and 3 epochs are worse than none (2026-09-04)

The training set is built right now — the crop is the ink the engine read, the
label is what a person said, and the pairing has been fixed — so the question
it was built for could finally be asked honestly. `spike_finetune.py` over the
strip crops, `Riksarkivet/trocr-base-handwritten-hist-swe-2`:

| held out | rows | train | settings | before | after |
|---|---|---|---|---|---|
| BS_ENT_014541-p2 | 6 | 149 | 3 epochs, lr 5e-5 | 0.340 | **0.451** |
| BS_ENT_013947-p3 | 48 | 107 | 1 epoch, lr 2e-5 | 0.606 | **0.605** |

Three epochs make it **worse**, and the training loss says why: 1.708 → 0.622
→ 0.314, a model learning the 149 crops by heart. What it learns is the
archive's *vocabulary* rather than its hands — `GUIDO CONTADORE` reads as
`Gaudi Santos` after training where it read `Gusti Cantadore.` before, and
`A. VIEIRA MIRANDA` collapses to `Santa`. One epoch at a lower rate over a
48-row held-out page moves nothing at all: 0.606 → 0.605.

So the answer to *"is 142 enough to say?"* is **no, and it is not close** —
the honest number to quote is that a set this size cannot move a pretrained
recogniser off its prior, and a search over epochs and rates would be tuning
noise on six rows. The `before` numbers are worth keeping, though: 0.340 on the
reference page is what this model reads the plain band at with labels that are
right, against the 0.892 quoted last week, and the engine reads that page at
0.205.

What this changes about the direction: nothing about *whether* an archive-
trained recogniser is the lever — it is still the only one left — but the
first cost is now known. It wants labels in the hundreds at least, which is
`training_set.py --records` and people using the review screen, not another
afternoon of spikes.

---

## The second opinion, asked with the right pictures (2026-09-04)

The plumbing was the easy half: `export_bands.py` writes the carved crop and
the plain band of every row, `read_bands.py --variant strip --refine 64` reads
whichever is asked for, and the bench understands a sidecar keyed by row
number. The subcorpus — 15 dossiers, 70 pages, 1,865 rows with a reading — was
cut and read again by `Riksarkivet/trocr-base-handwritten-hist-swe-2`, which
is 2.5 hours of engine and 2.5 hours of TrOCR on this machine.

**The crops do differ, and by far less than last week's numbers said.** Over
the 152 labelled rows, same model, same rows, same labels:

| crop | second opinion CER | median | engine on the same rows |
|---|---|---|---|
| carved (the engine's own) | 0.609 | 0.538 | 0.365 |
| plain band, trimmed and upscaled | **0.567** | 0.500 | 0.365 |

Last week this gap was quoted as **0.892 against 0.338**, and that was almost
entirely the labelling fault above: the 0.892 was six rows of a page whose
labels had slid three rows down. On today's labels the same page reads 0.515
carved and 0.368 on the band. So the carved crop *is* the worse picture for a
pretrained model — it keeps 71% of the band's height at the median, trimmed to
the ink, and TrOCR was trained on lines with air around them — but it is worth
about four points of character error, not fifty-five.

**And the engine still wins**, 0.365 against 0.567, on the crops that suit the
challenger best. That has now been true of six pretrained models.

**What it is worth to a searcher.** The subcorpus's 727 pairable rows were put
into the index beside the engine's own reading, and the matrix run again over
the whole corpus, 138 hand-read names against 32,322 rows:

| | top 5 | top 10 | top 20 | with the crossing named |
|---|---|---|---|---|
| the index as it ships | 87 | 97 | 105 | 118 / 123 / 129 |
| second reading, as a reading | **93** | **105** | **113** | 115 / 119 / 126 |
| second reading, counted with the guesses | 91 | 104 | 111 | 118 / 123 / 129 |

Counted as a reading it finds six to eight more names typed alone and **costs
three to four when the crossing is named** — the same trade, through the same
edit-distance pass, as the stroke spellings. **Counted with the guesses it
gains four to seven and costs nothing**, which is where it belongs: a
recogniser worse on average than the one that ships is weaker evidence, so it
is weighted below every reading and kept out of the pass that runs when
somebody names the ship.

On the reading itself: it differs from the engine on every row, is closer to
the truth on 35 of 152, and on **30 of 152 it spells a name the archive has
read or its languages carry where the engine's reading spells none**. That is
what a second opinion can do for a searcher, and it is the mechanism behind
the five names.

### Why this is still not the number to ship on

The sidecar's row numbers come from the reading taken the day the crops were
cut. The index's come from whenever each dossier was last read, and **the
engine has moved on while the corpus has not**: across the subcorpus today's
reading agrees with the stored one on **100% of the hand-read pages and 58% of
the rest**. Whole dossiers now read as names where the record holds `''`, `w`,
`D10`.

That is the bias of the 28%-coverage run wearing another hat — the rows being
searched for keep their second reading, the rows competing with them lose it —
and it runs in favour of the gain above. `--second-bands` refuses a row whose
two readings disagree — 97 of 1,213 — rather than pasting a reading onto a row
that no longer holds the same name. The comparison has to know what it is
comparing: the export carries what the recogniser said and the index carries
what the row is *searched by*, which for a row written with a repetition mark
is the words above it followed by its own, so the reading is tried against the
tail of the indexed text as well. Before that it refused 486 rows, four
fifths of them repetition marks.

But refusing is not fairness: it leaves the targets read twice and the
competitors not.

**What settles it, and it is now one flag.** `export_bands.py --write-records`
writes what it read as it cuts, so the pass that produces the crops also
produces a corpus that agrees with them. Copy the cache, write the fifteen
refreshed records over the copy, point the bench at that, and the same three
rows of the table above mean what they say. Until then the honest statement is:
*counted as a guess it is worth somewhere between nothing and seven names of
138, measured with the odds in its favour.*

---

## The labels were partly somebody else's (2026-09-04)

Fixing the crops turned up something underneath them. A hand-read page comes
in two shapes: `rows`, keyed by the row numbers somebody wrote names against,
and `names`, a run read straight down the column. The run has to be put
against the rows the page was cut into, and every instrument here did it a
different way.

* **Counting from `first_row` goes stale.** `data/truth/BS_ENT_014541-p2.json`
  records 4, because the comb that read it in July put those six passengers on
  rows four to nine; measured from the printing they are rows one to six. The
  menu bench counted from it and scored six names against the rows below them.
* **A single best-fit offset drifts.** `bench_rec.align` finds the offset that
  fits best, which cures the stale number and then walks off the first row that
  carries no reading. BS_ENT_015061-p6 has such rows, and its 42 truth names
  were scoring **CER above 1 for the engine's own stored reading** — a reading
  cannot be worse than empty, so that number was never about the recogniser.
  The search bench and the training set both used this.

`desembarque.truthset.aligned` places a run monotonically: name by name, in
order, paying for each mismatch and free to skip a row nobody wrote a name
against, which is what a person comparing the two lists does. Skipping a row is
free because a page is mostly rows the truth says nothing about; skipping a
*name* costs a whole name, because every name in the run is on the page
somewhere. The menu bench, the search bench and the training set all pair
through it now, so there is one pairing in the repository rather than three.

What moved:

| | before | after |
|---|---|---|
| BS_ENT_015061-p6, engine CER over 42 rows | 1.048 | **0.349** |
| BS_ENT_014541-p2, rows in the labelled set | 3 | **6** |
| hand-read names the search bench scores | 142 | 138 |
| labelled crops | 152 | **155** |

The four names the search bench lost sit on no row the engine read; counting
them against a neighbour's row was the only way they were ever counted. The
matrix itself is unmoved at 87/97/105 by name alone and 118/123/129 with the
crossing named, so the published retrieval numbers stand — but **every CER
taken on the training set before today was taken on labels that were partly
somebody else's**, including the fine-tune spike's `before`.

---

## What to do next, after 2026-09-03

Today closed a direction, so this says plainly what is left.

**The engine is the ceiling, and no pretrained model lifts it.** Five were
scored; the best loses to it. Everything shipped since August works *around* a
reading that is one or two letters wrong — the menu offers the reader the
right name, the index reaches it for a searcher — and each of those is worth a
few names of 142. They are worth having and they are not the answer.

**The one lever left is a recogniser trained on this archive's own hands**,
which is what `spike_htr.py` concluded in August and what today's numbers
confirm from the other side. The work that leads there, cheapest first:

1. **Keep the corrections.** *Done 2026-09-04, and nothing is kept.* Every
   time somebody retypes a row on the review screen that is a labelled crop —
   the image the engine read and the name a person says it is — and the plan
   here was to save the crop at the moment they type. That turned out to be
   the expensive way round: since T4 every page stores the geometry its rows
   were cut from, and a crop is a pure function of that geometry and the page
   image, so it can be cut again whenever anybody asks. `desembarque.bandcrops`
   does the cutting with the engine's own `carved_crops` and `band_boxes`, and
   a unit test holds it to being byte-for-byte the crop the engine read —
   a pair whose picture is the neighbouring row is a mislabelled pair.
   `training_set.py --records` then harvests every correction in the corpus,
   including ones made months ago, with nothing stored at save time and no
   recogniser run.

   There are **four** of them today, all made by choosing one of the offered
   readings rather than typing. Cutting their crops immediately earned its
   keep: the ink of one reads *Raymundo Cassaudii*, which is what somebody
   typed on two other records of the same page, and the label on it says
   *Nayomgo Cassaudi*. A chosen alternative is a person's word about the row
   and it is not always right, so the set records **how** each label was
   made — `typed`, `chosen`, `hand-read` — and a row merely marked verified is
   not a label at all unless `--verified` asks for it, since the person may
   have been checking another column.
2. **Count what a training set would need.** 142 hand-read names exist today.
   Fine-tuning a TrOCR base on a few hundred crops of one archive's hands is
   the smallest experiment that could beat 0.205, and the honest first step is
   to measure how far 142 gets before asking anyone to label more.
3. **Then fine-tune, and score it the same way as everything else** — the same
   crops, the same truth, `bench_search.py --matrix` and `bench_menu.py`, and
   `read_bands.py` will put it in front of the ink without any new plumbing.

**Still open from before, and unaffected by any of this:** T3's
`bench_columns.py` and per-column truth, and T10's other columns — both of
which want a cursive page whose columns read at all, which T11 measured and
found they do not.
---

## Did a clerk write these names in Cyrillic shapes? (asked 2026-09-03)

Allan watched somebody write Cyrillic and recognised shapes he had seen in
these manifests — letterforms he does not remember being taught — and asked
whether a clerk whose first script was Cyrillic carried it into portuary
work. It is a good question because it is a testable one: it predicts
*particular* misreadings, since a cursive `и` is shaped like a Latin u, `т`
like an m, `н` like an h, `р` like a p, `в` like a b, `г` like an r.

**Asked of the errors.** Over the 142 hand-read names, 2,169 truth characters
and 210 single-letter substitutions, the confusions those shapes predict are
**4 of 210 (2%)**, and no dossier carries more than 4% of them. What the hand
is actually read as: `L→T` 16, `A→O` 11, `M→E` 11, `Q→G` 8, `R→I` 5 — ordinary
Latin cursive.

**Asked of a recogniser.** Two Cyrillic-trained models were put in front of
exactly the crops the engine reads (`export_bands.py`, `read_bands.py`) and
their output carried back to Latin two ways — phonetically, if the clerk wrote
Cyrillic letters for the sounds, and by shape, if the clerk wrote Latin in
Cyrillic forms. Over 601 rows of 8 dossiers, `kazars24/trocr-base-handwritten-ru`
put a name from the archive or the language lists on **0 rows phonetically and
2 by shape**, against the engine's 313 on the same rows.
`Kansallisarkisto/cyrillic-htr-model`, trained on historical hands, behaves
the same way on a 66-row sample.

Both collapse in the same telling way: mean output length 7 and 9 characters
against the engine's ~18, and what comes out is common Russian words —
`это`, `от`, `на` — rather than letter-faithful nonsense. That is what a
recogniser does with a script it was not trained on.

**But this half has to be run again.** Those readings were taken from the
engine's *carved* crops, which a Latin TrOCR reads at CER 0.892 where it reads
the deskewed strip at 0.338 — see the second-opinion note above. A recogniser
handed pictures it cannot read says nothing about the script in them. The
confusion matrix above is unaffected, because it reads stored readings against
the truth and never touches a crop.

**What would still change this.** Neither test can see the page Allan was
looking at. The confusion matrix covers the 4 dossiers that have hand-read
truth and the recogniser test the 15 of the second-opinion subcorpus, and
none of those was chosen for looking Cyrillic. If he can name the dossier or
the year, the same instruments answer it directly on that hand — the crops
are exported per page and the analysis is a minute's work.

Kept from it either way: `strokes.MINIMS` already absorbs the one carryover
that would matter most, because a Cyrillic `и` is a minim shape and the
re-cut rule treats I, U, V, N, R, M and W as the same ink divided differently.
---

## What the reference set says to do next (2026-08-29 evening)

The plan above has no open task. `scripts/bench_refset.py` gives the baseline,
and two of its six tables read essentially no word this archive has ever seen.
Both were looked at rather than guessed about, and **neither is a geometry
failure** — the rows are cut, the writing is in them, and the recogniser is
what fails:

* **OL.PRJ.17347 p16**, the page whose stored name column was the ordinal
  strip. Measured fresh it reads 28 of 29 rows and the names are there under
  the damage — `MattenceSuireppe`, `MarcelloNittoms`, `MerleltaForlunato`,
  `Miaccagh Lurgi`, `Palai Nello`. **The commonest damage is two names glued
  into one word**, which is exactly what makes a row unfindable: a person
  searching *Giuseppe* shares no whole word with `MattenceSuireppe`.
* **OL.PRJ.16030 p3**, the faint cursive page. 36 of 37 rows read and most are
  one or two letters from a name: `Nose`/`Nosa` for José and Rosa, `Tuan` for
  Juan, `Gerolano` for Gerolamo, `Garpar` for Gaspar. One word of the whole
  page is a name this archive has read before.

- [~] **T13 — Findability on the pages that read as noise.** *Started
      2026-08-29; the glue is done and measured, the faint hand is not.*
      - [x] **Two names run into one word.** Cut where a capital stands inside
            a word — the recogniser dropped the space the clerk wrote and kept
            the capital after it — and index the split beside the reading, in
            `alts`, where a row's second reading already goes and is already
            scored. `bench_search.py --matrix` moves for the first time this
            session: 86→87 of 142 in the top five by name alone, 99→100 in the
            top twenty, 122→123 with the crossing named, nothing lost. The
            hand-read pages are not the pages this was written for and carry
            little glue; across the corpus **1,361 of 37,617 stored readings**
            carry a word a capital cuts in two.
            **And the reader is sent to those rows.** `colado` is a fifth
            reason in the check, measured by `bench_check.py` over the same 149
            rows: it catches 0.041 of the badly-read rows and **stops nobody on
            a correctly-read one** — the only reason in the table with no cost
            at all. It adds nothing to what the four reasons already catch
            together (0.868 either way), and is kept for what it says rather
            than for what it finds: *this row is two names in one word, retype
            it*, which is different advice from *the engine was unsure*.
            Tried and rejected: cutting where both halves are names the archive
            has read. On the page it was written for it splits nothing — the
            glue and the misreading come together, and `Suireppe` is no more in
            the dictionary than `MattenceSuireppe` is.
      - [x] **A hit names the spelling that found it**, done the same
            evening. `search.name_the_spelling` runs over the hits that will be
            shown — fifty comparisons against a query, not thirty thousand —
            and says which of a row's spellings read the query better than the
            reading did, or says nothing when it was the reading itself. The
            hit list prints *encontrado como “…”* under the reading, because a
            hit that explains itself when it did not need to is noise, and one
            that does not explain itself when it should is a tool answering
            with a word no page contains.
      - [ ] ~~A hit does not say which spelling it matched.~~ It carries
            `matched`, and that names the *kind* of match — year, ship, line,
            letters — not which of the row's spellings won. With a split now
            indexed beside the reading, a search for *Giuseppe* can land on a
            row whose stored reading contains no such word, and the hit list
            shows the reading with nothing to explain the hit. The rule this
            repository runs on says a guess is labelled a guess, and this one
            currently is not.
      - [x] **The faint hand**, done 2026-09-03. Not the recogniser after all:
            the stroke rules already knew the way from `Tuan` to Juan and were
            offered only to a person with the row open. They are now indexed
            beside the reading, in `alts`, and every constraint on them was
            measured rather than assumed.

            | | top 5 | top 10 | top 20 |
            |---|---|---|---|
            | by name alone | 87 → **87** | 95 → **97** | 100 → **105** |
            | naming the crossing | 118 → 118 | 123 → 123 | 129 → 129 |

            Four gates, each one put there by a number:

            * **A name somebody has read** — the archive, or the languages
              these ships carried. Ungated this is July's corpus-wide fuzzy
              pass, 91 findable against 90.
            * **Not a name the archive is full of** (`COMMON_NAME`, 40 — 14
              names of 1,081). Guessing rows into MARIA, read 270 times, buried
              the rows that read as it: `Lorenzo Maria`, read `Maria`, 4 → 13.
            * **Within a letter of the word it reads, and four letters long.**
              The edge rule trims `turelis` to `Lis` and `FidaePas` to `Pas`
              against a long enough list — not readings of that ink but what is
              left when most of it is thrown away. This gate alone takes the
              corpus from 46% of rows carrying a guess to 19.5%.
            * **Never to a searcher who named a crossing.** That query does not
              go through the trigram scoring at all; it goes through the
              edit-distance pass, where the ship bonus is added to every row in
              the pool, so a row that only *might* be the name rode the right
              ship past the row somebody had read. Six rows out of the top five,
              and not one row gained. This was the whole of the regression, and
              weighting and flooring the guesses had both failed to shift it
              before the pass itself was found.

            A guess is weighted at 0.95 of a reading so it can add a row and
            never displace one on a tie, and `name_the_spelling` already makes
            the hit say which spelling found it — checked through the running
            app, where `I goseph Ybrooks.` comes back for *Joseph* at 0.95 and
            says so.

            **What it reaches.** Read fresh, OL.PRJ.16030 p3 — the page this
            was written for — has 10 of its 36 read rows reachable by typing a
            real name: `Tuan Canars`→Juan, `Garpar bolhes`→Gaspar, `Nosa`→Rosa,
            `mvires`→Aires, `Gerolano Rrira`→Irma. Corpus-wide, 6,315 of 32,322
            rows carry a spelling nobody read.

            **What it costs.** A cold index build goes from 40 s to 2 m 20 s
            over the 660 dossiers, with the stroke readings of a word cached
            across the rows that repeat it. `/api/search` builds it once and
            keeps it, so this is paid at startup and after a re-read, not per
            keystroke — but at ten times the corpus it is the thing that will
            have to move to SQLite first.

            **Left open, deliberately.** With no floor on how much of a query a
            guess must account for, the numbers above are the best measured;
            a floor of 0.6 trades the +5 at twenty for +1 and protects nothing
            that the crossing fix does not already protect. The frontier, name
            alone, at floor 0.0 / 0.6 / 0.7: 87/97/105, 87/95/101, 87/95/100.

      **The original note, kept:** The candidate
      rules already know how to unglue a word (`strokes`, the *space* rule) and
      how to reach a name one stroke away, and all of that is offered to a
      person who opens the menu on a word. None of it reaches **search**, which
      is where these two pages actually fail — a dossier nobody can find a name
      in is a ship nobody can search, whatever the review screen would offer.
      The measurement already exists and is the one that must move:
      `bench_search.py --matrix`, 86/95/99 of 142 by name alone.
      To settle first, because they are different claims: what is indexed
      beside a reading is not a reading, and a search that matches an invented
      spelling has to say which spelling it matched, or the tool starts
      answering with words no page contains.
