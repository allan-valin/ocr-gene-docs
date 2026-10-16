"""The window a person double-clicks.

Three buttons and a folder: *Iniciar* starts the server on the folder of PDFs,
*Abrir no navegador* opens the page, *Parar* stops the server — and closing
the window stops it too, so nothing is left running that nobody can see.
The first time, with nothing installed, the only button is *Instalar*, which
makes the virtual environment and installs the recogniser, showing what it is
doing, because a blank window for ten minutes looks broken.

Only the standard library: this has to run on whatever Python the person
installed, before anything else is installed.
"""
from __future__ import annotations

import queue
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from tkinter import (BOTH, DISABLED, END, LEFT, NORMAL, RIGHT, W, X, Checkbutton,
                     BooleanVar, Button, Entry, Frame, Label, StringVar, Text, Tk,
                     filedialog, messagebox)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from launcher import core  # noqa: E402

TITLE = "Desembarque"
POLL_MS = 2000


class Window:
    def __init__(self, root: Tk) -> None:
        self.root = root
        root.title(TITLE)
        root.minsize(560, 360)
        self.settings = core.load_settings()
        self.folder = StringVar(value=self.settings.get("folder", ""))
        self.port = int(self.settings.get("port", core.DEFAULT_PORT))
        self.index_on_start = BooleanVar(value=self.settings.get("index", True))
        self.status = StringVar(value="")
        self.server = core.Server(self._command)
        self.events: queue.Queue = queue.Queue()
        self._installing = False
        self._build()
        self._refresh()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(POLL_MS, self._poll)

    # ---- layout ----------------------------------------------------------
    def _build(self) -> None:
        pad = {"padx": 10, "pady": 4}
        top = Frame(self.root)
        top.pack(fill=X, **pad)
        Label(top, text="Pasta com os PDFs:").pack(side=LEFT)
        Entry(top, textvariable=self.folder).pack(side=LEFT, fill=X, expand=True, padx=6)
        Button(top, text="Escolher…", command=self.choose).pack(side=LEFT)

        row = Frame(self.root)
        row.pack(fill=X, **pad)
        self.b_install = Button(row, text="Instalar (uma vez)", command=self.install)
        self.b_start = Button(row, text="Iniciar", command=self.start)
        self.b_open = Button(row, text="Abrir no navegador", command=self.open)
        self.b_stop = Button(row, text="Parar", command=self.stop)
        for b in (self.b_install, self.b_start, self.b_open, self.b_stop):
            b.pack(side=LEFT, padx=3)
        Checkbutton(row, text="Indexar a pasta ao iniciar",
                    variable=self.index_on_start).pack(side=RIGHT)

        Label(self.root, textvariable=self.status, anchor=W, justify=LEFT,
              wraplength=540).pack(fill=X, **pad)
        self.log = Text(self.root, height=12, state=DISABLED, wrap="word")
        self.log.pack(fill=BOTH, expand=True, **pad)
        self._say("Escolha a pasta com os PDFs e carregue em Iniciar.")

    def _say(self, line: str) -> None:
        self.log.configure(state=NORMAL)
        self.log.insert(END, line.rstrip() + "\n")
        self.log.see(END)
        self.log.configure(state=DISABLED)

    def _refresh(self) -> None:
        installed = core.venv_python() is not None
        running = self.server.alive
        self.b_install.configure(state=NORMAL if not installed and not self._installing else DISABLED)
        self.b_start.configure(state=NORMAL if installed and not running else DISABLED)
        self.b_open.configure(state=NORMAL if running else DISABLED)
        self.b_stop.configure(state=NORMAL if running else DISABLED)
        if not installed and not self._installing:
            self.status.set("Nada instalado ainda: carregue em Instalar (uma vez). "
                            "Demora alguns minutos e precisa de internet.")
        elif not running and not self._installing:
            self.status.set("Servidor parado.")

    # ---- actions ---------------------------------------------------------
    def _command(self, folder: Path, port: int) -> list[str]:
        py = core.venv_python()
        return core.serve_command(py, core.ROOT, folder, port)

    def choose(self) -> None:
        d = filedialog.askdirectory(title="Pasta com os PDFs das listas")
        if d:
            self.folder.set(d)
            self._save()

    def _save(self) -> None:
        core.save_settings(core.SETTINGS, {"folder": self.folder.get(),
                                           "port": self.port,
                                           "index": bool(self.index_on_start.get())})

    def install(self) -> None:
        self._installing = True
        self._refresh()
        self.status.set("A instalar… isto demora alguns minutos.")
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self) -> None:
        for cmd in core.install_command():
            self.events.put(("log", "$ " + " ".join(cmd)))
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, cwd=str(core.ROOT))
            for line in p.stdout:
                self.events.put(("log", line))
            if p.wait() != 0:
                self.events.put(("installed", False))
                return
        self.events.put(("installed", True))

    def start(self) -> None:
        folder = Path(self.folder.get() or "").expanduser()
        if not folder.is_dir():
            messagebox.showwarning(TITLE, "Escolha primeiro a pasta com os PDFs.")
            return
        self._save()
        self.status.set("A arrancar o servidor…")
        self.b_start.configure(state=DISABLED)
        threading.Thread(target=self._start_worker, args=(folder,), daemon=True).start()

    def _start_worker(self, folder: Path) -> None:
        ok = self.server.start(folder, self.port)
        self.events.put(("started", ok, folder))

    def open(self) -> None:
        webbrowser.open(f"http://127.0.0.1:{self.port}/")

    def stop(self) -> None:
        self.server.stop()
        self._say("Servidor parado.")
        self._refresh()

    def close(self) -> None:
        self.server.stop()
        self.root.destroy()

    # ---- the clock -------------------------------------------------------
    def _poll(self) -> None:
        try:
            while True:
                ev = self.events.get_nowait()
                self._handle(ev)
        except queue.Empty:
            pass
        if self.server.alive:
            st = core.index_status(self.port)
            self.status.set("A correr em http://127.0.0.1:%d — %s"
                            % (self.port, core.describe_index(st)))
        elif self.server.proc is None and self.b_stop["state"] == NORMAL:
            self._refresh()
        self.root.after(POLL_MS, self._poll)

    def _handle(self, ev: tuple) -> None:
        kind = ev[0]
        if kind == "log":
            self._say(ev[1])
        elif kind == "installed":
            self._installing = False
            self._say("Instalação concluída." if ev[1]
                      else "A instalação falhou — veja as linhas acima.")
            self._refresh()
        elif kind == "started":
            ok, folder = ev[1], ev[2]
            if not ok:
                self._say(self.server.last_error)
                self.status.set("Não arrancou.")
                self._refresh()
                return
            self._say(f"Servidor a correr sobre {folder}")
            self._refresh()
            self.open()
            if self.index_on_start.get():
                st = core.start_index(self.port)
                self._say("Indexação iniciada: " + core.describe_index(st))


def main() -> int:
    root = Tk()
    Window(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
