"""What the corpus knows about its own voyages, counted.

The voyage fields are only worth the search they narrow, so the useful question
is what actually came out of the corpus: how many dossiers name a ship, how many
resolve to a year, which ships recur. It is also the cheapest check that a
change to the parser has not quietly started filing letterhead as vessels — a
sudden crowd of one-off "ships" is what that looks like from here.
"""
from __future__ import annotations

import difflib
from collections import Counter

from desembarque.voyage import fold

# Two spellings of one vessel, through the same recogniser that mangles the
# surnames. Counting `Valdivia` and `Valdivin` apart would report twice as many
# ships as sailed and hide whatever depth the corpus has. This is the same
# measure and the same threshold the search uses to match a typed ship name.
SAME_SHIP = 0.75


def _cluster(names: list[str]) -> list[tuple[str, int]]:
    """Names grouped by spelling, the commonest spelling naming the group.

    A letterhead read three ways — `Companhia`, `Conpanhia`, `Comnpanhia
    Nacional de Navegação Costeira` — is one company, and listed apart it looks
    like three with one sailing each.
    """
    groups: list[list[str]] = []
    for name in sorted(names, key=lambda n: (-len(n), n)):
        for group in groups:
            if difflib.SequenceMatcher(None, fold(name), fold(group[0])).ratio() >= SAME_SHIP:
                group.append(name)
                break
        else:
            groups.append([name])
    counted = [(Counter(g).most_common(1)[0][0], len(g)) for g in groups]
    return sorted(counted, key=lambda t: (-t[1], t[0]))


def summarise(records: list[dict]) -> dict:
    """Counts over stored transcriptions, for a person deciding what to trust."""
    voyages = [r.get("voyage") or {} for r in records]
    stated = [v for v in voyages if v]
    ships = [v["ship"] for v in stated if v.get("ship")]
    years = Counter(v["year"] for v in stated if v.get("year"))
    return {
        "documents": len(records),
        "with_voyage": len(stated),
        "with_ship": len(ships),
        "with_year": sum(years.values()),
        "with_full_date": sum(1 for v in stated if v.get("arrival")),
        "with_port": sum(1 for v in stated if v.get("port")),
        "with_line": sum(1 for v in stated if v.get("line")),
        "ships": _cluster(ships),
        "years": sorted(years.items()),
        "lines": _cluster([v["line"] for v in stated if v.get("line")]),
    }
