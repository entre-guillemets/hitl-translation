# app/api/routers/health.py

from fastapi import APIRouter, HTTPException
from datetime import datetime
import psutil
import torch
from app.db.base import prisma

health_service = None

def set_health_service(service):
    """Setter to inject the HealthService instance."""
    global health_service
    health_service = service

router = APIRouter(prefix="/api/health", tags=["Health"])

@router.get("/")
async def health_check():
    """Basic health check using the HealthService."""
    if health_service is None:
        raise HTTPException(status_code=503, detail="Health service not initialized.")
    
    detailed_status = await health_service.get_detailed_status()
    return {
        "status": detailed_status.get("status", "unknown"),
        "timestamp": detailed_status.get("timestamp", datetime.now().isoformat()),
        "service": "Translation Management API"
    }

@router.get("/detailed")
async def detailed_health_check():
    """Detailed health check with system info, now powered by HealthService."""
    if health_service is None:
        raise HTTPException(status_code=503, detail="Health service not initialized.")
    
    try:
        return await health_service.get_detailed_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get detailed health: {str(e)}")