from pathlib import Path
from app.config import settings


def snapshot_fs_path(snapshot) -> Path:
    """Resolve a PropertySnapshot to its file on disk (private uploads or public snapshots)."""
    meta = snapshot.capture_metadata or {}
    if meta.get("storage_filename"):
        return settings.UPLOADS_DIR / Path(meta["storage_filename"]).name
    clean = snapshot.image_path.lstrip("/")
    if clean.startswith("private/uploads/"):
        return settings.UPLOADS_DIR / Path(clean).name
    if clean.startswith("static/"):
        clean = clean[len("static/"):]
    return settings.STORAGE_DIR / clean
