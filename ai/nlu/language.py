"""Language Detection Module for WeatherGPT.

Accurately distinguishes between English, Tamil (Tamil script),
Hindi (Devanagari script), and Tanglish (Tamil-English transliteration).
"""

import re
from ai.models import LanguageEnum

# Common Tanglish lexicon markers
TANGLISH_MARKERS = {
    "naalaiku", "nalaiku", "inniku", "iniku", "netru", "kaalai", "kaalaile",
    "mazhai", "malai", "varuma", "varum", "iruka", "irukku", "pogalama",
    "poga", "kadhal", "kadhaluku", "kadalluku", "kadallukku", "kadallukku",
    "kadalu", "kadalukku", "kadal", "meen", "meenavar", "college",
    "office", "veli", "veliya", "veliye", "veetula", "oorla", "engae",
    "engada", "eppo", "eppadi", "nalla", "veiyil", "veyil", "kaathu", "katru"
}

# Suffix markers common in Tamil Romanization: e.g. "Coimbatore-la", "morning-la"
LOCATIVE_SUFFIX_PATTERN = re.compile(r"\b\w+(?:-la|la|le)\b", re.IGNORECASE)


def detect_language(text: str) -> LanguageEnum:
    """Detects whether text is English, Tamil script, Hindi script, or Tanglish."""
    if not text or not text.strip():
        return LanguageEnum.EN

    # Check for Tamil Unicode range (0x0B80 - 0x0BFF)
    tamil_chars = len(re.findall(r"[\u0B80-\u0BFF]", text))
    if tamil_chars > 0:
        return LanguageEnum.TA

    # Check for Hindi/Devanagari Unicode range (0x0900 - 0x097F)
    hindi_chars = len(re.findall(r"[\u0900-\u097F]", text))
    if hindi_chars > 0:
        return LanguageEnum.HI

    # Check for Tanglish markers in Latin text
    clean_text = text.lower()
    words = set(re.findall(r"\b[a-z]+\b", clean_text))

    tanglish_hits = words.intersection(TANGLISH_MARKERS)
    has_locative_suffix = bool(LOCATIVE_SUFFIX_PATTERN.search(clean_text))

    if tanglish_hits or has_locative_suffix:
        return LanguageEnum.TANGLISH

    return LanguageEnum.EN
