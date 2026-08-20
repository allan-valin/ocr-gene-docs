"""The job runner is what makes 'selecting a file shows loading' honest."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque.jobs import JobRunner


def wait_for(job, statuses, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if job.status in statuses:
            return job.status
        time.sleep(0.02)
    return job.status


def test_job_reports_progress_then_completes(tmp_path):
    r = JobRunner(tmp_path)

    def work(job):
        for n in range(1, 4):
            job.page = n
            time.sleep(0.01)
        return {"pages": 3, "rows": []}

    job = r.submit("abc", "doc", 3, work)
    assert wait_for(job, {"done"}) == "done"
    assert job.page == 3
    assert r.cached("abc") == {"pages": 3, "rows": []}


def test_result_is_cached_by_hash_so_a_rename_reuses_it(tmp_path):
    r = JobRunner(tmp_path)
    r.store("hash123", {"rows": [{"n": 1}]})
    assert r.cached("hash123")["rows"][0]["n"] == 1
    assert r.cached("otherhash") is None


def test_submitting_twice_returns_the_running_job(tmp_path):
    r = JobRunner(tmp_path)

    def slow(job):
        time.sleep(0.3)
        return {"ok": True}

    a = r.submit("same", "doc", 1, slow)
    b = r.submit("same", "doc", 1, slow)
    assert a.id == b.id
    wait_for(a, {"done"})


def test_failure_is_reported_not_swallowed(tmp_path):
    r = JobRunner(tmp_path)

    def boom(job):
        raise RuntimeError("pdftoppm exploded")

    job = r.submit("bad", "doc", 1, boom)
    assert wait_for(job, {"error"}) == "error"
    assert "pdftoppm exploded" in job.message
    assert r.cached("bad") is None


def test_unavailable_engine_is_not_recorded_as_a_transcription(tmp_path):
    """A missing engine must never leave an empty result cached as if it were real."""
    r = JobRunner(tmp_path)
    job = r.submit("nomodel", "doc", 1,
                   lambda j: {"unavailable": True, "message": "no model"})
    assert wait_for(job, {"unavailable"}) == "unavailable"
    assert r.cached("nomodel") is None


def test_elapsed_is_reported(tmp_path):
    r = JobRunner(tmp_path)
    job = r.submit("t", "doc", 1, lambda j: {"ok": True})
    wait_for(job, {"done"})
    assert job.as_dict()["elapsed"] >= 0


def test_transcribing_again_does_not_discard_what_a_person_typed(tmp_path):
    """The button says "transcribe this document", not "throw away the
    corrections". Someone fixes a page, clicks it again to pick up an engine
    improvement, and the typing has to survive it."""
    from desembarque.jobs import JobRunner
    runner = JobRunner(tmp_path / "cache")
    runner.store("h", {"hash": "h", "source": "manual", "saved_at": "2026-08-19",
                       "rows": [{"n": 1, "surname": "CONTADORE", "verified": True}]})
    job = runner.submit("h", "doc.pdf", 2,
                       lambda j: {"hash": "h", "engine": "paddle", "schema": 5,
                                  "rows": [{"n": 1, "surname": "Camtadore"}],
                                  "voyage": {"ship": "Valdivia"}})
    import time
    for _ in range(200):
        if runner.get(job.id).status in ("done", "error", "unavailable"):
            break
        time.sleep(0.01)
    out = runner.cached("h")
    assert out["rows"][0]["surname"] == "CONTADORE"
    assert out["voyage"] == {"ship": "Valdivia"}
