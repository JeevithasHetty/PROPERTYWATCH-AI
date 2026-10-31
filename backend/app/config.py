import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

# Base directory for backend
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

# Load .env if present
load_dotenv(ROOT_DIR / ".env")
load_dotenv(ROOT_DIR.parent / ".env")

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
    
    # India localisation
    DEFAULT_CURRENCY: str = "INR"
    DEFAULT_COUNTRY_CODE: str = os.getenv("DEFAULT_COUNTRY_CODE", "in")
    # Geographic centre of India; used only when no property coordinates exist.
    DEFAULT_MAP_CENTER: tuple = (20.5937, 78.9629)
    DEFAULT_MAP_ZOOM: int = 5
    # Rough India bounding box (south, west, north, east) used to sanity-check geocoding results.
    INDIA_BBOX: tuple = (6.0, 68.0, 37.5, 97.5)

    # Satellite provider: "auto" (use whichever has credentials), "copernicus" or "gee"
    SATELLITE_PROVIDER: str = os.getenv("SATELLITE_PROVIDER", "auto").lower()
    SATELLITE_AOI_HALF_SIZE_M: int = int(os.getenv("SATELLITE_AOI_HALF_SIZE_M", "640"))
    SATELLITE_OUTPUT_PX: int = int(os.getenv("SATELLITE_OUTPUT_PX", "256"))
    HTTP_TIMEOUT_SECONDS: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "60"))

    # Google Earth Engine (GEE). No project defaults: supply your own.
    GEE_PROJECT_ID: str = os.getenv("GEE_PROJECT_ID", "")
    GEE_SERVICE_ACCOUNT_EMAIL: str = os.getenv("GEE_SERVICE_ACCOUNT_EMAIL", "")
    GEE_SERVICE_ACCOUNT_KEY: str = os.getenv("GEE_SERVICE_ACCOUNT_KEY", "")  # path to JSON key file

    # Copernicus Data Space Ecosystem (Sentinel Hub OAuth client)
    COPERNICUS_CLIENT_ID: str = os.getenv("COPERNICUS_CLIENT_ID", "")
    COPERNICUS_CLIENT_SECRET: str = os.getenv("COPERNICUS_CLIENT_SECRET", "")
    COPERNICUS_TOKEN_URL: str = os.getenv(
        "COPERNICUS_TOKEN_URL",
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
    )
    COPERNICUS_CATALOG_URL: str = os.getenv(
        "COPERNICUS_CATALOG_URL", "https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search"
    )
    COPERNICUS_PROCESS_URL: str = os.getenv(
        "COPERNICUS_PROCESS_URL", "https://sh.dataspace.copernicus.eu/api/v1/process"
    )
    SENTINEL_INSTANCE_ID: str = os.getenv("SENTINEL_INSTANCE_ID", "")  # legacy; unused by CDSE

    # Geocoding
    NOMINATIM_URL: str = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
    NOMINATIM_USER_AGENT: str = os.getenv("NOMINATIM_USER_AGENT", "PropertyWatchAI-App/1.0 (info@propertywatch.local)")

    # Trained model weights (ONNX). Missing files => model reported UNAVAILABLE.
    MODELS_DIR: Path = Path(os.getenv("MODELS_DIR", str(ROOT_DIR.parent / "models")))
    LEVIR_CD_MODEL_PATH: str = os.getenv("LEVIR_CD_MODEL_PATH", "")
    ROOFTOP_MODEL_PATH: str = os.getenv("ROOFTOP_MODEL_PATH", "")
    ROOFTOP_MODEL_CLASSES: str = os.getenv("ROOFTOP_MODEL_CLASSES", "solar_panel")

    # Automated monitoring
    MONITORING_ENABLED: bool = os.getenv("MONITORING_ENABLED", "true").lower() in ("true", "1", "yes")
    MONITORING_INTERVAL_HOURS: float = float(os.getenv("MONITORING_INTERVAL_HOURS", "24"))
    MONITORING_MAX_CLOUD_COVER: float = float(os.getenv("MONITORING_MAX_CLOUD_COVER", "20"))
    MONITORING_ALERT_CHANGE_SCORE: float = float(os.getenv("MONITORING_ALERT_CHANGE_SCORE", "8.0"))
    MONITORING_RUN_IN_DEMO: bool = os.getenv("MONITORING_RUN_IN_DEMO", "false").lower() in ("true", "1", "yes")

    # Optional e-mail notifications (in-app notifications are always created)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "")
    
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
