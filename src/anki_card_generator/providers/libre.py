"""LibreTranslate.

Self-hostable and open source.  The public instance now requires a key, so the
endpoint is configurable via ``LIBRETRANSLATE_URL`` for anyone running their own.
"""

from __future__ import annotations

import os

import requests

from ..models import WordEntry
from .base import ProviderError

DEFAULT_URL = "https://libretranslate.com/translate"
TIMEOUT = 15


class LibreTranslateProvider:
    name = "libre"

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.url = url or os.environ.get("LIBRETRANSLATE_URL", DEFAULT_URL)
        self.api_key = api_key or os.environ.get("LIBRETRANSLATE_API_KEY", "")
        self.session = session or requests.Session()

    def enrich(self, word: str, source: str, target: str, n_examples: int = 0) -> WordEntry:
        payload = {"q": word, "source": source, "target": target, "format": "text"}
        if self.api_key:
            payload["api_key"] = self.api_key

        try:
            response = self.session.post(self.url, json=payload, timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise ProviderError(f"LibreTranslate request failed for {word!r}: {exc}") from exc

        if response.status_code != 200:
            raise ProviderError(
                f"LibreTranslate returned {response.status_code} for {word!r}. "
                "The public instance requires an API key; set LIBRETRANSLATE_URL "
                "to your own instance or LIBRETRANSLATE_API_KEY."
            )

        text = response.json().get("translatedText", "")
        if not text:
            raise ProviderError(f"LibreTranslate returned no translation for {word!r}.")
        return WordEntry(word=word, translations=[text], tags=["libre"])
