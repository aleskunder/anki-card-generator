"""The LLM provider, driven through a fake Anthropic client.

No network, no key: the point is to pin the request shape and the caching and
error-translation behaviour around it.
"""

import anthropic
import httpx2
import pytest

from anki_card_generator.models import Example, WordEntry
from anki_card_generator.providers.base import ProviderError
from anki_card_generator.providers.llm import LLMProvider


class FakeResponse:
    def __init__(self, parsed_output, stop_reason="end_turn"):
        self.parsed_output = parsed_output
        self.stop_reason = stop_reason


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, response=None, error=None):
        self.messages = FakeMessages(response, error)


def make_entry(**overrides):
    data = {
        "word": "Haus",
        "pos": "noun",
        "translations": ["house"],
        "gender": "das",
        "plural": "die Häuser",
        "examples": [
            Example(source="Das Haus ist groß.", target="The house is big."),
            Example(source="Ein rotes Haus.", target="A red house."),
        ],
    }
    data.update(overrides)
    return WordEntry(**data)


def build(response=None, error=None, **kwargs):
    return LLMProvider(client=FakeClient(response, error), **kwargs)


def _api_error(cls, status_code):
    """Construct a real SDK exception; they need a response carrying a request."""
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(status_code, request=request)
    return cls("boom", response=response, body=None)


def test_passes_the_model_schema_as_the_output_format():
    provider = build(FakeResponse(make_entry()))
    provider.enrich("Haus", "de", "en", n_examples=2)

    call = provider.client.messages.calls[0]
    assert call["output_format"] is WordEntry
    assert call["model"] == "claude-opus-5"
    assert call["output_config"] == {"effort": "medium"}


def test_effort_is_configurable():
    provider = build(FakeResponse(make_entry()), effort="low")
    provider.enrich("Haus", "de", "en")
    assert provider.client.messages.calls[0]["output_config"]["effort"] == "low"


def test_prompt_carries_the_word_and_languages():
    provider = build(FakeResponse(make_entry()))
    provider.enrich("Haus", "de", "en", n_examples=2)

    content = provider.client.messages.calls[0]["messages"][0]["content"]
    assert "Haus" in content and "de" in content and "en" in content


def test_headword_from_the_input_wins_over_the_echo():
    # If the model normalises or mangles the headword, the card must still be filed
    # under what the user actually asked for.
    provider = build(FakeResponse(make_entry(word="haus")))
    assert provider.enrich("Haus", "de", "en").word == "Haus"


def test_examples_are_trimmed_to_the_request():
    provider = build(FakeResponse(make_entry()))
    assert len(provider.enrich("Haus", "de", "en", n_examples=1).examples) == 1


def test_examples_are_dropped_when_none_were_asked_for():
    provider = build(FakeResponse(make_entry()))
    assert provider.enrich("Haus", "de", "en", n_examples=0).examples == []


def test_second_lookup_is_served_from_cache():
    provider = build(FakeResponse(make_entry()))
    provider.enrich("Haus", "de", "en", n_examples=1)
    provider.enrich("Haus", "de", "en", n_examples=1)
    assert len(provider.client.messages.calls) == 1


def test_cache_can_be_bypassed():
    provider = build(FakeResponse(make_entry()), use_cache=False)
    provider.enrich("Haus", "de", "en")
    provider.enrich("Haus", "de", "en")
    assert len(provider.client.messages.calls) == 2


def test_cache_key_separates_language_pairs():
    provider = build(FakeResponse(make_entry()))
    provider.enrich("Haus", "de", "en")
    provider.enrich("Haus", "de", "fr")
    assert len(provider.client.messages.calls) == 2


def test_missing_credentials_give_an_actionable_message():
    with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
        build(error=_api_error(anthropic.AuthenticationError, 401)).enrich("Haus", "de", "en")


def test_rate_limiting_is_reported_per_word():
    with pytest.raises(ProviderError, match="Rate limited"):
        build(error=_api_error(anthropic.RateLimitError, 429)).enrich("Haus", "de", "en")


def test_server_errors_name_the_status():
    with pytest.raises(ProviderError, match="API error 500"):
        build(error=_api_error(anthropic.InternalServerError, 500)).enrich("Haus", "de", "en")


def test_a_refusal_is_reported_rather_than_returned():
    provider = build(FakeResponse(make_entry(), stop_reason="refusal"))
    with pytest.raises(ProviderError, match="declined"):
        provider.enrich("Haus", "de", "en")


def test_absent_structured_output_is_an_error():
    provider = build(FakeResponse(None))
    with pytest.raises(ProviderError, match="No structured output"):
        provider.enrich("Haus", "de", "en")
