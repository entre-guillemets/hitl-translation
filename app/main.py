from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import traceback
import os

from app.services.model_manager import model_manager
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
from app.services.health_service import HealthService
from app.services.multimodal_service import multimodal_service as multimodal_service_instance
from app.services.transcreation_service import TranscreationService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


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
    # Load COMET model using ModelManager
    comet_model = None
    try:
        logger.info("Loading COMET model...")

        import time
        start_time = time.time()

        logger.info("Step 1: Getting model path from ModelManager...")
        comet_model_path = model_manager.get_model_path("comet")
        path_time = time.time()
        logger.info(f"Step 1 completed in {path_time - start_time:.2f} seconds")
        logger.info(f"COMET model path: {comet_model_path}")

        logger.info("Step 2: Loading COMET model...")
        load_start = time.time()

        try:
            from comet import load_from_checkpoint, download_model

            logger.info("Downloading/loading COMET model from Unbabel...")
            model_path = download_model("Unbabel/wmt20-comet-da")
            comet_model = load_from_checkpoint(model_path)
            comet_model.eval()
            logger.info("✓ COMET model loaded from Unbabel download")
            load_time = time.time()
        except Exception as e:
            logger.warning(f"Failed to download Unbabel model: {e}")
            # Fallback to local path if available
            if comet_model_path:
                logger.info("Attempting to load from local checkpoint...")
                comet_model = load_from_checkpoint(comet_model_path)
                logger.info("✓ COMET model loaded from local checkpoint")
                load_time = time.time()
            else:
                logger.error("❌ No COMET model available (neither download nor local path worked)")
                comet_model = None
                load_time = time.time()

        logger.info(f"Step 2 completed in {load_time - load_start:.2f} seconds")

        if comet_model:
            logger.info(f"✓ COMET model loaded successfully: {type(comet_model)}")
            logger.info("✓ COMET model will be used (skipping validation test)")
        else:
            logger.warning("❌ COMET model is None")

    except Exception as e:
        logger.error(f"❌ Failed to load COMET model: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        comet_model = None

    app.state.comet_model = comet_model

    if comet_model:
        logger.info("✓ COMET model stored on app.state")
    else:
        logger.warning("❌ COMET model not available - quality assessment will be disabled")

    # Load COMETKiwi QE model for reference-free quality prediction.
    # wmt22-cometkiwi-da is gated on HuggingFace and requires access approval; we use
    # wmt20-comet-qe-da which is freely available and runs efficiently on CPU/Apple Silicon.
    # Both are reference-free QE models from the COMET family.
    cometkiwi_model = None
    try:
        logger.info("Loading COMETKiwi (wmt20-comet-qe-da) for reference-free quality estimation...")
        from comet import load_from_checkpoint, download_model
        cometkiwi_path = download_model("Unbabel/wmt20-comet-qe-da")
        cometkiwi_model = load_from_checkpoint(cometkiwi_path)
        cometkiwi_model.eval()
        logger.info("✓ COMETKiwi model (wmt20-comet-qe-da) loaded successfully")
    except Exception as e:
        logger.error(f"❌ COMETKiwi initialization failed: {e}")
        cometkiwi_model = None

    app.state.cometkiwi_model = cometkiwi_model

    # Initialize FuzzyMatchingService
    fuzzy_matcher = FuzzyMatchingService(prisma=prisma)
    app.state.fuzzy_matcher = fuzzy_matcher

    # Initialize TranscreationService (file-based, non-blocking if API key absent)
    transcreation_service = TranscreationService()
    app.state.transcreation_service = transcreation_service

    # Initialize MultiEngineService (pass transcreation so it can register the Claude engine)
    multi_engine_service = CleanMultiEngineService(
        translation_service_instance=translation_service,
        transcreation_service=transcreation_service,
    )
    app.state.multi_engine_service = multi_engine_service

    # Initialize and set HealthService
    health_service = HealthService()
    health_service.set_services(cometkiwi_model, multi_engine_service)
    app.state.health_service = health_service

    # --- New Multimodal Service Initialization ---
    logger.info("Initializing Multimodal Service...")
    app.state.multimodal_service = multimodal_service_instance
    logger.info("✓ Multimodal Service initialized and stored on app.state.")
    # --- End New Multimodal Service Initialization ---

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