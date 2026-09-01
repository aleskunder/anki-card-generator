"""The card data model.

``WordEntry`` is the single currency of this project: every provider returns one,
every writer consumes one, and the LLM provider hands the very same schema to the
API as its structured-output format.  Fields a given backend cannot fill are left
empty rather than faked, so a card is always a truthful view of what was found.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

_LEADING_ARTICLE = re.compile(r"^(?:an?|the)\s+", re.IGNORECASE)


def _shorten(gloss: str) -> str:
    """Reduce one dictionary gloss to its head term.

    Drops parenthetical qualifications, keeps only the first of several comma- or
    semicolon-separated synonyms, and strips a leading English article -- "a key"
    is one word of answer and one word of noise.
    """
    without_parens = re.sub(r"\([^)]*\)", " ", gloss)
    head = re.split(r"[;,]", without_parens)[0]
    return _LEADING_ARTICLE.sub("", " ".join(head.split()))


class Example(BaseModel):
    """One example sentence and its translation."""

    source: str = Field(description="Example sentence in the source language.")
    target: str = Field(description="Translation of that sentence into the target language.")


class WordEntry(BaseModel):
    """Everything known about a single vocabulary item."""

    word: str = Field(description="The headword, in its dictionary form.")
    pos: str = Field(
        default="",
        description="Part of speech: noun, verb, adjective, adverb, preposition, etc.",
    )
    translations: list[str] = Field(
        default_factory=list,
        description="Translations into the target language, most common first.",
    )
    ipa: str = Field(default="", description="IPA transcription, without slashes.")

    # --- grammar metadata (German-focused, empty for languages that lack it) ---
    gender: str = Field(
        default="",
        description="For nouns, the definite article: der, die, or das. Empty otherwise.",
    )
    plural: str = Field(
        default="",
        description="For nouns, the plural form with its article, e.g. 'die Häuser'.",
    )
    verb_forms: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "For verbs, principal parts keyed by name, e.g. "
            "{'praesens_3sg': 'läuft', 'praeteritum': 'lief', 'perfekt': 'ist gelaufen'}. "
            "Empty for non-verbs."
        ),
    )

    examples: list[Example] = Field(
        default_factory=list, description="Natural example sentences using the word."
    )

    # --- media, filled in after enrichment by the media layer ---
    audio_path: str = Field(default="", description="Local path to a pronunciation audio file.")
    image_path: str = Field(default="", description="Local path to an illustrative image.")

    tags: list[str] = Field(default_factory=list, description="Anki tags for this note.")

    def article_word(self) -> str:
        """The headword as a learner should memorise it: 'das Haus' rather than 'Haus'."""
        return f"{self.gender} {self.word}".strip() if self.gender else self.word

    def primary_sense(self) -> str:
        """A short term naming the main sense, for searching and summarising.

        Dictionary glosses run long -- 'week (period of seven days counting from
        Monday to Sunday...)' -- which is useless as an image-search query, so
        keep only the leading term.
        """
        return _shorten(self.translations[0]) or self.word if self.translations else self.word

    def short_translations(self, limit: int = 2) -> list[str]:
        """Card-sized translations: at most *limit* senses, each cut to its head term.

        A flashcard answer has to be recallable in one glance. The full gloss --
        'week (period of seven days counting from Monday to Sunday, or from Sunday
        to Saturday)' -- is reference material, not something you can check yourself
        against, so only the leading term of each distinct sense survives.
        """
        short: list[str] = []
        for gloss in self.translations:
            term = _shorten(gloss)
            if term and term not in short:
                short.append(term)
            if len(short) >= limit:
                break
        return short
