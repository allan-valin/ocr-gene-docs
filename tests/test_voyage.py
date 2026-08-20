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


def test_the_months_are_read_in_french_too():
    """The forms are Brazilian and the shipping companies are not. A list
    printed by the Compagnie de Navigation Sud Atlantique has its date written
    `Octobre`, and reading only Portuguese loses the year of every French line
    in the corpus."""
    assert month_number("Octobre") == 10
    assert month_number("Juillet") == 7
    assert month_number("Février") == 2
    assert month_number("décembre") == 12


def test_the_extra_vocabulary_does_not_soften_the_test():
    """Twice as many words to match against is twice as many ways to match
    something that is not a month."""
    for word in ("Buenos Aires", "entrado", "paquete", "Bordeaux", "Santos",
                 "immigrantes", "Interprete", "Marseille"):
        assert month_number(word) is None, word


# BR_..._16583 page 2, verbatim. A French line's list, dated in French, with the
# port written where the form asks for it.
LISTA_16583 = """POLICIA DO PORTO
1
COMPAGNIE DE NAVIGATION SUD ATLANTIQUE
Nio Sumalos,
Octobre
de 1919
de
de5224
Bondeaux
pessoas de tripulação procedente de
(2)
Jouay Theodore
dias"""


def test_a_list_dated_in_french_still_gives_up_its_year():
    """This form has no `entrado em`. The date is written where the letterhead
    leaves room for it, and on a French line it is written in French."""
    v = parse_voyage(LISTA_16583)
    assert v.month == 10
    assert v.year == 1919


def test_a_date_with_no_readable_day_is_still_not_a_date():
    v = parse_voyage(LISTA_16583)
    assert v.arrival is None


def test_the_port_is_taken_from_where_the_form_asks_for_it():
    """`Santos,` and `Rio de Janeiro,` are printed or written above the date,
    and the comma is the form's, not the clerk's."""
    assert parse_voyage(LISTA_16456).port == "Santos"
    assert parse_voyage(LISTA_16583).port == "Nio Sumalos"


# BR_..._014486 page 2, verbatim. A third printing of the same list header, from
# a Brazilian coastal line, with the port on its own labelled line.
LISTA_014486 = """B5.RPV. ENT 014486
CA S
EMPREZA NACIONAL DE NAVEGAÇÃO HOEPCKE
HOEPCKE
EXT  EO
Santos
em 19 de Marco
Porto de
de 1919
entrrds
lime e  comande dAthur Loe Cad
consignado meste porte a Vietar Broithaupt
LASSE
NUMERO
NOMES
ORDEM"""


def test_a_list_header_no_two_companies_print_the_same_way():
    """Each shipping line had its own forms printed. Matching only the exact
    wording of one of them leaves the rest of the corpus unread — this sheet
    says `consignado meste porte`, and the phrase never matches."""
    v = parse_voyage(LISTA_014486)
    assert v is not None and v.source == "lista"
    assert v.line == "EMPREZA NACIONAL DE NAVEGAÇÃO HOEPCKE"


def test_a_date_written_without_entrado_still_resolves():
    """`em 19 de Marco` / `de 1919`. The month anchors it, the day is beside the
    month, and the year is on the line the detector split off."""
    v = parse_voyage(LISTA_014486)
    assert v.arrival == "1919-03-19"


def test_the_parte_form_is_still_read_as_a_parte_form():
    """Widening what counts as a list header must not start pulling the other
    form into it — they disagree about what the word beside `paquete` means."""
    for text in (PARTE_19845, PARTE_18224, PARTE_19032, PARTE_20039):
        assert parse_voyage(text).source == "parte"


# The same page read at a workable size. Scaling the scan down before detection
# also groups the lines better: the ship and its nationality, split across three
# lines at full resolution, come back on the one printed line they share.
PARTE_19845_SCALED = """BR.AN.RIO. OL.O. RPV. PR.J, 19845
TM.
MODELO N. 4
MINISTERIO DA AGRICULTURA, INDUSTRIA E COMMERCIO
1
SERVIÇO DE POVOAMENTO
Intendencia de Immigração do Porto do Rio de Janeiro
PARTE
do Interprete Arthur K Fexerria
que visiton o paquete trancer "Valdivia"
procedente de B. Aires e escalas
entrado em 10 de Desembro de 1924
SAUDE DOS PASSAGEIROS
Bom
MORTALIDADE
Venhum
NÁSCIMENTOS
Nao forve
OBSERVAÇÕES
Entregou 1 lista com 12 immigrantes"""


def test_the_ship_is_not_left_inside_its_own_nationality():
    """Where the whole printed line comes back at once, the words beside
    `paquete` are the nationality *and* the quoted ship. Reporting both as the
    nationality would file the Valdivia's flag as `trancer "Valdivia"`."""
    v = parse_voyage(PARTE_19845_SCALED)
    assert v.ship == "Valdivia"
    assert v.flag == "trancer"


def test_the_same_page_reads_the_same_at_either_size():
    """Scaling is a speed decision, and it must not be a transcription
    decision. The two readings of this page differ in how the detector grouped
    the lines, not in what the page says."""
    big, small = parse_voyage(PARTE_19845), parse_voyage(PARTE_19845_SCALED)
    for field in ("ship", "origin", "arrival", "year", "month", "passengers"):
        assert getattr(big, field) == getattr(small, field), field


# Three more printings, read off real pages by the header pass. Every shipping
# line worded its own form: `Relação dos passageiros que desembarcaram` here,
# `Lista de entrada de passageiros` there, `vapor` for what another calls
# `paquete`.
HEADER_013990 = """BS.RPV.ENT 013990
1
MODELO
A-80
Conpanhia Nacional de Navegação Costeira
ÉRIIEL
orto
Facional
Relação dos passageiros que desembarcaram neste porto vindo no vapor."""

HEADER_014037 = """BS.FRPV.ENT.014037
4
POLICIA DO PORTO
 Lloyd Brazileiro
Santos, 2.3 de Jen
1917
entirsa
RepartiçãodaPolicia"""

HEADER_16548 = """BR.AN.RIO.OL.0.RPVPRJ.16548
No. 461B.
The Koyal Mail Steam Packet Company.
metear
2104
Relação dos passageiros que desembarcaram n'este porto vindos no paquete Inglez
de
toneladas
149
Buenos Aires"""


def test_a_form_that_says_vapor_rather_than_paquete_is_still_a_list():
    v = parse_voyage(HEADER_013990)
    assert v is not None and v.source == "lista"
    assert v.line == "Conpanhia Nacional de Navegação Costeira"


def test_the_shipping_line_survives_where_the_rest_of_the_header_does_not():
    """The letterhead is printed and large; the clerk's writing beside it is
    neither. On this page the line is all that came back, and it is worth
    having on its own — it is what someone means by "the Lloyd ship"."""
    v = parse_voyage(HEADER_014037)
    assert v.line == "Lloyd Brazileiro"


def test_the_port_may_have_the_date_written_after_it_on_the_same_line():
    """`Santos, 2.3 de Jen` — the form prints the comma and the clerk writes on
    past it."""
    assert parse_voyage(HEADER_014037).port == "Santos"


def test_a_nationality_beside_paquete_is_not_recorded_as_a_ship():
    """`vindos no paquete Inglez` names the flag, not the vessel. Filing
    `Inglez` as a ship would put a hundred unrelated voyages under one name and
    make searching by ship worse than not searching by ship."""
    v = parse_voyage(HEADER_16548)
    assert v.flag == "Inglez"
    assert v.ship != "Inglez"


def test_a_number_off_the_form_is_not_a_ship():
    """`2104` sits where the ship's name should be on this sheet. A ship filed
    under a number is a ship nobody can search for, and worse, it is a claim the
    page never made."""
    assert parse_voyage(HEADER_16548).ship is None


def test_a_fragment_of_the_letterhead_is_not_a_ship():
    """The detector reports `Facional` — half of `Navegação Costeira`'s
    `Nacional`, broken off the printed letterhead directly above. It is the
    printing, not the vessel."""
    v = parse_voyage(HEADER_013990)
    assert v.ship is None
    assert v.line == "Conpanhia Nacional de Navegação Costeira"


def test_a_scattering_of_letters_is_not_a_name():
    """Real output from the corpus run: `ri  ad` was filed as a ship and
    `RI VE` as a port of origin. Both are the detector's account of a rubber
    stamp. A name has a word in it."""
    from desembarque.voyage import plausible_value
    assert plausible_value("ri  ad") is None
    assert plausible_value("RI VE") is None
    assert plausible_value("Itapuca") == "Itapuca"
    assert plausible_value("B. Aires e escalas") == "B. Aires e escalas"


def test_a_month_with_no_year_beside_it_is_not_a_date():
    """Also from the run: `Lista de entrada de passagiras no Paguete...` was
    recorded as March, because one word in a badly-read line came within reach
    of a month name. On the dateline there is no `entrado em` to vouch for it,
    so the year standing next to it is what makes it a date at all."""
    v = parse_voyage("""POLICIA DO PORTO
Lloyd Brazileiro
Santos,
Lista de entrada de passagiras no Paguete aco nal dapuna" RI""")
    assert v is not None
    assert v.month is None and v.arrival_raw is None


def test_two_pages_of_one_dossier_are_read_together():
    """A dossier states its voyage twice — the header above the list, and the
    interpreter's PARTE — and the two are good at different things. The header
    is printed and gives up the shipping line and the port; the ship's name and
    the date are handwritten there and mostly lost, while the PARTE form gives
    them up readily. Taking only the first form found throws away the half the
    other one had."""
    from desembarque.voyage import merge_voyages
    header = parse_voyage(HEADER_014037)          # line and port, no ship
    parte = parse_voyage(PARTE_19845)             # ship, origin, date
    merged = merge_voyages(header, parte)
    assert merged.line == "Lloyd Brazileiro"
    assert merged.port == "Santos"
    assert merged.ship == "Valdivia"
    assert merged.arrival == "1924-12-10"


def test_the_page_read_first_is_not_overruled_by_the_page_read_after():
    """Filling a gap is not the same as changing an answer. Two forms that
    disagree about the ship are a thing to show a person, not to resolve by
    reading order."""
    from desembarque.voyage import merge_voyages
    a = parse_voyage(PARTE_19845)
    b = parse_voyage(PARTE_20039)
    assert merge_voyages(a, b).ship == "Valdivia"


def test_merging_with_nothing_is_the_thing_itself():
    from desembarque.voyage import merge_voyages
    v = parse_voyage(PARTE_19845)
    assert merge_voyages(None, v) is v
    assert merge_voyages(v, None) is v
    assert merge_voyages(None, None) is None


def test_a_voyage_is_complete_when_it_names_a_ship_and_a_time():
    """Complete enough to stop reading the rest of the dossier for one. The
    shipping line alone does not narrow a search — every Lloyd Brazileiro
    sailing shares it."""
    from desembarque.voyage import is_complete
    assert not is_complete(parse_voyage(HEADER_014037))
    assert is_complete(parse_voyage(PARTE_19845))
    assert not is_complete(None)


# ---- pairing a printed label with the handwriting beside it ------------------
#
# Reading order is not layout. The detector reports fragments roughly top-down,
# and the clerk's hand sits a little above the printed baseline it belongs to,
# so the ship's name arrives *before* the label that names it. These fragments
# are the detector's own output for the header of BS.ENT.013942, boxes and all.

FRAGS_013942 = [
    {"text": "BS.RPV. ENT. 013942", "x0": 419, "y0": 69, "x1": 1218, "y1": 175},
    {"text": "LLOYD ITALIANO", "x0": 548, "y0": 182, "x1": 1272, "y1": 242},
    {"text": "ABR 2 917 2", "x0": 1498, "y0": 186, "x1": 1551, "y1": 427},
    {"text": "SOCIETÀ DI NAVIGAZIONE", "x0": 713, "y0": 253, "x1": 1121, "y1": 287},
    {"text": "SEDE IN GENOVA", "x0": 664, "y0": 347, "x1": 1166, "y1": 391},
    {"text": "SANTOG", "x0": 688, "y0": 459, "x1": 991, "y1": 520},
    {"text": "de", "x0": 1263, "y0": 477, "x1": 1311, "y1": 513},
    {"text": "INDIANA", "x0": 769, "y0": 517, "x1": 1066, "y1": 584},
    {"text": "de(3)toneladas de registro", "x0": 1206, "y0": 533, "x1": 1726, "y1": 592},
    {"text": "Lista de passageiros entrados no vapor(2)",
     "x0": 113, "y0": 550, "x1": 744, "y1": 602},
    {"text": "e(4)|03pessoas de tripulação, procedente de()JENOS AYRES",
     "x0": 168, "y0": 590, "x1": 1281, "y1": 683},
    {"text": "NOME E COGNOMES", "x0": 245, "y0": 820, "x1": 492, "y1": 852},
]

# BS.ENT.013947: the ship is over to the right of a long printed label, with a
# footnote marker `(1)` sitting between them.
FRAGS_013947 = [
    {"text": "POLICIA DO PORTO", "x0": 136, "y0": 135, "x1": 473, "y1": 173},
    {"text": "COMPAGNIE DE NAVIGATION SUD ATLANTIQUE",
     "x0": 656, "y0": 126, "x1": 1757, "y1": 186},
    {"text": "Santos,", "x0": 1145, "y0": 197, "x1": 1256, "y1": 234},
    {"text": "(1)", "x0": 823, "y0": 250, "x1": 854, "y1": 276},
    {"text": "Jaronna", "x0": 1220, "y0": 252, "x1": 1485, "y1": 302},
    {"text": "Lista de entrada de passageiros no",
     "x0": 212, "y0": 267, "x1": 851, "y1": 319},
    {"text": "de3 530 toneladas de registro e", "x0": 103, "y0": 319, "x1": 613, "y1": 396},
    {"text": "Ruenes", "x0": 1258, "y0": 305, "x1": 1445, "y1": 372},
    {"text": "pessoas de tripulação procedente de",
     "x0": 719, "y0": 332, "x1": 1273, "y1": 381},
]


def test_the_ship_is_the_writing_beside_the_label_not_the_line_before_it():
    """`INDIANA` is reported before the label that names it, because the clerk
    wrote it a little higher than the printed baseline. By reading order it is
    two fragments away from `vapor`; by position it is directly beside it."""
    v = parse_voyage("", fragments=FRAGS_013942)
    assert v is not None and v.ship == "INDIANA"


def test_the_rest_of_the_header_still_reads_the_same_way():
    v = parse_voyage("", fragments=FRAGS_013942)
    assert v.line == "LLOYD ITALIANO"
    assert v.origin and "JENOS AYRES" in v.origin


def test_a_footnote_marker_between_label_and_value_is_not_the_value():
    """`(1)` sits closer to the label than the ship does. It is the form's own
    reference mark, and it is not a name."""
    v = parse_voyage("", fragments=FRAGS_013947)
    assert v.ship == "Jaronna"


def test_the_value_has_to_share_the_label_s_line():
    """Something further down the page is not beside anything, however well it
    lines up on the left."""
    from desembarque.voyage import beside_fragment
    label = {"text": "no vapor", "x0": 100, "y0": 500, "x1": 300, "y1": 560}
    below = {"text": "Brasil", "x0": 400, "y0": 900, "x1": 600, "y1": 960}
    assert beside_fragment(label, [label, below]) is None


def test_without_fragments_it_reads_the_text_as_before():
    """Every stored transcription written before the boxes were kept is text
    only, and has to go on being read."""
    assert parse_voyage(PARTE_19845).ship == "Valdivia"


def test_the_form_s_own_printing_is_never_a_ship():
    """From the corpus run, filed as vessels: `Paguete`, `(2) papor hespanhol`,
    `Repartição da Pette`, `de antos`. They are the form's own words, a rubber
    stamp and half the port — everything a label has beside it that is not a
    ship. A wrong ship in the index is worse than no ship: it answers a search
    that should have found nothing."""
    from desembarque.voyage import plausible_ship
    for junk in ("Paguete", "(2) papor hespanhol", "Repartição da Pette",
                 "de antos", "Lista de entrada", "Policia do Porto",
                 "toneladas de registro", "Observações"):
        assert plausible_ship(junk, None) is None, junk


def test_a_vessel_name_survives_the_same_test():
    from desembarque.voyage import plausible_ship
    for ship in ("INDIANA", "Itapuca", "Jaronna", "Valdivia", "Formosa",
                 "Highland Rock", "Baden", "San-America"):
        assert plausible_ship(ship, None) == ship, ship


def test_four_letters_is_not_a_ship_on_this_archive():
    """`RI IVEO` came through the run twice — a port stamp, read as a vessel.
    Ship names in this archive run to five letters and up, and nothing shorter
    survived the readings that were checked against the scans."""
    from desembarque.voyage import plausible_ship
    assert plausible_ship("RI IVEO", None) is None
    assert plausible_ship("Baden", None) == "Baden"
    assert plausible_ship("San-America", None) == "San-America"
