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
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "pagecache"
SAMPLE_ROWS = ROOT / "prototype" / "sample_rows.json"
SAMPLE_INDEX = "017397"

STATE = {"root": ROOT / "data" / "scans"}


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
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
    n = 0
    for line in out.stdout.splitlines():
        if line.startswith("Pages:"):
            n = int(line.split()[1])
            break
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
    stem = dest.with_suffix("")
    r = subprocess.run(
        ["pdftoppm", "-f", str(n), "-l", str(n), "-r", str(dpi), "-jpeg",
         "-jpegopt", "quality=78", str(pdf), str(stem)],
        capture_output=True)
    made = sorted(stem.parent.glob(f"{stem.name}-*.jpg"))
    if r.returncode != 0 or not made:
        return None
    made[0].replace(dest)
    return dest


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


def corpus(folder: Path, limit: int = 0) -> dict:
    """Build the sidebar's document list from a folder of PDFs."""
    sample = json.loads(SAMPLE_ROWS.read_text(encoding="utf-8")) if SAMPLE_ROWS.exists() else None
    manifest = {}
    mpath = folder / "manifest.jsonl"
    if mpath.exists():
        for line in mpath.open(encoding="utf-8"):
            row = json.loads(line)
            for f in row.get("files", []):
                manifest[f] = row

    docs = []
    for pdf in sorted(folder.glob("*.pdf")):
        meta = manifest.get(pdf.name, {})
        is_sample = SAMPLE_INDEX in pdf.name and sample is not None
        total = pdf_pages(pdf)
        docs.append({
            "id": pdf.stem,
            "file": pdf.name,
            "notation": f"{meta.get('fundo','?')}.{meta.get('series','?')}.{meta.get('index','?')}"
                        if meta else pdf.stem[:28],
            "ship": meta.get("ship") or pdf.stem.replace("_", " ")[:34],
            "total_pages": total,
            "pages": [{"n": n, "file": f"/api/page?pdf={pdf.name}&n={n}"} for n in range(1, total + 1)],
            "rows": sample["rows"] if is_sample else None,
            "geometry": sample["geometry"] if is_sample else None,
            "meta": sample["document"] if is_sample else None,
            "transcribed_page": 2 if is_sample else None,
        })
        if limit and len(docs) >= limit:
            break
    return {"documents": docs, "active": next((i for i, d in enumerate(docs) if d["rows"]), 0),
            "root": str(folder)}


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

            if u.path == "/api/health":
                return self._send(200, {"ok": True, "root": str(STATE["root"])})

            return self._send(404, {"error": "not found"})
        except Exception as e:  # keep the server alive; surface the error to the UI
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/transcribe":
            return self._send(501, {
                "error": "no transcription engine wired up yet",
                "detail": "Open-weight local models are the chosen engine; nothing is "
                          "invented in the meantime.",
            })
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
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
