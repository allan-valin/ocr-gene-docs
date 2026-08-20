"""Transcription engine interface, and the registry the app resolves it through.

No engine is wired up yet. That is deliberate rather than pending: the chosen
engine is an open-weight model run locally (see the spec's engine decision), and
until one is installed this returns an explicit "unavailable" instead of
plausible-looking rows. A legal-evidence corpus cannot absorb invented data, so
an absent engine must look absent.

An engine is any object with:

    name: str
    available() -> bool
    transcribe_page(image: Path, kind: str) -> PageResult

where `kind` is the page classification ("cover" or "list"), since a cover card
and a passenger table need different prompting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class PageResult:
    """One page's transcription. `rows` empty is a legitimate answer."""
    kind: str = "unknown"          # cover | list | blank | unknown
    text: str = ""                 # raw text, used for cover-card identity
    # the same text with each fragment's box, so a printed label can be paired
    # with the handwriting *beside* it rather than with whatever the detector
    # happened to report next
    fragments: list[dict] | None = None
    rows: list[dict] = field(default_factory=list)
    geometry: dict | None = None   # row bands / column ranges, when measurable
    engine: str = ""
    error: str | None = None


class Engine(Protocol):
    name: str

    def available(self) -> bool: ...
    def transcribe_page(self, image: Path, kind: str = "unknown",
                        source: Path | None = None,
                        page: int | None = None,
                        text: bool = True) -> PageResult: ...


class NullEngine:
    """Stands in until an open-weight model is installed.

    It never fabricates. Every page comes back with an error, which the UI shows
    as "nenhum modelo instalado" rather than as an empty transcription — an
    empty result and a missing engine mean very different things to someone
    checking whether their ancestor is on a page.
    """

    name = "none"

    def available(self) -> bool:
        return False

    def transcribe_page(self, image: Path, kind: str = "unknown",
                        source: Path | None = None,
                        page: int | None = None,
                        text: bool = True) -> PageResult:
        return PageResult(
            kind=kind,
            engine=self.name,
            error="nenhum modelo de transcrição instalado",
        )


_REGISTRY: dict[str, Engine] = {}
_ACTIVE: Engine = NullEngine()


def register(engine: Engine, make_active: bool = True) -> None:
    global _ACTIVE
    _REGISTRY[engine.name] = engine
    if make_active and engine.available():
        _ACTIVE = engine


def active() -> Engine:
    return _ACTIVE


def status() -> dict:
    return {
        "engine": _ACTIVE.name,
        "available": _ACTIVE.available(),
        "registered": sorted(_REGISTRY),
        "detail": ("Motor de transcrição pronto." if _ACTIVE.available() else
                   "Nenhum modelo instalado. A transcrição automática fica "
                   "indisponível; nada é inventado."),
    }
