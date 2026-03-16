"""LLM-as-Judge evaluation service using Gemini.

Scores MT hypotheses on adequacy (0–4) and fluency (0–4) using a structured
prompt. Results are stored in the llm_judgments table alongside a disagreement
signal comparing the LLM judgment to automatic COMET-DA scores.

Disagreement calculation:
  - Normalize COMET-DA: (comet + 1) / 2  → [0, 1]  (COMET-DA range ≈ -1 to 1)
  - Normalize adequacy: adequacy / 4      → [0, 1]
  - cometDisagreement = |comet_norm - adequacy_norm|

High disagreement (> 0.25) indicates segments where surface metrics give
misleading confidence — the primary signal for LLM-as-judge analysis.
"""

import asyncio
import json
import logging
import os
import re
from typing import Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# gemini-3.1-flash-lite-preview: 15 RPM, 500 RPD on free tier
JUDGE_MODEL = "gemini-3.1-flash-lite-preview"

# Language-pair-specific evaluation guidance injected when the pair involves
# a low-resource language where automatic metrics are known to be unreliable.
# Keyed by ISO 639-1 code (lowercase).
_LOW_RESOURCE_NOTES: dict[str, str] = {
    "sw": """\
NOTE — Low-resource language pair (Swahili):
- Automatic metrics (BLEU, TER, COMET) are unreliable for Swahili due to \
agglutinative morphology, 8 noun classes, and sparse training data. \
Your judgment is the PRIMARY quality signal for this pair, not a supplement to metrics.
- Pay particular attention to: (1) noun class concord — agreement between nouns and \
adjectives/verbs must match the noun class prefix (e.g., m-/wa- for people, ki-/vi- \
for objects); (2) verb aspect and tense markers, which are commonly garbled by MT; \
(3) dropped or mistranslated subject prefixes, which change meaning significantly.
- Score CONFIDENCE lower if you are uncertain about Swahili-specific structure. \
A confidence of 0.5–0.7 is appropriate when evaluating morphological correctness \
without native-speaker verification.
""",
}


def _build_low_resource_note(source_lang: str, target_lang: str) -> str:
    """Return language-pair-specific evaluation guidance, or empty string."""
    for lang in (source_lang.lower(), target_lang.lower()):
        if lang in _LOW_RESOURCE_NOTES:
            return "\n" + _LOW_RESOURCE_NOTES[lang]
    return ""


_PROMPT_TEMPLATE = """\
You are an expert machine translation evaluator.{low_resource_note}
Source ({source_lang}): {source}
Machine translation ({target_lang}): {hypothesis}{reference_block}

Score the machine translation on two dimensions:

ADEQUACY (0–4): Does the MT output convey the full meaning of the source?
  4 = All meaning preserved
  3 = Most meaning preserved (minor omissions or distortions)
  2 = Some meaning preserved (significant omissions or distortions)
  1 = Little meaning preserved
  0 = No meaning preserved

FLUENCY (0–4): Is the MT output natural and grammatical in {target_lang}?
  4 = Flawless
  3 = Good (minor grammatical errors or awkward phrasing)
  2 = Disfluent (noticeable errors that impede reading)
  1 = Poor (frequent errors)
  0 = Incomprehensible

CONFIDENCE (0–1): How certain are you in this assessment given the available context?

Respond with valid JSON only, no markdown fences:
{{"adequacy": <float 0-4>, "fluency": <float 0-4>, "confidence": <float 0-1>, "rationale": "<1-2 sentences>"}}"""


def _compute_comet_disagreement(comet_score: Optional[float], adequacy: float) -> Optional[float]:
    if comet_score is None:
        return None
    comet_norm = (comet_score + 1.0) / 2.0   # COMET-DA: roughly -1 to 1 → 0 to 1
    comet_norm = max(0.0, min(1.0, comet_norm))
    adequacy_norm = adequacy / 4.0
    return round(abs(comet_norm - adequacy_norm), 4)


class LLMJudgeService:
    def __init__(self):
        self._client: Optional[genai.Client] = None
        self._init_client()

    def _init_client(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not set — LLM judge will be unavailable.")
            return
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version="v1beta"),
        )
        logger.info(f"LLMJudgeService: Gemini client initialised (model: {JUDGE_MODEL}).")

    @property
    def available(self) -> bool:
        return self._client is not None

    @property
    def model(self) -> str:
        return JUDGE_MODEL

    async def evaluate(
        self,
        source: str,
        hypothesis: str,
        source_lang: str,
        target_lang: str,
        reference: Optional[str] = None,
        max_retries: int = 3,
    ) -> dict:
        """Call Gemini to score one hypothesis. Retries on 429 with backoff."""
        if not self._client:
            raise RuntimeError("LLM judge not available — check GEMINI_API_KEY.")

        ref_block = ""
        if reference:
            ref_block = f"\nHuman post-edit reference ({target_lang.upper()}): {reference}"

        prompt = _PROMPT_TEMPLATE.format(
            source_lang=source_lang.upper(),
            target_lang=target_lang.upper(),
            source=source,
            hypothesis=hypothesis,
            reference_block=ref_block,
            low_resource_note=_build_low_resource_note(source_lang, target_lang),
        )

        last_exc: Exception = RuntimeError("No attempts made")
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    self._client.models.generate_content,
                    model=JUDGE_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=256,
                    ),
                )
                text = response.text.strip()
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
                parsed = json.loads(text)
                return {
                    "adequacy": float(parsed["adequacy"]),
                    "fluency": float(parsed["fluency"]),
                    "confidence": float(parsed["confidence"]),
                    "rationale": parsed.get("rationale", ""),
                }
            except Exception as exc:
                last_exc = exc
                exc_str = str(exc)
                if "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str:
                    # Parse suggested retryDelay from the error message if present
                    delay_match = re.search(r"retry in (\d+(?:\.\d+)?)s", exc_str)
                    wait = float(delay_match.group(1)) if delay_match else (30 * (attempt + 1))
                    logger.warning(f"Gemini 429 on attempt {attempt + 1}/{max_retries} — waiting {wait:.0f}s")
                    await asyncio.sleep(wait)
                else:
                    raise

        raise last_exc

    def compute_disagreement(self, comet_score: Optional[float], adequacy: float) -> Optional[float]:
        return _compute_comet_disagreement(comet_score, adequacy)


llm_judge_service = LLMJudgeService()
