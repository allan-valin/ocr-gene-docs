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

The voyage travels on every row for the same reason the notation does: a
spreadsheet gets sorted and filtered, and a row has to stand alone. Without the
ship and the date the row says only that somebody with a mangled name is written
on a page somewhere, which is not evidence of anything.
"""
from __future__ import annotations

import csv
import io

FIELDS = [
    "notacao", "arquivo", "navio", "companhia", "procedencia", "porto_chegada",
    "data_chegada", "pagina", "linha", "nome_lido", "sobrenome", "nome",
    "origem", "score_motor",
]


def _arrival(voyage: dict) -> str:
    """The date the ship landed, as far as the page actually stated it.

    A full date where all three parts were read, the year alone where the day
    was a stroke nobody can make out. Never a completed guess: a plausible wrong
    date on a document taken to a registry is the worst kind of wrong.
    """
    if voyage.get("arrival"):
        return str(voyage["arrival"])
    return str(voyage.get("year") or "")


def _origin(row: dict, doc: dict) -> str:
    """Who produced this row: a person, or which engine."""
    return row.get("source") or doc.get("engine") or ""


def rows_to_csv(doc: dict, catalogued: str | None = None) -> str:
    """One document's rows as CSV text, header included even when empty.

    `catalogued` is the ship the archive filed this dossier under. The page
    gives up a ship in about a fifth of them and a registrar reading this needs
    one above almost anything else, so the archive's typed name stands in where
    the page said nothing. Where the page said something, it wins: it is the
    document, and the catalogue is somebody's note about it.
    """
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    voyage = doc.get("voyage") or {}
    for row in doc.get("rows") or []:
        conf = row.get("conf") or {}
        w.writerow({
            "notacao": doc.get("notation") or "",
            "arquivo": doc.get("file") or "",
            "navio": voyage.get("ship") or doc.get("ship") or catalogued or "",
            "companhia": voyage.get("line") or "",
            "procedencia": voyage.get("origin") or "",
            "porto_chegada": voyage.get("port") or "",
            "data_chegada": _arrival(voyage),
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
