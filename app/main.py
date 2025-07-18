from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import traceback
import os

from app.services.model_manager import model_manager
from comet import load_from_checkpoint
from app.core.config import settings
from app.db.base import initialize_database, cleanup_database, prisma

from app.api.routers import (
    translation_requests,
    data_management,
    wmt_benchmarks,
    quality_assessment,
    debugging,
    health,
    analytics
)

from app.services.fuzzy_matching_service import FuzzyMatchingService
from app.services.multi_engine_service import CleanMultiEngineService
from app.services.translation_service import translation_service
from app.services.metricx_service import MetricXService
from app.services.health_service import HealthService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Global variables for models and services
comet_model = None
metricx_service = None
fuzzy_matcher = None
multi_engine_service = None
health_service = None

# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    swagger_ui_parameters={"operationsSorter": "method"}
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Include routers
app.include_router(health.router)
app.include_router(translation_requests.router)
app.include_router(data_management.router)
app.include_router(wmt_benchmarks.router)
app.include_router(quality_assessment.router)
app.include_router(debugging.router)
app.include_router(analytics.router)
app.include_router(analytics.router, prefix="/api")

# Database startup/shutdown events
@app.on_event("startup")
async def startup():
    await initialize_database()

@app.on_event("startup")
async def startup_event():
    global metricx_service, comet_model, fuzzy_matcher, multi_engine_service, health_service

    # Load COMET model using ModelManager
    try:
        logger.info("Loading COMET model...")
        
        # Add detailed logging
        import time
        start_time = time.time()
        
        logger.info("Step 1: Getting model path from ModelManager...")
        comet_model_path = model_manager.get_model_path("comet")
        path_time = time.time()
        logger.info(f"Step 1 completed in {path_time - start_time:.2f} seconds")
        logger.info(f"COMET model path: {comet_model_path}")

        if comet_model_path:
            logger.info("Step 2: Loading model from checkpoint...")
            load_start = time.time()
            comet_model = load_from_checkpoint(comet_model_path)
            load_time = time.time()
            logger.info(f"Step 2 completed in {load_time - load_start:.2f} seconds")
            
            logger.info(f"✓ COMET model loaded successfully: {type(comet_model)}")
            logger.info(f"Total COMET loading time: {load_time - start_time:.2f} seconds")
        else:
            logger.warning("COMET model path not found")
            comet_model = None
            
    except Exception as e:
        logger.error(f"❌ Failed to load COMET model: {e}")
        comet_model = None

    if comet_model:
        from app.api.routers.quality_assessment import set_comet_model
        set_comet_model(comet_model)
        
        from app.api.routers.debugging import set_comet_model as set_debug_comet_model
        set_debug_comet_model(comet_model)
        
        logger.info("✓ COMET model passed to quality assessment and debugging routers")
    else:
        logger.warning("❌ COMET model not available - quality assessment will be disabled")

    # MetricX will be None, but we still pass it to HealthService
    try:
        logger.info("MetricX loading disabled - using COMET for quality assessment")
        metricx_service = MetricXService() # Instantiate it even if it won't load models, so it can be passed.
    except Exception as e:
        logger.error(f"❌ MetricX initialization failed: {e}")
        metricx_service = None # Ensure it's None if init fails

    # Initialize FuzzyMatchingService
    fuzzy_matcher = FuzzyMatchingService(prisma=prisma)
    from app.api.routers.translation_requests import set_fuzzy_matcher
    set_fuzzy_matcher(fuzzy_matcher)

    # Initialize MultiEngineService
    multi_engine_service = CleanMultiEngineService(translation_service_instance=translation_service)
    from app.api.routers.translation_requests import set_multi_engine_service
    set_multi_engine_service(multi_engine_service)

    from app.api.routers.wmt_benchmarks import set_multi_engine_service as set_wmt_multi_engine_service
    set_wmt_multi_engine_service(multi_engine_service)

    from app.api.routers.debugging import set_multi_engine_service as set_debug_multi_engine_service
    set_debug_multi_engine_service(multi_engine_service)

    # Pass MetricX service to relevant routers
    from app.api.routers.quality_assessment import set_metricx_service
    set_metricx_service(metricx_service)

    from app.api.routers.debugging import set_metricx_service as set_debug_metricx_service
    set_debug_metricx_service(metricx_service)

    # NEW: Initialize and set HealthService
    health_service = HealthService()
    health_service.set_services(metricx_service, multi_engine_service) # Pass other services to HealthService

    # Pass HealthService to relevant routers
    from app.api.routers.health import set_health_service as set_health_router_service
    set_health_router_service(health_service) # Pass to health router so it can use the shared service

    from app.api.routers.analytics import set_health_service as set_analytics_health_service
    set_analytics_health_service(health_service) # Pass to analytics router

    logger.info("Model and service loading complete")

@app.on_event("shutdown")
async def shutdown():
    await cleanup_database()

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to catch all unhandled exceptions"""
    # Log the full error with traceback
    logger.error(f"Global exception handler caught: {exc}")
    logger.error(f"Request: {request.method} {request.url}")
    logger.error(f"Traceback: {traceback.format_exc()}")

    # Handle specific exception types
    if "prisma" in str(exc).lower() or "database" in str(exc).lower():
        return JSONResponse(
            status_code=500,
            content={
                "error": "Database operation failed",
                "detail": "A database error occurred. Please try again later.",
                "type": "database_error"
            }
        )

    # Handle Prisma connection errors
    if "not connected" in str(exc).lower():
        return JSONResponse(
            status_code=503,
            content={
                "error": "Service temporarily unavailable",
                "detail": "Database connection issue. Please try again later.",
                "type": "connection_error"
            }
        )

    # Handle enum/validation errors
    if "enum" in str(exc).lower() or "AttributeError" in str(type(exc).__name__):
        return JSONResponse(
            status_code=400,
            content={
                "error": "Invalid data",
                "detail": "The provided data contains invalid values.",
                "type": "validation_error"
            }
        )

    # Generic error for everything else
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred. Please try again later.",
            "type": "server_error"
        }
    )

@app.get("/")
async def root():
    return {"message": "Translation Management API is running", "status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
