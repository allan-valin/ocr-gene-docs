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

    def transcribe_page(self, image, kind="unknown"):
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
