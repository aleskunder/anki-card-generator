"""Command-line entrypoint."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from . import __version__
from .card_generator import generate_anki_tsv
from .models import WordEntry
from .providers import DEFAULT_PROVIDER, PROVIDER_NAMES, ProviderError, get_provider
from .utils import load_words


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ankigen",
        description="Generate Anki cards from a word list.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--input", required=True, help="Path to input word list (.txt)")
    parser.add_argument("--source", required=True, help="Source language, e.g. 'de'")
    parser.add_argument("--target", required=True, help="Target language, e.g. 'en'")
    parser.add_argument(
        "--provider",
        default=DEFAULT_PROVIDER,
        choices=PROVIDER_NAMES,
        help=f"Where word data comes from (default: {DEFAULT_PROVIDER})",
    )
    parser.add_argument(
        "--format",
        default="apkg",
        choices=("apkg", "tsv"),
        dest="fmt",
        help="Output format (default: apkg)",
    )
    parser.add_argument("--output", help="Output file (default: <deck name>.<format>)")
    parser.add_argument("--deck", help="Anki deck name (default: derived from the languages)")
    parser.add_argument(
        "--examples",
        type=int,
        default=0,
        metavar="N",
        help="Example sentences per word (default: 0)",
    )
    parser.add_argument(
        "--fallback",
        choices=PROVIDER_NAMES,
        help=(
            "Provider to try for words the main provider cannot describe. "
            "'--provider wiktionary --fallback llm' pays only for the misses."
        ),
    )
    parser.add_argument("--model", help="LLM model id, for --provider llm")
    parser.add_argument(
        "--effort",
        choices=("low", "medium", "high"),
        default="medium",
        help="LLM reasoning effort, the main cost/quality dial (default: medium)",
    )
    parser.add_argument("--no-audio", action="store_true", help="Skip pronunciation audio")
    parser.add_argument(
        "--voice",
        help="piper voice model (.onnx); falls back to espeak-ng when unset",
    )
    parser.add_argument("--no-images", action="store_true", help="Skip images")
    parser.add_argument(
        "--no-cache", action="store_true", help="Ignore cached provider results"
    )
    parser.add_argument("--tag", action="append", default=[], help="Extra Anki tag (repeatable)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    words = load_words(args.input)
    if not words:
        print(f"No words found in {args.input}", file=sys.stderr)
        return 1

    deck_name = args.deck or f"Vocabulary ({args.source.upper()}-{args.target.upper()})"
    output = Path(args.output) if args.output else Path(f"{_slug(deck_name)}.{args.fmt}")

    provider_kwargs = {}
    if args.model:
        provider_kwargs["model"] = args.model
    if args.provider == "llm":
        provider_kwargs["effort"] = args.effort
        provider_kwargs["use_cache"] = not args.no_cache

    provider = get_provider(args.provider, **provider_kwargs)
    chain = None
    if args.fallback and args.fallback != args.provider:
        from .providers.chain import ChainProvider

        fallback_kwargs = dict(provider_kwargs)
        if args.fallback == "llm":
            fallback_kwargs.setdefault("effort", args.effort)
            fallback_kwargs.setdefault("use_cache", not args.no_cache)
        chain = ChainProvider(
            [provider, get_provider(args.fallback, **fallback_kwargs)],
            [args.provider, args.fallback],
        )
        provider = chain

    entries: list[WordEntry] = []
    failed: list[str] = []
    for index, word in enumerate(words, start=1):
        print(f"[{index}/{len(words)}] {word}", file=sys.stderr)
        try:
            entry = provider.enrich(word, args.source, args.target, args.examples)
        except ProviderError as exc:
            # One failed lookup should cost one card, not the whole run.
            print(f"  ! {exc}", file=sys.stderr)
            failed.append(word)
            continue
        entry.tags.extend(args.tag)
        entries.append(entry)

    if not entries:
        print("No cards were generated.", file=sys.stderr)
        return 1

    if not args.no_audio:
        _add_audio(entries, args.source, args.voice)
    if not args.no_images:
        _add_images(entries)

    if args.fmt == "tsv":
        generate_anki_tsv(entries, output)
    else:
        from .deck import write_apkg

        write_apkg(entries, output, deck_name, args.source, args.target)

    print(f"\nWrote {len(entries)} cards to {output}", file=sys.stderr)
    if chain is not None and chain.fallback_words:
        # Worth surfacing: with a paid fallback this is the line that cost money.
        print(
            f"Fell back to {args.fallback} for {len(chain.fallback_words)}: "
            f"{', '.join(chain.fallback_words)}",
            file=sys.stderr,
        )
    if failed:
        print(f"Skipped {len(failed)}: {', '.join(failed)}", file=sys.stderr)
    return 0


def _add_audio(entries: list[WordEntry], lang: str, voice: str | None = None) -> None:
    """Synthesise pronunciation, degrading to no audio if no engine is installed."""
    from .media.tts import TTSUnavailable, synthesize

    for entry in entries:
        try:
            entry.audio_path = synthesize(entry.word, lang, voice)
        except TTSUnavailable as exc:
            print(f"Audio disabled: {exc}", file=sys.stderr)
            return
        except Exception as exc:  # a single word failing is not fatal
            print(f"  ! audio for {entry.word}: {exc}", file=sys.stderr)


def _add_images(entries: list[WordEntry]) -> None:
    """Attach an image to concrete nouns; abstract words are only cluttered by one."""
    from .media.images import fetch_image

    for entry in entries:
        if entry.pos and entry.pos.lower() != "noun":
            continue
        try:
            entry.image_path = fetch_image(entry.word, entry.primary_sense())
        except Exception as exc:
            print(f"  ! image for {entry.word}: {exc}", file=sys.stderr)


def _slug(name: str) -> str:
    """Turn a deck name into a filename: 'Vocabulary (DE-EN)' -> 'Vocabulary_DE-EN'."""
    cleaned = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    return re.sub(r"_+", "_", cleaned).strip("_")


if __name__ == "__main__":
    raise SystemExit(main())
