from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import MonitoringRun, User
from app.auth import get_current_user, require_roles
from app.services.monitoring_service import run_monitoring_cycle, scheduler_status

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
