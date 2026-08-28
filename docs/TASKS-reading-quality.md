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
  - [ ] `scripts/bench_columns.py` + per-column truth for one typed and one
        cursive page (blocked on §4 having anything to score).
- [ ] **T4 — Per-row provenance** (§2). `preserve_human_work` keeps the rows a
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
- [ ] **T6 — Stop asserting surname and given** (§1). *Not started: `surname`
      is 84 references across the engine, ditto, search, export, voyages, the
      server and the review screen, so it is a session of its own rather than
      the tail of another.* `name_raw` is the row's
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
      Still to do: re-run once 013947 is re-read, then drop what still scores
      nothing; and the ordering, where the archive's own first guess is still
      the best single thing in the menu (0.241 at rank one).
- [ ] **T8 — Ask the right question when marking** (§5, `doubtful`). Flag
      *near a name, not a name* apart from *unknown to this archive*. Keep it
      only if it catches misreads the current three reasons miss.
- [ ] **T9 — Display** (§6, §6b). Glued repetition marks shown as marks,
      capitalisation with the archive's particles, and the demo saying it is a
      hand transcription.
- [ ] **T10 — The other columns** (§4), cheapest first: age, sex, class, then
      nationality, profession, port against gazetteers.
- [ ] **T11 — The language prior** (§7). Depends on T10.
