"""Try providers in order until one answers.

The point is cost.  Wiktionary is free and handles most words well, but it misses
some outright (reflexive phrases are filed under the bare verb) and defines others
only as inflections.  Putting a paid provider behind it means paying for the
handful of words that need it rather than the whole list.
"""

from __future__ import annotations

from ..models import WordEntry
from .base import Provider, ProviderError


class ChainProvider:
    """Ask each provider in turn; the first usable answer wins."""

    name = "chain"

    def __init__(self, providers: list[Provider], names: list[str] | None = None) -> None:
        if not providers:
            raise ValueError("ChainProvider needs at least one provider")
        self.providers = providers
        self.names = names or [getattr(p, "name", type(p).__name__) for p in providers]
        # Populated per run so the CLI can report what the fallback actually cost.
        self.fallback_words: list[str] = []

    def enrich(self, word: str, source: str, target: str, n_examples: int = 0) -> WordEntry:
        failures = []
        for index, provider in enumerate(self.providers):
            try:
                entry = provider.enrich(word, source, target, n_examples)
            except ProviderError as exc:
                failures.append(f"{self.names[index]}: {exc}")
                continue
            if index:
                self.fallback_words.append(word)
            return entry
        raise ProviderError(f"No provider could describe {word!r} — " + "; ".join(failures))
