"""An offline provider that invents nothing and needs nothing.

Useful for exercising the pipeline (templates, media, packaging) without a network
round-trip or an API key, and as the fixture backend in tests.
"""

from __future__ import annotations

from ..models import Example, WordEntry


class StubProvider:
    """Echoes the word back with obviously-synthetic filler."""

    name = "stub"

    def enrich(self, word: str, source: str, target: str, n_examples: int = 0) -> WordEntry:
        return WordEntry(
            word=word,
            pos="unknown",
            translations=[f"{word} [{source}->{target}]"],
            examples=[
                Example(source=f"Example {i + 1} with {word}.", target=f"Example {i + 1}.")
                for i in range(n_examples)
            ],
            tags=["stub"],
        )
