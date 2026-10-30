import datetime
from io import BytesIO
import uuid

from fastapi.testclient import TestClient
import pytest
from PIL import Image

from app.main import app
from app.models import InsurancePolicy
from app.schemas import PolicyCreate, ProvisionalCalculationCreate
from app.services.ai_models_service import levir_cd_detector, rooftop_object_detector
from app.services.policy_rules_engine import PolicyRulesEngine

client = TestClient(app)


def test_policy_schema_does_not_supply_terms():
    policy = PolicyCreate(
        property_id=1,
        policy_number="POL-UNKNOWN-TERMS",
        effective_date=datetime.datetime(2025, 1, 1),
        expiry_date=datetime.datetime(2027, 1, 1),
    )

    assert policy.policy_type is None
    assert policy.coverage_limits is None
    assert policy.deductibles is None
    assert policy.exclusions is None
    assert policy.endorsements is None


def test_policy_rules_leave_missing_terms_unresolved():
    policy = InsurancePolicy(
        policy_number="POL-UNVERIFIED",
        policy_type=None,
        effective_date=datetime.datetime(2025, 1, 1),
        expiry_date=datetime.datetime(2027, 1, 1),
        coverage_limits={},
        deductibles={},
        exclusions=[],
        endorsements=[],
        terms_verified=False,
    )

    coverage = PolicyRulesEngine.evaluate_rule_cov_limit(policy, claimed_amount=0)
    deductible = PolicyRulesEngine.evaluate_rule_deductible(
        policy, claimed_amount=1000, cause_of_loss="wind"
    )
    solar = PolicyRulesEngine.evaluate_rule_solar_endorsement(
        policy, claim=type("ClaimStub", (), {"description": "solar panel damage", "reported_cause": "roof damage"})()
    )
    flood = PolicyRulesEngine.evaluate_rule_flood_exclusion(
        policy, cause_of_loss="flood"
    )

    assert coverage["result"] == "PENDING_REVIEW"
    assert deductible["result"] == "PENDING_REVIEW"
    assert solar["result"] == "INCONCLUSIVE"
    assert flood["result"] == "INCONCLUSIVE"


def test_building_and_rooftop_models_do_not_fabricate_predictions():
    building = levir_cd_detector.detect_building_changes("missing-baseline", "missing-target", 1)
    rooftop = rooftop_object_detector.detect_rooftop_objects("missing-image", 1)

    assert building["status"] == "UNAVAILABLE"
    assert building["change_detected"] is None
    assert building["confidence"] is None
    assert rooftop["status"] == "UNAVAILABLE"
    assert rooftop["solar_detected"] is None
    assert rooftop["confidence"] is None


def test_provisional_calculation_requires_policy_derived_values():
    with pytest.raises(Exception):
        ProvisionalCalculationCreate(
            claim_id=1,
            gross_claimed_loss=10000,
            calculation_method="",
            assumptions="",
        )


def test_property_policy_claim_registration_with_unknown_terms():
    login = client.post("/api/auth/login", json={
        "email": "admin@propertywatch.ai",
        "password": "AdminPass123!",
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    property_response = client.post("/api/properties", headers=headers, json={
        "owner_name": "Workflow Test Owner",
        "address": f"{uuid.uuid4().hex[:8]} Test Street, Seattle",
        "latitude": 47.6062,
        "longitude": -122.3321,
        "property_type": "Residential",
    })
    assert property_response.status_code == 201
    property_id = property_response.json()["id"]

    policy_response = client.post("/api/policies", headers=headers, json={
        "property_id": property_id,
        "policy_number": f"POL-{uuid.uuid4().hex[:12]}",
        "effective_date": "2025-01-01T00:00:00",
        "expiry_date": "2027-01-01T00:00:00",
    })
    assert policy_response.status_code == 201
    policy = policy_response.json()
    assert policy["coverage_limits"] == {}
    assert policy["deductibles"] == {}
    assert policy["exclusions"] == []
    assert policy["terms_verified"] is False

    claim_response = client.post("/api/claims", headers=headers, json={
        "property_id": property_id,
        "incident_date": "2026-01-15T00:00:00",
        "reported_cause": "Storm damage",
        "description": "Owner-reported roof damage",
        "estimated_loss": 12000,
    })
    assert claim_response.status_code == 201
    assert claim_response.json()["policy_id"] == policy["id"]


def test_baseline_photo_uses_authenticated_private_storage():
    login = client.post("/api/auth/login", json={
        "email": "owner@propertywatch.ai",
        "password": "OwnerPass123!",
    })
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}

    property_response = client.post("/api/properties", headers=headers, json={
        "owner_name": "Private Image Test Owner",
        "address": f"{uuid.uuid4().hex[:8]} Private Image Street, Seattle",
        "latitude": 47.6062,
        "longitude": -122.3321,
        "property_type": "Residential",
    })
    assert property_response.status_code == 201
    property_id = property_response.json()["id"]

    image = Image.new("RGB", (3, 3), color=(12, 34, 56))
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")
    upload = client.post(
        f"/api/properties/{property_id}/baseline-photo",
        headers=headers,
        files={"file": ("baseline.png", image_bytes.getvalue(), "image/png")},
    )
    assert upload.status_code == 200
    result = upload.json()
    assert result["image_url"] == f"/api/properties/{property_id}/snapshots/{result['snapshot_id']}/image"

    assert client.get(result["image_url"]).status_code == 401
    downloaded = client.get(result["image_url"], headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.content == image_bytes.getvalue()
