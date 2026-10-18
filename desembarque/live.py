"""What the engine is reading right now, for a page to watch.

Indexing a document takes twenty seconds a page and the browser showed a
bar. Allan asked to see the rows appear as they are read and the band being
read outlined on the scan (2026-10-16). The engine reports here as it goes:
the bands it cut, then each batch of names; `scripts/serve.py` serves the
state at `/api/live?pdf=` and the review page paints it.

Keyed by the document's file name and by thread: the server reads on four
threads sharing one engine, so the engine cannot be told which document it
is on -- the thread that called `watch` is the thread that reads it, and
`emit` finds the document through the thread. Nothing here changes what is
stored; a watcher that never asks costs a dictionary write per batch.
"""
from __future__ import annotations

import threading
import time

_local = threading.local()
_lock = threading.Lock()
_docs: dict[str, dict] = {}
# the seconds each page took, by phase (`page`: the engine; `second`: the
# kraken second reading), kept so the estimate shown is one measured on
# this machine: the "uns 20 s" the box promised was a constant, and the
# Windows CPU took 181 s (2026-10-17). The last fifty of each.
_timings: dict[str, list[float]] = {"page": [], "second": []}


def watch(name: str, pages: int = 0) -> None:
    """This thread is about to read `name`, `pages` long; events from it
    belong to it."""
    _local.name = name
    with _lock:
        _docs[name] = {"file": name, "page": 0, "pages": int(pages or 0),
                       "bands": [], "columns": None,
                       "rows": [], "done": 0, "total": 0, "at": None,
                       # cutting | reading | second: what the page bar shows
                       # instead of a clock (Windows test, 2026-10-17)
                       "phase": None, "second": None,
                       "updated": time.time()}


def unwatch(name: str) -> None:
    _local.name = None
    with _lock:
        _docs.pop(name, None)


def watching() -> str | None:
    return getattr(_local, "name", None)


def emit(event: dict) -> None:
    """The engine's report: `bands` when a page's grid is cut, `read` after
    each batch of names. Ignored on a thread that watches nothing."""
    name = watching()
    if not name:
        return
    with _lock:
        d = _docs.get(name)
        if d is None:
            return
        kind = event.get("event")
        if kind == "page":
            # a new page, before anything is cut from it: a page with no
            # table never reports bands, and the page number is the only
            # sign of progress inside a document (Allan, 2026-10-16)
            d.update(page=int(event.get("page") or 0), bands=[], columns=None,
                     rows=[], done=0, total=0, at=None, page_at=time.time(),
                     phase="cutting")
        elif kind == "bands":
            bands = [list(b) for b in event.get("bands") or []]
            d.update(page=int(event.get("page") or 0), bands=bands,
                     columns=event.get("columns"),
                     rows=[{"n": i + 1, "name_raw": ""} for i in range(len(bands))],
                     done=0, total=len(event.get("written") or bands), at=None,
                     phase="reading")
        elif kind == "read":
            for i, text in event.get("bands") or ():
                if 0 <= i < len(d["rows"]):
                    d["rows"][i]["name_raw"] = text
                    d["at"] = i
            d["done"] += len(event.get("bands") or ())
        elif kind == "page_done":
            _keep("page", event.get("seconds"))
        elif kind == "second":
            # the handwriting reader on one page, of how many it will read:
            # on a CPU this is two thirds of the document's time, and the
            # box showed nothing of it (Windows test, 2026-10-17)
            d.update(phase="second", page=int(event.get("page") or d["page"]),
                     second={"page": int(event.get("page") or 0),
                             "done": int(event.get("done") or 0),
                             "total": int(event.get("total") or 0)})
        elif kind == "second_done":
            if d.get("second"):
                d["second"] = {**d["second"], "done": d["second"]["done"] + 1}
            _keep("second", event.get("seconds"))
        d["updated"] = time.time()


def _keep(phase: str, seconds) -> None:
    if seconds is None:
        return
    lst = _timings.setdefault(phase, [])
    lst.append(float(seconds))
    del lst[:-50]


def emit_timing(phase: str, seconds: float) -> None:
    """A page's seconds, from any thread, watched or not."""
    with _lock:
        _keep(phase, seconds)


def timings() -> dict[str, list[float]]:
    with _lock:
        return {k: list(v) for k, v in _timings.items()}


def forget_timings() -> None:
    with _lock:
        for v in _timings.values():
            v.clear()


def estimate() -> float | None:
    """Seconds a page takes on this machine: the median engine time plus
    the median second-reading time, when any page has been read; None
    before. The median, so one slow page is not the norm."""
    with _lock:
        pages, second = _timings.get("page") or [], _timings.get("second") or []
    if not pages:
        return None
    med = lambda xs: sorted(xs)[len(xs) // 2] if len(xs) % 2 else sum(sorted(xs)[len(xs) // 2 - 1:len(xs) // 2 + 1]) / 2  # noqa: E731
    return round(med(pages) + (med(second) if second else 0.0), 1)


def get(name: str) -> dict | None:
    with _lock:
        d = _docs.get(name)
        return None if d is None else {
            **d, "rows": [dict(r) for r in d["rows"]],
            "bands": [list(b) for b in d["bands"]],
            "page_s": round(time.time() - d["page_at"], 1) if d.get("page_at") else None}


def names() -> list[str]:
    with _lock:
        return sorted(_docs)


def summary() -> list[dict]:
    """Every document being read, and where the engine is in it: the page
    of how many, the names read of how many on that page. What the folder
    index status carries so one poll says everything."""
    with _lock:
        now = time.time()
        return [{"file": d["file"], "page": d["page"], "pages": d["pages"],
                 "done": d["done"], "total": d["total"],
                 "phase": d.get("phase"), "second": d.get("second"),
                 # how long this page has been read for: on a page with no
                 # table nothing else moves, and twenty seconds is the norm
                 "page_s": round(now - d["page_at"], 1) if d.get("page_at") else None}
                for _, d in sorted(_docs.items())]
