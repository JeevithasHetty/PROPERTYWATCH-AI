from unittest.mock import patch, MagicMock
from tests.conftest import png_bytes
from app.config import settings
from app.services.satellite_service import satellite_service


def _prop_id(client, auth):
    return client.get("/api/properties", headers=auth["admin"]).json()[3]["id"]


def test_live_mode_without_credentials_never_returns_synthetic(client, auth, live_mode):
    r = client.get("/api/satellite/search", params={"latitude": 19.07, "longitude": 72.87,
                   "start_date": "2026-01-01", "end_date": "2026-02-01"}, headers=auth["admin"])
    assert r.status_code == 503
    assert "COPERNICUS_CLIENT_ID" in r.json()["detail"]
    pid = _prop_id(client, auth)
    r = client.post("/api/satellite/retrieve", json={"property_id": pid, "catalog_id": "x", "acquisition_date": "2026-01-05",
                    "satellite_name": "S2"}, headers=auth["admin"])
    assert r.status_code == 503


def test_demo_results_are_labelled_synthetic(client, auth):
    r = client.get("/api/satellite/search", params={"latitude": 19.07, "longitude": 72.87,
                   "start_date": "2026-03-01", "end_date": "2026-04-01"}, headers=auth["admin"])
    assert r.status_code == 200
    assert all(i["data_origin"] == "DEMO_SYNTHETIC" and "DEMO" in i["mode"] for i in r.json())


def _fake_post(url, **kw):
    m = MagicMock()
    if "openid-connect/token" in url:
        assert kw["data"]["grant_type"] == "client_credentials"
        m.status_code, m.json.return_value = 200, {"access_token": "tok", "expires_in": 600}
    elif url.endswith("/search"):
        assert kw["headers"]["Authorization"] == "Bearer tok"
        assert kw["json"]["collections"] == ["sentinel-2-l2a"]
        m.status_code = 200
        m.json.return_value = {"features": [
            {"id": "S2B_A", "properties": {"datetime": "2026-03-10T05:30:00Z", "eo:cloud_cover": 3.2, "platform": "sentinel-2b"}},
            {"id": "S2A_B", "properties": {"datetime": "2026-03-20T05:30:00Z", "eo:cloud_cover": 1.0, "platform": "sentinel-2a"}}]}
    else:  # process API
        assert kw["headers"]["Authorization"] == "Bearer tok"
        m.status_code, m.content = 200, png_bytes(noise=True, size=256)
    return m


def test_copernicus_live_search_and_retrieve(client, auth, live_mode):
    satellite_service.copernicus._token = None
    with patch.object(settings, "COPERNICUS_CLIENT_ID", "id"), patch.object(settings, "COPERNICUS_CLIENT_SECRET", "secret"), \
         patch("app.services.satellite_service.requests.post", side_effect=_fake_post):
        # live-mode property so the demo gate does not matter
        pid = _prop_id(client, auth)
        r = client.get("/api/satellite/search", params={"property_id": pid, "start_date": "2026-03-01",
                       "end_date": "2026-03-31"}, headers=auth["admin"])
        assert r.status_code == 200, r.text
        items = r.json()
        assert items[0]["catalog_id"] == "S2A_B" and items[0]["data_origin"] == "SATELLITE_LIVE"
        r = client.post("/api/satellite/retrieve", json={"property_id": pid, "catalog_id": "S2A_B",
                        "acquisition_date": "2026-03-20", "satellite_name": "S2A", "cloud_coverage": 1.0},
                        headers=auth["admin"])
        assert r.status_code == 200, r.text
        snap = r.json()
        assert snap["data_origin"] == "SATELLITE_LIVE"
        assert snap["capture_metadata"]["synthetic"] is False
        assert snap["capture_metadata"]["native_resolution_m"] == 10.0
        assert "Copernicus" in snap["image_source"]
    satellite_service.copernicus._token = None


def test_copernicus_auth_failure_is_502(client, auth, live_mode):
    satellite_service.copernicus._token = None
    bad = MagicMock(status_code=401, text="nope")
    with patch.object(settings, "COPERNICUS_CLIENT_ID", "id"), patch.object(settings, "COPERNICUS_CLIENT_SECRET", "bad"), \
         patch("app.services.satellite_service.requests.post", return_value=bad):
        r = client.get("/api/satellite/search", params={"latitude": 19.0, "longitude": 72.8,
                       "start_date": "2026-03-01", "end_date": "2026-03-31"}, headers=auth["admin"])
    assert r.status_code == 502 and "authentication failed" in r.json()["detail"]


def test_status_is_truthful(client, auth):
    s = client.get("/api/settings/status", headers=auth["admin"]).json()
    assert "DEMO ONLY" in s["satellite_service"]["status"]
    assert s["satellite_service"]["copernicus_configured"] is False
    assert "LEVIR-CD-Building-v2" in s["ai_models_registry"]["unavailable_models"]
