"""The launcher a person double-clicks: it starts the server, opens the
browser, and stops the server — and nothing in here needs a window."""
import json
import os
import socket
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from launcher import core  # noqa: E402

STUB = Path(__file__).parent / "stub_server.py"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_the_engine_venv_is_found_by_platform(tmp_path):
    assert core.venv_python(tmp_path) is None
    exe = tmp_path / ".venv-ocr" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    assert core.venv_python(tmp_path) == exe


def test_the_server_is_started_in_the_venv_on_the_chosen_folder(tmp_path):
    cmd = core.serve_command(Path("/v/python"), tmp_path, Path("/scans"), 8765)
    assert cmd[0] == "/v/python"
    assert cmd[1].endswith("serve.py")
    assert "--root" in cmd and cmd[cmd.index("--root") + 1] == "/scans"
    assert cmd[cmd.index("--port") + 1] == "8765"
    assert "--no-open" in cmd   # the launcher opens the browser itself


def test_nothing_answers_before_the_server_is_up():
    assert core.is_up(free_port(), timeout=0.2) is False


def test_start_waits_for_the_port_and_stop_frees_it(tmp_path):
    port = free_port()
    srv = core.Server(lambda folder, p: [sys.executable, str(STUB), str(p)])
    assert srv.start(tmp_path, port, wait=10) is True
    assert srv.alive and core.is_up(port)
    assert core.index_status(port)["status"] == "idle"
    assert core.start_index(port)["status"] == "running"
    srv.stop()
    assert not srv.alive
    deadline = time.time() + 5
    while core.is_up(port, timeout=0.2) and time.time() < deadline:
        time.sleep(0.1)
    assert not core.is_up(port, timeout=0.2)


def test_a_server_that_dies_at_once_is_reported_not_waited_for(tmp_path):
    srv = core.Server(lambda folder, p: [sys.executable, "-c", "raise SystemExit(3)"])
    t0 = time.time()
    assert srv.start(tmp_path, free_port(), wait=10) is False
    assert time.time() - t0 < 5
    assert "3" in srv.last_error


def test_the_index_bar_speaks_hours_not_percentages():
    assert core.describe_index({"status": "idle"}) == "nada para indexar ainda"
    s = core.describe_index({"status": "running", "done": 3, "skipped": 2,
                             "total": 50, "eta_s": 7200, "failed": 0})
    assert "5 de 50" in s and "2 h" in s
    s = core.describe_index({"status": "done", "done": 48, "skipped": 2,
                             "total": 50, "eta_s": None, "failed": 1})
    assert "50 de 50" in s and "1 falhou" in s


def test_settings_remember_the_folder(tmp_path):
    f = tmp_path / "settings.json"
    assert core.load_settings(f) == {}
    core.save_settings(f, {"folder": "/x", "port": 8765})
    assert json.loads(f.read_text())["folder"] == "/x"
    assert core.load_settings(f)["port"] == 8765


def test_the_first_document_shows_its_name_and_the_clock_before_any_eta():
    """Allan watched the window for minutes on a folder of five PDFs and saw
    nothing move: the first document takes 3+ min (nine pages, the engine
    loading, another job on the machine), and until it is done there is no
    ETA to print. The line names the document and says how long it has been
    at it, so a person can tell working from stuck."""
    s = core.describe_index({"status": "running", "done": 0, "skipped": 0,
                             "total": 5, "eta_s": None, "failed": 0,
                             "elapsed_s": 150,
                             "current": "BR_RJANRIO_BS_0_RPV_ENT_015033_d0001de0001.pdf"})
    assert "0 de 5" in s
    assert "BR_RJANRIO_BS_0_RPV_ENT_015033" in s
    assert "há 3 min" in s or "há 2 min" in s


def test_the_server_is_given_three_minutes_to_load_its_models():
    import inspect
    assert inspect.signature(core.Server.start).parameters["wait"].default >= 180


def test_the_help_says_what_each_button_does_and_why():
    """Allan: the buttons do not say what 'Iniciar' starts or what 'Parar'
    stops. The help is one page a person reaches with F1 or the Ajuda button,
    and it names every button, what it does, why it exists, and how long
    things take."""
    h = core.help_text(port=8765)
    for word in ("Verificar a instalação", "Ligar", "Desligar",
                 "Ler os PDFs", "127.0.0.1:8765", "PDF", "35 s", "3 min", "fechar a janela",
                 "Aquecer", "Desinstalar"):
        assert word in h, word
    assert len(h) < 4000


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="no display")
def test_f1_opens_the_help_window():
    from tkinter import Tk, Toplevel
    import launcher.desembarque_launcher as dl
    root = Tk()
    root.withdraw()
    try:
        w = dl.Window(root)
        assert root.bind("<F1>"), "F1 is bound on the window"
        w.help()
        root.update()
        tops = [c for c in root.winfo_children() if isinstance(c, Toplevel)]
        assert len(tops) == 1
        w.help()
        root.update()
        tops = [c for c in root.winfo_children() if isinstance(c, Toplevel)]
        assert len(tops) == 1, "a second F1 does not open a second window"
        assert w.b_start.cget("text") == "Ligar"
        assert w.b_stop.cget("text") == "Desligar"
    finally:
        root.destroy()


def test_a_server_too_busy_to_answer_is_not_reported_as_nothing_to_index():
    """Measured with the index running: /api/index took 2 to 20 s to answer
    (four recogniser threads hold the interpreter). The launcher's 2 s poll
    timed out, got nothing, and printed 'nada a indexar ainda' for minutes
    while five documents were being read. No answer is 'busy', not 'idle'."""
    assert "ocupado" in core.describe_index({"status": "unknown"})
    assert core.describe_index({"status": "idle"}) == "nada para indexar ainda"
    import inspect
    assert inspect.signature(core.index_status).parameters["timeout"].default >= 15


def test_the_install_brings_the_second_reading_with_it():
    """A launcher install read cursive pages with the engine alone until
    2026-10-16: kraken and its model lived in a venv on one machine. The
    install now puts kraken on a CPU-only torch into the same venv and
    fetches the weights, so the friend's copy reads what Allan's reads."""
    cmds = [" ".join(c) for c in core.install_command(Path("/r"))]
    kraken = [c for c in cmds if "requirements-kraken.txt" in c]
    assert len(kraken) == 1
    assert "download.pytorch.org/whl/cpu" in kraken[0] and " torch " in kraken[0], \
        "torch and kraken in one resolution, or pip brings the CUDA torch back"
    assert any("fetch_model" in c for c in cmds)
    assert cmds.index(next(c for c in cmds if "fetch_model" in c)) == len(cmds) - 1


def test_the_help_window_has_its_own_close_button_and_is_not_the_main_window():
    """Allan, 2026-10-16: the help opened as a window the same size as the
    main one, and closing it looked like closing the program. The help is
    smaller, offset, and carries a *Fechar a ajuda* button of its own."""
    import inspect
    import launcher.desembarque_launcher as dl
    src = inspect.getsource(dl.Window.help)
    assert "Fechar a ajuda" in src
    assert "geometry(" in src


def test_one_button_starts_the_server_and_opens_the_page():
    """Allan: Ligar opened the browser, then Abrir a página opened a second
    one. One button: Ligar starts and opens; there is no Abrir a página."""
    import inspect
    import launcher.desembarque_launcher as dl
    src = inspect.getsource(dl.Window._build)
    assert "Abrir a página" not in src
    h = core.help_text()
    assert "Abrir a página" not in h
    assert "fechar a aba" in h.lower() or "fecha a aba" in h.lower()


def test_the_server_stops_when_the_browser_tab_is_closed():
    """The page says goodbye when its tab closes (and keeps saying hello
    while it is open). Gone is: a goodbye with no hello after it, once the
    grace for a reload has passed — or no hello at all for minutes, when
    the browser died without a word. Never gone before a hello was ever
    heard: the browser takes a while to open."""
    gone = core.browser_gone
    assert not gone({"seen_s": None, "left_s": None})
    assert not gone({"seen_s": 3.0, "left_s": None})
    # the tab closed 2 s ago: a reload may still be on its way
    assert not gone({"seen_s": 2.5, "left_s": 2.0})
    # closed 30 s ago and nothing since
    assert gone({"seen_s": 31.0, "left_s": 30.0})
    # closed 30 s ago, but a page said hello since (a reload, another tab)
    assert not gone({"seen_s": 4.0, "left_s": 30.0})
    # no goodbye, but silent for five minutes: the browser is gone
    assert gone({"seen_s": 300.0, "left_s": None})
    # a background tab is throttled to a beat a minute: not gone
    assert not gone({"seen_s": 70.0, "left_s": None})


def test_stopping_tells_the_page_first():
    """Desligar cannot close a tab the launcher did not open through a
    script, so the page is told to show that the server is gone before
    the process is killed, instead of a frozen page."""
    import inspect
    src = inspect.getsource(core.Server.stop)
    assert "shutdown" in src


def test_the_reading_can_be_stopped_from_the_launcher():
    """Allan: "I can't stop the indexing anywhere with the browser or
    launcher". A button on the window, live while the index runs."""
    import inspect
    import launcher.desembarque_launcher as dl
    assert callable(core.stop_index)
    src = inspect.getsource(dl.Window._build)
    assert "Parar ao fim da página" in src


def test_readiness_is_three_tiers_and_the_install_does_only_what_is_missing(tmp_path):
    """Allan, 2026-10-17: "why is Completar a instalação even an option for
    me? I supposedly already have everything" — his engine venv had no
    kraken, and nothing on screen said what was there. The launcher checks
    three tiers and says each: reading (open, see, search what is already
    transcribed: the server needs pypdfium2, numpy, Pillow), the engine,
    the handwriting reader. A pendrive with PDFs and their transcriptions
    on a new PC needs the first tier only. The install does the missing
    tiers, never the whole thing again."""
    model = tmp_path / "medium.safetensors"
    r = core.readiness(tmp_path, model=model)
    assert r == {"python": False, "viewer": False, "engine": False, "handwriting": False,
                 "gpu": False}
    assert core.missing(r) == ["viewer", "engine", "handwriting"]
    venv = tmp_path / ".venv-ocr"
    site = venv / "lib" / "python3.12" / "site-packages"
    site.mkdir(parents=True)
    (venv / "bin").mkdir()
    (venv / "bin" / "python").write_text("")
    for pkg in ("pypdfium2", "numpy", "PIL"):
        (site / pkg).mkdir()
    r = core.readiness(tmp_path, model=model)
    assert r["python"] and r["viewer"] and not r["engine"] and not r["handwriting"]
    assert core.missing(r) == ["engine", "handwriting"]
    (site / "paddleocr").mkdir()
    (site / "kraken").mkdir()
    assert core.missing(core.readiness(tmp_path, model=model)) == ["handwriting"], "no model file yet"
    model.write_bytes(b"x")
    assert core.missing(core.readiness(tmp_path, model=model)) == []

    cmds = [" ".join(c) for c in core.install_command(tmp_path, tiers=["viewer"])]
    assert any("venv" in c for c in cmds) and any("requirements.txt" in c for c in cmds)
    assert not any("requirements-ocr" in c or "kraken" in c for c in cmds)
    cmds = [" ".join(c) for c in core.install_command(tmp_path, tiers=["handwriting"])]
    assert len(cmds) == 2 and "requirements-kraken.txt" in cmds[0] and "fetch_model" in cmds[1]
    assert not any("venv " in c for c in cmds), "a venv that exists is not made again"
    cmds = [" ".join(c) for c in core.install_command(tmp_path, tiers=["engine", "handwriting"])]
    assert "requirements-ocr.txt" in cmds[0] and "requirements-kraken.txt" in cmds[1]


def test_each_tier_says_what_it_is_for_and_what_it_costs():
    for tier in ("viewer", "engine", "handwriting"):
        name, what, size = core.TIERS[tier]
        assert name and what and ("MB" in size or "GB" in size)
    h = core.help_text()
    assert "Verificar a instalação" in h and "Completar" not in h.split("Verificar a instalação")[0]


def test_a_chatty_server_does_not_hang_on_its_own_output(tmp_path):
    """The launcher piped the server's stdout and never read it: after
    64 KB of paddle warnings and kraken INFO lines (a few pages) the
    server blocked on a print, stopped answering, and the window sat on
    "Desligando…" (Allan, 2026-10-17). The output is drained as it comes
    and its tail kept for the window."""
    port = free_port()
    srv = core.Server(lambda folder, p: [sys.executable, str(STUB), str(p), "--chatty"])
    try:
        assert srv.start(tmp_path, port, wait=15) is True
        assert core.is_up(port)
        assert any("line 3999" in ln for ln in srv.log), "the tail of what it said is kept"
        assert len(srv.log) <= 400
    finally:
        srv.stop(pause=0)


def test_a_server_that_dies_on_its_own_is_noticed_and_the_window_can_start_again(tmp_path):
    """The server went away (a crash, a kill from outside) and the window
    kept Ligar disabled and Desligar doing nothing for minutes: it only
    looked at the process when it was asked to stop. `reap` says the
    process is gone, with its exit code and last lines, and clears it."""
    port = free_port()
    srv = core.Server(lambda folder, p: [sys.executable, str(STUB), str(p), "--die-after", "0.5"])
    assert srv.start(tmp_path, port, wait=15) is True
    assert srv.reap() is None, "alive: nothing to reap"
    deadline = time.time() + 6
    while srv.alive and time.time() < deadline:
        time.sleep(0.1)
    assert not srv.alive
    note = srv.reap()
    assert note and "7" in note
    assert srv.proc is None
    assert srv.reap() is None


# ---- Windows test, 2026-10-17 (docs/WINDOWS-TEST-2026-10-17.md) ------------

def test_an_nvidia_card_is_found_through_nvidia_smi_and_its_driver_judged():
    """Allan's Windows laptop has an RTX 4050 and the launcher installed
    the CPU wheels: a page took three minutes instead of half a one. The
    launcher asks nvidia-smi, which the driver installs on every system,
    and says whether the driver is new enough for the CUDA 13 wheels."""
    smi = lambda: "NVIDIA GeForce RTX 4050 Laptop GPU, 595.99.02\n"
    g = core.gpu(query=smi)
    assert g == {"vendor": "nvidia", "name": "NVIDIA GeForce RTX 4050 Laptop GPU",
                 "driver": "595.99.02", "cuda": True}
    old = core.gpu(query=lambda: "NVIDIA GeForce GTX 1060, 552.44")
    assert old["cuda"] is False, "CUDA 13 wants a 580 driver"
    assert core.gpu(query=lambda: None) is None
    assert core.gpu(query=lambda: "") is None


def test_the_install_takes_the_cuda_wheels_when_the_card_can_use_them():
    """Device choice is the install's, never a flag's (engine_paddle.device_for):
    so the install is where the card has to be seen. With an NVIDIA card and
    a driver for it, torch comes from the cu130 index and paddle is the
    GPU build from PaddlePaddle's cu130 index, in the same .venv-ocr."""
    card = {"vendor": "nvidia", "name": "x", "driver": "595.99.02", "cuda": True}
    cmds = [" ".join(c) for c in core.install_command(Path("/r"), gpu=card)]
    kraken = [c for c in cmds if "requirements-kraken.txt" in c]
    assert len(kraken) == 1 and "whl/cu130" in kraken[0] and "whl/cpu" not in kraken[0]
    gpu = [c for c in cmds if "paddlepaddle-gpu" in c]
    assert len(gpu) == 1 and "packages/stable/cu130" in gpu[0]
    assert cmds.index(gpu[0]) < cmds.index(next(c for c in cmds if "paddleocr" in c)), \
        "the GPU paddle goes in before paddleocr"
    assert not any("requirements-ocr.txt" in c for c in cmds), "that file names the CPU wheel"
    assert all("paddlepaddle-gpu" in c for c in cmds if "paddlepaddle" in c and "uninstall" not in c)
    # an old driver: the CPU wheels, as before
    old = {"vendor": "nvidia", "name": "x", "driver": "552.44", "cuda": False}
    cmds = [" ".join(c) for c in core.install_command(Path("/r"), gpu=old)]
    assert any("whl/cpu" in c for c in cmds) and not any("paddlepaddle-gpu" in c for c in cmds)


def test_a_cpu_venv_can_be_switched_to_the_card_without_a_second_venv(tmp_path):
    """Allan's Windows copy already has a 2.5 GB CPU venv: the switch
    replaces the wheels in it ("never leave an orphan", "do not build a
    second venv next to a usable one"). The `gpu` tier: paddle's CPU wheel
    out, the GPU one in, torch force-reinstalled from the cu130 index."""
    venv = tmp_path / ".venv-ocr"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "python").write_text("")
    card = {"vendor": "nvidia", "name": "x", "driver": "595.99.02", "cuda": True}
    cmds = [" ".join(c) for c in core.install_command(tmp_path, tiers=["gpu"], gpu=card)]
    assert not any("venv " in c for c in cmds)
    assert any("uninstall -y paddlepaddle" in c for c in cmds)
    assert any("paddlepaddle-gpu" in c and "cu130" in c for c in cmds)
    assert any("force-reinstall" in c and "whl/cu130" in c and "torch" in c for c in cmds)
    assert not any("requirements.txt" in c or "requirements-ocr.txt" in c for c in cmds)


def test_readiness_says_whether_the_installed_readers_can_see_a_card(tmp_path):
    """Read off two files pip wrote, no interpreter started: torch/version.py
    says `cuda = '13.0'` or `cuda = None`; paddle/version/__init__.py says
    `cuda_version = '13.0'` or `'False'`. Both must be CUDA builds for the
    launcher to offer the card."""
    venv = tmp_path / ".venv-ocr"
    site = venv / "lib" / "python3.12" / "site-packages"
    (site / "torch").mkdir(parents=True)
    (site / "paddle" / "version").mkdir(parents=True)
    (venv / "bin").mkdir()
    (venv / "bin" / "python").write_text("")
    # the lines sit where pip writes them: line 6 of torch's file, line 11
    # of paddle's — a match anchored at the start of the file said "CPU"
    # to Allan's CUDA venv (2026-10-18)
    head_t = "from typing import Optional\n__all__ = ['cuda']\n__version__ = '2.14.0'\ndebug = False\n\n"
    head_p = "# THIS FILE IS GENERATED\nfull_version  = '3.4.0'\nmajor = '3'\n"
    (site / "torch" / "version.py").write_text(head_t + "cuda: Optional[str] = None\n")
    (site / "paddle" / "version" / "__init__.py").write_text(head_p + "cuda_version     = 'False'\n")
    assert core.readiness(tmp_path)["gpu"] is False
    (site / "torch" / "version.py").write_text(head_t + "cuda: Optional[str] = '13.0'\n")
    assert core.readiness(tmp_path)["gpu"] is False, "paddle is still the CPU build"
    (site / "paddle" / "version" / "__init__.py").write_text(head_p + "cuda_version     = '13.0'\n")
    assert core.readiness(tmp_path)["gpu"] is True
    assert "gpu" not in core.missing(core.readiness(tmp_path)), "a CPU install is not a missing tier"


def test_uninstall_removes_the_venv_and_the_model_and_nothing_of_the_person_s(tmp_path):
    """"No traces left behind": everything installed is .venv-ocr and the
    model under ~/.cache/kraken; the PDFs and their transcriptions are the
    person's and stay. The models can be kept for a reinstall."""
    venv = tmp_path / ".venv-ocr"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "python").write_text("")
    model = tmp_path / "cache" / "kraken" / "ppocrv6-hist" / "medium.safetensors"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"x")
    settings = tmp_path / "launcher" / "settings.json"
    settings.parent.mkdir()
    settings.write_text("{}")
    pdfs = tmp_path / "pdfs" / "transcriptions"
    pdfs.mkdir(parents=True)
    (pdfs / "a.json").write_text("{}")
    gone = core.uninstall(tmp_path, model=model, settings=settings, models=False)
    assert not venv.exists() and model.exists() and not settings.exists()
    assert (pdfs / "a.json").exists()
    assert any(".venv-ocr" in g for g in gone) and not any("ppocrv6" in g for g in gone)
    gone = core.uninstall(tmp_path, model=model, settings=settings, models=True)
    assert not model.parent.exists()
    assert any("ppocrv6-hist" in g for g in gone)


def test_the_server_is_started_on_the_chosen_device_and_told_to_warm_up(tmp_path):
    """The toggle has teeth: `DESEMBARQUE_DEVICE` forces the device even
    when both builds are there, and `--warm` has the server load its
    models at start instead of inside the first page."""
    cmd = core.serve_command(Path("/v/python"), Path("/r"), Path("/pdfs"), 8765, warm=True)
    assert "--warm" in cmd
    assert "--warm" not in core.serve_command(Path("/v/python"), Path("/r"), Path("/pdfs"), 8765)
    assert core.serve_env("cpu")["DESEMBARQUE_DEVICE"] == "cpu"
    assert core.serve_env("gpu")["DESEMBARQUE_DEVICE"] == "gpu"
    assert "DESEMBARQUE_DEVICE" not in core.serve_env(None)
    port = free_port()
    srv = core.Server(lambda folder, p: [sys.executable, str(STUB), str(p), "--say-device"])
    try:
        assert srv.start(tmp_path, port, wait=15, env={"DESEMBARQUE_DEVICE": "cpu"}) is True
        time.sleep(0.3)
        assert any("device=cpu" in ln for ln in srv.log)
    finally:
        srv.stop(pause=0)


def test_the_page_estimate_is_measured_or_per_device_never_twenty_seconds():
    """The help and the progress box promised "uns 20 s"; a page on the
    Windows CPU took three minutes and the bar sat at the end for most of
    it. The number is what was measured when there is a measurement, and
    the device's figure when there is none."""
    assert core.page_estimate("gpu") == "uns 35 s por página"
    assert core.page_estimate("cpu") == "uns 3 min por página"
    assert core.page_estimate("cpu", measured=181) == "uns 3 min por página"
    assert core.page_estimate("gpu", measured=34.2) == "uns 34 s por página"
    assert core.page_estimate("cpu", measured=95.6) == "uns 1 min 36 s por página"
    assert "20 s" not in core.help_text()


def test_the_install_log_is_summarised_into_a_status_line():
    """Thirty minutes of pip's log looked like a hang: the status line
    says what is being downloaded and how big it is, and the bar counts
    the install's commands."""
    d = core.describe_install_line
    assert d("  Downloading torch-2.14.0+cu130-cp312-cp312-win_amd64.whl (2.9 GB)") == "baixando torch (2.9 GB)"
    assert d("  Downloading paddlepaddle_gpu-3.4.0-cp312-cp312-win_amd64.whl (1.1 GB)") == "baixando paddlepaddle_gpu (1.1 GB)"
    assert d("Collecting kraken==7.1.1") == "resolvendo kraken"
    assert d("Installing collected packages: a, b, c") == "instalando 3 pacotes"
    assert d("Successfully installed a-1 b-2") == "instalados: a-1 b-2"
    assert d("     |████| 1.2/2.9 GB") is None


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="no display")
def test_the_window_offers_the_device_the_warm_up_and_an_uninstall(monkeypatch):
    """Windows test, 2026-10-17: a radio for where to read (the card greyed
    when the install cannot use one), each with its time per page; the
    warm-up toggle on by default; an install bar; and Desinstalar in the
    check window."""
    from tkinter import Tk, Toplevel
    import launcher.desembarque_launcher as dl
    monkeypatch.setattr(core, "gpu", lambda: None)
    monkeypatch.setattr(core, "load_settings", lambda *a: {})
    root = Tk()
    root.withdraw()
    try:
        w = dl.Window(root)
        root.update()
        assert w.device.get() in ("gpu", "cpu")
        assert w.warm.get() is True
        assert "35 s" in w.r_gpu.cget("text") and "3 min" in w.r_cpu.cget("text")
        assert str(w.r_gpu.cget("state")) == "disabled", "no card: the option is there, greyed"
        assert w.install_bar is not None
        cmd = w._command(Path("/pdfs"), 8765)
        assert "--warm" in cmd
        w.warm.set(False)
        assert "--warm" not in w._command(Path("/pdfs"), 8765)
        w.check()
        root.update()
        top = [c for c in root.winfo_children() if isinstance(c, Toplevel)][-1]
        texts = []
        def walk(x):
            for c in x.winfo_children():
                try: texts.append(str(c.cget("text")))
                except Exception: pass
                walk(c)
        walk(top)
        assert any(t.startswith("Desinstalar") for t in texts)
    finally:
        root.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="no display")
def test_the_card_is_the_default_once_it_is_known_to_be_usable(monkeypatch, tmp_path):
    """Allan, 2026-10-18: "if gpu is available, using it should be default".
    The radio was set before nvidia-smi had answered, fell to CPU, and
    stayed there. The card is the default when it is usable and the
    person has not chosen; a saved choice is kept."""
    from tkinter import Tk
    import launcher.desembarque_launcher as dl
    card = {"vendor": "nvidia", "name": "RTX", "driver": "595.99.02", "cuda": True}
    ready = {"python": True, "viewer": True, "engine": True, "handwriting": True, "gpu": True}
    monkeypatch.setattr(core, "gpu", lambda: card)
    monkeypatch.setattr(core, "readiness", lambda *a, **k: ready)
    monkeypatch.setattr(core, "load_settings", lambda *a: {})
    monkeypatch.setattr(core, "SETTINGS", tmp_path / "s.json")
    root = Tk()
    root.withdraw()
    try:
        w = dl.Window(root)
        root.update()
        w._handle(("gpu", card))
        assert w.device.get() == "gpu"
        assert str(w.r_gpu.cget("state")) == "normal"
        # the person chose the CPU last time: kept
        monkeypatch.setattr(core, "load_settings", lambda *a: {"device": "cpu"})
        w2 = dl.Window(root)
        w2._handle(("gpu", card))
        assert w2.device.get() == "cpu"
        # no usable card: CPU, whatever was saved
        monkeypatch.setattr(core, "load_settings", lambda *a: {"device": "gpu"})
        w3 = dl.Window(root)
        w3._handle(("gpu", None))
        assert w3.device.get() == "cpu"
    finally:
        root.destroy()
