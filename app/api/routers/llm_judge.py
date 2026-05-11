# app/api/routers/llm_judge.py
"""LLM-as-Judge evaluation endpoints.

POST /api/llm-judge/evaluate/{translation_string_id}
    Evaluate all MT engine outputs for a single approved/reviewed string.
    Writes one LLMJudgment row per engine. Computes cometDisagreement by
    joining with the existing QualityMetrics row for the same engine.

POST /api/llm-judge/evaluate-all-approved
    Batch evaluate all approved/reviewed strings that have no LLMJudgment yet.

GET /api/llm-judge/disagreements
    Return segments ranked by cometDisagreement (highest first).
    Query params: limit (default 50), min_disagreement (default 0.0).
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.db.base import prisma
from app.dependencies import get_llm_judge_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/llm-judge", tags=["LLM Judge"])


def _parse_engine_results(raw) -> list:
    """Parse engineResults regardless of whether it is already a list or a
    JSON-encoded string (Prisma Json fields can be returned as either)."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return []


# ---------------------------------------------------------------------------
# Single-string evaluation
# ---------------------------------------------------------------------------

@router.post("/evaluate/{translation_string_id}")
async def evaluate_string(
    translation_string_id: str,
    judge=Depends(get_llm_judge_service),
):
    """Evaluate all MT engine outputs for one translation string."""
    if not judge.available:
        raise HTTPException(status_code=503, detail="LLM judge not available — check GEMINI_API_KEY.")

    if not prisma.is_connected():
        await prisma.connect()

    ts = await prisma.translationstring.find_unique(
        where={"id": translation_string_id},
        include={"translationRequest": True},
    )
    if not ts:
        raise HTTPException(status_code=404, detail="Translation string not found.")

    from prisma.enums import StringStatus
    if ts.status not in [StringStatus.REVIEWED, StringStatus.APPROVED]:
        raise HTTPException(
            status_code=400,
            detail="String must be REVIEWED or APPROVED to evaluate.",
        )

    reference = ts.translatedText   # human post-edit
    source = ts.sourceText
    target_lang = ts.targetLanguage.lower()
    src_lang = (
        str(ts.translationRequest.sourceLanguage).lower()
        if ts.translationRequest else "en"
    )

    # Build (engine_name, hypothesis) pairs
    candidates: list[tuple] = []
    engine_results = _parse_engine_results(ts.engineResults)
    for result in engine_results:
        engine_id = result.get("engine")
        text = (result.get("text") or "").strip()
        if engine_id and text and text != reference.strip():
            candidates.append((engine_id, text))

    original_mt = (ts.originalTranslation or "").strip()
    if original_mt and original_mt != reference.strip():
        if not any(h == original_mt for _, h in candidates):
            candidates.append((None, original_mt))

    if not candidates:
        return {"evaluated": 0, "message": "No scoreable MT hypotheses found."}

    # Fetch existing QualityMetrics for disagreement calculation
    existing_metrics = await prisma.qualitymetrics.find_many(
        where={"translationStringId": translation_string_id},
    )
    comet_by_engine: dict = {m.engineName: m.cometScore for m in existing_metrics}

    # Delete any previous judgments for this string to allow re-evaluation
    await prisma.llmjudgment.delete_many(where={"translationStringId": translation_string_id})

    created = []
    for engine_name, hypothesis in candidates:
        try:
            scores = await judge.evaluate(
                source=source,
                hypothesis=hypothesis,
                source_lang=src_lang,
                target_lang=target_lang,
                reference=reference,
            )
            comet_score = comet_by_engine.get(engine_name)
            disagreement = judge.compute_disagreement(comet_score, scores["adequacy"])

            await prisma.llmjudgment.create(
                data={
                    "translationStringId": translation_string_id,
                    "engineName": engine_name,
                    "judgeModel": judge.model,
                    "adequacyScore": scores["adequacy"],
                    "fluencyScore": scores["fluency"],
                    "confidenceScore": scores["confidence"],
                    "rationale": scores["rationale"],
                    "cometDisagreement": disagreement,
                }
            )
            created.append({
                "engine": engine_name,
                "adequacy": scores["adequacy"],
                "fluency": scores["fluency"],
                "confidence": scores["confidence"],
                "cometDisagreement": disagreement,
                "rationale": scores["rationale"],
            })
            logger.info(
                f"✅ LLM judge [{engine_name or 'single-engine'}] {translation_string_id}: "
                f"adequacy={scores['adequacy']:.1f} fluency={scores['fluency']:.1f} "
                f"disagreement={disagreement}"
            )
        except Exception as e:
            logger.error(f"LLM judge failed for engine={engine_name} string={translation_string_id}: {e}")

    return {"evaluated": len(created), "judgments": created}


# ---------------------------------------------------------------------------
# Batch evaluation
# ---------------------------------------------------------------------------

@router.post("/evaluate-all-approved")
async def evaluate_all_approved(
    judge=Depends(get_llm_judge_service),
    limit: int = Query(10, ge=1, le=200, description="Max strings to evaluate per run (free tier: ~40 strings/day)"),
):
    """Batch LLM-judge approved/reviewed strings that have no judgment yet."""
    if not judge.available:
        raise HTTPException(status_code=503, detail="LLM judge not available — check GEMINI_API_KEY.")

    if not prisma.is_connected():
        await prisma.connect()

    # Only process strings not yet judged, capped by limit
    strings = await prisma.translationstring.find_many(
        where={
            "status": {"in": ["REVIEWED", "APPROVED"]},
            "llmJudgments": {"none": {}},
            "translationRequest": {
                "is": {
                    "requestType": {"not": "WMT_BENCHMARK"}
                }
            }
        },
        include={"translationRequest": True},
        take=limit,
    )

    logger.info(f"LLM judge batch: {len(strings)} strings to evaluate (limit={limit}).")

    processed = 0
    skipped = 0
    errors = []

    for ts in strings:
        # --- Skip condition 1: missing required fields ---
        if not ts.translatedText:
            logger.info(f"SKIP {ts.id}: missing translatedText")
            skipped += 1
            continue

        reference = ts.translatedText
        source = ts.sourceText
        target_lang = ts.targetLanguage.lower()
        src_lang = (
            str(ts.translationRequest.sourceLanguage).lower()
            if ts.translationRequest else "en"
        )

        # Build candidates — parse engineResults safely whether list or JSON string
        candidates: list[tuple] = []
        engine_results = _parse_engine_results(ts.engineResults)
        logger.info(f"STRING {ts.id}: engineResults type={type(ts.engineResults).__name__}, parsed count={len(engine_results)}")

        for result in engine_results:
            engine_id = result.get("engine")
            text = (result.get("text") or "").strip()
            if engine_id and text and text != reference.strip():
                candidates.append((engine_id, text))

        original_mt = (ts.originalTranslation or "").strip()
        if original_mt and original_mt != reference.strip():
            if not any(h == original_mt for _, h in candidates):
                candidates.append((None, original_mt))

        # If no engine-specific candidates, treat translatedText as a single hypothesis.
        # This handles seed strings and single-engine submissions that have no engineResults.
        if not candidates:
            if reference.strip():
                candidates.append((None, reference.strip()))
            else:
                logger.info(f"SKIP {ts.id}: no candidates and no translatedText")
                skipped += 1
                continue

        logger.info(f"STRING {ts.id}: {len(candidates)} candidates to evaluate: {[e for e, _ in candidates]}")

        existing_metrics = await prisma.qualitymetrics.find_many(
            where={"translationStringId": ts.id},
        )
        comet_by_engine: dict = {m.engineName: m.cometScore for m in existing_metrics}

        string_processed = 0
        for engine_name, hypothesis in candidates:
            try:
                scores = await judge.evaluate(
                    source=source,
                    hypothesis=hypothesis,
                    source_lang=src_lang,
                    target_lang=target_lang,
                    reference=reference,
                )
                comet_score = comet_by_engine.get(engine_name)
                disagreement = judge.compute_disagreement(comet_score, scores["adequacy"])

                await prisma.llmjudgment.create(
                    data={
                        "translationStringId": ts.id,
                        "engineName": engine_name,
                        "judgeModel": judge.model,
                        "adequacyScore": scores["adequacy"],
                        "fluencyScore": scores["fluency"],
                        "confidenceScore": scores["confidence"],
                        "rationale": scores["rationale"],
                        "cometDisagreement": disagreement,
                    }
                )
                string_processed += 1
                logger.info(
                    f"✅ LLM judge batch [{engine_name or 'single-engine'}] {ts.id}: "
                    f"adequacy={scores['adequacy']:.1f} fluency={scores['fluency']:.1f}"
                )
            except Exception as e:
                logger.error(f"LLM judge error string={ts.id} engine={engine_name}: {e}")
                errors.append({"id": ts.id, "engine": engine_name, "error": str(e)})
            finally:
                # Throttle to ~12 RPM — well under the 15 RPM free-tier limit
                await asyncio.sleep(5)

        if string_processed > 0:
            processed += 1
        else:
            skipped += 1

    return {
        "success": True,
        "processed": processed,
        "skipped": skipped,
        "total": len(strings),
        "errors": errors or None,
        "message": f"LLM judge evaluated {processed} strings (skipped {skipped})",
    }


# ---------------------------------------------------------------------------
# Disagreement report
# ---------------------------------------------------------------------------

@router.get("/disagreements")
async def get_disagreements(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    min_disagreement: float = Query(0.0, ge=0.0, le=1.0),
):
    """Return segments with highest COMET vs LLM-judge disagreement.

    cometDisagreement is |comet_normalized - adequacy_normalized| where both
    are scaled to [0, 1]. Values above 0.25 indicate meaningful disagreement.
    """
    if not prisma.is_connected():
        await prisma.connect()

    judgments = await prisma.llmjudgment.find_many(
        where={
            "cometDisagreement": {"gte": min_disagreement},
        },
        include={
            "translationString": {
                "include": {"translationRequest": True}
            }
        },
        order={"createdAt": "desc"},
        take=limit,
        skip=offset,
    )

    results = []
    for j in judgments:
        ts = j.translationString
        lang_pair = None
        if ts and ts.translationRequest:
            src = str(ts.translationRequest.sourceLanguage)
            tgt = ts.targetLanguage.upper()
            lang_pair = f"{src}-{tgt}"
        hypothesis = None
        if ts and ts.engineResults:
            engine_results = ts.engineResults if isinstance(ts.engineResults, list) else json.loads(ts.engineResults) if isinstance(ts.engineResults, str) else []
            for result in engine_results:
                if result.get("engine") == j.engineName:
                    hypothesis = result.get("text")
                    break
        # Fall back to originalTranslation, then translatedText for seed/single-engine strings
        if not hypothesis and ts:
            hypothesis = ts.originalTranslation or ts.translatedText

        results.append({
            "translationStringId": j.translationStringId,
            "engineName": j.engineName,
            "languagePair": lang_pair,
            "sourceText": ts.sourceText if ts else None,
            "hypothesis": hypothesis,        
            "humanReference": ts.translatedText if ts else None,
            "adequacyScore": j.adequacyScore,
            "fluencyScore": j.fluencyScore,
            "confidenceScore": j.confidenceScore,
            "cometDisagreement": j.cometDisagreement,
            "rationale": j.rationale,
            "judgeModel": j.judgeModel,
            "createdAt": j.createdAt.isoformat(),
        })

    return {
        "count": len(results),
        "minDisagreement": min_disagreement,
        "disagreements": results,
    }


# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------

@router.get("/summary")
async def get_judge_summary():
    """Aggregate adequacy/fluency/disagreement stats per language pair."""
    if not prisma.is_connected():
        await prisma.connect()

    judgments = await prisma.llmjudgment.find_many(
        include={
            "translationString": {
                "include": {"translationRequest": True}
            }
        }
    )

    from collections import defaultdict
    import statistics as _stats

    by_pair: dict = defaultdict(lambda: {
        "adequacy": [], "fluency": [], "confidence": [], "disagreement": []
    })

    for j in judgments:
        ts = j.translationString
        if not ts or not ts.translationRequest:
            continue
        src = str(ts.translationRequest.sourceLanguage)
        tgt = ts.targetLanguage.upper()
        pair = f"{src}-{tgt}"
        by_pair[pair]["adequacy"].append(j.adequacyScore)
        by_pair[pair]["fluency"].append(j.fluencyScore)
        by_pair[pair]["confidence"].append(j.confidenceScore)
        if j.cometDisagreement is not None:
            by_pair[pair]["disagreement"].append(j.cometDisagreement)

    summary = []
    for pair, data in by_pair.items():
        n = len(data["adequacy"])
        summary.append({
            "languagePair": pair,
            "n": n,
            "avgAdequacy": round(_stats.mean(data["adequacy"]), 3) if n else None,
            "avgFluency": round(_stats.mean(data["fluency"]), 3) if n else None,
            "avgConfidence": round(_stats.mean(data["confidence"]), 3) if n else None,
            "avgCometDisagreement": (
                round(_stats.mean(data["disagreement"]), 3)
                if data["disagreement"] else None
            ),
            "highDisagreementCount": sum(1 for d in data["disagreement"] if d > 0.25),
        })

    summary.sort(key=lambda x: x["avgCometDisagreement"] or 0, reverse=True)
    return {"languagePairs": summary, "totalJudgments": len(judgments)}


# ---------------------------------------------------------------------------
# Style guide constraint scoring
# ---------------------------------------------------------------------------

class ConstraintEvalRequest(BaseModel):
    styleGuideId: str


@router.post("/evaluate-constraint-score/{translation_string_id}")
async def evaluate_constraint_score(
    translation_string_id: str,
    body: ConstraintEvalRequest,
    judge=Depends(get_llm_judge_service),
):
    """Score a translation string against a StyleGuide's constraint set.

    Writes constraintScore and styleGuideId back to the LLMJudgment row
    (creates one if none exists yet).
    """
    if not judge.available:
        raise HTTPException(status_code=503, detail="LLM judge not available — check GEMINI_API_KEY.")

    if not prisma.is_connected():
        await prisma.connect()

    ts = await prisma.translationstring.find_unique(
        where={"id": translation_string_id},
        include={"translationRequest": True},
    )
    if not ts:
        raise HTTPException(status_code=404, detail="Translation string not found.")

    guide = await prisma.styleguide.find_unique(
        where={"id": body.styleGuideId},
        include={"terms": True},
    )
    if not guide:
        raise HTTPException(status_code=404, detail="Style guide not found.")

    source_lang = (
        str(ts.translationRequest.sourceLanguage).lower()
        if ts.translationRequest else "en"
    )
    target_lang = ts.targetLanguage.lower()

    scores = await judge.evaluate_constraint_score(
        source=ts.sourceText,
        hypothesis=ts.translatedText,
        source_lang=source_lang,
        target_lang=target_lang,
        style_guide=guide,
    )

    existing = await prisma.llmjudgment.find_first(
        where={"translationStringId": translation_string_id, "engineName": None}
    )
    if existing:
        await prisma.llmjudgment.update(
            where={"id": existing.id},
            data={
                "constraintScore": scores["constraint_score"],
                "styleGuideId": body.styleGuideId,
                "rationale": scores["rationale"],
            },
        )
    else:
        await prisma.llmjudgment.create(
            data={
                "translationStringId": translation_string_id,
                "judgeModel": judge.model,
                "adequacyScore": 0.0,
                "fluencyScore": 0.0,
                "confidenceScore": 0.0,
                "constraintScore": scores["constraint_score"],
                "styleGuideId": body.styleGuideId,
                "rationale": scores["rationale"],
            }
        )

    return {
        "translationStringId": translation_string_id,
        "styleGuideId": body.styleGuideId,
        "styleGuideName": guide.name,
        "constraintScore": scores["constraint_score"],
        "requiredTermsHit": scores["required_terms_hit"],
        "forbiddenTermsFound": scores["forbidden_terms_found"],
        "rationale": scores["rationale"],
    }