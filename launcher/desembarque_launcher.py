"""The window a person double-clicks.

Two buttons and a folder: *Ligar* starts the server on the folder of PDFs and
opens the page in the browser, *Desligar* stops the server — and closing the
window, or the browser tab, stops it too, so nothing is left running that
nobody can see.
*Ajuda* (or F1) opens one page that says what each button does and why.
At start the window checks what is installed, in three tiers (reading, the
engine, the handwriting reader), and when something is missing a check window
says which, what it is for, and offers to install only that — or to go on with
what there is, which with the first tier alone is a pendrive of PDFs already
transcribed. The install shows what it is doing, because a blank window for
ten minutes looks broken.

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
        self.index_on_start = BooleanVar(value=self.settings.get("index", False))
        # where to read and whether to load the models at start (Windows
        # test, 2026-10-17): the card when the install can use one
        self.device = StringVar(value=self.settings.get("device", "gpu"))
        self.warm = BooleanVar(value=self.settings.get("warm", True))
        self.card: dict | None = None
        self.card_known = False
        self.status = StringVar(value="")
        self.install_status = StringVar(value="")
        self.server = core.Server(self._command)
        self.events: queue.Queue = queue.Queue()
        self._installing = False
        self._stopping = False
        self._last_status: dict | None = None
        self._help: Toplevel | None = None
        self._check: Toplevel | None = None
        self._tiers: list[str] = []
        self._build()
        self._refresh()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<F1>", lambda _e: self.help())
        # something missing: the check window first, by itself
        if core.missing(core.readiness()):
            root.after(150, self.check)
        threading.Thread(target=self._status_worker, daemon=True).start()
        threading.Thread(target=lambda: self.events.put(("gpu", core.gpu())), daemon=True).start()
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
        self.b_check = ttk.Button(head, text="Verificar a instalação", command=self.check)
        self.b_check.pack(side=RIGHT, padx=(0, 6))

        top = ttk.LabelFrame(self.root, text="Pasta com os PDFs", padding=(10, 6))
        top.pack(fill=X, pady=(12, 8))
        ttk.Entry(top, textvariable=self.folder).pack(side=LEFT, fill=X, expand=True)
        ttk.Button(top, text="Escolher…", command=self.choose).pack(side=LEFT, padx=(8, 0))

        row = ttk.Frame(self.root)
        row.pack(fill=X, pady=(0, 8))
        self.b_start = ttk.Button(row, text="Ligar", command=self.start, style="Accent.TButton")
        self.b_stopidx = ttk.Button(row, text="Parar ao fim da página", command=self.stop_index)
        self.b_stop = ttk.Button(row, text="Desligar", command=self.stop)
        for b in (self.b_start, self.b_stopidx, self.b_stop):
            b.pack(side=LEFT, padx=(0, 6))
        how = ttk.LabelFrame(self.root, text="Como ler", padding=(10, 6))
        how.pack(fill=X, pady=(0, 8))
        self.card_line = ttk.Label(how, text="procurando placa de vídeo…", style="Muted.TLabel",
                                   wraplength=600, justify=LEFT)
        self.card_line.pack(anchor=W)
        dev = ttk.Frame(how)
        dev.pack(fill=X, pady=(4, 0))
        ttk.Label(dev, text="Ler usando:").pack(side=LEFT)
        self.r_gpu = ttk.Radiobutton(dev, text="placa de vídeo", variable=self.device, value="gpu",
                                     command=self._save)
        self.r_cpu = ttk.Radiobutton(dev, text="processador", variable=self.device, value="cpu",
                                     command=self._save)
        self.r_gpu.pack(side=LEFT, padx=(8, 0))
        self.r_cpu.pack(side=LEFT, padx=(8, 0))
        self.b_gpu = ttk.Button(dev, text="Instalar os leitores de GPU (uns 3 GB)",
                                command=lambda: self.install(["gpu"]))
        ttk.Checkbutton(how, text="Aquecer os leitores ao ligar (1 a 2 min; desligue para uma "
                                  "sessão só de busca)",
                        variable=self.warm, command=self._save).pack(anchor=W, pady=(4, 0))
        ttk.Checkbutton(how, text="Ler os PDFs da pasta ao ligar (os já lidos são pulados)",
                        variable=self.index_on_start, command=self._save).pack(anchor=W)
        self._device_lines()

        ttk.Label(self.root, textvariable=self.status, anchor=W, justify=LEFT,
                  wraplength=600, style="Muted.TLabel").pack(fill=X, pady=(0, 6))
        # the install: a bar that counts its commands and a line saying what
        # pip is downloading and how big it is — thirty minutes of log
        # alone looked like a hang (Windows test, 2026-10-17)
        self.install_box = ttk.Frame(self.root)
        self.install_bar = ttk.Progressbar(self.install_box, mode="determinate", maximum=1, value=0)
        self.install_bar.pack(fill=X)
        ttk.Label(self.install_box, textvariable=self.install_status, style="Muted.TLabel",
                  wraplength=600, justify=LEFT).pack(anchor=W)

        box = ttk.Frame(self.root)
        box.pack(fill=BOTH, expand=True)
        self.log = Text(box, height=12, state=DISABLED, wrap="word", relief="flat",
                        padx=8, pady=6, background="#f7f7f5", font=base)
        bar = ttk.Scrollbar(box, command=self.log.yview)
        self.log.configure(yscrollcommand=bar.set)
        self.log.pack(side=LEFT, fill=BOTH, expand=True)
        bar.pack(side=RIGHT, fill=Y)
        self._say("Escolha a pasta com os PDFs e clique em Ligar. "
                  "Ajuda (F1) explica cada botão; Verificar a instalação diz o que há.")

    def _device_lines(self, measured: float | None = None) -> None:
        """The radio's labels with the time per page — measured on this
        machine once the server has read one, the device's figure before —
        and the card's line; the card greyed when the readers cannot use it."""
        ready = core.readiness()
        usable = bool(self.card and self.card.get("cuda") and ready.get("gpu"))
        self.r_gpu.configure(text="placa de vídeo (" + core.page_estimate(
            "gpu", measured if self.device.get() == "gpu" else None) + ")",
            state=NORMAL if usable else DISABLED)
        self.r_cpu.configure(text="processador (" + core.page_estimate(
            "cpu", measured if self.device.get() == "cpu" else None) + ")")
        if not usable and self.device.get() == "gpu":
            self.device.set("cpu")
        if self.card_known:
            self.card_line.configure(text=core.describe_gpu(self.card, ready))
        if self.card and self.card.get("cuda") and not ready.get("gpu") and ready.get("engine") \
                and not self._installing:
            self.b_gpu.pack(side=LEFT, padx=(12, 0))
        else:
            self.b_gpu.pack_forget()

    def _say(self, line: str) -> None:
        self.log.configure(state=NORMAL)
        self.log.insert(END, line.rstrip() + "\n")
        self.log.see(END)
        self.log.configure(state=DISABLED)

    def _refresh(self) -> None:
        ready = core.readiness()
        installed = ready["viewer"]
        lacking = core.missing(ready)
        running = self.server.alive
        self.b_check.configure(state=DISABLED if self._installing else NORMAL)
        self.b_start.configure(state=NORMAL if installed and not running
                               and not self._stopping and not self._installing else DISABLED)
        self.b_stop.configure(state=NORMAL if running and not self._stopping else DISABLED)
        reading = running and (self._last_status or {}).get("status") == "running"
        self.b_stopidx.configure(state=NORMAL if reading and not self._stopping else DISABLED)
        if not installed and not self._installing:
            self.status.set("Nada instalado ainda: clique em Verificar a instalação.")
        elif lacking and not self._installing and not running:
            self.status.set("Falta: " + ", ".join(core.TIERS[t][0].lower() for t in lacking)
                            + ". Funciona com o que há; Verificar a instalação diz o que muda.")
        elif self._stopping:
            self.status.set("Desligando…")
        elif not running and not self._installing:
            self.status.set("Servidor parado.")

    # ---- actions ---------------------------------------------------------
    def _command(self, folder: Path, port: int) -> list[str]:
        py = core.venv_python()
        return core.serve_command(py, core.ROOT, folder, port, warm=bool(self.warm.get()))

    def choose(self) -> None:
        d = filedialog.askdirectory(title="Pasta com os PDFs das listas")
        if d:
            self.folder.set(d)
            self._save()

    def _save(self) -> None:
        core.save_settings(core.SETTINGS, {"folder": self.folder.get(),
                                           "port": self.port,
                                           "index": bool(self.index_on_start.get()),
                                           "device": self.device.get(),
                                           "warm": bool(self.warm.get())})

    def check(self) -> None:
        """The check window: what is installed, by tier, what each is for
        and costs, and what to do — install what is missing, or go on with
        what there is. Shown by itself at start when something is missing
        (Allan, 2026-10-17); nothing when all three are there."""
        if self._check is not None and self._check.winfo_exists():
            self._check.lift()
            return
        ready = core.readiness()
        lacking = core.missing(ready)
        top = Toplevel(self.root)
        top.title("Verificação da instalação — " + TITLE)
        top.geometry("560x420+%d+%d" % (self.root.winfo_rootx() + 50,
                                         self.root.winfo_rooty() + 50))
        top.configure(padx=16, pady=12)
        ttk.Label(top, text="O que está instalado", style="Title.TLabel").pack(anchor=W)
        for tier in core.TIER_ORDER:
            name, what, size = core.TIERS[tier]
            ok = ready[tier]
            row = ttk.Frame(top)
            row.pack(fill=X, pady=(8, 0))
            ttk.Label(row, text="✓" if ok else "✗", width=2,
                      foreground="#2a7" if ok else "#c33").pack(side=LEFT, anchor="n")
            ttk.Label(row, text=f"{name} — {'instalado' if ok else 'falta'} ({size})",
                      font=(nametofont("TkDefaultFont").cget("family"), 10, "bold")).pack(anchor=W)
            ttk.Label(row, text=what, style="Muted.TLabel", wraplength=480).pack(anchor=W, padx=(22, 0))
        note = ("Tudo instalado." if not lacking else
                "Dá para continuar com o que há: só a Leitura basta para abrir PDFs já "
                "transcritos (de um pendrive, por exemplo). Sem o motor nada novo é lido; "
                "sem o leitor de manuscritos os nomes à mão saem na leitura fraca do motor. "
                "A instalação baixa só o que falta e precisa de internet.")
        ttk.Label(top, text=note, wraplength=520, justify=LEFT).pack(anchor=W, pady=(14, 0))
        if self.card_known:
            ttk.Label(top, text=core.describe_gpu(self.card, ready), wraplength=520,
                      justify=LEFT, style="Muted.TLabel").pack(anchor=W, pady=(8, 0))
        foot = ttk.Frame(top)
        foot.pack(side="bottom", fill=X, pady=(10, 0))
        if ready["python"] and not self.server.alive and not self._installing:
            # "no traces left behind": the venv and the model are all there is
            ttk.Button(foot, text="Desinstalar…",
                       command=lambda: (top.destroy(), self.uninstall())).pack(side=LEFT, padx=(0, 6))
        if lacking:
            ttk.Button(foot, text="Instalar o que falta", style="Accent.TButton",
                       command=lambda: (top.destroy(), self.install(lacking))).pack(side=LEFT)
            if "viewer" in lacking and len(lacking) > 1:
                ttk.Button(foot, text="Instalar só a Leitura",
                           command=lambda: (top.destroy(), self.install(["viewer"]))).pack(side=LEFT, padx=(6, 0))
            b = ttk.Button(foot, text="Continuar assim", command=top.destroy)
            b.pack(side=RIGHT)
            if "viewer" in lacking:
                b.configure(state=DISABLED)   # nothing to go on with
        else:
            ttk.Button(foot, text="Fechar", command=top.destroy).pack(side=RIGHT)
        top.bind("<Escape>", lambda _e: top.destroy())
        self._check = top

    def uninstall(self) -> None:
        """Everything the install put on the machine, and nothing of the
        person's: the venv, the settings, and if wanted the model."""
        if self.server.alive or self._installing:
            messagebox.showinfo(TITLE, "Desligue o servidor primeiro.")
            return
        if not messagebox.askyesno(
                "Desinstalar — " + TITLE,
                "Apagar tudo o que foi instalado (a pasta .venv-ocr, uns 3 GB, e as "
                "configurações)?\n\nOs PDFs e as subpastas \"transcriptions\" são seus e "
                "não são tocados. Depois disto, basta apagar a pasta do programa."):
            return
        models = messagebox.askyesno(
            "Desinstalar — " + TITLE,
            "Apagar também o modelo de letra manuscrita baixado (~60 MB, em "
            "~/.cache/kraken)?\n\nNão: ele fica para uma reinstalação não baixar de novo.")
        gone = core.uninstall(models=models)
        self._say("Desinstalado: " + (", ".join(gone) if gone else "não havia nada."))
        self._refresh()
        self._device_lines()

    def install(self, tiers=None) -> None:
        self._tiers = list(tiers or core.missing(core.readiness()))
        if not self._tiers:
            return
        self._installing = True
        self._refresh()
        self._device_lines()
        names = {**{t: core.TIERS[t][0].lower() for t in core.TIERS}, "gpu": "leitores de GPU"}
        self.status.set("Instalando: " + ", ".join(names[t] for t in self._tiers)
                        + "… leva alguns minutos (uns 3 GB baixados).")
        self.install_status.set("")
        self.install_bar.configure(value=0, maximum=1)
        self.install_box.pack(fill=X, pady=(0, 6))
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self) -> None:
        cmds = core.install_command(tiers=self._tiers, gpu=self.card)
        for i, cmd in enumerate(cmds):
            self.events.put(("step", i, len(cmds), " ".join(cmd[-2:])))
            self.events.put(("log", "$ " + " ".join(cmd)))
            kw = {}
            if sys.platform == "win32":
                kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, errors="replace", cwd=str(core.ROOT), **kw)
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
        ok = self.server.start(folder, self.port, env=core.serve_env(self.device.get()))
        self.events.put(("started", ok, folder))

    def open(self) -> None:
        webbrowser.open(f"http://127.0.0.1:{self.port}/")

    def stop(self, why: str = "") -> None:
        """Off the UI thread: the server is told first and the page given a
        few seconds to hear, which is too long for a window to freeze."""
        if self._stopping:
            return
        if not self.server.alive:
            gone = self.server.reap()
            self._say(gone or "Servidor já estava parado.")
            self._refresh()
            return
        self._stopping = True
        self._refresh()
        threading.Thread(target=self._stop_worker, args=(why,), daemon=True).start()

    def stop_index(self) -> None:
        self._say("Parando: a página em leitura termina, o que já foi lido fica; Ligar de novo continua da seguinte.")
        self.b_stopidx.configure(state=DISABLED)
        threading.Thread(target=lambda: self.events.put(
            ("index-stopped", core.stop_index(self.port))), daemon=True).start()

    def _stop_worker(self, why: str) -> None:
        try:
            self.server.stop()
        finally:
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
                eng = core._get(self.port, "/api/engine", timeout=20.0)
                if eng:
                    self.events.put(("engine", eng))
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
        # a server that went away on its own: say so, forget it, and let
        # Ligar work again — the window used to notice only on Desligar
        gone = self.server.reap()
        if gone:
            self._say(gone)
            self._stopping = False
            self._refresh()
        elif not self.server.alive and self.server.proc is None \
                and str(self.b_stop["state"]) == NORMAL:
            self._refresh()
        self.root.after(POLL_MS, self._poll)

    def _handle(self, ev: tuple) -> None:
        kind = ev[0]
        if kind == "log":
            self._say(ev[1])
            said = core.describe_install_line(ev[1].rstrip())
            if said and self._installing:
                self.install_status.set(said)
        elif kind == "step":
            _, i, n, what = ev
            self.install_bar.configure(maximum=n, value=i)
            self.install_status.set(f"passo {i + 1} de {n}: {what}")
        elif kind == "gpu":
            self.card, self.card_known = ev[1], True
            self._device_lines()
            if self.card:
                self._say(core.describe_gpu(self.card, core.readiness()))
        elif kind == "engine":
            e = ev[1]
            self._device_lines(measured=e.get("page_s"))
            if e.get("warm") == "warming" and not getattr(self, "_said_warm", False):
                self._said_warm = True
                self._say("Aquecendo os leitores: carregando os modelos (1 a 2 min); a página diz quando estão prontos.")
            elif e.get("warm") == "warm" and getattr(self, "_said_warm", False):
                self._said_warm = False
                self._say("Leitores prontos." + (" Aviso: " + e["warm_error"] if e.get("warm_error") else ""))
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
            tail = self.server.tail(6)
            if "Traceback" in tail or "Error" in tail:
                self._say(tail)
            self._refresh()
        elif kind == "installed":
            self._installing = False
            self.install_box.pack_forget()
            still = core.missing(core.readiness())
            self._say(("Instalação concluída." if not still else
                       "Instalado; ainda falta " + ", ".join(core.TIERS[t][0].lower() for t in still) + ".")
                      if ev[1] else "A instalação falhou — veja as linhas acima.")
            if ev[1] and "gpu" in self._tiers and core.readiness().get("gpu"):
                self.device.set("gpu")
                self._save()
            self._refresh()
            self._device_lines()
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
