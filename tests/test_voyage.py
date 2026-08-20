"""The voyage a dossier records: ship, where it sailed from, when it arrived.

Every dossier has a page that says this in print — the interpreter's PARTE form,
or the printed header of the passenger list itself — and none of it is in the
index today. Someone searching for an ancestor knows the ship, or the year, or
the port far more often than they know how a clerk spelled the name, so this is
the cheapest way to cut the pool a name is compared against.

The division of trust is the whole design. Labels are printed and come through
the recogniser well; the values beside them are handwritten and come through
mangled. So labels are matched and the value beside them is reported verbatim.
The one exception is the month, which is one of twelve known words rather than
an open set.

The fixtures below are real recogniser output, not invented: they are what
`PaddleEngine` returns for these pages today, mangling and all.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque.voyage import month_number, parse_voyage

# BR_RJANRIO_OL_0_RPV_PRJ_19845 page 2, verbatim.
PARTE_19845 = """BR.AN.RIO. OL.O. RPV. PR.J, 19845
T.M.
MODELON.4
MINISTERIO DA AGRICULTURA, INDUSTRIA E COMMERCIO
1
SERVIÇO DE POVOAMENTO
Intendencia de Immigração do Porto do Rio de Janeiro
PARTE
do Interprete Arthur K Fexxerria
"Valdivia"
keib
que visitou o paquete Francer
procedente de B. Aires e escalas
entrado em 10 deDesembro de 1924
SAUDE DOS PASSAGEIROS
Bom
MORTALIDADE
Venhum
NÁSCIMENTOS
Nao forve
OBSERVAÇÕES
Entregou 1 lista com 12 immigrantes pendo 10 er sequua Clarse
Espontaneos"""


def test_the_months_are_read_in_portuguese():
    assert month_number("Dezembro") == 12
    assert month_number("janeiro") == 1
    assert month_number("Setembro") == 9


def test_a_month_the_recogniser_mangled_is_still_read():
    """`Dezembro` comes back as `Desembro`, `Março` as `Marco` or `Margo`. A
    month is one of twelve known words, so a near miss is not a guess."""
    assert month_number("Desembro") == 12
    assert month_number("Oatubro") == 10
    assert month_number("Margo") == 3
    assert month_number("Fevereire") == 2


def test_a_word_that_is_not_a_month_is_not_forced_into_one():
    """Twelve buckets accept anything if the distance is generous enough, and a
    wrong month on an arrival record is a wrong record."""
    assert month_number("Buenos Aires") is None
    assert month_number("") is None
    assert month_number("entrado") is None


def test_the_parte_form_is_recognised_as_one():
    v = parse_voyage(PARTE_19845)
    assert v is not None and v.source == "parte"


def test_the_ship_is_taken_from_the_name_in_quotes():
    """The clerk wrote the ship's name in quotation marks and its nationality
    beside `paquete`. Taking whatever follows `paquete` yields `Francer`, which
    is the word Francez badly read — not a ship."""
    v = parse_voyage(PARTE_19845)
    assert v.ship == "Valdivia"
    assert v.flag == "Francer"


def test_where_the_ship_sailed_from_is_kept_verbatim():
    v = parse_voyage(PARTE_19845)
    assert v.origin == "B. Aires e escalas"


def test_the_arrival_date_is_resolved():
    """`entrado em 10 deDesembro de 1924` — the space the recogniser dropped
    between `de` and the month is the normal case, not the exception."""
    v = parse_voyage(PARTE_19845)
    assert v.arrival == "1924-12-10"
    assert v.arrival_raw == "10 deDesembro de 1924"


def test_how_many_people_the_ship_landed():
    """A dossier's headcount says whether a list is complete before anyone reads
    it, and it is printed rather than inferred."""
    v = parse_voyage(PARTE_19845)
    assert v.passengers == 12


def test_a_page_that_is_not_one_of_these_forms_returns_nothing():
    assert parse_voyage("Nome e Cognomes\nNacionalidade\nIdade\nEstado civil") is None
    assert parse_voyage("") is None


def test_a_form_missing_a_field_reports_the_rest():
    """Conservation varies: a torn corner takes the date and leaves the ship."""
    text = PARTE_19845.replace("entrado em 10 deDesembro de 1924", "")
    v = parse_voyage(text)
    assert v.ship == "Valdivia"
    assert v.arrival is None and v.arrival_raw is None


# BR_RJANRIO_OL_0_RPV_PRJ_18224 page 2, verbatim. The same form, and almost
# nothing lands on the same line as its label: the handwriting sits a little
# above the printed baseline, so the detector reports it first.
PARTE_18224 = """BR.AN.RIO.Oh.O.RPV.PR5.1822H
MODELO N. 4
MINISTERIO DA AGRICULTURA, INDUSTRIA E COMMERCIO
SERVIÇO DE POVOAMENTO
Intendencia de Immigração do Porto do Rio. de Janeiro
PARTE
SLomingos Marques
Freina
do Interprete
San-America
Aneronans
que visitou o paquete
Nova forke
procedente de
entrado em Hp de Olluho
de 1922
SAUDE DOS PASSAGEIROS
Bon
MORTALIDADE
Nimhum
NASCIMENTOS
Nao honve
OBSERVAÇÕES
lista com le
immigrantes  3belas
Entregou
Espontaneos"""

# BR_RJANRIO_OL_0_RPV_PRJ_19032 page 2, verbatim. The ship carries one stray
# quotation mark rather than two, and the year sits on the line below its day.
PARTE_19032 = """BRANRI0.040.RPV.PR5.19032
MODELO N. 4
MINISTERIO DA AGRICULTURA, INDUSTRIA E COMMERCIO
SERVIÇO DE POVOAMENTO
Intendencia de Immigração do Porto do Rio de Janeiro
PARTE
Domingos Marques Fereina
do Interprete
"Flighland Boch.
Sngles
que visitou o paquete
procedente de Ponde g prealas
entrado em f de Novemlro
de 1923
SAUDE DOS PASSAGEIROS
Bom
MORTALIDADE
Nmlunn
NASCIMENTOS
Nas houve
OBSERVAÇÕES
Entregou 1 lista com H immigrantes sendo 3 un Segund. Blasre
Espontaneos
Imprensa Nacional — 7695-919"""


def test_a_value_written_above_its_label_still_belongs_to_it():
    """Nothing on this page shares a line with its label. The handwriting sits
    a little above the printed baseline, so the detector reports it first, and
    reading only what follows a label would find nothing at all here."""
    v = parse_voyage(PARTE_18224)
    assert v is not None
    assert v.ship == "San-America"
    assert v.flag == "Aneronans"
    assert v.origin == "Nova forke"


def test_the_year_may_sit_on_the_line_below_the_day():
    """`entrado em f de Novemlro` / `de 1923` is one printed line that the
    detector split in two."""
    v = parse_voyage(PARTE_19032)
    assert v.arrival_raw == "f de Novemlro de 1923"


def test_a_day_the_recogniser_could_not_read_leaves_no_date():
    """`entrado em f de Novemlro` — the day is a stroke the recogniser made an
    `f` of. The month and year are certain and the day is not, so the record
    keeps what was read and asserts no date."""
    v = parse_voyage(PARTE_19032)
    assert v.arrival is None
    assert v.month == 11 and v.year == 1923


def test_one_stray_quotation_mark_is_not_a_quoted_name():
    v = parse_voyage(PARTE_19032)
    assert v.ship == "Flighland Boch"
    assert v.flag == "Sngles"


def test_a_headcount_that_is_not_a_number_is_not_invented():
    """`lista com H immigrantes`. A number nobody can read is not a number."""
    assert parse_voyage(PARTE_19032).passengers is None
    assert parse_voyage(PARTE_18224).passengers is None


# BR_RJANRIO_OL_0_RPV_PRJ_20039 page 2, verbatim. The form prints `de 19__` and
# the clerk completes the year, so the detector reports `de 19 25`.
PARTE_20039 = """BR.AN.RIO.Oh.O.RPV.PR.J.2.0039
MODELO N. 4
MINISTERIO DA AGRICULTURA, INDUSTRIA E COMMERCIO
SERVIÇO DE POVOAMENTO
Intendencia de Immigração do Porto do Rio de Janeiro
PARTE
Baden
do Interprete Acthwr  Ferrevea
que visitou o paquete Allemas
procedente de Hamlurge e emalas
entrado em 1 de Março
de 19 25
SAUDE DOS PASSAGEIROS
Bom
MORTALIDADE
Nenhum
NASCIMENTOS
Nao houve
OBSERVAÇÕES
Entregou I lista com  immigrantes Lendo todos en terccira Clase
Espontaneos
Imprensa Nacional— 7693-919"""


def test_the_century_is_printed_and_the_year_is_written():
    """The form says `de 19` and the clerk fills in `25`, which the detector
    reports as two numbers with a space between them."""
    v = parse_voyage(PARTE_20039)
    assert v.year == 1925
    assert v.arrival == "1925-03-01"


def test_the_ship_is_not_the_line_that_belongs_to_another_label():
    """Here the nationality follows `paquete` on its own line, and the line
    directly above carries the interpreter's name against the interpreter's
    label. The ship is the first line above that belongs to nothing else."""
    v = parse_voyage(PARTE_20039)
    assert v.ship == "Baden"
    assert v.flag == "Allemas"
    assert v.origin == "Hamlurge e emalas"


# The other form: the printed header above a passenger list. Same voyage, said
# differently, and present on every list rather than only on the dossiers that
# kept their PARTE page. BR_..._18738 page 2, verbatim.
LISTA_18738 = """BRANRIO.OLORPV.PRS18738
POLICIA DO PORTO
Scété Géérale de TrasprtMarmes a Vapeur
de 192 3
Lista de entraSa
Formosa
de passageiros no paquete
de 2 toneladas de registro e 119 pessoas de tripulação procedente de
Beuenes crures
com
dias e
horas de viagem, sob o commando de B. allerman
e consignado neste porto ao COMPANHIA COMMERCIAL E MARITIMA.
Ordem
Nome e Cognomes
Nacionalidade"""

# BR_..._16456 page 2, verbatim. The clerk left the date blank, so the printed
# skeleton `Santos, de de 19` is all there is of it.
LISTA_16456 = """COMPAGNIE DE NAVIGATION SUD ATLANTIQUE
Santos,
de
de 19
Lista de entrada de passageiros no
(1)
deeldasde registro pessas detripulçã procedente d
com 29 dias e1
horas de viagem, sob o commando de u' Bremonk Ahel.
e consignado neste porto a Antunes dos Santos & Cia.
Ordem
Nome e Cognomes
Nacionalidade"""


def test_the_printed_header_of_a_list_is_recognised_as_its_own_form():
    v = parse_voyage(LISTA_18738)
    assert v is not None and v.source == "lista"


def test_on_a_list_the_name_beside_paquete_is_the_ship_itself():
    """The PARTE form writes the nationality there and the ship elsewhere. This
    form has no nationality field at all, so reading it the same way would file
    every voyage under the wrong word."""
    v = parse_voyage(LISTA_18738)
    assert v.ship == "Formosa"
    assert v.flag is None


def test_the_origin_may_be_written_on_the_line_after_its_label():
    """`procedente de` ends the line here and the port begins the next. On the
    PARTE form the same value sits on the line above. Both are the same printed
    line of the form as far as the page is concerned."""
    assert parse_voyage(LISTA_18738).origin == "Beuenes crures"
    assert parse_voyage(PARTE_18224).origin == "Nova forke"


def test_the_shipping_line_is_the_first_thing_printed_on_the_sheet():
    """It is printed letterhead, so it survives the scan when the handwriting
    does not — and it is what someone means when they say 'the Lloyd ship'."""
    assert parse_voyage(LISTA_18738).line == "Scété Géérale de TrasprtMarmes a Vapeur"
    assert parse_voyage(LISTA_16456).line == "COMPAGNIE DE NAVIGATION SUD ATLANTIQUE"


def test_a_blank_date_on_the_form_is_not_read_as_a_date():
    """`Santos, / de / de 19` is the empty skeleton of a date. The clerk never
    filled it in, and inventing 1900 from the printed century would be the
    worst kind of wrong: plausible."""
    v = parse_voyage(LISTA_16456)
    assert v.arrival is None and v.year is None
