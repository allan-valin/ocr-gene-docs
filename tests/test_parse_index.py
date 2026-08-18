"""Tests for the SIAN index parser.

Fixtures are real lines copied out of the saved index PDFs (pdftotext -layout),
including the wrapped-title and letter-suffix cases that occur in the corpus.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from parse_index import Entry, build_url, fix_mojibake, parse_lines


def test_parses_santos_entry():
    lines = [
        "  • BR RJANRIO BS.0.RPV, ENT.13936 - relação de passageiros do vapor itaquera. - Dossiê"
    ]
    (e,) = parse_lines(lines)
    assert e.fundo == "BS"
    assert e.series == "ENT"
    assert e.index == "13936"
    assert e.ship == "itaquera"


def test_parses_rio_entry_with_rv_suffix():
    lines = [
        "  • BR RJANRIO OL.0.RPV, PRJ.15938 - relação de passageiros do vapor orita (rv 195) -"
    ]
    (e,) = parse_lines(lines)
    assert e.fundo == "OL"
    assert e.series == "PRJ"
    assert e.index == "15938"
    assert e.ship == "orita"
    assert e.rv == "195"


def test_joins_title_wrapped_across_lines():
    lines = [
        "  • BR RJANRIO BS.0.RPV, ENT.13949 - relação de passageiros do vapor p. de satrustegui.",
        "    - Dossiê",
    ]
    (e,) = parse_lines(lines)
    assert e.ship == "p. de satrustegui"


def test_keeps_letter_suffix_on_index():
    lines = [
        "  • BR RJANRIO OL.0.RPV, PRJ.15942A - relação de passageiros do vapor samara (rv 195) -"
    ]
    (e,) = parse_lines(lines)
    assert e.index == "15942A"


def test_ignores_navigation_chrome():
    lines = [
        "  ◦ Relações Vapores Entrada Porto Santos",
        "1 of 198                                            8/18/26, 21:26",
        "  • BR RJANRIO BS.0.RPV, ENT.13940 - relação de passageiros do vapor saga. - Dossiê",
    ]
    assert [e.index for e in parse_lines(lines)] == ["13940"]


def test_santos_index_is_zero_padded_to_six():
    e = Entry(fundo="BS", series="ENT", index="17397", ship="gelria", rv=None)
    assert build_url(e) == (
        "https://imagem.sian.an.gov.br/acervo/derivadas/BR_RJANRIO_BS/0/RPV/ENT/"
        "017397/BR_RJANRIO_BS_0_RPV_ENT_017397_d0001de0001.pdf"
    )


def test_rio_index_is_not_padded():
    e = Entry(fundo="OL", series="PRJ", index="17322", ship="formosa", rv=None)
    assert build_url(e) == (
        "https://imagem.sian.an.gov.br/acervo/derivadas/BR_RJANRIO_OL/0/RPV/PRJ/"
        "17322/BR_RJANRIO_OL_0_RPV_PRJ_17322_d0001de0001.pdf"
    )


def test_letter_suffix_pads_only_the_digits():
    e = Entry(fundo="BS", series="ENT", index="14091A", ship="x", rv=None)
    assert "/ENT/014091A/" in build_url(e)
    assert build_url(e).endswith("BR_RJANRIO_BS_0_RPV_ENT_014091A_d0001de0001.pdf")


def test_lettered_dossier_is_distinct_from_unlettered():
    lettered = Entry(fundo="BS", series="ENT", index="14091A", ship="x", rv=None)
    plain = Entry(fundo="BS", series="ENT", index="14091", ship="y", rv=None)
    assert build_url(lettered) != build_url(plain)
    assert "/ENT/014091/" in build_url(plain)


def test_multi_file_index_numbers_every_part():
    e = Entry(fundo="BS", series="ENT", index="17397", ship="gelria", rv=None)
    urls = [build_url(e, part=n, total=2) for n in (1, 2)]
    assert urls[0].endswith("_d0001de0002.pdf")
    assert urls[1].endswith("_d0002de0002.pdf")


def test_repairs_utf8_read_as_latin1():
    assert fix_mojibake("relaÃ§Ã£o") == "relação"
    assert fix_mojibake("relação") == "relação"
