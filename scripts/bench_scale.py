"""What the index costs at the size of the whole archive.

660 dossiers are transcribed and the archive holds 7,679, so everything the
progress log says about memory and cold load past that point is an
extrapolation from an eleventh of the corpus — and the two things that grow
worst, the trigram postings and the folded readings, were both written after
the last measurement.

This stands the transcriptions it already has up two, four, eight times over —
symlinks, so it costs no disk and no reading — and measures the load, the
memory and a query at each size.

    .venv/bin/python scripts/bench_scale.py                  # 1, 2, 4, 8, 12
    .venv/bin/python scripts/bench_scale.py --times 1 4      # just those
    .venv/bin/python scripts/bench_scale.py --cap 4          # 4 GB per child

Each size runs in a child process with an address-space cap, so a size the
laptop cannot hold kills the child with a MemoryError and prints a row saying
so, instead of taking the desktop down with it. The default cap is half of
whatever the machine has free when the run starts.
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque.search import load_index, search  # noqa: E402

# What a searcher types: a name alone, a name with the crossing named, and a
# ship on its own — the three shapes the search has different costs for.
QUERIES = ("Contadore",
           "Manoel da Cruz Valdivia",
           "Maria Silva Gelria 1924")


def fanout(cache: Path, dest: Path, times: int) -> Path:
    """The transcription cache, standing `times` times over, as symlinks.

    Each copy is a file of its own as far as the index is concerned — a
    different path, so a different reading — which is what makes the row count
    grow. Nothing is copied: at twelve times the corpus that would be 300 MB of
    writing to measure a number about memory.
    """
    dest.mkdir(parents=True, exist_ok=True)
    for stale in dest.glob("*.json"):
        stale.unlink()
    for f in sorted(Path(cache).glob("*.json")):
        for i in range(times):
            (dest / f"{i:03d}-{f.name}").symlink_to(f.resolve())
    return dest


def rss_mb() -> float:
    """Resident memory now, in MB — what the machine is actually holding."""
    with open("/proc/self/statm", encoding="ascii") as fh:
        pages = int(fh.read().split()[1])
    return pages * os.sysconf("SC_PAGE_SIZE") / 1e6


def free_mb() -> float:
    for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1000
    return 0.0


def measure(cache: Path, limit: int = 50, repeats: int = 5) -> dict:
    """Load the index once and time a query of each shape against it."""
    base = rss_mb()
    t0 = time.perf_counter()
    rows = load_index(cache, engine_only=False)
    load = time.perf_counter() - t0
    loaded = rss_mb()

    # what every keystroke pays: the endpoint loads the index per request, and
    # a load that finds nothing changed still stats every file in the cache.
    t0 = time.perf_counter()
    load_index(cache, engine_only=False)
    warm = time.perf_counter() - t0

    t0 = time.perf_counter()
    post, owner, size, folded = rows.postings
    postings = time.perf_counter() - t0
    with_postings = rss_mb()

    t0 = time.perf_counter()
    rows.crossings
    crossings = time.perf_counter() - t0
    with_crossings = rss_mb()

    timed = {}
    for q in QUERIES:
        search(rows, q, limit=limit)          # once to warm what is cached
        runs = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            hits = search(rows, q, limit=limit)
            runs.append((time.perf_counter() - t0) * 1000)
        runs.sort()
        # the median, because the laptop is also running a desktop: one slow
        # run out of five said a change had cost twice what it saved
        timed[q] = {"ms": runs[len(runs) // 2], "best": runs[0],
                    "hits": len(hits)}
    return {"rows": len(rows), "readings": len(owner), "trigrams": len(post),
            "load_s": load, "warm_s": warm, "postings_s": postings, "crossings_s": crossings,
            "rss_rows_mb": loaded - base, "rss_postings_mb": with_postings - loaded,
            "rss_crossings_mb": with_crossings - with_postings,
            "rss_total_mb": with_crossings - base,
            "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000,
            "queries": timed}


def child(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--cap-mb", type=float, default=0.0)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--repeats", type=int, default=5)
    args = ap.parse_args(argv)
    if args.cap_mb:
        cap = int(args.cap_mb * 1e6)
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    print(json.dumps(measure(args.dir, limit=args.limit, repeats=args.repeats)))
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "--child":
        return child(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--work", type=Path,
                    default=Path(os.environ.get("TMPDIR", "/tmp")) / "desembarque-scale")
    ap.add_argument("--times", type=int, nargs="+", default=[1, 2, 4, 8, 12])
    ap.add_argument("--cap", type=float, default=0.0,
                    help="GB of address space a child may have; default half of free")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "bench_scale.json")
    args = ap.parse_args(argv)

    free = free_mb()
    cap_mb = args.cap * 1000 if args.cap else free / 2
    dossiers = len(list(Path(args.cache).glob("*.json")))
    print(f"{dossiers} dossiers on disk, {free / 1000:.1f} GB free, "
          f"each child capped at {cap_mb / 1000:.1f} GB")
    print(f"{'x':>4} {'dossiers':>9} {'rows':>9} {'load s':>7} {'rows MB':>8} "
          f"{'post MB':>8} {'total MB':>9} {'warm ms':>8}  query ms")

    out = []
    for times in args.times:
        d = fanout(args.cache, args.work / f"x{times}", times)
        proc = subprocess.run(
            [sys.executable, __file__, "--child", "--dir", str(d),
             "--cap-mb", str(cap_mb), "--limit", str(args.limit),
             "--repeats", str(args.repeats)],
            capture_output=True, text=True)
        if proc.returncode != 0:
            tail = (proc.stderr or "").strip().splitlines()[-1:] or ["killed"]
            print(f"{times:>4} {dossiers * times:>9} {'—':>9}  {tail[0][:60]}")
            out.append({"times": times, "failed": tail[0]})
            for stale in d.glob("*.json"):
                stale.unlink()
            continue
        m = json.loads(proc.stdout)
        m["times"] = times
        m["dossiers"] = dossiers * times
        out.append(m)
        qs = " ".join(f"{v['ms']:.0f}" for v in m["queries"].values())
        print(f"{times:>4} {m['dossiers']:>9} {m['rows']:>9} {m['load_s']:>7.1f} "
              f"{m['rss_rows_mb']:>8.0f} {m['rss_postings_mb']:>8.0f} "
              f"{m['rss_total_mb']:>9.0f} {m['warm_s'] * 1000:>8.0f}  {qs}")
        for stale in d.glob("*.json"):
            stale.unlink()
    args.out.write_text(json.dumps({"queries": list(QUERIES), "sizes": out},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwritten to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
