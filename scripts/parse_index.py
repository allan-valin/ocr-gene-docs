"""Parse saved SIAN result pages into a download catalog.

The Arquivo Nacional search UI is paginated HTML behind a login; the practical
way to get a corpus list is to save the result pages as PDF and read them back.
This turns those PDFs into one row per dossier, with the direct image URL.

Usage:
    python scripts/parse_index.py indices/ -o catalog.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

BASE = "https://imagem.sian.an.gov.br/acervo/derivadas"

# "BR RJANRIO BS.0.RPV, ENT.13936 - relação de passageiros do vapor itaquera. - Dossiê"
ENTRY_RE = re.compile(
    r"BR\s+RJANRIO\s+(?P<fundo>[A-Z]{2})\.0\.RPV,\s*"
    r"(?P<series>[A-Z]{3})\.(?P<index>\d+[A-Z]?)\s*-\s*(?P<rest>.*)"
)
SHIP_RE = re.compile(r"vapor\s+(?P<ship>.+?)\s*$", re.IGNORECASE)
RV_RE = re.compile(r"\(\s*rv\s*(?P<rv>[\w\s]+?)\s*\)", re.IGNORECASE)
# page furniture from the saved browser print
CHROME_RE = re.compile(r"^\s*(\d+\s+of\s+\d+|Arquivo Nacional\b|https?://)")

# Santos (BS) folders are zero-padded to six digits; Rio (OL) folders are not.
PAD = {"BS": 6}


@dataclass
class Entry:
    fundo: str
    series: str
    index: str
    ship: str | None
    rv: str | None


def fix_mojibake(s: str) -> str:
    """Repair UTF-8 that was decoded as latin-1 ('relaÃ§Ã£o' -> 'relação')."""
    if not any(ch in s for ch in "ÃÂ"):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _clean_title(rest: str) -> tuple[str | None, str | None]:
    rest = fix_mojibake(rest)
    rv_m = RV_RE.search(rest)
    rv = rv_m.group("rv").strip() if rv_m else None
    rest = RV_RE.sub("", rest)
    # drop the trailing level marker ("- Dossiê", "- Item") and stray dashes
    rest = re.sub(r"[-–]\s*(Dossiê|Dossie|Item|Série|Serie)\s*$", "", rest, flags=re.I)
    rest = rest.strip().strip("-").strip()
    ship_m = SHIP_RE.search(rest)
    if not ship_m:
        return None, rv
    ship = ship_m.group("ship").strip().rstrip(".").strip()
    return (ship or None), rv


def parse_lines(lines: list[str]) -> list[Entry]:
    """Parse pdftotext output. Titles wrap, so an entry ends at the next entry."""
    entries: list[Entry] = []
    pending: dict | None = None

    def flush() -> None:
        nonlocal pending
        if pending is None:
            return
        ship, rv = _clean_title(pending["rest"])
        entries.append(
            Entry(
                fundo=pending["fundo"],
                series=pending["series"],
                index=pending["index"],
                ship=ship,
                rv=rv,
            )
        )
        pending = None

    for raw in lines:
        line = raw.rstrip()
        m = ENTRY_RE.search(line)
        if m:
            flush()
            pending = m.groupdict()
            continue
        if pending is None:
            continue
        stripped = line.strip().lstrip("•◦▪").strip()
        # a wrapped continuation is plain text; anything else closes the entry
        if not stripped or CHROME_RE.match(line) or stripped.startswith("_"):
            flush()
            continue
        pending["rest"] += " " + stripped
    flush()
    return entries


def build_url(e: Entry, part: int = 1, total: int = 1) -> str:
    """Direct URL for one PDF of a dossier.

    Filenames end in d{part}de{total}; `total` is how many PDFs the dossier has,
    which is only known after fetching the first one (or from the archive page).
    """
    width = PAD.get(e.fundo, 0)
    # Some dossiers carry a letter suffix (14091A). Only the digits are padded,
    # and the lettered dossier is distinct from the unlettered one of the same number.
    num, letter = re.match(r"(\d+)([A-Z]*)", e.index).groups()
    folder = (num.zfill(width) if width else num) + letter
    stem = f"BR_RJANRIO_{e.fundo}_0_RPV_{e.series}_{folder}"
    return f"{BASE}/BR_RJANRIO_{e.fundo}/0/RPV/{e.series}/{folder}/{stem}_d{part:04d}de{total:04d}.pdf"


def pdf_lines(path: Path) -> list[str]:
    out = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        check=True,
    )
    return out.stdout.decode("utf-8", errors="replace").splitlines()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src", type=Path, help="directory of saved index PDFs")
    ap.add_argument("-o", "--out", type=Path, default=Path("catalog.jsonl"))
    args = ap.parse_args(argv)

    pdfs = sorted(args.src.rglob("*.pdf"))
    if not pdfs:
        print(f"no PDFs under {args.src}", file=sys.stderr)
        return 1

    seen: dict[tuple[str, str, str], Entry] = {}
    duplicates = 0
    for pdf in pdfs:
        found = parse_lines(pdf_lines(pdf))
        for e in found:
            key = (e.fundo, e.series, e.index)
            if key in seen:
                duplicates += 1
                continue
            seen[key] = e
        print(f"{pdf.relative_to(args.src)}: {len(found)} entries", file=sys.stderr)

    with args.out.open("w", encoding="utf-8") as fh:
        for e in sorted(seen.values(), key=lambda x: (x.fundo, x.index)):
            row = asdict(e)
            row["url"] = build_url(e)
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    no_ship = sum(1 for e in seen.values() if not e.ship)
    lettered = sum(1 for e in seen.values() if not e.index.isdigit())
    print(
        f"\n{len(seen)} unique dossiers -> {args.out} "
        f"({duplicates} duplicate rows dropped, {no_ship} without a ship name, "
        f"{lettered} with a letter-suffixed index)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
