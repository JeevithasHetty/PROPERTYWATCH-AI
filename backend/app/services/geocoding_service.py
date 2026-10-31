import time
import logging
import threading
from typing import Dict, Any, Optional
import requests
from app.config import settings

logger = logging.getLogger(__name__)

_GEOCODE_CACHE: Dict[str, Dict[str, Any]] = {}
_LAST_REQUEST_TIME = 0.0
_LOCK = threading.Lock()


class GeocodingError(Exception):
    """Raised when an address cannot be geocoded. Never replaced by invented coordinates."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


# Illustrative Indian addresses used ONLY in DEMO_MODE when Nominatim is unreachable.
# Coordinates are real city-centre locations; the street addresses are fictional.
DEMO_COORDINATES = {
    "bandra west, mumbai": ("Bandra West, Mumbai, Maharashtra 400050, India", 19.0596, 72.8295, "Mumbai", "Maharashtra", "400050"),
    "indiranagar, bengaluru": ("Indiranagar, Bengaluru, Karnataka 560038, India", 12.9784, 77.6408, "Bengaluru", "Karnataka", "560038"),
    "jubilee hills, hyderabad": ("Jubilee Hills, Hyderabad, Telangana 500033, India", 17.4326, 78.4071, "Hyderabad", "Telangana", "500033"),
    "t nagar, chennai": ("T. Nagar, Chennai, Tamil Nadu 600017, India", 13.0418, 80.2341, "Chennai", "Tamil Nadu", "600017"),
    "connaught place, new delhi": ("Connaught Place, New Delhi, Delhi 110001, India", 28.6315, 77.2167, "New Delhi", "Delhi", "110001"),
}


def _in_india(lat: float, lon: float) -> bool:
    s, w, n, e = settings.INDIA_BBOX
    return s <= lat <= n and w <= lon <= e


def _result(query, display, lat, lon, city, state, pin, source, extra=None):
    res = {
        "query": query, "display_name": display, "latitude": lat, "longitude": lon,
        "city": city, "state": state, "postal_code": pin, "country": "India", "source": source,
    }
    if extra:
        res.update(extra)
    return res


def _candidate_queries(cleaned: str) -> list:
    """Progressively coarser queries. Nominatim rarely knows Indian house numbers / 'Nth main' roads."""
    import re
    out = [cleaned]
    no_house = re.sub(r"^\s*(?:#|no\.?|plot|flat|door)?\s*[\w/-]*\d[\w/-]*\s*[,.\-]?\s*", "", cleaned, flags=re.I)
    no_house = re.sub(r"\b\d+(?:st|nd|rd|th)?\s*(?:main|cross|block|phase|stage|sector)\b[,\s]*", "", no_house, flags=re.I)
    no_house = re.sub(r"\s+", " ", no_house).strip(" ,")
    if no_house and no_house.lower() != cleaned.lower():
        out.append(no_house)
    parts = [p.strip() for p in re.split(r",", cleaned) if p.strip()]
    pin_m = re.search(r"\b\d{6}\b", cleaned)
    pin = pin_m.group(0) if pin_m else None
    locality = re.sub(r"^\s*(?:#|no\.?)?\s*\d+[\w/-]*\s*,?\s*", "", parts[0], flags=re.I) if parts else ""
    locality = re.sub(r"\b\d+(?:st|nd|rd|th)?\s*(?:main|cross|block|phase|stage)\b", "", locality, flags=re.I).strip(" ,")
    tail = " ".join(parts[1:])
    if locality and tail:
        out.append(f"{locality}, {tail}")
    if pin:
        out.append(f"{pin}, India" if not tail else f"{pin} {re.sub(pin, '', tail).strip()}")
    seen, uniq = set(), []
    for q in out:
        k = q.lower().strip()
        if k and k not in seen:
            seen.add(k)
            uniq.append(q.strip())
    return uniq[:5]


def _nominatim_once(query: str):
    """One rate-limited Nominatim request. Returns first hit dict or None; raises requests errors."""
    global _LAST_REQUEST_TIME
    params = {"q": query, "format": "jsonv2", "addressdetails": 1, "limit": 1,
              "countrycodes": settings.DEFAULT_COUNTRY_CODE, "accept-language": "en"}
    headers = {"User-Agent": settings.NOMINATIM_USER_AGENT, "Accept": "application/json"}
    with _LOCK:
        wait = 1.05 - (time.time() - _LAST_REQUEST_TIME)
        if wait > 0:
            time.sleep(wait)
        try:
            response = requests.get(settings.NOMINATIM_URL, params=params, headers=headers, timeout=8.0)
        finally:
            _LAST_REQUEST_TIME = time.time()
    if response.status_code != 200:
        raise requests.RequestException(f"Nominatim returned HTTP {response.status_code}")
    data = response.json()
    return data[0] if data else None


def geocode_address(address: str) -> Dict[str, Any]:
    """
    Geocode an Indian address with OpenStreetMap Nominatim (countrycodes=in, 1 req/sec, cached).
    If the full address has no match, coarser queries are tried (without house number / 'Nth main',
    then locality + city + PIN). Coarser matches are returned with precision="approximate" so the
    user can place the pin manually. Coordinates are never invented.
    """
    cleaned = " ".join(address.split())
    cache_key = cleaned.lower()
    if cache_key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[cache_key]

    network_error: Optional[str] = None
    reachable = False
    outside_india = False
    for i, query in enumerate(_candidate_queries(cleaned)):
        try:
            hit = _nominatim_once(query)
        except requests.RequestException as exc:
            network_error = f"Nominatim unreachable: {exc.__class__.__name__}"
            break
        reachable = True
        if not hit:
            continue
        addr = hit.get("address", {})
        lat, lon = float(hit["lat"]), float(hit["lon"])
        if not _in_india(lat, lon):
            outside_india = True
            continue
        result = _result(
            address, hit.get("display_name", cleaned), lat, lon,
            addr.get("city") or addr.get("town") or addr.get("village") or addr.get("suburb") or addr.get("state_district"),
            addr.get("state"), addr.get("postcode"),
            "OpenStreetMap Nominatim (live)" if i == 0 else f"OpenStreetMap Nominatim (live, approximate: matched '{query}')",
            {"osm_type": hit.get("osm_type"), "osm_id": hit.get("osm_id"),
             "precision": "exact" if i == 0 else "approximate", "matched_query": query},
        )
        _GEOCODE_CACHE[cache_key] = result
        return result

    if outside_india and not network_error:
        raise GeocodingError("The address resolved to a location outside India. PropertyWatch AI currently supports Indian properties only.", 422)
    if reachable and not network_error:
        raise GeocodingError(
            f"OpenStreetMap has no match for '{cleaned}' in India, even at locality/PIN level. "
            "Search the area name (e.g. 'Jakkur, Bengaluru') and then click the map to place the pin exactly.", 404)

    if settings.DEMO_MODE:
        for key, (display, lat, lon, city, state, pin) in DEMO_COORDINATES.items():
            if key in cache_key or all(tok in cache_key for tok in key.replace(",", " ").split()):
                return _result(address, display, lat, lon, city, state, pin,
                               "DEMO DATA - offline Indian city-centre fallback (not a street-level match)",
                               {"precision": "approximate"})
    raise GeocodingError(f"Geocoding unavailable: {network_error}", 502)
