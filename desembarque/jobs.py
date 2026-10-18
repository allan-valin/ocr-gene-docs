"""A tiny in-process job runner, so the UI can show progress while a document
is transcribed.

Transcribing a dossier is slow on commodity hardware — the whole point of
selecting a file and seeing "transcrevendo…" rather than a frozen window. Jobs
run on a worker thread; the UI polls for progress.

Results are cached by the document's content hash, so renaming a file, or
opening the same dossier from a different folder, reuses the work.
"""
from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from desembarque.batch import preserve_human_work


@dataclass
class Job:
    id: str
    doc_hash: str
    label: str
    status: str = "queued"           # queued | running | done | error | unavailable
    page: int = 0
    total: int = 0
    message: str = ""
    started: float = field(default_factory=time.time)
    finished: float | None = None
    result_path: str | None = None
    # only these pages, when one page is asked for alone
    pages: list[int] | None = None
    # asked to stop at the end of the page it is on; `abort` throws away
    # what it had read of the document instead of keeping it
    stop: bool = False
    abort: bool = False

    def should_stop(self) -> bool:
        return self.stop

    def as_dict(self) -> dict:
        d = asdict(self)
        d["elapsed"] = round((self.finished or time.time()) - self.started, 1)
        return d


class JobRunner:
    def __init__(self, cache_dir: Path):
        self.cache = cache_dir
        self.cache.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, Job] = {}
        self._by_hash: dict[str, str] = {}
        self._lock = threading.Lock()
        # one worker thread for every job, kept: the engine's predictors
        # are per thread, and a thread per job rebuilt them on every
        # Transcrever — 27 of a page's 33 s on the card (2026-10-18)
        self._queue: queue.Queue = queue.Queue()
        self._worker: threading.Thread | None = None

    def _ensure_worker(self) -> None:
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._loop, name="jobs", daemon=True)
            self._worker.start()

    def _loop(self) -> None:
        while True:
            fn = self._queue.get()
            try:
                fn()
            except Exception:   # a job's own errors are caught in run(); this is the hook's
                pass

    def on_worker(self, fn: Callable[[], None]) -> threading.Event:
        """Run `fn` on the worker thread — the warm-up, so what it builds
        is what the next job uses. The event is set when it has run."""
        done = threading.Event()

        def go() -> None:
            try:
                fn()
            finally:
                done.set()
        self._queue.put(go)
        self._ensure_worker()
        return done

    # ---- cache -------------------------------------------------------------
    def cached_path(self, doc_hash: str) -> Path:
        return self.cache / f"{doc_hash}.json"

    def cached(self, doc_hash: str) -> dict | None:
        p = self.cached_path(doc_hash)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def store(self, doc_hash: str, data: dict) -> Path:
        p = self.cached_path(doc_hash)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return p

    # ---- jobs --------------------------------------------------------------
    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def for_hash(self, doc_hash: str) -> Job | None:
        jid = self._by_hash.get(doc_hash)
        return self._jobs.get(jid) if jid else None

    def submit(self, doc_hash: str, label: str, total: int,
               work: Callable[[Job], dict], pages: list[int] | None = None) -> Job:
        """Start a job, or return the one already running for this document."""
        with self._lock:
            existing = self.for_hash(doc_hash)
            if existing and existing.status in ("queued", "running"):
                return existing
            job = Job(id=uuid.uuid4().hex[:12], doc_hash=doc_hash, label=label,
                      total=total, pages=pages)
            self._jobs[job.id] = job
            self._by_hash[doc_hash] = job.id

        def run() -> None:
            job.status = "running"
            try:
                data = work(job)
                if data.get("unavailable"):
                    job.status = "unavailable"
                    job.message = data.get("message", "")
                elif data.get("partial") and job.abort:
                    job.status = "stopped"
                    job.message = "leitura abortada: o que tinha sido lido foi descartado"
                else:
                    # reading a document again must not discard the reading a
                    # person typed over the last one
                    job.result_path = str(self.store(
                        doc_hash, preserve_human_work(self.cached(doc_hash), data)))
                    job.status = "done"
            except Exception as e:  # a failed page must not kill the server
                job.status = "error"
                job.message = f"{type(e).__name__}: {e}"
            finally:
                job.finished = time.time()

        self._queue.put(run)
        self._ensure_worker()
        return job
