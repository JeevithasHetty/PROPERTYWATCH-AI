import datetime
import requests
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.config import settings
from app.schemas import ServiceStatusOut
from app.auth import get_current_user, require_roles
from app.models import User, PolicyRule, AIModelRegistry
from app.services.satellite_service import satellite_service
from app.services.monitoring_service import scheduler_status


def _probe_nominatim() -> str:
    try:
        r = requests.get(settings.NOMINATIM_URL.replace('/search', '/status.php'), timeout=6,
                         headers={'User-Agent': settings.NOMINATIM_USER_AGENT})
        return 'ok' if r.status_code == 200 else f'HTTP {r.status_code}'
    except requests.RequestException as exc:
        return exc.__class__.__name__


router = APIRouter(prefix="/settings", tags=["Settings & System Status"])

@router.get("/status", response_model=ServiceStatusOut)
def get_service_status(
    probe: bool = Query(False, description="Actively test external services (slower)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check operational status and configuration of external APIs, AI engines, and database.
    Never exposes plaintext secrets or tokens.
    """
    # 1. Database check
    db_ok = True
    table_count = 0
    try:
        res = db.execute(text("SELECT count(*) FROM sqlite_master WHERE type='table'")).scalar()
        table_count = int(res)
    except Exception:
        db_ok = False

    # 2. Geocoding Status (OpenStreetMap Nominatim, India only)
    geocoding_status = {
        "provider": "OpenStreetMap Nominatim",
        "status": "CONFIGURED",
        "countrycodes": settings.DEFAULT_COUNTRY_CODE,
        "rate_limit_compliance": "1 req/sec with identifying User-Agent",
        "user_agent_is_default": "propertywatch.local" in settings.NOMINATIM_USER_AGENT,
        "caching_active": True,
        "map_engine": "Leaflet with OpenStreetMap tiles (c) OpenStreetMap contributors",
        "mode": "Live OSM API" + (" (offline Indian city fallback in demo mode)" if settings.DEMO_MODE else ""),
        "probe": None,
    }
    if probe:
        geocoding_status["probe"] = _probe_nominatim()
        geocoding_status["status"] = "OPERATIONAL" if geocoding_status["probe"] == "ok" else "UNREACHABLE"

    # 3. Satellite status: reflects real credentials, never a hard-coded claim
    sat = satellite_service.status()
    if sat["active_provider"]:
        sat_label = f"CONFIGURED ({sat['active_provider']})"
    elif settings.DEMO_MODE:
        sat_label = "DEMO ONLY (synthetic imagery; no live provider configured)"
    else:
        sat_label = "NOT CONFIGURED (live mode: retrieval disabled)"
    satellite_status = {
        "provider": "Copernicus Data Space / Google Earth Engine (Sentinel-2)",
        "status": sat_label,
        "active_provider": sat["active_provider"],
        "copernicus_configured": sat["copernicus_configured"],
        "gee_configured": sat["gee_configured"],
        "gee_missing": sat["gee_missing"],
        "dataset": "sentinel-2-l2a / COPERNICUS/S2_SR_HARMONIZED",
        "resolution": "10 m per pixel (small rooftop objects are not resolvable)",
        "synthetic_imagery_possible": sat["synthetic_imagery_possible"],
        "probe": None,
    }
    if probe and sat["copernicus_configured"]:
        try:
            satellite_service.copernicus.token()
            satellite_status["probe"] = "copernicus authentication ok"
        except Exception as exc:  # noqa: BLE001
            satellite_status["probe"] = f"copernicus authentication FAILED: {exc}"

    # 4. Deepfake Detection & Authenticity Forensics Status
    authenticity_status = {
        "engine": "PropertyWatch Spectral-ELA Deepfake & Tampering Forensics Engine",
        "status": "OPERATIONAL",
        "deepfake_detection_active": True,
        "spectral_fft_analysis": "Active (SciPy 2D FFT & DCT Lattice Detection)",
        "error_level_analysis": "Active (Pillow ELA 90% Compression)",
        "noise_print_variance": "Active (PRNU High-Pass Residuals)",
        "metadata_ai_markers": "Active (Scanning for Stable Diffusion, Midjourney, DALL-E, ComfyUI)",
        "forensic_heatmaps": "Automated Overlay Generation Enabled"
    }

    # 5. LLM Service Status
    has_llm_key = bool(settings.LLM_API_KEY)
    llm_status = {
        "engine": f"LLM Summarizer ({settings.LLM_MODEL})" if has_llm_key else "Deterministic Case Summarizer",
        "status": "CONFIGURED (LIVE)" if has_llm_key else "LOCAL DETERMINISTIC ENGINE",
        "external_api_configured": has_llm_key,
        "purpose": "Evidence aggregation and chronological summaries only (no automated decisions)"
    }

    # 6. Policy rules engine (counts come from the database)
    active_rules = db.query(PolicyRule).filter(PolicyRule.is_active == True).count()  # noqa: E712
    policy_rules_status = {
        "engine": "Deterministic policy rules engine",
        "status": "OPERATIONAL",
        "rules_catalogue": "docs/policy_rules_catalogue.md",
        "active_rules_count": active_rules,
        "supported_outcomes": ["PASS", "ALERT_CREATED", "MORE_EVIDENCE_REQUIRED", "PENDING_REVIEW", "INCONCLUSIVE", "SYSTEM_ERROR"],
        "auto_approval_permitted": False,
        "mode": "Verified-terms only; unverified terms yield PENDING_REVIEW",
    }

    # 7. AI models: availability is read from the registry, which checks real weight files
    models = db.query(AIModelRegistry).all()
    models_registry_status = {
        "engine": "AI model registry (ONNX Runtime)",
        "status": "OPERATIONAL" if all(m.is_available for m in models) else "PARTIAL",
        "registered_models": [m.model_key for m in models],
        "available_models": [m.model_key for m in models if m.is_available],
        "unavailable_models": {m.model_key: m.provider for m in models if not m.is_available},
        "fabrication_policy": "Strict (no prediction is generated when weights are missing)",
    }

    return {
        "geocoding": geocoding_status,
        "satellite_service": satellite_status,
        "authenticity_service": authenticity_status,
        "llm_service": llm_status,
        "policy_rules_engine": policy_rules_status,
        "ai_models_registry": models_registry_status,
        "database": {
            "status": "CONNECTED" if db_ok else "ERROR",
            "type": "SQLite (Persistent)",
            "tables_initialized": table_count
        },
        "monitoring": scheduler_status(),
        "demo_mode": settings.DEMO_MODE,
        "last_checked": datetime.datetime.utcnow()
    }

@router.post("/toggle-demo")
def toggle_demo_mode(
    current_user: User = Depends(require_roles(["admin"]))
):
    """Toggle between Live API and Demo Mode without rewriting database records."""
    settings.DEMO_MODE = not settings.DEMO_MODE
    return {
        "message": f"Demo mode successfully set to: {settings.DEMO_MODE}",
        "demo_mode": settings.DEMO_MODE
    }
