"""Shared fixtures.

Nothing here touches the network: every provider test drives its backend through an
injected fake session or client, so the suite is deterministic and runnable offline.
"""

from __future__ import annotations

import pytest

from anki_card_generator.models import Example, WordEntry


@pytest.fixture
def haus() -> WordEntry:
    """A fully-populated German noun."""
    return WordEntry(
        word="Haus",
        pos="noun",
        translations=["house", "building"],
        ipa="haʊ̯s",
        gender="das",
        plural="die Häuser",
        examples=[Example(source="Das Haus ist groß.", target="The house is big.")],
        tags=["german"],
    )


@pytest.fixture
def laufen() -> WordEntry:
    """A German verb, exercising the verb_forms path."""
    return WordEntry(
        word="laufen",
        pos="verb",
        translations=["to run", "to walk"],
        verb_forms={
            "praesens_3sg": "läuft",
            "praeteritum": "lief",
            "perfekt": "ist gelaufen",
        },
    )


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Point the on-disk cache at a temp dir so tests never read or write the real one."""
    cache_path = tmp_path / "cache"
    cache_path.mkdir(exist_ok=True)
    monkeypatch.setattr("anki_card_generator.cache.cache_dir", lambda: cache_path)
    return cache_path
