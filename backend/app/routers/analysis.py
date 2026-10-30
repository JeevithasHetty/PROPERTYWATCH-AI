from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models import Property, PropertySnapshot, ImageAnalysis, AuditLog, User
from app.schemas import ImageComparisonRequest, ImageAnalysisOut
from app.services.cv_service import run_image_comparison_pipeline
from app.auth import get_current_user

router = APIRouter(prefix="/analysis", tags=["Image Analysis & Computer Vision"])

def resolve_storage_path(relative_url: str) -> Path:
    """Resolve API static relative URL to real filesystem path."""
    clean = relative_url.lstrip("/")
    if clean.startswith("private/uploads/"):
        return settings.UPLOADS_DIR / Path(clean).name
    if clean.startswith("static/"):
        clean = clean[len("static/"):]
    return settings.STORAGE_DIR / clean

@router.post("/compare", response_model=ImageAnalysisOut, status_code=status.HTTP_201_CREATED)
def compare_property_images(
    req: ImageComparisonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Execute Computer Vision change analysis on two property snapshots:
    Dimension normalization, feature-based ORB alignment, differential SSIM,
    morphological segmentation, contour detection, and heatmap generation.
    """
    prop = db.query(Property).filter(Property.id == req.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if current_user.role == "owner" and prop.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property's imagery.")

    base_snap = db.query(PropertySnapshot).filter(PropertySnapshot.id == req.baseline_snapshot_id).first()
    comp_snap = db.query(PropertySnapshot).filter(PropertySnapshot.id == req.comparison_snapshot_id).first()

    if not base_snap or not comp_snap:
        raise HTTPException(status_code=404, detail="One or both selected snapshot records could not be found.")
    if base_snap.property_id != prop.id or comp_snap.property_id != prop.id:
        raise HTTPException(status_code=400, detail="Both comparison snapshots must belong to the selected property.")

    base_path = (
        settings.UPLOADS_DIR / Path(base_snap.capture_metadata["storage_filename"]).name
        if base_snap.capture_metadata and base_snap.capture_metadata.get("storage_filename")
        else resolve_storage_path(base_snap.image_path)
    )
    comp_path = (
        settings.UPLOADS_DIR / Path(comp_snap.capture_metadata["storage_filename"]).name
        if comp_snap.capture_metadata and comp_snap.capture_metadata.get("storage_filename")
        else resolve_storage_path(comp_snap.image_path)
    )

    if not base_path.exists():
        raise HTTPException(status_code=400, detail=f"Baseline image file missing on disk: {base_path}")
    if not comp_path.exists():
        raise HTTPException(status_code=400, detail=f"Comparison image file missing on disk: {comp_path}")

    try:
        cv_result = run_image_comparison_pipeline(
            baseline_path=str(base_path),
            comparison_path=str(comp_path),
            property_id=prop.id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Computer Vision pipeline failed: {str(e)}")

    analysis = ImageAnalysis(
        property_id=prop.id,
        baseline_snapshot_id=base_snap.id,
        comparison_snapshot_id=comp_snap.id,
        algorithm_name=cv_result["algorithm_name"],
        change_score=cv_result["change_score"],
        changed_area_percentage=cv_result["changed_area_percentage"],
        diff_image_path=cv_result["diff_image_path"],
        heatmap_image_path=cv_result["heatmap_image_path"],
        contours_count=cv_result["contours_count"],
        analysis_result=cv_result["analysis_result"],
        explanation=cv_result["explanation"],
        limitations=cv_result["limitations"]
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    # Log audit
    audit = AuditLog(
        user_id=current_user.id,
        entity_type="ImageAnalysis",
        entity_id=str(analysis.id),
        action="IMAGE_ANALYSIS_COMPUTED",
        new_state={
            "change_score": analysis.change_score,
            "classification": analysis.analysis_result,
            "baseline_date": base_snap.acquisition_date.isoformat(),
            "comparison_date": comp_snap.acquisition_date.isoformat()
        },
        notes=f"CV analysis triggered by {current_user.name}"
    )
    db.add(audit)
    db.commit()

    return analysis

@router.get("/{analysis_id}", response_model=ImageAnalysisOut)
def get_analysis_result(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve full technical metrics and generated overlays of an image analysis."""
    analysis = db.query(ImageAnalysis).filter(ImageAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis record not found")
    prop = db.query(Property).filter(Property.id == analysis.property_id).first()
    if current_user.role == "owner" and (not prop or prop.owner_user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property's analysis.")
    return analysis
