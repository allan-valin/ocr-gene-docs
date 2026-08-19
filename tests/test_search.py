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
