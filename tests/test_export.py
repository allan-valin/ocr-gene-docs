"""Export is what leaves the tool, so it says what was read and who read it.

A row that an engine guessed and a row a person confirmed are not the same
evidence, and a registrar looking at a spreadsheet cannot tell them apart
unless the file says so. Every row therefore carries where it came from, which
page and line it sits on, and the verbatim text alongside any split of it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque.export import rows_to_csv


DOC = {
    "notation": "BS.ENT.013990", "file": "BR_..._013990.pdf", "ship": "itapema",
    "engine": "paddle", "schema": 4,
    "rows": [
        {"n": 1, "page": 2, "name_raw": "Nayomgo Cassaudii",
         "surname": "Nayomgo", "given": "Cassaudii", "conf": {"surname": 0.79}},
        {"n": 2, "page": 2, "name_raw": "", "surname": None, "given": None,
         "conf": {"surname": 0.0}},
        {"n": 3, "page": 2, "name_raw": "Jaim C. Gil", "surname": "Jaim C.",
         "given": "Gil", "source": "manual"},
    ],
}


def lines(csv_text):
    return [l for l in csv_text.splitlines() if l.strip()]


def test_every_row_is_exported_including_the_blank_ones():
    """A blank line on the form means the information was not known. Dropping
    it would silently renumber the page it came from."""
    out = lines(rows_to_csv(DOC))
    assert len(out) == 4, "header plus three rows"


def test_the_verbatim_reading_is_carried():
    out = rows_to_csv(DOC)
    assert "Nayomgo Cassaudii" in out


def test_a_row_says_which_page_and_line_it_came_from():
    head, first = lines(rows_to_csv(DOC))[:2]
    cols = head.split(",")
    assert "pagina" in cols and "linha" in cols
    assert first.split(",")[cols.index("linha")] == "1"
    assert first.split(",")[cols.index("pagina")] == "2"


def test_a_row_says_whether_a_person_or_the_engine_produced_it():
    head = lines(rows_to_csv(DOC))[0].split(",")
    assert "origem" in head
    body = lines(rows_to_csv(DOC))[1:]
    assert body[0].split(",")[head.index("origem")] == "paddle"
    assert body[2].split(",")[head.index("origem")] == "manual"


def test_the_document_is_identified_on_every_row():
    """A spreadsheet gets sorted and filtered; a row has to stand alone."""
    head = lines(rows_to_csv(DOC))[0].split(",")
    for row in lines(rows_to_csv(DOC))[1:]:
        assert row.split(",")[head.index("notacao")] == "BS.ENT.013990"


def test_a_name_with_a_comma_does_not_break_the_columns():
    doc = {"notation": "X", "rows": [{"n": 1, "page": 1,
           "name_raw": 'SILVA, JOSE "ZE"', "surname": "SILVA", "given": "JOSE"}]}
    out = lines(rows_to_csv(doc))
    import csv as _csv
    parsed = list(_csv.reader(out))
    assert parsed[1][parsed[0].index("nome_lido")] == 'SILVA, JOSE "ZE"'


def test_a_document_with_no_rows_still_exports_its_header():
    out = lines(rows_to_csv({"notation": "X", "rows": []}))
    assert len(out) == 1


def test_confidence_is_exported_but_not_dressed_up_as_accuracy():
    """It is the recogniser's own decode score, which stays high on confident
    nonsense. It is exported under a name that says so rather than "precisao"."""
    head = lines(rows_to_csv(DOC))[0].split(",")
    assert "score_motor" in head
    assert "precisao" not in head and "confianca" not in head


VOYAGE_DOC = {
    "notation": "OL.PRJ.19845", "file": "BR_..._19845.pdf", "engine": "paddle",
    "voyage": {"source": "parte", "ship": "Valdivia", "origin": "B. Aires e escalas",
               "arrival": "1924-12-10", "year": 1924},
    "rows": [{"n": 1, "page": 2, "name_raw": "Guudo Camtadore",
              "surname": "Guudo", "given": "Camtadore", "conf": {"surname": 0.6}}],
}


def test_the_ship_and_the_date_travel_with_the_row():
    """A spreadsheet taken to an office says an ancestor arrived on a named ship
    on a named date. Without those the row says only that somebody with a
    mangled name is written on a page somewhere."""
    from desembarque.export import rows_to_csv
    import csv as _csv
    out = list(_csv.reader(lines(rows_to_csv(VOYAGE_DOC))))
    head, row = out[0], out[1]
    assert row[head.index("navio")] == "Valdivia"
    assert row[head.index("data_chegada")] == "1924-12-10"
    assert row[head.index("procedencia")] == "B. Aires e escalas"


def test_a_year_without_a_full_date_is_exported_as_the_year():
    from desembarque.export import rows_to_csv
    import csv as _csv
    doc = {**VOYAGE_DOC, "voyage": {"ship": "Baden", "year": 1925}}
    out = list(_csv.reader(lines(rows_to_csv(doc))))
    assert out[1][out[0].index("data_chegada")] == "1925"


def test_a_document_that_states_no_voyage_leaves_those_columns_empty():
    """Empty means the page did not say. It must not mean the tool guessed."""
    from desembarque.export import rows_to_csv
    import csv as _csv
    doc = {k: v for k, v in VOYAGE_DOC.items() if k != "voyage"}
    out = list(_csv.reader(lines(rows_to_csv(doc))))
    assert out[1][out[0].index("navio")] == ""
    assert out[1][out[0].index("data_chegada")] == ""
    assert out[1][out[0].index("procedencia")] == ""


def test_the_ship_the_archive_filed_it_under_is_exported_when_the_page_lost_it():
    """A registrar reading this spreadsheet needs the ship above almost
    anything else, and the page gives one up in about a fifth of dossiers. The
    archive filed all of them under a typed name."""
    from desembarque.export import rows_to_csv
    import csv as _csv
    doc = {k: v for k, v in VOYAGE_DOC.items() if k != "voyage"}
    out = list(_csv.reader(lines(rows_to_csv(doc, catalogued="itapuca"))))
    assert out[1][out[0].index("navio")] == "itapuca"


def test_what_the_page_said_is_what_is_exported():
    """The catalogue is somebody's note about the document. The document wins."""
    from desembarque.export import rows_to_csv
    import csv as _csv
    out = list(_csv.reader(lines(rows_to_csv(VOYAGE_DOC, catalogued="itapuca"))))
    assert out[1][out[0].index("navio")] == "Valdivia"


def test_the_company_and_the_port_travel_too():
    from desembarque.export import rows_to_csv
    import csv as _csv
    doc = {**VOYAGE_DOC, "voyage": {**VOYAGE_DOC["voyage"],
                                    "line": "Lloyd Brazileiro", "port": "Santos"}}
    out = list(_csv.reader(lines(rows_to_csv(doc))))
    assert out[1][out[0].index("companhia")] == "Lloyd Brazileiro"
    assert out[1][out[0].index("porto_chegada")] == "Santos"


def test_an_inherited_surname_says_it_was_inherited_and_how():
    """Most rows on a family list carry a repetition mark rather than a name,
    and some carry nothing at all and take the surname from their position.
    A spreadsheet that cannot tell those from a reading invites somebody to take
    an inference to a registry as evidence."""
    doc = {**DOC, "rows": [
        {"n": 1, "page": 2, "name_raw": "Martinez Francisco",
         "surname": "Martinez", "given": "Francisco"},
        {"n": 2, "page": 2, "name_raw": '" Maria', "surname": "Martinez",
         "given": "Maria", "ditto": ["surname"], "ditto_source": "mark"},
        {"n": 3, "page": 2, "name_raw": "Manuel", "surname": "Martinez",
         "given": "Manuel", "ditto": ["surname"], "ditto_source": "position"},
    ]}
    rows = lines(rows_to_csv(doc))
    head = rows[0]
    assert "sobrenome_origem" in head
    assert "lido" in rows[1]
    assert "aspas de repetição" in rows[2]
    assert "inferido" in rows[3]
    # and the reading itself is untouched by any of it
    assert '" Maria' in rows[2] and "Manuel" in rows[3]
