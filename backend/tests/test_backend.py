"""Core API tests (India data). Replaces the earlier US-data test_backend.py."""
import io
import os
from unittest.mock import patch, MagicMock
from PIL import Image
from app.services import geocoding_service as gs


def test_login_success(client):
    r = client.post("/api/auth/login", json={"email": "admin@propertywatch.ai", "password": "AdminPass123!"})
    assert r.status_code == 200 and r.json()["access_token"]


def test_login_invalid_password(client):
    r = client.post("/api/auth/login", json={"email": "admin@propertywatch.ai", "password": "WrongPassword!"})
    assert r.status_code == 401


def test_get_current_user_me(client, auth):
    r = client.get("/api/auth/me", headers=auth["admin"])
    assert r.status_code == 200 and r.json()["email"] == "admin@propertywatch.ai"


def test_geocoding_address(client, auth):
    gs._GEOCODE_CACHE.clear()
    payload = [{"display_name": "Indiranagar, Bengaluru, Karnataka, India", "lat": "12.9784", "lon": "77.6408",
                "address": {"city": "Bengaluru", "state": "Karnataka", "postcode": "560038"}}]
    m = MagicMock(status_code=200)
    m.json.return_value = payload
    with patch("app.services.geocoding_service.requests.get", return_value=m):
        r = client.post("/api/geocode", json={"address": "100 Feet Road, Indiranagar, Bengaluru"}, headers=auth["admin"])
    assert r.status_code == 200 and r.json()["country"] == "India"


def test_geocoding_invalid_empty(client, auth):
    assert client.post("/api/geocode", json={"address": ""}, headers=auth["admin"]).status_code == 400


def test_list_properties(client, auth):
    r = client.get("/api/properties", headers=auth["admin"])
    assert r.status_code == 200 and len(r.json()) >= 4


def test_create_and_retrieve_property(client, auth):
    new_prop = {
        "owner_name": "Test Owner Automation", "owner_contact": "test@example.in",
        "address": "12 MG Road, Camp, Pune, Maharashtra 411001", "city": "Pune", "state": "Maharashtra",
        "postal_code": "411001", "latitude": 18.5204, "longitude": 73.8567,
        "property_type": "Residential Single Family", "number_of_floors": 1, "built_up_area": 1800.0,
        "reference_policy_number": "POL-MH-TEST-01", "monitoring_enabled": True,
    }
    r = client.post("/api/properties", json=new_prop, headers=auth["admin"])
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    g = client.get(f"/api/properties/{pid}", headers=auth["admin"])
    assert g.status_code == 200 and g.json()["city"] == "Pune"
    # keep the shared test database free of this extra record
    from app.database import SessionLocal
    from app.models import Property
    db = SessionLocal()
    try:
        db.query(Property).filter(Property.id == pid).delete()
        db.commit()
    finally:
        db.close()


def test_satellite_search(client, auth):
    r = client.get("/api/satellite/search", params={"latitude": 19.0596, "longitude": 72.8295, "start_date": "2026-01-01",
                   "end_date": "2026-06-30", "max_cloud_cover": 25.0}, headers=auth["admin"])
    assert r.status_code == 200 and r.json()


def test_duplicate_snapshot_prevention(client, auth):
    payload = {"property_id": 1, "catalog_id": "DEMO-SYNTHETIC-2026-01-10", "acquisition_date": "2026-01-10",
               "satellite_name": "Sentinel-2B", "cloud_coverage": 1.0, "is_baseline": False}
    assert client.post("/api/satellite/retrieve", json=payload, headers=auth["admin"]).status_code == 409


def test_image_comparison_cv(client, auth):
    snaps = client.get("/api/satellite/properties/1/snapshots", headers=auth["admin"]).json()
    ids = sorted(s["id"] for s in snaps)
    r = client.post("/api/analysis/compare", json={"property_id": 1, "baseline_snapshot_id": ids[0],
                    "comparison_snapshot_id": ids[-1]}, headers=auth["admin"])
    assert r.status_code == 201, r.text


def test_modification_alert_creation_and_unique_id(client, auth):
    ids = set()
    for _ in range(2):
        r = client.post("/api/modifications", json={"property_id": 1, "suspected_category": "Rooftop Solar Array",
                        "description": "Automated test alert creation", "change_score": 18.5}, headers=auth["admin"])
        assert r.status_code == 201, r.text
        ids.add(r.json()["modification_alert_id"])
    assert len(ids) == 2


def test_review_decision_and_property_update(client, auth):
    mods = client.get("/api/modifications", headers=auth["admin"]).json()
    target = next(m for m in mods if m["status"] not in ("Verified", "Not Confirmed", "Closed"))
    r = client.post(f"/api/reviews/{target['id']}/decision", json={
        "decision": "Verified", "reason": "Contractor invoice and permit confirmed.",
        "notes": "Verified addition.", "updated_area": 4350.0}, headers=auth["reviewer"])
    assert r.status_code == 201, r.text


def test_chronological_property_history(client, auth):
    assert client.get("/api/properties/1/history", headers=auth["admin"]).status_code == 200


def test_audit_logs_exist(client, auth):
    r = client.get("/api/audit-logs", headers=auth["admin"])
    assert r.status_code == 200 and len(r.json()) > 0


def test_dashboard_metrics(client, auth):
    assert client.get("/api/dashboard/metrics", headers=auth["admin"]).status_code == 200


def test_service_status(client, auth):
    r = client.get("/api/settings/status", headers=auth["admin"])
    assert r.status_code == 200
    body = r.json()
    for key in ("geocoding", "satellite_service", "ai_models_registry", "database"):
        assert key in body


def test_evidence_authenticity_endpoint(client, auth):
    img = Image.new("RGB", (16, 16), color=tuple(os.urandom(1)[0] for _ in range(3)))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    mods = client.get("/api/modifications", headers=auth["admin"]).json()
    mid = mods[0]["id"]
    up = client.post(f"/api/modifications/{mid}/evidence", files={"file": ("photo.png", buf.getvalue(), "image/png")},
                     data={"category": "Site Photo", "description": "Verification photo"}, headers=auth["admin"])
    assert up.status_code == 201, up.text
    an = client.post(f"/api/evidence/{up.json()['id']}/analyze-authenticity", headers=auth["admin"])
    assert an.status_code in (200, 201), an.text
