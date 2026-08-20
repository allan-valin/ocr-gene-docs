"""What leaves the tool, in a form a registrar can read.

This is the evidence half of the project: someone takes a spreadsheet to an
office and says an ancestor was on a ship. So the file has to be honest about
what it is. Three things follow from that.

A row that the engine guessed and a row a person confirmed are different
evidence, and nothing in a spreadsheet distinguishes them unless it is written
down — so every row carries its origin.

The verbatim reading travels with the split of it. The engine reads
"Nayomgo Cassaudii" for Raymundo Cassaudi; the split into surname and given
name is a derivation, and on some forms it is derived the wrong way round,
because the name order is not constant even inside one dossier. The raw string
is the thing that was actually read.

And the recogniser's score is exported under a name that says what it is. It is
a decode score, high on confident nonsense; calling it "precisão" in a column
header would invite exactly the reading it does not support.

Blank rows are kept. A blank line on these forms means the information was not
known, which is a fact about the page; dropping it would silently renumber
everyone below it.
"""
from __future__ import annotations

import csv
import io

FIELDS = [
    "notacao", "arquivo", "navio", "pagina", "linha",
    "nome_lido", "sobrenome", "nome", "origem", "score_motor",
]


def _origin(row: dict, doc: dict) -> str:
    """Who produced this row: a person, or which engine."""
    return row.get("source") or doc.get("engine") or ""


def rows_to_csv(doc: dict) -> str:
    """One document's rows as CSV text, header included even when empty."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    for row in doc.get("rows") or []:
        conf = row.get("conf") or {}
        w.writerow({
            "notacao": doc.get("notation") or "",
            "arquivo": doc.get("file") or "",
            "navio": doc.get("ship") or "",
            "pagina": row.get("page") or "",
            "linha": row.get("n") or "",
            "nome_lido": row.get("name_raw") or "",
            "sobrenome": row.get("surname") or "",
            "nome": row.get("given") or "",
            "origem": _origin(row, doc),
            "score_motor": conf.get("surname") if conf.get("surname") is not None else "",
        })
    return buf.getvalue()


def csv_filename(doc: dict) -> str:
    """A filename that says which dossier this came from."""
    stem = (doc.get("notation") or doc.get("file") or "desembarque").replace("/", "-")
    return f"{stem}.csv".replace(" ", "_")
