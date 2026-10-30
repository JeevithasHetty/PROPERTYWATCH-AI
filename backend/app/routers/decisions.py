import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Claim, ClaimRecommendation, ClaimDecision, ClaimStatusHistory,
    Notification, User, AuditLog
)
from app.schemas import (
    ClaimRecommendationCreate, ClaimRecommendationOut,
    ClaimDecisionCreate, ClaimDecisionOut
)
from app.auth import get_current_user, require_roles

router = APIRouter(prefix="/claims", tags=["Reviewer Recommendations & Authorized Decisions"])

@router.post("/{claim_id}/recommendation", response_model=ClaimRecommendationOut, status_code=status.HTTP_201_CREATED)
def submit_reviewer_recommendation(
    claim_id: int,
    req: ClaimRecommendationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "reviewer", "decision_maker"]))
):
    """
    Authorized examiner records an advisory recommendation, reasoning, applicable policy clauses,
    and evidence references.
    Recommendation types:
    - APPROVE_PROVISIONAL
    - REQUEST_MORE_DOCUMENTS
    - REQUEST_INSPECTION
    - REDUCE_AMOUNT
    - DENY_EXCLUDED
    Advisory only: does NOT finalize the claim. Final decisions require decision-maker sign-off.
    """
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    rec = ClaimRecommendation(
        claim_id=claim.id,
        reviewer_id=current_user.id,
        recommendation_type=req.recommendation_type,
        recommended_amount=req.recommended_amount,
        reasoning=req.reasoning,
        applicable_policy_clauses=req.applicable_policy_clauses,
        evidence_references=req.evidence_references,
        created_at=datetime.datetime.utcnow()
    )
    db.add(rec)

    prev_status = claim.status
    if req.recommendation_type == "REQUEST_MORE_DOCUMENTS":
        claim.status = "Information Requested"
    elif req.recommendation_type == "REQUEST_INSPECTION":
        claim.status = "Inspection Requested"
    else:
        claim.status = "Recommendation Recorded"
    claim.updated_at = datetime.datetime.utcnow()

    # Log status history
    hist = ClaimStatusHistory(
        claim_id=claim.id,
        from_status=prev_status,
        to_status=claim.status,
        changed_by_user_id=current_user.id,
        notes=f"Reviewer Recommendation ({req.recommendation_type}): {req.reasoning}",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(hist)
    db.add(AuditLog(
        user_id=current_user.id,
        entity_type="ClaimRecommendation",
        entity_id=claim.claim_reference,
        action="CLAIM_RECOMMENDATION_RECORDED",
        new_state={
            "recommendation_type": req.recommendation_type,
            "recommended_amount": req.recommended_amount,
            "policy_clauses": req.applicable_policy_clauses,
            "evidence_references": req.evidence_references
        },
        notes=req.reasoning,
        timestamp=datetime.datetime.utcnow()
    ))

    # If info requested, notify owner
    if req.recommendation_type in ["REQUEST_MORE_DOCUMENTS", "REQUEST_INSPECTION"]:
        notif = Notification(
            user_id=claim.user_id,
            title="Action Required: Additional Information Requested for Claim",
            message=f"Reviewer {current_user.name} has requested: {req.reasoning}",
            type="RFI_REQUEST",
            link=f"/claims/{claim.id}",
            created_at=datetime.datetime.utcnow()
        )
        db.add(notif)

    db.commit()
    db.refresh(rec)

    rec_out = ClaimRecommendationOut.model_validate(rec)
    rec_out.reviewer_name = current_user.name
    return rec_out

@router.post("/{claim_id}/decision", response_model=ClaimDecisionOut, status_code=status.HTTP_201_CREATED)
def submit_authorized_decision(
    claim_id: int,
    req: ClaimDecisionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "decision_maker"]))
):
    """
    Commit an authoritative, final claim determination.
    Strictly role-gated: only users with explicit decision-making authority (admin, decision_maker) can commit.
    AI is strictly prohibited from making final claim decisions automatically.
    Maintains versioned decisions, rationale, clauses, and notifies property owner.
    """
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    decision_version = len(claim.decisions) + 1

    dec = ClaimDecision(
        claim_id=claim.id,
        decision_maker_id=current_user.id,
        decision=req.decision,
        authorized_amount=req.authorized_amount,
        rationale=req.rationale,
        applicable_policy_clauses=req.applicable_policy_clauses,
        decision_version=decision_version,
        created_at=datetime.datetime.utcnow()
    )
    db.add(dec)

    prev_status = claim.status
    if req.decision in ["APPROVED", "APPROVED_PARTIAL"]:
        claim.status = "Approved" if req.decision == "APPROVED" else "Partially Approved"
    elif req.decision == "DENIED":
        claim.status = "Denied"
    elif req.decision == "MORE_INFO_REQUESTED":
        claim.status = "Information Requested"
    elif req.decision == "INSPECTION_ORDERED":
        claim.status = "Inspection Ordered"

    claim.updated_at = datetime.datetime.utcnow()

    # Log status history
    hist = ClaimStatusHistory(
        claim_id=claim.id,
        from_status=prev_status,
        to_status=claim.status,
        changed_by_user_id=current_user.id,
        notes=f"Authorized Decision (v{decision_version}) by {current_user.name}: {req.decision}. Rationale: {req.rationale}",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(hist)

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        entity_type="Claim",
        entity_id=claim.claim_reference,
        action="DECISION_COMMITTED",
        new_state={
            "decision": req.decision,
            "authorized_amount": req.authorized_amount,
            "version": decision_version
        },
        notes=f"Authorized decision committed for {claim.claim_reference}: {req.decision}",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(audit)

    # Notify property owner
    notif = Notification(
        user_id=claim.user_id,
        title=f"Claim Determination: {claim.claim_reference}",
        message=f"Official determination recorded: {req.decision}. " +
                (f"Authorized Amount: ${req.authorized_amount:,.2f}. " if req.authorized_amount else "") +
                f"Rationale: {req.rationale}",
        type="CLAIM_STATUS_UPDATE",
        link=f"/claims/{claim.id}",
        created_at=datetime.datetime.utcnow()
    )
    db.add(notif)

    db.commit()
    db.refresh(dec)

    dec_out = ClaimDecisionOut.model_validate(dec)
    dec_out.decision_maker_name = current_user.name
    return dec_out
