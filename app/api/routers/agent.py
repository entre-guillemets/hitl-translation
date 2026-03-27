# app/api/routers/agent.py
"""Agentic refinement loop endpoint.

GET /api/agent/refine-stream/{translation_string_id}

Streams an SSE narration while the agent autonomously:
  1. Checks the current brand-voice score for the string.
  2. Builds corrective feedback from the score + AdvertiserProfile constraints.
  3. Re-translates using Gemini with the corrective feedback turn.
  4. Re-scores the new output via the LLM judge.
  5. Repeats up to MAX_ATTEMPTS times or until the threshold is met.
  6. Writes the best output back to TranslationString.translatedText and
     persists the full iteration log to LLMJudgment.agentIterations.

Query params:
  force (bool, default False) — run even if the current score already meets
                                 the threshold.

SSE event shape (all events are in the default un-named channel):
  data: {"type": "narrate",   "message": "..."}
  data: {"type": "iteration", "attempt": N, "brand_voice_before": F,
          "brand_voice_after": F, "cultural_fitness_after": F,
          "feedback": "...", "text": "..."}
  data: {"type": "done",      "message": "...", "final_score": F,
          "iterations": N, "was_improved": bool, "final_text": "..."}
  data: {"type": "error",     "message": "..."}
"""

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.db.base import prisma
from app.dependencies import get_transcreation_service, get_llm_judge_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent", tags=["Agent"])

REFINEMENT_THRESHOLD = 3.0
MAX_ATTEMPTS = 2


def _sse(event_type: str, payload: dict) -> str:
    """Format one SSE data line."""
    return f"data: {json.dumps({'type': event_type, **payload})}\n\n"


def _normalize_source_lang(enum_val: str) -> str:
    """Convert Prisma SourceLanguage enum value to lowercase ISO code."""
    return enum_val.lower()  # EN→en, JP→jp, FR→fr, SW→sw


def _build_feedback(
    brand_voice_score: float,
    cultural_score: float | None,
    profile,
) -> str:
    """Compose a corrective feedback string from current scores + profile."""
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

    taboo_terms = list(profile.tabooTerms or [])
    if taboo_terms:
        parts.append(
            f"Ensure NONE of these terms appear in the output: {', '.join(taboo_terms)}."
        )

    key_terms = list(profile.keyTerms or [])
    if key_terms:
        parts.append(
            f"Preserve or appropriately adapt these key terms: {', '.join(key_terms)}."
        )

    return " ".join(parts) if parts else (
        "Refine the translation to better match the brand voice and cultural expectations."
    )


async def _run_refinement(
    string_id: str,
    force: bool,
    transcreation_svc,
    judge,
) -> AsyncGenerator[str, None]:
    """Core generator — yields SSE strings."""

    if not prisma.is_connected():
        await prisma.connect()

    yield _sse("narrate", {"message": "Agent started — fetching translation context…"})

    # ── 1. Fetch string + request + profile ──────────────────────────────────
    ts = await prisma.translationstring.find_unique(
        where={"id": string_id},
        include={
            "translationRequest": {
                "include": {"advertiserProfile": True}
            }
        },
    )

    if not ts:
        yield _sse("error", {"message": f"Translation string '{string_id}' not found."})
        return

    if not ts.translationRequest or not ts.translationRequest.advertiserProfile:
        yield _sse("error", {"message": "No advertiser profile linked to this request. Attach a brand profile before refining."})
        return

    profile = ts.translationRequest.advertiserProfile
    yield _sse("narrate", {"message": f"Profile loaded: {profile.brandName} ({profile.brandTone} / {profile.adRegister})."})

    # ── 2. Check Gemini availability ─────────────────────────────────────────
    if not transcreation_svc.is_available():
        yield _sse("error", {"message": "Gemini transcreation service unavailable — check GEMINI_API_KEY."})
        return

    if not judge.available:
        yield _sse("error", {"message": "LLM judge service unavailable — check GEMINI_API_KEY."})
        return

    # ── 3. Fetch existing LLMJudgment ────────────────────────────────────────
    existing_judgment = await prisma.llmjudgment.find_first(
        where={"translationStringId": string_id},
        order={"createdAt": "desc"},
    )

    current_bv = existing_judgment.brandVoiceScore if existing_judgment else None
    current_cf = existing_judgment.culturalFitnessScore if existing_judgment else None

    if current_bv is not None:
        yield _sse("narrate", {"message": f"Current brand-voice score: {current_bv:.1f}/5.0 (cultural fitness: {current_cf:.1f if current_cf is not None else '—'}/5.0)."})
    else:
        yield _sse("narrate", {"message": "No brand-voice score on record — will score during refinement."})

    if current_bv is not None and current_bv >= REFINEMENT_THRESHOLD and not force:
        yield _sse("narrate", {"message": f"Score already meets the threshold ({REFINEMENT_THRESHOLD}). Use ?force=true to refine anyway."})
        yield _sse("done", {
            "message": "No refinement needed.",
            "final_score": current_bv,
            "iterations": 0,
            "was_improved": False,
            "final_text": ts.translatedText,
        })
        return

    source_lang = _normalize_source_lang(str(ts.translationRequest.sourceLanguage))
    target_lang = ts.targetLanguage.lower()

    yield _sse("narrate", {
        "message": f"Starting refinement loop — max {MAX_ATTEMPTS} attempt(s), threshold {REFINEMENT_THRESHOLD}/5.0."
    })

    best_text = ts.translatedText
    best_bv = current_bv or 0.0
    best_cf = current_cf
    iterations: list[dict] = []

    # ── 4. Refinement loop ───────────────────────────────────────────────────
    for attempt in range(1, MAX_ATTEMPTS + 1):
        yield _sse("narrate", {"message": f"Attempt {attempt}/{MAX_ATTEMPTS}: building corrective feedback…"})

        feedback = _build_feedback(best_bv, best_cf, profile)
        yield _sse("narrate", {"message": f"Feedback: {feedback}"})
        yield _sse("narrate", {"message": "Re-translating with Gemini…"})

        try:
            new_text = await transcreation_svc.transcreate_with_corrective_feedback(
                ts.sourceText,
                source_lang,
                target_lang,
                profile,
                feedback,
                best_text,
            )
        except Exception as exc:
            yield _sse("error", {"message": f"Translation failed on attempt {attempt}: {exc}"})
            break

        yield _sse("narrate", {"message": "Re-evaluating brand-voice score…"})

        try:
            await asyncio.sleep(4)  # Gemini free-tier throttle
            score_result = await judge.evaluate_brand_voice(
                source=ts.sourceText,
                hypothesis=new_text,
                source_lang=source_lang,
                target_lang=target_lang,
                brand_name=profile.brandName,
                brand_tone=str(profile.brandTone),
                register=str(profile.adRegister),
                target_markets=list(profile.targetMarkets or []),
                key_terms=list(profile.keyTerms or []),
                taboo_terms=list(profile.tabooTerms or []),
                policy_notes=profile.policyNotes,
            )
        except Exception as exc:
            yield _sse("error", {"message": f"Scoring failed on attempt {attempt}: {exc}"})
            break

        new_bv = score_result["brand_voice"]
        new_cf = score_result["cultural_fitness"]

        iteration_record = {
            "attempt": attempt,
            "feedback": feedback,
            "brand_voice_before": best_bv,
            "brand_voice_after": new_bv,
            "cultural_fitness_after": new_cf,
            "text": new_text,
        }
        iterations.append(iteration_record)

        yield _sse("iteration", iteration_record)

        if new_bv > best_bv:
            best_text = new_text
            best_bv = new_bv
            best_cf = new_cf
            yield _sse("narrate", {"message": f"Improved to {new_bv:.1f}/5.0 — keeping this version."})
        else:
            yield _sse("narrate", {"message": f"Score did not improve ({new_bv:.1f}/5.0 vs {best_bv:.1f}/5.0) — keeping previous best."})

        if best_bv >= REFINEMENT_THRESHOLD:
            yield _sse("narrate", {"message": f"Threshold met ({best_bv:.1f}/5.0). Stopping."})
            break
        elif attempt < MAX_ATTEMPTS:
            yield _sse("narrate", {"message": f"Still below threshold after attempt {attempt}. Trying again…"})
        else:
            yield _sse("narrate", {"message": f"Max attempts reached. Best score: {best_bv:.1f}/5.0."})

    # ── 5. Persist results ───────────────────────────────────────────────────
    yield _sse("narrate", {"message": "Saving refined translation to database…"})

    was_improved = best_bv > (current_bv or 0.0)

    try:
        if was_improved:
            await prisma.translationstring.update(
                where={"id": string_id},
                data={"translatedText": best_text},
            )

        judgment_data = {
            "brandVoiceScore": best_bv,
            "culturalFitnessScore": best_cf,
            "wasRefined": True,
            "refinementAttempts": len(iterations),
            "agentIterations": iterations,
        }

        if existing_judgment:
            await prisma.llmjudgment.update(
                where={"id": existing_judgment.id},
                data=judgment_data,
            )
        else:
            await prisma.llmjudgment.create(
                data={
                    "translationStringId": string_id,
                    "judgeModel": "gemini-3.1-flash-lite-preview",
                    "adequacyScore": 3.0,
                    "fluencyScore": 3.0,
                    "confidenceScore": 0.7,
                    **judgment_data,
                },
            )

        yield _sse("narrate", {"message": "Database updated successfully."})

    except Exception as exc:
        yield _sse("error", {"message": f"DB update failed: {exc}"})

    yield _sse("done", {
        "message": "Refinement complete.",
        "final_score": best_bv,
        "iterations": len(iterations),
        "was_improved": was_improved,
        "final_text": best_text,
    })


@router.get("/refine-stream/{translation_string_id}")
async def refine_stream(
    translation_string_id: str,
    force: bool = Query(False, description="Refine even if the current score already meets the threshold"),
    transcreation_svc=Depends(get_transcreation_service),
    judge=Depends(get_llm_judge_service),
):
    """Stream the agentic brand-voice refinement loop for one translation string."""

    return StreamingResponse(
        _run_refinement(translation_string_id, force, transcreation_svc, judge),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
