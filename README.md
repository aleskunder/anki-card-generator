# Anki Card Generator

Turn a plain word list into a ready-to-import Anki deck — with translations, grammar
metadata, example sentences, pronunciation audio, and images.

```
Haus                                das Haus                    das Haus
laufen        ─── ankigen ──▶       die Häuser        ──▶       /haʊ̯s/
schön                               house; building             house; building
                                    Das Haus ist groß.          🔊  🖼
```

## Install

```bash
micromamba create -n anki_repo -c conda-forge python=3.12 -y
micromamba run -n anki_repo pip install -e ".[dev]"
```

For pronunciation audio:

```bash
sudo apt install espeak-ng
```

espeak-ng needs no voice model and is used automatically once installed. For
better voices, install [piper](https://github.com/rhasspy/piper) *and* point
`--voice` (or `ANKIGEN_PIPER_VOICE`) at a `.onnx` model — piper is only preferred
when a model is actually configured, so it can never shadow a working espeak-ng.
Without either, the run warns once and continues without audio.

## Use

```bash
ankigen --input data/words.txt --source de --target en --examples 2
```

That writes `Vocabulary_DE-EN.apkg`, which you import into Anki with
*File → Import*. Every word becomes one note and two cards: **Recognition**
(German → English) and **Production** (English → German).

### Options

| Flag | Default | What it does |
|---|---|---|
| `--input` | required | Word list, one headword per line; `#` comments and blank lines are ignored |
| `--source` / `--target` | required | Language codes, e.g. `de` and `en` |
| `--provider` | `llm` | Where word data comes from — see below |
| `--fallback` | — | Provider to try for words the main one misses |
| `--format` | `apkg` | `apkg` for a real deck, `tsv` for a table to import by hand |
| `--examples N` | `0` | Example sentences per word |
| `--deck` | `Vocabulary (DE-EN)` | Anki deck name |
| `--output` | derived from deck name | Output file |
| `--model` | `claude-opus-5` | LLM model id, for `--provider llm` |
| `--effort` | `medium` | LLM reasoning effort — the main cost/quality dial |
| `--tag` | — | Extra Anki tag, repeatable (`--tag a1 --tag chapter3`) |
| `--voice` | — | piper voice model (`.onnx`); falls back to espeak-ng when unset |
| `--no-audio` / `--no-images` | off | Skip media |
| `--no-cache` | off | Ignore cached provider results |

### Providers

| Name | Needs | Fills |
|---|---|---|
| `llm` *(default)* | `ANTHROPIC_API_KEY` or `ant auth login` | Everything: translations, gender, plural, verb forms, IPA, examples |
| `wiktionary` | nothing | Translations, gender, plural, IPA — free, but coverage varies |
| `deepl` | `DEEPL_API_KEY` | Translations only |
| `libre` | `LIBRETRANSLATE_URL` / `LIBRETRANSLATE_API_KEY` | Translations only |
| `stub` | nothing | Nothing real — offline filler for testing the pipeline |

Only the LLM provider can fill a card on its own. The others leave what they do not
know empty rather than guessing, so a card is always a truthful view of what was found.

### Running it for free

`--provider wiktionary` costs nothing and needs no account. Combined with espeak-ng
for audio and Openverse for images, the whole pipeline is free:

```bash
ankigen --input data/words.txt --source de --target en \
        --provider wiktionary --examples 1
```

Wiktionary does miss words, though — reflexive phrases like *sich erinnern* are
filed under the bare verb. `--fallback` pays for only those:

```bash
ankigen --input words.txt --source de --target en \
        --provider wiktionary --fallback llm
```

The run reports which words fell through, so you can see exactly what was billed.

## Regenerating a deck

Re-running on an updated list is safe, and this is the main reason to prefer `.apkg`
over a TSV export. A note's identity is derived from its headword and language pair,
not its contents, so fixing a translation and re-importing **updates** the existing
card and keeps its review history instead of adding a duplicate beside it.

Enrichment results are cached on disk, so a second run over the same words costs
nothing and hits no API — iterate on card templates freely.

## Development

```bash
micromamba run -n anki_repo python -m pytest
micromamba run -n anki_repo python -m ruff check .
```

The test suite never touches the network: providers are driven through injected fake
sessions and clients.

## License

MIT — see [LICENSE](LICENSE).
