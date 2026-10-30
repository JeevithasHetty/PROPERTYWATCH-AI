import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import Property, PropertySnapshot, AuditLog, User
from app.schemas import SatelliteSearchResultItem, SatelliteRetrieveRequest, PropertySnapshotOut
from app.services.satellite_service import satellite_service
from app.auth import get_current_user

router = APIRouter(prefix="/satellite", tags=["Satellite Monitoring"])

@router.get("/search", response_model=List[SatelliteSearchResultItem])
def search_satellite_imagery(
    property_id: Optional[int] = Query(None),
    latitude: Optional[float] = Query(None),
    longitude: Optional[float] = Query(None),
    start_date: str = Query(..., description="Start Date YYYY-MM-DD"),
    end_date: str = Query(..., description="End Date YYYY-MM-DD"),
    max_cloud_cover: float = Query(25.0, description="Max acceptable cloud percentage"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search Copernicus Data Space / Sentinel Hub catalogue for optical satellite passes.
    Accepts property coordinates or looks up coordinates from registered property.
    """
    lat, lon = latitude, longitude
    if property_id:
        prop = db.query(Property).filter(Property.id == property_id).first()
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
        lat, lon = prop.latitude, prop.longitude

    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="Latitude and longitude coordinates are required.")

    # Validate date range
    try:
        s_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        e_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        if s_dt > e_dt:
            raise HTTPException(status_code=400, detail="Start date must precede or equal end date.")
    except ValueError:
        raise HTTPException(status_code=400, detail="Dates must be in YYYY-MM-DD format.")

    results = satellite_service.search_imagery(
        latitude=lat,
        longitude=lon,
        start_date=start_date,
        end_date=end_date,
        max_cloud_cover=max_cloud_cover
    )
    return results

@router.post("/retrieve", response_model=PropertySnapshotOut)
def retrieve_satellite_snapshot(
    req: SatelliteRetrieveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve and persist an optical satellite snapshot tile for a registered property.
    Verifies duplicate snapshots are not created for the same acquisition date.
    """
    prop = db.query(Property).filter(Property.id == req.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    # Check for duplicate snapshot on this date
    try:
        acq_dt = datetime.datetime.strptime(req.acquisition_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid acquisition date format (YYYY-MM-DD required).")

    existing_snapshot = db.query(PropertySnapshot).filter(
        PropertySnapshot.property_id == prop.id,
        PropertySnapshot.acquisition_date == acq_dt
    ).first()

    if existing_snapshot:
        raise HTTPException(
            status_code=409,
            detail=f"A snapshot for date {req.acquisition_date} already exists for this property (Snapshot ID: {existing_snapshot.id})."
        )

    # Determine feature hint based on whether baseline exists
    has_baseline = db.query(PropertySnapshot).filter(
        PropertySnapshot.property_id == prop.id,
        PropertySnapshot.is_baseline == True
    ).first()

    feature_hint = "baseline"
    if has_baseline and not req.is_baseline:
        # For demo purposes, pick a modification feature if newer date
        if "solar" in prop.property_reference.lower() or "solar" in prop.address.lower() or prop.id % 3 == 0:
            feature_hint = "solar"
        elif "pool" in prop.property_reference.lower() or "pool" in prop.address.lower() or prop.id % 3 == 1:
            feature_hint = "pool"
        else:
            feature_hint = "extension"

    retrieval_res = satellite_service.retrieve_imagery(
        catalog_id=req.catalog_id,
        acquisition_date=req.acquisition_date,
        satellite_name=req.satellite_name,
        latitude=prop.latitude,
        longitude=prop.longitude,
        feature_hint=feature_hint
    )

    snapshot = PropertySnapshot(
        property_id=prop.id,
        image_path=retrieval_res["image_path"],
        image_source=retrieval_res["image_source"],
        acquisition_date=retrieval_res["acquisition_date"],
        cloud_coverage=req.cloud_coverage or retrieval_res["cloud_coverage"],
        is_baseline=req.is_baseline,
        capture_metadata=retrieval_res["capture_metadata"]
    )
    db.add(snapshot)

    # If this is set as baseline or no baseline exists yet, set baseline
    if req.is_baseline or not prop.baseline_image_url:
        prop.baseline_image_url = retrieval_res["image_path"]

    prop.last_monitoring_date = datetime.datetime.utcnow()
    db.commit()
    db.refresh(snapshot)

    # Record Audit Log
    audit = AuditLog(
        user_id=current_user.id,
        entity_type="PropertySnapshot",
        entity_id=str(snapshot.id),
        action="SATELLITE_SNAPSHOT_RETRIEVED",
        new_state={
            "property_id": prop.id,
            "acquisition_date": req.acquisition_date,
            "satellite": req.satellite_name,
            "is_baseline": snapshot.is_baseline
        },
        notes=f"Retrieved satellite tile {req.catalog_id} by {current_user.name}"
    )
    db.add(audit)
    db.commit()

    return snapshot

@router.get("/properties/{property_id}/snapshots", response_model=List[PropertySnapshotOut])
def get_property_snapshots(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all satellite and aerial snapshots stored for a given property."""
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    snapshots = db.query(PropertySnapshot).filter(
        PropertySnapshot.property_id == property_id
    ).order_by(desc(PropertySnapshot.acquisition_date)).all()

    return snapshots
