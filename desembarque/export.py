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
    "origem", "sobrenome_origem", "score_motor",
]


# Where a row's surname came from. A surname the clerk wrote and a surname
# inherited from the row above are different claims, and on a family list most
# rows are the second kind: a spreadsheet that does not say which is which
# invites somebody to take an inference to a registry as a reading.
SURNAME_SOURCE = {"mark": "aspas de repetição",
                  "indent": "recuo sob as aspas",
                  "position": "posição na lista (inferido)"}


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
            "sobrenome_origem": (SURNAME_SOURCE.get(row.get("ditto_source"), "herdado")
                                 if row.get("ditto") else "lido"),
            "score_motor": conf.get("surname") if conf.get("surname") is not None else "",
        })
    return buf.getvalue()


HIT_FIELDS = [
    "consulta", "leitura", "notacao", "arquivo", "pagina", "linha",
    "navio", "companhia", "ano", "origem_do_ano", "pontuacao", "achado_por",
    "score_motor",
]

# Why a row came back. A name that resembles what was typed is a different kind
# of answer from every passenger on a ship that was typed, and somebody ordering
# copies from the archive is entitled to know which they are looking at.
FOUND_BY = {"ship": "todos os passageiros deste navio",
            "line": "todos os passageiros desta companhia",
            "year": "todas as chegadas deste ano",
            # a row that shares no trigram with the query, found by comparing
            # letters within the crossing that was named
            "letters": "comparação letra a letra dentro da viagem indicada",
            None: "semelhança com o nome procurado"}


def hits_to_csv(query: str, hits: list[dict]) -> str:
    """Search results as CSV: candidates to check against the scans, not matches.

    The list a person takes to the archive. Every row says where to look — the
    dossier's notation, the page, the line — and what it is: `pontuacao` is how
    much the reading resembles what was typed, and `score_motor` is the
    recogniser's own decode score, which stays high on confident nonsense.
    """
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=HIT_FIELDS, extrasaction="ignore")
    w.writeheader()
    for h in hits:
        w.writerow({
            "consulta": query,
            "leitura": h.get("text") or "",
            "notacao": h.get("notation") or "",
            "arquivo": h.get("file") or "",
            "pagina": h.get("page") or "",
            "linha": h.get("row") or "",
            "navio": h.get("ship") or "",
            "companhia": h.get("line") or "",
            "ano": h.get("year") or "",
            "origem_do_ano": h.get("year_source") or "",
            "pontuacao": h.get("score") if h.get("score") is not None else "",
            "achado_por": FOUND_BY.get(h.get("matched"), FOUND_BY[None]),
            "score_motor": h.get("conf") if h.get("conf") is not None else "",
        })
    return buf.getvalue()


def search_filename(query: str) -> str:
    """A filename that says what was searched for."""
    stem = "".join(c if c.isalnum() or c in "-_" else "-" for c in (query or "busca"))
    return f"busca-{stem.strip('-') or 'vazia'}.csv"


def csv_filename(doc: dict) -> str:
    """A filename that says which dossier this came from."""
    stem = (doc.get("notation") or doc.get("file") or "desembarque").replace("/", "-")
    return f"{stem}.csv".replace(" ", "_")
