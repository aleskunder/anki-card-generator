import argparse
from src.card_generator import generate_anki_tsv
from src.translation_api import get_translations
from src.pronunciation import fetch_pronunciation
from src.utils import load_words

def main():
    parser = argparse.ArgumentParser(description="Anki Card Generator")
    parser.add_argument('--input', type=str, required=True, help="Path to input word list (.txt)")
    parser.add_argument('--source', type=str, required=True, help="Source language (e.g., 'en')")
    parser.add_argument('--target', type=str, required=True, help="Target language (e.g., 'de')")
    parser.add_argument('--translations', type=int, default=1, help="Max number of translations per word")
    parser.add_argument('--examples', type=int, default=0, help="Number of example sentences per word")
    parser.add_argument('--pronunciation', action='store_true', help="Add pronunciation")
    parser.add_argument('--output', type=str, default="anki_cards.tsv", help="Output file name")
    args = parser.parse_args()

    # Load word list
    words = load_words(args.input)

    # Generate cards
    cards = []
    for word in words:
        translations = get_translations(word, args.source, args.target, args.translations)

        # Add examples, metadata, pronunciation if needed
        if args.pronunciation:
            pronunciation = fetch_pronunciation(word, args.source)

        cards.append([word, translations, pronunciation]  if args.pronunciation else  [word, translations,]) # Simplified for now
    # Generate Anki file
    generate_anki_tsv(cards, args.output)
