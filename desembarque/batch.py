"""Index a whole folder in the background.

The product's useful case is "two hundred dossiers, I don't know which ship",
not "is my ancestor in this one page" — a person beats the machine at the
latter. So indexing runs unattended over a folder while nobody waits, and
search answers instantly over whatever is done so far.

Unattended means a single bad PDF must not end the run. Every document is
isolated, failures are recorded and surfaced rather than skipped silently, and
an interrupted run resumes from the content-hash cache having re-done nothing.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


def is_indexed(data: dict | None, schema: int) -> bool:
    """Whether this document has already been read by the engine that ships now.

    Two things are being told apart. A record an *engine* wrote is only current
    if it carries the present schema stamp: when the engine learns to read
    something it previously could not — a faint page the ink mask destroyed,
    say — every record written before that is stale, and a run that skips them
    reports success while leaving the corpus exactly as wrong as it was.

    A record a *person* typed is not the engine's to redo, whatever its age.
    But an empty note is not a transcription: someone opens a document, types
    nothing, and leaves, and treating that as done drops the document out of
    every future run with nobody told — the worst failure an archive index has,
    because the person is simply never found.
    """
    if not data:
        return False
    if data.get("engine"):
        return int(data.get("schema", 0)) >= schema
    return bool(data.get("rows"))


# What a person leaves on a record when they correct it. The engine's own stamp
# stays on the record too, so these are the only marks that say a human was here.
HUMAN_MARKS = ("source", "saved_at")


def preserve_human_work(existing: dict | None, fresh: dict) -> dict:
    """A fresh reading of a document, with anything a person typed kept.

    Correcting a row saves the whole record, engine stamp and all, so the next
    schema bump marks that record stale and the run reads the document again —
    and storing is a whole-record write. Every correction anybody had typed
    would be gone, on the run that was supposed to make the corpus better, with
    nobody told. That is the same silent-loss shape as an empty note marking a
    document done, and it is worse, because the work destroyed was real.

    Only the rows are the person's. Everything else the re-read brings — the
    voyage, the geometry, the schema stamp — is why it was read again at all.

    An empty note is still not a transcription: someone opens a dossier, types
    nothing and leaves, and treating that as a correction would freeze the
    document against every future improvement.
    """
    if not existing or not existing.get("rows"):
        return fresh
    if not any(existing.get(mark) for mark in HUMAN_MARKS):
        return fresh
    out = dict(fresh)
    out["rows"] = existing["rows"]
    for mark in HUMAN_MARKS:
        if existing.get(mark):
            out[mark] = existing[mark]
    return out


def collect_pdfs(folder: Path, recursive: bool = True) -> list[Path]:
    """Every PDF under a folder, in a stable order.

    Someone points this at "the dossiers I downloaded", which in practice is a
    tree with a folder per ship or per year, so the default walks it. Hidden
    directories are skipped: they hold caches and version control, never
    scans, and walking them turns a folder index into a disk crawl.
    """
    out: list[Path] = []
    for p in (folder.rglob("*") if recursive else folder.glob("*")):
        if p.suffix.lower() != ".pdf" or not p.is_file():
            continue
        rel = p.relative_to(folder)
        if any(part.startswith(".") for part in rel.parts):
            continue
        out.append(p)
    return sorted(out, key=lambda q: str(q.relative_to(folder)).lower())


@dataclass
class BatchState:
    folder: str
    total: int = 0
    done: int = 0
    skipped: int = 0          # already in the cache
    failed: list[dict] = field(default_factory=list)
    current: str = ""
    status: str = "idle"      # idle | running | stopped | finished
    started: float = field(default_factory=time.time)
    finished: float | None = None

    def as_dict(self) -> dict:
        elapsed = (self.finished or time.time()) - self.started
        processed = self.done + self.skipped
        remaining = max(0, self.total - processed)
        # only count documents actually transcribed towards the rate
        rate = (self.done / elapsed) if (self.done and elapsed > 0) else 0.0
        return {
            "folder": self.folder, "total": self.total, "done": self.done,
            "skipped": self.skipped, "failed": self.failed,
            "current": self.current, "status": self.status,
            "elapsed_s": round(elapsed, 1),
            "eta_s": round(remaining / rate) if rate > 0 else None,
        }


class BatchIndexer:
    """Runs one folder index at a time on a worker thread."""

    def __init__(self) -> None:
        self.state: BatchState | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def running(self) -> bool:
        return bool(self.state and self.state.status == "running")

    def stop(self) -> None:
        self._stop.set()

    def start(self, folder: Path, pdfs: list[Path],
              is_cached: Callable[[Path], bool],
              transcribe: Callable[[Path], None],
              workers: int = 1) -> BatchState:
        """Index every document, on `workers` threads.

        Seventy thousand pages is a week of one core, so the run is parallel by
        default. Threads rather than processes: recognition releases the GIL
        while it runs, and a process per worker would load a copy of the model
        weights on a laptop that has already been made to swap once.

        Counters are only touched under the lock, and each document is claimed
        once from a shared iterator — indexing a document twice is wasted hours,
        not a harmless duplicate.
        """
        with self._lock:
            if self.running():
                return self.state
            self._stop.clear()
            state = BatchState(folder=str(folder), total=len(pdfs), status="running")
            self.state = state

        pending = iter(pdfs)
        claim = threading.Lock()

        def next_pdf() -> Path | None:
            with claim:
                return next(pending, None)

        def run() -> None:
            while not self._stop.is_set():
                pdf = next_pdf()
                if pdf is None:
                    return
                with self._lock:
                    state.current = pdf.name
                try:
                    if is_cached(pdf):
                        with self._lock:
                            state.skipped += 1      # resume: nothing to re-do
                        continue
                    transcribe(pdf)
                    with self._lock:
                        state.done += 1
                except Exception as e:
                    # one bad document must not end an unattended run, and a
                    # silently skipped document is worse than a loud failure
                    with self._lock:
                        state.failed.append({"file": pdf.name,
                                             "error": f"{type(e).__name__}: {e}"})

        def supervise() -> None:
            threads = [threading.Thread(target=run, daemon=True)
                       for _ in range(max(1, workers))]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            state.status = "stopped" if self._stop.is_set() else "finished"
            state.current = ""
            state.finished = time.time()

        threading.Thread(target=supervise, daemon=True).start()
        return state
