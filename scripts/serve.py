"""Run Desembarque locally: a small HTTP server plus the review UI.

Why a server at all, when the prototype was a single HTML file:

* A file:// page cannot list a directory, so it cannot offer a folder picker.
* A file:// page cannot fetch(), so its data had to be baked in at build time.
* Transcription needs to run somewhere with the models and the filesystem.

A localhost server solves all three with no packaging and no new dependency —
this uses only the standard library — and it still runs in any browser, which a
desktop-only build would not. A native window (see scripts/shell.py) is a thin
wrapper over the same server rather than a separate application.

It binds 127.0.0.1 only. It reads the filesystem beneath a root directory you
choose, and refuses paths outside it.

Usage:
    python scripts/serve.py                      # serves ./data/scans
    python scripts/serve.py --root ~/Documents   # browse elsewhere
    python scripts/serve.py --no-open            # don't launch a browser
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from desembarque import engine as engines          # noqa: E402
from desembarque.identity import identify, cached_hash  # noqa: E402
from desembarque.jobs import JobRunner             # noqa: E402
from desembarque.batch import (BatchIndexer, collect_pdfs, is_indexed,  # noqa: E402
                               preserve_human_work)
from desembarque.serve_shapes import (ui_geometry, ui_meta,  # noqa: E402
                                      ui_transcription)
from desembarque.export import (csv_filename, hits_to_csv,  # noqa: E402
                                rows_to_csv, search_filename)
from desembarque.voyage import (is_complete, merge_voyages,  # noqa: E402
                                parse_voyage)
from desembarque import search as searchlib          # noqa: E402
from desembarque.gazetteer import Names               # noqa: E402
from desembarque import pdf as pdflib               # noqa: E402
from page_geometry import analyze_pdf_page, page_image  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "pagecache"
SAMPLE_ROWS = ROOT / "prototype" / "sample_rows.json"
SAMPLE_INDEX = "017397"

STATE = {"root": ROOT / "data" / "scans"}
# Built by scripts/build_names.py out of the pages this archive typed. Absent is
# a legitimate state: the menu then offers only what the engine read.
NAMES = Names.load(ROOT / "data" / "names.json")


# Which rows to look at first, and why. Measured against 139 hand-read rows, of
# which 67 were badly read: the recogniser's own score below 0.85 catches 81% of
# them (71% of what it flags is wrong), and a surname inherited from a row's
# position is wrong 94% of the time it is flagged. A reading that resembles no
# name in the archive is nearly always wrong and nearly never fires — 3 rows of
# 139 — so it is kept as a third reason rather than the only one.
CHECK_SCORE = 0.85


def _why_check(row: dict, names: Names) -> list[str]:
    """The reasons this row is worth a second look, in the order they matter."""
    out = []
    score = (row.get("conf") or {}).get("surname")
    if score is not None and score < CHECK_SCORE:
        out.append("score")
    if row.get("ditto_source") == "position":
        out.append("inferido")
    from desembarque import search as _s
    if names.doubtful(_s.row_text(row)):
        out.append("desconhecido")
    return out


def current_names() -> Names:
    """The dictionary, rebuilt from disk if it has changed since it was read."""
    global NAMES
    NAMES = NAMES.fresh()
    return NAMES
JOBS = JobRunner(ROOT / "data" / "transcriptions")
BATCH = BatchIndexer()
# Documents are indexed in parallel: one page is ~4 s, and a real folder is
# thousands of them. Four workers rather than one per core — each loads its own
# recogniser, and this has to leave a laptop usable while it runs.
INDEX_WORKERS = int(os.environ.get("DESEMBARQUE_WORKERS", "4"))


def register_engines() -> None:
    """Activate a local engine if its dependencies are installed.

    The engine venv is optional on purpose: the app is useful without it
    (geometry-detected grids, manual entry, search over what is transcribed),
    and a missing model must read as missing rather than as an empty page."""
    try:
        from desembarque.engine_paddle import PaddleEngine
        engines.register(PaddleEngine())
    except Exception:      # an engine that cannot even be imported is absent
        pass


register_engines()


def safe(path_str: str, root: Path) -> Path | None:
    """Resolve a request path, refusing anything outside the chosen root."""
    try:
        p = (root / path_str).resolve() if path_str else root.resolve()
    except (OSError, ValueError):
        return None
    root = root.resolve()
    return p if p == root or root in p.parents else None


_COUNTS: dict[str, int] = {}
_COUNTS_FILE = CACHE / "pagecounts.json"


def pdf_pages(pdf: Path) -> int:
    """Page count, cached. Shelling out per PDF made /api/corpus take seconds
    on a 57-file folder, which is long enough for the UI to paint without an
    image and for scroll sync to have nothing to work with."""
    if not _COUNTS and _COUNTS_FILE.exists():
        try:
            _COUNTS.update(json.loads(_COUNTS_FILE.read_text()))
        except (OSError, ValueError):
            pass
    key = f"{pdf.name}:{pdf.stat().st_mtime_ns}"
    if key in _COUNTS:
        return _COUNTS[key]
    n = pdflib.page_count(pdf)
    _COUNTS[key] = n
    CACHE.mkdir(parents=True, exist_ok=True)
    try:
        _COUNTS_FILE.write_text(json.dumps(_COUNTS))
    except OSError:
        pass
    return n


def render_page(pdf: Path, n: int, dpi: int = 120) -> Path | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / f"{pdf.stem}-p{n}-{dpi}.jpg"
    if dest.exists() and dest.stat().st_size:
        return dest
    return dest if pdflib.render_page(pdf, n, dest, dpi=dpi) else None


def list_dir(d: Path) -> dict:
    dirs, pdfs = [], []
    try:
        for e in sorted(d.iterdir(), key=lambda x: x.name.lower()):
            if e.name.startswith("."):
                continue
            if e.is_dir():
                dirs.append(e.name)
            elif e.suffix.lower() == ".pdf":  # only PDFs, as asked
                pdfs.append({"name": e.name, "size": e.stat().st_size})
    except PermissionError:
        pass
    return {"dirs": dirs, "pdfs": pdfs}


def catalogue(folder: Path) -> dict[str, dict]:
    """The archive's own index of the dossiers in this folder, by filename.

    It names every one of them after a ship, typed, where the tool reads a ship
    off the page in about a fifth of them and mangled. It is somebody's note
    about the document rather than the document, and the archive's own
    cataloguing errors are part of why this corpus needed building — but it is
    how a dossier is filed, and it is the name a person searching knows.
    """
    out: dict[str, dict] = {}
    mpath = folder / "manifest.jsonl"
    if not mpath.exists():
        return out
    try:
        for line in mpath.open(encoding="utf-8"):
            row = json.loads(line)
            for f in row.get("files", []):
                out[f] = row
    except (OSError, ValueError):
        return out
    return out


def catalogue_ships(folder: Path) -> dict[str, str]:
    return {name: row["ship"] for name, row in catalogue(folder).items()
            if row.get("ship")}


def corpus(folder: Path, limit: int = 0) -> dict:
    """Build the sidebar's document list from a folder of PDFs."""
    sample = json.loads(SAMPLE_ROWS.read_text(encoding="utf-8")) if SAMPLE_ROWS.exists() else None
    manifest = catalogue(folder)

    docs = []
    for pdf in sorted(folder.glob("*.pdf")):
        meta = manifest.get(pdf.name, {})
        is_sample = SAMPLE_INDEX in pdf.name and sample is not None
        total = pdf_pages(pdf)
        # identity comes from the file's bytes, not its name: the person using
        # this renames dossiers when saving them
        ident = identify(pdf)
        cached = JOBS.cached(ident.doc_hash)
        docs.append({
            "id": ident.doc_hash[:16],
            "hash": ident.doc_hash,
            "file": pdf.name,
            "notation": ident.notation or (meta.get("index") and
                        f"{meta.get('fundo')}.{meta.get('series')}.{meta.get('index')}")
                        or "sem notação",
            "identified_by": ident.source,
            # the folder list is a list of ships, so it uses the archive's
            # typed name where there is one; the page's own reading is in the
            # header, beside the scan that can settle the two
            "ship": (meta.get("ship")
                     or ((cached or {}).get("voyage") or {}).get("ship")
                     or (cached or {}).get("ship") or "—"),
            "total_pages": total,
            "pages": [{"n": n, "file": f"/api/page?pdf={pdf.name}&n={n}"} for n in range(1, total + 1)],
            "rows": (cached or {}).get("rows") or (sample["rows"] if is_sample else None),
            "geometry": (cached or {}).get("geometry") or (sample["geometry"] if is_sample else None),
            "meta": (ui_meta((cached or {}).get("voyage"), ident.notation,
                             catalogued=meta.get("ship"))
                     or (sample["document"] if is_sample else None)),
            "transcribed_page": (cached or {}).get("transcribed_page") or (2 if is_sample else None),
            "transcribed": bool(cached) or is_sample,
        })
        if limit and len(docs) >= limit:
            break
    return {"documents": docs, "active": next((i for i, d in enumerate(docs) if d["rows"]), 0),
            "root": str(folder)}


COLUMN_LABELS = ["numero", "nome", "nacionalidade", "idade", "sexo",
                 "estado", "profissao", "procedencia", "classe", "observacoes"]


def build_grid(pdf: Path, page_n: int) -> dict:
    """Recover a page's table structure with no model involved.

    Detecting the grid is geometry, not recognition: the rules and the written
    lines are measurable. That gives an empty table with the right number of
    rows, aligned to the scan, which someone can fill in by hand with the
    original beside it. It is the useful floor when no transcription engine is
    installed — structure without invention.
    """
    geo = analyze_pdf_page(pdf, page_n, CACHE / "geometry")
    if not geo or not geo.rows or len(geo.col_edges) < 3:
        return {"detected": False,
                "reason": "nenhuma tabela com réguas detectada nesta página"}

    bands = geo.normalized_rows()
    cols = geo.normalized_cols()
    name = geo.name_column(0)
    rows = [{"n": i + 1, "surname": None, "given": None, "nationality": None,
             "age": None, "sex": None, "status": None, "occupation": None,
             "origin": None, "notes": None, "conf": {}, "band": list(b)}
            for i, b in enumerate(bands)]
    return {
        "detected": True,
        "source": "geometry",
        "rows": rows,
        "columns": cols,
        "labels": COLUMN_LABELS[: max(0, len(cols) - 1)],
        "geometry": {
            "bands_source": "detected",
            "note": "Estrutura detectada geometricamente (sem modelo). "
                    "As células estão vazias: preencha conferindo com o original.",
            "name_column": list(name) if name else None,
            "row_bands": [list(b) for b in bands],
            "skew_deg": geo.skew,
            "row_pitch": geo.row_pitch,
        },
    }


# How far into a dossier the printed forms can be. The cover card, the
# interpreter's PARTE and the printed header above the first list are all at the
# front; a dossier carrying none of them must not cost twenty seconds a page to
# establish that.
TEXT_PAGES = int(os.environ.get("DESEMBARQUE_TEXT_PAGES", "4"))


def text_wanted(page_n: int, have_notation: bool, have_voyage: bool,
                limit: int = TEXT_PAGES) -> bool:
    """Whether this page still needs reading as prose.

    Reading a whole page is detection over the entire scan, and it is done for
    exactly two facts: the archival notation, and the voyage. A nine-page
    dossier with five ungriddable pages was paying for it six times.

    Losing the notation files a dossier under nothing at all, so a document
    nothing else identifies is read as far as it takes.
    """
    if not have_notation:
        return True
    if have_voyage:
        return False
    # Page one is the archive's own cover card: it carries the notation and
    # says nothing about a ship. Once the filename has given the notation there
    # is nothing on it worth detection over the whole sheet.
    if page_n == 1:
        return False
    return page_n <= limit


def classify(page_n: int) -> str:
    """Placeholder classification. Real page typing is a model job; the cover
    card is not reliably page 1 (conservation varies), so this only biases the
    prompt and never decides what a page is."""
    return "cover" if page_n == 1 else "list"


def transcribe_document(pdf: Path, job) -> dict:
    """Render each page and hand it to the active engine."""
    eng = engines.active()
    if not eng.available():
        return {"unavailable": True, "message": engines.status()["detail"]}

    ident = identify(pdf)
    pages, rows, cover_text, voyage = [], [], "", None
    for n in range(1, job.total + 1):
        job.page = n
        img = page_image(pdf, n, CACHE) or render_page(pdf, n, dpi=200)
        if img is None:
            pages.append({"n": n, "error": "render failed"})
            continue
        want = text_wanted(n, bool(ident.notation) or bool(cover_text),
                           is_complete(voyage))
        res = eng.transcribe_page(img, classify(n), source=pdf, page=n,
                                  text=want)
        page = {"n": n, "kind": res.kind, "error": res.error}
        # What the page said as prose, and where each fragment sat. Reading a
        # page costs twenty seconds and re-reading the corpus costs hours, so
        # every improvement to the way these forms are parsed was making the
        # whole corpus stale and unaffordable to refresh. Kept, a parser change
        # becomes a re-parse of what is already on disk.
        if res.text or res.fragments:
            page["form"] = {"text": res.text, "fragments": res.fragments}
        # The grid the rows were cut from. It is measured on the page image to
        # cut them and was then thrown away, so a search hit could name a row
        # and not show where it sits on the scan — and checking the image is
        # what makes a mangled reading usable as evidence. Absent means the
        # page was never measured; the cover card has no grid.
        if res.geometry:
            page["geometry"] = res.geometry
        pages.append(page)
        if res.kind == "cover" and res.text:
            cover_text = cover_text or res.text
        # A page with no rows is not a page with nothing on it. Most of them
        # are the interpreter's PARTE form, which states the ship, the port it
        # sailed from and the arrival date in print — the three things a person
        # searching for an ancestor actually knows.
        if (res.text or res.fragments) and not is_complete(voyage):
            voyage = merge_voyages(
                voyage, parse_voyage(res.text, fragments=res.fragments))
        for r in res.rows:
            r["page"] = n
            rows.append(r)

    ident = identify(pdf, cover_text=cover_text or None)
    return {
        "schema": searchlib.SCHEMA,
        # how the pages were read, as opposed to how the record was parsed. A
        # re-parse lifts `schema` and must not lift this one.
        "read_schema": searchlib.SCHEMA,
        "hash": ident.doc_hash,
        "file": pdf.name,
        "notation": ident.notation,
        "identified_by": ident.source,
        "engine": eng.name,
        "pages": pages,
        "rows": rows,
        **({"voyage": voyage.as_dict()} if voyage else {}),
    }


def hash_index(folder: Path) -> dict[str, str]:
    """Content hash -> filename, for the folder being browsed.

    Transcriptions are keyed by content hash, which is the point: the file can
    be renamed, copied or re-downloaded and keep its work. The consequence is
    that a search hit knows *what* it found and not *where*, so the folder has
    to answer that, and it can only answer for the folder in front of it.
    """
    out = {}
    for pdf in collect_pdfs(folder):
        try:
            out[cached_hash(pdf)] = pdf.name
        except OSError:
            continue
    return out


def warm_the_index(root: Path | None = None) -> None:
    """Read the corpus and build what a search needs, before anybody types.

    The first search after the server starts paid for all of it — two seconds
    over the 660 dossiers on disk and fifteen over the whole archive — with a
    cursor blinking in an empty list. Nobody is waiting while the browser is
    still opening, so it is done then instead.
    """
    rows = searchlib.load_index(JOBS.cache, engine_only=False,
                                ships=catalogue_ships(root or STATE["root"]))
    getattr(rows, "postings", None)
    getattr(rows, "crossings", None)


def name_the_files(hits: list[dict], folder: Path) -> list[dict]:
    """Give each hit the name of the dossier it came from.

    A row stores that name, so most hits answer for themselves; 26 rows of
    31,000 do not, from records written before it was stored, and for those the
    folder in front of the user is the only thing that can say. Asking it means
    walking the folder, which is the largest thing a search request pays for
    once the corpus is the whole archive — so it is asked only when a hit
    cannot name itself.
    """
    if all(h.get("file") for h in hits):
        return hits
    names = hash_index(folder)
    for h in hits:
        h["file"] = h.get("file") or names.get(h.get("doc") or "")
    return hits


class _BatchJob:
    """What transcribe_document needs from a job, without the UI job machinery.

    A folder index reports progress per document, not per page, so there is
    nothing for a per-document job record to be polled for."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.page = 0


def index_folder(folder: Path):
    """Transcribe every PDF under a folder, resuming from the cache.

    The engine is checked once, before anything starts: with no model
    installed every document would fail identically, and a failure list seven
    thousand entries long says less than one refusal does.
    """
    eng = engines.active()
    if not eng.available():
        return None
    pdfs = collect_pdfs(folder)

    def is_cached(pdf: Path) -> bool:
        """Already indexed by the engine that ships now — see `is_indexed`."""
        return is_indexed(JOBS.cached(identify(pdf).doc_hash),
                          schema=searchlib.SCHEMA)

    def transcribe(pdf: Path) -> None:
        data = transcribe_document(pdf, _BatchJob(pdf_pages(pdf)))
        if data.get("unavailable"):
            raise RuntimeError(data.get("message", "motor indisponível"))
        JOBS.store(data["hash"], preserve_human_work(JOBS.cached(data["hash"]), data))

    return BATCH.start(folder, pdfs, is_cached, transcribe,
                       workers=INDEX_WORKERS)


class Handler(BaseHTTPRequestHandler):
    server_version = "Desembarque"

    def log_message(self, fmt, *a):  # quieter console
        pass

    def _send(self, code, body, ctype="application/json", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                html = (ROOT / "prototype" / "review.html").read_text(encoding="utf-8")
                # served over http, so the page fetches its data instead
                return self._send(200, html.replace("__DATA__", ""), "text/html; charset=utf-8")

            if u.path == "/selftest":
                # the same page with the smoke-test script appended, so the served
                # mode is verified by the same assertions as the file:// build
                html = (ROOT / "prototype" / "review.html").read_text(encoding="utf-8")
                js = (ROOT / "prototype" / "selftest.js").read_text(encoding="utf-8")
                html = html.replace("__DATA__", "").replace(
                    "</body>", f"<script>\n{js}\n</script>\n</body>")
                return self._send(200, html, "text/html; charset=utf-8")

            if u.path == "/api/corpus":
                folder = safe(q.get("path", ""), STATE["root"]) or STATE["root"]
                if not folder.is_dir():
                    return self._send(400, {"error": "not a folder"})
                return self._send(200, corpus(folder, int(q.get("limit", 0) or 0)))

            if u.path == "/api/browse":
                folder = safe(q.get("path", ""), STATE["root"]) or STATE["root"]
                root = STATE["root"].resolve()
                rel = "" if folder == root else str(folder.relative_to(root))
                return self._send(200, {"path": rel, "root": str(root),
                                        "parent": str(Path(rel).parent) if rel else None,
                                        **list_dir(folder)})

            if u.path == "/api/page":
                folder = safe(q.get("dir", ""), STATE["root"]) or STATE["root"]
                pdf = safe(str(Path(q.get("dir", "")) / q["pdf"]), STATE["root"])
                if not pdf or not pdf.exists():
                    return self._send(404, {"error": "no such pdf"})
                img = render_page(pdf, int(q.get("n", 1)), int(q.get("dpi", 120)))
                if not img:
                    return self._send(500, {"error": "render failed"})
                return self._send(200, img.read_bytes(), "image/jpeg",
                                  {"Cache-Control": "max-age=86400"})

            if u.path == "/api/grid":
                pdf = safe(str(Path(q.get("dir", "")) / q.get("pdf", "")), STATE["root"])
                if not pdf or not pdf.exists():
                    return self._send(404, {"error": "no such pdf"})
                return self._send(200, build_grid(pdf, int(q.get("n", 1))))

            if u.path == "/api/names":
                # Names this archive is known to carry, offered for one word.
                # They are guesses and the response says so; the caller shows
                # them as guesses and stores nothing unless a person picks one.
                word = q.get("q", "")
                return self._send(200, {
                    "word": word,
                    "guesses": current_names().suggest(word),
                    "of": len(current_names()),
                    "source": "páginas datilografadas deste acervo e linhas "
                              "digitadas por pessoas — não é leitura do motor",
                })

            if u.path == "/api/check":
                # Which rows on a page a person should look at first: the ones
                # where nothing in the reading resembles a name this archive
                # carries. It says nothing about whether the row is wrong — a
                # rare name is unknown here and perfectly correct.
                stored = JOBS.cached(q.get("hash", "")) or {}
                page = int(q.get("page", 0) or 0)
                # A document indexed by the engine has a page on every row. One
                # transcribed by hand predates that and carries a single
                # `transcribed_page` instead — the same distinction the review
                # page makes, and without it the hand-made sample reported no
                # rows at all.
                # Resolved the way the index resolves them, so a record
                # written before the repetition mark was understood is judged
                # by what its rows mean rather than by what is stored.
                all_rows = searchlib._resolved(stored.get("rows") or [])
                numbered = any(r.get("page") is not None for r in all_rows)
                rows = [r for r in all_rows
                        if not page
                        or (r.get("page") == page if numbered
                            else stored.get("transcribed_page") == page)]
                # `row_text` for the emptiness test as well as for the check:
                # a row a person typed carries a surname and a given name and
                # no verbatim reading at all, and testing the reading dropped
                # every one of them.
                names = current_names()
                out = [{"n": r.get("n"), "why": _why_check(r, names),
                        "doubtful": bool(_why_check(r, names))}
                       for r in rows if searchlib.row_text(r).strip()]
                return self._send(200, {
                    "page": page, "rows": out,
                    "doubtful": sum(1 for r in out if r["doubtful"]),
                    "of": len(out),
                    "means": "linhas que valem uma segunda olhada primeiro — "
                             "não quer dizer que estejam erradas",
                })

            if u.path == "/api/geometry":
                # Per page, and asked for rather than sent with the folder
                # list: the corpus carries 1,600 measured pages and three and a
                # half megabytes of bands, while one dossier's are a few
                # kilobytes and are wanted only once it is opened.
                stored = JOBS.cached(q.get("hash", "")) or {}
                geo = {str(p["n"]): ui_geometry(p.get("geometry"))
                       for p in stored.get("pages") or []
                       if isinstance(p, dict) and p.get("geometry")}
                # how each page was measured, which is the difference between a
                # band drawn from the page's own printing and one drawn from
                # rules the scan may have lost
                how = {str(p["n"]): (p.get("geometry") or {}).get("measured_by")
                       for p in stored.get("pages") or []
                       if isinstance(p, dict) and (p.get("geometry") or {}).get("measured_by")}
                return self._send(200, {"hash": q.get("hash", ""), "pages": geo,
                                        "measured_by": how})

            if u.path == "/api/health":
                return self._send(200, {"ok": True, "root": str(STATE["root"]),
                                        **engines.status()})

            if u.path == "/api/engine":
                return self._send(200, engines.status())

            if u.path == "/api/job":
                job = JOBS.get(q.get("id", ""))
                if not job:
                    return self._send(404, {"error": "no such job"})
                return self._send(200, job.as_dict())

            if u.path == "/api/search":
                # across everything indexed, not the open document: the whole
                # point is that the user does not know which dossier to open
                rows = searchlib.load_index(
                    JOBS.cache, engine_only=False,
                    ships=catalogue_ships(STATE["root"]))
                hits = name_the_files(
                    searchlib.search(rows, q.get("q", ""),
                                     limit=int(q.get("limit", 50))),
                    STATE["root"])
                return self._send(200, {
                    "query": q.get("q", ""), "indexed": len(rows),
                    # the page needs both: which scale the scores are on, and
                    # whether telling this searcher to name the ship makes
                    # any sense
                    "crossing": searchlib.names_a_crossing(rows, q.get("q", "")),
                    "advice_bar": searchlib.ADVICE_BAR, "hits": hits})

            if u.path == "/api/index":
                st = BATCH.state
                return self._send(200, st.as_dict() if st else {"status": "idle"})

            if u.path == "/api/export":
                data = JOBS.cached(q.get("hash", ""))
                if not data:
                    return self._send(404, {"error": "not transcribed"})
                # a download, not a page: the browser must offer to save it
                # under a name that says which dossier it came from
                ships = catalogue_ships(STATE["root"])
                return self._send(
                    200, rows_to_csv(data, catalogued=ships.get(data.get("file") or "")),
                    ctype="text/csv; charset=utf-8",
                    extra={"Content-Disposition":
                           f'attachment; filename="{csv_filename(data)}"'})

            if u.path == "/api/export/search":
                # The list somebody takes to the archive: every candidate the
                # search returned, with where to look and why it came back.
                query = q.get("q", "")
                rows = searchlib.load_index(
                    JOBS.cache, engine_only=False,
                    ships=catalogue_ships(STATE["root"]))
                hits = name_the_files(
                    searchlib.search(rows, query, limit=int(q.get("limit", 500))),
                    STATE["root"])
                return self._send(
                    200, hits_to_csv(query, hits),
                    ctype="text/csv; charset=utf-8",
                    extra={"Content-Disposition":
                           f'attachment; filename="{search_filename(query)}"'})

            if u.path == "/api/transcription":
                data = JOBS.cached(q.get("hash", ""))
                return self._send(200 if data else 404,
                                  ui_transcription(data) or {"error": "not transcribed"})

            return self._send(404, {"error": "not found"})
        except Exception as e:  # keep the server alive; surface the error to the UI
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def do_POST(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

        if u.path == "/api/save":
            # Manual transcription is real work — an hour of typing against a
            # scan — so it is written to the same content-hash cache the engine
            # uses, and survives a refresh, a rename, or reopening the folder.
            pdf = safe(str(Path(q.get("dir", "")) / q.get("pdf", "")), STATE["root"])
            if not pdf or not pdf.exists():
                return self._send(404, {"error": "no such pdf"})
            body = self._body()
            rows = body.get("rows")
            if not isinstance(rows, list):
                return self._send(400, {"error": "rows must be a list"})
            ident = identify(pdf)
            existing = JOBS.cached(ident.doc_hash) or {}
            existing.update({
                "hash": ident.doc_hash,
                "notation": ident.notation,
                "identified_by": ident.source,
                "rows": rows,
                "geometry": body.get("geometry") or existing.get("geometry"),
                "transcribed_page": body.get("page") or existing.get("transcribed_page"),
                "source": body.get("source") or "manual",
                "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            })
            JOBS.store(ident.doc_hash, existing)
            return self._send(200, {"saved": True, "hash": ident.doc_hash,
                                    "rows": len(rows)})
        if u.path == "/api/index":
            folder = safe(q.get("dir", ""), STATE["root"])
            if not folder or not folder.is_dir():
                return self._send(404, {"error": "no such folder"})
            if BATCH.running():
                return self._send(200, BATCH.state.as_dict())
            state = index_folder(folder)
            if state is None:
                return self._send(409, {"error": engines.status()["detail"]})
            return self._send(202, state.as_dict())

        if u.path == "/api/index/stop":
            BATCH.stop()
            st = BATCH.state
            return self._send(200, st.as_dict() if st else {"status": "idle"})

        if u.path == "/api/transcribe":
            pdf = safe(str(Path(q.get("dir", "")) / q.get("pdf", "")), STATE["root"])
            if not pdf or not pdf.exists():
                return self._send(404, {"error": "no such pdf"})
            ident = identify(pdf)
            # Asking again is cheap by default: a page costs half a minute and
            # most requests are somebody reopening a document. But `force`
            # exists because without it an engine improvement could never reach
            # a dossier already in the cache — the same silent staleness the
            # schema stamp guards against, from the other end.
            if JOBS.cached(ident.doc_hash) and q.get("force", "") in ("", "0"):
                return self._send(200, {"status": "done", "cached": True,
                                        "hash": ident.doc_hash})
            job = JOBS.submit(ident.doc_hash, pdf.name, pdf_pages(pdf),
                              lambda j: transcribe_document(pdf, j))
            return self._send(202, job.as_dict())
        return self._send(404, {"error": "not found"})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args(argv)

    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"not a folder: {root}", file=sys.stderr)
        return 1
    STATE["root"] = root

    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Desembarque serving {root}\n  {url}\nCtrl-C to stop")
    if not args.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    # in the background: the port answers immediately, and the corpus is ready
    # by the time a name has been typed into it
    threading.Thread(target=warm_the_index, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
