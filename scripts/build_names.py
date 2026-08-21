"""Build a name dictionary out of the pages this archive typed rather than wrote.

The recogniser is at its ceiling on cursive — measured, not guessed — so the
remaining help for a person reading a mangled row is a list of names that
actually occur in these lists, offered as *probable* and never as read.

Where such a list comes from matters. A general name dictionary would be
somebody else's idea of which names exist; these ships carried Italians,
Spaniards, Portuguese and Syrians to Santos between 1917 and 1925, and the names
on them are the names on them. So the dictionary is built from the archive's own
typewritten pages, which the recogniser reads at a character error rate of 0.01,
and from every row a person has typed by hand.

    .venv/bin/python scripts/build_names.py            # writes data/names.json
    .venv/bin/python scripts/build_names.py --min 2    # only names seen twice

Nothing is trained and nothing is guessed here: it is a frequency count of what
the clean pages say.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desembarque.search import _is_printed_word, is_heading   # noqa: E402
from desembarque.voyage import _is_form_word                  # noqa: E402

# What counts as a clean reading: the recogniser's own score, which is worth
# little as a measure of truth on cursive and a great deal on typescript, where
# it is either sure or empty.
CLEAN_SCORE = 0.95
WORD = re.compile(r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\-]{2,}$")
# What people were, not who they were. These reach the name column on pages read
# before the column was measured from the printing, and a profession offered as
# a probable *name* is exactly the kind of confident wrong answer this tool is
# built to avoid.
TRADES = """lavrador trabalhador agricultor jornaleiro jornalier negociante
    comerciante commerciante domestica doméstica dona casa marinheiro alfaiate
    sapateiro carpinteiro pedreiro costureira cozinheira lavradora empregada
    estudante menor comercio commercio nenhuma nenhum professor medico
    engenheiro operario operário motorista padeiro ferreiro barbeiro
    servente vendedor caixeiro industrial fazendeiro criada""".split()


def fold(text: str) -> str:
    s = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in s if not unicodedata.combining(c)).upper()


def words_of(row: dict) -> list[str]:
    text = row.get("name_raw") or ""
    return [w for w in re.split(r"\s+", text.strip()) if WORD.match(w)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "transcriptions")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "names.json")
    ap.add_argument("--min", type=int, default=1, help="keep names seen this often")
    args = ap.parse_args(argv)

    counts: Counter[str] = Counter()
    typed = handwritten = people = 0
    for f in sorted(args.cache.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for r in d.get("rows") or []:
            if is_heading(r.get("name_raw") or ""):
                continue          # the column caption is not a passenger
            conf = (r.get("conf") or {}).get("surname")
            by_hand = r.get("source") == "manual"
            if not by_hand and (conf is None or conf < CLEAN_SCORE):
                handwritten += 1
                continue
            people += 1
            typed += 0 if by_hand else 1
            for w in words_of(r):
                # the form's own printing gets read as cleanly as a name and is
                # exactly what a dictionary must not suggest
                low = w.lower()
                if (_is_printed_word(low) or _is_form_word(low)
                        or any(difflib.SequenceMatcher(None, fold(low), fold(t)).ratio() >= 0.85
                               for t in TRADES)):
                    continue
                counts[fold(w)] += 1

    kept = {w: n for w, n in counts.items() if n >= args.min}
    args.out.write_text(json.dumps(
        {"note": "Names counted from this archive's own typewritten pages and "
                 "from rows a person typed. Not a general name dictionary: it is "
                 "what these ships carried.",
         "built_from": {"clean_rows": people, "typed_rows": typed,
                        "rows_left_out": handwritten},
         "names": dict(sorted(kept.items(), key=lambda kv: (-kv[1], kv[0])))},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(kept)} names from {people} clean rows "
          f"({handwritten} handwritten rows left out) -> {args.out}")
    print("Rebuild this after a corpus refresh: the pages read before the table "
          "was measured from its printing put professions and form words in the "
          "name column, and those become probable names here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
