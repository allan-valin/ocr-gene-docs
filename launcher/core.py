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
        # the second reading of handwritten pages: kraken on a CPU-only torch
        # (the default torch pulls CUDA, five gigabytes nobody here needs), and
        # its PP-OCRv6 weights from Zenodo into ~/.cache/kraken
        # one command, with the CPU wheels as an extra index: installed in two
        # (CPU torch first, then kraken) pip resolved torch again from PyPI
        # and the CUDA build came back, 2026-10-16
        [str(py), "-m", "pip", "install", "--extra-index-url",
         "https://download.pytorch.org/whl/cpu", "torch", "torchvision",
         "-r", str(root / "requirements-kraken.txt")],
        [str(py), "-c", "from desembarque.secondreading import fetch_model; "
                        "print(fetch_model())"],
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


def index_status(port: int, timeout: float = 20.0) -> dict:
    """The index's state. With the recogniser threads busy the server takes
    seconds to answer this — measured 2 to 20 s on a laptop also running
    another job — so the wait is long, and the caller must not be the UI
    thread. No answer is reported as `unknown`, which is not `idle`."""
    return _get(port, "/api/index", timeout=timeout) or {"status": "unknown"}


def start_index(port: int, folder: str = "") -> dict:
    return _get(port, f"/api/index?dir={folder}", post=True) or {"status": "unknown"}


def clients(port: int, timeout: float = 20.0) -> dict | None:
    """Whether a browser page is there, as the server counts it: seconds
    since the last hello and since the last goodbye. None when the server
    did not answer, which says nothing about the browser."""
    return _get(port, "/api/clients", timeout=timeout)


def shutdown(port: int) -> dict | None:
    """Tell the server a stop is coming, so the page can say so."""
    return _get(port, "/api/shutdown", post=True, timeout=2.0)


def browser_gone(c: dict | None, grace: float = 15.0, silence: float = 180.0) -> bool:
    """Whether the last browser page has gone, so the server can stop with it
    (Allan, 2026-10-16: "if the tab is closed, server shuts down").

    The page says hello every few seconds while open and goodbye when its
    tab closes. Gone is a goodbye with no hello after it, once `grace` has
    passed — a reload is a goodbye followed by a hello a second later — or
    no hello at all for `silence`, when the browser died without a word.
    Three minutes, because a browser throttles a tab in the background to a
    beat a minute. Never gone before a hello was ever heard: the browser
    takes a while to open, and a server nobody has reached is not one
    somebody has left.
    """
    if not c:
        return False
    seen, left = c.get("seen_s"), c.get("left_s")
    if seen is None:
        return False
    if left is not None and left >= grace and seen >= left:
        return True
    return seen >= silence


def describe_index(st: dict) -> str:
    """One line a person can read: how far, and how long, in hours."""
    status = st.get("status", "unknown")
    if status == "idle":
        return "nada para indexar ainda"
    if status == "unknown":
        return "o servidor está ocupado e não respondeu (lendo?)"
    done = int(st.get("done") or 0) + int(st.get("skipped") or 0)
    total = int(st.get("total") or 0)
    failed = int(st.get("failed") or 0)
    parts = [f"{done} de {total} documentos"]
    eta = st.get("eta_s")
    if status == "running":
        if eta is None:
            # the first document gives no ETA until it is done, and that can
            # be minutes: name it and say how long, so working looks unlike stuck
            cur = str(st.get("current") or "")
            if cur:
                cur = cur.rsplit(".", 1)[0]
                cur = cur if len(cur) <= 40 else cur[:37] + "…"
                mins = int(st.get("elapsed_s") or 0) // 60
                parts.append(f"lendo {cur} há {mins} min" if mins
                             else f"lendo {cur}")
            else:
                parts.append("estimando o tempo…")
        else:
            h = f"{eta / 3600:.1f}".rstrip("0").rstrip(".")
            parts.append(f"faltam cerca de {h} h" if eta >= 3600
                         else f"faltam cerca de {max(1, round(eta / 60))} min")
    elif status in ("done", "stopped"):
        parts.append("concluído" if status == "done" else "parado")
    if failed:
        parts.append(f"{failed} falhou" if failed == 1 else f"{failed} falharam")
    return " · ".join(parts)


HELP = """\
O que isto faz
O Desembarque lê listas de passageiros em PDF e permite buscar nomes em uma
página no navegador. Tudo roda no seu computador; nada é enviado para fora.

Pasta com os PDFs
Onde estão as listas. Só arquivos .pdf contam; imagens (JPG, PNG) são
ignoradas. Pode trocar de pasta e clicar em Ligar de novo.

Instalar (uma vez)
Cria um ambiente Python próprio e baixa os dois leitores: o motor que
corta a página em linhas e o que lê a letra manuscrita (cerca de 3 GB,
precisa de internet). Só aparece enquanto não estiver instalado.

Ligar
Inicia o servidor (o programa que lê os PDFs) e abre a página no navegador,
em http://127.0.0.1:{port}/. Carregar os modelos leva 1 a 2 minutos; a
janela avisa quando está pronto. Fechar a aba do navegador desliga o
servidor; para voltar, clique em Ligar de novo.

Ler os PDFs da pasta ao ligar
Transcreve os PDFs da pasta que ainda não foram lidos. Cerca de 20 s por
página: uma lista de 9 páginas leva uns 3 minutos; os já lidos são pulados.
A linha de status diz em que documento está e quanto falta. Enquanto lê, o
computador fica lento.

Desligar
Para o servidor; fechar a janela ou a aba do navegador faz o mesmo. A aba
avisa que o servidor foi desligado (o navegador não deixa um programa
fechá-la). O que já foi lido fica salvo na subpasta "transcriptions",
dentro da pasta dos PDFs, e não se perde; da próxima vez continua de onde
parou.

Se algo der errado
"o servidor não respondeu a tempo": o computador estava ocupado; espere e
clique em Ligar de novo. Outras mensagens: copie o texto da caixa abaixo
e mande para quem lhe passou o programa.
"""


def help_text(port: int = DEFAULT_PORT) -> str:
    """The one page of help: every button, what it does, why, how long."""
    return HELP.replace("{port}", str(port))


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

    def start(self, folder: Path, port: int, wait: float = 180.0) -> bool:
        """True once the port answers. False, with `last_error`, when the
        process dies first or the wait runs out. Three minutes: the engine
        loads its models before the port answers, and on a laptop already
        busy with another job that took over a minute."""
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
                self.last_error = (f"o servidor parou ao iniciar (código "
                                   f"{self.proc.returncode})\n{out[-2000:]}")
                self.proc = None
                return False
            if is_up(port, timeout=0.5):
                return True
            time.sleep(0.25)
        self.last_error = "o servidor não respondeu a tempo"
        self.stop()
        return False

    def stop(self, wait: float = 10.0, pause: float = 4.5) -> None:
        """Stop the server. First it is told (`/api/shutdown`), and the page
        hears on its next hello and says the server is gone — a browser lets
        no program close a tab it did not open, so the page saying so is the
        most Desligar can do about the tab. `pause` is how long the page is
        given to hear; it beats every 4 s."""
        p = self.proc
        if p is None:
            return
        if p.poll() is None:
            if pause > 0 and shutdown(self.port) is not None:
                time.sleep(pause)
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
