"""Unattended indexing has to survive the corpus, not just the happy path."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque.batch import BatchIndexer


def wait(state, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout and state.status == "running":
        time.sleep(0.02)
    return state.status


def files(tmp_path, n):
    out = []
    for i in range(n):
        p = tmp_path / f"doc{i}.pdf"
        p.write_bytes(b"%PDF-1.7\n")
        out.append(p)
    return out


def test_indexes_every_document(tmp_path):
    b = BatchIndexer()
    seen = []
    st = b.start(tmp_path, files(tmp_path, 4), lambda p: False, lambda p: seen.append(p.name))
    assert wait(st) == "finished"
    assert len(seen) == 4 and st.done == 4


def test_one_bad_document_does_not_end_the_run(tmp_path):
    b = BatchIndexer()
    def transcribe(p):
        if p.name == "doc1.pdf":
            raise RuntimeError("corrupt page tree")
    st = b.start(tmp_path, files(tmp_path, 4), lambda p: False, transcribe)
    assert wait(st) == "finished"
    assert st.done == 3
    assert len(st.failed) == 1
    assert "corrupt page tree" in st.failed[0]["error"]
    assert st.failed[0]["file"] == "doc1.pdf"


def test_failures_are_surfaced_not_swallowed(tmp_path):
    b = BatchIndexer()
    st = b.start(tmp_path, files(tmp_path, 2), lambda p: False,
                 lambda p: (_ for _ in ()).throw(ValueError("boom")))
    wait(st)
    assert st.as_dict()["failed"] and st.done == 0


def test_cached_documents_are_skipped_so_a_rerun_redoes_nothing(tmp_path):
    b = BatchIndexer()
    calls = []
    st = b.start(tmp_path, files(tmp_path, 3), lambda p: True, lambda p: calls.append(p))
    assert wait(st) == "finished"
    assert calls == [] and st.skipped == 3 and st.done == 0


def test_can_be_stopped_midway(tmp_path):
    b = BatchIndexer()
    def slow(p):
        time.sleep(0.2)
    st = b.start(tmp_path, files(tmp_path, 20), lambda p: False, slow)
    time.sleep(0.25)
    b.stop()
    assert wait(st) == "stopped"
    assert st.done < 20


def test_only_one_run_at_a_time(tmp_path):
    b = BatchIndexer()
    st1 = b.start(tmp_path, files(tmp_path, 5), lambda p: False, lambda p: time.sleep(0.1))
    st2 = b.start(tmp_path, files(tmp_path, 5), lambda p: False, lambda p: None)
    assert st1 is st2
    b.stop(); wait(st1)


def test_eta_ignores_skipped_documents(tmp_path):
    """Resumed documents cost nothing, so counting them would flatter the estimate."""
    b = BatchIndexer()
    st = b.start(tmp_path, files(tmp_path, 4),
                 lambda p: p.name in ("doc0.pdf", "doc1.pdf"), lambda p: time.sleep(0.05))
    wait(st)
    d = st.as_dict()
    assert d["skipped"] == 2 and d["done"] == 2


def test_collect_pdfs_finds_nested_documents(tmp_path):
    from desembarque.batch import collect_pdfs
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.pdf").write_bytes(b"%PDF")
    (tmp_path / "sub" / "b.PDF").write_bytes(b"%PDF")
    (tmp_path / "notes.txt").write_text("x")
    got = [p.name for p in collect_pdfs(tmp_path)]
    assert got == ["a.pdf", "b.PDF"]


def test_collect_pdfs_ignores_hidden_and_stays_flat_when_asked(tmp_path):
    from desembarque.batch import collect_pdfs
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "h.pdf").write_bytes(b"%PDF")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.pdf").write_bytes(b"%PDF")
    (tmp_path / "a.pdf").write_bytes(b"%PDF")
    assert [p.name for p in collect_pdfs(tmp_path)] == ["a.pdf", "b.pdf"]
    assert [p.name for p in collect_pdfs(tmp_path, recursive=False)] == ["a.pdf"]


def test_workers_share_the_queue_without_repeating_a_document(tmp_path):
    """Seventy thousand pages is a week on one core, so the run is parallel —
    and a document indexed twice is wasted hours, not a harmless duplicate."""
    import threading
    b = BatchIndexer()
    lock, seen = threading.Lock(), []

    def transcribe(p):
        time.sleep(0.005)
        with lock:
            seen.append(p.name)

    st = b.start(tmp_path, files(tmp_path, 24), lambda p: False, transcribe, workers=4)
    assert wait(st) == "finished"
    assert sorted(seen) == sorted(f"doc{i}.pdf" for i in range(24))
    assert st.done == 24


def test_parallel_run_still_isolates_a_bad_document(tmp_path):
    b = BatchIndexer()

    def transcribe(p):
        if p.name in ("doc3.pdf", "doc7.pdf"):
            raise RuntimeError("corrupt page tree")

    st = b.start(tmp_path, files(tmp_path, 12), lambda p: False, transcribe, workers=4)
    assert wait(st) == "finished"
    assert st.done == 10
    assert sorted(f["file"] for f in st.failed) == ["doc3.pdf", "doc7.pdf"]


def test_parallel_run_stops_on_request(tmp_path):
    b = BatchIndexer()

    def transcribe(p):
        time.sleep(0.05)

    st = b.start(tmp_path, files(tmp_path, 200), lambda p: False, transcribe, workers=4)
    time.sleep(0.1)
    b.stop()
    assert wait(st, timeout=5) == "stopped"
    assert st.done < 200
