import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database import get_db
from app.models import AuditLog, Property, Modification, User
from app.schemas import AuditLogOut, DashboardMetricsOut, ModificationOut
from app.auth import get_current_user

router = APIRouter(prefix="", tags=["Audit & Dashboard"])

@router.get("/audit-logs", response_model=List[AuditLogOut])
def list_audit_logs(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve immutable chronological audit trail."""
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)

    logs = query.order_by(desc(AuditLog.timestamp)).offset(skip).limit(limit).all()

    results = []
    for l in logs:
        l_out = AuditLogOut.model_validate(l)
        l_out.user_name = l.user.name if l.user else "System Process"
        results.append(l_out)

    return results

@router.get("/dashboard/metrics", response_model=DashboardMetricsOut)
def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate real-time operational dashboard metrics and analytics directly from the database:
    - Total properties & monitored count
    - Alert volume breakdowns by status
    - Monthly distribution
    - Category breakdowns
    - Recent cases and recent audit activity
    """
    total_properties = db.query(Property).count()
    monitored_properties = db.query(Property).filter(Property.monitoring_enabled == True).count()
    
    new_alerts_count = db.query(Modification).filter(Modification.status == "New").count()
    awaiting_review_count = db.query(Modification).filter(Modification.status.in_(["Awaiting Evidence", "Under Review"])).count()
    confirmed_modifications_count = db.query(Modification).filter(Modification.status == "Verified").count()
    additional_evidence_count = db.query(Modification).filter(Modification.status == "Additional Evidence Required").count()

    # Category distribution
    categories_query = db.query(
        Modification.suspected_category,
        func.count(Modification.id).label("count")
    ).group_by(Modification.suspected_category).all()

    category_data = [
        {"name": cat or "General Modification", "count": count}
        for cat, count in categories_query
    ]
    if not category_data:
        category_data = [{"name": "No Alerts Logged", "count": 0}]

    # Monthly alert counts for charts (e.g. past 6 months)
    # Using python grouping for SQLite date compatibility
    all_mods = db.query(Modification).all()
    month_counts: Dict[str, int] = {}
    for m in all_mods:
        m_str = m.detected_at.strftime("%b %Y") if m.detected_at else "Unknown"
        month_counts[m_str] = month_counts.get(m_str, 0) + 1

    alerts_by_month = [{"month": m, "alerts": c} for m, c in month_counts.items()]
    if not alerts_by_month:
        # Default placeholder month for empty db
        now = datetime.datetime.utcnow().strftime("%b %Y")
        alerts_by_month = [{"month": now, "alerts": 0}]

    # Recent cases
    recent_mods = db.query(Modification).order_by(desc(Modification.created_at)).limit(8).all()
    recent_cases = []
    for m in recent_mods:
        m_out = ModificationOut.model_validate(m)
        m_out.property_reference = m.property.property_reference if m.property else None
        m_out.property_address = m.property.address if m.property else None
        m_out.evidence_count = len(m.evidence_items)
        m_out.reviewer_name = m.reviewer.name if m.reviewer else None
        recent_cases.append(m_out)

    # Recent activity
    recent_audits = db.query(AuditLog).order_by(desc(AuditLog.timestamp)).limit(10).all()
    recent_activity = []
    for l in recent_audits:
        l_out = AuditLogOut.model_validate(l)
        l_out.user_name = l.user.name if l.user else "System Process"
        recent_activity.append(l_out)

    return {
        "total_properties": total_properties,
        "monitored_properties": monitored_properties,
        "new_alerts_count": new_alerts_count,
        "awaiting_review_count": awaiting_review_count,
        "confirmed_modifications_count": confirmed_modifications_count,
        "additional_evidence_count": additional_evidence_count,
        "alerts_by_month": alerts_by_month,
        "modification_categories": category_data,
        "recent_cases": recent_cases,
        "recent_activity": recent_activity
    }
