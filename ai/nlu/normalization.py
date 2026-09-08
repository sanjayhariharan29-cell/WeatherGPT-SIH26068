"""Query Normalization Module for WeatherGPT NLU.

Performs deterministic text normalization, whitespace cleaning,
and phonetic transliteration canonicalization while preserving original query text.
"""

import re
from typing import Tuple

# Common transliteration canonical mappings (spelling variant -> canonical variant)
PHONETIC_VARIANTS = {
    # Tamil / Tanglish
    r"\bnaalaikku\b": "naalaiku",
    r"\bnalaiku\b": "naalaiku",
    r"\bnalaikku\b": "naalaiku",
    r"\binnaiku\b": "inniku",
    r"\biniku\b": "inniku",
    r"\bmazha\b": "mazhai",
    r"\bkaalaila\b": "kaalai",
    r"\bmaalaila\b": "maalai",
    r"\bepdi\b": "eppadi",
    r"\bkovai\b": "coimbatore",
    # Hindi / Hinglish
    r"\bbaarish\b": "barish",
    r"\bbarsaath\b": "barish",
    r"\bbarsaat\b": "barish",
    r"\bmosam\b": "mausam",
    r"\bmausm\b": "mausam",
    r"\bkaal\b": "kal",
    r"\bsubeh\b": "subah",
    r"\bshaam\b": "sham",
    r"\bthand\b": "thandi",
}


def normalize_query(text: str) -> str:
    """Normalizes whitespace, punctuation, and known transliteration variations."""
    if not text:
        return ""

    # Convert to lowercase and trim
    cleaned = text.lower().strip()

    # Normalize multiple whitespace into single space
    cleaned = re.sub(r"\s+", " ", cleaned)

    # Clean leading/trailing punctuation except question marks
    cleaned = re.sub(r"^[^\w\s]+|[^\w\s\?]+$", "", cleaned)

    # Apply canonical phonetic replacements
    for pattern, replacement in PHONETIC_VARIANTS.items():
        cleaned = re.sub(pattern, replacement, cleaned)

    return cleaned
