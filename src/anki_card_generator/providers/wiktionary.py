"""Wiktionary via Wiktextract.

The previous implementation asked the MediaWiki API for ``action=query`` and then ran
BeautifulSoup over the reply looking for a ``Translations`` section.  That could never
work -- ``action=query`` returns page metadata, not rendered HTML -- and scraping the
rendered page instead would only trade one silent breakage for another whenever the
markup shifts.

This goes at Wiktextract's machine-readable extraction of the same content, served by
kaikki.org as one JSON object per line: gender, plural, principal parts, IPA and
glosses arrive as real fields rather than something recovered from a page layout.
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote

import requests

from ..models import Example, WordEntry
from .base import ProviderError

BASE_URL = "https://kaikki.org/dictionary"
TIMEOUT = 20

LANG_NAMES = {
    "de": "German",
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "ru": "Russian",
    "nl": "Dutch",
    "pl": "Polish",
    "pt": "Portuguese",
}

# Wiktextract marks noun gender with a bare m/f/n on the headword line.
_GENDER_ARTICLES = {"m": "der", "f": "die", "n": "das"}

# A page carries one record per part of speech; prefer the ones a learner is
# actually studying over proper nouns and single inflected forms.
_POS_PRIORITY = ("verb", "noun", "adj", "adv", "prep", "conj", "pron", "num")

# German principal parts, as WordEntry.verb_forms keys, keyed by the Wiktextract
# form tags that identify them.
_VERB_FORMS = {
    "praesens_3sg": {"indicative", "present", "singular", "third-person"},
    "praeteritum": {"indicative", "preterite", "singular", "third-person"},
    "partizip_2": {"participle", "past"},
}


# Senses that point at another word instead of defining this one. On a flashcard
# "present participle of anstrengen" or "Short for certain compounds, such as
# Schraubenschlüssel" is true but unusable as an answer.
_POINTER_TAGS = frozenset({"form-of", "alt-of", "abbreviation"})


def _is_form_of(sense: dict) -> bool:
    """Whether a sense merely points at another word rather than defining one."""
    return bool(_POINTER_TAGS & set(sense.get("tags") or [])) or bool(sense.get("form_of"))


def _has_real_sense(record: dict) -> bool:
    return any(
        not _is_form_of(sense) and sense.get("glosses")
        for sense in record.get("senses", [])
    )


class WiktionaryProvider:
    """Structured dictionary data: authoritative grammar, patchier coverage."""

    name = "wiktionary"

    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.session.headers.setdefault(
            "User-Agent",
            "anki-card-generator (+https://github.com/aleskunder/anki-card-generator)",
        )

    @staticmethod
    def build_url(word: str, lang_name: str) -> str:
        """Kaikki shards entries by the first one and two characters of the word."""
        first, second = word[:1], word[:2]
        return (
            f"{BASE_URL}/{quote(lang_name)}/meaning/"
            f"{quote(first)}/{quote(second)}/{quote(word)}.jsonl"
        )

    def enrich(self, word: str, source: str, target: str, n_examples: int = 0) -> WordEntry:
        lang_name = LANG_NAMES.get(source)
        if lang_name is None:
            raise ProviderError(f"Wiktionary provider has no language mapping for {source!r}.")

        try:
            response = self.session.get(self.build_url(word, lang_name), timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise ProviderError(f"Wiktionary lookup failed for {word!r}: {exc}") from exc

        if response.status_code == 404:
            raise ProviderError(f"{word!r} not found in {lang_name} Wiktionary.")
        if response.status_code != 200:
            raise ProviderError(f"Wiktionary returned {response.status_code} for {word!r}.")

        # The endpoint sends no charset, so requests falls back to Latin-1 and
        # quietly mangles every umlaut. The payload is always UTF-8.
        response.encoding = "utf-8"
        record = self._pick_record(response.text, word)
        return self._parse(record, word, n_examples)

    @staticmethod
    def _pick_record(body: str, word: str) -> dict:
        """Choose the most useful of the page's per-part-of-speech records."""
        records = []
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a single malformed line should not lose the whole entry

        if not records:
            raise ProviderError(f"No usable Wiktionary data for {word!r}.")

        def rank(record: dict) -> tuple[int, int]:
            pos = record.get("pos", "")
            pos_rank = (
                _POS_PRIORITY.index(pos) if pos in _POS_PRIORITY else len(_POS_PRIORITY)
            )
            # A record whose every sense is "present participle of X" defines
            # nothing. 'anstrengend' has one of those under `verb` and the real
            # adjective senses under `adj`, so definitions must outrank part of
            # speech here.
            return (0 if _has_real_sense(record) else 1, pos_rank)

        return min(records, key=rank)

    def _parse(self, record: dict, word: str, n_examples: int) -> WordEntry:
        """Map a Wiktextract record onto a :class:`WordEntry`."""
        entry = WordEntry(word=word, pos=record.get("pos", ""), tags=["wiktionary"])

        for sound in record.get("sounds", []):
            if sound.get("ipa"):
                entry.ipa = sound["ipa"].strip("/[]")
                break

        expansion = ""
        templates = record.get("head_templates") or []
        if templates:
            expansion = str(templates[0].get("expansion", ""))

        if entry.pos == "noun":
            entry.gender = self._gender(expansion, word)
            plural = self._form(record, {"plural"}, exclude={"definite", "indefinite"})
            if plural:
                article = "die " if entry.gender else ""
                entry.plural = f"{article}{plural}"
        elif entry.pos == "verb":
            entry.verb_forms = self._verb_forms(record, expansion)

        senses = [s for s in record.get("senses", []) if not _is_form_of(s)]
        for sense in senses or record.get("senses", []):
            for gloss in sense.get("glosses", []):
                if gloss not in entry.translations:
                    entry.translations.append(gloss)
            if n_examples:
                for example in sense.get("examples", []):
                    text = example.get("text")
                    if text and len(entry.examples) < n_examples:
                        entry.examples.append(
                            Example(
                                source=text,
                                target=example.get("english")
                                or example.get("translation", ""),
                            )
                        )

        if not entry.translations:
            raise ProviderError(f"No senses found for {word!r}.")
        return entry

    @staticmethod
    def _gender(expansion: str, word: str) -> str:
        """Read the gender marker that follows the headword, e.g. 'Haus n (...)'."""
        match = re.search(rf"{re.escape(word)}\s+([mfn])\b", expansion)
        return _GENDER_ARTICLES.get(match.group(1), "") if match else ""

    @staticmethod
    def _form(record: dict, required: set[str], exclude: set[str] | None = None) -> str:
        """First inflected form carrying all *required* tags and none excluded."""
        exclude = exclude or set()
        for form in record.get("forms", []):
            tags = set(form.get("tags", []))
            if required <= tags and not (tags & exclude) and form.get("form"):
                return form["form"]
        return ""

    @classmethod
    def _verb_forms(cls, record: dict, expansion: str) -> dict[str, str]:
        """Principal parts, with the perfekt assembled from participle + auxiliary."""
        forms = {
            name: cls._form(record, tags) for name, tags in _VERB_FORMS.items()
        }
        participle = forms.pop("partizip_2", "")
        if participle:
            # 'auxiliary sein' on the headword line decides ist/hat.
            auxiliary = "ist" if "auxiliary sein" in expansion else "hat"
            forms["perfekt"] = f"{auxiliary} {participle}"
        return {k: v for k, v in forms.items() if v}
