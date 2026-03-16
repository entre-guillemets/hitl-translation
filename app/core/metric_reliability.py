# app/core/metric_reliability.py
"""
Static domain knowledge about metric reliability per language.

These reflect known methodological limitations of automatic MT metrics, not
computed properties. They are combined with dynamic DB sample-size stats to
produce the final reliability assessment returned by the API.

Sources:
- Papineni et al. (2002) — BLEU tokenization sensitivity
- Popović (2015) — ChrF character n-gram advantage for morphological languages
- Freitag et al. (2022) — COMET vs. surface metrics for human judgment correlation
- Bentivogli et al. (2016) — TER limitations for morphological languages
"""

from typing import Literal

ReliabilityLevel = Literal["high", "medium", "low"]

LANGUAGE_METADATA: dict[str, dict] = {
    "ja": {
        "script": "CJK",
        "language_name": "Japanese",
        "tokenization_strategy": "ja-mecab for BLEU; character-level pre-tokenization for TER",
        "notes": "Agglutinative morphology and lack of whitespace boundaries make n-gram metrics unreliable. MeCab tokenizer reduces but does not eliminate BLEU sensitivity.",
        "metrics": {
            "bleu": {
                "reliability": "low",
                "reason": "N-gram precision is tokenizer-sensitive. Japanese morphology (verb conjugation, postpositional particles) produces high surface variation for semantically equivalent outputs.",
            },
            "ter": {
                "reliability": "medium",
                "reason": "Character-level pre-tokenization applied (avoids the 100% TER artifact from whitespace splitting). Still approximate — word-level edit distance is more meaningful than character-level.",
            },
            "chrf": {
                "reliability": "high",
                "reason": "Character n-gram overlap is well-suited for CJK scripts. Less sensitive to tokenization choice than BLEU.",
            },
            "comet": {
                "reliability": "high",
                "reason": "Multilingual embeddings trained on Japanese data. Best available automatic signal for JA; correlates better with human judgment than surface metrics.",
            },
        },
    },
    "jp": {
        # Alias: DB stores JP, normalization maps both
        "script": "CJK",
        "language_name": "Japanese",
        "tokenization_strategy": "ja-mecab for BLEU; character-level pre-tokenization for TER",
        "notes": "Agglutinative morphology and lack of whitespace boundaries make n-gram metrics unreliable. MeCab tokenizer reduces but does not eliminate BLEU sensitivity.",
        "metrics": {
            "bleu": {
                "reliability": "low",
                "reason": "N-gram precision is tokenizer-sensitive. Japanese morphology produces high surface variation for semantically equivalent outputs.",
            },
            "ter": {
                "reliability": "medium",
                "reason": "Character-level pre-tokenization applied. Still approximate compared to word-level edit distance.",
            },
            "chrf": {
                "reliability": "high",
                "reason": "Character n-gram overlap is well-suited for CJK scripts.",
            },
            "comet": {
                "reliability": "high",
                "reason": "Multilingual embeddings trained on Japanese data. Best available automatic signal for JA.",
            },
        },
    },
    "fr": {
        "script": "Latin",
        "language_name": "French",
        "tokenization_strategy": "Moses 13a tokenizer (sacrebleu default)",
        "notes": "Well-resourced language pair. Standard metrics are reliable. ChrF handles French morphology (gendered forms, verb conjugation) slightly better than BLEU at segment level.",
        "metrics": {
            "bleu": {
                "reliability": "high",
                "reason": "Moses tokenizer is well-calibrated for French. Large training sets in WMT benchmarks make scores interpretable.",
            },
            "ter": {
                "reliability": "high",
                "reason": "Word-level edit distance is meaningful for whitespace-delimited French. Direct measure of post-editing effort.",
            },
            "chrf": {
                "reliability": "high",
                "reason": "Character n-grams handle French inflectional morphology better than BLEU at the segment level.",
            },
            "comet": {
                "reliability": "high",
                "reason": "Strong multilingual embedding coverage for French. Highest-signal metric for EN↔FR.",
            },
        },
    },
    "en": {
        "script": "Latin",
        "language_name": "English",
        "tokenization_strategy": "Moses 13a tokenizer (sacrebleu default)",
        "notes": "Well-resourced language. All standard metrics reliable. English serves as source or target depending on language pair direction.",
        "metrics": {
            "bleu": {
                "reliability": "high",
                "reason": "BLEU was developed and benchmarked primarily on English. Tokenization is deterministic and well-understood.",
            },
            "ter": {
                "reliability": "high",
                "reason": "Word-level edit distance is well-defined for English whitespace-delimited text.",
            },
            "chrf": {
                "reliability": "high",
                "reason": "Reliable for English; provides character-level granularity useful for morphological variation.",
            },
            "comet": {
                "reliability": "high",
                "reason": "Best-calibrated for English-centric language pairs. Highest correlation with human judgment.",
            },
        },
    },
    "sw": {
        "script": "Latin-agglutinative",
        "language_name": "Swahili",
        "tokenization_strategy": "Moses 13a (whitespace) — no dedicated Swahili tokenizer available",
        "notes": "Low-resource language. NLLB-200 covers Swahili (swh_Latn) but training data is sparse. BLEU is substantially less reliable due to 8 noun classes and rich verb morphology. LLM-as-judge is the primary quality signal for this language pair.",
        "metrics": {
            "bleu": {
                "reliability": "low",
                "reason": "Swahili's 8 noun classes and agglutinative verb morphology mean that semantically equivalent translations have low n-gram overlap. BLEU scores should not be interpreted comparably to EN↔FR scores.",
            },
            "ter": {
                "reliability": "low",
                "reason": "Word-level edit distance is unstable for agglutinative languages where morphological variants are single tokens. No Swahili-specific tokenizer applied.",
            },
            "chrf": {
                "reliability": "medium",
                "reason": "Character n-grams partially capture morphological similarity. More meaningful than BLEU for Swahili but still noisy given sparse reference data.",
            },
            "comet": {
                "reliability": "medium",
                "reason": "COMET-DA coverage of Swahili is limited in the wmt22-cometkiwi training data. Scores may not correlate with human judgment as well as for high-resource pairs. Treat as indicative, not authoritative.",
            },
        },
    },
}

# Minimum segment count below which aggregate claims are considered unreliable
MIN_RELIABLE_SAMPLE_SIZE = 30

# BLEU standard deviation threshold above which variance is considered unusually high
HIGH_BLEU_VARIANCE_THRESHOLD = 0.30

# Per-pair recommendation for the primary evaluation signal.
# Operationalizes the reliability table: given known metric limitations,
# what should an evaluator actually look at first for this language pair?
# The "complex" language in the pair determines the recommendation.
PAIR_RECOMMENDATIONS: dict[str, str] = {
    "en-ja": "COMET + ChrF (ignore BLEU)",
    "en-jp": "COMET + ChrF (ignore BLEU)",
    "ja-en": "COMET + ChrF",
    "jp-en": "COMET + ChrF",
    "en-fr": "COMET or BLEU",
    "fr-en": "COMET or BLEU",
    "sw-en": "LLM judge (auto metrics unreliable)",
    "en-sw": "LLM judge (auto metrics unreliable)",
}


def get_recommended_primary_metric(source_lang: str, target_lang: str) -> str:
    """Return the recommended primary metric for a language pair. Defaults to COMET."""
    pair = f"{source_lang.lower()}-{target_lang.lower()}"
    return PAIR_RECOMMENDATIONS.get(pair, "COMET")


def get_language_metadata(lang_code: str) -> dict | None:
    """Return static metadata for a language code (case-insensitive)."""
    return LANGUAGE_METADATA.get(lang_code.lower())


def parse_language_pair(language_pair: str) -> tuple[str, str] | None:
    """
    Parse a language pair string into (source, target) codes.
    Accepts formats: 'JA-EN', 'ja_en', 'JP-EN', 'fr-en', etc.
    """
    normalized = language_pair.upper().replace("_", "-")
    parts = normalized.split("-")
    if len(parts) == 2:
        return parts[0].lower(), parts[1].lower()
    return None


def compute_reliability_warning(
    source_lang: str,
    target_lang: str,
    sample_size: int,
    bleu_std: float | None,
) -> tuple[bool, list[str], bool, bool]:
    """
    Returns (reliability_warning, warning_reasons, metric_reliability_warning, statistical_confidence_warning).

    Two distinct warning dimensions:
    - metric_reliability_warning: inherent to the language pair — known methodological
      limitations (tokenization sensitivity, morphological complexity, training data gaps).
      This does NOT change as more data accumulates.
    - statistical_confidence_warning: driven by current sample size and BLEU variance.
      Will resolve as more segments are evaluated.

    reliability_warning is True when either dimension is triggered.
    """
    metric_reasons: list[str] = []
    confidence_reasons: list[str] = []

    # --- Statistical confidence dimension ---
    if sample_size < MIN_RELIABLE_SAMPLE_SIZE:
        confidence_reasons.append(
            f"Small sample (n={sample_size}); minimum {MIN_RELIABLE_SAMPLE_SIZE} segments required for reliable aggregate claims."
        )

    if bleu_std is not None and bleu_std > HIGH_BLEU_VARIANCE_THRESHOLD:
        confidence_reasons.append(
            f"High BLEU variance (σ={bleu_std:.2f}); scores are unstable across segments."
        )

    # --- Metric reliability dimension ---
    # Check static reliability for target language (translation quality is assessed in target)
    target_meta = get_language_metadata(target_lang)
    if target_meta:
        low_metrics = [
            metric
            for metric, info in target_meta["metrics"].items()
            if info["reliability"] == "low"
        ]
        if low_metrics:
            metric_reasons.append(
                f"Known metric reliability concerns for {target_meta['language_name']}: {', '.join(m.upper() for m in low_metrics)} rated low reliability."
            )

    all_reasons = confidence_reasons + metric_reasons
    return (
        bool(all_reasons),
        all_reasons,
        bool(metric_reasons),
        bool(confidence_reasons),
    )
