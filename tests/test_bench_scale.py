"""Standing the corpus up at the size of the whole archive, without reading it.

The index is measured at 660 dossiers and the archive holds 7,679, so every
number about memory and cold load in the progress log is an extrapolation from
an eleventh of the corpus. The bench multiplies the transcriptions it already
has so the wall can be walked into on purpose, in a child process with a
memory cap, rather than met by the machine one evening.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from bench_scale import fanout  # noqa: E402
from desembarque.search import load_index  # noqa: E402


def record(doc: str, n: int = 2) -> dict:
    return {"hash": doc, "engine": "paddle", "file": f"{doc}.pdf", "schema": 18,
            "pages": [{"n": 1, "kind": "list"}],
            "rows": [{"page": 1, "n": i, "name_raw": f"MARIA {doc} {i}"}
                     for i in range(n)]}


def cache_of(tmp_path: Path, docs: int = 2) -> Path:
    cache = tmp_path / "transcriptions"
    cache.mkdir()
    for d in range(docs):
        (cache / f"doc{d}.json").write_text(json.dumps(record(f"doc{d}")),
                                            encoding="utf-8")
    return cache


def test_one_copy_is_the_corpus_itself(tmp_path):
    cache = cache_of(tmp_path)
    out = fanout(cache, tmp_path / "x1", 1)
    assert len(list(out.glob("*.json"))) == 2


def test_the_corpus_stands_up_as_many_times_as_asked(tmp_path):
    cache = cache_of(tmp_path)
    out = fanout(cache, tmp_path / "x5", 5)
    assert len(list(out.glob("*.json"))) == 10


def test_every_copy_is_indexed_as_rows_of_its_own(tmp_path):
    """A copy that the index folds back into the original measures nothing."""
    cache = cache_of(tmp_path)
    once = len(load_index(fanout(cache, tmp_path / "x1", 1), engine_only=False))
    five = len(load_index(fanout(cache, tmp_path / "x5", 5), engine_only=False))
    assert once == 4
    assert five == 5 * once


def test_standing_it_up_again_does_not_double_it(tmp_path):
    """The bench is run repeatedly; a leftover directory must not accumulate."""
    cache = cache_of(tmp_path)
    fanout(cache, tmp_path / "x3", 3)
    out = fanout(cache, tmp_path / "x3", 3)
    assert len(list(out.glob("*.json"))) == 6
