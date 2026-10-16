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


def watch(name: str) -> None:
    """This thread is about to read `name`; events from it belong to it."""
    _local.name = name
    with _lock:
        _docs[name] = {"file": name, "page": 0, "bands": [], "columns": None,
                       "rows": [], "done": 0, "total": 0, "at": None,
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
        if kind == "bands":
            bands = [list(b) for b in event.get("bands") or []]
            d.update(page=int(event.get("page") or 0), bands=bands,
                     columns=event.get("columns"),
                     rows=[{"n": i + 1, "name_raw": ""} for i in range(len(bands))],
                     done=0, total=len(event.get("written") or bands), at=None)
        elif kind == "read":
            for i, text in event.get("bands") or ():
                if 0 <= i < len(d["rows"]):
                    d["rows"][i]["name_raw"] = text
                    d["at"] = i
            d["done"] += len(event.get("bands") or ())
        d["updated"] = time.time()


def get(name: str) -> dict | None:
    with _lock:
        d = _docs.get(name)
        return None if d is None else {**d, "rows": [dict(r) for r in d["rows"]],
                                       "bands": [list(b) for b in d["bands"]]}


def names() -> list[str]:
    with _lock:
        return sorted(_docs)
