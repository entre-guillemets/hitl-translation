# app/services/persona_transcreation_service.py
"""Fan-out persona transcreation service.

Runs the brand-voice refinement loop once per persona, sequentially (to respect
Gemini free-tier rate limits), then computes pairwise differentiation scores
across all persona outputs.

Sequential execution is a deliberate tier-driven constraint. With a paid Gemini
tier, the per-persona calls could be parallelised via asyncio.gather().
"""

import asyncio
import logging
import math
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

REFINEMENT_THRESHOLD = 3.0
MAX_ATTEMPTS = 2
GEMINI_RATE_LIMIT_DELAY = 4  # seconds between Gemini calls (free tier)


@dataclass
class PersonaRunResult:
    persona_id: str
    persona_name: str
    output_text: Optional[str]
    status: str  # mirrors PersonaTranscreationStatus enum values
    brand_voice_score: Optional[float]
    cultural_fitness_score: Optional[float]
    taboo_violation: Optional[bool]
    key_term_missing: Optional[bool]
    differentiation_score: Optional[float]
    refinement_attempts: int
    agent_iterations: list
    rationale: Optional[str]


def _build_persona_feedback(
    brand_voice_score: float,
    cultural_score: Optional[float],
    profile,
    persona,
) -> str:
    """Build corrective feedback that incorporates both profile constraints and
    persona-specific messaging priorities."""
    parts = []

    if brand_voice_score < 2.0:
        parts.append(
            "The previous output severely misses the brand voice — be much more "
            "faithful to the registered tone and register."
        )
    elif brand_voice_score < REFINEMENT_THRESHOLD:
        parts.append(
            "The previous output only partially captures the brand voice. "
            "Strengthen the tone and register match."
        )

    if cultural_score is not None and cultural_score < 3.0:
        parts.append(
            "The cultural adaptation for the target market is insufficient — "
            "use idiomatic expressions native to the target audience."
        )

    priorities = list(persona.messagingPriorities or [])
    if priorities:
        parts.append(
            f"This output is for the '{persona.name}' audience. "
            f"Messaging priorities: {', '.join(priorities)}."
        )

    taboo_terms = list(profile.tabooTerms or [])
    if taboo_terms:
        parts.append(
            f"Ensure NONE of these terms appear: {', '.join(taboo_terms)}."
        )

    key_terms = list(profile.keyTerms or [])
    if key_terms:
        parts.append(
            f"Preserve or appropriately adapt these key terms: {', '.join(key_terms)}."
        )

    return " ".join(parts) if parts else (
        f"Refine the translation to better match the '{persona.name}' audience, "
        "brand voice, and cultural expectations."
    )


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Simple cosine similarity between two equal-length vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _char_trigram_vector(text: str, vocab: set) -> list[float]:
    """Represent text as a character trigram frequency vector over a shared vocab."""
    trigrams: dict[str, int] = {}
    for i in range(len(text) - 2):
        tg = text[i:i + 3]
        trigrams[tg] = trigrams.get(tg, 0) + 1
    total = sum(trigrams.values()) or 1
    return [trigrams.get(tg, 0) / total for tg in sorted(vocab)]


def _compute_pairwise_differentiation(results: list[PersonaRunResult]) -> list[float]:
    """
    For each persona output, compute the average cosine similarity against all
    other persona outputs using character trigram vectors.

    Lower similarity = more differentiated (which is what we want).
    Returns a list of avg similarity scores, one per result, in input order.
    """
    texts = [r.output_text or "" for r in results]
    if len(texts) < 2:
        return [None] * len(texts)

    # Build shared trigram vocabulary across all outputs
    vocab: set[str] = set()
    for text in texts:
        for i in range(len(text) - 2):
            vocab.add(text[i:i + 3])

    if not vocab:
        return [None] * len(texts)

    vectors = [_char_trigram_vector(t, vocab) for t in texts]

    avg_similarities = []
    for i, vec_i in enumerate(vectors):
        sims = []
        for j, vec_j in enumerate(vectors):
            if i != j:
                sims.append(_cosine_similarity(vec_i, vec_j))
        avg_similarities.append(sum(sims) / len(sims) if sims else None)

    return avg_similarities


async def run_persona_fan_out(
    source_text: str,
    source_lang: str,
    target_lang: str,
    profile,
    personas: list,
    transcreation_svc,
    judge,
) -> list[PersonaRunResult]:
    """
    Run one refinement loop per persona, sequentially.

    Each persona may have a toneOverride / registerOverride that takes precedence
    over the profile-level values for that specific run.

    NOTE: Sequential by design — Gemini free tier does not support the call
    volume required for parallel fan-out. With a paid tier this loop body can be
    wrapped in asyncio.gather().
    """
    results: list[PersonaRunResult] = []

    for idx, persona in enumerate(personas):
        logger.info("Starting persona run %d/%d: %s", idx + 1, len(personas), persona.name)

        # Effective tone and register (persona overrides take precedence)
        effective_tone = str(persona.toneOverride or profile.brandTone)
        effective_register = str(persona.registerOverride or profile.adRegister)

        result = await _run_single_persona(
            source_text=source_text,
            source_lang=source_lang,
            target_lang=target_lang,
            profile=profile,
            persona=persona,
            effective_tone=effective_tone,
            effective_register=effective_register,
            transcreation_svc=transcreation_svc,
            judge=judge,
        )
        results.append(result)

        # Rate limit between personas — not needed after the last one
        if idx < len(personas) - 1:
            logger.debug("Rate-limit pause between personas (%ds)", GEMINI_RATE_LIMIT_DELAY)
            await asyncio.sleep(GEMINI_RATE_LIMIT_DELAY)

    # Compute differentiation scores across all completed outputs
    diff_scores = _compute_pairwise_differentiation(results)
    for result, score in zip(results, diff_scores):
        result.differentiation_score = score

    return results


async def _run_single_persona(
    source_text: str,
    source_lang: str,
    target_lang: str,
    profile,
    persona,
    effective_tone: str,
    effective_register: str,
    transcreation_svc,
    judge,
) -> PersonaRunResult:
    """Run the brand-voice refinement loop for one persona. Does not stream."""

    best_text: Optional[str] = None
    best_bv: float = 0.0
    best_cf: Optional[float] = None
    last_taboo: Optional[bool] = None
    last_key_term_missing: Optional[bool] = None
    last_rationale: Optional[str] = None
    iterations: list[dict] = []
    status = "IN_PROGRESS"

    # Build persona-specific system prompt addendum
    persona_context = (
        f"Audience segment: {persona.name}. "
        f"{persona.psychographicDescription} "
    )
    if persona.messagingPriorities:
        persona_context += f"Messaging priorities: {', '.join(persona.messagingPriorities)}."

    for attempt in range(1, MAX_ATTEMPTS + 1):
        feedback = _build_persona_feedback(best_bv, best_cf, profile, persona)

        try:
            if attempt == 1:
                # First attempt: transcreate with persona context injected
                new_text = await transcreation_svc.transcreate_with_profile(
                    text=source_text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    profile=_PersonaProfileAdapter(profile, persona, effective_tone, effective_register, persona_context),
                )
            else:
                # Subsequent attempts: corrective feedback loop
                new_text = await transcreation_svc.transcreate_with_corrective_feedback(
                    source_text,
                    source_lang,
                    target_lang,
                    _PersonaProfileAdapter(profile, persona, effective_tone, effective_register, persona_context),
                    feedback,
                    best_text,
                )
        except Exception as exc:
            logger.error("Transcreation failed for persona %s attempt %d: %s", persona.name, attempt, exc)
            status = "FAILED"
            break

        # Score — rate-limit pause before judge call
        await asyncio.sleep(GEMINI_RATE_LIMIT_DELAY)

        try:
            score_result = await judge.evaluate_brand_voice(
                source=source_text,
                hypothesis=new_text,
                source_lang=source_lang,
                target_lang=target_lang,
                brand_name=profile.brandName,
                brand_tone=effective_tone,
                register=effective_register,
                target_markets=list(profile.targetMarkets or []),
                key_terms=list(profile.keyTerms or []),
                taboo_terms=list(profile.tabooTerms or []),
                policy_notes=profile.policyNotes,
            )
        except Exception as exc:
            logger.error("Judge scoring failed for persona %s attempt %d: %s", persona.name, attempt, exc)
            status = "FAILED"
            break

        new_bv = score_result["brand_voice"]
        new_cf = score_result.get("cultural_fitness")
        last_taboo = score_result.get("taboo_violation")
        last_key_term_missing = score_result.get("key_term_missing")
        last_rationale = score_result.get("rationale")

        iteration_record = {
            "attempt": attempt,
            "feedback": feedback,
            "brand_voice_before": best_bv,
            "brand_voice_after": new_bv,
            "cultural_fitness_after": new_cf,
            "text": new_text,
        }
        iterations.append(iteration_record)

        if new_bv > best_bv:
            best_text = new_text
            best_bv = new_bv
            best_cf = new_cf

        if best_bv >= REFINEMENT_THRESHOLD:
            status = "COMPLETED"
            break

        if attempt == MAX_ATTEMPTS:
            # Exhausted attempts without meeting threshold
            status = "NEEDS_REVIEW"

    # If we exited the loop without a text (FAILED on first attempt)
    if best_text is None and iterations:
        best_text = iterations[-1].get("text")

    if status == "IN_PROGRESS":
        status = "NEEDS_REVIEW"

    return PersonaRunResult(
        persona_id=persona.id,
        persona_name=persona.name,
        output_text=best_text,
        status=status,
        brand_voice_score=best_bv if best_bv > 0 else None,
        cultural_fitness_score=best_cf,
        taboo_violation=last_taboo,
        key_term_missing=last_key_term_missing,
        differentiation_score=None,  # filled after fan-out completes
        refinement_attempts=len(iterations),
        agent_iterations=iterations,
        rationale=last_rationale,
    )


class _PersonaProfileAdapter:
    """Thin adapter that presents a Persona-aware interface to TranscreationService.

    TranscreationService expects an AdvertiserProfile-shaped object with
    brandTone, adRegister, keyTerms, tabooTerms, policyNotes, and brandName.
    This adapter merges the profile with persona overrides and appends the
    persona context to policyNotes so Gemini sees it in the system prompt.
    """

    def __init__(self, profile, persona, effective_tone: str, effective_register: str, persona_context: str):
        self.brandName = profile.brandName
        self.brandTone = effective_tone
        self.adRegister = effective_register
        self.targetMarkets = profile.targetMarkets
        self.keyTerms = profile.keyTerms
        self.tabooTerms = profile.tabooTerms
        # Append persona context to policyNotes so it surfaces in the system prompt
        base_notes = profile.policyNotes or ""
        self.policyNotes = f"{base_notes}\n\nAUDIENCE CONTEXT: {persona_context}".strip()
