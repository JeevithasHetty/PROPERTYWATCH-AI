from unittest.mock import patch, MagicMock
import requests
from app.services import geocoding_service as gs


def _resp(payload, code=200):
    m = MagicMock(status_code=code)
    m.json.return_value = payload
    return m


def test_geocode_restricts_to_india_and_parses(client, auth):
    gs._GEOCODE_CACHE.clear()
    payload = [{"display_name": "Bandra West, Mumbai, Maharashtra, India", "lat": "19.0596", "lon": "72.8295",
                "address": {"suburb": "Bandra West", "city": "Mumbai", "state": "Maharashtra", "postcode": "400050"}}]
    with patch("app.services.geocoding_service.requests.get", return_value=_resp(payload)) as g:
        r = client.post("/api/geocode", json={"address": "Pali Hill Bandra West Mumbai"}, headers=auth["admin"])
    assert r.status_code == 200
    assert g.call_args.kwargs["params"]["countrycodes"] == "in"
    body = r.json()
    assert body["country"] == "India" and body["postal_code"] == "400050"


def test_geocode_no_match_is_404_not_fabricated(client, auth):
    gs._GEOCODE_CACHE.clear()
    with patch("app.services.geocoding_service.requests.get", return_value=_resp([])):
        r = client.post("/api/geocode", json={"address": "zzzz nowhere lane"}, headers=auth["admin"])
    assert r.status_code == 404


def test_geocode_outside_india_rejected(client, auth):
    gs._GEOCODE_CACHE.clear()
    payload = [{"display_name": "Atlanta", "lat": "33.77", "lon": "-84.35", "address": {}}]
    with patch("app.services.geocoding_service.requests.get", return_value=_resp(payload)):
        r = client.post("/api/geocode", json={"address": "Atlanta Georgia"}, headers=auth["admin"])
    assert r.status_code == 422


def test_geocode_live_network_failure_returns_502(client, auth, live_mode):
    gs._GEOCODE_CACHE.clear()
    with patch("app.services.geocoding_service.requests.get", side_effect=requests.ConnectionError()):
        r = client.post("/api/geocode", json={"address": "Indiranagar Bengaluru"}, headers=auth["admin"])
    assert r.status_code == 502


def test_seed_data_is_indian(client, auth):
    props = client.get("/api/properties", headers=auth["admin"]).json()
    assert props
    for p in props:
        assert 6 < p["latitude"] < 37 and 68 < p["longitude"] < 98, p["address"]
        assert p["is_demo"] is True


def test_inr_format():
    from app.services.format_utils import format_inr
    assert format_inr(1234567.5) == "₹12,34,567.50"
    assert format_inr(999) == "₹999.00"
    assert format_inr(100000, 0) == "₹1,00,000"


def test_fallback_to_locality_when_house_number_unknown(client, auth):
    gs._GEOCODE_CACHE.clear()
    calls = []

    def fake(url, params=None, **kw):
        calls.append(params["q"])
        m = MagicMock(status_code=200)
        # only a coarse (no house number / no '3rd main') query matches
        ok = "#26" not in params["q"] and "3rd" not in params["q"]
        m.json.return_value = [{"display_name": "Sapthagiri Layout, Bengaluru, Karnataka, India", "lat": "13.0817", "lon": "77.5800",
                                "address": {"city": "Bengaluru", "state": "Karnataka", "postcode": "560064"}}] if ok else []
        return m

    with patch("app.services.geocoding_service.requests.get", side_effect=fake), patch("app.services.geocoding_service.time.sleep"):
        r = client.post("/api/geocode", json={"address": "#26,Sapthagiri layout 3rd main, Bengaluru, Karnataka 560064"}, headers=auth["admin"])
    assert r.status_code == 200, r.text
    assert r.json()["precision"] == "approximate" and len(calls) >= 2
    assert "Sapthagiri" in calls[-1] or "560064" in calls[-1]
