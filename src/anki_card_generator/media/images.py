"""Illustrative images from Openverse.

Openverse indexes openly-licensed images across Wikimedia, Flickr and others, needs
no API key for anonymous search, and returns licence metadata -- which matters,
because a deck built from arbitrary web images is not something you can share.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import requests

from . import media_dir

SEARCH_URL = "https://api.openverse.org/v1/images/"
TIMEOUT = 20
MAX_BYTES = 2_000_000

_session = requests.Session()
_session.headers.setdefault(
    "User-Agent", "anki-card-generator (+https://github.com/aleskunder/anki-card-generator)"
)


def fetch_image(word: str, translations: list[str] | None = None) -> str:
    """Download one image for *word*, returning its path or ``""`` if none fits.

    The English translation is used as the search term when available: Openverse's
    index is overwhelmingly English-tagged, so searching for "house" finds far more
    than searching for "Haus".
    """
    query = (translations or [word])[0] if translations else word
    key = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]

    for existing in media_dir("images").glob(f"{key}.*"):
        return str(existing)

    response = _session.get(
        SEARCH_URL,
        params={
            "q": query,
            "page_size": 1,
            "license_type": "all-cc",
            "extension": "jpg",
        },
        timeout=TIMEOUT,
    )
    if response.status_code != 200:
        return ""

    results = response.json().get("results", [])
    if not results:
        return ""

    url = results[0].get("url")
    if not url:
        return ""

    image = _session.get(url, timeout=TIMEOUT, stream=True)
    if image.status_code != 200:
        return ""

    # Guard against a surprisingly large file bloating the .apkg.
    data = image.raw.read(MAX_BYTES + 1, decode_content=True)
    if not data or len(data) > MAX_BYTES:
        return ""

    out = Path(media_dir("images")) / f"{key}.jpg"
    out.write_bytes(data)
    return str(out)
