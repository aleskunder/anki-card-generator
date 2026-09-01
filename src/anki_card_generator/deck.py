"""Anki ``.apkg`` output.

The note type is defined once, here, with a fixed ``MODEL_ID``.  That id is what
Anki uses to recognise "this is the same note type I already have", so changing it
would orphan every card already in the user's collection -- treat it as permanent.

The same reasoning applies, per note, to the GUID: it is derived from the headword
and language pair rather than from the note's contents, so regenerating a deck after
fixing a translation *updates* the existing note and keeps its review history,
instead of importing a duplicate alongside it.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import genanki

from .models import WordEntry

# Permanent identity of the note type. Do not change.
MODEL_ID = 1723498561

FIELD_NAMES = (
    "Word",
    "Reading",
    "Translations",
    "Examples",
    "Gender",
    "Plural",
    "VerbForms",
    "Audio",
    "Image",
    "Tags",
)

CSS = """
.card {
  font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
  font-size: 20px;
  text-align: center;
  color: #1a1a1a;
  background: #fdfdfd;
}
.nightMode.card, .night_mode .card { color: #e8e8e8; background: #2b2b2b; }

.word { font-size: 34px; font-weight: 600; }
.reading { font-size: 17px; color: #777; margin-top: 4px; }
.nightMode .reading, .night_mode .reading { color: #9a9a9a; }

.translations { font-size: 24px; margin: 12px 0; }
.grammar { font-size: 16px; color: #555; margin-top: 8px; }
.nightMode .grammar, .night_mode .grammar { color: #b0b0b0; }

.examples { font-size: 16px; text-align: left; margin: 14px auto 0; max-width: 34em; }
.examples li { margin-bottom: 6px; }
.examples .target { color: #777; }
.nightMode .examples .target, .night_mode .examples .target { color: #9a9a9a; }

img { max-width: 100%; max-height: 260px; border-radius: 6px; margin-top: 10px; }
hr#answer { border: none; border-top: 1px solid #ddd; margin: 16px 0; }
.nightMode hr#answer, .night_mode hr#answer { border-top-color: #555; }
"""

# Recognition: see the foreign word, recall what it means.
#
# The front deliberately shows the bare headword. Putting the article there --
# "das Haus" -- hands over the gender before you have recalled it, which is the
# harder half of learning a German noun; it belongs on the reveal.
_RECOGNITION_FRONT = """
<div class="word">{{Word}}</div>
"""

_RECOGNITION_BACK = """
<div class="word">{{Gender}} {{Word}}</div>
{{#Reading}}<div class="reading">/{{Reading}}/</div>{{/Reading}}
<hr id="answer">
<div class="translations">{{Translations}}</div>
{{#Plural}}<div class="grammar">plural: {{Plural}}</div>{{/Plural}}
{{#VerbForms}}<div class="grammar">{{VerbForms}}</div>{{/VerbForms}}
{{#Image}}<div>{{Image}}</div>{{/Image}}
{{#Examples}}<div class="examples">{{Examples}}</div>{{/Examples}}
{{#Audio}}<div>{{Audio}}</div>{{/Audio}}
"""

# Production: see the meaning, produce the foreign word. Harder, and the direction
# that actually builds active vocabulary -- so the answer includes the article,
# because producing "Haus" without "das" is only half the word.
_PRODUCTION_FRONT = """
<div class="translations">{{Translations}}</div>
"""

_PRODUCTION_BACK = """
{{FrontSide}}
<hr id="answer">
<div class="word">{{Gender}} {{Word}}</div>
{{#Reading}}<div class="reading">/{{Reading}}/</div>{{/Reading}}
{{#Plural}}<div class="grammar">plural: {{Plural}}</div>{{/Plural}}
{{#VerbForms}}<div class="grammar">{{VerbForms}}</div>{{/VerbForms}}
{{#Examples}}<div class="examples">{{Examples}}</div>{{/Examples}}
{{#Audio}}<div>{{Audio}}</div>{{/Audio}}
"""


def build_model() -> genanki.Model:
    """The note type shared by every deck this tool produces."""
    return genanki.Model(
        MODEL_ID,
        "Anki Card Generator — Vocab",
        fields=[{"name": name} for name in FIELD_NAMES],
        templates=[
            {
                "name": "Recognition",
                "qfmt": _RECOGNITION_FRONT,
                "afmt": _RECOGNITION_BACK,
            },
            {
                "name": "Production",
                "qfmt": _PRODUCTION_FRONT,
                "afmt": _PRODUCTION_BACK,
            },
        ],
        css=CSS,
    )


def deck_id_for(deck_name: str) -> int:
    """A stable deck id derived from the name.

    Anki merges imports into an existing deck when the id matches, so the same
    ``--deck`` name must always produce the same number across runs and machines --
    which rules out anything random.
    """
    digest = hashlib.sha256(deck_name.encode("utf-8")).digest()
    # Anki deck ids are positive and comfortably below 2**63.
    return int.from_bytes(digest[:8], "big") % (1 << 62) or 1


def build_note(
    entry: WordEntry, model: genanki.Model, source: str, target: str
) -> genanki.Note:
    """Turn one entry into a note whose GUID is keyed to the word, not its contents."""
    return genanki.Note(
        model=model,
        guid=genanki.guid_for(entry.word, source, target),
        tags=[t.replace(" ", "_") for t in entry.tags],
        fields=[
            # Bare, not article_word(): the gender is revealed by the template on
            # the answer side, never on the prompt.
            entry.word,
            entry.ipa,
            "; ".join(entry.short_translations()),
            _format_examples(entry),
            entry.gender,
            entry.plural,
            ", ".join(f"{k}: {v}" for k, v in entry.verb_forms.items()),
            f"[sound:{Path(entry.audio_path).name}]" if entry.audio_path else "",
            f'<img src="{Path(entry.image_path).name}">' if entry.image_path else "",
            " ".join(entry.tags),
        ],
    )


def _format_examples(entry: WordEntry) -> str:
    if not entry.examples:
        return ""
    items = "".join(
        f"<li>{ex.source}<br><span class='target'>{ex.target}</span></li>"
        for ex in entry.examples
    )
    return f"<ul>{items}</ul>"


def write_apkg(
    entries: list[WordEntry],
    output_file: str | Path,
    deck_name: str,
    source: str,
    target: str,
) -> None:
    """Package *entries* into an importable ``.apkg``, media included."""
    model = build_model()
    deck = genanki.Deck(deck_id_for(deck_name), deck_name)

    media_files: list[str] = []
    for entry in entries:
        deck.add_note(build_note(entry, model, source, target))
        for path in (entry.audio_path, entry.image_path):
            # A media file referenced but missing on disk makes Anki show a broken
            # card, so only ship what is actually there.
            if path and Path(path).is_file():
                media_files.append(path)

    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(str(output_file))
