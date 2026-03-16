# app/api/routers/admin.py
"""Administrative endpoints — destructive operations, benchmark resets, etc.

POST /api/admin/reset
    Wipe all transactional data from the database and return to a clean state.
    Preserves only LocalModel and SystemConfig rows.
    Intended for benchmark experiment setup, not production use.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.db.base import prisma

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.post("/reset")
async def reset_all_data():
    """Delete all transactional data, returning the database to a clean state.

    Deletion order respects FK constraints. Cascade relations handle child rows
    automatically where defined; non-cascade children are deleted explicitly first.

    Preserved: LocalModel, SystemConfig (configuration, not transactional data).
    """
    if not prisma.is_connected():
        await prisma.connect()

    counts: dict[str, int] = {}

    try:
        # ── 1. Non-cascade children of TranslationString ──────────────────────
        r = await prisma.enginepreference.delete_many()
        counts["engine_preferences"] = r

        r = await prisma.modeloutput.delete_many()
        counts["model_outputs"] = r

        # ── 2. QualityMetrics (FK to both TranslationString and TranslationRequest) ─
        r = await prisma.qualitymetrics.delete_many()
        counts["quality_metrics"] = r

        # ── 3. HumanFeedback (independent) ────────────────────────────────────
        r = await prisma.humanfeedback.delete_many()
        counts["human_feedback"] = r

        # ── 4. EvalSnapshot (independent) ─────────────────────────────────────
        r = await prisma.evalsnapshot.delete_many()
        counts["eval_snapshots"] = r

        # ── 5. TranslationRequests (cascades → TranslationStrings →
        #        Annotations, LLMJudgments) ────────────────────────────────────
        r = await prisma.translationrequest.delete_many()
        counts["translation_requests"] = r

        # ── 6. SegmentationSessions (now safe — FK on requests is gone) ────────
        r = await prisma.segmentationsession.delete_many()
        counts["segmentation_sessions"] = r

        # ── 7. Linguistic resources ────────────────────────────────────────────
        r = await prisma.translationmemory.delete_many()
        counts["translation_memory"] = r

        r = await prisma.glossaryterm.delete_many()
        counts["glossary_terms"] = r

        r = await prisma.donotranslateitem.delete_many()
        counts["do_not_translate_items"] = r

        r = await prisma.offensiveword.delete_many()
        counts["offensive_words"] = r

        # ── 8. WMT legacy benchmark records (best-effort — table may not exist) ─
        try:
            r = await prisma.wmtbenchmark.delete_many()
            counts["wmt_benchmarks"] = r
        except Exception:
            counts["wmt_benchmarks"] = 0  # table absent from current schema

        # ── 9. LocalModel usage counters (reset counts but keep rows) ──────────
        await prisma.localmodel.update_many(
            data={"totalTranslations": 0, "lastUsed": None}
        )
        counts["local_models_reset"] = "counters cleared"

    except Exception as exc:
        logger.error(f"Reset failed mid-run: {exc}")
        raise HTTPException(status_code=500, detail=f"Reset failed: {exc}")

    total_rows = sum(v for v in counts.values() if isinstance(v, int))
    logger.info(f"Database reset complete — {total_rows} rows deleted")

    return {
        "success": True,
        "message": f"Database reset complete. {total_rows} rows deleted.",
        "deleted": counts,
    }
