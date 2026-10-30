from fastapi import APIRouter, Depends, HTTPException
from app.schemas import GeocodeRequest, GeocodeResponse
from app.services.geocoding_service import geocode_address
from app.auth import get_current_user
from app.models import User

router = APIRouter(prefix="/geocode", tags=["Geocoding"])

@router.post("", response_model=GeocodeResponse)
def geocode_property_address(
    req: GeocodeRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Geocode an address to latitude and longitude using OpenStreetMap Nominatim.
    Includes rate-limiting compliance (1 req/sec) and local caching.
    """
    if not req.address or len(req.address.strip()) < 3:
        raise HTTPException(status_code=400, detail="Address query string is too short.")

    try:
        result = geocode_address(req.address)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Geocoding service error: {str(e)}")
