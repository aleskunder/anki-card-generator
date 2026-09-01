"""TSV output, for importing into Anki by hand.

Kept alongside the ``.apkg`` writer in :mod:`anki_card_generator.deck` because a
plain table is still the quickest way to eyeball a run or to feed some other tool.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .models import WordEntry

TSV_COLUMNS = (
    "Word",
    "Translations",
    "IPA",
    "Gender",
    "Plural",
    "VerbForms",
    "Examples",
    "Tags",
)


def generate_anki_tsv(cards, output_file: str | Path) -> None:
    """Write rows to a tab-separated file.

    Accepts either :class:`WordEntry` objects or plain sequences, so existing
    callers that pass raw rows keep working.
    """
    with open(output_file, "w", newline="", encoding="utf-8") as tsvfile:
        writer = csv.writer(tsvfile, delimiter="\t")
        for card in cards:
            writer.writerow(_as_row(card) if isinstance(card, WordEntry) else card)


def _as_row(entry: WordEntry) -> list[str]:
    """Flatten an entry into one TSV row, collapsing the list-valued fields."""
    return [
        entry.article_word(),
        "; ".join(entry.translations),
        entry.ipa,
        entry.gender,
        entry.plural,
        ", ".join(f"{k}: {v}" for k, v in entry.verb_forms.items()),
        " | ".join(f"{ex.source} — {ex.target}" for ex in entry.examples),
        " ".join(entry.tags),
    ]
