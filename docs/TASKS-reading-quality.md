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
- [ ] **T6 — Stop asserting surname and given** (§1). *Half done.*
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
      - [ ] The engine still calls `split_name`, and `surname`/`given` are
            still written and still read by search, export, the voyages report
            and the review screen. 108 test references sit on those two fields,
            so removing them is a session of its own, and it is the next one.
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

      Still to do: drop the rules that keep scoring nothing once the pages
      their examples live on are scorable; and the ordering, where the
      archive's own first guess is still the best single thing in the menu
      (0.230 at rank one against the whole menu's 0.161).
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
            answer.
      - [ ] Read them: crop each band × column, recognise, and store the
            reading beside the snapped value, never instead of it.
      - [ ] `scripts/bench_columns.py` and a per-column truth page, before any
            of it ships.
- [ ] **T11 — The language prior** (§7). Depends on T10.
