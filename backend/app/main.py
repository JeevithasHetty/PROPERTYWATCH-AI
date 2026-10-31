import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import engine, Base, sync_database_schema
from app.seed_data import seed_database
from app.services.ai_models_service import init_ai_model_registry
from app.services.policy_rules_engine import init_policy_rules_in_db
from app.routers import (
    auth, properties, geocoding, satellite, analysis,
    modifications, evidence, authenticity, reviews, reports,
    settings as settings_router, audit,
    policies, claims, evaluations, decisions, declarations, models_registry, monitoring
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("propertywatch")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables and columns exist and seed initial demo data
    logger.info("Initializing PropertyWatch AI database schema and models...")
    sync_database_schema()
    try:
        init_ai_model_registry()
        init_policy_rules_in_db()
        seed_database()
        logger.info("Database and AI services initialization completed successfully.")
    except Exception as e:
        logger.error(f"Error during application startup initialization: {e}")
    from app.services.monitoring_service import start_scheduler, stop_scheduler
    start_scheduler()
    yield
    stop_scheduler()
    # Shutdown
    logger.info("PropertyWatch AI backend shutting down.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "PropertyWatch AI: An AI-Powered Full-Stack Web Application for Property Modification Monitoring, "
        "Evidence Verification, Insurance Policy Rule Evaluation, and Claim Assistance Workflow."
    ),
    lifespan=lifespan
)

# Enable CORS for frontend development & local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Satellite imagery and derived heatmaps are served separately from uploaded
# policy documents and user evidence, which remain private behind API routes.
app.mount("/static/heatmaps", StaticFiles(directory=str(settings.HEATMAPS_DIR)), name="heatmaps")


@app.get("/static/snapshots/{filename}", include_in_schema=False)
def get_public_snapshot(filename: str):
    if Path(filename).name != filename or filename.startswith("baseline_"):
        raise HTTPException(status_code=404, detail="Snapshot not found.")
    image_path = settings.SNAPSHOTS_DIR / filename
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found.")
    return FileResponse(path=str(image_path))

# Register API routers with common prefix /api
api_prefix = settings.API_PREFIX

app.include_router(auth.router, prefix=api_prefix)
app.include_router(properties.router, prefix=api_prefix)
app.include_router(geocoding.router, prefix=api_prefix)
app.include_router(satellite.router, prefix=api_prefix)
app.include_router(analysis.router, prefix=api_prefix)
app.include_router(modifications.router, prefix=api_prefix)
app.include_router(evidence.router, prefix=api_prefix)
app.include_router(authenticity.router, prefix=api_prefix)
app.include_router(reviews.router, prefix=api_prefix)
app.include_router(reports.router, prefix=api_prefix)
app.include_router(settings_router.router, prefix=api_prefix)
app.include_router(audit.router, prefix=api_prefix)

# Workflow extension routers
app.include_router(policies.router, prefix=api_prefix)
app.include_router(claims.router, prefix=api_prefix)
app.include_router(evaluations.router, prefix=api_prefix)
app.include_router(decisions.router, prefix=api_prefix)
app.include_router(declarations.router, prefix=api_prefix)
app.include_router(models_registry.router, prefix=api_prefix)
app.include_router(monitoring.router, prefix=api_prefix)

@app.get("/")
def root():
    return {
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "Online",
        "docs_url": "/docs",
        "demo_mode": settings.DEMO_MODE,
        "notice": "Property Intelligence & Insurance Claim Assistance Platform"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
