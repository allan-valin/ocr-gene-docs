"""Search across everything indexed.

The product's premise is that nobody knows which dossier holds their ancestor,
so search has to run over the whole index and be forgiving: the names come out
of a cursive hand through a recogniser, and "Guudo Camtadore" has to be findable
by someone typing "Guido Contadore".
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque.search import fold, search, load_index


def idx(*texts):
    return [{"doc": "D", "file": "d.pdf", "page": 2, "row": i + 1, "text": t}
            for i, t in enumerate(texts)]


def test_finds_an_exact_name():
    hits = search(idx("JOSE MUESSO", "EMMA CONTADORE"), "JOSE MUESSO")
    assert hits[0]["text"] == "JOSE MUESSO"


def test_finds_a_name_the_recogniser_got_wrong():
    rows = idx("Guudo Camtadore", "Jose Muerso", "Nemma Comtadiie")
    hits = search(rows, "Guido Contadore")
    assert hits[0]["text"] == "Guudo Camtadore"


def test_ignores_accents_and_case():
    hits = search(idx("JOSÉ MUESSO"), "jose muesso")
    assert hits and hits[0]["score"] > 0.8


def test_returns_nothing_rather_than_a_bad_guess():
    assert search(idx("JOSE MUESSO"), "KOWALCZYK") == []


def test_orders_by_similarity_and_reports_where_each_hit_is():
    rows = idx("JOSE MUESSO", "JOSE MUERSO", "MARIA SILVA")
    hits = search(rows, "JOSE MUESSO")
    assert [h["row"] for h in hits[:2]] == [1, 2]
    assert hits[0]["page"] == 2 and hits[0]["file"] == "d.pdf"
    assert hits[0]["score"] >= hits[1]["score"]


def test_a_short_query_is_refused_rather_than_matching_everything():
    assert search(idx("JOSE MUESSO"), "jo") == []


def test_fold_strips_diacritics():
    assert fold("José Múñoz") == "JOSE MUNOZ"


def test_load_index_skips_manual_rows_and_empty_names(tmp_path):
    import json
    (tmp_path / "a.json").write_text(json.dumps({
        "hash": "aaa", "notation": "BS.ENT.1", "file": "a.pdf", "engine": "paddle",
        "rows": [{"n": 1, "name_raw": "JOSE MUESSO", "page": 2},
                 {"n": 2, "name_raw": "", "page": 2}]}))
    (tmp_path / "b.json").write_text(json.dumps({
        "hash": "bbb", "source": "manual",
        "rows": [{"n": 1, "surname": "SILVA", "given": "MARIA", "page": 2}]}))
    rows = load_index(tmp_path)
    assert [r["text"] for r in rows] == ["JOSE MUESSO"]
    assert rows[0]["notation"] == "BS.ENT.1"


def test_load_index_keeps_manual_rows_when_asked(tmp_path):
    import json
    (tmp_path / "b.json").write_text(json.dumps({
        "hash": "bbb", "source": "manual", "file": "b.pdf",
        "rows": [{"n": 1, "surname": "SILVA", "given": "MARIA", "page": 2}]}))
    rows = load_index(tmp_path, engine_only=False)
    assert rows and "SILVA" in rows[0]["text"]


def test_column_headings_are_not_searchable_rows():
    from desembarque.search import load_index
    import json, tempfile
    from pathlib import Path as P
    with tempfile.TemporaryDirectory() as d:
        (P(d) / "a.json").write_text(json.dumps({
            "hash": "a", "engine": "paddle", "rows": [
                {"n": 2, "name_raw": "Nomes e Cognomes", "header": True, "page": 2},
                {"n": 4, "name_raw": "JOSE MUESSO", "page": 2}]}))
        rows = load_index(P(d))
    assert [r["text"] for r in rows] == ["JOSE MUESSO"]


def test_a_misread_column_heading_is_still_a_heading():
    """The recogniser reads the printed caption differently on every page —
    "Nome e Cognomes", "Nomes e Cognome" — so exact matching missed most of
    them and they came back as passengers."""
    from desembarque.search import is_heading
    assert is_heading("Nome e Cognomes")
    assert is_heading("Nomes e Cognomes")
    assert is_heading("NOMES E COGNOME")
    assert not is_heading("JOSE MUESSO")
    assert not is_heading("Guudo Camtadore")


def test_index_tolerates_records_from_before_versioning(tmp_path):
    """Records written today have no schema version. Reading must not depend on
    one, or the first schema change silently drops everything already indexed."""
    import json
    from desembarque.search import load_index
    (tmp_path / "old.json").write_text(json.dumps({
        "hash": "a", "engine": "paddle",
        "rows": [{"n": 1, "name_raw": "JOSE MUESSO", "page": 2}]}))
    (tmp_path / "new.json").write_text(json.dumps({
        "hash": "b", "engine": "paddle", "schema": 1,
        "rows": [{"n": 1, "name_raw": "MARIA SILVA", "page": 2}]}))
    assert sorted(r["text"] for r in load_index(tmp_path)) == ["JOSE MUESSO", "MARIA SILVA"]


def test_index_skips_a_record_from_a_future_schema(tmp_path):
    """A newer version of the app may write rows this one cannot read. Skipping
    them loudly-in-the-logs is safer than mis-reading them into search results."""
    import json
    from desembarque.search import load_index
    (tmp_path / "future.json").write_text(json.dumps({
        "hash": "c", "engine": "paddle", "schema": 99,
        "rows": [{"n": 1, "name_raw": "JOSE MUESSO", "page": 2}]}))
    assert load_index(tmp_path) == []


def test_index_is_reread_only_where_it_changed(tmp_path, monkeypatch):
    """At seven thousand dossiers the cache is ~100 MB, and re-reading it on
    every keystroke would make search unusable exactly when it matters."""
    import json
    from desembarque import search as sl

    def write(name, text):
        (tmp_path / name).write_text(json.dumps({
            "hash": name, "engine": "paddle",
            "rows": [{"n": 1, "name_raw": text, "page": 2}]}))

    write("a.json", "JOSE MUESSO")
    write("b.json", "MARIA SILVA")

    reads = []
    real = Path.read_text
    def counting(self, *a, **k):
        reads.append(self.name)
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", counting)

    first = sl.load_index(tmp_path)
    assert len(first) == 2 and len(reads) == 2

    reads.clear()
    again = sl.load_index(tmp_path)
    assert len(again) == 2 and reads == []          # nothing changed, nothing read

    reads.clear()
    write("c.json", "GUIDO CONTADORE")
    third = sl.load_index(tmp_path)
    assert len(third) == 3
    assert reads == ["c.json"]                       # only the new document


def test_a_deleted_document_leaves_the_index(tmp_path):
    import json
    from desembarque.search import load_index
    (tmp_path / "a.json").write_text(json.dumps({
        "hash": "a", "engine": "paddle",
        "rows": [{"n": 1, "name_raw": "JOSE MUESSO", "page": 2}]}))
    assert len(load_index(tmp_path)) == 1
    (tmp_path / "a.json").unlink()
    assert load_index(tmp_path) == []


def test_matching_the_whole_name_beats_matching_one_word_of_it():
    """Measured, not assumed: scoring each word separately and taking the best
    was tried and made retrieval worse — an exact hit on "EMMA" in an unrelated
    "Nina Emma Lundqwist" outranked a fuzzy hit on the whole right name. The
    shape of the whole name carries more signal than any word of it."""
    from desembarque.search import similarity
    right = similarity("EMMA CONTADORE", "Nemma Comtadiie")
    lucky = similarity("EMMA CONTADORE", "Nina Emma Lundqwist")
    assert right > lucky


# ---- the voyage, as something to search with --------------------------------
#
# A person looking for an ancestor knows the ship, or the year, or the port far
# more reliably than they know how a clerk spelled a surname. Until the dossiers
# stated their own voyage there was nothing to narrow a name against; now there
# is, and it is the cheapest way to cut the pool a fuzzy match competes in.

def voyaged(*docs):
    """Rows carrying the voyage of the document they came from."""
    rows = []
    for d, (ship, year, names) in enumerate(docs):
        for i, t in enumerate(names):
            rows.append({"doc": f"D{d}", "file": f"d{d}.pdf", "page": 2,
                         "row": i + 1, "text": t, "ship": ship, "year": year})
    return rows


ROWS = voyaged(
    ("Valdivia", 1924, ["Guudo Camtadore", "Jose Muerso"]),
    ("Baden", 1925, ["Guido Contadore"]),
)


def test_a_year_in_the_query_is_not_matched_against_the_name():
    """`Contadore 1924` is a name and a year, not a nine-character surname."""
    hits = search(ROWS, "Camtadore 1924")
    assert hits, "the year swallowed the query"
    assert hits[0]["text"] == "Guudo Camtadore"


def test_the_right_year_lifts_a_row_without_overruling_the_name():
    """The voyage breaks ties the recogniser cannot; it does not decide the
    match. `Guido Contadore` spelled exactly stays first even when the year
    points elsewhere — the user may be wrong about the year, and the name is
    the stronger evidence. What the year changes is everything below that."""
    with_year = {h["text"]: h["score"] for h in search(ROWS, "Camtadore 1924")}
    without = {h["text"]: h["score"] for h in search(ROWS, "Camtadore")}
    assert with_year["Guudo Camtadore"] > without["Guudo Camtadore"]


def test_a_row_from_a_year_the_query_rules_out_falls_behind():
    """Thin margins are what a seventy-thousand-row pool destroys, and this is
    where the year earns its place: not by winning the top spot but by pushing
    the wrong ship down the list."""
    with_year = {h["text"]: h["score"] for h in search(ROWS, "Camtadore 1924")}
    without = {h["text"]: h["score"] for h in search(ROWS, "Camtadore")}
    assert with_year["Guido Contadore"] < without["Guido Contadore"]


def test_naming_the_ship_does_the_same():
    lifted = {h["text"]: h["score"] for h in search(ROWS, "Contadore Valdivia")}
    plain = {h["text"]: h["score"] for h in search(ROWS, "Contadore")}
    assert lifted["Guudo Camtadore"] > plain["Guudo Camtadore"]


def test_the_ship_is_not_compared_against_every_surname_on_every_page():
    """Which word is a ship cannot be decided from the query alone, so it is
    decided against the index. Left in the string it is matched against each
    name and dilutes the one it was typed to narrow."""
    from desembarque.search import split_ship
    assert split_ship("Contadore Valdivia", ROWS) == ("Contadore", "Valdivia")
    assert split_ship("Guido Contadore", ROWS) == ("Guido Contadore", None)


def test_a_ship_the_recogniser_mangled_still_matches_a_typed_one():
    """The ship's name came off the page through the same recogniser as the
    surnames, so it is as mangled as they are."""
    rows = voyaged(("Valdivin", 1924, ["Jose Muerso"]))
    from desembarque.search import split_ship
    assert split_ship("Muesso Valdivia", rows) == ("Muesso", "Valdivia")


def test_a_passenger_whose_name_is_also_the_ship_is_still_searchable():
    """Somebody looking for a passenger called Baden aboard the Baden must not
    be left searching for nothing."""
    from desembarque.search import split_ship
    rows = voyaged(("Baden", 1925, ["Baden"]))
    assert split_ship("Baden", rows) == ("Baden", None)


def test_a_document_with_no_voyage_is_never_hidden_by_one():
    """Most of the corpus is not indexed for voyage yet, and a filter would make
    those dossiers unfindable — the failure this whole tool exists to prevent."""
    rows = ROWS + [{"doc": "D9", "file": "d9.pdf", "page": 2, "row": 1,
                    "text": "Guido Contadore"}]
    hits = search(rows, "Guido Contadore 1924")
    assert any(h["doc"] == "D9" for h in hits)


# ---- the archive's own index of ships ----------------------------------------
#
# The archive catalogues every dossier under a ship's name, typed. The tool
# reads a ship off the page in about a fifth of them, mangled. Both are worth
# having and they are different claims: one is how the dossier is filed, the
# other is what the page says.

def test_a_ship_the_archive_names_is_searchable_even_where_the_page_lost_it(tmp_path):
    """Reading `Jaronna` off a header is a fifth of the corpus. The archive
    filed all of it under a typed name, and a person searching knows that name,
    not the recogniser's account of it."""
    from desembarque.search import load_index
    (tmp_path / "a.json").write_text(json.dumps({
        "hash": "h", "engine": "paddle", "file": "d.pdf", "schema": 12,
        "rows": [{"n": 1, "surname": "CONTADORE", "given": "GUIDO"}],
    }), encoding="utf-8")
    rows = load_index(tmp_path, ships={"d.pdf": "gelria"})
    assert rows[0]["ship"] == "gelria"


def test_what_the_page_said_wins_over_the_index_card(tmp_path):
    """The page is the document; the catalogue is somebody's note about it, and
    the archive's own cataloguing errors are why this corpus needed building."""
    from desembarque.search import load_index
    (tmp_path / "a.json").write_text(json.dumps({
        "hash": "h", "engine": "paddle", "file": "d.pdf", "schema": 12,
        "voyage": {"ship": "Valdivia"},
        "rows": [{"n": 1, "surname": "CONTADORE"}],
    }), encoding="utf-8")
    rows = load_index(tmp_path, ships={"d.pdf": "gelria"})
    assert rows[0]["ship"] == "Valdivia"


def test_no_catalogue_changes_nothing(tmp_path):
    from desembarque.search import load_index
    (tmp_path / "a.json").write_text(json.dumps({
        "hash": "h", "engine": "paddle", "file": "d.pdf", "schema": 12,
        "rows": [{"n": 1, "surname": "CONTADORE"}],
    }), encoding="utf-8")
    assert "ship" not in load_index(tmp_path)[0]


def test_a_ship_s_name_on_its_own_lists_who_was_aboard():
    """"Show me everyone on the Itapuca" is the other half of the tool. Typed
    alone, a ship's name was compared against surnames and returned whatever
    happened to look like it — `ITALIAS`, `Itabea Tevures` — while the dossier
    filed under that exact name was nowhere in the results."""
    hits = search(ROWS, "Valdivia")
    assert hits, "the ship's own passengers were not returned"
    assert all(h["ship"] == "Valdivia" for h in hits)
    assert {h["text"] for h in hits} == {"Guudo Camtadore", "Jose Muerso"}


def test_the_hits_say_it_was_the_ship_that_matched():
    """A page of names that do not resemble what was typed needs to explain
    itself, or it reads as a broken search."""
    assert search(ROWS, "Valdivia")[0]["matched"] == "ship"
    assert "matched" not in search(ROWS, "Camtadore")[0]


def test_a_name_that_is_also_a_ship_still_searches_names():
    """`Formosa` is a ship and a surname. Someone typing it means a person more
    often than not, so the names come first and the ship's passengers after."""
    rows = ROWS + [{"doc": "D3", "file": "d3.pdf", "page": 1, "row": 1,
                    "text": "Maria Valdivia", "ship": "Baden", "year": 1925}]
    hits = search(rows, "Valdivia")
    assert hits[0]["text"] == "Maria Valdivia"


def test_a_ship_nobody_indexed_still_finds_nothing():
    assert search(ROWS, "Lusitania") == []


def test_a_year_on_its_own_lists_that_year_s_arrivals():
    """Somebody who knows only the year has the same question as somebody who
    knows only the ship. Typed alone the year was stripped out of the query as a
    year should be, leaving nothing at all to search for."""
    hits = search(ROWS, "1924")
    assert hits and all(h["year"] == 1924 for h in hits)
    assert hits[0]["matched"] == "year"


def test_a_year_nobody_indexed_finds_nothing():
    assert search(ROWS, "1931") == []


def test_a_name_and_a_year_is_still_a_name_search():
    """The year narrows; it does not take over."""
    hits = search(ROWS, "Camtadore 1924")
    assert hits[0]["text"] == "Guudo Camtadore"
    assert "matched" not in hits[0]


def test_naming_the_ship_does_not_promote_a_row_that_looks_like_nothing():
    """Real behaviour before this: `Contadore belvedere` put `CONGE NGLONE A`
    above `Guudo Casrtadore`, because a flat bonus lifts every row on the named
    ship by the same amount and most rows on any ship resemble nothing that was
    typed. The voyage should sharpen a match, not manufacture one."""
    rows = voyaged(("Valdivia", 1924, ["CONGE NGLONE A"]),
                   ("Sirio", 1923, ["Guudo Casrtadore"]))
    hits = search(rows, "Contadore Valdivia")
    assert hits[0]["text"] == "Guudo Casrtadore"


def test_the_form_s_own_words_are_not_indexed_as_passengers():
    """Live search for `Contadore` returned rows read off the printed form —
    `toneladas`, `pessoas de tripulação` — caught by the row comb and filed as
    people. They score against anything that shares a few letters with them and
    they belong to no ship."""
    from desembarque.search import is_heading
    for junk in ("toneladas", "PROFISSÃO", "pessoas de tripulação",
                 "OBSERVAÇÕES", "procedencia destino"):
        assert is_heading(junk), junk


def test_one_misread_printed_word_is_left_alone():
    """`consigr` is `consignado` broken by the row comb, and no threshold
    catches it without also catching `gomes` (against `cognomes`) and `romano`
    (against `comando`) — both real surnames in this corpus. Losing a passenger
    is the failure this tool exists to prevent, so the doubtful ones stay in.
    Telling them apart wants the geometry that knows they sit above the table."""
    from desembarque.search import is_heading
    assert not is_heading("consigr")
    assert not is_heading("gomes")
    assert not is_heading("romano")


def test_a_surname_that_looks_like_a_port_is_still_a_passenger():
    """`Santos` is on the letterhead of half this corpus and is also one of the
    commonest surnames in Brazil. Dropping it would lose real people."""
    from desembarque.search import is_heading
    for name in ("Santos", "JOSE SANTOS", "Maria da Silva", "Nacional Pereira"):
        assert not is_heading(name), name


def test_a_changed_catalogue_is_not_served_from_the_cache(tmp_path):
    """Rows are cached by the file's mtime, and the catalogue is part of what a
    row says it is. Two folders with the same number of ships in them are not
    the same folder."""
    from desembarque.search import load_index
    (tmp_path / "a.json").write_text(json.dumps({
        "hash": "h", "engine": "paddle", "file": "d.pdf", "schema": 12,
        "rows": [{"n": 1, "surname": "CONTADORE"}],
    }), encoding="utf-8")
    first = load_index(tmp_path, ships={"d.pdf": "gelria"})[0]["ship"]
    second = load_index(tmp_path, ships={"d.pdf": "itapuca"})[0]["ship"]
    assert (first, second) == ("gelria", "itapuca")


def test_the_index_narrows_the_rows_a_query_is_scored_against():
    """Every keystroke scores the query against every row in the corpus. At 660
    dossiers that is 19,373 rows and 100 ms; the archive holds 7,679, which is
    the same work eleven times over on every letter typed.

    A row can only score above zero if it shares a trigram with the query, so
    the rows that share none can be skipped without changing a single result.
    """
    from desembarque.search import RowIndex, candidates
    rows = RowIndex(idx("JOSE MUESSO", "EMMA CONTADORE", "MARIA SILVA"))
    pool = [r["text"] for r, _s in candidates(rows, "muesso")]
    assert "JOSE MUESSO" in pool
    # It narrows rather than filters: the padding trigrams a query shares with
    # any row beginning the same way keep a few strangers in the pool, and they
    # are scored and dropped exactly as before. Cheap is the point, not exact.
    assert "EMMA CONTADORE" not in pool


def test_narrowing_returns_exactly_what_scanning_everything_returned():
    """The index is an optimisation and nothing else: same hits, same order,
    same scores. A search that quietly returns less is the failure this tool
    exists to prevent."""
    from desembarque.search import RowIndex
    names = ["Guudo Camtadore", "Jose Muerso", "Nemma Comtadiie", "MARIA SILVA",
             "JOAO GOMES", "Anna Contadore", "CEZARIO SAMMAMED"]
    plain = idx(*names)
    indexed = RowIndex(idx(*names))
    for q in ("contadore", "jose", "gomes", "sammamed", "silva", "kowalczyk"):
        assert search(indexed, q) == search(plain, q), f"{q} came out different"


def test_a_query_sharing_nothing_with_the_corpus_scores_nothing():
    from desembarque.search import RowIndex, candidates
    rows = RowIndex(idx("JOSE MUESSO"))
    assert list(candidates(rows, "kowalczyk")) == []


def test_rows_that_were_not_built_as_an_index_are_still_searched():
    """`load_index` returns one; a script that assembles rows by hand passes a
    plain list, and it has to keep working."""
    hits = search(idx("JOSE MUESSO", "MARIA SILVA"), "muesso")
    assert hits and hits[0]["text"] == "JOSE MUESSO"


def test_the_posting_list_is_not_rebuilt_on_every_keystroke(tmp_path):
    """`/api/search` loads the index per request — that is what makes a changed
    transcription searchable immediately — and rebuilding the postings each
    time would cost more than the scan they replace."""
    import json
    (tmp_path / "a.json").write_text(json.dumps({
        "hash": "h", "file": "d.pdf", "engine": "paddle",
        "rows": [{"n": 1, "page": 2, "name_raw": "JOSE MUESSO"}]}))
    first = load_index(tmp_path)
    second = load_index(tmp_path)
    assert first.postings is second.postings


def test_a_changed_transcription_gets_a_new_posting_list(tmp_path):
    """Rows that are no longer on disk must not stay findable."""
    import json
    f = tmp_path / "a.json"
    f.write_text(json.dumps({
        "hash": "h", "file": "d.pdf", "engine": "paddle",
        "rows": [{"n": 1, "page": 2, "name_raw": "JOSE MUESSO"}]}))
    before = load_index(tmp_path)
    before.postings
    f.write_text(json.dumps({
        "hash": "h", "file": "d.pdf", "engine": "paddle",
        "rows": [{"n": 1, "page": 2, "name_raw": "MARIA SILVA"}]}))
    after = load_index(tmp_path)
    assert [h["text"] for h in search(after, "silva")] == ["MARIA SILVA"]
    assert search(after, "muesso") == []


# Read off real pages, and none of them is a passenger: the tally block at the
# foot of a list, and the interpreter's prose caught by the row comb.
NOT_PEOPLE = ["Total", "Total34", "Total 10412190", "Total.",
              "EM Tranzito em 1a 28 em 3a 9 total 37",
              "de registro, com/8pessoas de tripolação, entrado",
              "Passageiros total in a Classe"]

# Also read off real pages, and every one of them is somebody. Losing a
# passenger is the failure this tool exists to prevent, so the filter is
# measured against these first.
PEOPLE = ["GUIDO CONTADORE", "CEZARIO SAMMAMED", "A. VIEIRA MIRANDA",
          "JOSE MUESSO", "JOAO GOMES", "Anna Romano", "Maria Soma",
          "Nemma Comtadiie", "Rosalena Piseguerra"]


def test_the_tally_at_the_foot_of_the_list_is_not_a_passenger():
    """The row comb fits the printed lines as well as the written ones, so the
    total the clerk wrote under the last name is read as a person."""
    from desembarque.search import is_heading
    for junk in NOT_PEOPLE:
        assert is_heading(junk), f"{junk!r} was indexed as a passenger"


def test_the_passengers_are_still_passengers():
    from desembarque.search import is_heading
    for name in PEOPLE:
        assert not is_heading(name), f"{name!r} was dropped as printing"


def test_a_hit_carries_where_its_year_came_from(tmp_path):
    """The hit list shows the year beside the ship, and a year off the port's
    rubber stamp is a weaker claim than one the clerk wrote — 1928 in this
    corpus is a misread 1923 every time."""
    import json
    (tmp_path / "a.json").write_text(json.dumps({
        "hash": "h", "file": "d.pdf", "engine": "paddle",
        "voyage": {"ship": "Baden", "year": 1928, "year_source": "stamp"},
        "rows": [{"n": 1, "page": 2, "name_raw": "JOSE MUESSO"}]}))
    hits = search(load_index(tmp_path), "muesso")
    assert hits[0]["year"] == 1928 and hits[0]["year_source"] == "stamp"


def test_a_row_written_as_a_repetition_mark_is_found_by_its_surname():
    """Seven of the eight Martinezes on BS.ENT.013947 p3 are written `"`. Read
    verbatim, a search for the surname finds one of them."""
    import json
    from pathlib import Path

    def doc(tmp, rows):
        (tmp / "a.json").write_text(json.dumps({
            "hash": "h", "file": "d.pdf", "engine": "paddle", "rows": rows}))

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        doc(tmp, [{"n": 1, "page": 2, "name_raw": "Martinez Francisco",
                   "surname": "Martinez", "given": "Francisco"},
                  {"n": 2, "page": 2, "name_raw": '" Maria', "surname": "Martinez",
                   "given": "Maria", "ditto": ["surname"]}])
        hits = search(load_index(tmp), "martinez")
        assert len(hits) == 2, [h["text"] for h in hits]
        assert {h["row"] for h in hits} == {1, 2}


def test_the_second_reading_of_a_row_is_searched_too():
    """Every row is read twice and the readings differ where the hand is hard.
    `Waria` and `Maria` are one word on one page: the second reading was kept
    for the person correcting the row and never searched, so a name the engine
    had already got right stayed unfindable."""
    import json
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "a.json").write_text(json.dumps({
            "hash": "h", "file": "d.pdf", "engine": "paddle",
            "rows": [{"n": 1, "page": 2, "name_raw": "Waria Sonsalves",
                      "name_alts": [["Maria"], ["Gonsalves"]]}]}))
        rows = load_index(tmp)
        hits = search(rows, "maria gonsalves")
        assert hits, "the row was not found by what the second reading said"
        assert hits[0]["row"] == 1
        # and the reading itself is still what the row shows
        assert hits[0]["text"] == "Waria Sonsalves"


def test_one_mangled_word_does_not_sink_the_whole_name():
    """A family list writes one surname for eight people, and the recogniser
    mangles it once: `Martinez Dolores` comes back as `artinies Dotores`.
    Compared as one string the good half is dragged under by the bad half."""
    rows = idx("artinies Dotores", "MARIA SILVA", "JOSE MUESSO")
    hits = search(rows, "Martinez Dolores")
    assert hits and hits[0]["text"] == "artinies Dotores"


def test_a_single_word_row_does_not_outrank_a_whole_name():
    """`Maria` answers one word of `Martinez Maria` perfectly and the other not
    at all. It is a candidate, not the answer."""
    rows = idx("Martinez Maria", "Maria")
    hits = search(rows, "Martinez Maria")
    assert hits[0]["text"] == "Martinez Maria"


def test_a_year_the_searcher_got_wrong_never_hides_the_person():
    """The voyage reorders and does not decide. The reward for agreeing is large
    — it is what rescues a common name from a pool of twenty thousand — and the
    penalty for contradicting has to stay small enough that a row survives it,
    because the searcher is the one more likely to be wrong about a date."""
    rows = idx("MARIA ROSA CARRANA")
    for r in rows:
        r["year"] = 1922
    hits = search(rows, "Maria Rosa Carrana 1924")
    assert hits, "a wrong year removed the person from the results"
    assert hits[0]["score"] > 0


def test_naming_the_right_year_lifts_the_row_it_belongs_to():
    rows = idx("MARIA ROSA CARRANA", "MARIA ROSA CARRARA")
    rows[0]["year"] = 1922
    rows[1]["year"] = 1917
    hits = search(rows, "Maria Rosa Carrara 1922")
    assert hits[0]["text"] == "MARIA ROSA CARRANA"


# ---- a year range, and the shipping line ------------------------------------
#
# A person searching knows the crossing better than the spelling: the ship if
# the dossier states one — a third of them do — and otherwise the line printed
# on the letterhead, which two thirds of them state. And the year they know is
# usually "sometime in the early twenties", not 1924.

def test_a_range_of_years_narrows_the_way_one_year_does():
    """`1924-1926` is what somebody who knows the decade but not the date
    types. Left as two numbers it is matched against surnames."""
    ranged = {h["text"]: h["score"] for h in search(ROWS, "Camtadore 1924-1926")}
    plain = {h["text"]: h["score"] for h in search(ROWS, "Camtadore")}
    assert ranged["Guudo Camtadore"] > plain["Guudo Camtadore"]
    assert ranged["Guido Contadore"] > plain["Guido Contadore"]


def test_a_year_outside_the_range_still_falls_behind():
    rows = ROWS + [{"doc": "D8", "file": "d8.pdf", "page": 1, "row": 1,
                    "text": "Guido Camtadore", "ship": "Sirio", "year": 1901}]
    hits = {h["text"]: h["score"] for h in search(rows, "Camtadore 1924-1926")}
    plain = {h["text"]: h["score"] for h in search(rows, "Camtadore")}
    assert hits["Guido Camtadore"] < plain["Guido Camtadore"]


def test_the_range_is_read_however_it_is_typed():
    from desembarque.search import split_year
    for q in ("1924-1926", "1924 – 1926", "1924 a 1926", "1924 to 1926",
              "1924/1926", "1926-1924"):
        assert split_year(f"Camtadore {q}") == ("Camtadore", (1924, 1926)), q
    assert split_year("Camtadore 1924") == ("Camtadore", (1924, 1924))
    assert split_year("Camtadore") == ("Camtadore", None)


def test_a_range_on_its_own_lists_everyone_who_landed_in_it():
    hits = search(ROWS, "1924-1925")
    assert hits and all(h["matched"] == "year" for h in hits)
    assert {h["year"] for h in hits} == {1924, 1925}


def lined(*docs):
    """Rows carrying the shipping line printed on the document's letterhead."""
    rows = []
    for d, (line, names) in enumerate(docs):
        for i, t in enumerate(names):
            rows.append({"doc": f"L{d}", "file": f"l{d}.pdf", "page": 1,
                         "row": i + 1, "text": t, "line": line})
    return rows


LINED = lined(("KONINKLIJKE HOLLANDSCHE LLOYD", ["Jose Muerso", "Ana Silva"]),
              ("Comnpanhia Nacional de Navegação Costeira", ["Guudo Camtadore"]))


def test_the_line_is_carried_into_the_index(tmp_path):
    """Two thirds of the corpus states a line and a third states a ship, so it
    is the widest thing a searcher can narrow by — and it was not in the index
    at all."""
    from desembarque.search import load_index
    (tmp_path / "a.json").write_text(json.dumps({
        "hash": "h", "engine": "paddle", "file": "d.pdf", "schema": 12,
        "voyage": {"line": "LLOYD SABAUDO"},
        "rows": [{"n": 1, "surname": "CONTADORE", "given": "GUIDO"}],
    }), encoding="utf-8")
    assert load_index(tmp_path)[0]["line"] == "LLOYD SABAUDO"


def test_naming_the_line_lifts_the_rows_that_travelled_on_it():
    lifted = {h["text"]: h["score"]
              for h in search(LINED, "Muesso Hollandsche Lloyd")}
    plain = {h["text"]: h["score"] for h in search(LINED, "Muesso")}
    assert lifted["Jose Muerso"] > plain["Jose Muerso"]


def test_the_line_is_taken_out_of_the_name_query():
    """Left in the string, `Hollandsche Lloyd` is compared against every
    surname on every page and dilutes the name it was typed to narrow."""
    from desembarque.search import split_line
    assert split_line("Muesso Hollandsche Lloyd", LINED) == (
        "Muesso", ["HOLLANDSCHE", "LLOYD"])


def test_a_line_the_recogniser_mangled_still_matches_a_typed_one():
    """The letterhead came off the page through the same recogniser as the
    surnames — `Comnpanhia Nacional de Navegação Costeira` is what it read."""
    lifted = {h["text"]: h["score"]
              for h in search(LINED, "Camtadore Companhia Nacional de Navegação Costeira")}
    plain = {h["text"]: h["score"] for h in search(LINED, "Camtadore")}
    assert lifted["Guudo Camtadore"] > plain["Guudo Camtadore"]


def test_one_word_of_a_letterhead_narrows_without_being_taken_out():
    """`Costeira`, `Nacional` and `Brasileiro` are words of the companies that
    carried these people, and they are also their surnames. One word is not
    enough to be sure which was meant, so it narrows the search and stays in it
    — a passenger called Costeira is still searched for."""
    from desembarque.search import split_line
    assert split_line("Costeira Maria", LINED) == ("Costeira Maria", ["COSTEIRA"])
    hits = {h["text"]: h["score"] for h in search(LINED, "Camtadore Costeira")}
    plain = {h["text"]: h["score"] for h in search(LINED, "Camtadore")}
    assert hits["Guudo Camtadore"] > plain["Guudo Camtadore"]


def test_a_word_short_enough_to_be_a_surname_is_not_a_line():
    """`Lloyd` and `Nelson` are shipping lines and they are also people. A
    single short word is searched as the name it probably is."""
    from desembarque.search import split_line
    assert split_line("Lloyd", LINED) == ("Lloyd", [])
    assert split_line("Nelson Silva", LINED) == ("Nelson Silva", [])


def test_a_passenger_whose_name_is_the_whole_line_is_still_searchable():
    """What is left after the line comes out has to still be a name — and one
    word is never taken out at all, so a query that is only that word is still
    the name search it probably is, narrowed by the company it also names."""
    from desembarque.search import split_line
    assert split_line("Hollandsche", LINED) == ("Hollandsche", ["HOLLANDSCHE"])


def test_a_line_on_its_own_lists_everyone_who_sailed_with_it():
    """The same question as a ship typed on its own, and for the 015061 dossier
    it is the only one that can be asked: the page names no ship."""
    hits = search(LINED, "Koninklijke Hollandsche Lloyd")
    assert hits and all(h["matched"] == "line" for h in hits)
    assert {h["text"] for h in hits} == {"Jose Muerso", "Ana Silva"}


def test_a_document_with_no_line_is_never_hidden_by_one():
    rows = LINED + [{"doc": "L9", "file": "l9.pdf", "page": 1, "row": 1,
                     "text": "Jose Muesso"}]
    hits = search(rows, "Muesso Hollandsche Lloyd")
    assert any(h["doc"] == "L9" for h in hits)


def test_naming_the_line_does_not_promote_a_row_that_looks_like_nothing():
    """The same failure the ship bonus had: a flat lift puts a row resembling
    nothing above a good match on another letterhead."""
    rows = lined(("KONINKLIJKE HOLLANDSCHE LLOYD", ["CONGE NGLONE A"]),
                 ("LLOYD SABAUDO", ["Guudo Casrtadore"]))
    hits = search(rows, "Contadore Hollandsche Lloyd")
    assert hits[0]["text"] == "Guudo Casrtadore"


# ---- comparing letters, once the crossing has cut the pool -------------------
#
# Trigrams survive a letter dropped or doubled and collapse when the recogniser
# substitutes systematically: `EMILI MUESSO` read as `bmike Meesoo` shares not
# one trigram with what a person types, and edit distance puts the two at 0.58.
# Of the 23 hand-read names still unfound, 18 score below the search floor
# against their own row and most of those score well above it letter by letter.
#
# Letter by letter over 70,000 rows is neither affordable nor precise — every
# Maria in the corpus scores against every other. But a searcher who names the
# ship, the line or the year has already cut the pool to a few hundred rows,
# and there the comparison is both cheap and meaningful.

def test_a_name_trigrams_cannot_reach_is_found_when_the_ship_is_named():
    rows = voyaged(("Valdivia", 1924, ["bmike Meesoo", "CONGE NGLONE A"]),
                   ("Baden", 1925, ["Maria Silva"]))
    hits = search(rows, "EMILI MUESSO Valdivia")
    assert hits and hits[0]["text"] == "bmike Meesoo"


def test_the_letter_by_letter_pass_needs_a_crossing_to_run_in():
    """Without one there is no pool small enough to compare exhaustively, and
    the answer is an honest empty list rather than the nearest Maria."""
    rows = voyaged(("Valdivia", 1924, ["bmike Meesoo"]))
    assert search(rows, "EMILI MUESSO") == []


def test_a_row_on_the_named_ship_that_resembles_nothing_is_still_refused():
    rows = voyaged(("Valdivia", 1924, ["CONGE NGLONE A"]))
    assert search(rows, "EMILI MUESSO Valdivia") == []


def test_the_line_opens_the_same_door_as_the_ship():
    rows = lined(("KONINKLIJKE HOLLANDSCHE LLOYD", ["bmike Meesoo"]),
                 ("LLOYD SABAUDO", ["Maria Silva"]))
    hits = search(rows, "EMILI MUESSO Hollandsche Lloyd")
    assert hits and hits[0]["text"] == "bmike Meesoo"


def test_so_does_a_year():
    rows = voyaged(("Valdivia", 1924, ["bmike Meesoo"]),
                   ("Baden", 1931, ["Maria Silva"]))
    hits = search(rows, "EMILI MUESSO 1924")
    assert hits and hits[0]["text"] == "bmike Meesoo"


def test_a_row_off_the_named_crossing_is_not_read_letter_by_letter():
    """The pool is the crossing. A row on another ship is where it always was:
    matched by trigram or not at all."""
    rows = voyaged(("Valdivia", 1924, ["Maria Silva"]),
                   ("Baden", 1925, ["bmike Meesoo"]))
    hits = search(rows, "EMILI MUESSO Valdivia")
    assert not any(h["text"] == "bmike Meesoo" for h in hits)


def test_a_good_trigram_match_still_wins():
    """The letters are a second chance, not a re-ranking: a row that reads what
    was typed stays above one that has to be argued for."""
    rows = voyaged(("Valdivia", 1924, ["bmike Meesoo", "EMILI MUESSO"]))
    hits = search(rows, "EMILI MUESSO Valdivia")
    assert hits[0]["text"] == "EMILI MUESSO"


def test_the_crossing_is_what_buys_the_last_of_them():
    """`EMILI MUESSO` read as `bmike Meesoo` stands at 0.58, under the floor a
    corpus-wide scan can afford. Naming the ship cuts the pool to a dossier and
    the same reading is reachable — which is what the crossing is for."""
    rows = voyaged(("Valdivia", 1924, ["bmike Meesoo"]))
    assert search(rows, "EMILI MUESSO") == []
    assert search(rows, "EMILI MUESSO Valdivia")[0]["text"] == "bmike Meesoo"


def test_the_letter_pass_finds_the_same_rows_through_the_index(tmp_path):
    """The rows a search runs over carry a posting list once they come out of
    `load_index`, and the crossing scan has to walk a few hundred rows of the
    named ship rather than every row in the corpus. Same answer, both ways."""
    import json as _json
    for i, (ship, name) in enumerate([("Valdivia", "bmike Meesoo"),
                                      ("Baden", "MARIA SILVA")]):
        (tmp_path / f"{i}.json").write_text(_json.dumps({
            "hash": f"h{i}", "engine": "paddle", "file": f"d{i}.pdf",
            "schema": 12, "voyage": {"ship": ship},
            "rows": [{"n": 1, "name_raw": name}],
        }), encoding="utf-8")
    rows = load_index(tmp_path)
    hits = search(rows, "EMILI MUESSO Valdivia")
    assert [h["text"] for h in hits] == ["bmike Meesoo"]
    assert search(list(rows), "EMILI MUESSO Valdivia")[0]["text"] == "bmike Meesoo"


# ---- queries that are not names ---------------------------------------------
#
# The search box takes whatever a person types, including what they paste out of
# a spreadsheet or an archive listing. None of it may raise.

def test_odd_queries_are_answered_rather_than_raising():
    rows = ROWS + LINED
    for q in ("....", "1924-", "-1924", "1924--1926", "1924 1925 1926",
              "  Contadore  ", "Lloyd — Brasileiro", "N.º 12 Contadore",
              "MARIA" * 40, "ñçõ", "Валдивия", "BR_RJANRIO_BS_0_RPV_ENT_013947",
              "Camtadore Valdivia 1924 Hollandsche Lloyd"):
        hits = search(rows, q)
        assert isinstance(hits, list), q
        assert all("score" in h for h in hits), q


def test_a_query_of_only_a_range_is_still_a_range():
    from desembarque.search import split_year
    assert split_year("1924-1926") == ("", (1924, 1926))


def test_two_years_that_are_not_a_range_do_not_swallow_the_name():
    """`Contadore 1924` twice over is still one year and one name."""
    from desembarque.search import split_year
    name, years = split_year("Contadore 1924")
    assert (name, years) == ("Contadore", (1924, 1924))


def test_a_line_of_short_words_is_not_a_line():
    from desembarque.search import split_line
    assert split_line("de la e do", LINED) == ("de la e do", [])
