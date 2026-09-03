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

    out: dict[str, dict] = {}
    t0 = time.time()
    for job in want:
        pdf = args.scans / job["pdf"]
        if not pdf.exists():
            print(f"  no scan for {job['label']}", flush=True)
            continue
        page = int(job["page"])
        crops = crops_for(pdf, page, args.work, args.target_h)
        dt, said = run_trocr(crops, args.model, args.beams, args.batch)
        doc = cached_hash(pdf)
        # keyed by the band's position on the page: the crops come out of the
        # same geometry the engine cut its rows with, so band i is row i
        out.setdefault(doc, {})[str(page)] = {str(i): t for i, t in said.items()}
        print(f"  {job['label']} p{page}: {len(crops)} bands in {dt:.0f}s",
              flush=True)

    args.out.write_text(json.dumps(
        {"model": args.model, "seconds": round(time.time() - t0, 1),
         "read": out}, ensure_ascii=False, indent=2))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
