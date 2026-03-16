"""Canonical language-pair normalization.

Single source of truth for pair key strings used across WMT benchmarks,
EvalSnapshots, and QualityMetrics analytics.  Every place that builds or
stores a language-pair key should go through these functions so that
EvalSnapshot.languagePair and the analytics grouping keys always match.

Canonical form: two lowercase 2-letter codes joined by a hyphen, e.g.
    "jp-en"  "en-fr"  "fr-en"  "en-sw"  "sw-en"

Accepted inputs (all map to the same canonical output):
    ISO-639-3 3-letter:  "jpn-eng", "eng-fra", "swh-eng"
    ISO-639-1 2-letter:  "ja-en"   (sacrebleu/HF convention)
    DB enum values:      "JP-EN"   (Prisma SourceLanguage enum)
    Mixed case:          "Jpn-ENG"
"""

# ISO-639-3 → internal 2-letter
_ISO3_TO_2: dict[str, str] = {
    "jpn": "jp",
    "eng": "en",
    "fra": "fr",
    "swh": "sw",
}

# Aliases that differ from the plain lowercase of the canonical code
_ALIASES: dict[str, str] = {
    "ja": "jp",   # sacrebleu / HuggingFace use "ja"; DB / WMT sample data use "jp"
    "ja_xx": "jp",
    "jap": "jp",
    "fre": "fr",
    "swa": "sw",
}


def normalize_lang_code(code: str) -> str:
    """Normalize one language code to the canonical 2-letter lowercase form.

    Examples:
        "jpn" → "jp"
        "ja"  → "jp"
        "JA"  → "jp"
        "ENG" → "en"
        "FR"  → "fr"
        "swh" → "sw"
    """
    c = code.lower().strip()
    if c in _ISO3_TO_2:
        return _ISO3_TO_2[c]
    if c in _ALIASES:
        return _ALIASES[c]
    # Already a canonical 2-letter code (en, fr, jp, sw …)
    return c


def normalize_lang_pair(lang_pair: str) -> str:
    """Normalize a language-pair string to canonical form.

    Examples:
        "jpn-eng"  → "jp-en"
        "ja-en"    → "jp-en"
        "JP-EN"    → "jp-en"
        "eng-fra"  → "en-fr"
        "swh-eng"  → "sw-en"
        "en-fr"    → "en-fr"   (already canonical, no-op)
    """
    parts = lang_pair.lower().strip().split("-")
    if len(parts) != 2:
        # Return lowercased original rather than crash
        return lang_pair.lower()
    return f"{normalize_lang_code(parts[0])}-{normalize_lang_code(parts[1])}"


def pair_from_db_langs(source_language: str, target_language: str) -> str:
    """Build a canonical pair string from Prisma SourceLanguage enum values.

    The DB stores Japanese as "JP" (not "JA"), so this function goes through
    normalize_lang_code which maps "jp" → "jp" unchanged.

    Examples:
        ("JP", "EN") → "jp-en"
        ("EN", "FR") → "en-fr"
        ("SW", "EN") → "sw-en"
    """
    return (
        f"{normalize_lang_code(source_language)}"
        f"-"
        f"{normalize_lang_code(target_language)}"
    )
