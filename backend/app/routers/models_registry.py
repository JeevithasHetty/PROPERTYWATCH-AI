from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.config import settings
from app.models import AIModelRegistry, ModelInference, PropertySnapshot, Property
from app.schemas import AIModelRegistryOut, ModelInferenceOut
from app.auth import get_current_user, require_roles
from app.services.paths import snapshot_fs_path
from app.services.ai_models_service import (
    init_ai_model_registry, levir_cd_detector, rooftop_object_detector
)

router = APIRouter(prefix="/models", tags=["AI Model Registry & Diagnostics"])

class BuildingChangeRequest(BaseModel):
    property_id: int
    baseline_snapshot_id: int
    comparison_snapshot_id: int

class RooftopObjectsRequest(BaseModel):
    property_id: int
    snapshot_id: int

@router.get("", response_model=List[AIModelRegistryOut])
def list_ai_models(
    task: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    """
    List registered computer vision, building change, and forensic models
    with versions, confidence thresholds, and known operational limitations.
    """
    init_ai_model_registry()
    query = db.query(AIModelRegistry)
    if task:
        query = query.filter(AIModelRegistry.task == task)
    return query.order_by(AIModelRegistry.id).all()

@router.get("/inferences", response_model=List[ModelInferenceOut])
def list_model_inferences(
    model_id: Optional[int] = Query(None),
    entity_id: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: Any = Depends(require_roles(["admin", "reviewer", "decision_maker"]))
):
    """
    Retrieve auditable inference records with confidence scores, detected features, and limitations.
    """
    query = db.query(ModelInference)
    if model_id:
        query = query.filter(ModelInference.model_id == model_id)
    if entity_id:
        query = query.filter(ModelInference.entity_id == entity_id)

    infs = query.order_by(desc(ModelInference.created_at)).offset(skip).limit(limit).all()
    results = []
    for inf in infs:
        out = ModelInferenceOut.model_validate(inf)
        if inf.model:
            out.model_name = inf.model.name
            out.model_version = inf.model.version
        results.append(out)
    return results

@router.post("/building-change")
def run_building_change_detection(
    req: BuildingChangeRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    """
    Execute LEVIR-CD dual-temporal building change detection.
    Detects building expansions, floor additions, and outbuildings.
    """
    init_ai_model_registry()
    base_snap = db.query(PropertySnapshot).filter(PropertySnapshot.id == req.baseline_snapshot_id).first()
    comp_snap = db.query(PropertySnapshot).filter(PropertySnapshot.id == req.comparison_snapshot_id).first()

    if not base_snap or not comp_snap:
        raise HTTPException(status_code=404, detail="One or both property snapshots not found.")
    if (
        base_snap.property_id != req.property_id
        or comp_snap.property_id != req.property_id
    ):
        raise HTTPException(status_code=400, detail="Both snapshots must belong to the requested property.")
    prop = db.query(Property).filter(Property.id == req.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found.")
    if current_user.role == "owner" and prop.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property.")

    base_path = str(snapshot_fs_path(base_snap))
    comp_path = str(snapshot_fs_path(comp_snap))

    result = levir_cd_detector.detect_building_changes(base_path, comp_path, req.property_id)
    return result

@router.post("/rooftop-objects")
def run_rooftop_object_detection(
    req: RooftopObjectsRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    """
    Execute dedicated small-object detection for rooftop features (solar PV panels, HVAC units).
    """
    init_ai_model_registry()
    snap = db.query(PropertySnapshot).filter(PropertySnapshot.id == req.snapshot_id).first()
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    if snap.property_id != req.property_id:
        raise HTTPException(status_code=400, detail="The snapshot must belong to the requested property.")
    prop = db.query(Property).filter(Property.id == req.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found.")
    if current_user.role == "owner" and prop.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property.")

    img_path = str(snapshot_fs_path(snap))
    result = rooftop_object_detector.detect_rooftop_objects(img_path, req.property_id)
    return result
