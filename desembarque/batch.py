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

import os
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

    A page the engine *failed* on is the same trap wearing engine clothes. The
    recogniser on this machine intermittently refuses a model with
    `ConvertPirAttribute2RuntimeAttribute not support`; the page is stored with
    that error, no rows, and the present schema stamp — and every future run
    skips it. BS.ENT.013942 went from thirty-three rows to none that way, and
    nothing told anybody.
    """
    if not data:
        return False
    if data.get("engine"):
        # `schema` says how the record was *parsed* and `read_schema` how it was
        # *read*, and only the second answers this question. Re-parsing lifts the
        # first — it costs a second and touches only the voyage — and for one
        # evening that made every record look freshly read: four hundred dossiers
        # carrying the old geometry would have been skipped by every future run,
        # silently, which is the same failure as the empty note and the errored
        # page wearing different clothes.
        if int(data.get("read_schema", data.get("schema", 0))) < schema:
            return False
        return not any(p.get("error") for p in data.get("pages") or []
                       if isinstance(p, dict))
    return bool(data.get("rows"))


# What a person leaves on a record when they correct it. The engine's own stamp
# stays on the record too, so these are the only marks that say a human was here.
HUMAN_MARKS = ("source", "saved_at")

# And what a person leaves on the row they actually touched: text typed over the
# reading, a candidate chosen from the menu, or the tick that says this row is
# right. The record-level marks above say somebody opened the document; only
# these say which rows are theirs.
ROW_MARKS = ("edits", "verified")


def typed_by_a_person(row: dict) -> bool:
    """Whether this row carries a person's work, rather than the engine's."""
    if not isinstance(row, dict):
        return False
    return bool(row.get("edits")) or bool(row.get("verified"))


def _place(row: dict) -> tuple[int, int]:
    return int(row.get("page") or 0), int(row.get("n") or 0)


def preserve_human_work(existing: dict | None, fresh: dict) -> dict:
    """A fresh reading of a document, with the rows a person typed kept.

    Correcting a row saves the whole record, engine stamp and all, so the next
    schema bump marks that record stale and the run reads the document again —
    and storing is a whole-record write. Every correction anybody had typed
    would be gone, on the run that was supposed to make the corpus better, with
    nobody told. That is the same silent-loss shape as an empty note marking a
    document done, and it is worse, because the work destroyed was real.

    But the mark that says a person was here sits on the *record*, and keeping
    every row of a record because of it froze forty untouched rows for the sake
    of one corrected one — on exactly the documents somebody is working
    through, since those are the ones being corrected. BS.ENT.013947 sat that
    way: page 3 was never read at all while page 2 was being typed. So the
    question is asked per row. A row a person typed into, chose a reading for,
    or ticked is theirs and comes through untouched; every other row is the
    engine's, and the re-read is what it was for.

    A row of theirs that the new reading does not contain — a page cut into
    fewer bands — is kept in page and row order rather than dropped with the
    band.

    Everything outside the rows the re-read brings: the voyage, the geometry,
    the schema stamp — that is why it was read again at all.

    An empty note is still not a transcription: someone opens a dossier, types
    nothing and leaves, and treating that as a correction would freeze the
    document against every future improvement.
    """
    if not existing or not existing.get("rows"):
        return fresh
    if not any(existing.get(mark) for mark in HUMAN_MARKS):
        return fresh

    out = dict(fresh)
    theirs = [r for r in existing["rows"] if typed_by_a_person(r)]

    # A re-read that produced nothing is a failure, not a document with no
    # passengers on it, and it must never stand in for what was there.
    if not fresh.get("rows"):
        out["rows"] = existing["rows"]
    else:
        by_place = {_place(r): r for r in theirs}
        rows, used = [], set()
        for r in fresh["rows"]:
            mine = by_place.get(_place(r))
            rows.append(mine if mine is not None else r)
            if mine is not None:
                used.add(_place(r))
        missing = [r for r in theirs if _place(r) not in used]
        if missing:
            rows = sorted(rows + missing, key=_place)
        out["rows"] = rows

    for mark in HUMAN_MARKS:
        if existing.get(mark):
            out[mark] = existing[mark]
    return out


def saved_page(rows: list[dict], stated: int | None) -> int | None:
    """Which page a save is replacing: what the client said, or what the rows
    themselves all agree on. A batch of rows carrying two pages says nothing,
    and neither does one carrying none."""
    if stated is not None:
        return stated
    pages = {r.get("page") for r in rows if isinstance(r, dict)}
    if len(pages) == 1:
        return pages.pop()
    return None


def merge_page_rows(existing: dict | None, rows: list[dict],
                    page: int | None) -> list[dict]:
    """The rows of one page, saved back into a record that holds every page.

    The review screen shows one page and posts that page's rows, and the save
    wrote them as the record's whole `rows` — so correcting page 2 of an
    eleven-page dossier deleted pages 3 to 11. Nothing said so, and the pages
    were only missing, never wrong, which is the hardest kind of loss to see.

    What was saved is that page, entirely: a row the person deleted is gone
    from it. Every other page stays as it was, and the result comes back in
    page and row order.

    A save that carries no page number cannot say which page it replaces, so it
    replaces the rows, which is what the clients that do not send one expect.
    """
    kept = [r for r in (existing or {}).get("rows") or []
            if isinstance(r, dict) and r.get("page") != page]
    if page is None or not kept:
        return list(rows)
    return sorted(list(rows) + kept, key=_place)


def collect_pdfs(folder: Path, recursive: bool = True) -> list[Path]:
    """Every PDF under a folder, in a stable order.

    Someone points this at "the dossiers I downloaded", which in practice is a
    tree with a folder per ship or per year, so the default walks it. Hidden
    directories are skipped: they hold caches and version control, never
    scans, and walking them turns a folder index into a disk crawl.

    Walked with `os.walk` rather than `rglob`, because a search request walks
    the folder to say which file each hit came from: pathlib builds a `Path`
    for every entry it passes over, which was 55 ms per keystroke over 660
    dossiers and ten times that over the whole archive. Links to folders are
    not followed, the same as before — the folder is the user's and can hold
    anything, including a loop.
    """
    found: list[tuple[str, Path]] = []

    def take(where: str, names) -> None:
        for name in names:
            if name.startswith(".") or not name.lower().endswith(".pdf"):
                continue
            p = Path(where) / name
            if not p.is_file():
                continue
            found.append((os.path.relpath(p, folder).lower(), p))

    if recursive:
        for where, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            take(where, files)
    else:
        try:
            with os.scandir(folder) as it:
                take(str(folder), [e.name for e in it])
        except OSError:
            return []
    found.sort()
    return [p for _, p in found]


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
