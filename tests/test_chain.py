"""Provider chaining — the mechanism that keeps a paid fallback cheap."""

import pytest

from anki_card_generator.models import WordEntry
from anki_card_generator.providers.base import ProviderError
from anki_card_generator.providers.chain import ChainProvider


class Answers:
    """A provider that answers, recording every word it was asked about."""

    name = "answers"

    def __init__(self):
        self.asked = []

    def enrich(self, word, source, target, n_examples=0):
        self.asked.append(word)
        return WordEntry(word=word, translations=["ok"])


class Misses:
    """A provider that never has the word."""

    name = "misses"

    def __init__(self):
        self.asked = []

    def enrich(self, word, source, target, n_examples=0):
        self.asked.append(word)
        raise ProviderError(f"{word!r} not found")


def test_the_first_provider_wins_when_it_answers():
    first, second = Answers(), Answers()
    ChainProvider([first, second]).enrich("Haus", "de", "en")
    assert first.asked == ["Haus"]
    # The expensive provider must not be touched when the free one worked.
    assert second.asked == []


def test_the_fallback_is_used_only_on_a_miss():
    free, paid = Misses(), Answers()
    entry = ChainProvider([free, paid]).enrich("sich erinnern", "de", "en")
    assert entry.translations == ["ok"]
    assert paid.asked == ["sich erinnern"]


def test_fallback_words_are_recorded_for_reporting():
    chain = ChainProvider([Misses(), Answers()], ["wiktionary", "llm"])
    chain.enrich("sich erinnern", "de", "en")
    chain.enrich("teilnehmen", "de", "en")
    assert chain.fallback_words == ["sich erinnern", "teilnehmen"]


def test_words_the_first_provider_handles_are_not_recorded():
    chain = ChainProvider([Answers(), Answers()])
    chain.enrich("Haus", "de", "en")
    assert chain.fallback_words == []


def test_a_total_miss_reports_every_provider():
    chain = ChainProvider([Misses(), Misses()], ["wiktionary", "llm"])
    with pytest.raises(ProviderError) as exc:
        chain.enrich("Quatsch", "de", "en")
    assert "wiktionary" in str(exc.value) and "llm" in str(exc.value)


def test_an_empty_chain_is_rejected():
    with pytest.raises(ValueError):
        ChainProvider([])
