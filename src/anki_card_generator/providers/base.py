"""The provider seam.

A provider turns a bare word into a :class:`WordEntry`.  That is the whole contract.
Backends differ enormously in what they can supply -- an LLM fills every field, a
translation API fills exactly one -- so anything a backend does not know is simply
left at its default rather than invented.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import WordEntry


@runtime_checkable
class Provider(Protocol):
    """Anything that can describe a word."""

    def enrich(self, word: str, source: str, target: str, n_examples: int = 0) -> WordEntry:
        """Return what this backend knows about *word*.

        Args:
            word: The headword to look up.
            source: Source language code, e.g. ``"de"``.
            target: Target language code, e.g. ``"en"``.
            n_examples: How many example sentences to include, if supported.

        Raises:
            ProviderError: If the lookup fails in a way the caller should hear about.
        """
        ...


class ProviderError(RuntimeError):
    """A provider could not answer for a word.

    The CLI catches this per word, so one bad lookup degrades a single card
    instead of killing the run.
    """
