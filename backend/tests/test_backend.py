import os
import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

# Cache JWT token
auth_headers = {}

def test_root_endpoint():
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["app"] == "PropertyWatch AI"
    assert data["status"] == "Online"

def test_login_success():
    global auth_headers
    resp = client.post("/api/auth/login", json={
        "email": "admin@propertywatch.ai",
        "password": "AdminPass123!"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "admin@propertywatch.ai"
    assert data["user"]["role"] == "admin"
    auth_headers = {"Authorization": f"Bearer {data['access_token']}"}

def test_login_invalid_password():
    resp = client.post("/api/auth/login", json={
        "email": "admin@propertywatch.ai",
        "password": "WrongPassword!"
    })
    assert resp.status_code == 401

def test_get_current_user_me():
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "admin@propertywatch.ai"

def test_geocoding_address():
    resp = client.post("/api/geocode", json={"address": "1042 Highland Ave NE, Atlanta, GA"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "latitude" in data
    assert "longitude" in data
    assert abs(data["latitude"] - 33.7749) < 0.1

def test_geocoding_invalid_empty():
    resp = client.post("/api/geocode", json={"address": ""}, headers=auth_headers)
    assert resp.status_code == 400

def test_list_properties():
    resp = client.get("/api/properties", headers=auth_headers)
    assert resp.status_code == 200
    props = resp.json()
    assert len(props) >= 4
    refs = [p["property_reference"] for p in props]
    assert "PROP-2026-1001" in refs

def test_create_and_retrieve_property():
    new_prop = {
        "owner_name": "Test Owner Automation",
        "owner_contact": "test@domain.com",
        "address": "500 Test Avenue, Seattle, WA 98101",
        "city": "Seattle",
        "state": "Washington",
        "postal_code": "98101",
        "latitude": 47.6062,
        "longitude": -122.3321,
        "property_type": "Residential Single Family",
        "number_of_floors": 1,
        "built_up_area": 1800.0,
        "reference_policy_number": "POL-WA-TEST-01",
        "monitoring_enabled": True
    }
    resp = client.post("/api/properties", json=new_prop, headers=auth_headers)
    assert resp.status_code == 201
    prop_data = resp.json()
    prop_id = prop_data["id"]
    assert prop_data["property_reference"].startswith("PROP-")

    # Retrieve by ID
    get_resp = client.get(f"/api/properties/{prop_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["owner_name"] == "Test Owner Automation"

def test_satellite_search():
    resp = client.get(
        "/api/satellite/search?latitude=33.7749&longitude=-84.3541&start_date=2026-01-01&end_date=2026-06-30&max_cloud_cover=25.0",
        headers=auth_headers
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) > 0
    assert "catalog_id" in results[0]

def test_duplicate_snapshot_prevention():
    # Attempting to retrieve a snapshot for same date should raise 409
    payload = {
        "property_id": 1,
        "catalog_id": "S2B_TEST_DUP",
        "acquisition_date": "2026-01-10",
        "satellite_name": "Sentinel-2B",
        "cloud_coverage": 1.0,
        "is_baseline": False
    }
    resp = client.post("/api/satellite/retrieve", json=payload, headers=auth_headers)
    assert resp.status_code == 409

def test_image_comparison_cv():
    # Compare Property 1 snapshots (baseline 1 vs comparison 2)
    resp = client.post("/api/analysis/compare", json={
        "property_id": 1,
        "baseline_snapshot_id": 1,
        "comparison_snapshot_id": 2
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["change_score"] > 0
    assert "heatmap_image_path" in data
    assert "diff_image_path" in data
    assert "limitations" in data

def test_modification_alert_creation_and_unique_id():
    resp = client.post("/api/modifications", json={
        "property_id": 1,
        "suspected_category": "Rooftop Solar Array",
        "description": "Automated test alert creation",
        "change_score": 18.5
    }, headers=auth_headers)
    assert resp.status_code == 201
    alert = resp.json()
    assert alert["modification_alert_id"].startswith("MOD-2026-")
    assert alert["status"] == "New"

def test_review_decision_and_property_update():
    # Submit review for modification 2 (Swimming Pool)
    decision_payload = {
        "decision": "Verified",
        "reason": "Contractor invoice and pool permit confirmed.",
        "notes": "Verified outdoor swimming pool addition.",
        "updated_area": 4350.0
    }
    resp = client.post("/api/reviews/2/decision", json=decision_payload, headers=auth_headers)
    assert resp.status_code == 201
    rev = resp.json()
    assert rev["decision"] == "Verified"

    # Verify property 2 was updated with new built up area
    prop_resp = client.get("/api/properties/2", headers=auth_headers)
    assert prop_resp.status_code == 200
    assert prop_resp.json()["built_up_area"] == 4350.0

def test_chronological_property_history():
    resp = client.get("/api/properties/1/history", headers=auth_headers)
    assert resp.status_code == 200
    hist = resp.json()
    assert len(hist["timeline"]) >= 3
    event_types = [t["event_type"] for t in hist["timeline"]]
    assert "REGISTRATION" in event_types

def test_audit_logs_exist():
    resp = client.get("/api/audit-logs", headers=auth_headers)
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) > 0

def test_dashboard_metrics():
    resp = client.get("/api/dashboard/metrics", headers=auth_headers)
    assert resp.status_code == 200
    metrics = resp.json()
    assert metrics["total_properties"] >= 4
    assert metrics["monitored_properties"] >= 4
    assert len(metrics["modification_categories"]) > 0

def test_service_status():
    resp = client.get("/api/settings/status", headers=auth_headers)
    assert resp.status_code == 200
    status_data = resp.json()
    assert status_data["database"]["status"] == "CONNECTED"
    assert status_data["geocoding"]["status"] == "OPERATIONAL"
    assert "OpenStreetMap" in status_data["geocoding"]["provider"]
    assert "Leaflet" in status_data["geocoding"]["map_engine"]

def test_google_earth_engine_configuration():
    resp = client.get("/api/settings/status", headers=auth_headers)
    assert resp.status_code == 200
    status_data = resp.json()
    sat = status_data["satellite_service"]
    assert sat["gee_project_id"] == "youtube-1-476010"
    assert sat["gee_project_number"] == "741309446381"
    assert sat["gee_project_name"] == "youtube-1"
    assert "COPERNICUS/S2_SR_HARMONIZED" in sat["dataset"]

def test_deepfake_detector_forensics_pipeline():
    from app.services.deepfake_detector import deepfake_detector
    # Use one of the seeded snapshot images to test deepfake analysis
    snapshots = list(settings.SNAPSHOTS_DIR.glob("*.png"))
    assert len(snapshots) > 0, "Snapshots exist for testing"
    test_img = str(snapshots[0])

    analysis = deepfake_detector.analyze(test_img, evidence_id=999)
    assert "verdict" in analysis
    assert "deepfake_probability" in analysis
    assert 0.0 <= analysis["deepfake_probability"] <= 1.0
    assert "diffusion_spectral_score" in analysis
    assert "ela_metric" in analysis
    assert "noise_variance" in analysis
    assert "forensic_heatmap_url" in analysis
    assert analysis["forensic_heatmap_url"].startswith("/static/heatmaps/forensic_deepfake_ev_999_")

    # Verify physical heatmap artifact generated
    heatmap_filename = analysis["forensic_heatmap_url"].replace("/static/heatmaps/", "")
    heatmap_path = settings.HEATMAPS_DIR / heatmap_filename
    assert heatmap_path.exists(), f"Heatmap file should exist at {heatmap_path}"

def test_evidence_authenticity_endpoint():
    # Unique but valid image content keeps this test repeatable with duplicate detection enabled.
    test_image = Image.new("RGB", (16, 16), color=tuple(os.urandom(1)[0] for _ in range(3)))
    image_buffer = io.BytesIO()
    test_image.save(image_buffer, format="PNG")
    files = {"file": ("contractor_permit_photo.png", image_buffer.getvalue(), "image/png")}
    data = {"category": "Site Photo", "description": "Verification photo of property"}
    upload_resp = client.post("/api/modifications/1/evidence", files=files, data=data, headers=auth_headers)
    assert upload_resp.status_code == 201
    ev_id = upload_resp.json()["id"]

    # 2. Trigger Deepfake & Authenticity Analysis
    resp = client.post(f"/api/evidence/{ev_id}/analyze-authenticity", headers=auth_headers)
    assert resp.status_code == 201
    auth_data = resp.json()
    assert "result" in auth_data
    assert "raw_response" in auth_data
    raw = auth_data["raw_response"]
    assert "deepfake_probability" in raw
    assert "forensic_heatmap_url" in raw

