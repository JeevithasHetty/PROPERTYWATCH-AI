import os
import uuid
import datetime
import hashlib
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.services.format_utils import format_inr
from app.database import get_db
from app.config import settings
from app.models import (
    Claim, ClaimEvidence, ClaimStatusHistory, InsurancePolicy, Property,
    Modification, OwnerDeclaration, User, AuditLog, Notification
)
from app.schemas import (
    ClaimCreate, ClaimUpdate, ClaimOut, ClaimDetailOut,
    ClaimEvidenceOut, ClaimStatusUpdate
)
from app.auth import get_current_user, require_roles
from app.services.policy_rules_engine import run_policy_rules_pipeline
from app.services.file_validation import extract_file_metadata, validate_upload_content
from app.services.datetime_utils import normalize_utc_naive

router = APIRouter(prefix="/claims", tags=["Insurance Claims Workflow"])
logger = logging.getLogger(__name__)

MAX_CLAIM_FILE_SIZE = 25 * 1024 * 1024
ALLOWED_CLAIM_FILE_TYPES = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
    "application/pdf": {".pdf"},
}

def generate_claim_reference(db: Session) -> str:
    """Generate unique collision-resistant claim reference: CLM-YYYY-XXXX."""
    year = datetime.datetime.utcnow().year
    count = db.query(Claim).count()
    candidate = f"CLM-{year}-{count + 1:04d}"
    while db.query(Claim).filter(Claim.claim_reference == candidate).first():
        count += 1
        candidate = f"CLM-{year}-{count + 1:04d}"
    return candidate

@router.get("", response_model=List[ClaimOut])
def list_claims(
    property_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["owner", "admin", "reviewer", "decision_maker"]))
):
    """
    List insurance claims.
    Ownership isolation: Property owners only see claims they submitted or own.
    Reviewers and Administrators see all claims.
    """
    query = db.query(Claim)

    # Ownership check: If role is owner, isolate to their own claims
    if current_user.role == "owner":
        query = query.filter(Claim.user_id == current_user.id)

    if property_id:
        query = query.filter(Claim.property_id == property_id)
    if status_filter:
        query = query.filter(Claim.status == status_filter)

    claims = query.order_by(desc(Claim.created_at)).offset(skip).limit(limit).all()
    results = []
    for c in claims:
        c_out = ClaimOut.model_validate(c)
        c_out.property_reference = c.property.property_reference if c.property else None
        c_out.property_address = c.property.address if c.property else None
        c_out.policy_number = c.policy.policy_number if c.policy else None
        c_out.owner_name = c.user.name if c.user else (c.property.owner_name if c.property else None)
        c_out.evidence_count = len(c.evidence_items)
        results.append(c_out)
    return results

@router.post("", response_model=ClaimOut, status_code=status.HTTP_201_CREATED)
def register_claim(
    claim_in: ClaimCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["owner", "admin"]))
):
    """
    Register an insurance claim linked to a registered property and active policy.
    - Validates policy association and effective dates
    - Does NOT automatically reject a claim because a modification alert exists
    - Links relevant property history as supporting context
    - Assigns unique claim ID (CLM-2026-XXXX)
    """
    prop = db.query(Property).filter(Property.id == claim_in.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    if current_user.role == "owner" and prop.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property.")

    # Check linked policy
    policy = db.query(InsurancePolicy).filter(InsurancePolicy.property_id == prop.id).first()
    if not policy:
        raise HTTPException(
            status_code=400,
            detail=f"Property {prop.property_reference} does not have an active linked insurance policy. Please link a policy first."
        )

    # Validate incident date is not in the future
    now = datetime.datetime.utcnow()
    incident_date = normalize_utc_naive(claim_in.incident_date)
    if incident_date > now + datetime.timedelta(days=1):
        raise HTTPException(status_code=400, detail="Incident date cannot be in the future.")

    # Validate policy period (flag, do NOT block registration)
    is_outside_term = False
    if policy.effective_date and policy.expiry_date:
        if incident_date < normalize_utc_naive(policy.effective_date) or incident_date > normalize_utc_naive(policy.expiry_date):
            is_outside_term = True

    claim_ref = generate_claim_reference(db)

    claim = Claim(
        claim_reference=claim_ref,
        property_id=prop.id,
        policy_id=policy.id,
        user_id=current_user.id,
        incident_date=incident_date,
        reported_cause=claim_in.reported_cause,
        description=claim_in.description,
        estimated_loss=claim_in.estimated_loss,
        loss_items=claim_in.loss_items,
        status="Submitted",
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow()
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    # Initial status history
    status_entry = ClaimStatusHistory(
        claim_id=claim.id,
        from_status="New",
        to_status="Submitted",
        changed_by_user_id=current_user.id,
        notes=f"Initial claim registration by {current_user.name}. Policy: {policy.policy_number}." +
              (" (Notice: Incident date outside policy term flag)" if is_outside_term else ""),
        timestamp=datetime.datetime.utcnow()
    )
    db.add(status_entry)

    # Automatically trigger baseline policy rule evaluation
    try:
        run_policy_rules_pipeline(db=db, policy_id=policy.id, claim_id=claim.id)
    except Exception:
        logger.exception("Initial policy-rule evaluation failed for claim %s", claim.claim_reference)

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        entity_type="Claim",
        entity_id=claim.claim_reference,
        action="CLAIM_REGISTERED",
        new_state={"property_id": prop.id, "loss": claim.estimated_loss, "cause": claim.reported_cause},
        notes=f"Registered claim {claim.claim_reference} for property {prop.property_reference}",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(audit)

    # Notify reviewers
    admin_reviewers = db.query(User).filter(User.role.in_(["admin", "reviewer", "decision_maker"])).all()
    for ar in admin_reviewers:
        notif = Notification(
            user_id=ar.id,
            title="New Insurance Claim Submitted",
            message=f"Claim {claim.claim_reference} submitted for {prop.property_reference} ({claim.reported_cause}, {format_inr(claim.estimated_loss)}).",
            type="CLAIM_STATUS_UPDATE",
            link=f"/claims/{claim.id}",
            created_at=datetime.datetime.utcnow()
        )
        db.add(notif)

    db.commit()

    c_out = ClaimOut.model_validate(claim)
    c_out.property_reference = prop.property_reference
    c_out.property_address = prop.address
    c_out.policy_number = policy.policy_number
    c_out.owner_name = current_user.name
    return c_out

@router.get("/{claim_id}", response_model=ClaimDetailOut)
def get_claim_detail(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["owner", "admin", "reviewer", "decision_maker"]))
):
    """
    Retrieve full claim dossier including evidence, damage assessments,
    provisional calculations, policy rule executions, and related modification history.
    """
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Ownership isolation check
    if current_user.role == "owner" and claim.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not have permission to view this claim.")

    c_out = ClaimDetailOut.model_validate(claim)
    c_out.property_reference = claim.property.property_reference if claim.property else None
    c_out.property_address = claim.property.address if claim.property else None
    c_out.policy_number = claim.policy.policy_number if claim.policy else None
    c_out.owner_name = claim.user.name if claim.user else None
    c_out.evidence_count = len(claim.evidence_items)

    # Load related property modifications and declarations as supporting context
    if claim.property:
        c_out.related_modifications = [m for m in claim.property.modifications]
        c_out.related_declarations = [d for d in claim.property.declarations]

    return c_out

@router.post("/{claim_id}/status", response_model=ClaimOut)
def update_claim_status(
    claim_id: int,
    req: ClaimStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "reviewer", "decision_maker"]))
):
    """Transition claim status and log history."""
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    allowed_statuses = {
        "Submitted", "Under Evaluation", "Information Requested",
        "Inspection Requested", "Inspection Ordered", "Provisional Calculation Ready",
        "Recommendation Recorded", "Decision Recorded", "Approved",
        "Partially Approved", "Denied", "Settled", "Closed"
    }
    if req.to_status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Invalid claim status.")
    # Outcome statuses are only reachable through the dedicated, role-gated endpoints so that
    # no reviewer shortcut or automation can approve, deny or settle a claim.
    if req.to_status in {"Approved", "Partially Approved", "Denied", "Decision Recorded", "Settled",
                         "Provisional Calculation Ready", "Recommendation Recorded"}:
        raise HTTPException(status_code=400, detail=f"'{req.to_status}' can only be set via the decision/settlement/"
                                                    "calculation/recommendation endpoints.")
    if claim.status in {"Settled", "Denied"}:
        raise HTTPException(status_code=409, detail=f"Claim is {claim.status}; its status can no longer be changed.")

    from_st = claim.status
    claim.status = req.to_status
    claim.updated_at = datetime.datetime.utcnow()

    # Record history
    hist = ClaimStatusHistory(
        claim_id=claim.id,
        from_status=from_st,
        to_status=req.to_status,
        changed_by_user_id=current_user.id,
        notes=req.notes,
        timestamp=datetime.datetime.utcnow()
    )
    db.add(hist)
    db.add(AuditLog(
        user_id=current_user.id,
        entity_type="Claim",
        entity_id=claim.claim_reference,
        action="CLAIM_STATUS_UPDATED",
        previous_state={"status": from_st},
        new_state={"status": req.to_status},
        notes=req.notes,
        timestamp=datetime.datetime.utcnow()
    ))

    # Notify owner
    notif = Notification(
        user_id=claim.user_id,
        title=f"Claim Status Update: {claim.claim_reference}",
        message=f"Your claim status changed to '{req.to_status}'. Notes: {req.notes or 'No additional notes'}",
        type="CLAIM_STATUS_UPDATE",
        link=f"/claims/{claim.id}",
        created_at=datetime.datetime.utcnow()
    )
    db.add(notif)

    db.commit()
    db.refresh(claim)

    c_out = ClaimOut.model_validate(claim)
    c_out.property_reference = claim.property.property_reference if claim.property else None
    c_out.property_address = claim.property.address if claim.property else None
    c_out.policy_number = claim.policy.policy_number if claim.policy else None
    c_out.owner_name = claim.user.name if claim.user else None
    return c_out

@router.post("/{claim_id}/evidence", response_model=ClaimEvidenceOut, status_code=status.HTTP_201_CREATED)
async def upload_claim_evidence(
    claim_id: int,
    file: UploadFile = File(...),
    category: str = Form("Damage Photograph"), # Damage Photograph, Repair Estimate, Contractor Invoice, Inspection Report, Other
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["owner", "admin", "reviewer", "decision_maker"]))
):
    """
    Upload supporting claim evidence with SHA-256 tamper-evident hash and duplicate detection.
    """
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if current_user.role == "owner" and claim.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. Cannot upload evidence to another user's claim.")
    allowed_categories = {
        "Damage Photograph", "Repair Estimate", "Contractor Invoice",
        "Inspection Report", "Policy Document", "Other"
    }
    if category not in allowed_categories:
        raise HTTPException(status_code=400, detail="Invalid claim evidence category.")

    filename = Path(file.filename or "evidence").name
    content_type = (file.content_type or "").lower()
    extension = Path(filename).suffix.lower()

    contents = await file.read(MAX_CLAIM_FILE_SIZE + 1)
    validate_upload_content(contents, content_type, filename, ALLOWED_CLAIM_FILE_TYPES, MAX_CLAIM_FILE_SIZE)
    file_metadata = extract_file_metadata(contents, content_type)

    # SHA-256 hash
    sha256 = hashlib.sha256(contents).hexdigest()

    # Duplicate detection on same claim
    duplicate = db.query(ClaimEvidence).filter(
        ClaimEvidence.claim_id == claim.id,
        ClaimEvidence.file_hash == sha256
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate file detected. This evidence item was already uploaded as '{duplicate.original_filename}'."
        )

    unique_name = f"claim_{claim.id}_{uuid.uuid4().hex[:10]}{extension}"
    dest_path = settings.UPLOADS_DIR / unique_name

    with open(dest_path, "wb") as f:
        f.write(contents)

    ev = ClaimEvidence(
        claim_id=claim.id,
        uploaded_by_user_id=current_user.id,
        file_path=unique_name,
        original_filename=filename,
        file_type=content_type,
        file_size=len(contents),
        file_hash=sha256,
        category=category,
        description=description,
        metadata_json=file_metadata,
        uploaded_at=datetime.datetime.utcnow()
    )
    db.add(ev)

    # Transition claim to 'Under Evaluation' if it was submitted
    if claim.status == "Submitted":
        previous_status = claim.status
        claim.status = "Under Evaluation"
        db.add(ClaimStatusHistory(
            claim_id=claim.id,
            from_status=previous_status,
            to_status=claim.status,
            changed_by_user_id=current_user.id,
            notes="Claim evidence was uploaded.",
            timestamp=datetime.datetime.utcnow()
        ))

    db.add(AuditLog(
        user_id=current_user.id,
        entity_type="ClaimEvidence",
        entity_id=f"{claim.claim_reference}:{sha256}",
        action="CLAIM_EVIDENCE_UPLOADED",
        new_state={"claim_id": claim.id, "filename": filename, "category": category, "hash": sha256},
        notes=f"Claim evidence uploaded by {current_user.name}",
        timestamp=datetime.datetime.utcnow()
    ))
    try:
        db.commit()
    except Exception:
        db.rollback()
        dest_path.unlink(missing_ok=True)
        raise
    db.refresh(ev)

    ev_out = ClaimEvidenceOut.model_validate(ev)
    ev_out.uploaded_by_name = current_user.name
    return ev_out


@router.get("/{claim_id}/evidence/{evidence_id}/download")
def download_claim_evidence(
    claim_id: int,
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["owner", "admin", "reviewer", "decision_maker"]))
):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    evidence = db.query(ClaimEvidence).filter(
        ClaimEvidence.id == evidence_id,
        ClaimEvidence.claim_id == claim_id
    ).first()
    if not claim or not evidence:
        raise HTTPException(status_code=404, detail="Claim evidence not found")
    if current_user.role == "owner" and claim.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. Cannot download evidence from another user's claim.")

    file_path = settings.UPLOADS_DIR / Path(evidence.file_path).name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Evidence file is missing from private storage.")
    return FileResponse(path=str(file_path), filename=evidence.original_filename, media_type=evidence.file_type)
