import os
import uuid
import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from app.database import get_db
from app.config import settings
from app.models import Property, PropertySnapshot, Modification, Review, AuditLog, User
from app.schemas import PropertyCreate, PropertyUpdate, PropertyOut, PropertyDetailOut, PropertySnapshotOut
from app.auth import get_current_user
from app.services.file_validation import extract_file_metadata, validate_upload_content

router = APIRouter(prefix="/properties", tags=["Properties"])

def private_snapshot_url(snapshot: PropertySnapshot) -> str:
    return f"/api/properties/{snapshot.property_id}/snapshots/{snapshot.id}/image"


def is_owner_uploaded_snapshot(snapshot: PropertySnapshot) -> bool:
    return snapshot.image_source == "User Ground Baseline Photograph"


def generate_property_reference(db: Session) -> str:
    """Generate unique collision-resistant property reference: PROP-XXXX."""
    count = db.query(Property).count()
    year = datetime.datetime.utcnow().year
    candidate = f"PROP-{year}-{1001 + count}"
    # Verify uniqueness
    while db.query(Property).filter(Property.property_reference == candidate).first():
        count += 1
        candidate = f"PROP-{year}-{1001 + count}"
    return candidate

@router.get("", response_model=List[PropertyOut])
def list_properties(
    search: Optional[str] = Query(None, description="Search by address, owner, reference, or policy"),
    property_type: Optional[str] = Query(None, description="Filter by property type"),
    monitoring_enabled: Optional[bool] = Query(None, description="Filter by active monitoring"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve all registered properties with filtering, search, and summary counts."""
    query = db.query(Property)
    if current_user.role == "owner":
        query = query.filter(Property.owner_user_id == current_user.id)

    if search:
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Property.address.ilike(search_filter),
                Property.owner_name.ilike(search_filter),
                Property.property_reference.ilike(search_filter),
                Property.reference_policy_number.ilike(search_filter)
            )
        )

    if property_type:
        query = query.filter(Property.property_type == property_type)

    if monitoring_enabled is not None:
        query = query.filter(Property.monitoring_enabled == monitoring_enabled)

    properties = query.order_by(desc(Property.created_at)).offset(skip).limit(limit).all()

    # Populate summary counts
    results = []
    for prop in properties:
        open_alerts = db.query(Modification).filter(
            Modification.property_id == prop.id,
            Modification.status.in_(["New", "Awaiting Evidence", "Under Review", "Additional Evidence Required"])
        ).count()

        verified_mods = db.query(Modification).filter(
            Modification.property_id == prop.id,
            Modification.status == "Verified"
        ).count()

        prop_out = PropertyOut.model_validate(prop)
        baseline_snapshot = db.query(PropertySnapshot).filter(
            PropertySnapshot.property_id == prop.id,
            PropertySnapshot.is_baseline.is_(True),
            PropertySnapshot.image_source == "User Ground Baseline Photograph"
        ).order_by(desc(PropertySnapshot.acquisition_date)).first()
        if baseline_snapshot:
            prop_out.baseline_image_url = private_snapshot_url(baseline_snapshot)
        prop_out.open_alerts_count = open_alerts
        prop_out.verified_modifications_count = verified_mods
        results.append(prop_out)

    return results

@router.post("", response_model=PropertyOut, status_code=status.HTTP_201_CREATED)
def create_property(
    prop_in: PropertyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Register a new property after geocoding coordinates confirmation."""
    ref = prop_in.property_reference or generate_property_reference(db)

    # Check unique reference
    existing = db.query(Property).filter(Property.property_reference == ref).first()
    if existing:
        ref = generate_property_reference(db)

    if current_user.role == "owner" and prop_in.owner_user_id not in [None, current_user.id]:
        raise HTTPException(status_code=403, detail="Owners cannot register property records for another owner.")
    if prop_in.owner_user_id and current_user.role not in ["admin", "manager", "owner"]:
        raise HTTPException(status_code=403, detail="Only administrators or managers may assign a property owner.")
    owner_user_id = current_user.id if current_user.role == "owner" else prop_in.owner_user_id
    if owner_user_id and not db.query(User).filter(User.id == owner_user_id, User.role == "owner").first():
        raise HTTPException(status_code=400, detail="The assigned property owner must be an owner account.")

    prop = Property(
        property_reference=ref,
        owner_name=prop_in.owner_name,
        owner_contact=prop_in.owner_contact,
        owner_user_id=owner_user_id,
        address=prop_in.address,
        city=prop_in.city,
        state=prop_in.state,
        postal_code=prop_in.postal_code,
        latitude=prop_in.latitude,
        longitude=prop_in.longitude,
        property_type=prop_in.property_type,
        number_of_floors=prop_in.number_of_floors,
        built_up_area=prop_in.built_up_area,
        reference_policy_number=prop_in.reference_policy_number,
        monitoring_enabled=prop_in.monitoring_enabled,
        notes=prop_in.notes,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow()
    )
    db.add(prop)
    db.flush()

    from app.models import PropertyVersion
    db.add(PropertyVersion(
        property_id=prop.id,
        version_number=1,
        attributes_snapshot={
            "property_reference": prop.property_reference,
            "owner_name": prop.owner_name,
            "owner_contact": prop.owner_contact,
            "owner_user_id": prop.owner_user_id,
            "address": prop.address,
            "city": prop.city,
            "state": prop.state,
            "postal_code": prop.postal_code,
            "latitude": prop.latitude,
            "longitude": prop.longitude,
            "property_type": prop.property_type,
            "number_of_floors": prop.number_of_floors,
            "built_up_area": prop.built_up_area
        },
        change_reason="Initial property registration",
        changed_by_user_id=current_user.id,
        created_at=datetime.datetime.utcnow()
    ))

    # Record Audit Log
    audit = AuditLog(
        user_id=current_user.id,
        entity_type="Property",
        entity_id=str(prop.id),
        action="PROPERTY_REGISTERED",
        new_state={"reference": prop.property_reference, "address": prop.address, "owner": prop.owner_name},
        notes=f"Property registered by {current_user.name} ({current_user.role})"
    )
    db.add(audit)
    db.commit()
    db.refresh(prop)

    return PropertyOut.model_validate(prop)

@router.get("/{property_id}", response_model=PropertyDetailOut)
def get_property_detail(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve full details of a property including snapshots, alerts, and audit trail."""
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if current_user.role == "owner" and prop.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property.")
    if current_user.role == "owner" and prop.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property.")

    snapshots = db.query(PropertySnapshot).filter(PropertySnapshot.property_id == property_id).order_by(desc(PropertySnapshot.acquisition_date)).all()
    modifications = db.query(Modification).filter(Modification.property_id == property_id).order_by(desc(Modification.created_at)).all()
    audit_logs = db.query(AuditLog).filter(AuditLog.entity_type == "Property", AuditLog.entity_id == str(property_id)).order_by(desc(AuditLog.timestamp)).all()

    # Calculate counts
    verified_mods = sum(1 for m in modifications if m.status == "Verified")
    open_alerts = sum(1 for m in modifications if m.status in ["New", "Awaiting Evidence", "Under Review", "Additional Evidence Required"])

    prop_out = PropertyDetailOut.model_validate(prop)
    prop_out.verified_modifications_count = verified_mods
    prop_out.open_alerts_count = open_alerts
    prop_out.snapshots = [PropertySnapshotOut.model_validate(s) for s in snapshots]
    for snapshot_out, snapshot in zip(prop_out.snapshots, snapshots):
        if is_owner_uploaded_snapshot(snapshot):
            snapshot_out.image_path = private_snapshot_url(snapshot)
            if snapshot.is_baseline:
                prop_out.baseline_image_url = snapshot_out.image_path
    prop_out.modifications = modifications
    prop_out.audit_logs = audit_logs

    if prop.policy:
        from app.schemas import PolicyOut
        pol_out = PolicyOut.model_validate(prop.policy)
        pol_out.property_reference = prop.property_reference
        pol_out.property_address = prop.address
        prop_out.policy = pol_out

    if prop.versions:
        from app.schemas import PropertyVersionOut
        prop_out.versions = [PropertyVersionOut.model_validate(v) for v in prop.versions]

    if prop.declarations:
        from app.schemas import OwnerDeclarationOut
        prop_out.declarations = [OwnerDeclarationOut.model_validate(d) for d in prop.declarations]

    return prop_out

@router.put("/{property_id}", response_model=PropertyOut)
def update_property(
    property_id: int,
    prop_in: PropertyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update property details with audit logging."""
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if current_user.role == "owner" and prop.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property.")

    prev_state = {
        "owner_name": prop.owner_name,
        "address": prop.address,
        "property_type": prop.property_type,
        "number_of_floors": prop.number_of_floors,
        "built_up_area": prop.built_up_area,
        "monitoring_enabled": prop.monitoring_enabled
    }

    update_data = prop_in.model_dump(exclude_unset=True)
    if current_user.role == "owner" and "owner_user_id" in update_data:
        raise HTTPException(status_code=403, detail="Property ownership cannot be reassigned by an owner.")
    for field, value in update_data.items():
        setattr(prop, field, value)

    prop.updated_at = datetime.datetime.utcnow()

    # Commit new PropertyVersion
    from app.models import PropertyVersion
    next_ver = len(prop.versions) + 1
    p_ver = PropertyVersion(
        property_id=prop.id,
        version_number=next_ver,
        attributes_snapshot={
            "owner_name": prop.owner_name,
            "address": prop.address,
            "property_type": prop.property_type,
            "number_of_floors": prop.number_of_floors,
            "built_up_area": prop.built_up_area,
            "reference_policy_number": prop.reference_policy_number,
            "monitoring_enabled": prop.monitoring_enabled
        },
        change_reason=f"Property attributes updated: {', '.join(update_data.keys())}",
        changed_by_user_id=current_user.id,
        created_at=datetime.datetime.utcnow()
    )
    db.add(p_ver)

    # Log audit
    audit = AuditLog(
        user_id=current_user.id,
        entity_type="Property",
        entity_id=str(prop.id),
        action="PROPERTY_UPDATED",
        previous_state=prev_state,
        new_state=update_data,
        notes=f"Property updated by {current_user.name}"
    )
    db.add(audit)
    db.commit()
    db.refresh(prop)

    return PropertyOut.model_validate(prop)

@router.get("/{property_id}/history")
def get_property_chronological_history(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve unified chronological history of property events:
    Registration, Imagery acquisition, Modification alerts, Human verification decisions.
    """
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if current_user.role == "owner" and prop.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property.")

    timeline = []

    # 1. Registration event
    timeline.append({
        "event_type": "REGISTRATION",
        "title": "Property Initial Registration",
        "description": f"Registered at {prop.address} with reference {prop.property_reference}.",
        "timestamp": prop.created_at.isoformat(),
        "actor": "System / Property Manager",
        "badge_color": "blue"
    })

    # 2. Snapshots
    snapshots = db.query(PropertySnapshot).filter(PropertySnapshot.property_id == property_id).all()
    for s in snapshots:
        timeline.append({
            "event_type": "SNAPSHOT",
            "title": f"{'Baseline' if s.is_baseline else 'New'} Satellite Snapshot Acquired",
            "description": f"Acquired from {s.image_source} with {s.cloud_coverage}% cloud cover.",
            "timestamp": s.acquisition_date.isoformat(),
            "actor": "Satellite Monitoring Service",
            "image_url": private_snapshot_url(s) if is_owner_uploaded_snapshot(s) else s.image_path,
            "badge_color": "teal"
        })

    # 3. Modifications & Reviews
    mods = db.query(Modification).filter(Modification.property_id == property_id).all()
    for m in mods:
        timeline.append({
            "event_type": "ALERT",
            "title": f"Modification Alert Flagged ({m.modification_alert_id})",
            "description": f"Category: {m.suspected_category}. Change Score: {m.change_score}%.",
            "timestamp": m.detected_at.isoformat(),
            "actor": "AI Computer Vision Pipeline",
            "badge_color": "amber"
        })

        if m.verified_at:
            timeline.append({
                "event_type": "VERIFICATION",
                "title": f"Modification Human Verified ({m.modification_alert_id})",
                "description": f"Verified change: {m.suspected_category}. Decision Reason: {m.decision_reason or 'Corroborated by documentation'}",
                "timestamp": m.verified_at.isoformat(),
                "actor": m.reviewer.name if m.reviewer else "Authorized Reviewer",
                "badge_color": "green" if m.status == "Verified" else "red"
            })

    # Sort descending by timestamp
    timeline.sort(key=lambda x: x["timestamp"], reverse=True)

    return {
        "property_id": prop.id,
        "property_reference": prop.property_reference,
        "timeline": timeline
    }

@router.post("/{property_id}/baseline-photo")
async def upload_baseline_photo(
    property_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a baseline photograph for the property and register it as baseline snapshot."""
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if current_user.role == "owner" and prop.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property.")

    # Validate file type
    allowed_types = {"image/jpeg": {".jpg", ".jpeg"}, "image/png": {".png"}, "image/webp": {".webp"}}
    filename = Path(file.filename or "baseline-image").name
    content_type = (file.content_type or "").lower()
    contents = await file.read(20 * 1024 * 1024 + 1)
    validate_upload_content(contents, content_type, filename, allowed_types, 20 * 1024 * 1024)
    capture_metadata = extract_file_metadata(contents, content_type)

    # Generate safe filename
    ext = Path(filename).suffix.lower()
    safe_filename = f"baseline_{property_id}_{uuid.uuid4().hex[:8]}{ext}"
    dest_path = settings.UPLOADS_DIR / safe_filename

    with open(dest_path, "wb") as f:
        f.write(contents)

    relative_url = f"/private/uploads/{safe_filename}"

    # Create baseline snapshot record
    snapshot = PropertySnapshot(
        property_id=prop.id,
        image_path=relative_url,
        image_source="User Ground Baseline Photograph",
        acquisition_date=datetime.datetime.utcnow(),
        cloud_coverage=0.0,
        is_baseline=True,
        capture_metadata={
            **capture_metadata,
            "original_filename": filename,
            "uploaded_by": current_user.name,
            "storage_filename": safe_filename
        }
    )
    db.add(snapshot)
    db.flush()
    image_url = f"/api/properties/{prop.id}/snapshots/{snapshot.id}/image"
    snapshot.image_path = image_url
    prop.baseline_image_url = image_url

    audit = AuditLog(
        user_id=current_user.id,
        entity_type="Property",
        entity_id=str(prop.id),
        action="BASELINE_PHOTO_UPLOADED",
        new_state={"baseline_image_url": image_url},
        notes=f"Baseline photo uploaded by {current_user.name}"
    )
    db.add(audit)
    try:
        db.commit()
    except Exception:
        db.rollback()
        dest_path.unlink(missing_ok=True)
        raise

    return {"message": "Baseline photo uploaded successfully", "image_url": image_url, "snapshot_id": snapshot.id}


@router.get("/{property_id}/snapshots/{snapshot_id}/image")
def download_property_snapshot_image(
    property_id: int,
    snapshot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    prop = db.query(Property).filter(Property.id == property_id).first()
    snapshot = db.query(PropertySnapshot).filter(
        PropertySnapshot.id == snapshot_id,
        PropertySnapshot.property_id == property_id
    ).first()
    if not prop or not snapshot:
        raise HTTPException(status_code=404, detail="Property snapshot not found.")
    if current_user.role == "owner" and prop.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property's imagery.")
    filename = Path((snapshot.capture_metadata or {}).get("storage_filename", "")).name
    if filename:
        image_path = settings.UPLOADS_DIR / filename
    elif is_owner_uploaded_snapshot(snapshot) and snapshot.image_path.startswith("/static/snapshots/"):
        image_path = settings.SNAPSHOTS_DIR / Path(snapshot.image_path).name
    else:
        raise HTTPException(status_code=404, detail="Snapshot is not stored as a private upload.")
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot image is missing from private storage.")
    return FileResponse(path=str(image_path), media_type=snapshot.capture_metadata.get("mime_type", "application/octet-stream"))
