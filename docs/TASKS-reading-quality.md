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
- [ ] **T5 — Clear the fossils** (§3). Nationality/profession/origin/age on
      engine rows that no person typed, once T4 makes that distinguishable.
      Count before and after; 27/23/26/22 today.
- [ ] **T6 — Stop asserting surname and given** (§1). `name_raw` is the row's
      name; the repetition mark inherits the tokens written above it. Nothing
      claims a name order unless a person typed it. `bench_search.py --matrix`
      must not fall.
- [ ] **T7 — Candidates from the strokes** (§5). `desembarque/strokes.py`:
      minim re-cuts, ascender/descender swaps, round letters, a stroke lost at
      an edge, unrecognised marks, a missing space. Each rule measured on its
      own with T3's bench; a rule that adds noise without adding names comes out.
- [ ] **T8 — Ask the right question when marking** (§5, `doubtful`). Flag
      *near a name, not a name* apart from *unknown to this archive*. Keep it
      only if it catches misreads the current three reasons miss.
- [ ] **T9 — Display** (§6, §6b). Glued repetition marks shown as marks,
      capitalisation with the archive's particles, and the demo saying it is a
      hand transcription.
- [ ] **T10 — The other columns** (§4), cheapest first: age, sex, class, then
      nationality, profession, port against gazetteers.
- [ ] **T11 — The language prior** (§7). Depends on T10.
