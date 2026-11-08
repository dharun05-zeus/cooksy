"""Low-level text clean-up shared by the parser, the allergen check and search."""

from __future__ import annotations

import re
import unicodedata

UNICODE_FRACTIONS = {
    "½": " 1/2", "¼": " 1/4", "¾": " 3/4", "⅓": " 1/3", "⅔": " 2/3", "⅛": " 1/8",
    "⅜": " 3/8", "⅝": " 5/8", "⅞": " 7/8", "⅕": " 1/5", "⅙": " 1/6",
}
_SYMBOLS = str.maketrans({"®": "", "™": "", "©": "", "–": "-", "—": "-", "’": "'", "‘": "'"})
_SPACES = re.compile(r"\s+")


def clean_line(text: str) -> str:
    """Remove scraping artefacts but keep the line readable.

    Allrecipes lines end with the word "ADVERTISEMENT"; it is removed here.
    """
    text = text.replace("ADVERTISEMENT", "")
    for char, replacement in UNICODE_FRACTIONS.items():
        text = text.replace(char, replacement)
    text = text.translate(_SYMBOLS)
    return _SPACES.sub(" ", text).strip()


def fold(text: str) -> str:
    """Lower-case and strip accents, so "Crème Fraîche" and "creme fraiche" compare equal."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _SPACES.sub(" ", stripped.lower()).strip()
