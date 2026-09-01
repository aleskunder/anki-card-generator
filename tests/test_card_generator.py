from anki_card_generator.card_generator import generate_anki_tsv


def test_writes_a_row_per_entry(tmp_path, haus, laufen):
    out = tmp_path / "cards.tsv"
    generate_anki_tsv([haus, laufen], out)
    assert len(out.read_text(encoding="utf-8").splitlines()) == 2


def test_noun_row_carries_article_and_grammar(tmp_path, haus):
    out = tmp_path / "cards.tsv"
    generate_anki_tsv([haus], out)
    row = out.read_text(encoding="utf-8").rstrip("\n").split("\t")
    assert row[0] == "das Haus"
    assert row[1] == "house; building"
    assert row[4] == "die Häuser"


def test_accepts_plain_sequences(tmp_path):
    out = tmp_path / "cards.tsv"
    generate_anki_tsv([["test", "translation"]], out)
    assert out.read_text(encoding="utf-8").rstrip("\n") == "test\ttranslation"
