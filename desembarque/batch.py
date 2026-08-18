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
              transcribe: Callable[[Path], None]) -> BatchState:
        with self._lock:
            if self.running():
                return self.state
            self._stop.clear()
            state = BatchState(folder=str(folder), total=len(pdfs), status="running")
            self.state = state

        def run() -> None:
            for pdf in pdfs:
                if self._stop.is_set():
                    state.status = "stopped"
                    break
                state.current = pdf.name
                try:
                    if is_cached(pdf):
                        state.skipped += 1      # resume: nothing to re-do
                        continue
                    transcribe(pdf)
                    state.done += 1
                except Exception as e:
                    # one bad document must not end an unattended run, and a
                    # silently skipped document is worse than a loud failure
                    state.failed.append({"file": pdf.name,
                                         "error": f"{type(e).__name__}: {e}"})
            else:
                state.status = "finished"
            if state.status == "running":
                state.status = "finished"
            state.current = ""
            state.finished = time.time()

        threading.Thread(target=run, daemon=True).start()
        return state
