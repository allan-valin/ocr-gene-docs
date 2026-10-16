"""What the launcher does, apart from drawing buttons.

The application is a localhost server and a browser page, and running it has
meant a terminal, a virtual environment and a command with two flags. The
person this is for has none of those and should not need them: a folder of
PDFs, a button that starts, a button that opens the browser, and the server
gone when the window is closed. Everything here is plain library so that a
test can start a stand-in server and stop it without a screen.
"""
from __future__ import annotations

import collections
import json
import os
import subprocess
import threading
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


# What an install is made of, in three tiers, each with what it is for and
# what it costs. A pendrive with PDFs and their transcriptions on a new PC
# needs the first alone: the server is standard library plus these three
# packages, and the engine is optional by design.
TIERS = {
    "viewer": ("Leitura", "abrir os PDFs, ver e buscar o que já foi transcrito",
               "uns 100 MB"),
    "engine": ("Motor de transcrição",
               "ler páginas datilografadas e cortar as linhas das tabelas",
               "uns 1,5 GB"),
    "handwriting": ("Leitor de letra manuscrita",
                    "os nomes escritos à mão; sem ele saem na leitura fraca do motor",
                    "uns 1 GB"),
}
TIER_ORDER = ("viewer", "engine", "handwriting")
# where kraken keeps the handwriting model; the same path as
# desembarque.secondreading.MODEL, written here because the launcher runs on
# a bare Python before anything is installed and imports nothing of the app
MODEL = Path.home() / ".cache" / "kraken" / "ppocrv6-hist" / "medium.safetensors"


def _site_has(root: Path, pkg: str) -> bool:
    venv = root / ".venv-ocr"
    if os.name == "nt":
        return (venv / "Lib" / "site-packages" / pkg).is_dir()
    return any(p.is_dir() for p in venv.glob(f"lib/python*/site-packages/{pkg}"))


def readiness(root: Path = ROOT, model: Path = MODEL) -> dict:
    """What is installed, by tier, read off the venv's site-packages: no
    interpreter is started, so the check is instant on every launch
    (Allan, 2026-10-17: "it's probably better to enforce/verify")."""
    py = venv_python(root) is not None
    return {
        "python": py,
        "viewer": py and all(_site_has(root, p) for p in ("pypdfium2", "numpy", "PIL")),
        "engine": py and _site_has(root, "paddleocr"),
        "handwriting": py and _site_has(root, "kraken") and model.exists(),
    }


def missing(ready: dict) -> list[str]:
    return [t for t in TIER_ORDER if not ready.get(t)]


def serve_command(python: Path, root: Path, folder: Path, port: int) -> list[str]:
    """The server, on this folder, on this port, not opening a browser of its
    own — the launcher opens one when the port answers."""
    return [str(python), str(root / "scripts" / "serve.py"),
            "--root", str(folder), "--port", str(port), "--no-open"]


def install_command(root: Path = ROOT, tiers=TIER_ORDER) -> list[list[str]]:
    """The commands that install these tiers, in order. `sys.executable` is
    the Python the launcher itself runs under, which is the one the person
    has. The venv is made only when it is not there: an install never does
    again what is done, and never downloads what pip has in its cache."""
    py = (root / ".venv-ocr" / "Scripts" / "python.exe" if os.name == "nt"
          else root / ".venv-ocr" / "bin" / "python")
    steps: list[list[str]] = []
    if not py.exists():
        steps.append([sys.executable, "-m", "venv", str(root / ".venv-ocr")])
        steps.append([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    if "viewer" in tiers:
        steps.append([str(py), "-m", "pip", "install", "-r", str(root / "requirements.txt")])
    if "engine" in tiers:
        steps.append([str(py), "-m", "pip", "install", "-r", str(root / "requirements-ocr.txt")])
    if "handwriting" in tiers:
        # the second reading of handwritten pages: kraken on a CPU-only torch
        # (the default torch pulls CUDA, five gigabytes nobody here needs), and
        # its PP-OCRv6 weights from Zenodo into ~/.cache/kraken
        # one command, with the CPU wheels as an extra index: installed in two
        # (CPU torch first, then kraken) pip resolved torch again from PyPI
        # and the CUDA build came back, 2026-10-16
        steps.append([str(py), "-m", "pip", "install", "--extra-index-url",
                      "https://download.pytorch.org/whl/cpu", "torch", "torchvision",
                      "-r", str(root / "requirements-kraken.txt")])
        steps.append([str(py), "-c", "from desembarque.secondreading import fetch_model; "
                                     "print(fetch_model())"])
    return steps


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


def stop_index(port: int) -> dict:
    """Stop the folder index; the document being read finishes first."""
    return _get(port, "/api/index/stop", post=True, timeout=20.0) or {"status": "unknown"}


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

Verificar a instalação
Ao abrir, a janela confere o que está instalado, em três partes: Leitura
(abrir, ver e buscar o que já foi transcrito; uns 100 MB), Motor de
transcrição (páginas datilografadas e as linhas das tabelas; uns 1,5 GB)
e Leitor de letra manuscrita (nomes à mão; uns 1 GB). Se faltar alguma,
aparece uma janela dizendo qual, com Instalar o que falta e Continuar
assim. Só a Leitura basta para usar PDFs e transcrições já prontos (num
pendrive, por exemplo); sem o motor nada é lido; sem o leitor de
manuscritos os nomes à mão saem na leitura fraca do motor. A instalação
só baixa o que falta e precisa de internet.

Ligar
Inicia o servidor (o programa que lê os PDFs) e abre a página no navegador,
em http://127.0.0.1:{port}/. Carregar os modelos leva 1 a 2 minutos; a
janela avisa quando está pronto. Fechar a aba do navegador desliga o
servidor; para voltar, clique em Ligar de novo.

Ler os PDFs da pasta ao ligar
Desligado por padrão: na página, cada documento tem o botão Transcrever
(ou só uma página). Ligado, transcreve os PDFs da pasta que ainda não
foram lidos. Cerca de 20 s por
página: uma lista de 9 páginas leva uns 3 minutos; os já lidos são pulados.
A linha de status diz em que documento está e quanto falta. Enquanto lê, o
computador fica lento.

Parar ao fim da página
Para a leitura da pasta assim que a página em leitura termina (uns 20 s).
O que já foi lido fica, página por página; Ligar de novo continua da
página seguinte. Para abortar e descartar o documento em andamento, use o
botão Abortar na caixa de progresso da página.

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
        # the tail of what the server printed, drained as it comes: a pipe
        # nobody reads is full after 64 KB (paddle's warnings, kraken's
        # INFO lines — a few pages), and the server then blocks on a print
        # and stops answering (Allan, 2026-10-17)
        self.log: collections.deque = collections.deque(maxlen=400)

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
        self.log.clear()
        self.proc = subprocess.Popen(self._command(folder, port),
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     cwd=str(ROOT), text=True, errors="replace", **kw)
        threading.Thread(target=self._drain, args=(self.proc,), daemon=True).start()
        deadline = time.time() + wait
        while time.time() < deadline:
            if self.proc.poll() is not None:
                time.sleep(0.2)          # let the drain catch the last lines
                self.last_error = (f"o servidor parou ao iniciar (código "
                                   f"{self.proc.returncode})\n" + self.tail())
                self.proc = None
                return False
            if is_up(port, timeout=0.5):
                return True
            time.sleep(0.25)
        self.last_error = "o servidor não respondeu a tempo"
        self.stop()
        return False

    def _drain(self, proc: subprocess.Popen) -> None:
        try:
            for line in proc.stdout:
                self.log.append(line.rstrip("\n"))
        except (OSError, ValueError):
            pass

    def tail(self, n: int = 12) -> str:
        return "\n".join(list(self.log)[-n:])

    def reap(self) -> str | None:
        """When the process has gone on its own — a crash, a kill from
        outside — a note saying so with its exit code and last lines, and
        the process forgotten so the window can start again. None while it
        runs or when there is nothing to reap. The window asks on every
        tick: it used to look at the process only when told to stop, and
        a server that had died left Ligar disabled for good."""
        p = self.proc
        if p is None or p.poll() is None:
            return None
        time.sleep(0.2)
        self.proc = None
        return (f"o servidor parou sozinho (código {p.returncode})"
                + ("\n" + self.tail() if self.log else ""))

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
