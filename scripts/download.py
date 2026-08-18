"""Fetch a sample of dossiers from the Arquivo Nacional image server.

Reads the catalog produced by parse_index.py, samples N dossiers per saved
index page, resolves each to its real file URLs, and downloads them.

The archive is a public institution on modest infrastructure, so this is
deliberately slow: serial, delayed between requests, and it never re-fetches a
file already on disk. Downloaded scans are gitignored and are not redistributed.

Usage:
    python scripts/download.py --per-page 5 --out data/scans
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Iterable

from parse_index import Entry, build_url

MAX_PARTS = 8  # no sampled dossier is expected to exceed this many PDFs
DELAY = 1.5  # seconds between requests, to be a polite guest


def _curl(url: str, dest: Path | None = None, timeout: int = 180) -> int:
    """Run curl with retries. Returns the HTTP status code (0 if unreachable)."""
    cmd = [
        "curl", "-sS", "-L",
        "--retry", "5", "--retry-delay", "3", "--retry-all-errors",
        "--max-time", str(timeout),
        "-w", "%{http_code}",
    ]
    if dest is None:
        cmd += ["-I", "-o", "/dev/null"]
    else:
        cmd += ["-C", "-", "-o", str(dest)]
    cmd.append(url)
    out = subprocess.run(cmd, capture_output=True, text=True)
    code = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else "0"
    try:
        return int(code)
    except ValueError:
        return 0


def http_probe(url: str) -> bool:
    time.sleep(DELAY)
    return _curl(url) == 200


def _candidate_folders(e: Entry) -> list[Entry]:
    """Folder identities to try, most specific first.

    A letter-suffixed index is catalogued separately from the plain one, but
    ~1% of them have no lettered path on the image server. Try the lettered
    path first so we never mistake one dossier for another, then fall back.
    """
    if e.index.isdigit():
        return [e]
    plain = e.index.rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    return [e, Entry(e.fundo, e.series, plain, e.ship, e.rv, e.source)]


def resolve_parts(
    e: Entry, probe: Callable[[str], bool] = http_probe, max_parts: int = MAX_PARTS
) -> list[str]:
    """Find the real URLs for a dossier, or [] if it cannot be resolved.

    The filename encodes how many PDFs the dossier has (d0001de0002), and that
    count is not in the index, so it has to be discovered by probing totals.
    """
    for candidate in _candidate_folders(e):
        for total in range(1, max_parts + 1):
            if probe(build_url(candidate, part=1, total=total)):
                return [
                    build_url(candidate, part=n, total=total)
                    for n in range(1, total + 1)
                ]
    return []


def sample_per_source(rows: list[dict], n: int, seed: int) -> list[dict]:
    """Take n rows from each saved index page, deterministically.

    Sampling per source page rather than globally keeps the sample spread over
    the whole index range — the indices are sequential, so the pages Allan
    saved are what bounds the corpus to roughly 1919-1924.
    """
    by_source: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_source[r.get("source") or "?"].append(r)

    picked: list[dict] = []
    for source in sorted(by_source):
        group = sorted(by_source[source], key=lambda r: r["index"])
        rng = random.Random(f"{seed}:{source}")
        picked.extend(rng.sample(group, min(n, len(group))))
    return picked


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", type=Path, default=Path("data/catalog.jsonl"))
    ap.add_argument("--out", type=Path, default=Path("data/scans"))
    ap.add_argument("--per-page", type=int, default=5)
    ap.add_argument("--seed", type=int, default=1919)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if not shutil.which("curl"):
        print("curl not found", file=sys.stderr)
        return 1

    rows = [json.loads(l) for l in args.catalog.open(encoding="utf-8")]
    picked = sample_per_source(rows, n=args.per_page, seed=args.seed)
    print(f"sampling {len(picked)} dossiers from {len(rows)} catalogued", file=sys.stderr)

    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out / "manifest.jsonl"
    done = set()
    if manifest_path.exists():
        for line in manifest_path.open(encoding="utf-8"):
            done.add(json.loads(line)["index"])

    unresolved: list[dict] = []
    fetched = skipped = 0

    with manifest_path.open("a", encoding="utf-8") as mf:
        for i, row in enumerate(picked, 1):
            e = Entry(
                row["fundo"], row["series"], row["index"],
                row.get("ship"), row.get("rv"), row.get("source"),
            )
            tag = f"{e.fundo}.{e.series}.{e.index}"
            if e.index in done:
                skipped += 1
                continue

            print(f"[{i}/{len(picked)}] {tag} ({e.ship or 'no ship name'})", file=sys.stderr)
            if args.dry_run:
                continue

            urls = resolve_parts(e)
            if not urls:
                print(f"    unresolved", file=sys.stderr)
                unresolved.append(asdict(e))
                continue

            local: list[str] = []
            for url in urls:
                dest = args.out / url.rsplit("/", 1)[-1]
                if dest.exists() and dest.stat().st_size > 0:
                    local.append(dest.name)
                    continue
                time.sleep(DELAY)
                code = _curl(url, dest=dest)
                if code != 200 or not dest.exists() or dest.stat().st_size == 0:
                    dest.unlink(missing_ok=True)
                    print(f"    failed {code}: {url}", file=sys.stderr)
                    continue
                local.append(dest.name)
                print(f"    {dest.name} ({dest.stat().st_size//1024} KB)", file=sys.stderr)

            if local:
                mf.write(json.dumps({**asdict(e), "files": local}, ensure_ascii=False) + "\n")
                mf.flush()
                fetched += 1
            else:
                unresolved.append(asdict(e))

    if unresolved:
        report = args.out / "unresolved.jsonl"
        with report.open("w", encoding="utf-8") as fh:
            for u in unresolved:
                fh.write(json.dumps(u, ensure_ascii=False) + "\n")
        print(f"\n{len(unresolved)} unresolved -> {report}", file=sys.stderr)

    print(f"{fetched} dossiers fetched, {skipped} already present", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
