"""Language Detection Module for WeatherGPT.

Accurately distinguishes between English, Tamil (Tamil script),
Hindi (Devanagari script), Tanglish (Tamil transliteration),
and Hinglish (Hindi transliteration).
"""

import re
from ai.models import LanguageEnum

# Tanglish lexicon markers
TANGLISH_MARKERS = {
    "naalaiku", "nalaiku", "naalaikku", "inniku", "iniku", "netru", "kaalai", "kaalaile",
    "mazhai", "malai", "mazha", "varuma", "varum", "iruka", "irukku", "pogalama",
    "poga", "kadalukku", "kadal", "meen", "meenavar", "veli", "veliya", "veliye",
    "veetula", "oorla", "engae", "eppo", "eppadi", "epdi", "nalla", "veiyil", "veyil",
    "kaathu", "katru", "irukkuma", "panlama"
}

# Suffix markers common in Tamil Romanization: e.g. "Coimbatore-la", "morning-la", "Chennai-la"
LOCATIVE_SUFFIX_PATTERN = re.compile(r"\b\w+(?:-la|la|le)\b", re.IGNORECASE)

# Hinglish lexicon markers
HINGLISH_MARKERS = {
    "kaisa", "kaise", "kaisi", "hogi", "hoga", "hoge", "barish", "baarish", "barsaat",
    "mausam", "mosam", "subah", "shaam", "sham", "raat", "dophar", "aaj", "kal",
    "parso", "kya", "mein", "hawa", "toofan", "thand", "thandi", "garmi", "dhup",
    "kheti", "kisan", "jaana", "chahiye", "sakte", "batao", "rahega", "hogi kya"
}

# Postpositions common in Hindi Romanization: e.g. "Delhi mein", "Chennai ka", "baarish ki"
HINDI_POSTPOSITIONS = re.compile(r"\b(?:mein|me|ka|ki|ke|ko|se)\b", re.IGNORECASE)


def detect_language(text: str) -> LanguageEnum:
    """Detects whether text is English, Tamil script, Hindi script, Tanglish, or Hinglish."""
    if not text or not text.strip():
        return LanguageEnum.EN

    # 1. Check for Tamil Unicode range (0x0B80 - 0x0BFF)
    tamil_chars = len(re.findall(r"[\u0B80-\u0BFF]", text))
    if tamil_chars > 0:
        return LanguageEnum.TA

    # 2. Check for Hindi/Devanagari Unicode range (0x0900 - 0x097F)
    hindi_chars = len(re.findall(r"[\u0900-\u097F]", text))
    if hindi_chars > 0:
        return LanguageEnum.HI

    # 3. Analyze Latin script words
    clean_text = text.lower()
    words = set(re.findall(r"\b[a-z]+\b", clean_text))

    tanglish_score = len(words.intersection(TANGLISH_MARKERS))
    if LOCATIVE_SUFFIX_PATTERN.search(clean_text):
        tanglish_score += 2

    hinglish_score = len(words.intersection(HINGLISH_MARKERS))
    if HINDI_POSTPOSITIONS.search(clean_text):
        hinglish_score += 1

    # Determine predominant transliteration
    if tanglish_score > 0 and tanglish_score >= hinglish_score:
        return LanguageEnum.TANGLISH
    elif hinglish_score > 0 and hinglish_score > tanglish_score:
        return LanguageEnum.HINGLISH

    return LanguageEnum.EN
