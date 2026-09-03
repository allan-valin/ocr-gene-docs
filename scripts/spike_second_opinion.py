"""Throwaway spike: is a second recogniser worth a second reading?

`spike_htr.py` asked whether a pretrained handwriting model could replace the
engine and the answer was no -- the best of them reads a cursive name at CER
0.257 against the engine's 0.205. But an average hides the shape: the two
fail on *different* words. The engine reads `Guudo Camtadore` where the model
reads `Guiso Cantadore`, and a searcher only needs one of them to be reachable.

So this asks the question that matters instead. Every row of the hand-read
pages is read a second time by a historical-hand model, the reading is put in
`alts` beside the engine's own -- a reading, not a guess, because a recogniser
read it off the page -- and `bench_search.py --matrix` says whether anybody
can find more people.

Not intended to be kept as it is: at 6.6 s a row this belongs in the offline
batch, and probably only on the rows the check flags. What is being measured
here is whether it is worth building that.

    .venv-htr/bin/python scripts/spike_second_opinion.py --out data/second_opinion.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from desembarque.identity import cached_hash          # noqa: E402
from spike_htr import crops_for, run_trocr            # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="agomberto/trocr-large-handwritten-fr")
    ap.add_argument("--truth", type=Path, default=ROOT / "data" / "truth")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--target-h", type=int, default=64)
    ap.add_argument("--beams", type=int, default=4)
    ap.add_argument("--batch", type=int, default=6)
    ap.add_argument("--records", type=Path, default=None,
                    help="read every page of every record in this directory, "
                         "rather than the hand-read pages -- the whole of a "
                         "small corpus, so targets and competitors are read "
                         "the same number of times and the comparison is fair")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "data" / "second_opinion.json")
    args = ap.parse_args()

    if args.records:
        want = []
        for rf in sorted(args.records.glob("*.json")):
            rec = json.loads(rf.read_text(encoding="utf-8"))
            name = rec.get("file")
            for page in sorted({r.get("page") for r in rec.get("rows") or []
                                if r.get("page")}):
                want.append({"pdf": name, "page": page, "label": rf.name})
    else:
        want = []
        for tf in sorted(args.truth.glob("*.json")):
            d = json.loads(tf.read_text(encoding="utf-8"))
            want.append({"pdf": d["pdf"], "page": int(d["page"]),
                         "label": tf.name})

    # Written after every page and resumed from what is already there. The
    # first run of this over a small corpus died at 45 minutes with nothing on
    # disk, and a spike that can only be run in one sitting is a spike nobody
    # runs twice.
    out: dict[str, dict] = {}
    if args.out.exists():
        try:
            was = json.loads(args.out.read_text(encoding="utf-8"))
            if was.get("model") == args.model:
                out = was.get("read") or {}
                print(f"resuming: {sum(len(v) for v in out.values())} pages read")
        except ValueError:
            pass
    t0 = time.time()
    for job in want:
        pdf = args.scans / job["pdf"]
        if not pdf.exists():
            print(f"  no scan for {job['label']}", flush=True)
            continue
        page = int(job["page"])
        doc = cached_hash(pdf)
        if str(page) in out.get(doc, {}):
            continue
        # Marked before it is read, not after, so a page that cannot be cut is
        # skipped on the next run rather than retried for ever. `name_strip`
        # says `raise SystemExit("no grid detected")` on a page with no ruled
        # table, which is not an Exception and takes the whole process with it
        # -- caught here, because one page of a corpus having no grid is not a
        # reason to stop reading the other sixty-four.
        out.setdefault(doc, {})[str(page)] = {}
        args.out.write_text(json.dumps(
            {"model": args.model, "read": out}, ensure_ascii=False, indent=2))
        try:
            crops = crops_for(pdf, page, args.work, args.target_h)
        except (Exception, SystemExit) as e:  # noqa: BLE001 - a spike
            print(f"  {job['label']} p{page}: crop failed, {e}", flush=True)
            continue
        dt, said = run_trocr(crops, args.model, args.beams, args.batch)
        # keyed by the band's position on the page; `map_sidecar` pairs those
        # with the rows in an index, which drops headings and short rows
        out.setdefault(doc, {})[str(page)] = {str(i): t for i, t in said.items()}
        args.out.write_text(json.dumps(
            {"model": args.model, "seconds": round(time.time() - t0, 1),
             "read": out}, ensure_ascii=False, indent=2))
        print(f"  {job['label']} p{page}: {len(crops)} bands in {dt:.0f}s",
              flush=True)

    args.out.write_text(json.dumps(
        {"model": args.model, "seconds": round(time.time() - t0, 1),
         "read": out}, ensure_ascii=False, indent=2))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
