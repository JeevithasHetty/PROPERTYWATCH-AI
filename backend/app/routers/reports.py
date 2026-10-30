from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Modification, Property, User, Claim, InsurancePolicy
from app.services.report_service import generate_modification_pdf_report, generate_claim_pdf_report
from app.auth import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports & Dossiers"])

@router.get("/modifications/{modification_id}")
def download_modification_report_pdf(
    modification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate and download an official, professional PDF verification report for a modification case.
    Includes before/after satellite imagery, OpenCV change heatmap, evidence inventory,
    authenticity outcomes, and reviewer sign-off block.
    """
    mod = db.query(Modification).filter(Modification.id == modification_id).first()
    if not mod:
        raise HTTPException(status_code=404, detail="Modification record not found")

    prop = db.query(Property).filter(Property.id == mod.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Associated property not found")
    if current_user.role == "owner" and prop.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property's report.")

    # Serialize modification and property dicts
    mod_dict = {
        "modification_alert_id": mod.modification_alert_id,
        "suspected_category": mod.suspected_category,
        "description": mod.description,
        "status": mod.status,
        "change_score": mod.change_score,
        "detected_at": mod.detected_at,
        "verified_at": mod.verified_at,
        "analysis": {
            "explanation": mod.analysis.explanation if mod.analysis else None,
            "heatmap_image_path": mod.analysis.heatmap_image_path if mod.analysis else None,
            "diff_image_path": mod.analysis.diff_image_path if mod.analysis else None,
        } if mod.analysis else None,
        "evidence_items": [
            {
                "category": ev.category,
                "original_filename": ev.original_filename,
                "file_hash": ev.file_hash,
                "authenticity_analyses": [
                    {"result": a.result, "score": a.score} for a in ev.authenticity_analyses
                ]
            }
            for ev in mod.evidence_items
        ],
        "reviews": [
            {
                "decision": r.decision,
                "reason": r.reason,
                "notes": r.notes,
                "created_at": r.created_at
            }
            for r in mod.reviews
        ]
    }

    prop_dict = {
        "property_reference": prop.property_reference,
        "owner_name": prop.owner_name,
        "owner_contact": prop.owner_contact,
        "address": prop.address,
        "latitude": prop.latitude,
        "longitude": prop.longitude,
        "property_type": prop.property_type,
        "number_of_floors": prop.number_of_floors,
        "built_up_area": prop.built_up_area,
        "reference_policy_number": prop.reference_policy_number,
        "monitoring_enabled": prop.monitoring_enabled
    }

    try:
        pdf_path = generate_modification_pdf_report(mod_dict, prop_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compile PDF report: {str(e)}")

    filename = Path(pdf_path).name
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/properties/{property_id}")
def download_property_summary_report(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate and download a comprehensive property summary report with full modification history.
    """
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if current_user.role == "owner" and prop.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property's report.")

    # Find latest modification or generate general report
    latest_mod = db.query(Modification).filter(Modification.property_id == property_id).order_by(Modification.created_at.desc()).first()
    if latest_mod:
        return download_modification_report_pdf(latest_mod.id, db, current_user)

    # If no modifications, create a dummy modification dossier representing baseline status
    dummy_mod = {
        "modification_alert_id": f"PROP-DOSSIER-{prop.id}",
        "suspected_category": "Baseline Property Registration",
        "description": "Baseline monitoring record. No alerts or physical modifications recorded.",
        "status": "Verified",
        "change_score": 0.0,
        "detected_at": prop.created_at,
        "verified_at": prop.created_at,
        "analysis": None,
        "evidence_items": [],
        "reviews": []
    }
    prop_dict = {
        "property_reference": prop.property_reference,
        "owner_name": prop.owner_name,
        "owner_contact": prop.owner_contact,
        "address": prop.address,
        "latitude": prop.latitude,
        "longitude": prop.longitude,
        "property_type": prop.property_type,
        "number_of_floors": prop.number_of_floors,
        "built_up_area": prop.built_up_area,
        "reference_policy_number": prop.reference_policy_number,
        "monitoring_enabled": prop.monitoring_enabled
    }
    pdf_path = generate_modification_pdf_report(dummy_mod, prop_dict, output_filename=f"Property_{prop.property_reference}_Report.pdf")
    filename = Path(pdf_path).name
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/claims/{claim_id}")
def download_claim_report_pdf(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate and download an official PDF claim report containing:
    - Claim parameters and reported loss
    - Policy terms, coverage limits, deductibles, and exclusions
    - Observed damage indicators and AI damage suggestions (LEVIR-CD)
    - Policy rules execution results
    - Provisional calculations
    - Reviewer recommendation and authorized determination block.
    """
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if current_user.role not in ["owner", "admin", "reviewer", "decision_maker"]:
        raise HTTPException(status_code=403, detail="You are not authorized to access claim reports.")

    if current_user.role == "owner" and claim.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. Cannot download report for another user's claim.")

    prop = claim.property
    pol = claim.policy

    claim_dict = {
        "claim_reference": claim.claim_reference,
        "incident_date": claim.incident_date,
        "reported_cause": claim.reported_cause,
        "description": claim.description,
        "estimated_loss": claim.estimated_loss,
        "status": claim.status,
        "owner_name": claim.user.name if claim.user else None,
        "damage_assessment": {
            "observed_damage_indicators": claim.damage_assessment.observed_damage_indicators,
            "ai_damage_suggestions": claim.damage_assessment.ai_damage_suggestions,
            "ai_model_name": claim.damage_assessment.ai_model_name,
            "ai_confidence": claim.damage_assessment.ai_confidence,
            "missing_evidence_flags": claim.damage_assessment.missing_evidence_flags,
            "unresolved_policy_terms_flags": claim.damage_assessment.unresolved_policy_terms_flags,
            "human_findings": claim.damage_assessment.human_findings,
        } if claim.damage_assessment else None,
        "rule_executions": [
            {
                "rule_code": r.rule_code,
                "rule_name": r.rule_name,
                "result": r.result,
                "explanation": r.explanation,
                "applicable_clause": r.applicable_clause
            }
            for r in claim.rule_executions
        ],
        "calculations": [
            {
                "gross_claimed_loss": c.gross_claimed_loss,
                "applicable_coverage_limit": c.applicable_coverage_limit,
                "non_covered_excluded_amount": c.non_covered_excluded_amount,
                "applicable_deductible": c.applicable_deductible,
                "deductible_type_applied": c.deductible_type_applied,
                "provisional_net_payout": c.provisional_net_payout,
                "calculation_method": c.calculation_method,
                "assumptions": c.assumptions
            }
            for c in claim.calculations
        ],
        "recommendations": [
            {
                "recommendation_type": rec.recommendation_type,
                "recommended_amount": rec.recommended_amount,
                "reasoning": rec.reasoning,
                "applicable_policy_clauses": rec.applicable_policy_clauses
            }
            for rec in claim.recommendations
        ],
        "decisions": [
            {
                "decision": dec.decision,
                "authorized_amount": dec.authorized_amount,
                "rationale": dec.rationale,
                "decision_version": dec.decision_version
            }
            for dec in claim.decisions
        ]
    }

    prop_dict = {
        "property_reference": prop.property_reference if prop else "PROP-N/A",
        "owner_name": prop.owner_name if prop else "N/A",
        "address": prop.address if prop else "N/A",
        "reference_policy_number": prop.reference_policy_number if prop else None
    }

    pol_dict = {
        "policy_number": pol.policy_number if pol else "N/A",
        "policy_type": pol.policy_type if pol else "N/A",
        "coverage_limits": pol.coverage_limits if pol else {},
        "deductibles": pol.deductibles if pol else {},
        "exclusions": pol.exclusions if pol else [],
        "endorsements": pol.endorsements if pol else []
    } if pol else None

    try:
        pdf_path = generate_claim_pdf_report(claim_dict, prop_dict, pol_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate claim PDF: {str(e)}")

    filename = Path(pdf_path).name
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
