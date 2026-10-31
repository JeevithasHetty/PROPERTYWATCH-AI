import datetime
from unittest.mock import patch
import pytest
from app.config import settings
from app.database import SessionLocal
from app.models import Property, PropertySnapshot, Modification, MonitoringRun, Notification, User
from app.services import monitoring_service as mon
from app.services.satellite_service import satellite_service
from tests.conftest import png_bytes


def _owner_property(client, auth):
    props = client.get("/api/properties", headers=auth["owner"]).json()
    assert props, "owner should own a demo property"
    return props[0]


def test_full_property_policy_claim_workflow(client, auth):
    prop = _owner_property(client, auth)
    pol = next(p for p in client.get("/api/policies", headers=auth["admin"]).json() if p["property_id"] == prop["id"])
    assert pol["terms_verified"]

    # 1. submission (property has a verified modification; that must not block the claim)
    r = client.post("/api/claims", headers=auth["owner"], json={
        "property_id": prop["id"], "incident_date": "2026-09-01T10:00:00", "reported_cause": "Fire",
        "description": "Short circuit fire in kitchen of the flat", "estimated_loss": 600000,
        "loss_items": [{"category": "Kitchen repair", "amount": 450000}, {"category": "Solar", "amount": 150000}]})
    assert r.status_code == 201, r.text
    claim = r.json()
    assert claim["status"] == "Submitted" and claim["loss_items"]
    cid = claim["id"]

    # 2. evidence
    r = client.post(f"/api/claims/{cid}/evidence", headers=auth["owner"],
                    files={"file": ("fire.png", png_bytes(noise=True, size=128), "image/png")},
                    data={"category": "Damage Photograph", "description": "kitchen"})
    assert r.status_code == 201, r.text

    # rule outcomes were recorded at registration (15 rules), and no automatic rejection happened
    detail = client.get(f"/api/claims/{cid}", headers=auth["reviewer"]).json()
    assert len(detail["rule_executions"]) >= 15
    assert detail["status"] in ("Submitted", "Under Evaluation")

    # reviewer cannot shortcut to an outcome status
    for st in ("Approved", "Denied", "Settled"):
        r = client.post(f"/api/claims/{cid}/status", headers=auth["reviewer"], json={"to_status": st, "notes": "x"})
        assert r.status_code == 400

    # 3. review
    assert client.post(f"/api/claims/{cid}/status", headers=auth["reviewer"],
                       json={"to_status": "Under Evaluation", "notes": "start"}).status_code == 200

    # calculation before assessment is refused
    calc_body = {"claim_id": cid, "gross_claimed_loss": 600000, "limit_category": "dwelling",
                 "non_covered_excluded_amount": 0, "deductible_type_applied": "standard",
                 "calculation_method": "Net = min(gross, limit) - deductible", "assumptions": "test"}
    assert client.post(f"/api/claims/{cid}/provisional-calculation", headers=auth["reviewer"], json=calc_body).status_code == 409

    # 4. damage assessment (with pre/post snapshots: previously crashed with settings.ROOT_DIR)
    snaps = client.get(f"/api/satellite/properties/{prop['id']}/snapshots", headers=auth["reviewer"]).json()
    r = client.post(f"/api/claims/{cid}/damage-assessment", headers=auth["reviewer"], json={
        "claim_id": cid, "pre_event_snapshot_id": snaps[-1]["id"], "post_event_snapshot_id": snaps[0]["id"],
        "observed_damage_indicators": ["Kitchen fire damage"], "human_findings": "Inspected; consistent", "assessment_status": "Complete"})
    assert r.status_code == 201, r.text
    assert r.json()["ai_damage_suggestions"]["status"] == "UNAVAILABLE"  # no weights: reported, not faked

    # 5. policy evaluation + 6. provisional payout (limit 85,00,000; standard deductible 10,000)
    r = client.post(f"/api/claims/{cid}/provisional-calculation", headers=auth["reviewer"], json=calc_body)
    assert r.status_code == 201, r.text
    assert r.json()["provisional_net_payout"] == 590000.0

    # recommendation then decision
    r = client.post(f"/api/claims/{cid}/recommendation", headers=auth["reviewer"], json={
        "recommendation_type": "APPROVE_PROVISIONAL", "recommended_amount": 590000, "reasoning": "Covered peril"})
    assert r.status_code == 201

    # approval above payout refused; reviewers cannot decide; denial without clauses refused
    over = {"decision": "APPROVED", "authorized_amount": 700000, "rationale": "too much"}
    assert client.post(f"/api/claims/{cid}/decision", headers=auth["decision"], json=over).status_code == 409
    ok = {"decision": "APPROVED", "authorized_amount": 590000, "rationale": "Within verified terms",
          "applicable_policy_clauses": ["Perils covered: Fire"]}
    assert client.post(f"/api/claims/{cid}/decision", headers=auth["reviewer"], json=ok).status_code == 403
    assert client.post(f"/api/claims/{cid}/decision", headers=auth["decision"],
                       json={"decision": "DENIED", "rationale": "A modification was detected on the roof"}).status_code == 400

    # 7. approval -> settlement
    assert client.post(f"/api/claims/{cid}/decision", headers=auth["decision"], json=ok).status_code == 201
    assert client.get(f"/api/claims/{cid}", headers=auth["owner"]).json()["status"] == "Approved"
    pay = {"settled_amount": 590000, "payment_mode": "NEFT", "payment_reference": "UTR123456789"}
    assert client.post(f"/api/claims/{cid}/settlement", headers=auth["reviewer"], json=pay).status_code == 403
    assert client.post(f"/api/claims/{cid}/settlement", headers=auth["decision"],
                       json={**pay, "settled_amount": 600000}).status_code == 409
    assert client.post(f"/api/claims/{cid}/settlement", headers=auth["decision"], json={**pay, "payment_mode": "BITCOIN"}).status_code == 400
    r = client.post(f"/api/claims/{cid}/settlement", headers=auth["decision"], json=pay)
    assert r.status_code == 201 and r.json()["claim_status"] == "Settled"
    assert client.post(f"/api/claims/{cid}/settlement", headers=auth["decision"], json=pay).status_code == 409
    # owner was notified in rupees
    notes = client.get("/api/notifications", headers=auth["owner"]).json()
    assert any("₹" in n["message"] for n in notes)


def test_denial_requires_verified_terms(client, auth):
    prop = _owner_property(client, auth)
    r = client.post("/api/claims", headers=auth["owner"], json={
        "property_id": prop["id"], "incident_date": "2026-09-05T10:00:00", "reported_cause": "Structural Damage",
        "description": "wall cracks", "estimated_loss": 50000})
    cid = r.json()["id"]
    d = client.post(f"/api/claims/{cid}/decision", headers=auth["decision"], json={
        "decision": "DENIED", "rationale": "Excluded under wear and tear, see clause 4 in the policy.",
        "applicable_policy_clauses": ["Exclusions: wear and tear"]})
    assert d.status_code == 201  # terms are verified in the seed; cited clause present


# ----------------------------------------------------------------------------- monitoring
def _fake_search(lat, lon, start, end, cloud):
    return [{"catalog_id": "S2X", "satellite_name": "S2", "acquisition_date": datetime.date.today().isoformat(),
             "cloud_coverage": 2.0, "data_origin": "SATELLITE_LIVE", "provider": "copernicus"}]


def _fake_retrieve(catalog_id, acq, name, lat, lon, hint="baseline", cloud=None):
    from app.services.satellite_service import _save_png
    import cv2, numpy as np
    img = np.full((256, 256, 3), (90, 140, 90), np.uint8)
    cv2.rectangle(img, (60, 60), (200, 200), (30, 30, 200), -1)  # large new structure
    p = _save_png(img, "s2_test", acq)
    return {"image_path": f"/static/snapshots/{p.name}", "image_source": "Copernicus Sentinel-2 L2A (test double)",
            "data_origin": "SATELLITE_LIVE", "acquisition_date": datetime.datetime.strptime(acq, "%Y-%m-%d"),
            "cloud_coverage": 2.0, "capture_metadata": {"synthetic": False}}


def test_monitoring_creates_snapshot_alert_and_notifications(client, auth):
    db = SessionLocal()
    try:
        prop = db.query(Property).filter(Property.monitoring_enabled == True).first()  # noqa: E712
        pid, owner_id = prop.id, prop.owner_user_id
        before_mods = db.query(Modification).count()
    finally:
        db.close()
    with patch.object(satellite_service, "search_imagery", side_effect=_fake_search), \
         patch.object(satellite_service, "retrieve_imagery", side_effect=_fake_retrieve):
        out = mon.run_monitoring_cycle([pid])
    assert out["checked"] == 1 and out["new_snapshots"] == 1, out
    res = out["results"][0]
    assert res["alert"], res
    db = SessionLocal()
    try:
        snap = db.query(PropertySnapshot).filter(PropertySnapshot.property_id == pid).order_by(PropertySnapshot.id.desc()).first()
        assert snap.data_origin == "SATELLITE_LIVE"
        mod = db.query(Modification).filter(Modification.modification_alert_id == res["alert"]).first()
        assert mod.status == "New" and mod.analysis_id
        assert db.query(Modification).count() == before_mods + 1
        assert db.query(Notification).filter(Notification.type == "MODIFICATION_ALERT", Notification.link == f"/alerts/{mod.id}").count() >= 2
        assert db.query(MonitoringRun).filter(MonitoringRun.property_id == pid, MonitoringRun.status == "Change Detected").count() == 1
    finally:
        db.close()
    # second run: pass already stored -> no duplicate
    with patch.object(satellite_service, "search_imagery", side_effect=_fake_search), \
         patch.object(satellite_service, "retrieve_imagery", side_effect=_fake_retrieve):
        again = mon.run_monitoring_cycle([pid])
    assert again["new_snapshots"] == 0


def test_monitoring_live_without_credentials_fails_honestly(client, auth, live_mode):
    db = SessionLocal()
    try:
        pid = db.query(Property).order_by(Property.id.desc()).first().id
        snaps = db.query(PropertySnapshot).count()
        db.query(Property).filter(Property.id == pid).update({"is_demo": False})
        db.commit()
    finally:
        db.close()
    out = mon.run_monitoring_cycle([pid])
    assert out["failed"] == 1 and out["new_snapshots"] == 0
    assert "COPERNICUS" in out["results"][0]["message"]
    db = SessionLocal()
    try:
        assert db.query(PropertySnapshot).count() == snaps
        db.query(Property).filter(Property.id == pid).update({"is_demo": True})
        db.commit()
    finally:
        db.close()


def test_monitoring_api_and_scheduler_status(client, auth):
    assert client.get("/api/monitoring/status", headers=auth["admin"]).status_code == 200
    assert client.post("/api/monitoring/run", json={}, headers=auth["owner"]).status_code == 403
    assert client.get("/api/monitoring/runs", headers=auth["admin"]).status_code == 200


def test_live_mode_has_no_demo_users_unless_bootstrapped(tmp_path, monkeypatch):
    from app import seed_data
    from app.database import SessionLocal as SL
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    db = SL()
    n = db.query(User).count()
    db.close()
    seed_data.seed_database()  # must not add anything in live mode
    db = SL()
    assert db.query(User).count() == n
    db.close()
