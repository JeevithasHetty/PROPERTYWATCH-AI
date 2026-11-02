from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import MonitoringRun, User, Property, PropertySnapshot
from app.auth import get_current_user, require_roles
from fastapi import HTTPException
from app.services.monitoring_service import run_monitoring_cycle, scheduler_status, check_property
from app.services.paths import snapshot_fs_path
from app.services.ai_models_service import levir_cd_detector

router = APIRouter(prefix="/monitoring", tags=["Automated Monitoring"])


class RunRequest(BaseModel):
    property_ids: Optional[List[int]] = None


@router.get("/status")
def monitoring_status(current_user: User = Depends(get_current_user)):
    return scheduler_status()


@router.post("/run")
def run_now(req: RunRequest, current_user: User = Depends(require_roles(["admin", "reviewer"]))):
    """Run a monitoring cycle immediately (same code path as the scheduler)."""
    return run_monitoring_cycle(req.property_ids)


@router.get("/runs")
def list_runs(property_id: Optional[int] = Query(None), limit: int = Query(50, le=500),
              db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = db.query(MonitoringRun)
    if property_id:
        q = q.filter(MonitoringRun.property_id == property_id)
    return [{"id": r.id, "property_id": r.property_id, "run_date": r.run_date, "status": r.status,
             "change_score": r.change_score, "summary": r.summary} for r in q.order_by(desc(MonitoringRun.id)).limit(limit)]


class AutoCompareRequest(BaseModel):
    property_id: int


@router.post("/auto-compare")
def auto_compare(req: AutoCompareRequest, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """
    One click: fetch the baseline automatically if the property has none, fetch the newest clear satellite
    photo, compare the two (circled changes + heat map) and, when the building-change ONNX model is
    installed, add its result. Nothing is invented: when imagery or a model is unavailable the response says so.
    """
    prop = db.query(Property).filter(Property.id == req.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found.")
    if current_user.role == "owner" and prop.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property.")
    out = check_property(db, prop)
    if out.get("status") == "Failed":
        raise HTTPException(status_code=502, detail=out.get("message") or "Automatic check failed.")
    if out.get("baseline_snapshot_id") and out.get("comparison_snapshot_id"):
        base = db.query(PropertySnapshot).get(out["baseline_snapshot_id"])
        comp = db.query(PropertySnapshot).get(out["comparison_snapshot_id"])
        model = levir_cd_detector.detect_building_changes(str(snapshot_fs_path(base)), str(snapshot_fs_path(comp)), prop.id)
        out["building_change_model"] = model
        if base.data_origin == "SATELLITE_LIVE":
            out["model_note"] = ("These are 10 m Sentinel-2 images. The building-change model was trained on much sharper "
                                 "photos, so treat its result as indicative only.")
    return out
