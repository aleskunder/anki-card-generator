# anki-card-generator

## Environment

This project uses the micromamba env **`anki_repo`** (Python 3.12). See the global
micromamba rules in `~/.claude/CLAUDE.md`.

```bash
export MAMBA_EXE=/home/sasha/micromamba_folder/micromamba
export MAMBA_ROOT_PREFIX=/home/sasha/micromamba
ANKI_PY=/home/sasha/micromamba/envs/anki_repo/bin/python

$ANKI_PY -m pytest          # run tests
$ANKI_PY -m anki_card_generator --help   # run the CLI
$ANKI_PY -m ruff check .                 # lint
```

Install the package in editable mode after dependency changes:
`/home/sasha/micromamba/envs/anki_repo/bin/pip install -e ".[dev]"`

There is no `venv` here — the old `anki_repo_env/` was removed.

## Layout

`src/anki_card_generator/` (src-layout, console script `ankigen`)
- `cli.py` — argparse entrypoint
- `models.py` — `WordEntry`, the pydantic schema shared by every provider and
  reused directly as the LLM structured-output schema
- `providers/` — pluggable data sources behind `Provider.enrich()`; `llm` (Claude,
  default), plus `wiktionary`, `deepl`, `libre`, `stub`
- `deck.py` — genanki note type + `.apkg` writer; `card_generator.py` — TSV writer
- `media/` — `tts.py` (local piper/espeak-ng), `images.py` (Openverse)

## Conventions

- Never hardcode API keys. `anthropic.Anthropic()` resolves `ANTHROPIC_API_KEY` or an
  `ant auth login` profile; DeepL/other keys come from the environment.
- Provider network calls are cached on disk — tests must use fixtures, never the network.
- Note GUIDs come from `genanki.guid_for(word, source, target)` so regenerating a deck
  updates existing notes instead of duplicating them. Do not change that key casually.
