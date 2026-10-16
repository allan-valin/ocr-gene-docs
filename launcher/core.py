"""What the launcher does, apart from drawing buttons.

The application is a localhost server and a browser page, and running it has
meant a terminal, a virtual environment and a command with two flags. The
person this is for has none of those and should not need them: a folder of
PDFs, a button that starts, a button that opens the browser, and the server
gone when the window is closed. Everything here is plain library so that a
test can start a stand-in server and stop it without a screen.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv-ocr"
SETTINGS = ROOT / "launcher" / "settings.json"
DEFAULT_PORT = 8765


def venv_python(root: Path = ROOT) -> Path | None:
    """The engine venv's interpreter, or None when nothing is installed yet."""
    exe = (root / ".venv-ocr" / "Scripts" / "python.exe" if os.name == "nt"
           else root / ".venv-ocr" / "bin" / "python")
    return exe if exe.exists() else None


def serve_command(python: Path, root: Path, folder: Path, port: int) -> list[str]:
    """The server, on this folder, on this port, not opening a browser of its
    own — the launcher opens one when the port answers."""
    return [str(python), str(root / "scripts" / "serve.py"),
            "--root", str(folder), "--port", str(port), "--no-open"]


def install_command(root: Path = ROOT) -> list[list[str]]:
    """Make the venv and install into it, in order. `sys.executable` is the
    Python the launcher itself runs under, which is the one the person has."""
    py = (root / ".venv-ocr" / "Scripts" / "python.exe" if os.name == "nt"
          else root / ".venv-ocr" / "bin" / "python")
    return [
        [sys.executable, "-m", "venv", str(root / ".venv-ocr")],
        [str(py), "-m", "pip", "install", "--upgrade", "pip"],
        [str(py), "-m", "pip", "install", "-r", str(root / "requirements.txt"),
         "-r", str(root / "requirements-ocr.txt")],
    ]


def _get(port: int, path: str, timeout: float = 2.0, post: bool = False) -> dict | None:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                 method="POST" if post else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, OSError, ValueError):
        return None


def is_up(port: int, timeout: float = 1.0) -> bool:
    return _get(port, "/api/engine", timeout=timeout) is not None


def index_status(port: int) -> dict:
    return _get(port, "/api/index") or {"status": "unknown"}


def start_index(port: int, folder: str = "") -> dict:
    return _get(port, f"/api/index?dir={folder}", post=True) or {"status": "unknown"}


def describe_index(st: dict) -> str:
    """One line a person can read: how far, and how long, in hours."""
    status = st.get("status", "unknown")
    if status in ("idle", "unknown"):
        return "nada a indexar ainda"
    done = int(st.get("done") or 0) + int(st.get("skipped") or 0)
    total = int(st.get("total") or 0)
    failed = int(st.get("failed") or 0)
    parts = [f"{done} de {total} documentos"]
    eta = st.get("eta_s")
    if status == "running":
        if eta is None:
            parts.append("a estimar o tempo…")
        else:
            h = f"{eta / 3600:.1f}".rstrip("0").rstrip(".")
            parts.append(f"faltam cerca de {h} h" if eta >= 3600
                         else f"faltam cerca de {max(1, round(eta / 60))} min")
    elif status in ("done", "stopped"):
        parts.append("concluído" if status == "done" else "parado")
    if failed:
        parts.append(f"{failed} falhou" if failed == 1 else f"{failed} falharam")
    return " · ".join(parts)


class Server:
    """The server process, started on a folder and stopped on request.

    `command` builds the argv from (folder, port); the real one is
    `serve_command` with the venv's Python, the test's is a stub.
    """

    def __init__(self, command: Callable[[Path, int], list[str]]) -> None:
        self._command = command
        self.proc: subprocess.Popen | None = None
        self.port = DEFAULT_PORT
        self.last_error = ""
        self.log: list[str] = []

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, folder: Path, port: int, wait: float = 60.0) -> bool:
        """True once the port answers. False, with `last_error`, when the
        process dies first or the wait runs out."""
        if self.alive:
            return True
        self.port = port
        self.last_error = ""
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(self._command(folder, port),
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     cwd=str(ROOT), text=True, **kw)
        deadline = time.time() + wait
        while time.time() < deadline:
            if self.proc.poll() is not None:
                out = (self.proc.stdout.read() if self.proc.stdout else "") or ""
                self.last_error = (f"o servidor parou ao arrancar (código "
                                   f"{self.proc.returncode})\n{out[-2000:]}")
                self.proc = None
                return False
            if is_up(port, timeout=0.5):
                return True
            time.sleep(0.25)
        self.last_error = "o servidor não respondeu a tempo"
        self.stop()
        return False

    def stop(self, wait: float = 10.0) -> None:
        p = self.proc
        if p is None:
            return
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=wait)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=5)
        self.proc = None


def load_settings(path: Path = SETTINGS) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(path: Path, settings: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
