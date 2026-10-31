import io
import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from app.database import SessionLocal
from app.models import InsurancePolicy, Claim, PolicyRule, ClaimEvidence
from app.services import policy_rules_engine as pre


def _pdf(lines):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for ln in lines:
        c.drawString(40, y, ln)
        y -= 18
    c.save()
    return buf.getvalue()


POLICY_LINES = [
    "Policy No: SFSP/2026/000777",
    "1. Sum Insured: Building Rs. 45 lakhs",
    "2. Compulsory Excess: INR 25,000 per claim",
    "3. Perils covered: Fire, lightning, storm, cyclone, flood and inundation",
    "4. Exclusions: War, nuclear risks, wear and tear, earthquake",
    "5. Sub-limit for jewellery not exceeding INR 1,50,000",
]


def _new_policy(client, auth):
    props = client.get("/api/properties", headers=auth["admin"]).json()
    p = props[3]  # commercial demo property
    pol = client.get("/api/policies", headers=auth["admin"]).json()
    return next(x for x in pol if x["property_id"] == p["id"])


def test_fifteen_rules_registered(client, auth):
    db = SessionLocal()
    try:
        codes = {r.rule_code for r in db.query(PolicyRule)}
    finally:
        db.close()
    original7 = {"RULE-POL-PERIOD-01", "RULE-COV-LIMIT-01", "RULE-DED-APPLY-01", "RULE-EXCL-UNPERMITTED-01",
                 "RULE-EXCL-WATER-01", "RULE-ENDORSE-SOLAR-01", "RULE-DECLARATION-TIMELY-01"}
    assert original7 <= codes and len(codes) == 15


def test_pdf_extraction_clause_verification_and_apply(client, auth):
    pol = _new_policy(client, auth)
    pid = pol["id"]
    r = client.post(f"/api/policies/{pid}/document", files={"file": ("policy.pdf", _pdf(POLICY_LINES), "application/pdf")},
                    headers=auth["reviewer"])
    assert r.status_code == 200, r.text
    info = r.json()["extracted_terms"]
    assert info["extraction_status"] == "COMPLETED_NEEDS_HUMAN_VERIFICATION" and info["clauses_found"] >= 5
    clauses = client.get(f"/api/policies/{pid}/clauses", headers=auth["reviewer"]).json()
    cats = {c["category"] for c in clauses}
    assert {"sum_insured", "deductible", "insured_peril", "exclusion", "sub_limit"} <= cats
    assert all(c["status"] == "Extracted" for c in clauses)

    # nothing verified -> cannot apply
    assert client.post(f"/api/policies/{pid}/clauses/apply", json={}, headers=auth["reviewer"]).status_code == 409

    for c in clauses:
        vals = dict(c["extracted_values"] or {})
        if c["category"] == "sub_limit":
            vals["label"] = "Jewellery"
        if c["category"] == "deductible":
            vals["label"] = "standard"
        if c["category"] == "sum_insured":
            vals.update({"label": "dwelling", "reinstatement_value": 6000000})
        r = client.put(f"/api/policies/{pid}/clauses/{c['id']}", json={"status": "Verified", "extracted_values": vals},
                       headers=auth["reviewer"])
        assert r.status_code == 200
    # owners cannot verify clauses
    assert client.put(f"/api/policies/{pid}/clauses/{clauses[0]['id']}", json={"status": "Verified"},
                      headers=auth["owner"]).status_code == 403
    r = client.post(f"/api/policies/{pid}/clauses/apply", json={"confirm_terms_verified": True}, headers=auth["reviewer"])
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["coverage_limits"]["dwelling"] == 4500000.0
    assert out["deductibles"]["standard"] == 25000.0
    assert out["structured_terms"]["sub_limits"]["Jewellery"] == 150000.0
    assert out["structured_terms"]["sum_insured"] == 4500000.0 and out["structured_terms"]["reinstatement_value"] == 6000000
    assert out["terms_verified"] is True


def test_non_pdf_and_editing_terms_resets_verification(client, auth):
    pol = _new_policy(client, auth)
    r = client.put(f"/api/policies/{pol['id']}", json={"deductibles": {"standard": 1.0}, "change_reason": "t"},
                   headers=auth["reviewer"])
    assert r.status_code == 200 and r.json()["terms_verified"] is False


def _claim(**kw):
    c = Claim(claim_reference="CLM-T", property_id=1, policy_id=1, user_id=1,
              incident_date=datetime.datetime(2026, 7, 1), reported_cause=kw.get("cause", "Fire"),
              description=kw.get("desc", "kitchen fire"), estimated_loss=100000, loss_items=kw.get("items"))
    return c


class _P:  # lightweight policy stand-in
    def __init__(self, **kw):
        self.terms_verified = kw.pop("verified", True)
        self.structured_terms = kw.pop("st", {})
        self.exclusions = kw.pop("excl", [])
        self.coverage_limits = kw.pop("cl", {})
        self.id = 1


def test_peril_rule_requires_verification_and_matches():
    c = _claim(cause="Severe Windstorm & Hail", desc="roof damaged by gusts")
    assert pre.evaluate_rule_peril_insured(_P(verified=False), c)["result"] == "PENDING_REVIEW"
    assert pre.evaluate_rule_peril_insured(_P(), c)["result"] == "PENDING_REVIEW"  # no perils recorded
    p = _P(st={"insured_perils": ["Storm, cyclone, tempest"]})
    assert pre.evaluate_rule_peril_insured(p, c)["result"] == "PASS"
    p = _P(st={"insured_perils": ["Fire", "Lightning"]})
    assert pre.evaluate_rule_peril_insured(p, c)["result"] == "ALERT_CREATED"


def test_general_exclusion_screen():
    c = _claim(cause="Structural Damage", desc="cracks from earthquake tremor")
    r = pre.evaluate_rule_general_exclusions(_P(excl=["Earthquake, fire and shock"]), c)
    assert r["result"] == "ALERT_CREATED" and r["applicable_clause"]
    assert pre.evaluate_rule_general_exclusions(_P(excl=["Wear and tear"]), c)["result"] == "PASS"


def test_sublimit_rule():
    p = _P(st={"sub_limits": {"Jewellery": 150000}})
    assert pre.evaluate_rule_sublimit(p, _claim())["result"] == "MORE_EVIDENCE_REQUIRED"
    over = pre.evaluate_rule_sublimit(p, _claim(), [{"category": "Jewellery", "amount": 200000}])
    assert over["result"] == "ALERT_CREATED" and over["inputs"]["capped_items"][0]["excess"] == 50000
    assert pre.evaluate_rule_sublimit(p, _claim(), [{"category": "Jewellery", "amount": 100000}])["result"] == "PASS"
    assert pre.evaluate_rule_sublimit(_P(), _claim())["result"] == "INCONCLUSIVE"


def test_underinsurance_rule_and_factor():
    p = _P(st={"sum_insured": 4500000, "reinstatement_value": 6000000, "average_clause": True})
    assert pre.evaluate_rule_underinsurance(p)["result"] == "ALERT_CREATED"
    assert pre.underinsurance_factor(p) == 0.75
    p2 = _P(st={"sum_insured": 4500000, "reinstatement_value": 6000000, "average_clause": False})
    assert pre.evaluate_rule_underinsurance(p2)["result"] == "INCONCLUSIVE" and pre.underinsurance_factor(p2) is None
    assert pre.evaluate_rule_underinsurance(_P(verified=False, st={"average_clause": True}))["result"] == "PENDING_REVIEW"
    assert pre.evaluate_rule_underinsurance(_P(st={}))["result"] == "PENDING_REVIEW"


def test_usage_change_is_never_a_rejection():
    class Prop: property_type = "Residential"
    class Mod: suspected_category = "Extension"; description = "converted to guest house with paying guests"
    r = pre.evaluate_rule_usage_change(_P(st={"insured_usage": "Residential"}), _claim(), [Mod()], Prop())
    assert r["result"] == "MORE_EVIDENCE_REQUIRED"
    assert pre.evaluate_rule_usage_change(_P(st={"insured_usage": "Residential"}), _claim(), [], Prop())["result"] == "PASS"
    assert pre.evaluate_rule_usage_change(_P(st={}), _claim(), [], Prop())["result"] == "INCONCLUSIVE"


def test_duplicate_claim_rule(client, auth):
    db = SessionLocal()
    try:
        pol = db.query(InsurancePolicy).first()
        base = Claim(claim_reference="CLM-DUP-1", property_id=pol.property_id, policy_id=pol.id, user_id=1,
                     incident_date=datetime.datetime(2026, 8, 10), reported_cause="Fire", description="x", estimated_loss=1)
        dup = Claim(claim_reference="CLM-DUP-2", property_id=pol.property_id, policy_id=pol.id, user_id=1,
                    incident_date=datetime.datetime(2026, 8, 15), reported_cause="fire", description="y", estimated_loss=1)
        other = Claim(claim_reference="CLM-DUP-3", property_id=pol.property_id, policy_id=pol.id, user_id=1,
                      incident_date=datetime.datetime(2026, 8, 12), reported_cause="Water Intrusion", description="z", estimated_loss=1)
        db.add_all([base, dup, other]); db.commit()
        r = pre.evaluate_rule_duplicate_claim(db, pol, dup)
        assert r["result"] == "ALERT_CREATED" and "CLM-DUP-1" in r["inputs"]["same_cause_claims"]
        assert pre.evaluate_rule_duplicate_claim(db, pol, other)["result"] == "PASS"  # different cause, no shared evidence
        db.add(ClaimEvidence(claim_id=base.id, uploaded_by_user_id=1, file_path="a", original_filename="a.jpg", file_type="image/jpeg",
                             file_size=1, file_hash="h" * 64, category="Other"))
        db.add(ClaimEvidence(claim_id=other.id, uploaded_by_user_id=1, file_path="b", original_filename="b.jpg", file_type="image/jpeg",
                             file_size=1, file_hash="h" * 64, category="Other"))
        db.commit()
        db.refresh(other)
        assert pre.evaluate_rule_duplicate_claim(db, pol, other)["result"] == "ALERT_CREATED"
    finally:
        for c in db.query(Claim).filter(Claim.claim_reference.like("CLM-DUP-%")):
            db.delete(c)
        db.commit(); db.close()
