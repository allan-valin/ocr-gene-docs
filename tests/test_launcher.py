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
    for word in ("Instalar", "Ligar", "Desligar",
                 "Ler os PDFs", "127.0.0.1:8765", "PDF", "20 s", "fechar a janela"):
        assert word in h, word
    assert len(h) < 2500


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
