# app/api/routers/agent.py
"""Agentic refinement loop endpoint.

GET /api/agent/refine-stream/{translation_string_id}?style_guide_id=<id>

Streams SSE while the agent autonomously:
  1. Loads the translation string and the specified StyleGuide.
  2. Re-translates using Gemini with style guide constraints injected.
  3. Scores the output via the LLM judge (constraintScore).
  4. Repeats up to MAX_ATTEMPTS or until the threshold is met.
  5. Writes the best output back to TranslationString.translatedText and
     creates/updates the LLMJudgment row with constraintScore.

SSE event shape:
  data: {"type": "narrate",   "message": "..."}
  data: {"type": "iteration", "attempt": N, "score_before": F, "score_after": F,
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

REFINEMENT_THRESHOLD = 3.5
MAX_ATTEMPTS = 2


def _sse(event_type: str, payload: dict) -> str:
    return f"data: {json.dumps({'type': event_type, **payload})}\n\n"


def _build_feedback(score: float, guide) -> str:
    required_terms = [t.term for t in (guide.terms or []) if str(t.type) == "REQUIRED"]
    forbidden_terms = [t.term for t in (guide.terms or []) if str(t.type) == "FORBIDDEN"]
    parts = []
    if score < 2.0:
        parts.append("The previous output seriously violates the style guide — revisit register, tone, and all rules.")
    elif score < REFINEMENT_THRESHOLD:
        parts.append("The previous output only partially follows the style guide. Strengthen compliance.")
    if required_terms:
        parts.append(f"Ensure these required terms appear in the output: {', '.join(required_terms)}.")
    if forbidden_terms:
        parts.append(f"Ensure NONE of these forbidden terms appear: {', '.join(forbidden_terms)}.")
    if guide.rules:
        parts.append(f"Rules to follow: {'; '.join(guide.rules)}.")
    return " ".join(parts) or "Revise to better follow the style guide constraints."


async def _run_refinement(
    string_id: str,
    style_guide_id: str,
    force: bool,
    transcreation_svc,
    judge,
) -> AsyncGenerator[str, None]:

    if not prisma.is_connected():
        await prisma.connect()

    yield _sse("narrate", {"message": "Agent started — fetching translation context…"})

    ts = await prisma.translationstring.find_unique(
        where={"id": string_id},
        include={"translationRequest": True},
    )
    if not ts:
        yield _sse("error", {"message": f"Translation string '{string_id}' not found."})
        return

    guide = await prisma.styleguide.find_unique(
        where={"id": style_guide_id},
        include={"terms": True},
    )
    if not guide:
        yield _sse("error", {"message": f"Style guide '{style_guide_id}' not found."})
        return

    yield _sse("narrate", {"message": f"Style guide loaded: {guide.name} ({guide.styleRegister})."})

    if not transcreation_svc.is_available():
        yield _sse("error", {"message": "Gemini transcreation service unavailable — check GEMINI_API_KEY."})
        return

    if not judge.available:
        yield _sse("error", {"message": "LLM judge unavailable — check GEMINI_API_KEY."})
        return

    existing_judgment = await prisma.llmjudgment.find_first(
        where={"translationStringId": string_id},
        order={"createdAt": "desc"},
    )

    current_score = existing_judgment.constraintScore if existing_judgment else None

    if current_score is not None:
        yield _sse("narrate", {"message": f"Current constraint score: {current_score:.1f}/5.0."})
    else:
        yield _sse("narrate", {"message": "No constraint score on record — will score during refinement."})

    if current_score is not None and current_score >= REFINEMENT_THRESHOLD and not force:
        yield _sse("narrate", {"message": f"Score already meets threshold ({REFINEMENT_THRESHOLD}). Use ?force=true to refine anyway."})
        yield _sse("done", {
            "message": "No refinement needed.",
            "final_score": current_score,
            "iterations": 0,
            "was_improved": False,
            "final_text": ts.translatedText,
        })
        return

    source_lang = str(ts.translationRequest.sourceLanguage).lower() if ts.translationRequest else "en"
    target_lang = ts.targetLanguage.lower()

    yield _sse("narrate", {"message": f"Starting refinement — max {MAX_ATTEMPTS} attempt(s), threshold {REFINEMENT_THRESHOLD}/5.0."})

    best_text = ts.translatedText
    best_score = current_score or 0.0
    iterations: list[dict] = []

    for attempt in range(1, MAX_ATTEMPTS + 1):
        yield _sse("narrate", {"message": f"Attempt {attempt}/{MAX_ATTEMPTS}: building corrective feedback…"})

        feedback = _build_feedback(best_score, guide)
        yield _sse("narrate", {"message": f"Feedback: {feedback}"})
        yield _sse("narrate", {"message": "Re-translating with Gemini…"})

        try:
            new_text = await transcreation_svc.transcreate_with_style_guide(
                ts.sourceText, source_lang, target_lang, guide
            )
        except Exception as exc:
            yield _sse("error", {"message": f"Translation failed on attempt {attempt}: {exc}"})
            break

        yield _sse("narrate", {"message": "Scoring output against style guide constraints…"})

        try:
            await asyncio.sleep(4)
            score_result = await judge.evaluate_constraint_score(
                source=ts.sourceText,
                hypothesis=new_text,
                source_lang=source_lang,
                target_lang=target_lang,
                style_guide=guide,
            )
        except Exception as exc:
            yield _sse("error", {"message": f"Scoring failed on attempt {attempt}: {exc}"})
            break

        new_score = score_result["constraint_score"]

        iteration_record = {
            "attempt": attempt,
            "feedback": feedback,
            "score_before": best_score,
            "score_after": new_score,
            "text": new_text,
        }
        iterations.append(iteration_record)
        yield _sse("iteration", iteration_record)

        if new_score > best_score:
            best_text = new_text
            best_score = new_score
            yield _sse("narrate", {"message": f"Improved to {new_score:.1f}/5.0 — keeping this version."})
        else:
            yield _sse("narrate", {"message": f"Score did not improve ({new_score:.1f} vs {best_score:.1f}) — keeping previous best."})

        if best_score >= REFINEMENT_THRESHOLD:
            yield _sse("narrate", {"message": f"Threshold met ({best_score:.1f}/5.0). Stopping."})
            break
        elif attempt < MAX_ATTEMPTS:
            yield _sse("narrate", {"message": f"Still below threshold. Trying again…"})
        else:
            yield _sse("narrate", {"message": f"Max attempts reached. Best score: {best_score:.1f}/5.0."})

    yield _sse("narrate", {"message": "Saving refined translation…"})

    was_improved = best_score > (current_score or 0.0)

    try:
        if was_improved:
            await prisma.translationstring.update(
                where={"id": string_id},
                data={"translatedText": best_text},
            )

        judgment_data = {
            "constraintScore": best_score,
            "styleGuideId": style_guide_id,
            "rationale": iterations[-1]["feedback"] if iterations else None,
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

        yield _sse("narrate", {"message": "Database updated."})

    except Exception as exc:
        yield _sse("error", {"message": f"DB update failed: {exc}"})

    yield _sse("done", {
        "message": "Refinement complete.",
        "final_score": best_score,
        "iterations": len(iterations),
        "was_improved": was_improved,
        "final_text": best_text,
    })


@router.get("/refine-stream/{translation_string_id}")
async def refine_stream(
    translation_string_id: str,
    style_guide_id: str = Query(..., description="StyleGuide ID to use as constraint source"),
    force: bool = Query(False),
    transcreation_svc=Depends(get_transcreation_service),
    judge=Depends(get_llm_judge_service),
):
    async def generator():
        async for chunk in _run_refinement(
            translation_string_id, style_guide_id, force, transcreation_svc, judge
        ):
            yield chunk

    return StreamingResponse(generator(), media_type="text/event-stream")
