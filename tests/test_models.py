"""WordEntry helpers."""

from anki_card_generator.models import WordEntry


def test_article_word_prefixes_the_gender(haus):
    assert haus.article_word() == "das Haus"


def test_article_word_leaves_genderless_words_alone(laufen):
    assert laufen.article_word() == "laufen"


def test_primary_sense_drops_parentheticals():
    entry = WordEntry(
        word="Woche",
        translations=["week (period of seven days counting from Monday to Sunday)"],
    )
    assert entry.primary_sense() == "week"


def test_primary_sense_takes_only_the_first_sense():
    entry = WordEntry(word="Haus", translations=["house, building", "home"])
    assert entry.primary_sense() == "house"


def test_primary_sense_splits_on_semicolons_too():
    entry = WordEntry(word="laufen", translations=["to walk; to jog; to run"])
    assert entry.primary_sense() == "to walk"


def test_primary_sense_keeps_multiword_terms():
    entry = WordEntry(word="Ratschlag", translations=["piece of advice; (in plural) advice"])
    assert entry.primary_sense() == "piece of advice"


def test_primary_sense_falls_back_to_the_word():
    assert WordEntry(word="Haus").primary_sense() == "Haus"


def test_primary_sense_falls_back_when_a_gloss_is_all_parenthetical():
    entry = WordEntry(word="Haus", translations=["(obsolete)"])
    assert entry.primary_sense() == "Haus"
