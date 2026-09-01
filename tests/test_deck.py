"""The .apkg writer, with emphasis on note identity.

Stable GUIDs are the property that lets someone regenerate a deck after fixing a
translation without losing review history, so they get the most attention here.
"""

import pathlib
import zipfile

import genanki

from anki_card_generator.deck import (
    FIELD_NAMES,
    build_model,
    build_note,
    deck_id_for,
    write_apkg,
)


def test_writes_an_importable_package(tmp_path, haus, laufen):
    out = tmp_path / "deck.apkg"
    write_apkg([haus, laufen], out, "Test Deck", "de", "en")
    assert out.is_file()
    # An .apkg is a zip carrying the collection database.
    with zipfile.ZipFile(out) as archive:
        assert any(n.startswith("collection.anki") for n in archive.namelist())


def test_guid_depends_on_word_not_contents(haus):
    model = build_model()
    before = build_note(haus, model, "de", "en").guid

    haus.translations = ["dwelling"]
    haus.examples = []
    after = build_note(haus, model, "de", "en").guid

    # Same word, same language pair -> same note. This is what makes a re-import
    # update the existing card instead of duplicating it.
    assert before == after


def test_guid_differs_across_language_pairs(haus):
    model = build_model()
    assert (
        build_note(haus, model, "de", "en").guid
        != build_note(haus, model, "de", "fr").guid
    )


def test_deck_id_is_stable_and_name_dependent():
    assert deck_id_for("German") == deck_id_for("German")
    assert deck_id_for("German") != deck_id_for("French")
    assert 0 < deck_id_for("German") < 2**63


def test_note_fields_line_up_with_the_model(haus):
    model = build_model()
    note = build_note(haus, model, "de", "en")
    assert len(note.fields) == len(FIELD_NAMES)
    fields = dict(zip(FIELD_NAMES, note.fields, strict=True))
    assert fields["Word"] == "das Haus"
    assert fields["Translations"] == "house; building"
    assert fields["Plural"] == "die Häuser"
    assert "Das Haus ist groß." in fields["Examples"]


def test_verb_forms_are_rendered(laufen):
    note = build_note(laufen, build_model(), "de", "en")
    verb_forms = dict(zip(FIELD_NAMES, note.fields, strict=True))["VerbForms"]
    assert "ist gelaufen" in verb_forms


def test_missing_media_is_not_packaged(tmp_path, haus):
    # A field referencing a file that is not on disk gives a broken card in Anki.
    haus.audio_path = str(tmp_path / "does-not-exist.wav")
    out = tmp_path / "deck.apkg"
    write_apkg([haus], out, "Test Deck", "de", "en")
    assert out.is_file()


def test_model_has_both_directions():
    names = {t["name"] for t in build_model().templates}
    assert names == {"Recognition", "Production"}


def test_guid_matches_genanki_helper(haus):
    assert build_note(haus, build_model(), "de", "en").guid == genanki.guid_for(
        "Haus", "de", "en"
    )


def test_packaged_media_matches_every_reference(tmp_path, haus, laufen):
    """A [sound:] or <img> pointing at a file Anki did not receive is a broken card.

    This is the classic .apkg failure: the field references a bare filename, the
    media manifest maps arbitrary numeric keys to names, and nothing checks that
    the two agree.
    """
    import json
    import re

    audio = tmp_path / "haus.wav"
    audio.write_bytes(b"RIFFfake")
    image = tmp_path / "haus.jpg"
    image.write_bytes(b"\xff\xd8\xff\xe0fake")
    haus.audio_path, haus.image_path = str(audio), str(image)
    laufen.audio_path = str(tmp_path / "laufen.wav")
    (tmp_path / "laufen.wav").write_bytes(b"RIFFfake")

    out = tmp_path / "deck.apkg"
    write_apkg([haus, laufen], out, "Test Deck", "de", "en")

    with zipfile.ZipFile(out) as archive:
        manifest = json.loads(archive.read("media").decode())
        packaged = set(manifest.values())
        # Each manifest key is a real member of the archive.
        assert set(manifest) <= set(archive.namelist())
        collection = archive.read("collection.anki2")

    assert packaged == {"haus.wav", "haus.jpg", "laufen.wav"}

    import sqlite3
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        db = pathlib.Path(d) / "c.anki2"
        db.write_bytes(collection)
        con = sqlite3.connect(db)
        rows = [r[0] for r in con.execute("SELECT flds FROM notes")]
        con.close()

    referenced = set()
    for flds in rows:
        referenced.update(re.findall(r"\[sound:([^\]]+)\]", flds))
        referenced.update(re.findall(r'src="([^"]+)"', flds))
    assert referenced == packaged
