# app/api/routers/health.py

from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime
import psutil
import torch
from app.db.base import prisma
from app.dependencies import get_health_service

router = APIRouter(prefix="/api/health", tags=["Health"])

@router.get("/")
async def health_check(health_service=Depends(get_health_service)):
    """Basic health check using the HealthService."""
    detailed_status = await health_service.get_detailed_status()
    return {
        "status": detailed_status.get("status", "unknown"),
        "timestamp": detailed_status.get("timestamp", datetime.now().isoformat()),
        "service": "Translation Management API"
    }

@router.get("/engines", tags=["Health"])
async def list_engines(request: Request):
    """Return all configured translation engines with their display names.

    Used by the frontend to populate the model filter dropdown even before
    any translations have been scored (i.e., before the leaderboard has data).
    """
    service = getattr(request.app.state, "multi_engine_service", None)
    if not service:
        return {"engines": []}
    engines = [
        {
            "id": engine_id,
            "name": config.get("name", engine_id),
            "supportedPairs": config.get("supported_pairs", []),
            "type": config.get("type", "unknown"),
        }
        for engine_id, config in service.engine_configs.items()
    ]
    return {"engines": engines}


@router.get("/detailed")
async def detailed_health_check(health_service=Depends(get_health_service)):
    """Detailed health check with system info, now powered by HealthService."""
    try:
        return await health_service.get_detailed_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get detailed health: {str(e)}")