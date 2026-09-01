"""Audio and image generation for cards."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_cache_dir


def media_dir(kind: str) -> Path:
    """Where generated media lives, cached across runs alongside provider results."""
    path = Path(user_cache_dir("ankigen")) / kind
    path.mkdir(parents=True, exist_ok=True)
    return path
