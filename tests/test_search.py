"""Search across everything indexed.

The product's premise is that nobody knows which dossier holds their ancestor,
so search has to run over the whole index and be forgiving: the names come out
of a cursive hand through a recogniser, and "Guudo Camtadore" has to be findable
by someone typing "Guido Contadore".
"""
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
