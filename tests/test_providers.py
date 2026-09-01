"""Provider registry and the network-backed backends, driven through fakes."""

import json

import pytest
import requests

from anki_card_generator.providers import (
    DEFAULT_PROVIDER,
    PROVIDER_NAMES,
    ProviderError,
    get_provider,
)
from anki_card_generator.providers.deepl import DeepLProvider
from anki_card_generator.providers.stub import StubProvider
from anki_card_generator.providers.wiktionary import WiktionaryProvider


class FakeResponse:
    """Stands in for requests.Response, for both JSON and JSONL endpoints."""

    def __init__(self, status_code=200, payload=None, records=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.encoding = None
        self.text = (
            "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
            if records is not None
            else ""
        )

    def json(self):
        return self._payload


class FakeSession:
    """Records the request and replays a canned response."""

    def __init__(self, response):
        self.response = response
        self.calls = []
        self.headers = {}

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.response

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.response


# --- registry ---------------------------------------------------------------

def test_default_provider_is_the_llm():
    assert DEFAULT_PROVIDER == "llm"


def test_stub_is_registered():
    assert isinstance(get_provider("stub"), StubProvider)


def test_unknown_provider_names_the_alternatives():
    with pytest.raises(ValueError, match="wiktionary"):
        get_provider("reverso")


def test_every_registered_name_resolves_without_network():
    # Construction must not perform I/O; only enrich() is allowed to.
    for name in PROVIDER_NAMES:
        assert get_provider(name) is not None


# --- stub -------------------------------------------------------------------

def test_stub_honours_the_example_count():
    entry = StubProvider().enrich("Haus", "de", "en", n_examples=2)
    assert entry.word == "Haus"
    assert len(entry.examples) == 2


# --- wiktionary ---------------------------------------------------------------
# Shapes below mirror real kaikki.org records: gender lives in the head-template
# expansion, not in a dedicated field, and each page is JSONL with one record per
# part of speech.

HAUS_NOUN = {
    "word": "Haus",
    "pos": "noun",
    "sounds": [{"ipa": "[ha\u028a\u032fs]"}, {"audio": "De-Haus.ogg"}],
    "head_templates": [
        {"expansion": "Haus n (strong, genitive Hauses, plural H\u00e4user)"}
    ],
    "forms": [
        {"form": "H\u00e4user", "tags": ["plural"]},
        {"form": "H\u00e4usern", "tags": ["dative", "plural"], "source": "declension"},
    ],
    "senses": [
        {
            "glosses": ["house, building"],
            "examples": [
                {
                    "text": "Das Haus ist gro\u00df.",
                    "english": "The house is big.",
                }
            ],
        },
        {"glosses": ["home"]},
    ],
}

HAUS_PROPER_NOUN = {
    "word": "Haus",
    "pos": "name",
    "head_templates": [{"expansion": "Haus n (proper noun)"}],
    "senses": [{"glosses": ["a municipality in Styria"]}],
}

LAUFEN_VERB = {
    "word": "laufen",
    "pos": "verb",
    "sounds": [{"ipa": "[\u02c8la\u028a\u032ff\u0259n]"}],
    "head_templates": [
        {
            "expansion": (
                "laufen (class 7 strong, third-person singular present l\u00e4uft, "
                "past tense lief, past participle gelaufen, auxiliary sein)"
            )
        }
    ],
    "forms": [
        {"form": "l\u00e4uft", "tags": ["indicative", "present", "singular", "third-person"]},
        {"form": "lief", "tags": ["indicative", "preterite", "singular", "third-person"]},
        {"form": "gelaufen", "tags": ["participle", "past"]},
    ],
    "senses": [{"glosses": ["to run; to walk"]}],
}


def test_wiktionary_maps_structured_fields():
    session = FakeSession(FakeResponse(200, records=[HAUS_NOUN]))
    entry = WiktionaryProvider(session=session).enrich("Haus", "de", "en", n_examples=1)
    assert entry.pos == "noun"
    assert entry.translations == ["house, building", "home"]
    assert entry.ipa == "ha\u028a\u032fs"
    assert len(entry.examples) == 1


def test_wiktionary_reads_gender_from_the_head_template():
    session = FakeSession(FakeResponse(200, records=[HAUS_NOUN]))
    entry = WiktionaryProvider(session=session).enrich("Haus", "de", "en")
    assert entry.gender == "das"
    assert entry.plural == "die H\u00e4user"


def test_wiktionary_skips_declension_forms_when_picking_the_plural():
    # The bare {"tags": ["plural"]} entry is the citation form; the dative-plural
    # declension row must not win.
    session = FakeSession(FakeResponse(200, records=[HAUS_NOUN]))
    entry = WiktionaryProvider(session=session).enrich("Haus", "de", "en")
    assert "H\u00e4usern" not in entry.plural


def test_wiktionary_prefers_the_common_part_of_speech():
    # A page carrying both a noun and a proper noun should yield the noun.
    session = FakeSession(FakeResponse(200, records=[HAUS_PROPER_NOUN, HAUS_NOUN]))
    entry = WiktionaryProvider(session=session).enrich("Haus", "de", "en")
    assert entry.pos == "noun"


def test_wiktionary_assembles_verb_principal_parts():
    session = FakeSession(FakeResponse(200, records=[LAUFEN_VERB]))
    entry = WiktionaryProvider(session=session).enrich("laufen", "de", "en")
    assert entry.verb_forms == {
        "praesens_3sg": "l\u00e4uft",
        "praeteritum": "lief",
        "perfekt": "ist gelaufen",  # 'auxiliary sein' -> ist, not hat
    }


def test_wiktionary_uses_haben_when_the_auxiliary_is_not_sein():
    record = json.loads(json.dumps(LAUFEN_VERB))
    record["head_templates"][0]["expansion"] = "machen (weak, auxiliary haben)"
    session = FakeSession(FakeResponse(200, records=[record]))
    entry = WiktionaryProvider(session=session).enrich("machen", "de", "en")
    assert entry.verb_forms["perfekt"] == "hat gelaufen"


def test_wiktionary_forces_utf8_decoding():
    # The endpoint sends no charset; without an explicit override every umlaut
    # comes back mangled.
    response = FakeResponse(200, records=[HAUS_NOUN])
    WiktionaryProvider(session=FakeSession(response)).enrich("Haus", "de", "en")
    assert response.encoding == "utf-8"


def test_wiktionary_url_is_sharded_and_encoded():
    url = WiktionaryProvider.build_url("sch\u00f6n", "German")
    assert url.endswith("/German/meaning/s/sc/sch%C3%B6n.jsonl")


def test_wiktionary_requests_the_language_name_not_the_code():
    session = FakeSession(FakeResponse(200, records=[HAUS_NOUN]))
    WiktionaryProvider(session=session).enrich("Haus", "de", "en")
    assert "German" in session.calls[0][1]


def test_wiktionary_tolerates_a_malformed_line():
    response = FakeResponse(200, records=[HAUS_NOUN])
    response.text = "{ not json\n" + response.text
    entry = WiktionaryProvider(session=FakeSession(response)).enrich("Haus", "de", "en")
    assert entry.translations


def test_wiktionary_rejects_unmapped_languages():
    with pytest.raises(ProviderError, match="language mapping"):
        WiktionaryProvider(session=FakeSession(FakeResponse())).enrich("x", "zz", "en")


def test_wiktionary_reports_a_miss_as_provider_error():
    session = FakeSession(FakeResponse(404))
    with pytest.raises(ProviderError, match="not found"):
        WiktionaryProvider(session=session).enrich("Quatschwort", "de", "en")


def test_wiktionary_reports_an_empty_page():
    with pytest.raises(ProviderError, match="No usable"):
        WiktionaryProvider(session=FakeSession(FakeResponse(200, records=[]))).enrich(
            "Haus", "de", "en"
        )


def test_wiktionary_wraps_network_failures():
    class Broken(FakeSession):
        def get(self, url, **kwargs):
            raise requests.ConnectionError("down")

    with pytest.raises(ProviderError, match="lookup failed"):
        Broken(FakeResponse())
        WiktionaryProvider(session=Broken(FakeResponse())).enrich("Haus", "de", "en")


ANSTRENGEND_VERB_FORM = {
    "word": "anstrengend",
    "pos": "verb",
    "senses": [
        {
            "glosses": ["present participle of anstrengen"],
            "tags": ["form-of", "participle", "present"],
            "form_of": [{"word": "anstrengen"}],
        }
    ],
}

ANSTRENGEND_ADJ = {
    "word": "anstrengend",
    "pos": "adj",
    "senses": [
        {"glosses": ["strenuous (requiring great exertion)"]},
        {"glosses": ["exhausting"]},
    ],
}


def test_wiktionary_prefers_a_record_that_actually_defines_the_word():
    # 'verb' outranks 'adj' by part of speech, but the verb record only says
    # "present participle of anstrengen", which is useless on a card.
    session = FakeSession(
        FakeResponse(200, records=[ANSTRENGEND_VERB_FORM, ANSTRENGEND_ADJ])
    )
    entry = WiktionaryProvider(session=session).enrich("anstrengend", "de", "en")
    assert entry.pos == "adj"
    assert entry.translations[0].startswith("strenuous")


def test_wiktionary_skips_form_of_senses_within_a_record():
    record = {
        "word": "x",
        "pos": "noun",
        "senses": [
            {"glosses": ["plural of y"], "tags": ["form-of"]},
            {"glosses": ["a real definition"]},
        ],
    }
    session = FakeSession(FakeResponse(200, records=[record]))
    entry = WiktionaryProvider(session=session).enrich("x", "de", "en")
    assert entry.translations == ["a real definition"]


def test_wiktionary_keeps_form_of_glosses_when_there_is_nothing_else():
    # Better a pointer to the base form than no card at all.
    session = FakeSession(FakeResponse(200, records=[ANSTRENGEND_VERB_FORM]))
    entry = WiktionaryProvider(session=session).enrich("anstrengend", "de", "en")
    assert entry.translations == ["present participle of anstrengen"]


# --- deepl ------------------------------------------------------------------

def test_deepl_requires_a_key():
    with pytest.raises(ProviderError, match="DEEPL_API_KEY"):
        DeepLProvider(api_key="").enrich("Haus", "de", "en")


def test_deepl_free_key_uses_the_free_endpoint():
    assert "api-free" in DeepLProvider(api_key="abc:fx").url
    assert "api-free" not in DeepLProvider(api_key="abc").url


def test_deepl_sends_the_key_as_a_header_not_a_body_field():
    session = FakeSession(FakeResponse(200, {"translations": [{"text": "house"}]}))
    provider = DeepLProvider(api_key="secret:fx", session=session)
    entry = provider.enrich("Haus", "de", "en")

    assert entry.translations == ["house"]
    _, _, kwargs = session.calls[0]
    assert kwargs["headers"]["Authorization"] == "DeepL-Auth-Key secret:fx"
    assert "auth_key" not in kwargs["data"]


def test_deepl_reports_a_bad_key():
    session = FakeSession(FakeResponse(403))
    with pytest.raises(ProviderError, match="rejected the API key"):
        DeepLProvider(api_key="bad:fx", session=session).enrich("Haus", "de", "en")
