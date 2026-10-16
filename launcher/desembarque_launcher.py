"""The window a person double-clicks.

Two buttons and a folder: *Ligar* starts the server on the folder of PDFs and
opens the page in the browser, *Desligar* stops the server — and closing the
window, or the browser tab, stops it too, so nothing is left running that
nobody can see.
*Ajuda* (or F1) opens one page that says what each button does and why.
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
import time
import webbrowser
from pathlib import Path
from tkinter import (BOTH, DISABLED, END, LEFT, NORMAL, RIGHT, W, X, Y,
                     BooleanVar, StringVar, Text, Tk, Toplevel, filedialog,
                     messagebox, ttk)
from tkinter.font import nametofont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from launcher import core  # noqa: E402

TITLE = "Desembarque"
POLL_MS = 2000


class Window:
    def __init__(self, root: Tk) -> None:
        self.root = root
        root.title(TITLE)
        root.minsize(680, 420)
        self.settings = core.load_settings()
        self.folder = StringVar(value=self.settings.get("folder", ""))
        self.port = int(self.settings.get("port", core.DEFAULT_PORT))
        self.index_on_start = BooleanVar(value=self.settings.get("index", True))
        self.status = StringVar(value="")
        self.server = core.Server(self._command)
        self.events: queue.Queue = queue.Queue()
        self._installing = False
        self._stopping = False
        self._last_status: dict | None = None
        self._help: Toplevel | None = None
        self._build()
        self._refresh()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<F1>", lambda _e: self.help())
        threading.Thread(target=self._status_worker, daemon=True).start()
        root.after(POLL_MS, self._poll)

    # ---- layout ----------------------------------------------------------
    def _build(self) -> None:
        """Plain ttk, themed: a title, the folder, one row of buttons, the
        status line, the log. Only what the standard library ships, since this
        runs before anything is installed."""
        style = ttk.Style(self.root)
        if sys.platform.startswith("linux") and "clam" in style.theme_names():
            style.theme_use("clam")
        base = nametofont("TkDefaultFont")
        base.configure(size=10)
        self.root.option_add("*Font", base)
        style.configure("Title.TLabel", font=(base.cget("family"), 15, "bold"))
        style.configure("Muted.TLabel", foreground="#555")
        style.configure("Accent.TButton", font=(base.cget("family"), 10, "bold"))
        style.configure("TButton", padding=(10, 5))
        self.root.configure(padx=16, pady=12)

        head = ttk.Frame(self.root)
        head.pack(fill=X)
        ttk.Label(head, text=TITLE, style="Title.TLabel").pack(side=LEFT)
        ttk.Label(head, text="listas de passageiros, lidas e pesquisáveis",
                  style="Muted.TLabel").pack(side=LEFT, padx=(10, 0), pady=(6, 0))
        self.b_help = ttk.Button(head, text="Ajuda (F1)", command=self.help)
        self.b_help.pack(side=RIGHT)

        top = ttk.LabelFrame(self.root, text="Pasta com os PDFs", padding=(10, 6))
        top.pack(fill=X, pady=(12, 8))
        ttk.Entry(top, textvariable=self.folder).pack(side=LEFT, fill=X, expand=True)
        ttk.Button(top, text="Escolher…", command=self.choose).pack(side=LEFT, padx=(8, 0))

        row = ttk.Frame(self.root)
        row.pack(fill=X, pady=(0, 8))
        self.b_install = ttk.Button(row, text="Instalar (uma vez)", command=self.install)
        self.b_start = ttk.Button(row, text="Ligar", command=self.start, style="Accent.TButton")
        self.b_stopidx = ttk.Button(row, text="Parar a leitura", command=self.stop_index)
        self.b_stop = ttk.Button(row, text="Desligar", command=self.stop)
        for b in (self.b_install, self.b_start, self.b_stopidx, self.b_stop):
            b.pack(side=LEFT, padx=(0, 6))
        ttk.Checkbutton(self.root, text="Ler os PDFs da pasta ao ligar (os já lidos são pulados)",
                        variable=self.index_on_start).pack(anchor=W, pady=(0, 8))

        ttk.Label(self.root, textvariable=self.status, anchor=W, justify=LEFT,
                  wraplength=600, style="Muted.TLabel").pack(fill=X, pady=(0, 6))

        box = ttk.Frame(self.root)
        box.pack(fill=BOTH, expand=True)
        self.log = Text(box, height=12, state=DISABLED, wrap="word", relief="flat",
                        padx=8, pady=6, background="#f7f7f5", font=base)
        bar = ttk.Scrollbar(box, command=self.log.yview)
        self.log.configure(yscrollcommand=bar.set)
        self.log.pack(side=LEFT, fill=BOTH, expand=True)
        bar.pack(side=RIGHT, fill=Y)
        self._say("Escolha a pasta com os PDFs e clique em Ligar. "
                  "Ajuda (F1) explica cada botão.")

    def _say(self, line: str) -> None:
        self.log.configure(state=NORMAL)
        self.log.insert(END, line.rstrip() + "\n")
        self.log.see(END)
        self.log.configure(state=DISABLED)

    def _refresh(self) -> None:
        installed = core.venv_python() is not None
        running = self.server.alive
        self.b_install.configure(state=NORMAL if not installed and not self._installing else DISABLED)
        self.b_start.configure(state=NORMAL if installed and not running
                               and not self._stopping else DISABLED)
        self.b_stop.configure(state=NORMAL if running and not self._stopping else DISABLED)
        reading = running and (self._last_status or {}).get("status") == "running"
        self.b_stopidx.configure(state=NORMAL if reading and not self._stopping else DISABLED)
        if not installed and not self._installing:
            self.status.set("Nada instalado ainda: clique em Instalar (uma vez). "
                            "Demora alguns minutos e precisa de internet.")
        elif self._stopping:
            self.status.set("Desligando…")
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
        self.status.set("Instalando… isto leva alguns minutos.")
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
        self.status.set("Iniciando o servidor…")
        self.b_start.configure(state=DISABLED)
        threading.Thread(target=self._start_worker, args=(folder,), daemon=True).start()

    def _start_worker(self, folder: Path) -> None:
        ok = self.server.start(folder, self.port)
        self.events.put(("started", ok, folder))

    def open(self) -> None:
        webbrowser.open(f"http://127.0.0.1:{self.port}/")

    def stop(self, why: str = "") -> None:
        """Off the UI thread: the server is told first and the page given a
        few seconds to hear, which is too long for a window to freeze."""
        if self._stopping or not self.server.alive:
            return
        self._stopping = True
        self._refresh()
        threading.Thread(target=self._stop_worker, args=(why,), daemon=True).start()

    def stop_index(self) -> None:
        self._say("Parando a leitura: o documento em leitura termina antes.")
        self.b_stopidx.configure(state=DISABLED)
        threading.Thread(target=lambda: self.events.put(
            ("index-stopped", core.stop_index(self.port))), daemon=True).start()

    def _stop_worker(self, why: str) -> None:
        self.server.stop()
        self.events.put(("stopped", why))

    def help(self) -> None:
        """One window, reused: F1 twice does not open two."""
        if self._help is not None and self._help.winfo_exists():
            self._help.lift()
            return
        top = Toplevel(self.root)
        top.title("Ajuda — " + TITLE)
        # Smaller than the main window and set off from it: the same size on
        # top of it read as the program itself, and closing it looked like
        # closing the program (Allan, 2026-10-16). And its own Fechar button.
        top.geometry("520x540+%d+%d" % (self.root.winfo_rootx() + 70,
                                         self.root.winfo_rooty() + 70))
        top.minsize(420, 360)
        top.configure(padx=8, pady=8)
        foot = ttk.Frame(top)
        foot.pack(side="bottom", fill=X, pady=(8, 0))
        ttk.Button(foot, text="Fechar a ajuda", command=top.destroy).pack(side=RIGHT)
        text = Text(top, wrap="word", padx=14, pady=10, relief="flat",
                    background="#fbfbf9", font=nametofont("TkDefaultFont"))
        bold = nametofont("TkDefaultFont").copy()
        bold.configure(weight="bold", size=11)
        text.tag_configure("h", font=bold, spacing1=10, spacing3=2)
        for para in core.help_text(self.port).split("\n\n"):
            head, _, body = para.partition("\n")
            text.insert(END, head + "\n", "h")
            text.insert(END, body.replace("\n", " ").strip() + "\n")
        text.configure(state=DISABLED)
        bar = ttk.Scrollbar(top, command=text.yview)
        text.configure(yscrollcommand=bar.set)
        text.pack(side=LEFT, fill=BOTH, expand=True)
        bar.pack(side=RIGHT, fill=Y)
        top.bind("<Escape>", lambda _e: top.destroy())
        self._help = top

    def close(self) -> None:
        self.server.stop(pause=1.5)
        self.root.destroy()

    # ---- the clock -------------------------------------------------------
    def _status_worker(self) -> None:
        """Asks the server how the index is going, off the UI thread: with
        the recogniser busy an answer takes seconds, and a window that waits
        for it freezes, which is what a person reads as broken."""
        while True:
            if self.server.alive and not self._stopping:
                st = core.index_status(self.port)
                if st.get("status") == "unknown" and self._last_status:
                    st = {**self._last_status, "status": "unknown"}
                self.events.put(("status", st))
                # the browser tab closed: the server goes with it
                if core.browser_gone(core.clients(self.port)):
                    self.events.put(("gone",))
            time.sleep(POLL_MS / 1000)

    def _poll(self) -> None:
        try:
            while True:
                ev = self.events.get_nowait()
                self._handle(ev)
        except queue.Empty:
            pass
        if not self.server.alive and self.server.proc is None \
                and str(self.b_stop["state"]) == NORMAL:
            self._refresh()
        self.root.after(POLL_MS, self._poll)

    def _handle(self, ev: tuple) -> None:
        kind = ev[0]
        if kind == "log":
            self._say(ev[1])
        elif kind == "status":
            st = ev[1]
            if st.get("status") != "unknown":
                self._last_status = st
                self._refresh()
            if self.server.alive:
                line = core.describe_index(st)
                if st.get("status") == "unknown" and self._last_status:
                    line = (core.describe_index(self._last_status)
                            + " · sem resposta do servidor neste momento")
                self.status.set("Ligado em http://127.0.0.1:%d — %s"
                                % (self.port, line))
        elif kind == "index-stopped":
            self._say("Leitura parada: " + core.describe_index(ev[1]))
        elif kind == "gone":
            if self.server.alive and not self._stopping:
                self._say("A aba do navegador foi fechada: desligando o servidor.")
                self.stop()
        elif kind == "stopped":
            self._stopping = False
            self._say("Servidor parado." + (" " + ev[1] if ev[1] else ""))
            self._refresh()
        elif kind == "installed":
            self._installing = False
            self._say("Instalação concluída." if ev[1]
                      else "A instalação falhou — veja as linhas acima.")
            self._refresh()
        elif kind == "started":
            ok, folder = ev[1], ev[2]
            if not ok:
                self._say(self.server.last_error)
                self.status.set("Não iniciou.")
                self._refresh()
                return
            self._say(f"Servidor ligado sobre {folder}; abrindo a página no navegador.")
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
