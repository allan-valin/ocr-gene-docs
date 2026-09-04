"""Save the crops the engine reads, so another recogniser can read the same ink.

A second opinion is only worth having if it lands on the row it belongs to,
and the first attempt at this paired 28% of rows: the sidecar was cut by
`spike_speed.name_strip` and the index by the engine's own row cutting, and
where two segmentations disagree an alignment on what they *say* has nothing
to hold on to -- a TrOCR reading and a Paddle reading of the same faint hand
often share no word.

So the crops come from the engine here, out of the sink its own crop function
fills: exactly the images it reads, keyed by the band index its rows are
numbered from. Pairing those to the stored corpus is then engine against
engine, which alignment does well: 94% on the hand-read pages against 28%.

Two pictures of every row come out, because they are not read alike: the
carved crop the engine hands its own recogniser, cut to the row's ink, and the
plain rectangle of the same band. A historical-hand TrOCR reads the carved
crop at CER 0.892 and the plain band at 0.338, so a second opinion measured on
the carved crop measures the carving and nothing else.

    .venv-ocr/bin/python scripts/export_bands.py --records DIR --out DIR
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from desembarque.engine_paddle import PaddleEngine    # noqa: E402
from desembarque.identity import cached_hash          # noqa: E402
from page_geometry import page_image                  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=Path, required=True)
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    index_path = args.out / "bands.json"
    done = {}
    if index_path.exists():
        try:
            done = json.loads(index_path.read_text(encoding="utf-8"))
        except ValueError:
            done = {}

    eng = PaddleEngine()
    for rf in sorted(args.records.glob("*.json")):
        rec = json.loads(rf.read_text(encoding="utf-8"))
        pdf = args.scans / (rec.get("file") or "")
        if not pdf.exists():
            continue
        doc = cached_hash(pdf)
        for page in sorted({r.get("page") for r in rec.get("rows") or []
                            if r.get("page")}):
            key = f"{doc}/{page}"
            if key in done:
                continue
            done[key] = []                      # attempted, so a crash is final
            index_path.write_text(json.dumps(done))
            try:
                img = page_image(pdf, page, args.work)
                eng.band_sink = {}
                res = eng.transcribe_page(img, kind="unknown", source=pdf,
                                          page=page)
                sink = eng.band_sink
            except (Exception, SystemExit) as e:   # noqa: BLE001 - a spike
                print(f"  {doc[:8]} p{page}: {e}", flush=True)
                continue
            finally:
                eng.band_sink = None
            read = [r for r in (res.rows or []) if (r.get("name_raw") or "").strip()]
            # by band index rather than by position: a page is read more than
            # once -- the render fallback, the looser second reading -- and
            # zipping a row against the n-th crop of all those passes pairs a
            # name with somebody else's ink
            pairs = []
            folder = args.out / doc / str(page)
            folder.mkdir(parents=True, exist_ok=True)
            for r in read:
                band = sink.get(r["n"] - 1)
                if not band:
                    continue
                name = f"{r['n']}.png"
                strip = f"{r['n']}-strip.png"
                band["carved"].convert("RGB").save(folder / name)
                band["strip"].convert("RGB").save(folder / strip)
                pairs.append({"n": r["n"], "file": f"{doc}/{page}/{name}",
                              "strip": f"{doc}/{page}/{strip}",
                              "engine": r.get("name_raw") or ""})
            done[key] = pairs
            index_path.write_text(json.dumps(done))
            print(f"  {doc[:8]} p{page}: {len(pairs)} rows of {len(sink)} bands",
                  flush=True)

    print(f"wrote {index_path}")


if __name__ == "__main__":
    main()
