"""Identity must survive renaming, and must prefer the document over the filename."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desembarque.identity import (
    Identity, from_cover_text, from_filename, hash_file, identify,
)


def _pdf(tmp_path: Path, name: str, body: bytes = b"%PDF-1.7\nfake\n") -> Path:
    p = tmp_path / name
    p.write_bytes(body)
    return p


def test_hash_is_stable_across_renaming(tmp_path):
    a = _pdf(tmp_path, "BR_RJANRIO_BS_0_RPV_ENT_017397_d0001de0001.pdf")
    h1 = hash_file(a)
    b = tmp_path / "navio do meu bisavo.pdf"
    shutil.move(a, b)
    assert hash_file(b) == h1


def test_hash_differs_for_different_content(tmp_path):
    a = _pdf(tmp_path, "one.pdf", b"%PDF-1.7\naaa\n")
    b = _pdf(tmp_path, "two.pdf", b"%PDF-1.7\nbbb\n")
    assert hash_file(a) != hash_file(b)


def test_reads_notation_out_of_an_archive_filename(tmp_path):
    p = _pdf(tmp_path, "BR_RJANRIO_BS_0_RPV_ENT_017397_d0001de0001.pdf")
    ident = identify(p)
    assert ident.notation == "BS.ENT.017397"
    assert ident.source == "filename"


def test_a_renamed_file_still_identifies_by_hash(tmp_path):
    p = _pdf(tmp_path, "vovo chegou 1924.pdf")
    ident = identify(p)
    assert ident.notation is None
    assert ident.source == "unknown"
    assert len(ident.doc_hash) == 64
    assert "sem notação" in ident.label


def test_cover_card_notation_beats_the_filename(tmp_path):
    """The friend may rename a file wrongly; the document itself is authoritative."""
    p = _pdf(tmp_path, "BR_RJANRIO_BS_0_RPV_ENT_099999_d0001de0001.pdf")
    cover = "PRESIDENCIA DA REPUBLICA ARQUIVO NACIONAL NOTAÇÃO: BR.AN.RIO.OL.0.RPV.PRJ. 15992 VAPOR: ORITA"
    ident = identify(p, cover_text=cover)
    assert ident.notation == "OL.PRJ.15992"
    assert ident.source == "cover"


def test_cover_parser_tolerates_spacing_and_punctuation():
    for text in ["BR.AN.RIO.OL.0.RPV.PRJ. 15992",
                 "BR AN RIO OL 0 RPV PRJ 15992",
                 "BR.RJANRIO.BS.0.RPV.ENT.017397"]:
        got = from_cover_text(text, "h")
        assert got is not None, text
        assert got.index in ("15992", "017397")


def test_cover_parser_returns_none_on_unrelated_text():
    assert from_cover_text("lista de passageiros do vapor gelria", "h") is None


def test_filename_parser_handles_dashes_and_spaces(tmp_path):
    p = _pdf(tmp_path, "BR-RJANRIO-OL-0-RPV-PRJ-15992.pdf")
    assert from_filename(p, "h").notation == "OL.PRJ.15992"


def test_hashing_a_file_twice_reads_it_once(tmp_path, monkeypatch):
    """Resolving a search hit to a filename hashes the folder. At seven thousand
    dossiers that is 25 GB of reading, and it must not happen per query."""
    from desembarque import identity as ident
    p = tmp_path / "a.pdf"
    p.write_bytes(b"%PDF-1.7\nhello")

    calls = []
    real = ident.hash_file
    monkeypatch.setattr(ident, "hash_file", lambda q: (calls.append(q), real(q))[1])

    first = ident.cached_hash(p)
    second = ident.cached_hash(p)
    assert first == second and len(calls) == 1


def test_a_changed_file_is_hashed_again(tmp_path, monkeypatch):
    from desembarque import identity as ident
    p = tmp_path / "a.pdf"
    p.write_bytes(b"%PDF-1.7\nhello")
    first = ident.cached_hash(p)
    p.write_bytes(b"%PDF-1.7\nhello there, different bytes entirely")
    assert ident.cached_hash(p) != first
