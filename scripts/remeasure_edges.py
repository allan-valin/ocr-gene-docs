"""Read again the pages whose name column reached into the next one.

The name column's right edge was the left edge of the heading printed beside
it, and that heading is narrower than its column: on the Companhia Nacional
de Navegação Costeira's sheets `Nação` starts at 0.453 of the page and the
typed *Brazileiro* under it at 0.421, so every name on the page carried the
first letters of a nationality — `Enzo SantoniBra`, `José dos SantosPor`.
Since 2026-10-16 the edge is measured from where the next column's writing
starts (`tablegrid._right_from_writing`). What is on disk was read with the
old edge, and the app shows what is on disk.

Nothing can say from a record alone whether its page moves — the detector's
boxes are not stored — so this runs in two passes, each resumable:

    .venv-ocr/bin/python scripts/remeasure_edges.py survey data/edges-survey.json
    .venv-ocr/bin/python scripts/remeasure_edges.py apply  data/edges-survey.json

*survey* measures every list page again with the detector only (a few
seconds a page, no recognition) and writes down the pages whose edge moved by
more than `MOVED` of the sheet. *apply* reads those pages again, in page order
within each dossier so a continuation page takes its columns from the heading
page before it, and replaces the engine's rows — never a person's, and never
with an empty page (`retry.with_page_remeasured`).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from desembarque.retry import with_page_remeasured   # noqa: E402
from page_geometry import page_image                 # noqa: E402

MOVED = 0.004      # of the sheet; less than that is the detector's own jitter
_ENGINE = None


def engine():
    global _ENGINE
    if _ENGINE is None:
        from desembarque.engine_paddle import PaddleEngine
        _ENGINE = PaddleEngine()
        _ENGINE._import()
    return _ENGINE


def list_pages(record: dict) -> list[int]:
    return [p["n"] for p in record.get("pages") or []
            if isinstance(p, dict) and p.get("kind") == "list"]


def stored_edge(record: dict, n: int) -> float | None:
    for p in record.get("pages") or []:
        if isinstance(p, dict) and p.get("n") == n:
            cols = (p.get("geometry") or {}).get("columns")
            return float(cols[1]) if cols and len(cols) >= 2 else None
    return None


def measure(image: Path, hint: dict | None):
    """The printed table on this page, and the hint the next page inherits."""
    eng = engine()
    geo = eng._printed_table(image, hint=hint)
    if geo is not None and getattr(geo, "heading_found", False):
        hint = {"name": geo.name, "ordinal": geo.ordinal,
                "others": getattr(geo, "others", [])}
    return geo, hint


def survey_one(job: tuple) -> list[dict]:
    """Every list page of one dossier whose edge moves, with old and new."""
    file, pdf, pagecache = job
    try:
        record = json.loads(Path(file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out, hint = [], None
    for n in list_pages(record):
        img = page_image(Path(pdf), n, Path(pagecache))
        if img is None:
            continue
        try:
            geo, hint = measure(img, hint)
        except Exception as e:   # one page must not end the survey
            out.append({"file": file, "page": n, "error": f"{type(e).__name__}: {e}"})
            continue
        was = stored_edge(record, n)
        if geo is None or was is None:
            continue
        now = geo.name_column(0)
        if not now:
            continue
        if abs(float(now[1]) - was) > MOVED:
            out.append({"file": file, "page": n, "notation": record.get("notation"),
                        "was": round(was, 4), "now": round(float(now[1]), 4)})
    return out


def survey(a) -> int:
    done = {}
    if a.out.exists():
        done = {d["file"]: d for d in json.loads(a.out.read_text()).get("dossiers", [])}
    by_name = {p.name: p for p in a.scans.rglob("*.pdf")}
    jobs = []
    for f in sorted(a.cache.glob("*.json")):
        if str(f) in done:
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pdf = by_name.get(d.get("file") or "")
        if pdf is None or not list_pages(d):
            continue
        jobs.append((str(f), str(pdf), str(a.pagecache)))
    jobs = jobs[:a.limit] if a.limit else jobs
    print(f"{len(done)} dossiers surveyed already, {len(jobs)} to go, "
          f"{a.workers} workers", flush=True)
    t0 = time.time()
    results = list(done.values())

    def save():
        moved = [m for r in results for m in r["moved"] if "now" in m]
        a.out.write_text(json.dumps({"moved_threshold": MOVED, "dossiers": results,
                                     "moved": moved}, ensure_ascii=False, indent=0))

    with Pool(a.workers) as pool:
        for i, (job, moved) in enumerate(zip(jobs, pool.imap(survey_one, jobs)), 1):
            results.append({"file": job[0], "moved": moved})
            if i % 10 == 0 or i == len(jobs):
                save()
                el = time.time() - t0
                print(f"  {i}/{len(jobs)} dossiers, {sum(len(r['moved']) for r in results)} "
                      f"pages moved so far, {el / 60:.0f} min, "
                      f"~{el / i * (len(jobs) - i) / 60:.0f} min left", flush=True)
    save()
    moved = [m for r in results for m in r["moved"] if "now" in m]
    print(f"\n{len(moved)} pages moved across {len({m['file'] for m in moved})} dossiers "
          f"-> {a.out}")
    return 0


def apply(a) -> int:
    data = json.loads(a.out.read_text(encoding="utf-8"))
    wanted: dict[str, set[int]] = {}
    for m in data.get("moved", []):
        wanted.setdefault(m["file"], set()).add(int(m["page"]))
    by_name = {p.name: p for p in a.scans.rglob("*.pdf")}
    done_file = a.out.with_suffix(".applied.json")
    applied = set(json.loads(done_file.read_text())) if done_file.exists() else set()
    files = [f for f in sorted(wanted) if f not in applied]
    files = files[:a.limit] if a.limit else files
    print(f"{len(applied)} dossiers applied already, {len(files)} to go", flush=True)
    t0, pages, before, after = time.time(), 0, 0, 0
    for i, file in enumerate(files, 1):
        f = Path(file)
        record = json.loads(f.read_text(encoding="utf-8"))
        pdf = by_name.get(record.get("file") or "")
        if pdf is None:
            continue
        eng = engine()
        eng._last_columns.pop(str(pdf), None)
        hint = None
        for n in list_pages(record):
            img = page_image(pdf, n, a.pagecache)
            if img is None:
                continue
            if n not in wanted[file]:
                # cheap: only so the next page inherits this one's columns
                try:
                    _geo, hint = measure(img, hint)
                    if hint:
                        eng._last_columns[str(pdf)] = hint
                except Exception:
                    pass
                continue
            if hint:
                eng._last_columns[str(pdf)] = hint
            res = eng.transcribe_page(img, "list", source=pdf, page=n)
            hint = eng._last_columns.get(str(pdf), hint)
            rows = list(res.rows or [])
            was = [r for r in record.get("rows") or [] if r.get("page") == n]
            pages += 1
            before += sum(1 for r in was if (r.get("name_raw") or "").strip())
            after += sum(1 for r in rows if (r.get("name_raw") or "").strip())
            page = {"n": n, "kind": res.kind, "geometry": res.geometry}
            out = with_page_remeasured(record, n, page, rows)
            if out is None:
                print(f"  {record.get('notation')} p{n}: read nothing, kept", flush=True)
                continue
            record = out
        if not a.dry_run:
            f.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            applied.add(file)
            done_file.write_text(json.dumps(sorted(applied)))
        el = time.time() - t0
        print(f"  {i}/{len(files)} {record.get('notation')}: {pages} pages so far, "
              f"names {before} -> {after}, {el / 60:.0f} min, "
              f"~{el / i * (len(files) - i) / 60:.0f} min left", flush=True)
    print(f"\n{pages} pages read again: {before} names before, {after} after")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["survey", "apply"])
    ap.add_argument("out", type=Path)
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--pagecache", type=Path, default=ROOT / "data" / "pagecache")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    return survey(a) if a.mode == "survey" else apply(a)


if __name__ == "__main__":
    raise SystemExit(main())
