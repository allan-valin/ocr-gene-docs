"""Where the corpus stands, in one command.

    .venv/bin/python scripts/status.py

Reads what is on disk and asks the local server whether a run is going. Written
because the answer was being assembled by hand from four different places, and a
number assembled by hand is a number that drifts.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque.retry import pages_wanting_a_reading   # noqa: E402
from desembarque.search import SCHEMA                   # noqa: E402


def run_state(port: int) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/index",
                                    timeout=3) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, OSError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--port", type=int, default=8799)
    args = ap.parse_args(argv)

    records = rows = named = errors = stale = unread = unread_docs = 0
    voyage = Counter()
    ditto = Counter()
    for f in sorted(args.cache.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        records += 1
        # how it was read, not how it was parsed: a re-parse lifts the second
        if d.get("engine") and int(d.get("read_schema", d.get("schema", 0))) < SCHEMA:
            stale += 1
        if any(p.get("error") for p in d.get("pages") or [] if isinstance(p, dict)):
            errors += 1
        # A page the geometry could not measure is stored with nothing on it,
        # and the record around it stays current — so no run will ever look at
        # it again unless it is counted here.
        wanting = pages_wanting_a_reading(d, schema=SCHEMA)
        if wanting:
            unread += len(wanting)
            unread_docs += 1
        v = d.get("voyage") or {}
        for k in ("ship", "year", "port", "origin", "line"):
            voyage[k] += bool(v.get(k))
        for r in d.get("rows") or []:
            rows += 1
            if (r.get("name_raw") or "").strip():
                named += 1
            if r.get("ditto"):
                ditto[r.get("ditto_source") or "?"] += 1

    scans = len(list(args.scans.glob("*.pdf")))
    print(f"{records} records for {scans} dossiers, schema {SCHEMA}")
    print(f"   {rows} rows, {named} with a reading")
    if stale:
        print(f"   {stale} were read by an older engine — an index run redoes them")
    if errors:
        print(f"   {errors} carry a page the engine failed on — they will be read again")
    if unread:
        print(f"   {unread} pages in {unread_docs} records read nothing — "
              "scripts/retry_unknown.py reads them again")
    print("   voyage: " + ", ".join(
        f"{k} {voyage[k]} ({voyage[k] / max(records, 1):.0%})"
        for k in ("ship", "year", "port", "origin", "line")))
    if ditto:
        print("   surnames inherited: " + ", ".join(
            f"{k} {n}" for k, n in ditto.most_common()))

    st = run_state(args.port)
    if not st:
        print("no server on 127.0.0.1:%d" % args.port)
    elif st.get("status") == "running":
        seen = st["done"] + st["skipped"]
        print(f"indexing: {seen} of {st['total']} · {st['done']} read this pass · "
              f"{len(st.get('failed') or [])} failures · {st.get('current') or ''}")
    else:
        print(f"indexing: {st.get('status')}, "
              f"{st['done'] + st['skipped']} of {st['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
