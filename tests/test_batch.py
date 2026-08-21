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


# --- re-indexing after the engine changes ------------------------------------
#
# `is_cached` treated any record an engine had written as finished, so once the
# corpus was indexed no engine improvement could ever reach it: the run skipped
# all 168 documents and reported success. The stored schema stamp is what
# distinguishes "read by the engine that ships now" from "read by an older one".

def test_a_record_from_the_current_engine_is_indexed():
    from desembarque.batch import is_indexed
    assert is_indexed({"engine": "paddle", "schema": 2, "rows": []}, schema=2) is True


def test_a_record_from_an_older_schema_is_reindexed():
    """A page the mask ruined was stored as blank rows and an engine name. It
    must be read again once the engine learns to fall back to a render."""
    from desembarque.batch import is_indexed
    assert is_indexed({"engine": "paddle", "schema": 1, "rows": []}, schema=2) is False


def test_a_record_with_no_schema_stamp_is_reindexed():
    """The earliest records predate the stamp entirely."""
    from desembarque.batch import is_indexed
    assert is_indexed({"engine": "paddle", "rows": []}, schema=2) is False


def test_a_typed_record_is_kept_whatever_its_schema():
    """A person's own transcription is not the engine's to redo."""
    from desembarque.batch import is_indexed
    assert is_indexed({"rows": [{"surname": "BLOCH"}], "schema": 1}, schema=2) is True


def test_an_empty_manual_note_is_not_an_index():
    """Someone opens a document, types nothing, and leaves. Treating that as
    done drops the document out of every future run, and nobody is told."""
    from desembarque.batch import is_indexed
    assert is_indexed({"rows": [], "notes": ""}, schema=2) is False
    assert is_indexed(None, schema=2) is False


# ---- a person's work is never the engine's to redo ---------------------------

def test_a_document_someone_corrected_is_not_overwritten_by_a_later_run():
    """Saving a correction leaves the engine's own stamp on the record, so the
    next schema bump marks it stale and the run reads the document again — and
    `store` writes the whole record. Every correction a person typed would go,
    silently, on the run that was supposed to improve the corpus."""
    from desembarque.batch import preserve_human_work
    existing = {"hash": "h", "engine": "paddle", "schema": 4,
                "source": "manual", "saved_at": "2026-08-19T22:10:00",
                "rows": [{"n": 1, "surname": "CONTADORE", "given": "GUIDO",
                          "verified": True}]}
    fresh = {"hash": "h", "engine": "paddle", "schema": 5,
             "rows": [{"n": 1, "surname": "Camtadore", "given": "Guudo"}],
             "voyage": {"ship": "Valdivia"}}
    out = preserve_human_work(existing, fresh)
    assert out["rows"] == existing["rows"], "the correction was overwritten"
    assert out["source"] == "manual" and out["saved_at"] == existing["saved_at"]


def test_the_re_read_still_brings_back_what_the_person_did_not_type():
    """The point of reading it again is what the engine has learned since. Only
    the rows are the person's."""
    from desembarque.batch import preserve_human_work
    existing = {"hash": "h", "source": "manual", "rows": [{"n": 1}]}
    fresh = {"hash": "h", "schema": 5, "rows": [{"n": 1, "surname": "x"}],
             "voyage": {"ship": "Valdivia"}, "engine": "paddle"}
    out = preserve_human_work(existing, fresh)
    assert out["voyage"] == {"ship": "Valdivia"}
    assert out["schema"] == 5


def test_a_record_no_person_touched_is_replaced_wholesale():
    from desembarque.batch import preserve_human_work
    existing = {"hash": "h", "engine": "paddle", "schema": 4, "rows": [{"n": 1}]}
    fresh = {"hash": "h", "engine": "paddle", "schema": 5, "rows": [{"n": 2}]}
    assert preserve_human_work(existing, fresh) == fresh
    assert preserve_human_work(None, fresh) == fresh


def test_an_empty_manual_note_does_not_shield_a_document_forever():
    """Someone opens a dossier, types nothing, and leaves. Treating that as a
    correction would freeze the document against every future improvement."""
    from desembarque.batch import preserve_human_work
    existing = {"hash": "h", "source": "manual", "rows": []}
    fresh = {"hash": "h", "schema": 5, "rows": [{"n": 1}]}
    assert preserve_human_work(existing, fresh) == fresh


def test_a_page_the_engine_failed_on_is_not_a_finished_document():
    """The recogniser on this machine intermittently refuses a model with
    `ConvertPirAttribute2RuntimeAttribute not support`. The page was stored with
    that error, no rows and the current schema stamp — so every future run
    skipped it. BS.ENT.013942 went from thirty-three rows to none that way, and
    nothing told anybody."""
    from desembarque.batch import is_indexed
    failed = {"engine": "paddle", "schema": 18, "rows": [],
              "pages": [{"n": 1, "kind": "cover"},
                        {"n": 2, "kind": "list", "error": "NotImplementedError: ..."}]}
    assert not is_indexed(failed, 18)
    ok = {"engine": "paddle", "schema": 18, "rows": [{"n": 1}],
          "pages": [{"n": 1, "kind": "cover", "error": None},
                    {"n": 2, "kind": "list", "error": None}]}
    assert is_indexed(ok, 18)


def test_re_parsing_a_record_does_not_make_it_look_freshly_read():
    """`schema` says how a record was parsed and `read_schema` how it was read.
    Re-parsing costs a second and touches only the voyage, so it lifts the first
    — and for one evening that made four hundred dossiers carrying the old
    geometry look current to every future run."""
    from desembarque.batch import is_indexed
    reparsed = {"engine": "paddle", "schema": 18, "read_schema": 17,
                "rows": [{"n": 1}], "pages": [{"n": 1}]}
    assert not is_indexed(reparsed, 18)
    read = {**reparsed, "read_schema": 18}
    assert is_indexed(read, 18)
    # a record from before the distinction existed is judged by what it has
    old = {"engine": "paddle", "schema": 18, "rows": [{"n": 1}], "pages": [{"n": 1}]}
    assert is_indexed(old, 18)
