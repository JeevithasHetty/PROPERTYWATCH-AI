from fastapi import APIRouter, Depends, HTTPException
from app.schemas import GeocodeRequest, GeocodeResponse
from app.services.geocoding_service import geocode_address, GeocodingError
from app.auth import get_current_user
from app.models import User

router = APIRouter(prefix="/geocode", tags=["Geocoding"])


@router.post("", response_model=GeocodeResponse)
def geocode_property_address(req: GeocodeRequest, current_user: User = Depends(get_current_user)):
    """Geocode an Indian address via OpenStreetMap Nominatim (1 req/sec, cached, countrycodes=in)."""
    if not req.address or len(req.address.strip()) < 3:
        raise HTTPException(status_code=400, detail="Address query string is too short.")
    try:
        return geocode_address(req.address)
    except GeocodingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
