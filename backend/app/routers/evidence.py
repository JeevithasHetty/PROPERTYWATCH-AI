import os
import hashlib
import uuid
import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models import Modification, Evidence, AuditLog, User
from app.schemas import EvidenceOut
from app.auth import get_current_user
from app.services.file_validation import extract_file_metadata, validate_upload_content

router = APIRouter(prefix="", tags=["Evidence Management"])

ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "image/tiff": ".tif"
}

MAX_FILE_SIZE = 25 * 1024 * 1024 # 25 MB

@router.post("/modifications/{modification_id}/evidence", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def upload_evidence_item(
    modification_id: int,
    file: UploadFile = File(...),
    category: str = Form("Photograph"), # Photograph, Building Permit, Contractor Invoice, Architectural Drawing, Other
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Securely upload supporting evidence document or photograph:
    - Verifies file type and size limit
    - Computes SHA-256 cryptographic hash for tamper-evidence
    - Isolates storage with sanitized unique filename
    - Logs audit trail
    """
    mod = db.query(Modification).filter(Modification.id == modification_id).first()
    if not mod:
        raise HTTPException(status_code=404, detail="Modification alert not found")

    if current_user.role == "owner" and mod.property.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property's modification alert.")
    content_type = (file.content_type or "").lower()
    contents = await file.read(MAX_FILE_SIZE + 1)
    file_size = len(contents)
    filename = Path(file.filename or "evidence").name
    validate_upload_content(contents, content_type, filename, {k: {v} for k, v in ALLOWED_MIME_TYPES.items()}, MAX_FILE_SIZE)
    capture_metadata = extract_file_metadata(contents, content_type)

    duplicate = db.query(Evidence).filter(
        Evidence.modification_id == mod.id,
        Evidence.file_hash == hashlib.sha256(contents).hexdigest()
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail=f"Duplicate evidence already exists as '{duplicate.original_filename}'.")

    # Compute SHA-256 hash
    sha256 = hashlib.sha256(contents).hexdigest()

    # Generate secure sanitized filename
    ext = ALLOWED_MIME_TYPES[content_type]
    unique_name = f"ev_{modification_id}_{uuid.uuid4().hex[:12]}{ext}"
    dest_path = settings.UPLOADS_DIR / unique_name

    with open(dest_path, "wb") as f:
        f.write(contents)

    relative_url = f"/static/uploads/{unique_name}"

    evidence = Evidence(
        modification_id=mod.id,
        uploaded_by=current_user.name,
        file_path=relative_url,
        original_filename=filename,
        file_type=content_type,
        file_size=file_size,
        file_hash=sha256,
        description=description,
        category=category,
        capture_metadata=capture_metadata,
        uploaded_at=datetime.datetime.utcnow()
    )
    db.add(evidence)

    # If modification was 'Awaiting Evidence', transition to 'Under Review'
    if mod.status in ["New", "Awaiting Evidence", "Additional Evidence Required"]:
        mod.status = "Under Review"

    audit = AuditLog(
        user_id=current_user.id,
        entity_type="Evidence",
        entity_id=str(evidence.id),
        action="EVIDENCE_UPLOADED",
        new_state={
            "modification_id": mod.id,
            "filename": evidence.original_filename,
            "category": evidence.category,
            "hash": sha256
        },
        notes=f"Evidence uploaded by {current_user.name}"
    )
    db.add(audit)
    try:
        db.commit()
    except Exception:
        db.rollback()
        dest_path.unlink(missing_ok=True)
        raise
    db.refresh(evidence)

    return evidence

@router.get("/modifications/{modification_id}/evidence", response_model=List[EvidenceOut])
def list_modification_evidence(
    modification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve all evidence items attached to a modification case."""
    mod = db.query(Modification).filter(Modification.id == modification_id).first()
    if not mod:
        raise HTTPException(status_code=404, detail="Modification alert not found")
    if current_user.role == "owner" and mod.property.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property's modification alert.")

    items = db.query(Evidence).filter(Evidence.modification_id == modification_id).order_by(Evidence.uploaded_at.desc()).all()
    return items

@router.get("/evidence/{evidence_id}/download")
def download_evidence_file(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Secure access-controlled evidence download endpoint."""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence item not found")
    if current_user.role == "owner" and evidence.modification.property.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property's evidence.")

    filename = Path(evidence.file_path).name
    full_path = settings.UPLOADS_DIR / filename

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Evidence file missing on server storage.")

    return FileResponse(
        path=str(full_path),
        filename=evidence.original_filename,
        media_type=evidence.file_type
    )
