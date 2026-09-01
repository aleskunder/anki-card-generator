"""Small shared helpers."""

from __future__ import annotations

from pathlib import Path


def load_words(file_path: str | Path) -> list[str]:
    """Read a word list, one headword per line.

    Blank lines and ``#`` comments are skipped so a list can be annotated and
    sectioned without breaking the run.  Order is preserved and duplicates are
    dropped, since two identical headwords would collapse into one note anyway.
    """
    seen: set[str] = set()
    words: list[str] = []
    with open(file_path, encoding="utf-8") as file:
        for line in file:
            word = line.strip()
            if not word or word.startswith("#"):
                continue
            if word not in seen:
                seen.add(word)
                words.append(word)
    return words
