"""On-disk cache for provider results.

Enrichment is the only expensive step in the pipeline -- everything downstream
(templates, media layout, packaging) gets iterated on far more often than the word
list changes.  Caching by word rather than by run means tweaking a card template and
regenerating a 500-word deck costs nothing and hits no API.

The key includes ``SCHEMA_VERSION``, so widening :class:`WordEntry` invalidates old
entries automatically instead of silently serving cards that are missing the new
fields.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from platformdirs import user_cache_dir

from .models import WordEntry

# Bump when WordEntry gains a field that existing cached payloads would lack.
SCHEMA_VERSION = 1


def cache_dir() -> Path:
    path = Path(user_cache_dir("ankigen")) / "entries"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_key(provider: str, word: str, source: str, target: str, n_examples: int) -> str:
    raw = f"{SCHEMA_VERSION}|{provider}|{word}|{source}|{target}|{n_examples}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def load(key: str) -> WordEntry | None:
    """Return the cached entry, or ``None`` if absent or unreadable.

    A corrupt cache file is treated as a miss: re-fetching is cheap next to making
    the user hunt down a stray file in their cache directory.
    """
    path = cache_dir() / f"{key}.json"
    if not path.is_file():
        return None
    try:
        return WordEntry.model_validate_json(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError, OSError):
        return None


def store(key: str, entry: WordEntry) -> None:
    """Persist an entry, ignoring write failures.

    Media paths are deliberately not cached -- they are regenerated per run and
    point into a different directory each time.
    """
    payload = entry.model_dump()
    payload["audio_path"] = ""
    payload["image_path"] = ""
    try:
        (cache_dir() / f"{key}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    except OSError:
        pass
