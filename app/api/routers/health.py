# app/api/routers/health.py

from fastapi import APIRouter, Depends, HTTPException
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

@router.get("/detailed")
async def detailed_health_check(health_service=Depends(get_health_service)):
    """Detailed health check with system info, now powered by HealthService."""
    try:
        return await health_service.get_detailed_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get detailed health: {str(e)}")