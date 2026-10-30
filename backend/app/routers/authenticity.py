from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models import Evidence, AuthenticityAnalysis, AuditLog, User
from app.schemas import AuthenticityAnalysisOut
from app.services.authenticity_service import authenticity_service
from app.auth import get_current_user

router = APIRouter(prefix="", tags=["AI Image Authenticity Analysis"])

@router.post("/evidence/{evidence_id}/analyze-authenticity", response_model=AuthenticityAnalysisOut, status_code=status.HTTP_201_CREATED)
def run_authenticity_analysis(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger AI and forensic authenticity evaluation on an uploaded evidence photo:
    - Error Level Analysis (ELA) for localized recompression anomalies
    - Spectral & edge noise analysis
    - EXIF metadata synthesis signature check
    - Configured external API invocation when available
    """
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence item not found")

    if not evidence.file_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Authenticity analysis can only be performed on image files.")

    # Locate file on disk
    filename = Path(evidence.file_path).name
    full_path = settings.UPLOADS_DIR / filename
    if not full_path.exists():
        raise HTTPException(status_code=400, detail="Image file missing from server storage.")

    result = authenticity_service.analyze_evidence_image(str(full_path), evidence_id=evidence.id)

    analysis = AuthenticityAnalysis(
        evidence_id=evidence.id,
        provider=result["provider"],
        model_name=result["model_name"],
        result=result["result"],
        score=result["score"],
        explanation=result["explanation"],
        raw_response=result.get("raw_response"),
        is_demo=result.get("is_demo", False)
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    # Log audit
    audit = AuditLog(
        user_id=current_user.id,
        entity_type="AuthenticityAnalysis",
        entity_id=str(analysis.id),
        action="AUTHENTICITY_EVALUATED",
        new_state={
            "evidence_id": evidence.id,
            "filename": evidence.original_filename,
            "result": analysis.result,
            "score": analysis.score
        },
        notes=f"Authenticity evaluated by {current_user.name}"
    )
    db.add(audit)
    db.commit()

    return analysis

@router.get("/evidence/{evidence_id}/authenticity", response_model=List[AuthenticityAnalysisOut])
def get_evidence_authenticity_history(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve all authenticity analysis runs performed for an evidence item."""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence item not found")

    analyses = db.query(AuthenticityAnalysis).filter(
        AuthenticityAnalysis.evidence_id == evidence_id
    ).order_by(AuthenticityAnalysis.analyzed_at.desc()).all()

    return analyses
