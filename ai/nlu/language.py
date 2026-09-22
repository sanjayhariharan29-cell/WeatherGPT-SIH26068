"""Language Detection Module for WeatherGPT.

Accurately distinguishes between English, Tamil (Tamil script),
Telugu (Telugu script), Hindi (Devanagari script), Marathi (Devanagari script with Marathi markers),
Tanglish (Tamil transliteration), and Hinglish (Hindi transliteration).
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

# Suffix markers common in Tamil Romanization: e.g. "Coimbatore-la", "morning-la", "Chennai-la", or standalone "la" / "le"
LOCATIVE_SUFFIX_PATTERN = re.compile(r"\b\w+-(?:la|le)\b|\b(?:la|le)\b", re.IGNORECASE)

# Hinglish lexicon markers
HINGLISH_MARKERS = {
    "kaisa", "kaise", "kaisi", "hogi", "hoga", "hoge", "barish", "baarish", "barsaat",
    "mausam", "mosam", "subah", "shaam", "sham", "raat", "dophar", "aaj", "kal",
    "parso", "kya", "mein", "hawa", "toofan", "thand", "thandi", "garmi", "dhup",
    "kheti", "kisan", "jaana", "chahiye", "sakte", "batao", "rahega", "hogi kya"
}

# Postpositions common in Hindi Romanization: e.g. "Delhi mein", "Chennai ka", "baarish ki"
HINDI_POSTPOSITIONS = re.compile(r"\b(?:mein|me|ka|ki|ke|ko|se)\b", re.IGNORECASE)

# Marathi-distinct vocabulary / marker words in Devanagari (excluding common words shared with Hindi like 'आज')
MARATHI_DEVANAGARI_MARKERS = {
    "आहे", "आहेत", "नाही", "नाहीत", "पाऊस", "पावसाचा", "पावसाची", "हवामान", "हवामानाचा",
    "कसा", "कशी", "कसे", "कुठे", "करावे", "सांगा", "होईल", "होणार", "पिकांची",
    "उद्या", "शेतकरी", "सांग", "करायचे", "पडेल", "येईल"
}


def detect_language(text: str) -> LanguageEnum:
    """Detects whether text is English, Tamil, Telugu, Marathi, Hindi, Tanglish, or Hinglish."""
    if not text or not text.strip():
        return LanguageEnum.EN

    # 1. Check for Telugu Unicode range (0x0C00 - 0x0C7F)
    telugu_chars = len(re.findall(r"[\u0C00-\u0C7F]", text))
    if telugu_chars > 0:
        return LanguageEnum.TE

    # 2. Check for Tamil Unicode range (0x0B80 - 0x0BFF)
    tamil_chars = len(re.findall(r"[\u0B80-\u0BFF]", text))
    if tamil_chars > 0:
        return LanguageEnum.TA

    # 3. Check for Devanagari Unicode range (0x0900 - 0x097F)
    devanagari_chars = len(re.findall(r"[\u0900-\u097F]", text))
    if devanagari_chars > 0:
        # Check for Marathi specific character: ळ (\u0933)
        if "\u0933" in text:
            return LanguageEnum.MR

        # Check for Marathi words
        words = set(re.findall(r"[\u0900-\u097F]+", text))
        if words.intersection(MARATHI_DEVANAGARI_MARKERS):
            return LanguageEnum.MR

        return LanguageEnum.HI

    # 4. Analyze Latin script words for Tanglish or Hinglish
    clean_text = text.lower()
    latin_words = set(re.findall(r"\b[a-z]+\b", clean_text))

    tanglish_score = len(latin_words.intersection(TANGLISH_MARKERS))
    if LOCATIVE_SUFFIX_PATTERN.search(clean_text):
        tanglish_score += 2

    hinglish_score = len(latin_words.intersection(HINGLISH_MARKERS))
    postposition_matches = [p.lower() for p in HINDI_POSTPOSITIONS.findall(clean_text)]
    if postposition_matches:
        if postposition_matches == ["me"] and hinglish_score == 0:
            pass
        else:
            hinglish_score += len(postposition_matches)

    if tanglish_score > 0 and tanglish_score >= hinglish_score:
        return LanguageEnum.TANGLISH
    elif hinglish_score > 0 and hinglish_score > tanglish_score:
        return LanguageEnum.HINGLISH

    return LanguageEnum.EN
