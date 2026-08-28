"""Which reasons for a second look actually find the badly-read rows.

The review screen marks rows worth checking first, and the marking is only
worth the yellow bar if it points at the rows that are wrong. Scored against
the hand-read pages: a row is *badly read* when what the engine stored is not
what somebody read off the scan, and each reason is measured on its own —
how many of the bad rows it catches, and how many good rows it stops a person
on for nothing.

    .venv/bin/python scripts/bench_check.py
    .venv/bin/python scripts/bench_check.py --json out.json

A reason that fires on everything catches everything and says nothing, so both
columns matter: `catches` is of the badly-read rows, `stops` is of the rows
that were read correctly.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque import search as searchlib          # noqa: E402
from desembarque.gazetteer import Names, spoken_names  # noqa: E402
from desembarque.truthset import fold, rows_from_disk  # noqa: E402

CHECK_SCORE = 0.85


def reasons(row: dict, names: Names, spoken: set[str] | None = None) -> list[str]:
    """Every reason this row is worth a second look — the three the server
    gives today, and the one the plan argues for."""
    out = []
    score = (row.get("conf") or {}).get("surname")
    if score is not None and score < CHECK_SCORE:
        out.append("score")
    if row.get("ditto_source") == "position":
        out.append("inferido")
    text = searchlib.row_text(row)
    if names.doubtful(text):
        out.append("desconhecido")
    if names.near_miss(text):
        out.append("quase")
    if spoken and names.near_miss(text, spoken=spoken) and "quase" not in out:
        out.append("quase-lista")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)

    names = Names.load(ROOT / "data" / "names.json")
    spoken = spoken_names(ROOT / "data" / "language_names.json")
    rows, seen = rows_from_disk()
    scored = []
    for p in rows:
        scored.append({"bad": fold(p["truth"]) != fold(p["read"]),
                       "why": reasons(p["row"], names, spoken)})
    bad = [r for r in scored if r["bad"]]
    good = [r for r in scored if not r["bad"]]

    every = ["score", "inferido", "desconhecido", "quase", "quase-lista"]
    report = {"rows": len(scored), "bad": len(bad), "good": len(good),
              "dictionary": len(names), "reasons": {}}
    for why in every + ["hoje", "todas"]:
        def fires(r, why=why):
            if why == "hoje":
                return any(x in r["why"] for x in every[:3])
            if why == "todas":
                return bool(r["why"])
            return why in r["why"]
        report["reasons"][why] = {
            "catches": round(sum(1 for r in bad if fires(r)) / len(bad), 3) if bad else 0.0,
            "stops": round(sum(1 for r in good if fires(r)) / len(good), 3) if good else 0.0,
        }

    print(f"{len(scored)} rows paired with a hand reading, {len(bad)} of them "
          f"read wrong, over {seen['pages']} pages")
    print("reason        catches  stops")
    for why, m in report["reasons"].items():
        print(f"{why:<12}  {m['catches']:<7.3f}  {m['stops']:.3f}")
    if a.json:
        a.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
