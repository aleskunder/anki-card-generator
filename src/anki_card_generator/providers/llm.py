"""The default provider: one structured Claude call per word.

This is the only backend that can fill a card on its own -- translations, gender and
plural, verb principal parts, IPA and example sentences all come back from a single
request.  :class:`WordEntry` is handed to the API as the output schema, so the
response arrives already validated and there is no JSON parsing to get wrong.
"""

from __future__ import annotations

import anthropic

from .. import cache
from ..models import WordEntry
from .base import ProviderError

DEFAULT_MODEL = "claude-opus-5"

SYSTEM_PROMPT = """\
You are a lexicographer building vocabulary flashcards for a language learner.

For the given headword, fill every field you can from the schema, and leave a field
empty rather than guessing at it.

Rules:
- `translations`: the genuinely common senses, most frequent first. Two or three is
  usually right; do not pad the list with rare or technical senses.
- `gender`: for German nouns, exactly `der`, `die`, or `das`. Empty for other parts
  of speech and for languages without grammatical gender.
- `plural`: the plural with its article, e.g. `die Häuser`.
- `verb_forms`: for German verbs, use the keys `praesens_3sg`, `praeteritum`, and
  `perfekt`; the perfekt includes its auxiliary, e.g. `ist gelaufen`. Mark a
  separable prefix with `|`, e.g. `an|kommen`. Empty for non-verbs.
- `ipa`: broad transcription, no surrounding slashes.
- `examples`: short, natural sentences a learner would actually meet, each using the
  headword, with a faithful translation into the target language.
- `word`: echo the headword in its dictionary form, without an article.
"""


class LLMProvider:
    """Enrich words through the Claude API."""

    name = "llm"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        effort: str = "medium",
        use_cache: bool = True,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self.model = model
        self.effort = effort
        self.use_cache = use_cache
        # Zero-arg construction resolves ANTHROPIC_API_KEY or an `ant auth login`
        # profile; the key never belongs in this file.
        self._client = client
        self._explicit_client = client is not None

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic()
        return self._client

    def enrich(self, word: str, source: str, target: str, n_examples: int = 0) -> WordEntry:
        key = cache.cache_key(self.name, word, source, target, n_examples)
        if self.use_cache:
            cached = cache.load(key)
            if cached is not None:
                return cached

        prompt = (
            f"Headword: {word}\n"
            f"Source language: {source}\n"
            f"Target language: {target}\n"
            f"Example sentences wanted: {n_examples}"
        )

        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                output_config={"effort": self.effort},
                output_format=WordEntry,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.AuthenticationError as exc:
            raise ProviderError(
                "No usable Anthropic credentials. Set ANTHROPIC_API_KEY or run "
                "`ant auth login`."
            ) from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError(f"Rate limited while looking up {word!r}.") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"API error {exc.status_code} for {word!r}.") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError(f"Network error looking up {word!r}.") from exc

        if response.stop_reason == "refusal":
            raise ProviderError(f"Request for {word!r} was declined.")

        entry = response.parsed_output
        if entry is None:
            raise ProviderError(f"No structured output returned for {word!r}.")

        # The model echoes the headword; trust the input over the echo so a card
        # never ends up filed under a form the user did not ask for.
        entry.word = word
        entry.examples = entry.examples[:n_examples] if n_examples else []

        if self.use_cache:
            cache.store(key, entry)
        return entry
