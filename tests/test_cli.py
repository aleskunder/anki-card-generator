"""End-to-end CLI behaviour, using the offline stub provider throughout."""

import pytest

from anki_card_generator.cli import main


@pytest.fixture
def words(tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("Haus\nlaufen\n", encoding="utf-8")
    return path


def run(words, tmp_path, *extra):
    out = tmp_path / "out"
    argv = [
        "--input", str(words),
        "--source", "de",
        "--target", "en",
        "--provider", "stub",
        "--no-audio",
        "--no-images",
        "--output", str(out),
        *extra,
    ]
    return main(argv), out


def test_tsv_run_writes_one_row_per_word(words, tmp_path):
    code, out = run(words, tmp_path, "--format", "tsv")
    assert code == 0
    assert len(out.read_text(encoding="utf-8").splitlines()) == 2


def test_apkg_run_produces_a_package(words, tmp_path):
    code, out = run(words, tmp_path, "--format", "apkg")
    assert code == 0
    assert out.is_file() and out.stat().st_size > 0


def test_examples_flag_reaches_the_cards(words, tmp_path):
    _, out = run(words, tmp_path, "--format", "tsv", "--examples", "2")
    text = out.read_text(encoding="utf-8")
    assert "Example 1" in text and "Example 2" in text


def test_examples_default_to_none(words, tmp_path):
    _, out = run(words, tmp_path, "--format", "tsv")
    assert "Example 1" not in out.read_text(encoding="utf-8")


def test_extra_tags_are_applied(words, tmp_path):
    _, out = run(words, tmp_path, "--format", "tsv", "--tag", "a1", "--tag", "chapter3")
    text = out.read_text(encoding="utf-8")
    assert "a1" in text and "chapter3" in text


def test_empty_word_list_fails_cleanly(tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text("# nothing here\n", encoding="utf-8")
    assert main([
        "--input", str(empty), "--source", "de", "--target", "en",
        "--provider", "stub", "--no-audio", "--no-images",
    ]) == 1


def test_unknown_provider_is_rejected_by_the_parser(words, tmp_path):
    with pytest.raises(SystemExit):
        run(words, tmp_path, "--provider", "reverso")


def test_output_name_defaults_from_the_deck_name(words, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main([
        "--input", str(words), "--source", "de", "--target", "en",
        "--provider", "stub", "--no-audio", "--no-images", "--format", "tsv",
    ]) == 0
    assert (tmp_path / "Vocabulary_DE-EN.tsv").is_file()


def test_fallback_is_skipped_when_the_main_provider_answers(words, tmp_path, capsys):
    # stub always answers, so a fallback must never be reached -- with a paid
    # fallback, reaching it would mean spending money for nothing.
    code, _ = run(words, tmp_path, "--format", "tsv", "--fallback", "wiktionary")
    assert code == 0
    assert "Fell back" not in capsys.readouterr().err


def test_fallback_equal_to_the_provider_is_ignored(words, tmp_path):
    code, out = run(words, tmp_path, "--format", "tsv", "--fallback", "stub")
    assert code == 0
    assert len(out.read_text(encoding="utf-8").splitlines()) == 2
