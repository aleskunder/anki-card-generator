"""DeepL translation.

Translation only -- no grammar, no examples.  Useful as a second opinion on a
translation, not as a way to fill a card on its own.
"""

from __future__ import annotations

import os

import requests

from ..models import WordEntry
from .base import ProviderError

FREE_URL = "https://api-free.deepl.com/v2/translate"
PRO_URL = "https://api.deepl.com/v2/translate"
TIMEOUT = 15


class DeepLProvider:
    name = "deepl"

    def __init__(self, api_key: str | None = None, session: requests.Session | None = None):
        # Read at call time, never baked into the source.
        self.api_key = api_key or os.environ.get("DEEPL_API_KEY", "")
        self.session = session or requests.Session()

    @property
    def url(self) -> str:
        """Free-tier keys carry a `:fx` suffix and must use the free endpoint."""
        return FREE_URL if self.api_key.endswith(":fx") else PRO_URL

    def enrich(self, word: str, source: str, target: str, n_examples: int = 0) -> WordEntry:
        if not self.api_key:
            raise ProviderError("DEEPL_API_KEY is not set.")

        try:
            response = self.session.post(
                self.url,
                data={
                    "text": word,
                    "source_lang": source.upper(),
                    "target_lang": target.upper(),
                },
                headers={"Authorization": f"DeepL-Auth-Key {self.api_key}"},
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"DeepL request failed for {word!r}: {exc}") from exc

        if response.status_code == 403:
            raise ProviderError("DeepL rejected the API key.")
        if response.status_code != 200:
            raise ProviderError(f"DeepL returned {response.status_code} for {word!r}.")

        translations = [t["text"] for t in response.json().get("translations", [])]
        if not translations:
            raise ProviderError(f"DeepL returned no translation for {word!r}.")
        return WordEntry(word=word, translations=translations, tags=["deepl"])
