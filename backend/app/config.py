import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

# Base directory for backend
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

# Load .env if present
load_dotenv(ROOT_DIR / ".env")

class Settings:
    PROJECT_NAME: str = "PropertyWatch AI"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    # External APIs & Mode
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")) # 24 hours
    CORS_ORIGINS: list = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173"
        ).split(",")
        if origin.strip()
    ]
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'propertywatch.db'}")
    
    # Storage Paths
    STORAGE_DIR: Path = BASE_DIR / "storage"
    UPLOADS_DIR: Path = STORAGE_DIR / "uploads"
    SNAPSHOTS_DIR: Path = STORAGE_DIR / "snapshots"
    HEATMAPS_DIR: Path = STORAGE_DIR / "heatmaps"
    REPORTS_DIR: Path = STORAGE_DIR / "reports"
    
    # Google Earth Engine (GEE)
    GEE_PROJECT_ID: str = os.getenv("GEE_PROJECT_ID", "youtube-1-476010")
    GEE_PROJECT_NUMBER: str = os.getenv("GEE_PROJECT_NUMBER", "741309446381")
    GEE_PROJECT_NAME: str = os.getenv("GEE_PROJECT_NAME", "youtube-1")
    GEE_SERVICE_ACCOUNT_KEY: str = os.getenv("GEE_SERVICE_ACCOUNT_KEY", "")

    # Copernicus / Sentinel Hub
    COPERNICUS_CLIENT_ID: str = os.getenv("COPERNICUS_CLIENT_ID", "")
    COPERNICUS_CLIENT_SECRET: str = os.getenv("COPERNICUS_CLIENT_SECRET", "")
    SENTINEL_INSTANCE_ID: str = os.getenv("SENTINEL_INSTANCE_ID", "")
    
    # Geocoding
    NOMINATIM_USER_AGENT: str = os.getenv("NOMINATIM_USER_AGENT", "PropertyWatchAI-App/1.0 (info@propertywatch.local)")
    
    # AI Authenticity Detection Provider
    AUTHENTICITY_API_URL: str = os.getenv("AUTHENTICITY_API_URL", "")
    AUTHENTICITY_API_KEY: str = os.getenv("AUTHENTICITY_API_KEY", "")
    
    # LLM Evidence Summarizer
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_API_URL: str = os.getenv("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

settings = Settings()
if not settings.SECRET_KEY:
    if not settings.DEMO_MODE:
        raise RuntimeError("SECRET_KEY must be configured when DEMO_MODE is disabled.")
    settings.SECRET_KEY = secrets.token_urlsafe(48)

# Ensure directories exist
for path in [settings.STORAGE_DIR, settings.UPLOADS_DIR, settings.SNAPSHOTS_DIR, settings.HEATMAPS_DIR, settings.REPORTS_DIR]:
    path.mkdir(parents=True, exist_ok=True)
