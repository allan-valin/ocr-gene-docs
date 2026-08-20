"""Scripts in scripts/ have to run when run directly.

`make_prototype.py` imported the package from inside a function, and the
repository root was never on sys.path, so the import failed only once the
builder reached a PDF — long after argument parsing. The build then died,
`prototype/build/index.html` stayed as it was, and the browser smoke test went
on reporting a green run against a page two days old. A broken build that keeps
its previous artifact is worse than one that leaves nothing behind: the next
thing downstream believes it.
"""
import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = sorted((ROOT / "scripts").glob("*.py"))


def _imports_the_package(src: str) -> bool:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "desembarque":
            return True
        if isinstance(node, ast.Import):
            if any(a.name.split(".")[0] == "desembarque" for a in node.names):
                return True
    return False


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_a_script_that_imports_the_package_puts_the_root_on_the_path(script):
    """Including imports written inside a function, which run far later than
    the ones at the top and so fail in the middle of real work."""
    src = script.read_text(encoding="utf-8")
    if not _imports_the_package(src):
        pytest.skip("does not import the package")
    assert "sys.path" in src, (
        f"{script.name} imports desembarque but never adds the repository root "
        "to sys.path, so it only works when something else already has")


def test_the_prototype_builder_reaches_the_pdf_layer():
    """The failure was a ModuleNotFoundError raised from inside pdf_page_count.
    Any other error from a missing file is fine; that one is the regression."""
    proc = subprocess.run(
        [sys.executable, "-c",
         "import runpy,sys;sys.argv=['make_prototype'];"
         "m=runpy.run_path(%r);"
         "from pathlib import Path;\n"
         "try: m['pdf_page_count'](Path('/nonexistent.pdf'))\n"
         "except ModuleNotFoundError as e: print('IMPORT-BROKEN', e); raise SystemExit(2)\n"
         "except Exception: pass\n" % str(ROOT / "scripts" / "make_prototype.py")],
        capture_output=True, text=True, cwd="/", timeout=120)
    assert proc.returncode != 2, proc.stdout + proc.stderr


def test_the_smoke_test_refuses_a_build_older_than_its_source(tmp_path):
    """The browser test drives prototype/build/index.html, which the builder
    writes. When the builder failed, the old file stayed, and the smoke run
    reported a healthy page belonging to a version nobody had edited in days.
    A stale artifact has to be an error, not a silent pass."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "smoke_prototype", ROOT / "scripts" / "smoke_prototype.py")
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)

    src = tmp_path / "review.html"
    built = tmp_path / "index.html"
    built.write_text("built")
    src.write_text("source")            # written after the build
    import os
    os.utime(built, (1000, 1000))
    os.utime(src, (2000, 2000))

    assert smoke.stale_reason(built, [src]), "an older build must be reported"
    os.utime(built, (3000, 3000))
    assert smoke.stale_reason(built, [src]) is None
    assert "missing.html" in smoke.stale_reason(tmp_path / "missing.html", [src])
