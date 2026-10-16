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
    assert core.describe_index({"status": "idle"}) == "nada a indexar ainda"
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
