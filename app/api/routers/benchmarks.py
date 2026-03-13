# app/api/routers/benchmarks.py
"""Regression test harness for MT quality.

POST /api/benchmarks/snapshot
    Aggregate QualityMetrics for a WMT benchmark request into EvalSnapshot rows
    (one per engine + one aggregated). Call after running calculate-all-approved
    on a WMT request.

GET /api/benchmarks/snapshots
    List all snapshots, optionally filtered by language_pair or engine_name.

GET /api/benchmarks/regression-report
    Diff the two most recent snapshots per (language_pair, engine_name).
    Flags any metric that degraded past the configured threshold.
"""

import logging
import statistics
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.db.base import prisma

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/benchmarks", tags=["Benchmarks"])


# ---------------------------------------------------------------------------
# Snapshot creation
# ---------------------------------------------------------------------------

@router.post("/snapshot")
async def create_snapshot(
    request_id: str = Query(..., description="WMT benchmark TranslationRequest ID"),
    notes: Optional[str] = Query(None, description="Optional label, e.g. 'baseline'"),
):
    """Aggregate QualityMetrics for a WMT request into EvalSnapshot rows.

    Creates one snapshot row per engine that has metrics for this request, plus
    one aggregated row (engineName=None) across all engines.
    """
    if not prisma.is_connected():
        await prisma.connect()

    wmt_request = await prisma.translationrequest.find_unique(
        where={"id": request_id},
        include={"translationStrings": True},
    )
    if not wmt_request:
        raise HTTPException(status_code=404, detail="Translation request not found.")

    string_ids = [ts.id for ts in wmt_request.translationStrings]
    if not string_ids:
        raise HTTPException(status_code=400, detail="No translation strings found for this request.")

    metrics = await prisma.qualitymetrics.find_many(
        where={"translationStringId": {"in": string_ids}},
    )
    if not metrics:
        raise HTTPException(
            status_code=400,
            detail="No QualityMetrics found. Run calculate-all-approved first.",
        )

    language_pair = wmt_request.languagePair

    # Group metrics by engineName
    by_engine: dict[Optional[str], list] = {}
    for m in metrics:
        key = m.engineName  # may be None
        by_engine.setdefault(key, []).append(m)

    created_snapshots = []

    def _avg(vals: list) -> Optional[float]:
        clean = [v for v in vals if v is not None]
        return round(statistics.mean(clean), 4) if clean else None

    # One snapshot per engine
    for engine_name, engine_metrics in by_engine.items():
        snap = await prisma.evalsnapshot.create(
            data={
                "requestId": request_id,
                "languagePair": language_pair,
                "engineName": engine_name,
                "avgBleu": _avg([m.bleuScore for m in engine_metrics]),
                "avgComet": _avg([m.cometScore for m in engine_metrics]),
                "avgChrf": _avg([m.chrfScore for m in engine_metrics]),
                "avgTer": _avg([m.terScore for m in engine_metrics]),
                "segmentCount": len(engine_metrics),
                "notes": notes,
            }
        )
        created_snapshots.append({
            "id": snap.id,
            "engineName": engine_name,
            "segmentCount": snap.segmentCount,
            "avgBleu": snap.avgBleu,
            "avgComet": snap.avgComet,
            "avgChrf": snap.avgChrf,
            "avgTer": snap.avgTer,
        })

    # One aggregated snapshot across all engines (engineName=None handled separately
    # only if there are multiple engines — avoids a duplicate if already there)
    if len(by_engine) > 1:
        snap = await prisma.evalsnapshot.create(
            data={
                "requestId": request_id,
                "languagePair": language_pair,
                "engineName": None,
                "avgBleu": _avg([m.bleuScore for m in metrics]),
                "avgComet": _avg([m.cometScore for m in metrics]),
                "avgChrf": _avg([m.chrfScore for m in metrics]),
                "avgTer": _avg([m.terScore for m in metrics]),
                "segmentCount": len(metrics),
                "notes": f"{notes} (aggregated)" if notes else "aggregated",
            }
        )
        created_snapshots.append({
            "id": snap.id,
            "engineName": None,
            "segmentCount": snap.segmentCount,
            "avgBleu": snap.avgBleu,
            "avgComet": snap.avgComet,
            "avgChrf": snap.avgChrf,
            "avgTer": snap.avgTer,
        })

    logger.info(
        f"Snapshot created for request={request_id} language_pair={language_pair}: "
        f"{len(created_snapshots)} rows"
    )
    return {
        "success": True,
        "requestId": request_id,
        "languagePair": language_pair,
        "snapshots": created_snapshots,
    }


# ---------------------------------------------------------------------------
# Snapshot listing
# ---------------------------------------------------------------------------

@router.get("/snapshots")
async def list_snapshots(
    language_pair: Optional[str] = Query(None),
    engine_name: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """List EvalSnapshots, newest first."""
    if not prisma.is_connected():
        await prisma.connect()

    where: dict = {}
    if language_pair:
        where["languagePair"] = language_pair
    if engine_name:
        where["engineName"] = engine_name

    snaps = await prisma.evalsnapshot.find_many(
        where=where,
        order={"runDate": "desc"},
        take=limit,
    )
    return {"count": len(snaps), "snapshots": snaps}


# ---------------------------------------------------------------------------
# Regression report
# ---------------------------------------------------------------------------

@router.get("/regression-report")
async def regression_report(
    language_pair: Optional[str] = Query(None, description="Filter to one language pair"),
    engine_name: Optional[str] = Query(None, description="Filter to one engine"),
    threshold_bleu: float = Query(2.0, description="BLEU drop (points) that counts as a regression"),
    threshold_comet: float = Query(0.02, description="COMET drop that counts as a regression"),
    threshold_chrf: float = Query(2.0, description="ChrF drop (points) that counts as a regression"),
    threshold_ter: float = Query(2.0, description="TER increase (points) that counts as a regression"),
):
    """Diff the two most recent snapshots per (language_pair, engine_name).

    A regression is flagged when a metric drops (or rises, for TER) past the
    configured threshold between the previous snapshot and the latest snapshot.
    """
    if not prisma.is_connected():
        await prisma.connect()

    where: dict = {}
    if language_pair:
        where["languagePair"] = language_pair
    if engine_name:
        where["engineName"] = engine_name

    all_snaps = await prisma.evalsnapshot.find_many(
        where=where,
        order={"runDate": "desc"},
    )

    # Group by (languagePair, engineName), keep last 2 per group
    groups: dict[tuple, list] = {}
    for s in all_snaps:
        key = (s.languagePair, s.engineName)
        groups.setdefault(key, []).append(s)

    report = []
    for (lp, eng), snaps in groups.items():
        if len(snaps) < 2:
            report.append({
                "languagePair": lp,
                "engineName": eng,
                "status": "insufficient_data",
                "message": "Only one snapshot — need a second run to detect regressions.",
                "latest": _snap_dict(snaps[0]),
                "previous": None,
                "deltas": None,
                "regressions": [],
            })
            continue

        latest = snaps[0]   # newest (index 0 because sorted desc)
        previous = snaps[1]

        deltas = {
            "bleu": _delta(latest.avgBleu, previous.avgBleu),
            "comet": _delta(latest.avgComet, previous.avgComet),
            "chrf": _delta(latest.avgChrf, previous.avgChrf),
            "ter": _delta(latest.avgTer, previous.avgTer),
        }

        regressions = []
        if deltas["bleu"] is not None and deltas["bleu"] < -threshold_bleu:
            regressions.append({"metric": "BLEU", "delta": deltas["bleu"], "threshold": -threshold_bleu})
        if deltas["comet"] is not None and deltas["comet"] < -threshold_comet:
            regressions.append({"metric": "COMET", "delta": deltas["comet"], "threshold": -threshold_comet})
        if deltas["chrf"] is not None and deltas["chrf"] < -threshold_chrf:
            regressions.append({"metric": "ChrF", "delta": deltas["chrf"], "threshold": -threshold_chrf})
        # TER: lower is better, so an increase is a regression
        if deltas["ter"] is not None and deltas["ter"] > threshold_ter:
            regressions.append({"metric": "TER", "delta": deltas["ter"], "threshold": threshold_ter})

        report.append({
            "languagePair": lp,
            "engineName": eng,
            "status": "regression" if regressions else "ok",
            "latest": _snap_dict(latest),
            "previous": _snap_dict(previous),
            "deltas": deltas,
            "regressions": regressions,
        })

    report.sort(key=lambda x: (0 if x["status"] == "regression" else 1, x["languagePair"] or ""))
    regression_count = sum(1 for r in report if r["status"] == "regression")

    return {
        "regressionCount": regression_count,
        "pairCount": len(report),
        "thresholds": {
            "bleu": threshold_bleu,
            "comet": threshold_comet,
            "chrf": threshold_chrf,
            "ter": threshold_ter,
        },
        "report": report,
    }


def _delta(latest: Optional[float], previous: Optional[float]) -> Optional[float]:
    if latest is None or previous is None:
        return None
    return round(latest - previous, 4)


def _snap_dict(s) -> dict:
    return {
        "id": s.id,
        "runDate": s.runDate.isoformat(),
        "notes": s.notes,
        "segmentCount": s.segmentCount,
        "avgBleu": s.avgBleu,
        "avgComet": s.avgComet,
        "avgChrf": s.avgChrf,
        "avgTer": s.avgTer,
    }
