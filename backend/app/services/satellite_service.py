"""
Satellite imagery service.

Live providers (real imagery, real authentication):
  * Copernicus Data Space Ecosystem (CDSE) - OAuth2 client-credentials -> Sentinel Hub Catalog (STAC)
    search + Process API download of Sentinel-2 L2A true-colour tiles.
  * Google Earth Engine - service-account authentication, COPERNICUS/S2_SR_HARMONIZED search and
    thumbnail download.

DEMO_MODE only: a clearly watermarked synthetic tile generator (data_origin = DEMO_SYNTHETIC).
In live mode nothing synthetic is ever produced; if no provider is configured a
SatelliteUnavailableError explains exactly which credentials are missing.
"""
import math
import time
import uuid
import logging
import datetime
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
import cv2
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

try:  # optional dependency
    import ee  # type: ignore
    HAS_EE = True
except ImportError:  # pragma: no cover
    ee = None
    HAS_EE = False

ORIGIN_LIVE = "SATELLITE_LIVE"
ORIGIN_DEMO = "DEMO_SYNTHETIC"

# True-colour evalscript for Sentinel-2 L2A (reflectance gain 2.5)
_EVALSCRIPT = """//VERSION=3
function setup(){return{input:["B04","B03","B02","dataMask"],output:{bands:4}};}
function evaluatePixel(s){var g=2.5;return [g*s.B04,g*s.B03,g*s.B02,s.dataMask];}"""


class SatelliteUnavailableError(Exception):
    """No live provider is usable. Message states exactly what is missing."""


class SatelliteProviderError(Exception):
    """A configured provider rejected the request or failed."""


def bbox_for(lat: float, lon: float, half_size_m: float) -> List[float]:
    dlat = half_size_m / 111_320.0
    dlon = half_size_m / (111_320.0 * max(0.01, math.cos(math.radians(lat))))
    return [round(lon - dlon, 6), round(lat - dlat, 6), round(lon + dlon, 6), round(lat + dlat, 6)]


def _save_png(img_bgr_or_bgra: np.ndarray, prefix: str, date_str: str) -> Path:
    name = f"{prefix}_{date_str}_{uuid.uuid4().hex[:8]}.png"
    path = settings.SNAPSHOTS_DIR / name
    if not cv2.imwrite(str(path), img_bgr_or_bgra):
        raise SatelliteProviderError("Could not write downloaded imagery to disk.")
    return path


# --------------------------------------------------------------------------- demo generator
def generate_synthetic_satellite_tile(
    date_str: str, feature_type: str = "baseline", lat: float = 19.0760, lon: float = 72.8777
) -> str:
    """DEMO ONLY. Synthetic tile, watermarked as such. Never used when DEMO_MODE is off."""
    width = height = 800
    np.random.seed(int(abs(lat * 1000 + lon * 100)) % 100000)
    base = np.full((height, width, 3), [68, 115, 62], dtype=np.uint8)
    noise = np.random.normal(0, 8, (height, width, 3)).astype(np.int16)
    t = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    cv2.rectangle(t, (0, 680), (800, 800), (60, 60, 65), -1)
    for x in range(20, 800, 60):
        cv2.line(t, (x, 740), (x + 30, 740), (200, 200, 200), 2)
    cv2.rectangle(t, (460, 480), (520, 680), (140, 140, 145), -1)
    for tx, ty in [(120, 180), (160, 260), (680, 150), (710, 240), (130, 520), (690, 550)]:
        cv2.circle(t, (tx, ty), 45, (34, 75, 28), -1)
        cv2.circle(t, (tx - 5, ty - 5), 35, (45, 95, 38), -1)
    cv2.rectangle(t, (280, 260), (540, 480), (130, 110, 100), -1)
    for a, b in [((280, 260), (410, 370)), ((540, 260), (410, 370)), ((280, 480), (410, 370)), ((540, 480), (410, 370))]:
        cv2.line(t, a, b, (90, 80, 75), 2)
    if feature_type == "solar":
        for r in range(3):
            for c in range(5):
                px, py = 310 + c * 40, 390 + r * 24
                cv2.rectangle(t, (px, py), (px + 35, py + 20), (25, 25, 30), -1)
                cv2.rectangle(t, (px, py), (px + 35, py + 20), (180, 180, 190), 1)
    elif feature_type == "pool":
        cv2.rectangle(t, (320, 80), (500, 210), (190, 185, 175), -1)
        cv2.ellipse(t, (410, 145), (75, 45), 0, 0, 360, (200, 130, 30), -1)
    elif feature_type == "extension":
        cv2.rectangle(t, (170, 290), (280, 470), (115, 125, 135), -1)
        cv2.line(t, (170, 380), (280, 380), (70, 75, 85), 2)
    text = f"DEMO SYNTHETIC IMAGE - NOT SATELLITE DATA | {date_str}"
    cv2.putText(t, text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(t, text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 160), 1, cv2.LINE_AA)
    return str(_save_png(t, f"demo_{feature_type}", date_str))


# --------------------------------------------------------------------------- Copernicus
class _CopernicusClient:
    def __init__(self):
        self._token: Optional[str] = None
        self._expires = 0.0
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return bool(settings.COPERNICUS_CLIENT_ID and settings.COPERNICUS_CLIENT_SECRET)

    def token(self) -> str:
        with self._lock:
            if self._token and time.time() < self._expires - 30:
                return self._token
            try:
                r = requests.post(
                    settings.COPERNICUS_TOKEN_URL,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": settings.COPERNICUS_CLIENT_ID,
                        "client_secret": settings.COPERNICUS_CLIENT_SECRET,
                    },
                    timeout=settings.HTTP_TIMEOUT_SECONDS,
                )
            except requests.RequestException as exc:
                raise SatelliteProviderError(f"Copernicus identity service unreachable: {exc.__class__.__name__}")
            if r.status_code != 200:
                raise SatelliteProviderError(
                    f"Copernicus authentication failed (HTTP {r.status_code}). Check COPERNICUS_CLIENT_ID/SECRET "
                    "(create an OAuth client at dataspace.copernicus.eu > Dashboard > OAuth clients)."
                )
            body = r.json()
            self._token = body["access_token"]
            self._expires = time.time() + float(body.get("expires_in", 600))
            return self._token

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}"}

    def search(self, lat, lon, start, end, max_cloud) -> List[Dict[str, Any]]:
        bbox = bbox_for(lat, lon, 50)  # point-sized footprint intersection
        payload = {
            "collections": ["sentinel-2-l2a"],
            "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
            "bbox": bbox,
            "limit": 20,
            "filter": f"eo:cloud_cover <= {float(max_cloud)}",
            "filter-lang": "cql2-text",
            "fields": {"include": ["id", "properties.datetime", "properties.eo:cloud_cover", "properties.platform"]},
        }
        try:
            r = requests.post(settings.COPERNICUS_CATALOG_URL, json=payload, headers=self._headers(),
                              timeout=settings.HTTP_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            raise SatelliteProviderError(f"Copernicus catalogue unreachable: {exc.__class__.__name__}")
        if r.status_code != 200:
            raise SatelliteProviderError(f"Copernicus catalogue search failed (HTTP {r.status_code}): {r.text[:200]}")
        out = []
        for f in r.json().get("features", []):
            p = f.get("properties", {})
            dt = p.get("datetime", "")
            out.append({
                "catalog_id": f.get("id"),
                "satellite_name": f"Sentinel-2 MSI ({p.get('platform', 'sentinel-2')})",
                "acquisition_date": dt[:10],
                "acquisition_datetime": dt,
                "cloud_coverage": round(float(p.get("eo:cloud_cover", 0.0)), 1),
                "thumbnail_url": None,
                "resolution_meters": 10.0,
                "mode": "Copernicus Data Space (live)",
                "data_origin": ORIGIN_LIVE,
                "provider": "copernicus",
            })
        return sorted(out, key=lambda x: x["acquisition_datetime"], reverse=True)

    def download(self, lat, lon, acquisition_date: str, px: int, half_size_m: float) -> np.ndarray:
        bbox = bbox_for(lat, lon, half_size_m)
        body = {
            "input": {
                "bounds": {"bbox": bbox, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
                "data": [{
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {"from": f"{acquisition_date}T00:00:00Z", "to": f"{acquisition_date}T23:59:59Z"},
                        "mosaickingOrder": "leastCC",
                    },
                    "processing": {"upsampling": "BICUBIC"},
                }],
            },
            "output": {"width": px, "height": px,
                       "responses": [{"identifier": "default", "format": {"type": "image/png"}}]},
            "evalscript": _EVALSCRIPT,
        }
        try:
            r = requests.post(settings.COPERNICUS_PROCESS_URL, json=body,
                              headers={**self._headers(), "Accept": "image/png"},
                              timeout=settings.HTTP_TIMEOUT_SECONDS * 2)
        except requests.RequestException as exc:
            raise SatelliteProviderError(f"Copernicus Process API unreachable: {exc.__class__.__name__}")
        if r.status_code != 200:
            raise SatelliteProviderError(f"Copernicus Process API failed (HTTP {r.status_code}): {r.text[:200]}")
        img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_UNCHANGED)
        if img is None:
            raise SatelliteProviderError("Copernicus returned data that is not a decodable image.")
        return img


# --------------------------------------------------------------------------- Google Earth Engine
class _GEEClient:
    def __init__(self):
        self._ready = False
        self._error: Optional[str] = None

    @property
    def configured(self) -> bool:
        return bool(HAS_EE and settings.GEE_PROJECT_ID and settings.GEE_SERVICE_ACCOUNT_EMAIL
                    and settings.GEE_SERVICE_ACCOUNT_KEY)

    def missing(self) -> List[str]:
        m = []
        if not HAS_EE:
            m.append("pip package 'earthengine-api'")
        for k in ("GEE_PROJECT_ID", "GEE_SERVICE_ACCOUNT_EMAIL", "GEE_SERVICE_ACCOUNT_KEY"):
            if not getattr(settings, k):
                m.append(k)
        return m

    def init(self):
        if self._ready:
            return
        try:
            creds = ee.ServiceAccountCredentials(settings.GEE_SERVICE_ACCOUNT_EMAIL, settings.GEE_SERVICE_ACCOUNT_KEY)
            ee.Initialize(creds, project=settings.GEE_PROJECT_ID)
            self._ready = True
        except Exception as exc:
            raise SatelliteProviderError(f"Google Earth Engine authentication failed: {exc}")

    def search(self, lat, lon, start, end, max_cloud) -> List[Dict[str, Any]]:
        self.init()
        end_excl = (datetime.date.fromisoformat(end) + datetime.timedelta(days=1)).isoformat()
        try:
            col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                   .filterBounds(ee.Geometry.Point([lon, lat]))
                   .filterDate(start, end_excl)
                   .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
                   .sort("system:time_start", False).limit(20))
            feats = col.getInfo().get("features", [])
        except Exception as exc:
            raise SatelliteProviderError(f"Google Earth Engine query failed: {exc}")
        out = []
        for f in feats:
            p = f.get("properties", {})
            dt = datetime.datetime.utcfromtimestamp(p.get("system:time_start", 0) / 1000.0)
            out.append({
                "catalog_id": f.get("id"),
                "satellite_name": f"Sentinel-2 MSI ({p.get('SPACECRAFT_NAME', 'S2')})",
                "acquisition_date": dt.strftime("%Y-%m-%d"),
                "acquisition_datetime": dt.isoformat() + "Z",
                "cloud_coverage": round(float(p.get("CLOUDY_PIXEL_PERCENTAGE", 0.0)), 1),
                "thumbnail_url": None,
                "resolution_meters": 10.0,
                "mode": "Google Earth Engine (live)",
                "data_origin": ORIGIN_LIVE,
                "provider": "gee",
            })
        return out

    def download(self, catalog_id, lat, lon, px, half_size_m) -> np.ndarray:
        self.init()
        try:
            region = ee.Geometry.Rectangle(bbox_for(lat, lon, half_size_m))
            img = ee.Image(catalog_id).select(["B4", "B3", "B2"])
            url = img.getThumbURL({"region": region, "dimensions": f"{px}x{px}", "format": "png",
                                   "min": 0, "max": 3000, "gamma": 1.1})
            r = requests.get(url, timeout=settings.HTTP_TIMEOUT_SECONDS * 2)
        except Exception as exc:
            raise SatelliteProviderError(f"Google Earth Engine download failed: {exc}")
        if r.status_code != 200:
            raise SatelliteProviderError(f"Google Earth Engine download failed (HTTP {r.status_code}).")
        arr = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_UNCHANGED)
        if arr is None:
            raise SatelliteProviderError("Earth Engine returned data that is not a decodable image.")
        return arr


# --------------------------------------------------------------------------- facade
class SatelliteService:
    def __init__(self):
        self.copernicus = _CopernicusClient()
        self.gee = _GEEClient()

    # ---- provider selection (re-evaluated per call so toggling DEMO_MODE/credentials takes effect)
    def active_provider(self) -> Optional[str]:
        pref = settings.SATELLITE_PROVIDER
        if pref in ("auto", "copernicus") and self.copernicus.configured:
            return "copernicus"
        if pref in ("auto", "gee") and self.gee.configured:
            return "gee"
        return None

    def status(self) -> Dict[str, Any]:
        return {
            "demo_mode": settings.DEMO_MODE,
            "active_provider": self.active_provider(),
            "copernicus_configured": self.copernicus.configured,
            "gee_configured": self.gee.configured,
            "gee_missing": self.gee.missing(),
            "synthetic_imagery_possible": settings.DEMO_MODE,
        }

    def _require_live(self) -> str:
        provider = self.active_provider()
        if provider:
            return provider
        raise SatelliteUnavailableError(
            "No live satellite provider is configured. Set COPERNICUS_CLIENT_ID and COPERNICUS_CLIENT_SECRET "
            "(free OAuth client from dataspace.copernicus.eu), or GEE_PROJECT_ID + GEE_SERVICE_ACCOUNT_EMAIL + "
            "GEE_SERVICE_ACCOUNT_KEY (+ pip install earthengine-api). Synthetic imagery is only available when "
            "DEMO_MODE=true."
        )

    def search_imagery(self, latitude: float, longitude: float, start_date: str, end_date: str,
                       max_cloud_cover: float = 20.0) -> List[Dict[str, Any]]:
        provider = self.active_provider()
        if provider is None:
            if not settings.DEMO_MODE:
                self._require_live()
            return self._demo_search(start_date, end_date, max_cloud_cover)
        client = self.copernicus if provider == "copernicus" else self.gee
        return client.search(latitude, longitude, start_date, end_date, max_cloud_cover)

    def _demo_search(self, start_date, end_date, max_cloud):
        s = datetime.date.fromisoformat(start_date)
        e = datetime.date.fromisoformat(end_date)
        mid = s + (e - s) / 2
        rows = []
        for d, cc in ((s, 1.8), (mid, 0.9), (e, 0.4)):
            rows.append({
                "catalog_id": f"DEMO-SYNTHETIC-{d.isoformat()}",
                "satellite_name": "DEMO synthetic scene (not a real satellite pass)",
                "acquisition_date": d.isoformat(), "acquisition_datetime": f"{d.isoformat()}T05:00:00Z",
                "cloud_coverage": cc, "thumbnail_url": None, "resolution_meters": 10.0,
                "mode": "DEMO DATA (synthetic)", "data_origin": ORIGIN_DEMO, "provider": "demo",
            })
        return [r for r in rows if r["cloud_coverage"] <= max_cloud]

    def retrieve_imagery(self, catalog_id: str, acquisition_date: str, satellite_name: str,
                         latitude: float, longitude: float, feature_hint: str = "baseline",
                         cloud_coverage: Optional[float] = None) -> Dict[str, Any]:
        acq = datetime.datetime.strptime(acquisition_date, "%Y-%m-%d")
        half, px = settings.SATELLITE_AOI_HALF_SIZE_M, settings.SATELLITE_OUTPUT_PX
        provider = self.active_provider()
        demo_requested = catalog_id.startswith("DEMO-SYNTHETIC-")

        if demo_requested or provider is None:
            if not settings.DEMO_MODE:
                self._require_live()
            path = generate_synthetic_satellite_tile(acquisition_date, feature_hint, latitude, longitude)
            return self._pack(path, acq, "DEMO synthetic tile (not satellite data)", ORIGIN_DEMO, cloud_coverage or 0.0,
                              {"catalog_id": catalog_id, "provider": "demo", "synthetic": True},
                              latitude, longitude)

        if provider == "copernicus":
            img = self.copernicus.download(latitude, longitude, acquisition_date, px, half)
            label = "Copernicus Sentinel-2 L2A (CDSE Process API)"
        else:
            img = self.gee.download(catalog_id, latitude, longitude, px, half)
            label = "Google Earth Engine Sentinel-2 SR Harmonized"
        if img.ndim == 3 and img.shape[2] == 4:  # drop alpha, flag fully-masked output
            if int(img[:, :, 3].max()) == 0:
                raise SatelliteProviderError("Provider returned an empty (fully masked) tile for this date/location.")
            img = img[:, :, :3]
        path = _save_png(img, f"s2_{provider}", acquisition_date)
        meta = {
            "catalog_id": catalog_id, "provider": provider, "synthetic": False,
            "dataset": "sentinel-2-l2a" if provider == "copernicus" else "COPERNICUS/S2_SR_HARMONIZED",
            "bands": ["B04", "B03", "B02"], "native_resolution_m": 10.0,
            "output_pixels": px, "aoi_half_size_m": half,
            "bbox_wgs84": bbox_for(latitude, longitude, half),
            "resolution_note": "Sentinel-2 is 10 m/pixel: footprint-scale change only; small rooftop objects are not resolvable.",
        }
        return self._pack(path, acq, label, ORIGIN_LIVE, cloud_coverage or 0.0, meta, latitude, longitude)

    @staticmethod
    def _pack(path, acq, source, origin, cloud, meta, lat, lon):
        meta = {**meta, "target_coordinates": {"lat": lat, "lon": lon},
                "retrieved_at": datetime.datetime.utcnow().isoformat(), "data_origin": origin}
        p = Path(path)
        return {
            "image_path": f"/static/snapshots/{p.name}", "full_filesystem_path": str(p),
            "image_source": source, "data_origin": origin, "acquisition_date": acq,
            "cloud_coverage": cloud, "capture_metadata": meta,
        }


satellite_service = SatelliteService()
