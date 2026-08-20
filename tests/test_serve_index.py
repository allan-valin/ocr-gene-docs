"""Folder indexing over HTTP.

Indexing a folder is the flow the product is actually for — "two hundred
dossiers, I don't know which ship" — so it is exercised end to end through the
server rather than only at the BatchIndexer level.
"""
import json
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import pytest

import serve
from desembarque import engine as engines


class FakeEngine:
    name = "fake"

    def available(self):
        return True

    def transcribe_page(self, image, kind="unknown", source=None, page=None,
                        text=True):
        return engines.PageResult(kind=kind, engine=self.name, rows=[{"name": "TEST"}])


@pytest.fixture
def server(tmp_path, monkeypatch):
    """A server on an ephemeral port, rooted at a temp folder."""
    monkeypatch.setitem(serve.STATE, "root", tmp_path)
    monkeypatch.setattr(serve, "JOBS", serve.JobRunner(tmp_path / ".cache"))
    monkeypatch.setattr(serve, "BATCH", serve.BatchIndexer())
    srv = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", tmp_path
    serve.BATCH.stop()
    srv.shutdown()


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setattr(engines, "_ACTIVE", FakeEngine())
    yield


def call(url, method="GET"):
    try:
        with urlopen(Request(url, method=method)) as r:
            return r.status, json.loads(r.read())
    except HTTPError as e:
        return e.code, json.loads(e.read())


def docs(folder, n=3):
    for i in range(n):
        (folder / f"doc{i}.pdf").write_bytes(b"%PDF-1.7\n")


def wait_done(base, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        _, s = call(f"{base}/api/index")
        if s.get("status") in ("finished", "stopped"):
            return s
        time.sleep(0.02)
    return s


def test_refuses_to_start_without_an_engine(server, monkeypatch):
    base, folder = server
    monkeypatch.setattr(engines, "_ACTIVE", engines.NullEngine())
    docs(folder)
    code, body = call(f"{base}/api/index?dir=", "POST")
    assert code == 409
    assert "modelo" in body["error"].lower()
    _, state = call(f"{base}/api/index")
    assert state["status"] == "idle"


def test_indexes_every_pdf_in_the_folder(server, engine):
    base, folder = server
    docs(folder, 3)
    code, body = call(f"{base}/api/index?dir=", "POST")
    assert code == 202 and body["total"] == 3
    state = wait_done(base)
    assert state["status"] == "finished"
    assert state["done"] + state["skipped"] == 3
    assert state["failed"] == []


def test_resumes_without_redoing_cached_documents(server, engine):
    base, folder = server
    docs(folder, 2)
    call(f"{base}/api/index?dir=", "POST")
    wait_done(base)
    call(f"{base}/api/index?dir=", "POST")
    state = wait_done(base)
    assert state["skipped"] == 2 and state["done"] == 0


def test_stop_halts_the_run(server, engine):
    base, folder = server
    docs(folder, 40)
    call(f"{base}/api/index?dir=", "POST")
    code, _ = call(f"{base}/api/index/stop", "POST")
    assert code == 200
    state = wait_done(base)
    assert state["status"] in ("stopped", "finished")


def test_refuses_a_folder_outside_the_root(server, engine):
    base, _ = server
    code, _ = call(f"{base}/api/index?dir=../../etc", "POST")
    assert code == 404


def test_a_manual_note_with_no_rows_does_not_count_as_indexed(server, engine):
    """Saving nothing, or opening a document and typing one row, must not make
    the indexer skip it forever — an empty manual record is not a transcription."""
    base, folder = server
    docs(folder, 1)
    from desembarque.identity import identify
    ident = identify(folder / "doc0.pdf")
    serve.JOBS.store(ident.doc_hash, {"hash": ident.doc_hash, "source": "manual",
                                      "rows": []})
    call(f"{base}/api/index?dir=", "POST")
    state = wait_done(base)
    assert state["done"] == 1 and state["skipped"] == 0


def test_an_engine_result_is_not_redone(server, engine):
    """A document already read by the engine that ships now is left alone."""
    base, folder = server
    docs(folder, 1)
    from desembarque.identity import identify
    from desembarque.search import SCHEMA
    ident = identify(folder / "doc0.pdf")
    serve.JOBS.store(ident.doc_hash, {"hash": ident.doc_hash, "engine": "paddle",
                                      "schema": SCHEMA, "pages": [], "rows": []})
    call(f"{base}/api/index?dir=", "POST")
    state = wait_done(base)
    assert state["skipped"] == 1 and state["done"] == 0


def test_a_result_from_an_older_engine_is_redone(server, engine):
    """The other half of the rule. A page the ink mask ruined was stored as an
    engine result with no rows; if that counts as done, no improvement to the
    engine can ever reach the corpus and the run reports success anyway."""
    base, folder = server
    docs(folder, 1)
    from desembarque.identity import identify
    ident = identify(folder / "doc0.pdf")
    serve.JOBS.store(ident.doc_hash, {"hash": ident.doc_hash, "engine": "paddle",
                                      "schema": 1, "pages": [], "rows": []})
    call(f"{base}/api/index?dir=", "POST")
    state = wait_done(base)
    assert state["done"] == 1 and state["skipped"] == 0


def test_search_spans_every_indexed_document(server, engine):
    base, folder = server
    docs(folder, 1)
    from desembarque.identity import identify
    ident = identify(folder / "doc0.pdf")
    serve.JOBS.store(ident.doc_hash, {
        "hash": ident.doc_hash, "engine": "paddle", "file": "doc0.pdf",
        "notation": "BS.ENT.9", "rows": [
            {"n": 4, "name_raw": "Guudo Camtadore", "page": 2},
            {"n": 5, "name_raw": "Jose Muerso", "page": 2}]})
    code, body = call(f"{base}/api/search?q=Guido%20Contadore")
    assert code == 200
    assert body["hits"][0]["text"] == "Guudo Camtadore"
    assert body["hits"][0]["file"] == "doc0.pdf" and body["hits"][0]["page"] == 2
    assert body["indexed"] >= 2


def test_search_declines_a_query_too_short_to_mean_anything(server, engine):
    base, _ = server
    code, body = call(f"{base}/api/search?q=jo")
    assert code == 200 and body["hits"] == []


def test_search_can_open_documents_indexed_before_filenames_were_stored(server, engine):
    """Early transcriptions recorded only the content hash. The file a hash
    refers to depends on the folder being browsed anyway, so it is resolved at
    query time rather than trusted from the record."""
    base, folder = server
    docs(folder, 1)
    from desembarque.identity import identify
    ident = identify(folder / "doc0.pdf")
    serve.JOBS.store(ident.doc_hash, {
        "hash": ident.doc_hash, "engine": "paddle", "notation": "BS.ENT.9",
        "rows": [{"n": 4, "name_raw": "Guudo Camtadore", "page": 2}]})
    code, body = call(f"{base}/api/search?q=Guido%20Contadore")
    assert code == 200 and body["hits"]
    assert body["hits"][0]["file"] == "doc0.pdf"


# --- one shape for the geometry, whoever produced it -------------------------
#
# The empty-grid endpoint returns `row_bands` and `name_column`; the engine
# stored `rows` and `columns` for the same thing. The review UI paints the band
# for the selected row from `row_bands`, so on every engine-transcribed page it
# fell through to a pitch that was never stored, computed NaN, and painted
# nothing — clicking a name simply stopped highlighting it.

def test_a_stored_transcription_is_served_in_the_shape_the_ui_paints(server, engine):
    base, folder = server
    docs(folder, 1)
    from desembarque.identity import identify
    from desembarque.search import SCHEMA
    ident = identify(folder / "doc0.pdf")
    serve.JOBS.store(ident.doc_hash, {
        "hash": ident.doc_hash, "engine": "paddle", "schema": SCHEMA,
        "pages": [{"n": 2, "kind": "list",
                   "geometry": {"rows": [[0.1, 0.2], [0.2, 0.3]],
                                "columns": [0.08, 0.35, 0.5],
                                "skew": -0.06, "read_from": "mask"}}],
        "rows": [{"n": 1, "name_raw": "BLOCH LINE", "page": 2}],
    })
    status, got = call(f"{base}/api/transcription?hash={ident.doc_hash}")
    assert status == 200
    geo = got["pages"][0]["geometry"]
    assert geo["row_bands"] == [[0.1, 0.2], [0.2, 0.3]], "bands under the name the UI reads"
    assert geo["name_column"] == [0.08, 0.35], "the widest column, as a pair"
    assert geo["rows"] == [[0.1, 0.2], [0.2, 0.3]], "and the original key is kept"


def test_geometry_already_in_ui_shape_is_left_alone():
    from desembarque.serve_shapes import ui_geometry
    g = {"row_bands": [[0.1, 0.2]], "name_column": [0.1, 0.4], "bands_source": "detected"}
    assert ui_geometry(g) == g


def test_geometry_without_columns_still_gets_its_bands():
    """A page whose columns were not measurable still has rows to highlight."""
    from desembarque.serve_shapes import ui_geometry
    out = ui_geometry({"rows": [[0.1, 0.2]]})
    assert out["row_bands"] == [[0.1, 0.2]]
    assert out.get("name_column") is None


def test_empty_geometry_is_not_invented():
    from desembarque.serve_shapes import ui_geometry
    assert ui_geometry(None) is None
    assert ui_geometry({}) == {}


def test_the_export_endpoint_offers_a_download(server, engine):
    """Exporting is how evidence leaves the tool, so it arrives as a file with
    the dossier's notation on it rather than as text in a browser tab."""
    import urllib.request
    base, folder = server
    docs(folder, 1)
    from desembarque.identity import identify
    ident = identify(folder / "doc0.pdf")
    serve.JOBS.store(ident.doc_hash, {
        "hash": ident.doc_hash, "engine": "paddle", "notation": "BS.ENT.013990",
        "rows": [{"n": 1, "page": 2, "name_raw": "Jaim C. Gil"}],
    })
    with urllib.request.urlopen(f"{base}/api/export?hash={ident.doc_hash}") as r:
        body = r.read().decode()
        assert r.headers["Content-Type"].startswith("text/csv")
        assert "BS.ENT.013990.csv" in r.headers["Content-Disposition"]
    assert "Jaim C. Gil" in body and "notacao" in body


def test_exporting_something_never_read_is_not_an_empty_file(server, engine):
    """An empty spreadsheet would look like a page with nobody on it."""
    base, folder = server
    status, _ = call(f"{base}/api/export?hash=deadbeef")
    assert status == 404


PARTE_TEXT = """MINISTERIO DA AGRICULTURA, INDUSTRIA E COMMERCIO
SERVIÇO DE POVOAMENTO
PARTE
do Interprete Arthur K Fexxerria
"Valdivia"
que visitou o paquete Francer
procedente de B. Aires e escalas
entrado em 10 deDesembro de 1924
SAUDE DOS PASSAGEIROS
MORTALIDADE
NASCIMENTOS
OBSERVAÇÕES
Entregou 1 lista com 12 immigrantes"""


class VoyageEngine:
    """A dossier whose second page is the interpreter's form, not a list.

    This is the common shape in the corpus and it is currently thrown away: the
    engine reads the page, finds no grid, returns the text, and nothing keeps
    it. The ship, the port it sailed from and the arrival date are printed on
    that page and are the only things a searcher reliably knows.
    """
    name = "fake-voyage"

    def available(self):
        return True

    def transcribe_page(self, image, kind="unknown", source=None, page=None,
                        text=True):
        if page == 2:
            return engines.PageResult(kind="unknown", engine=self.name,
                                      text=PARTE_TEXT)
        return engines.PageResult(kind=kind, engine=self.name, text="")


def test_the_voyage_a_dossier_records_is_kept(server, monkeypatch):
    """A page with no rows is not a page with nothing on it."""
    base, folder = server
    monkeypatch.setattr(engines, "_ACTIVE", VoyageEngine())
    docs(folder, 1)
    monkeypatch.setattr(serve, "page_image", lambda *a, **k: None)
    monkeypatch.setattr(serve, "render_page", lambda *a, **k: Path("x.png"))

    from desembarque.identity import identify
    ident = identify(folder / "doc0.pdf")

    class Job:
        total = 2
        page = 0
    data = serve.transcribe_document(folder / "doc0.pdf", Job())
    voyage = data.get("voyage")
    assert voyage, "the dossier's own statement of the voyage was thrown away"
    assert voyage["ship"] == "Valdivia"
    assert voyage["origin"] == "B. Aires e escalas"
    assert voyage["arrival"] == "1924-12-10"
    assert voyage["passengers"] == 12


def test_a_dossier_that_states_no_voyage_carries_none(server, engine, monkeypatch):
    """Absent and empty are different claims, here as everywhere else."""
    base, folder = server
    docs(folder, 1)
    monkeypatch.setattr(serve, "page_image", lambda *a, **k: None)
    monkeypatch.setattr(serve, "render_page", lambda *a, **k: Path("x.png"))

    class Job:
        total = 1
        page = 0
    data = serve.transcribe_document(folder / "doc0.pdf", Job())
    assert "voyage" not in data


def test_the_sidebar_names_the_ship_the_document_names(server, monkeypatch):
    """Until now every real dossier showed `—` where the ship goes, because the
    only ship the corpus knew was the hand-made sample's."""
    base, folder = server
    monkeypatch.setattr(engines, "_ACTIVE", VoyageEngine())
    docs(folder, 1)
    from desembarque.identity import identify
    ident = identify(folder / "doc0.pdf")
    serve.JOBS.store(ident.doc_hash, {
        "hash": ident.doc_hash, "engine": "fake-voyage", "notation": "OL.PRJ.19845",
        "rows": [], "voyage": {"source": "parte", "ship": "Valdivia",
                               "origin": "B. Aires e escalas", "arrival": "1924-12-10"},
    })
    out = serve.corpus(folder)
    doc = out["documents"][0]
    assert doc["ship"] == "Valdivia"
    assert doc["meta"]["arrival"] == "1924-12-10"
    assert doc["meta"]["origin"] == "B. Aires e escalas"


def test_a_field_the_page_never_stated_is_absent_rather_than_empty(server, engine):
    """The header line is built from whatever is known. A missing port printed
    as `undefined` is worse than a missing port, and an empty string reads as a
    page that said nothing where the page was never asked."""
    from desembarque.serve_shapes import ui_meta
    meta = ui_meta({"source": "parte", "ship": "Baden", "year": 1925}, "OL.PRJ.20039")
    assert meta["ship"] == "Baden"
    assert "arrival" not in meta and "origin" not in meta
    assert meta["notation"] == "OL.PRJ.20039"
    assert ui_meta(None, "OL.PRJ.1") is None


# ---- how many times a dossier has to be read as prose ------------------------
#
# Reading a whole page is detection over the entire scan and costs about twenty
# seconds even scaled down. A nine-page dossier with five pages the geometry
# cannot grid was paying that six times over, for two facts: the archival
# notation and the voyage.

def test_the_cover_is_not_read_when_the_filename_already_says_which_dossier():
    from serve import text_wanted
    assert not text_wanted(1, have_notation=True, have_voyage=True)


def test_the_cover_is_read_when_nothing_else_identifies_the_document():
    """The notation is the document's own name for itself, and a filename is
    whatever the last person typed."""
    from serve import text_wanted
    assert text_wanted(1, have_notation=False, have_voyage=True)


def test_reading_stops_once_the_voyage_has_been_found():
    from serve import text_wanted
    assert text_wanted(2, have_notation=True, have_voyage=False)
    assert not text_wanted(3, have_notation=True, have_voyage=True)


def test_a_long_dossier_is_not_read_to_the_end_looking_for_a_form():
    """The forms are at the front — a cover card, the interpreter's PARTE, the
    printed header above the first list. A dossier that has none of them must
    not cost twenty seconds a page to establish that."""
    from serve import text_wanted, TEXT_PAGES
    assert text_wanted(TEXT_PAGES, have_notation=True, have_voyage=False)
    assert not text_wanted(TEXT_PAGES + 1, have_notation=True, have_voyage=False)


def test_a_document_nothing_identifies_is_still_read_past_that_limit():
    """Losing the notation means the dossier is filed under nothing at all."""
    from serve import text_wanted, TEXT_PAGES
    assert text_wanted(TEXT_PAGES + 3, have_notation=False, have_voyage=True)


def test_the_cover_card_is_not_read_for_a_voyage_it_never_states():
    """Page one is the archive's own cover card. It carries the notation and
    says nothing about the ship, so once the filename has given the notation
    there is nothing on it worth twenty seconds of detection."""
    from serve import text_wanted
    assert not text_wanted(1, have_notation=True, have_voyage=False)
    assert text_wanted(2, have_notation=True, have_voyage=False)


PARTE_PAGE3 = """MINISTERIO DA AGRICULTURA, INDUSTRIA E COMMERCIO
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

HEADER_PAGE2 = """POLICIA DO PORTO
Lloyd Brazileiro
Santos, 2.3 de Jen
Repartição da Policia"""


class TwoFormEngine:
    """A dossier that states its voyage twice, as most of them do."""
    name = "fake-two-form"

    def available(self):
        return True

    def transcribe_page(self, image, kind="unknown", source=None, page=None, text=True):
        body = {2: HEADER_PAGE2, 3: PARTE_PAGE3}.get(page, "")
        return engines.PageResult(kind="list" if page == 2 else "unknown",
                                  engine=self.name, text=body if text else "")


def test_a_dossier_is_read_until_its_voyage_names_a_ship(server, monkeypatch):
    """The header above the list gives up the shipping line and the port and
    loses the ship; the interpreter's form two pages later gives up the ship and
    the date. Stopping at the first form found kept the half that narrows
    nothing — every Lloyd Brazileiro sailing shares a shipping line."""
    base, folder = server
    monkeypatch.setattr(engines, "_ACTIVE", TwoFormEngine())
    monkeypatch.setattr(serve, "page_image", lambda *a, **k: None)
    monkeypatch.setattr(serve, "render_page", lambda *a, **k: Path("x.png"))
    docs(folder, 1)

    class Job:
        total = 3
        page = 0
    v = serve.transcribe_document(folder / "doc0.pdf", Job())["voyage"]
    assert v["line"] == "Lloyd Brazileiro"
    assert v["port"] == "Santos"
    assert v["ship"] == "Valdivia"
    assert v["arrival"] == "1924-12-10"


def test_the_form_a_voyage_was_read_from_is_kept_with_the_record(server, monkeypatch):
    """Reading a page as prose costs twenty seconds and re-reading the corpus
    costs hours, so every improvement to the parser was making the whole corpus
    stale and unaffordable to refresh. The text and its boxes are cheap to keep
    and are what the voyage was derived from — kept, a parser change is a
    re-parse of what is already on disk."""
    base, folder = server
    monkeypatch.setattr(engines, "_ACTIVE", VoyageEngine())
    monkeypatch.setattr(serve, "page_image", lambda *a, **k: None)
    monkeypatch.setattr(serve, "render_page", lambda *a, **k: Path("x.png"))
    docs(folder, 1)

    class Job:
        total = 2
        page = 0
    data = serve.transcribe_document(folder / "doc0.pdf", Job())
    forms = [p.get("form") for p in data["pages"] if p.get("form")]
    assert forms, "the page the voyage came from was thrown away"
    assert "Valdivia" in forms[0]["text"]


def test_a_page_read_only_for_its_rows_keeps_no_form(server, engine, monkeypatch):
    """Most pages are never read as prose at all, and an empty form on every one
    of them is noise in a file somebody may open."""
    base, folder = server
    monkeypatch.setattr(serve, "page_image", lambda *a, **k: None)
    monkeypatch.setattr(serve, "render_page", lambda *a, **k: Path("x.png"))
    docs(folder, 1)

    class Job:
        total = 1
        page = 0
    data = serve.transcribe_document(folder / "doc0.pdf", Job())
    assert all("form" not in p for p in data["pages"])


def test_the_archive_s_name_for_a_dossier_reaches_the_header():
    """Two claims about one ship: what the page says, and what the dossier is
    filed under. The header carries both when they differ, because the way to
    settle it is to look at the scan."""
    from desembarque.serve_shapes import ui_meta
    meta = ui_meta({"ship": "Jaronna"}, "BS.ENT.013947", catalogued="garonne")
    assert meta["ship"] == "Jaronna"
    assert meta["catalog_ship"] == "garonne"


def test_a_dossier_the_page_says_nothing_about_still_gets_its_filed_name():
    from desembarque.serve_shapes import ui_meta
    meta = ui_meta({"line": "Lloyd Brazileiro"}, "X", catalogued="itapuca")
    assert meta["catalog_ship"] == "itapuca"


def test_the_filed_name_alone_is_enough_to_have_a_header():
    """Nothing was read off the page, and the folder still knows which ship."""
    from desembarque.serve_shapes import ui_meta
    assert ui_meta(None, "X", catalogued="itapuca")["catalog_ship"] == "itapuca"
    assert ui_meta(None, "X") is None
