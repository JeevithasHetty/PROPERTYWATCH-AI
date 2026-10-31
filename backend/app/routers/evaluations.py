import datetime
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models import (
    Claim, DamageAssessment, ProvisionalCalculation, PropertySnapshot,
    InsurancePolicy, User, AuditLog
)
from app.schemas import (
    DamageAssessmentCreate, DamageAssessmentOut,
    ProvisionalCalculationCreate, ProvisionalCalculationOut
)
from app.auth import get_current_user, require_roles
from app.services.ai_models_service import levir_cd_detector
from app.services.paths import snapshot_fs_path
from app.services.policy_rules_engine import run_policy_rules_pipeline, underinsurance_factor

router = APIRouter(prefix="/claims", tags=["Damage Evaluation & Calculations"])
logger = logging.getLogger(__name__)

@router.post("/{claim_id}/damage-assessment", response_model=DamageAssessmentOut, status_code=status.HTTP_201_CREATED)
def create_or_update_damage_assessment(
    claim_id: int,
    req: DamageAssessmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "reviewer", "decision_maker"]))
):
    """
    Evaluate damage combining owner report, pre/post event satellite imagery,
    AI damage suggestions (LEVIR-CD), human findings, and missing evidence flags.
    Separates observed indicators from AI suggestions and policy terms.
    """
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if req.claim_id != claim.id:
        raise HTTPException(status_code=400, detail="The request claim ID must match the claim in the URL.")

    # Check pre/post event snapshots
    pre_snap = db.query(PropertySnapshot).filter(PropertySnapshot.id == req.pre_event_snapshot_id).first() if req.pre_event_snapshot_id else None
    post_snap = db.query(PropertySnapshot).filter(PropertySnapshot.id == req.post_event_snapshot_id).first() if req.post_event_snapshot_id else None
    if pre_snap and pre_snap.property_id != claim.property_id:
        raise HTTPException(status_code=400, detail="Pre-event imagery must belong to the claim's property.")
    if post_snap and post_snap.property_id != claim.property_id:
        raise HTTPException(status_code=400, detail="Post-event imagery must belong to the claim's property.")

    # Run AI damage analysis if bitemporal snapshots exist
    ai_suggestions = None
    ai_model_name = None
    ai_conf = None

    if pre_snap and post_snap:
        base_path = str(snapshot_fs_path(pre_snap))
        comp_path = str(snapshot_fs_path(post_snap))

        # Run LEVIR-CD building change detector
        det_res = levir_cd_detector.detect_building_changes(base_path, comp_path, claim.property_id)
        if det_res.get("status") == "COMPLETED":
            ai_suggestions = {
                "change_detected": det_res.get("change_detected"),
                "change_area_percentage": det_res.get("change_area_percentage"),
                "structural_modifications_count": det_res.get("structural_modifications_count"),
                "detected_features": det_res.get("detected_features"),
                "summary": det_res.get("summary"),
                "limitations": det_res.get("limitations")
            }
            ai_conf = det_res.get("confidence")
            ai_model_name = f"{det_res.get('model_key')} {det_res.get('model_version')}"
        else:
            ai_suggestions = {"status": det_res.get("status"), "limitations": det_res.get("limitations")}

    # Missing evidence check
    missing_evidence = req.missing_evidence_flags or []
    if len(claim.evidence_items) == 0:
        if "No supporting photographs uploaded by owner" not in missing_evidence:
            missing_evidence.append("No supporting photographs uploaded by owner")
    if not any(ev.category == "Repair Estimate" for ev in claim.evidence_items):
        if "Formal itemized contractor repair estimate missing" not in missing_evidence:
            missing_evidence.append("Formal itemized contractor repair estimate missing")

    # Unresolved policy terms check
    unresolved_terms = req.unresolved_policy_terms_flags or []
    if not claim.policy or not claim.policy.terms_verified:
        unresolved_terms.append("Policy terms have not been formally verified against original policy jacket")

    # Create or update DamageAssessment
    assessment = db.query(DamageAssessment).filter(DamageAssessment.claim_id == claim.id).first()
    if not assessment:
        assessment = DamageAssessment(
            claim_id=claim.id,
            pre_event_snapshot_id=req.pre_event_snapshot_id,
            post_event_snapshot_id=req.post_event_snapshot_id,
            observed_damage_indicators=req.observed_damage_indicators,
            ai_damage_suggestions=ai_suggestions,
            ai_model_name=ai_model_name,
            ai_confidence=ai_conf,
            human_findings=req.human_findings,
            missing_evidence_flags=missing_evidence,
            unresolved_policy_terms_flags=unresolved_terms,
            assessment_status=req.assessment_status or "Provisional",
            assessed_by_user_id=current_user.id,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        db.add(assessment)
    else:
        assessment.pre_event_snapshot_id = req.pre_event_snapshot_id
        assessment.post_event_snapshot_id = req.post_event_snapshot_id
        assessment.observed_damage_indicators = req.observed_damage_indicators
        if ai_suggestions:
            assessment.ai_damage_suggestions = ai_suggestions
            assessment.ai_confidence = ai_conf
        assessment.human_findings = req.human_findings
        assessment.missing_evidence_flags = missing_evidence
        assessment.unresolved_policy_terms_flags = unresolved_terms
        assessment.assessment_status = req.assessment_status or assessment.assessment_status
        assessment.assessed_by_user_id = current_user.id
        assessment.updated_at = datetime.datetime.utcnow()

    db.flush()
    db.add(AuditLog(
        user_id=current_user.id,
        entity_type="DamageAssessment",
        entity_id=str(assessment.id),
        action="DAMAGE_ASSESSMENT_RECORDED",
        new_state={
            "observed_damage_indicators": assessment.observed_damage_indicators,
            "ai_suggestions_available": bool(assessment.ai_damage_suggestions),
            "assessment_status": assessment.assessment_status
        },
        notes=f"Damage assessment recorded by {current_user.name}",
        timestamp=datetime.datetime.utcnow()
    ))
    db.commit()
    db.refresh(assessment)

    a_out = DamageAssessmentOut.model_validate(assessment)
    a_out.assessed_by_name = current_user.name
    return a_out

@router.post("/{claim_id}/provisional-calculation", response_model=ProvisionalCalculationOut, status_code=status.HTTP_201_CREATED)
def calculate_provisional_payout(
    claim_id: int,
    req: ProvisionalCalculationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "reviewer", "decision_maker"]))
):
    """
    Generate an auditable provisional claim calculation:
    - Gross Claimed Loss
    - Less Non-Covered / Excluded Items
    - Less Applicable Deductible
    - Capped at Applicable Policy Limit
    - Fully documented calculation method and assumptions.
    """
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    policy = claim.policy
    if not policy:
        raise HTTPException(status_code=400, detail="Claim has no linked policy for limits and deductibles.")
    if req.claim_id != claim.id:
        raise HTTPException(status_code=400, detail="The request claim ID must match the claim in the URL.")
    if not policy.terms_verified:
        raise HTTPException(status_code=409, detail="Policy terms must be verified before calculating a provisional amount.")
    sub_limits = (policy.structured_terms or {}).get("sub_limits") or {}
    limits_pool = {**(policy.coverage_limits or {}), **sub_limits}
    if req.limit_category not in limits_pool:
        raise HTTPException(status_code=409, detail="The requested coverage limit or sub-limit is missing from the verified policy terms.")
    if not claim.damage_assessment:
        raise HTTPException(status_code=409, detail="Record the damage assessment before calculating a provisional payout.")
    if not policy.deductibles or req.deductible_type_applied not in policy.deductibles:
        raise HTTPException(status_code=409, detail="The requested deductible is missing from the verified policy terms.")
    if req.damage_assessment_id:
        assessment = db.query(DamageAssessment).filter(
            DamageAssessment.id == req.damage_assessment_id,
            DamageAssessment.claim_id == claim.id
        ).first()
        if not assessment:
            raise HTTPException(status_code=400, detail="The damage assessment must belong to this claim.")
    if req.non_covered_excluded_amount > req.gross_claimed_loss:
        raise HTTPException(status_code=400, detail="Excluded amount cannot exceed the gross claimed loss.")

    # Calculate net provisional payout:
    # Net = max(0.0, min(Gross - Excluded, Limit) - Deductible)
    gross = req.gross_claimed_loss
    excluded = req.non_covered_excluded_amount
    limit = float(limits_pool[req.limit_category])
    deductible = float(policy.deductibles[req.deductible_type_applied])

    # Evaluate all policy rules for this claim first so the calculation rests on recorded rule outcomes.
    executions = run_policy_rules_pipeline(db=db, policy_id=policy.id, claim_id=claim.id,
                                           custom_inputs={"claimed_amount": gross})
    subtotal_covered = max(0.0, gross - excluded)
    factor = underinsurance_factor(policy)
    if factor is not None:  # verified average clause + verified underinsurance
        subtotal_covered *= factor
    capped_loss = min(subtotal_covered, limit)
    net_payout = max(0.0, capped_loss - deductible)
    flagged = [e.rule_code for e in executions if e.result in ("ALERT_CREATED", "MORE_EVIDENCE_REQUIRED", "PENDING_REVIEW")]
    extra = (f" Average clause factor {factor:.4f} applied." if factor is not None else "") + \
            (f" Rules needing human attention: {', '.join(flagged)}." if flagged else "")

    calc = ProvisionalCalculation(
        claim_id=claim.id,
        damage_assessment_id=req.damage_assessment_id,
        gross_claimed_loss=gross,
        applicable_coverage_limit=limit,
        limit_category=req.limit_category,
        non_covered_excluded_amount=excluded,
        applicable_deductible=deductible,
        deductible_type_applied=req.deductible_type_applied,
        provisional_net_payout=net_payout,
        calculation_method=req.calculation_method,
        assumptions=((req.assumptions or "") + extra).strip(),
        is_provisional=True,
        calculated_by_user_id=current_user.id,
        created_at=datetime.datetime.utcnow()
    )
    db.add(calc)

    # Transition claim status
    claim.status = "Provisional Calculation Ready"
    claim.updated_at = datetime.datetime.utcnow()

    db.flush()
    db.add(AuditLog(
        user_id=current_user.id,
        entity_type="ProvisionalCalculation",
        entity_id=str(calc.id),
        action="PROVISIONAL_CALCULATION_RECORDED",
        new_state={
            "gross_claimed_loss": gross,
            "coverage_limit": limit,
            "deductible": deductible,
            "provisional_net_payout": net_payout
        },
        notes="Provisional calculation recorded; not a claim decision.",
        timestamp=datetime.datetime.utcnow()
    ))
    db.commit()
    db.refresh(calc)

    return calc
