import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import Modification, Property, Review, Evidence, AuditLog, User
from app.schemas import ReviewDecisionRequest, ReviewOut, ModificationOut
from app.auth import get_current_user, require_roles
from app.services.llm_service import llm_service

router = APIRouter(prefix="", tags=["Human Reviewer Workspace"])

@router.get("/reviews", response_model=List[ModificationOut])
def get_pending_review_cases(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve cases currently queued for human review.
    Accessible to authorized reviewers and property managers.
    """
    query = db.query(Modification)
    if status_filter:
        query = query.filter(Modification.status == status_filter)
    else:
        # Default to cases awaiting review or under review
        query = query.filter(Modification.status.in_(["New", "Awaiting Evidence", "Under Review", "Additional Evidence Required"]))

    mods = query.order_by(desc(Modification.detected_at)).all()
    results = []
    for m in mods:
        m_out = ModificationOut.model_validate(m)
        m_out.property_reference = m.property.property_reference if m.property else None
        m_out.property_address = m.property.address if m.property else None
        m_out.evidence_count = len(m.evidence_items)
        m_out.reviewer_name = m.reviewer.name if m.reviewer else None
        results.append(m_out)

    return results

@router.post("/reviews/{modification_id}/decision", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def submit_verification_decision(
    modification_id: int,
    req: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "reviewer"]))
):
    """
    Authorized human verification decision for a property modification case only.
    - Verified: Confirms modification, updates property attributes, maintains chronological audit trail.
    - Not Confirmed: Marks signal as rejected / false positive with documented reason.
    - Additional Evidence Required: Requests further documentation from property owner/manager.
    Strictly restricted to property records (no insurance claim logic).
    """
    mod = db.query(Modification).filter(Modification.id == modification_id).first()
    if not mod:
        raise HTTPException(status_code=404, detail="Modification alert not found")

    prop = db.query(Property).filter(Property.id == mod.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Associated property record not found")

    prev_mod_status = mod.status
    prev_prop_attributes = {
        "number_of_floors": prop.number_of_floors,
        "built_up_area": prop.built_up_area,
        "property_type": prop.property_type
    }

    # Record Review decision
    review = Review(
        modification_id=mod.id,
        reviewer_id=current_user.id,
        decision=req.decision,
        reason=req.reason,
        notes=req.notes,
        created_at=datetime.datetime.utcnow()
    )
    db.add(review)

    # Update Modification record
    mod.status = req.decision
    mod.reviewer_id = current_user.id
    mod.reviewer_notes = req.notes
    mod.decision_reason = req.reason
    mod.updated_at = datetime.datetime.utcnow()

    # If Verified, update property's verified attributes where applicable while preserving original baseline
    prop_updated_fields = {}
    if req.decision == "Verified":
        mod.verified_at = datetime.datetime.utcnow()

        if req.updated_floors is not None and req.updated_floors > 0:
            prop.number_of_floors = req.updated_floors
            prop_updated_fields["number_of_floors"] = req.updated_floors
        elif "floor" in mod.suspected_category.lower() or "story" in mod.suspected_category.lower():
            prop.number_of_floors += 1
            prop_updated_fields["number_of_floors"] = prop.number_of_floors

        if req.updated_area is not None and req.updated_area > 0:
            prop.built_up_area = req.updated_area
            prop_updated_fields["built_up_area"] = req.updated_area

        if req.updated_property_type:
            prop.property_type = req.updated_property_type
            prop_updated_fields["property_type"] = req.updated_property_type

        prop.updated_at = datetime.datetime.utcnow()

    db.commit()
    db.refresh(review)

    # Record detailed audit logs
    audit_mod = AuditLog(
        user_id=current_user.id,
        entity_type="Modification",
        entity_id=str(mod.id),
        action=f"MODIFICATION_{req.decision.upper().replace(' ', '_')}",
        previous_state={"status": prev_mod_status},
        new_state={"status": mod.status, "reason": req.reason},
        notes=f"Decision rendered by reviewer {current_user.name} ({current_user.role})"
    )
    db.add(audit_mod)

    if prop_updated_fields:
        audit_prop = AuditLog(
            user_id=current_user.id,
            entity_type="Property",
            entity_id=str(prop.id),
            action="PROPERTY_ATTRIBUTES_UPDATED_BY_VERIFIED_MODIFICATION",
            previous_state=prev_prop_attributes,
            new_state=prop_updated_fields,
            notes=f"Property attributes updated following verification of {mod.modification_alert_id}"
        )
        db.add(audit_prop)

    db.commit()

    rev_out = ReviewOut.model_validate(review)
    rev_out.reviewer_name = current_user.name
    return rev_out

@router.get("/reviews/{modification_id}/summary")
def get_ai_evidence_summary(
    modification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate an objective, factual evidence summary for the reviewer workspace using the LLM service.
    """
    mod = db.query(Modification).filter(Modification.id == modification_id).first()
    if not mod:
        raise HTTPException(status_code=404, detail="Modification alert not found")

    evidence_items = [
        {
            "category": ev.category,
            "original_filename": ev.original_filename,
            "description": ev.description,
            "uploaded_at": str(ev.uploaded_at)[:10]
        }
        for ev in mod.evidence_items
    ]

    summary = llm_service.generate_evidence_summary(
        modification_alert_id=mod.modification_alert_id,
        category=mod.suspected_category,
        detection_date=str(mod.detected_at)[:10],
        change_score=mod.change_score,
        evidence_list=evidence_items
    )

    return {
        "modification_alert_id": mod.modification_alert_id,
        "evidence_count": len(evidence_items),
        "summary": summary
    }
