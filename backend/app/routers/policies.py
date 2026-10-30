import os
import uuid
import datetime
import hashlib
import math
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.config import settings
from app.models import (
    InsurancePolicy, PolicyVersion, PolicyRule, PolicyRuleExecution, Property,
    User, AuditLog, Claim, Modification
)
from app.schemas import (
    PolicyCreate, PolicyUpdate, PolicyOut, PolicyVersionOut,
    PolicyRuleOut, PolicyRuleUpdate, PolicyRuleExecutionOut, PolicyRuleEvaluationRequest,
    PolicyVerificationRequest
)
from app.auth import get_current_user, require_roles
from app.services.policy_rules_engine import (
    run_policy_rules_pipeline, init_policy_rules_in_db
)
from app.services.file_validation import extract_file_metadata, validate_upload_content
from app.services.datetime_utils import normalize_utc_naive

router = APIRouter(prefix="/policies", tags=["Insurance Policies & Rules Engine"])
MAX_POLICY_FILE_SIZE = 25 * 1024 * 1024
ALLOWED_POLICY_FILE_TYPES = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
}


def _require_property_access(prop: Property, user: User) -> None:
    if user.role == "owner" and prop.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property's policy.")


def _require_policy_access(policy: InsurancePolicy, user: User) -> None:
    _require_property_access(policy.property, user)

@router.get("", response_model=List[PolicyOut])
def list_policies(
    property_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List registered insurance policies with optional property or status filter."""
    query = db.query(InsurancePolicy)
    if current_user.role == "owner":
        query = query.join(Property).filter(Property.owner_user_id == current_user.id)
    if property_id:
        query = query.filter(InsurancePolicy.property_id == property_id)
    if status_filter:
        query = query.filter(InsurancePolicy.status == status_filter)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            (InsurancePolicy.policy_number.ilike(s)) |
            (InsurancePolicy.policy_type.ilike(s))
        )

    policies = query.order_by(desc(InsurancePolicy.created_at)).offset(skip).limit(limit).all()
    results = []
    for pol in policies:
        p_out = PolicyOut.model_validate(pol)
        if pol.property:
            p_out.property_reference = pol.property.property_reference
            p_out.property_address = pol.property.address
        results.append(p_out)
    return results

@router.post("", response_model=PolicyOut, status_code=status.HTTP_201_CREATED)
def link_insurance_policy(
    policy_in: PolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Register and link an insurance policy to a registered property.
    Validates policy dates (effective_date <= expiry_date) and property association.
    Never invents missing policy terms.
    """
    prop = db.query(Property).filter(Property.id == policy_in.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property record not found.")
    _require_property_access(prop, current_user)

    # Check for existing policy on this property
    existing_pol = db.query(InsurancePolicy).filter(InsurancePolicy.property_id == prop.id).first()
    if existing_pol:
        raise HTTPException(
            status_code=409,
            detail=f"Property {prop.property_reference} is already linked to policy {existing_pol.policy_number}."
        )

    # Validate dates
    effective_date = normalize_utc_naive(policy_in.effective_date)
    expiry_date = normalize_utc_naive(policy_in.expiry_date)
    if effective_date >= expiry_date:
        raise HTTPException(
            status_code=400,
            detail="Policy effective date must precede expiration date."
        )

    policy = InsurancePolicy(
        policy_number=policy_in.policy_number.strip().upper(),
        property_id=prop.id,
        policy_type=policy_in.policy_type,
        status="Active",
        effective_date=effective_date,
        expiry_date=expiry_date,
        coverage_limits=policy_in.coverage_limits or {},
        deductibles=policy_in.deductibles or {},
        exclusions=policy_in.exclusions or [],
        endorsements=policy_in.endorsements or [],
        terms_verified=False,
        notes=policy_in.notes,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow()
    )
    db.add(policy)
    db.flush()
    # Update property reference_policy_number for quick indexing
    prop.reference_policy_number = policy.policy_number

    # Create initial version record
    ver = PolicyVersion(
        policy_id=policy.id,
        version_number=1,
        terms_snapshot={
            "policy_number": policy.policy_number,
            "policy_type": policy.policy_type,
            "effective_date": policy.effective_date.isoformat(),
            "expiry_date": policy.expiry_date.isoformat(),
            "coverage_limits": policy.coverage_limits,
            "deductibles": policy.deductibles,
            "exclusions": policy.exclusions,
            "endorsements": policy.endorsements
        },
        change_reason="Initial policy registration and property linkage",
        changed_by_user_id=current_user.id,
        created_at=datetime.datetime.utcnow()
    )
    db.add(ver)

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        entity_type="Policy",
        entity_id=policy.policy_number,
        action="POLICY_LINKED",
        new_state={"property_id": prop.id, "policy_number": policy.policy_number},
        notes=f"Linked policy {policy.policy_number} to property {prop.property_reference}",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(audit)
    db.commit()
    db.refresh(policy)

    p_out = PolicyOut.model_validate(policy)
    p_out.property_reference = prop.property_reference
    p_out.property_address = prop.address
    return p_out

@router.get("/{policy_id}", response_model=PolicyOut)
def get_policy_detail(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve full insurance policy details."""
    pol = db.query(InsurancePolicy).filter(InsurancePolicy.id == policy_id).first()
    if not pol:
        raise HTTPException(status_code=404, detail="Policy not found")
    _require_policy_access(pol, current_user)

    p_out = PolicyOut.model_validate(pol)
    if pol.property:
        p_out.property_reference = pol.property.property_reference
        p_out.property_address = pol.property.address
    return p_out

@router.put("/{policy_id}", response_model=PolicyOut)
def update_policy_terms(
    policy_id: int,
    req: PolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "reviewer"]))
):
    """
    Update policy terms and commit a new immutable PolicyVersion record.
    """
    pol = db.query(InsurancePolicy).filter(InsurancePolicy.id == policy_id).first()
    if not pol:
        raise HTTPException(status_code=404, detail="Policy not found")
    _require_policy_access(pol, current_user)

    effective_date = normalize_utc_naive(req.effective_date) if req.effective_date else normalize_utc_naive(pol.effective_date)
    expiry_date = normalize_utc_naive(req.expiry_date) if req.expiry_date else normalize_utc_naive(pol.expiry_date)
    if effective_date >= expiry_date:
        raise HTTPException(status_code=400, detail="Effective date must precede expiry date.")

    # Apply updates
    if req.policy_type: pol.policy_type = req.policy_type
    if req.status: pol.status = req.status
    if req.effective_date: pol.effective_date = effective_date
    if req.expiry_date: pol.expiry_date = expiry_date
    if req.coverage_limits is not None: pol.coverage_limits = req.coverage_limits
    if req.deductibles is not None: pol.deductibles = req.deductibles
    if req.exclusions is not None: pol.exclusions = req.exclusions
    if req.endorsements is not None: pol.endorsements = req.endorsements
    if req.terms_verified is not None: pol.terms_verified = req.terms_verified
    if req.notes: pol.notes = req.notes
    pol.updated_at = datetime.datetime.utcnow()

    # Bump version
    next_ver = len(pol.versions) + 1
    new_version = PolicyVersion(
        policy_id=pol.id,
        version_number=next_ver,
        terms_snapshot={
            "policy_number": pol.policy_number,
            "policy_type": pol.policy_type,
            "effective_date": pol.effective_date.isoformat(),
            "expiry_date": pol.expiry_date.isoformat(),
            "coverage_limits": pol.coverage_limits,
            "deductibles": pol.deductibles,
            "exclusions": pol.exclusions,
            "endorsements": pol.endorsements,
            "terms_verified": pol.terms_verified
        },
        change_reason=req.change_reason or "Policy terms modification",
        changed_by_user_id=current_user.id,
        created_at=datetime.datetime.utcnow()
    )
    db.add(new_version)
    db.commit()
    db.refresh(pol)

    p_out = PolicyOut.model_validate(pol)
    if pol.property:
        p_out.property_reference = pol.property.property_reference
        p_out.property_address = pol.property.address
    return p_out

@router.post("/{policy_id}/document", response_model=PolicyOut)
async def upload_policy_document(
    policy_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload policy document (PDF/Image/Text), compute SHA-256 hash, and run term extraction.
    """
    pol = db.query(InsurancePolicy).filter(InsurancePolicy.id == policy_id).first()
    if not pol:
        raise HTTPException(status_code=404, detail="Policy not found")
    _require_policy_access(pol, current_user)

    filename = Path(file.filename or "policy-document").name
    content_type = (file.content_type or "").lower()
    extension = Path(filename).suffix.lower()
    contents = await file.read(MAX_POLICY_FILE_SIZE + 1)
    validate_upload_content(contents, content_type, filename, ALLOWED_POLICY_FILE_TYPES, MAX_POLICY_FILE_SIZE)
    extract_file_metadata(contents, content_type)

    sha256 = hashlib.sha256(contents).hexdigest()
    unique_name = f"policy_{pol.id}_{uuid.uuid4().hex[:8]}{extension}"
    dest_path = settings.UPLOADS_DIR / unique_name
    with open(dest_path, "wb") as f:
        f.write(contents)

    extracted = {
        "extraction_status": "UNAVAILABLE",
        "message": "No PDF text extraction or OCR provider is configured; terms must be entered and verified by an authorized reviewer."
    }

    pol.document_path = unique_name
    pol.document_filename = filename
    pol.document_hash = sha256
    pol.extracted_terms = extracted
    pol.updated_at = datetime.datetime.utcnow()

    next_ver = len(pol.versions) + 1
    db.add(PolicyVersion(
        policy_id=pol.id,
        version_number=next_ver,
        terms_snapshot={
            "policy_number": pol.policy_number,
            "policy_type": pol.policy_type,
            "effective_date": pol.effective_date.isoformat(),
            "expiry_date": pol.expiry_date.isoformat(),
            "coverage_limits": pol.coverage_limits,
            "deductibles": pol.deductibles,
            "exclusions": pol.exclusions,
            "endorsements": pol.endorsements,
            "document_filename": filename,
            "document_hash": sha256,
            "document_path": unique_name,
            "extracted_terms": extracted
        },
        change_reason="Policy document uploaded; prior documents remain in private storage",
        changed_by_user_id=current_user.id
    ))
    db.add(AuditLog(
        user_id=current_user.id,
        entity_type="Policy",
        entity_id=pol.policy_number,
        action="POLICY_DOCUMENT_UPLOADED",
        new_state={"filename": filename, "sha256": sha256},
        notes=f"Policy document uploaded by {current_user.name}",
        timestamp=datetime.datetime.utcnow()
    ))
    try:
        db.commit()
    except Exception:
        db.rollback()
        dest_path.unlink(missing_ok=True)
        raise
    db.refresh(pol)

    p_out = PolicyOut.model_validate(pol)
    if pol.property:
        p_out.property_reference = pol.property.property_reference
        p_out.property_address = pol.property.address
    return p_out

@router.get("/{policy_id}/document")
def download_policy_document(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    policy = db.query(InsurancePolicy).filter(InsurancePolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    _require_policy_access(policy, current_user)
    if not policy.document_path:
        raise HTTPException(status_code=404, detail="No policy document has been uploaded.")
    path = settings.UPLOADS_DIR / Path(policy.document_path).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Policy document is missing from private storage.")
    return FileResponse(path, filename=policy.document_filename or path.name)

@router.post("/{policy_id}/verify-terms", response_model=PolicyOut)
def verify_policy_terms(
    policy_id: int,
    req: PolicyVerificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "reviewer"]))
):
    """
    Allow authorized reviewer to verify and correct extracted policy terms.
    Commits verified terms and marks terms_verified=True.
    """
    pol = db.query(InsurancePolicy).filter(InsurancePolicy.id == policy_id).first()
    if not pol:
        raise HTTPException(status_code=404, detail="Policy not found")
    _require_policy_access(pol, current_user)

    vt = req.verified_terms
    required_terms = {"coverage_limits", "deductibles", "exclusions", "endorsements"}
    if not required_terms.issubset(vt):
        raise HTTPException(
            status_code=400,
            detail="Verification must explicitly include coverage_limits, deductibles, exclusions, and endorsements. Use empty values only when confirmed absent."
        )
    if not isinstance(vt["coverage_limits"], dict) or not isinstance(vt["deductibles"], dict):
        raise HTTPException(status_code=400, detail="Verified coverage_limits and deductibles must be JSON objects.")
    if not isinstance(vt["exclusions"], list) or not isinstance(vt["endorsements"], list):
        raise HTTPException(status_code=400, detail="Verified exclusions and endorsements must be JSON arrays.")
    for amount_map in (vt["coverage_limits"], vt["deductibles"]):
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 for value in amount_map.values()):
            raise HTTPException(status_code=400, detail="Verified coverage and deductible amounts must be finite non-negative numbers.")
    if "coverage_limits" in vt: pol.coverage_limits = vt["coverage_limits"]
    if "deductibles" in vt: pol.deductibles = vt["deductibles"]
    if "exclusions" in vt: pol.exclusions = vt["exclusions"]
    if "endorsements" in vt: pol.endorsements = vt["endorsements"]
    if "policy_type" in vt: pol.policy_type = vt["policy_type"]
    if pol.effective_date >= pol.expiry_date:
        raise HTTPException(status_code=400, detail="Effective date must precede expiry date.")

    pol.terms_verified = True
    pol.notes = f"{pol.notes or ''}\n[Terms Verified by {current_user.name} on {datetime.datetime.utcnow().strftime('%Y-%m-%d')}]: {req.verification_notes or 'Standard verification'}"
    pol.updated_at = datetime.datetime.utcnow()

    # Create version
    next_ver = len(pol.versions) + 1
    new_version = PolicyVersion(
        policy_id=pol.id,
        version_number=next_ver,
        terms_snapshot={
            "coverage_limits": pol.coverage_limits,
            "deductibles": pol.deductibles,
            "exclusions": pol.exclusions,
            "endorsements": pol.endorsements,
            "policy_type": pol.policy_type,
            "effective_date": pol.effective_date.isoformat(),
            "expiry_date": pol.expiry_date.isoformat(),
            "terms_verified": True
        },
        change_reason=f"Human verification: {req.verification_notes or 'Terms verified against document'}",
        changed_by_user_id=current_user.id,
        created_at=datetime.datetime.utcnow()
    )
    db.add(new_version)
    db.add(AuditLog(
        user_id=current_user.id,
        entity_type="Policy",
        entity_id=pol.policy_number,
        action="POLICY_TERMS_VERIFIED",
        new_state={
            "coverage_limits": pol.coverage_limits,
            "deductibles": pol.deductibles,
            "exclusions": pol.exclusions,
            "endorsements": pol.endorsements,
            "terms_verified": True
        },
        notes=req.verification_notes or f"Terms verified by {current_user.name}",
        timestamp=datetime.datetime.utcnow()
    ))
    db.commit()
    db.refresh(pol)

    p_out = PolicyOut.model_validate(pol)
    if pol.property:
        p_out.property_reference = pol.property.property_reference
        p_out.property_address = pol.property.address
    return p_out

@router.get("/{policy_id}/versions", response_model=List[PolicyVersionOut])
def get_policy_versions(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve full chronological version history of a policy."""
    pol = db.query(InsurancePolicy).filter(InsurancePolicy.id == policy_id).first()
    if not pol:
        raise HTTPException(status_code=404, detail="Policy not found")
    _require_policy_access(pol, current_user)
    return pol.versions

@router.get("/{policy_id}/rules", response_model=List[PolicyRuleOut])
def list_available_policy_rules(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all available configurable policy rules."""
    pol = db.query(InsurancePolicy).filter(InsurancePolicy.id == policy_id).first()
    if not pol:
        raise HTTPException(status_code=404, detail="Policy not found")
    _require_policy_access(pol, current_user)
    init_policy_rules_in_db()
    rules = db.query(PolicyRule).filter(PolicyRule.is_active == True).all()
    return rules

@router.put("/rules/{rule_id}", response_model=PolicyRuleOut)
def update_policy_rule(
    rule_id: int,
    req: PolicyRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    rule = db.query(PolicyRule).filter(PolicyRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Policy rule not found")

    changes = req.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="At least one rule field must be supplied.")
    for field, value in changes.items():
        setattr(rule, field, value)
    db.add(AuditLog(
        user_id=current_user.id,
        entity_type="PolicyRule",
        entity_id=rule.rule_code,
        action="POLICY_RULE_UPDATED",
        previous_state=None,
        new_state=changes,
        notes=f"Policy rule {rule.rule_code} updated by {current_user.name}",
        timestamp=datetime.datetime.utcnow()
    ))
    db.commit()
    db.refresh(rule)
    return rule

@router.post("/{policy_id}/evaluate-rules", response_model=List[PolicyRuleExecutionOut])
def evaluate_policy_rules_endpoint(
    policy_id: int,
    req: PolicyRuleEvaluationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Execute the insurance policy rules engine against policy conditions, claims, and modifications.
    Records every rule ID, version, input snapshot, outcome, explanation, and timestamp.
    """
    init_policy_rules_in_db()
    pol = db.query(InsurancePolicy).filter(InsurancePolicy.id == policy_id).first()
    if not pol:
        raise HTTPException(status_code=404, detail="Policy not found")
    _require_policy_access(pol, current_user)

    if req.claim_id:
        claim = db.query(Claim).filter(Claim.id == req.claim_id).first()
        if not claim or claim.policy_id != pol.id:
            raise HTTPException(status_code=400, detail="The claim must be associated with this policy.")
    if req.modification_id:
        modification = db.query(Modification).filter(Modification.id == req.modification_id).first()
        if not modification or modification.property_id != pol.property_id:
            raise HTTPException(status_code=400, detail="The modification alert must belong to this policy's property.")

    custom_inputs = {
        "incident_date": req.incident_date,
        "claimed_amount": req.claimed_amount,
        "cause_of_loss": req.cause_of_loss,
        "has_permit": req.has_permit
    }

    executions = run_policy_rules_pipeline(
        db=db,
        policy_id=pol.id,
        claim_id=req.claim_id,
        modification_id=req.modification_id,
        custom_inputs=custom_inputs
    )
    return executions

@router.get("/{policy_id}/executions", response_model=List[PolicyRuleExecutionOut])
def get_rule_execution_history(
    policy_id: int,
    claim_id: Optional[int] = Query(None),
    modification_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve immutable execution history for policy rules."""
    pol = db.query(InsurancePolicy).filter(InsurancePolicy.id == policy_id).first()
    if not pol:
        raise HTTPException(status_code=404, detail="Policy not found")
    _require_policy_access(pol, current_user)
    query = db.query(PolicyRuleExecution).filter(PolicyRuleExecution.policy_id == policy_id)
    if claim_id:
        query = query.filter(PolicyRuleExecution.claim_id == claim_id)
    if modification_id:
        query = query.filter(PolicyRuleExecution.modification_id == modification_id)

    return query.order_by(desc(PolicyRuleExecution.execution_timestamp)).all()
