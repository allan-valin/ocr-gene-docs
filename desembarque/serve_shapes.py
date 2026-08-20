"""One shape for a page's geometry, whoever measured it.

Two producers described the same thing differently. `/api/grid`, which measures
a page without transcribing it, returned `row_bands` and `name_column`. The
engine, transcribing the same page, stored `rows` and `columns`.

The review UI paints the band for the selected row from `row_bands`. On every
engine-transcribed page it therefore found nothing, fell through to a row pitch
that had never been stored, computed NaN, and painted nothing at all — clicking
a name stopped highlighting it, silently, on exactly the pages that had been
read successfully.

Nothing caught it because nothing tested the join. The browser assertions run
against `prototype/sample_rows.json`, which is hand-fitted and has always
carried `row_bands`; the Python tests cover the engine's output and the
server's endpoints separately. Both sides passed while disagreeing.

So the translation lives here, in one function, with tests naming the contract.
"""
from __future__ import annotations


def ui_geometry(geo: dict | None) -> dict | None:
    """A page's geometry in the shape the review UI reads.

    Additive: the keys the engine stored are kept, so a stored record stays
    readable by anything that already understood it, and re-serving is
    idempotent.
    """
    if not geo:
        return geo
    out = dict(geo)
    bands = out.get("row_bands") or out.get("rows")
    if bands and "row_bands" not in out:
        out["row_bands"] = [list(b) for b in bands]
    if "name_column" not in out:
        cols = out.get("columns") or []
        # the widest column is the names; the same choice the engine makes when
        # it decides which strip to hand the recogniser
        pairs = list(zip(cols, cols[1:]))
        if pairs:
            a, b = max(pairs, key=lambda p: p[1] - p[0])
            out["name_column"] = [a, b]
    if "bands_source" not in out and bands:
        out["bands_source"] = "detected"
    return out


def ui_transcription(data: dict | None) -> dict | None:
    """A stored transcription with every page's geometry in the UI's shape."""
    if not data:
        return data
    out = dict(data)
    pages = out.get("pages")
    if isinstance(pages, list):
        out["pages"] = [
            {**p, "geometry": ui_geometry(p.get("geometry"))} if isinstance(p, dict) else p
            for p in pages
        ]
    if isinstance(out.get("geometry"), dict):
        out["geometry"] = ui_geometry(out["geometry"])
    return out


# What the review UI's document header shows, in the order it shows it. Every
# one of these is absent on some page: conservation varies, and the clerk left
# fields blank.
META_FIELDS = ("ship", "line", "flag", "origin", "port", "arrival", "year", "passengers")


def ui_meta(voyage: dict | None, notation: str | None = None,
            catalogued: str | None = None) -> dict | None:
    """A stored voyage in the shape the document header reads.

    Only the fields the page actually stated are carried. A missing port
    rendered as `undefined` is worse than a missing port, and an empty string
    reads as a page that said nothing where the page was never asked — the same
    distinction the row cells make between *ilegível* and never attempted.
    """
    out = {k: (voyage or {})[k] for k in META_FIELDS
           if (voyage or {}).get(k) not in (None, "", [])}
    # Two claims about one ship: what the page says, and what the dossier is
    # filed under at the archive. Both are kept where they differ, because the
    # way to settle that is to look at the scan beside them.
    if catalogued:
        out["catalog_ship"] = catalogued
    if not out:
        return None
    if notation:
        out["notation"] = notation
    # the page it was read from, so a wrong ship can be checked against the scan
    if (voyage or {}).get("source"):
        out["source"] = voyage["source"]
    return out
