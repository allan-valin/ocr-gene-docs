"""Tests for the dossier downloader.

Network is stubbed: `probe` returns True for whichever URLs the fake archive
"has", so the fallback ladder can be tested against the real-world shapes we
found (lettered path missing, multi-file dossiers, dead indices).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from download import entry_from_row, resolve_parts, sample_per_source
from parse_index import Entry


def fake_archive(*present: str):
    """Build a probe() that reports only the given URL substrings as existing."""
    return lambda url: any(p in url for p in present)


def test_resolves_the_common_single_file_case():
    e = Entry("BS", "ENT", "17397", "gelria", None)
    urls = resolve_parts(e, probe=fake_archive("017397_d0001de0001"))
    assert len(urls) == 1
    assert urls[0].endswith("017397_d0001de0001.pdf")


def test_discovers_multi_file_dossier_and_returns_every_part():
    e = Entry("BS", "ENT", "14000", "x", None)
    probe = fake_archive("014000_d0001de0003", "014000_d0002de0003", "014000_d0003de0003")
    urls = resolve_parts(e, probe=probe)
    assert len(urls) == 3
    assert urls[0].endswith("d0001de0003.pdf")
    assert urls[-1].endswith("d0003de0003.pdf")


def test_follows_the_cross_reference_when_the_lettered_path_is_absent():
    """A lettered dossier is a catalog stub pointing at the real one.

    14222A is "s. paulo. ver ... ent. 20445": the images live under 020445.
    """
    e = Entry("BS", "ENT", "14222A", "s. paulo", None, see_also=("BS", "ENT", "20445"))
    urls = resolve_parts(e, probe=fake_archive("020445_d0001de0001"))
    assert len(urls) == 1
    assert "/ENT/020445/" in urls[0]


def test_never_strips_the_letter_to_reach_a_different_dossier():
    """014222 exists but is a DIFFERENT dossier; taking it would misattribute a ship."""
    e = Entry("BS", "ENT", "14222A", "s. paulo", None, see_also=("BS", "ENT", "20445"))
    urls = resolve_parts(e, probe=fake_archive("014222_d0001de0001"))
    assert urls == []


def test_lettered_dossier_without_a_cross_reference_is_left_unresolved():
    e = Entry("BS", "ENT", "14999A", "x", None, see_also=None)
    assert resolve_parts(e, probe=fake_archive("014999_d0001de0001")) == []


def test_prefers_lettered_path_when_it_does_exist():
    # 014091A and 014091 are different dossiers; do not silently take the wrong one.
    e = Entry("BS", "ENT", "14091A", "x", None)
    probe = fake_archive("014091A_d0001de0001", "014091_d0001de0001")
    urls = resolve_parts(e, probe=probe)
    assert "/ENT/014091A/" in urls[0]


def test_returns_nothing_when_the_dossier_cannot_be_resolved():
    e = Entry("BS", "ENT", "99999", "x", None)
    assert resolve_parts(e, probe=fake_archive()) == []


def test_unlettered_fallback_is_not_tried_for_plain_indices():
    """A plain index that 404s must not fall back onto some other dossier."""
    seen = []

    def probe(url):
        seen.append(url)
        return False

    resolve_parts(Entry("BS", "ENT", "14222", "x", None), probe=probe)
    assert all("/ENT/014222/" in u for u in seen)


def test_entry_from_row_carries_the_cross_reference():
    """Dropping see_also here sends a resolvable dossier to the unresolved pile."""
    row = {
        "fundo": "OL", "series": "PRJ", "index": "18792A", "ship": "vandyck",
        "rv": "230", "source": "RJ/p28.pdf", "see_also": ["OL", "PRJ", "18784"],
    }
    e = entry_from_row(row)
    assert e.see_also == ("OL", "PRJ", "18784")
    assert e.ship == "vandyck"
    assert e.source == "RJ/p28.pdf"


def test_entry_from_row_handles_a_row_without_a_cross_reference():
    e = entry_from_row({"fundo": "BS", "series": "ENT", "index": "13936", "ship": "itaquera"})
    assert e.see_also is None
    assert e.rv is None


def test_samples_n_per_source_page():
    rows = [
        {"source": "SP/p21.pdf", "index": str(i), "fundo": "BS", "series": "ENT"}
        for i in range(20)
    ] + [
        {"source": "RJ/p24.pdf", "index": str(i), "fundo": "OL", "series": "PRJ"}
        for i in range(20)
    ]
    picked = sample_per_source(rows, n=5, seed=1)
    assert len(picked) == 10
    by_src = {}
    for r in picked:
        by_src.setdefault(r["source"], []).append(r)
    assert {k: len(v) for k, v in by_src.items()} == {"SP/p21.pdf": 5, "RJ/p24.pdf": 5}


def test_sampling_is_deterministic_for_a_given_seed():
    rows = [{"source": "a", "index": str(i)} for i in range(50)]
    assert sample_per_source(rows, n=5, seed=42) == sample_per_source(rows, n=5, seed=42)


def test_sampling_takes_everything_when_a_source_is_smaller_than_n():
    rows = [{"source": "tiny", "index": "1"}, {"source": "tiny", "index": "2"}]
    assert len(sample_per_source(rows, n=5, seed=1)) == 2
