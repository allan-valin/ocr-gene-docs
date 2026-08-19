"""Document identity that survives renaming.

The person using this saves dossiers from the archive under whatever name they
like, so the filename cannot be the key. Two things stand in for it:

* a content hash of the PDF bytes, which is stable across renames, copies and
  re-downloads, and is what the transcription cache is keyed on;
* the notation printed or written on the dossier's cover card, which is the
  citable archival identity and is recovered by transcription, not guessed.

Filenames are still *read* opportunistically, because archive downloads carry
the notation in them, but a name that says nothing is not an error.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

CHUNK = 1 << 20

# BR_RJANRIO_BS_0_RPV_ENT_017397_d0001de0001.pdf, and looser handwritten forms
FILENAME_NOTATION = re.compile(
    r"BR[_\s.-]*RJANRIO[_\s.-]*(?P<fundo>[A-Z]{2})[_\s.-]*0[_\s.-]*RPV[_\s.-]*"
    r"(?P<series>[A-Z]{3})[_\s.-]*(?P<index>\d+[A-Z]?)",
    re.IGNORECASE,
)
# "NOTAÇÃO: BR.AN.RIO.OL.0.RPV.PRJ. 15992" as it appears on a cover card
# the archive writes it as "BR.AN.RIO", "BR AN RIO" and "BR RJANRIO" interchangeably
COVER_NOTATION = re.compile(
    r"BR[.\s,]*(?:RJ)?AN?[.\s,]*RIO[.\s,]*(?P<fundo>[A-Z]{2})[.\s,]*0[.\s,]*RPV[.\s,]*"
    r"(?P<series>[A-Z]{3})[.\s,]*(?P<index>\d+[A-Z]?)",
    re.IGNORECASE,
)


@dataclass
class Identity:
    doc_hash: str
    notation: str | None = None
    fundo: str | None = None
    series: str | None = None
    index: str | None = None
    source: str = "unknown"  # filename | cover | unknown

    @property
    def label(self) -> str:
        return self.notation or f"sem notação ({self.doc_hash[:8]})"


def hash_file(path: Path) -> str:
    """SHA-256 of the file's bytes — the rename-proof cache key."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


# Hashing is cheap once and expensive per query: resolving search hits to
# filenames hashes the whole folder, which at seven thousand dossiers is tens of
# gigabytes of reading. Keyed by mtime and size, so a file edited in place is
# still noticed.
_HASHES: dict[str, tuple[tuple[int, int], str]] = {}


def cached_hash(path: Path) -> str:
    """hash_file, memoised on the file's mtime and size."""
    try:
        st = path.stat()
    except OSError:
        return hash_file(path)
    stamp = (st.st_mtime_ns, st.st_size)
    hit = _HASHES.get(str(path))
    if hit is not None and hit[0] == stamp:
        return hit[1]
    digest = hash_file(path)
    _HASHES[str(path)] = (stamp, digest)
    return digest


def _pack(m: re.Match, source: str, doc_hash: str) -> Identity:
    fundo = m.group("fundo").upper()
    series = m.group("series").upper()
    index = m.group("index").upper()
    return Identity(doc_hash=doc_hash, notation=f"{fundo}.{series}.{index}",
                    fundo=fundo, series=series, index=index, source=source)


def from_filename(path: Path, doc_hash: str) -> Identity:
    m = FILENAME_NOTATION.search(path.stem)
    if m:
        return _pack(m, "filename", doc_hash)
    return Identity(doc_hash=doc_hash)


def from_cover_text(text: str, doc_hash: str) -> Identity | None:
    """Recover the notation from a transcribed cover card."""
    m = COVER_NOTATION.search(text or "")
    return _pack(m, "cover", doc_hash) if m else None


def identify(path: Path, cover_text: str | None = None) -> Identity:
    """Best available identity. The cover card wins: it is the document itself,
    while a filename is whatever the last person typed."""
    doc_hash = hash_file(path)
    if cover_text:
        found = from_cover_text(cover_text, doc_hash)
        if found:
            return found
    return from_filename(path, doc_hash)
