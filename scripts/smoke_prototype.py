"""Run the prototype's smoke test in whatever browsers are installed.

The prototype is a browser artifact, so its behaviour cannot be checked from
Python alone: an earlier version rendered but did nothing, because fetch() is
blocked on file:// URLs. This drives the real page in a real browser and fails
loudly on any assertion.

Usage:
    python scripts/smoke_prototype.py            # every browser it can find
    python scripts/smoke_prototype.py --browser firefox
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "prototype" / "build"
PAGE = BUILD / "selftest.html"


# What the built page is made of. If any of these is newer than the build, the
# browser is being shown an older program than the one in the repository.
SOURCES = [ROOT / "prototype" / "review.html", ROOT / "prototype" / "sample_rows.json"]


def stale_reason(built: Path, sources: list[Path]) -> str | None:
    """Why this build cannot be trusted, or None if it can.

    The builder used to die on an import error, leaving the previous
    index.html in place; the smoke test then drove a two-day-old page and
    printed a green result for assertions the current code would have failed.
    Age is the only evidence available here, and it is enough.
    """
    if not built.exists():
        return f"no prototype build at {built.name} — run scripts/make_prototype.py first"
    newer = [s.name for s in sources if s.exists() and s.stat().st_mtime > built.stat().st_mtime]
    if newer:
        return (f"{built.name} is older than {', '.join(newer)} — the build did not run "
                "or it failed; rerun scripts/make_prototype.py")
    return None


def build_harness() -> str:
    index = BUILD / "index.html"
    reason = stale_reason(index, SOURCES)
    if reason:
        raise SystemExit(reason)
    body = (ROOT / "prototype" / "selftest.js").read_text(encoding="utf-8")
    html = index.read_text(encoding="utf-8").replace(
        "</body>", f"<script>\n{body}\n</script>\n</body>")
    PAGE.write_text(html, encoding="utf-8")
    return PAGE.as_uri()


# A harness that throws early reports only the assertions it reached, which
# looked like "2/2 passed - ALL PASS" when a duplicate declaration killed the
# script. A truncated run must fail, not congratulate itself.
MIN_ASSERTIONS = 15


def parse(text: str) -> list[str]:
    text = text.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")
    m = re.search(r"RESULTS>>\s*(.*)", text)
    return [p.strip() for p in m.group(1).split("|")] if m else []


def run_chromium(url: str) -> list[str] | None:
    """The assertions this browser reported, or None if it is not installed.

    The two are not the same answer and were both reported as `[]`: a run that
    produced nothing printed "not available, skipped" and the suite went on to
    say ALL PASS. That is how the served run went unchecked — Firefox loaded a
    corpus of 660 dossiers, took longer than the harness waited, and reported
    nothing at all.
    """
    exe = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    if not exe:
        return None
    out = subprocess.run(
        [exe, "--headless", "--disable-gpu", "--no-sandbox",
         # match the Firefox run: at the default 800x600 the panes are too short
         # for the scroll assertions, so the two browsers would not be comparable
         "--window-size=1400,900",
         "--virtual-time-budget=15000", "--dump-dom", url],
        capture_output=True, text=True, timeout=180)
    return parse(out.stdout)


def run_firefox(url: str, port: int = 4455) -> list[str] | None:
    if not (shutil.which("firefox") and shutil.which("geckodriver")):
        return None
    base = f"http://127.0.0.1:{port}"

    def rq(method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())

    drv = subprocess.Popen(["geckodriver", "--port", str(port)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/status", timeout=2)
                break
            except Exception:
                time.sleep(0.5)
        # a separate profile so this never disturbs a Firefox the user has open
        prof = BUILD / ".ffprof-smoke"
        prof.mkdir(exist_ok=True)
        sess = rq("POST", "/session", {"capabilities": {"alwaysMatch": {
            "browserName": "firefox",
            "moz:firefoxOptions": {"args": ["-headless", "-profile", str(prof),
                                            "-width", "1400", "-height", "900"]},
        }}})
        sid = sess["value"]["sessionId"]
        rq("POST", f"/session/{sid}/window/rect",
           {"width": 1400, "height": 900, "x": 0, "y": 0})
        rq("POST", f"/session/{sid}/url", {"url": url})
        # Waited a flat four seconds, which is enough for the file:// build and
        # not for a served corpus of 660 dossiers. Polling costs nothing when
        # the page is quick and is the difference between a checked run and a
        # skipped one.
        results: list[str] = []
        deadline = time.time() + 90
        while time.time() < deadline:
            res = rq("POST", f"/session/{sid}/execute/sync",
                     {"script": "return document.getElementById('warn').textContent;",
                      "args": []})
            results = parse(res["value"] or "")
            if results:
                break
            time.sleep(1)
        rq("DELETE", f"/session/{sid}")
        return results
    finally:
        drv.terminate()


def main(argv: list[str] | None = None,
         runners: dict | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--browser", choices=["chromium", "firefox", "all"], default="all")
    ap.add_argument("--url", help="test a served URL instead of the file:// build")
    args = ap.parse_args(argv)

    url = args.url or build_harness()
    runners = runners or {"chromium": run_chromium, "firefox": run_firefox}
    if args.browser != "all" and args.browser in runners:
        runners = {args.browser: runners[args.browser]}

    failed = ran = 0
    for name, fn in runners.items():
        results = fn(url)
        if results is None:
            print(f"{name}: not installed, skipped", file=sys.stderr)
            continue
        ran += 1
        if not results:
            # It ran. Reporting nothing is a failure of the page, not an
            # absent browser, and it used to be printed as a skip.
            failed += 1
            print(f"\n{name}: reported no assertions at all — the page did not "
                  "finish, or the harness never ran")
            continue
        bad = [r for r in results if r.startswith("FAIL") or r.startswith("THREW")]
        if len(results) < MIN_ASSERTIONS:
            bad.append(f"TRUNCATED only {len(results)} assertions ran, expected at least "
                       f"{MIN_ASSERTIONS} — the harness stopped early")
        failed += len(bad)
        print(f"\n{name}: {len(results) - len([b for b in bad if not b.startswith('TRUNCATED')])}"
              f"/{len(results)} passed")
        for b in bad:
            print(f"  {b}")

    if not ran:
        print("no browser available to test with", file=sys.stderr)
        return 1
    print("\nALL PASS" if not failed else f"\n{failed} FAILURES")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
