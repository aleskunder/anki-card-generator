from anki_card_generator.utils import load_words


def test_load_words_reads_one_word_per_line(tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("Haus\nlaufen\nschön\n", encoding="utf-8")
    assert load_words(path) == ["Haus", "laufen", "schön"]


def test_load_words_skips_blanks_and_comments(tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("# nouns\nHaus\n\n  \nlaufen\n# verbs\n", encoding="utf-8")
    assert load_words(path) == ["Haus", "laufen"]


def test_load_words_drops_duplicates_but_keeps_order(tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("Haus\nlaufen\nHaus\n", encoding="utf-8")
    assert load_words(path) == ["Haus", "laufen"]
