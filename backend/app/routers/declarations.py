import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import (
    OwnerDeclaration, Modification, Property, User, Notification, AuditLog
)
from app.schemas import (
    OwnerDeclarationCreate, OwnerDeclarationUpdate, OwnerDeclarationOut,
    NotificationOut
)
from app.auth import get_current_user, require_roles

router = APIRouter(prefix="", tags=["Owner Declarations & Notifications"])

@router.get("/declarations", response_model=List[OwnerDeclarationOut])
def list_declarations(
    property_id: Optional[int] = Query(None),
    modification_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List owner declarations with chronological history.
    Owners see only their declarations; reviewers/admins see all.
    """
    query = db.query(OwnerDeclaration)
    if current_user.role == "owner":
        query = query.filter(OwnerDeclaration.user_id == current_user.id)
    if property_id:
        query = query.filter(OwnerDeclaration.property_id == property_id)
    if modification_id:
        query = query.filter(OwnerDeclaration.modification_id == modification_id)
    if status_filter:
        query = query.filter(OwnerDeclaration.status == status_filter)

    decls = query.order_by(desc(OwnerDeclaration.created_at)).all()
    results = []
    for d in decls:
        d_out = OwnerDeclarationOut.model_validate(d)
        d_out.user_name = d.user.name if d.user else None
        results.append(d_out)
    return results

@router.post("/declarations", response_model=OwnerDeclarationOut, status_code=status.HTTP_201_CREATED)
def submit_owner_declaration(
    req: OwnerDeclarationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Property owner submits formal declaration regarding a suspected modification.
    Options:
    - CONFIRM: Confirm physical alteration with permit/contractor details.
    - DISPUTE: Dispute detection (e.g. temporary shadow, seasonal lawn, false positive).
    - EXPLAIN: Explain nature of work (e.g. maintenance, minor repair, non-structural change).
    """
    prop = db.query(Property).filter(Property.id == req.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if current_user.role == "owner" and prop.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied. You do not own this property.")
    if current_user.role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="Only a property owner may submit an owner declaration.")

    mod = None
    if req.modification_id:
        mod = db.query(Modification).filter(Modification.id == req.modification_id).first()
        if not mod:
            raise HTTPException(status_code=404, detail="Modification alert not found")
        if mod.property_id != prop.id:
            raise HTTPException(status_code=400, detail="The modification alert must belong to the declared property.")

    decl = OwnerDeclaration(
        property_id=prop.id,
        modification_id=mod.id if mod else None,
        user_id=current_user.id,
        declaration_type=req.declaration_type,
        statement=req.statement,
        permit_number=req.permit_number,
        contractor_name=req.contractor_name,
        completion_date=req.completion_date,
        status="Submitted",
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow()
    )
    db.add(decl)

    # If modification alert linked, update status to 'Under Review'
    if mod and mod.status in ["New", "Awaiting Evidence"]:
        mod.status = "Under Review"
        mod.updated_at = datetime.datetime.utcnow()

    # Log audit
    audit = AuditLog(
        user_id=current_user.id,
        entity_type="Modification" if mod else "Property",
        entity_id=mod.modification_alert_id if mod else prop.property_reference,
        action="OWNER_DECLARATION_SUBMITTED",
        new_state={
            "declaration_type": req.declaration_type,
            "permit_number": req.permit_number
        },
        notes=f"Owner submitted {req.declaration_type} declaration: {req.statement[:80]}...",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(audit)

    # Notify reviewers
    reviewers = db.query(User).filter(User.role.in_(["admin", "reviewer"])).all()
    for r in reviewers:
        notif = Notification(
            user_id=r.id,
            title=f"Owner Declaration: {prop.property_reference}",
            message=f"{current_user.name} submitted a {req.declaration_type} declaration for {prop.property_reference}.",
            type="MODIFICATION_ALERT",
            link=f"/modifications/{mod.id}" if mod else f"/properties/{prop.id}",
            created_at=datetime.datetime.utcnow()
        )
        db.add(notif)

    db.commit()
    db.refresh(decl)

    d_out = OwnerDeclarationOut.model_validate(decl)
    d_out.user_name = current_user.name
    return d_out

@router.put("/declarations/{declaration_id}", response_model=OwnerDeclarationOut)
def review_owner_declaration(
    declaration_id: int,
    req: OwnerDeclarationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "reviewer"]))
):
    """Reviewer responds to or verifies an owner declaration."""
    decl = db.query(OwnerDeclaration).filter(OwnerDeclaration.id == declaration_id).first()
    if not decl:
        raise HTTPException(status_code=404, detail="Declaration not found")

    allowed_statuses = {"Submitted", "Under Review", "Verified", "Additional Info Requested"}
    if req.status and req.status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Invalid declaration review status.")
    if req.status: decl.status = req.status
    if req.reviewer_response: decl.reviewer_response = req.reviewer_response
    decl.updated_at = datetime.datetime.utcnow()

    # Notify owner
    notif = Notification(
        user_id=decl.user_id,
        title=f"Declaration Update: {decl.property.property_reference}",
        message=f"Reviewer responded: {req.reviewer_response or 'Declaration reviewed and status updated.'}",
        type="RFI_REQUEST",
        link=f"/properties/{decl.property_id}",
        created_at=datetime.datetime.utcnow()
    )
    db.add(notif)
    db.add(AuditLog(
        user_id=current_user.id,
        entity_type="OwnerDeclaration",
        entity_id=str(decl.id),
        action="OWNER_DECLARATION_REVIEWED",
        new_state={"status": decl.status, "reviewer_response": req.reviewer_response},
        notes=f"Declaration reviewed by {current_user.name}",
        timestamp=datetime.datetime.utcnow()
    ))
    db.commit()
    db.refresh(decl)

    d_out = OwnerDeclarationOut.model_validate(decl)
    d_out.user_name = decl.user.name if decl.user else None
    return d_out

@router.get("/notifications", response_model=List[NotificationOut])
def get_user_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve notifications and alerts for the currently authenticated user."""
    return db.query(Notification).filter(Notification.user_id == current_user.id).order_by(desc(Notification.created_at)).limit(30).all()

@router.put("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark a notification as read."""
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif
