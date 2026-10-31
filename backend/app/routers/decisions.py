import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.services.format_utils import format_inr
from app.database import get_db
from app.models import (
    Claim, ClaimRecommendation, ClaimDecision, ClaimStatusHistory,
    Notification, User, AuditLog, ClaimSettlement
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

    if claim.status in ("Settled", "Closed"):
        raise HTTPException(status_code=409, detail=f"Claim is {claim.status}; no further decisions can be recorded.")
    if req.decision in ("APPROVED", "APPROVED_PARTIAL"):
        if not claim.calculations:
            raise HTTPException(status_code=409, detail="A provisional calculation is required before approval.")
        if not claim.recommendations:
            raise HTTPException(status_code=409, detail="A reviewer recommendation is required before approval.")
        latest_calc = max(claim.calculations, key=lambda c: c.id)
        if req.authorized_amount is None or req.authorized_amount < 0:
            raise HTTPException(status_code=400, detail="authorized_amount is required for approval.")
        if req.authorized_amount > latest_calc.provisional_net_payout + 0.005:
            raise HTTPException(status_code=409, detail=(
                f"Authorized amount {format_inr(req.authorized_amount)} exceeds the latest provisional payout "
                f"{format_inr(latest_calc.provisional_net_payout)}. Record a new calculation first."))
    if req.decision == "DENIED":
        # A denial must rest on cited, verified policy terms - never on a satellite/rule signal or a modification alone.
        if not req.applicable_policy_clauses:
            raise HTTPException(status_code=400, detail="A denial must cite the applicable policy clause(s).")
        if not claim.policy or not claim.policy.terms_verified:
            raise HTTPException(status_code=409, detail="A claim cannot be denied on unverified policy terms.")
        if len((req.rationale or "").strip()) < 20:
            raise HTTPException(status_code=400, detail="A denial requires a substantive written rationale.")

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
                (f"Authorized Amount: {format_inr(req.authorized_amount)}. " if req.authorized_amount else "") +
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


class SettlementCreate(BaseModel):
    settled_amount: float = Field(..., ge=0)
    payment_mode: str
    payment_reference: str = Field(..., min_length=3)
    payment_date: Optional[datetime.datetime] = None
    notes: Optional[str] = None


@router.post("/{claim_id}/settlement", status_code=status.HTTP_201_CREATED)
def record_settlement(
    claim_id: int,
    req: SettlementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "decision_maker"]))
):
    """Record payment of an APPROVED claim (amount cannot exceed the authorised amount). Moves claim to 'Settled'."""
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.status not in ("Approved", "Partially Approved"):
        raise HTTPException(status_code=409, detail="Only an approved claim can be settled.")
    if req.payment_mode.upper() not in {"NEFT", "RTGS", "UPI", "IMPS", "CHEQUE"}:
        raise HTTPException(status_code=400, detail="payment_mode must be one of NEFT, RTGS, UPI, IMPS, CHEQUE.")
    last = max((d for d in claim.decisions if d.decision in ("APPROVED", "APPROVED_PARTIAL")),
               key=lambda d: d.decision_version, default=None)
    if last is None:
        raise HTTPException(status_code=409, detail="No approving decision found.")
    paid = sum(x.settled_amount for x in db.query(ClaimSettlement).filter(ClaimSettlement.claim_id == claim.id))
    if paid + req.settled_amount > (last.authorized_amount or 0) + 0.005:
        raise HTTPException(status_code=409, detail=(
            f"Settlement would exceed the authorised amount {format_inr(last.authorized_amount)} "
            f"(already paid {format_inr(paid)})."))
    st = ClaimSettlement(claim_id=claim.id, decision_id=last.id, settled_amount=req.settled_amount,
                         payment_mode=req.payment_mode.upper(), payment_reference=req.payment_reference,
                         payment_date=req.payment_date or datetime.datetime.utcnow(),
                         settled_by_user_id=current_user.id, notes=req.notes)
    db.add(st)
    prev = claim.status
    fully_paid = abs(paid + req.settled_amount - (last.authorized_amount or 0)) < 0.005
    if fully_paid:
        claim.status = "Settled"
    claim.updated_at = datetime.datetime.utcnow()
    db.add(ClaimStatusHistory(claim_id=claim.id, from_status=prev, to_status=claim.status,
                              changed_by_user_id=current_user.id,
                              notes=f"Payment {format_inr(req.settled_amount)} via {st.payment_mode} ref {st.payment_reference}",
                              timestamp=datetime.datetime.utcnow()))
    db.add(AuditLog(user_id=current_user.id, entity_type="Claim", entity_id=claim.claim_reference,
                    action="CLAIM_SETTLEMENT_RECORDED",
                    new_state={"amount": req.settled_amount, "mode": st.payment_mode, "reference": st.payment_reference},
                    timestamp=datetime.datetime.utcnow()))
    db.add(Notification(user_id=claim.user_id, title=f"Claim payment: {claim.claim_reference}",
                        message=f"{format_inr(req.settled_amount)} paid via {st.payment_mode} (ref {st.payment_reference}).",
                        type="CLAIM_STATUS_UPDATE", link=f"/claims/{claim.id}"))
    db.commit()
    db.refresh(st)
    return {"id": st.id, "claim_id": claim.id, "settled_amount": st.settled_amount, "payment_mode": st.payment_mode,
            "payment_reference": st.payment_reference, "payment_date": st.payment_date,
            "claim_status": claim.status, "fully_settled": fully_paid}
