# app/api/routers/persona_transcreation.py
"""Persona transcreation endpoints.

POST /api/persona-transcreation/run
    Fan-out SSE stream — runs one refinement loop per persona sequentially.

GET  /api/persona-transcreation/{translation_string_id}
    Return all PersonaTranscreation rows for a string.

GET  /api/persona-transcreation/comparison/{translation_string_id}
    Side-by-side comparison payload for the UI.

POST /api/persona-transcreation/{id}/approve
    Promote a persona output to TranslationMemory (persona-scoped).

--- Persona CRUD (nested under advertiser profiles) ---

POST   /api/personas
GET    /api/personas
PATCH  /api/personas/{id}
DELETE /api/personas/{id}
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.db.base import prisma
from app.dependencies import get_transcreation_service, get_llm_judge_service
from app.services.persona_transcreation_service import run_persona_fan_out

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/persona-transcreation", tags=["Persona Transcreation"])
personas_router = APIRouter(prefix="/api/personas", tags=["Personas"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class PersonaRunRequest(BaseModel):
    translationStringId: str
    personaIds: list[str]
    targetLanguage: str


class PersonaCreate(BaseModel):
    advertiserProfileId: str
    name: str
    psychographicDescription: str
    messagingPriorities: list[str] = []
    toneOverride: Optional[str] = None
    registerOverride: Optional[str] = None


class PersonaUpdate(BaseModel):
    name: Optional[str] = None
    psychographicDescription: Optional[str] = None
    messagingPriorities: Optional[list[str]] = None
    toneOverride: Optional[str] = None
    registerOverride: Optional[str] = None


class ApprovePersonaOutput(BaseModel):
    domain: str = "advertising"


# ── SSE helper ────────────────────────────────────────────────────────────────

def _sse(event_type: str, payload: dict) -> str:
    return f"data: {json.dumps({'type': event_type, **payload})}\n\n"


# ── Run endpoint (SSE) ────────────────────────────────────────────────────────

async def _stream_persona_fan_out(
    body: PersonaRunRequest,
    transcreation_svc,
    judge,
):
    if not prisma.is_connected():
        await prisma.connect()

    yield _sse("narrate", {"message": f"Fetching translation string and {len(body.personaIds)} persona(s)…"})

    # Fetch translation string + advertiser profile
    ts = await prisma.translationstring.find_unique(
        where={"id": body.translationStringId},
        include={"translationRequest": {"include": {"advertiserProfile": True}}},
    )
    if not ts:
        yield _sse("error", {"message": f"Translation string '{body.translationStringId}' not found."})
        return

    if not ts.translationRequest or not ts.translationRequest.advertiserProfile:
        yield _sse("error", {"message": "No advertiser profile linked to this request."})
        return

    profile = ts.translationRequest.advertiserProfile

    # Fetch requested personas, validate they belong to this profile
    personas = await prisma.persona.find_many(
        where={
            "id": {"in": body.personaIds},
            "advertiserProfileId": profile.id,
        }
    )
    if not personas:
        yield _sse("error", {"message": "No valid personas found for this advertiser profile."})
        return

    if len(personas) != len(body.personaIds):
        found_ids = {p.id for p in personas}
        missing = [pid for pid in body.personaIds if pid not in found_ids]
        yield _sse("narrate", {"message": f"Warning: personas not found or not in profile: {missing}. Continuing with {len(personas)} persona(s)."})

    if not transcreation_svc.is_available():
        yield _sse("error", {"message": "Gemini transcreation service unavailable."})
        return

    if not judge.available:
        yield _sse("error", {"message": "LLM judge service unavailable."})
        return

    source_lang = str(ts.translationRequest.sourceLanguage).lower()
    target_lang = body.targetLanguage.lower()

    yield _sse("narrate", {
        "message": (
            f"Running persona fan-out for '{profile.brandName}': "
            f"{', '.join(p.name for p in personas)} → {target_lang.upper()}. "
            "Sequential execution (Gemini free tier)."
        )
    })

    # Create PENDING PersonaTranscreation rows in DB
    db_rows: dict[str, str] = {}  # persona_id → PersonaTranscreation.id
    for persona in personas:
        # Upsert: delete existing row for this string+persona if present
        existing = await prisma.personatranscreation.find_first(
            where={
                "translationStringId": body.translationStringId,
                "personaId": persona.id,
                "targetLanguage": target_lang,
            }
        )
        if existing:
            await prisma.personatranscreation.delete(where={"id": existing.id})

        row = await prisma.personatranscreation.create(
            data={
                "translationStringId": body.translationStringId,
                "personaId": persona.id,
                "targetLanguage": target_lang,
                "status": "PENDING",
            }
        )
        db_rows[persona.id] = row.id

    # Fan-out (sequential inside the service)
    for idx, persona in enumerate(personas):
        yield _sse("persona_start", {
            "message": f"[{idx+1}/{len(personas)}] Starting persona: {persona.name}",
            "personaId": persona.id,
            "personaName": persona.name,
        })

        # Mark IN_PROGRESS
        await prisma.personatranscreation.update(
            where={"id": db_rows[persona.id]},
            data={"status": "IN_PROGRESS"},
        )

    # Run the full fan-out
    results = await run_persona_fan_out(
        source_text=ts.sourceText,
        source_lang=source_lang,
        target_lang=target_lang,
        profile=profile,
        personas=personas,
        transcreation_svc=transcreation_svc,
        judge=judge,
    )

    # Persist results and stream completion events
    for result in results:
        row_id = db_rows.get(result.persona_id)
        if not row_id:
            continue

        update_data = {
            "status": result.status,
            "outputText": result.output_text,
            "brandVoiceScore": result.brand_voice_score,
            "culturalFitnessScore": result.cultural_fitness_score,
            "tabooViolation": result.taboo_violation,
            "keyTermMissing": result.key_term_missing,
            "differentiationScore": result.differentiation_score,
            "refinementAttempts": result.refinement_attempts,
            "agentIterations": result.agent_iterations,
            "rationale": result.rationale,
        }

        await prisma.personatranscreation.update(
            where={"id": row_id},
            data=update_data,
        )

        yield _sse("persona_complete", {
            "personaId": result.persona_id,
            "personaName": result.persona_name,
            "status": result.status,
            "brandVoiceScore": result.brand_voice_score,
            "culturalFitnessScore": result.cultural_fitness_score,
            "differentiationScore": result.differentiation_score,
            "refinementAttempts": result.refinement_attempts,
            "outputText": result.output_text,
        })

    completed = sum(1 for r in results if r.status == "COMPLETED")
    needs_review = sum(1 for r in results if r.status == "NEEDS_REVIEW")
    failed = sum(1 for r in results if r.status == "FAILED")

    yield _sse("differentiation_computed", {
        "message": "Pairwise differentiation scores computed.",
        "scores": {r.persona_name: r.differentiation_score for r in results},
    })

    yield _sse("done", {
        "message": (
            f"Fan-out complete: {completed} completed, "
            f"{needs_review} need review, {failed} failed."
        ),
        "completed": completed,
        "needsReview": needs_review,
        "failed": failed,
        "total": len(results),
    })


@router.post("/run")
async def run_persona_transcreation(
    body: PersonaRunRequest,
    transcreation_svc=Depends(get_transcreation_service),
    judge=Depends(get_llm_judge_service),
):
    """Stream the persona fan-out refinement loop via SSE."""
    return StreamingResponse(
        _stream_persona_fan_out(body, transcreation_svc, judge),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Results endpoints ─────────────────────────────────────────────────────────

@router.get("/{translation_string_id}")
async def get_persona_results(translation_string_id: str):
    """Return all PersonaTranscreation rows for a translation string."""
    rows = await prisma.personatranscreation.find_many(
        where={"translationStringId": translation_string_id},
        include={"persona": True},
        order={"createdAt": "asc"},
    )
    return {"translationStringId": translation_string_id, "results": rows}


@router.get("/comparison/{translation_string_id}")
async def get_comparison(translation_string_id: str):
    """Side-by-side comparison payload for the UI."""
    ts = await prisma.translationstring.find_unique(
        where={"id": translation_string_id},
        include={
            "translationRequest": {"include": {"advertiserProfile": True}},
            "personaTranscreations": {"include": {"persona": True}},
        },
    )
    if not ts:
        raise HTTPException(status_code=404, detail="Translation string not found.")

    rows = ts.personaTranscreations or []

    return {
        "translationStringId": translation_string_id,
        "sourceText": ts.sourceText,
        "advertiserProfile": ts.translationRequest.advertiserProfile if ts.translationRequest else None,
        "personas": [
            {
                "personaId": row.personaId,
                "personaName": row.persona.name if row.persona else None,
                "psychographicDescription": row.persona.psychographicDescription if row.persona else None,
                "outputText": row.outputText,
                "status": row.status,
                "brandVoiceScore": row.brandVoiceScore,
                "culturalFitnessScore": row.culturalFitnessScore,
                "differentiationScore": row.differentiationScore,
                "tabooViolation": row.tabooViolation,
                "keyTermMissing": row.keyTermMissing,
                "refinementAttempts": row.refinementAttempts,
                "agentIterations": row.agentIterations,
                "rowId": row.id,
            }
            for row in rows
        ],
    }


@router.post("/{persona_transcreation_id}/approve")
async def approve_persona_output(
    persona_transcreation_id: str,
    body: ApprovePersonaOutput,
):
    """Promote a persona output to TranslationMemory (persona-scoped).

    Only COMPLETED or NEEDS_REVIEW rows can be approved. Approval adds the
    output to TM with personaId set so future lookups can filter by persona.
    """
    row = await prisma.personatranscreation.find_unique(
        where={"id": persona_transcreation_id},
        include={
            "persona": True,
            "translationString": {
                "include": {
                    "translationRequest": {"include": {"advertiserProfile": True}}
                }
            },
        },
    )
    if not row:
        raise HTTPException(status_code=404, detail="PersonaTranscreation not found.")

    if row.status not in ("COMPLETED", "NEEDS_REVIEW"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve a row with status '{row.status}'."
        )

    if not row.outputText:
        raise HTTPException(status_code=400, detail="No output text to approve.")

    ts = row.translationString
    source_lang = str(ts.translationRequest.sourceLanguage).lower() if ts.translationRequest else "en"

    # Promote to TM with persona scoping
    await prisma.translationmemory.create(
        data={
            "sourceText": ts.sourceText,
            "targetText": row.outputText,
            "sourceLanguage": source_lang,
            "targetLanguage": row.targetLanguage,
            "quality": "HIGH",
            "domain": body.domain,
            "createdFrom": "PERSONA_APPROVED",
            "personaId": row.personaId,
        }
    )

    # If the row was NEEDS_REVIEW, mark it COMPLETED on human approval
    if row.status == "NEEDS_REVIEW":
        await prisma.personatranscreation.update(
            where={"id": persona_transcreation_id},
            data={"status": "COMPLETED"},
        )

    return {
        "message": f"Output approved and added to Translation Memory (persona-scoped: {row.persona.name if row.persona else row.personaId}).",
        "personaTranscreationId": persona_transcreation_id,
    }


# ── Persona CRUD ──────────────────────────────────────────────────────────────

@personas_router.post("")
async def create_persona(body: PersonaCreate):
    """Create a persona under an advertiser profile."""
    profile = await prisma.advertiserprofile.find_unique(where={"id": body.advertiserProfileId})
    if not profile:
        raise HTTPException(status_code=404, detail="Advertiser profile not found.")

    persona = await prisma.persona.create(
        data={
            "advertiserProfileId": body.advertiserProfileId,
            "name": body.name,
            "psychographicDescription": body.psychographicDescription,
            "messagingPriorities": body.messagingPriorities,
            "toneOverride": body.toneOverride,
            "registerOverride": body.registerOverride,
        }
    )
    return persona


@personas_router.get("")
async def list_personas(advertiserProfileId: str = Query(..., description="Filter by advertiser profile")):
    """List all personas for an advertiser profile."""
    personas = await prisma.persona.find_many(
        where={"advertiserProfileId": advertiserProfileId},
        order={"createdAt": "asc"},
    )
    return {"personas": personas}


@personas_router.patch("/{persona_id}")
async def update_persona(persona_id: str, body: PersonaUpdate):
    """Update a persona."""
    existing = await prisma.persona.find_unique(where={"id": persona_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Persona not found.")

    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update.")

    persona = await prisma.persona.update(where={"id": persona_id}, data=update_data)
    return persona


@personas_router.delete("/{persona_id}")
async def delete_persona(persona_id: str):
    """Delete a persona. Cascades to PersonaTranscreation rows."""
    existing = await prisma.persona.find_unique(where={"id": persona_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Persona not found.")

    await prisma.persona.delete(where={"id": persona_id})
    return {"message": f"Persona '{existing.name}' deleted."}
