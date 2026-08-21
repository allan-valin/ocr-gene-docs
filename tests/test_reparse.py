"""Re-deriving the voyage from what is already on disk.

Reading a page as prose costs about twenty seconds, and the corpus takes hours.
Every improvement to the way these printed forms are parsed was therefore
making the whole corpus stale and unaffordable to refresh — which is the kind of
cost that stops improvements being made at all. The pages the voyage was read
from are now kept with the record, so a parser change is a re-parse.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque.reparse import reparse

PARTE = """MINISTERIO DA AGRICULTURA, INDUSTRIA E COMMERCIO
SERVIÇO DE POVOAMENTO
PARTE
do Interprete Arthur K Fexxerria
que visitou o paquete Francer "Valdivia"
procedente de B. Aires e escalas
entrado em 10 de Desembro de 1924
SAUDE DOS PASSAGEIROS
MORTALIDADE
NASCIMENTOS
OBSERVAÇÕES"""

HEADER = """POLICIA DO PORTO
Lloyd Brazileiro
Santos, 2.3 de Jen
Repartição da Policia"""


def record(**over):
    base = {"hash": "h", "engine": "paddle", "schema": 3,
            "pages": [{"n": 1, "kind": "cover"},
                      {"n": 2, "kind": "list", "form": {"text": HEADER}},
                      {"n": 3, "kind": "unknown", "form": {"text": PARTE}}],
            "rows": []}
    base.update(over)
    return base


def test_the_voyage_is_rebuilt_from_the_stored_pages():
    out = reparse(record(), schema=9)
    assert out["voyage"]["ship"] == "Valdivia"
    assert out["voyage"]["arrival"] == "1924-12-10"
    assert out["voyage"]["line"] == "Lloyd Brazileiro"
    assert out["schema"] == 9


def test_a_record_with_no_stored_form_is_left_exactly_as_it_was():
    """It was written before the forms were kept, and re-parsing nothing would
    replace a voyage that took twenty seconds to read with no voyage at all."""
    old = {"hash": "h", "engine": "paddle", "schema": 3,
           "voyage": {"ship": "Itapuca"}, "pages": [{"n": 1}], "rows": []}
    assert reparse(old, schema=9) is None


def test_a_voyage_that_re_reads_the_same_way_is_not_rewritten():
    """Nothing changed is not a change, and rewriting every file in the corpus
    to say so churns mtimes the search index watches."""
    first = reparse(record(), schema=9)
    assert reparse(first, schema=9) is None


def test_the_rows_a_person_typed_are_not_touched():
    """Re-parsing is about the header. It has no business near the names."""
    rows = [{"n": 1, "surname": "CONTADORE", "verified": True}]
    out = reparse(record(rows=rows, source="manual"), schema=9)
    assert out["rows"] == rows
    assert out["source"] == "manual"


def test_it_refuses_to_run_while_the_indexer_is_writing(tmp_path, monkeypatch):
    """Re-parsing rewrites every record and an index run writes them too. A lost
    write is a dossier that quietly reverts to what it said before."""
    import runpy
    from pathlib import Path
    m = runpy.run_path(str(Path(__file__).resolve().parents[1]
                           / "scripts" / "reparse_voyages.py"))
    monkeypatch.setitem(m, "indexing_now", lambda port=8799: True)
    rc = m["main"](["--cache", str(tmp_path)])
    assert rc == 2, "it rewrote records while the indexer was running"
    # and a dry run is always safe
    assert m["main"](["--cache", str(tmp_path), "--dry-run"]) == 0
