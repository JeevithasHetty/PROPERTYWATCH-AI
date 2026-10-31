import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON, Index
)
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="reviewer") # admin, reviewer, manager, owner, decision_maker
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    reviews = relationship("Review", back_populates="reviewer")
    audit_logs = relationship("AuditLog", back_populates="user")
    declarations = relationship("OwnerDeclaration", back_populates="user")
    claims = relationship("Claim", back_populates="user")
    claim_recommendations = relationship("ClaimRecommendation", back_populates="reviewer")
    claim_decisions = relationship("ClaimDecision", back_populates="decision_maker")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    property_reference = Column(String(50), unique=True, index=True, nullable=False) # e.g. PROP-1001
    owner_name = Column(String(150), nullable=False)
    owner_contact = Column(String(100), nullable=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    address = Column(String(300), nullable=False)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    postal_code = Column(String(50), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    property_type = Column(String(100), default="Residential Single Family") # Residential, Commercial, Industrial, Mixed
    number_of_floors = Column(Integer, default=1)
    built_up_area = Column(Float, nullable=True) # in sq ft / sq meters
    reference_policy_number = Column(String(100), nullable=True, index=True) # for recordkeeping / quick reference
    monitoring_enabled = Column(Boolean, default=True)
    is_demo = Column(Boolean, default=False)
    baseline_image_url = Column(String(300), nullable=True)
    last_monitoring_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    owner_user = relationship("User", foreign_keys=[owner_user_id])
    snapshots = relationship("PropertySnapshot", back_populates="property", cascade="all, delete-orphan", order_by="PropertySnapshot.acquisition_date.desc()")
    analyses = relationship("ImageAnalysis", back_populates="property", cascade="all, delete-orphan")
    modifications = relationship("Modification", back_populates="property", cascade="all, delete-orphan")
    policy = relationship("InsurancePolicy", back_populates="property", uselist=False, cascade="all, delete-orphan")
    versions = relationship("PropertyVersion", back_populates="property", cascade="all, delete-orphan", order_by="PropertyVersion.version_number.desc()")
    claims = relationship("Claim", back_populates="property", cascade="all, delete-orphan", order_by="Claim.created_at.desc()")
    declarations = relationship("OwnerDeclaration", back_populates="property", cascade="all, delete-orphan", order_by="OwnerDeclaration.created_at.desc()")
    imagery_assets = relationship("ImageryAsset", back_populates="property", cascade="all, delete-orphan")
    monitoring_runs = relationship("MonitoringRun", back_populates="property", cascade="all, delete-orphan")


class PropertyVersion(Base):
    __tablename__ = "property_versions"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    attributes_snapshot = Column(JSON, nullable=False) # full serialized snapshot of property attributes
    change_reason = Column(Text, nullable=False)
    changed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="versions")
    changed_by = relationship("User", foreign_keys=[changed_by_user_id])


class InsurancePolicy(Base):
    __tablename__ = "insurance_policies"

    id = Column(Integer, primary_key=True, index=True)
    policy_number = Column(String(100), unique=True, index=True, nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), unique=True, nullable=False, index=True)
    policy_type = Column(String(100), nullable=True)
    status = Column(String(50), default="Active", index=True) # Active, Pending Verification, Expired, Suspended
    effective_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=False)
    coverage_limits = Column(JSON, nullable=True)
    deductibles = Column(JSON, nullable=True)
    exclusions = Column(JSON, nullable=True)
    endorsements = Column(JSON, nullable=True)
    terms_verified = Column(Boolean, default=False)
    document_path = Column(String(300), nullable=True)
    document_filename = Column(String(200), nullable=True)
    document_hash = Column(String(64), nullable=True)
    extracted_terms = Column(JSON, nullable=True)
    # Verified structured terms: insured_perils, sub_limits, sum_insured, reinstatement_value,
    # average_clause, insured_usage, claim_duplicate_window_days, ...
    structured_terms = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="policy")
    versions = relationship("PolicyVersion", back_populates="policy", cascade="all, delete-orphan", order_by="PolicyVersion.version_number.desc()")
    rule_executions = relationship("PolicyRuleExecution", back_populates="policy", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="policy", cascade="all, delete-orphan")


class PolicyVersion(Base):
    __tablename__ = "policy_versions"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("insurance_policies.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    terms_snapshot = Column(JSON, nullable=False)
    change_reason = Column(Text, nullable=False)
    changed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    policy = relationship("InsurancePolicy", back_populates="versions")
    changed_by = relationship("User", foreign_keys=[changed_by_user_id])


class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id = Column(Integer, primary_key=True, index=True)
    rule_code = Column(String(50), unique=True, index=True, nullable=False) # e.g. RULE-COV-LIMIT-01, RULE-DED-APPLY-01, RULE-EXCL-UNPERMITTED
    name = Column(String(150), nullable=False)
    category = Column(String(50), nullable=False) # Coverage Limit, Deductible, Exclusion, Declaration, Policy Period
    description = Column(Text, nullable=False)
    version = Column(String(20), default="1.0")
    is_active = Column(Boolean, default=True)
    rule_config = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    executions = relationship("PolicyRuleExecution", back_populates="rule")


class PolicyRuleExecution(Base):
    __tablename__ = "policy_rule_executions"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("insurance_policies.id"), nullable=False, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True, index=True)
    modification_id = Column(Integer, ForeignKey("modifications.id"), nullable=True, index=True)
    rule_id = Column(Integer, ForeignKey("policy_rules.id"), nullable=True)
    rule_code = Column(String(50), nullable=False, index=True)
    rule_name = Column(String(150), nullable=False)
    rule_version = Column(String(20), nullable=False)
    inputs_snapshot = Column(JSON, nullable=False)
    result = Column(String(50), nullable=False, index=True) # PASS, ALERT_CREATED, MORE_EVIDENCE_REQUIRED, PENDING_REVIEW, INCONCLUSIVE, SYSTEM_ERROR
    explanation = Column(Text, nullable=False)
    applicable_clause = Column(String(200), nullable=True)
    execution_timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    # Relationships
    policy = relationship("InsurancePolicy", back_populates="rule_executions")
    claim = relationship("Claim", back_populates="rule_executions")
    modification = relationship("Modification", back_populates="rule_executions")
    rule = relationship("PolicyRule", back_populates="executions")


class PropertySnapshot(Base):
    __tablename__ = "property_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    image_path = Column(String(300), nullable=False)
    image_source = Column(String(100), nullable=False, default="Copernicus Sentinel-2") # Copernicus, Sentinel Hub, Demo Satellite Hub, Aerial Inspection, Ground Upload
    acquisition_date = Column(DateTime, nullable=False, index=True)
    capture_metadata = Column(JSON, nullable=True) # resolution, sensor, sun angle, coordinates
    cloud_coverage = Column(Float, default=0.0)
    is_baseline = Column(Boolean, default=False)
    # SATELLITE_LIVE (real provider imagery) | DEMO_SYNTHETIC (generated) | USER_UPLOAD
    data_origin = Column(String(30), default="USER_UPLOAD", index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="snapshots")


class ImageryAsset(Base):
    __tablename__ = "imagery_assets"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    source = Column(String(100), default="Copernicus Sentinel-2")
    acquisition_date = Column(DateTime, nullable=False, index=True)
    resolution_meters = Column(Float, default=10.0)
    cloud_coverage = Column(Float, default=0.0)
    processing_status = Column(String(50), default="Available") # Available, Processed, Unsuitable Resolution, Unavailable, Failed
    file_path = Column(String(300), nullable=False)
    asset_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="imagery_assets")


class MonitoringRun(Base):
    __tablename__ = "monitoring_runs"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    baseline_asset_id = Column(Integer, ForeignKey("imagery_assets.id"), nullable=True)
    target_asset_id = Column(Integer, ForeignKey("imagery_assets.id"), nullable=True)
    run_date = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String(50), default="Completed") # Completed, Change Detected, No Change, Failed, Inconclusive
    change_score = Column(Float, default=0.0)
    model_used = Column(String(100), default="OpenCV Differencing + LEVIR-CD")
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="monitoring_runs")


class ImageAnalysis(Base):
    __tablename__ = "image_analyses"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    baseline_snapshot_id = Column(Integer, ForeignKey("property_snapshots.id"), nullable=False)
    comparison_snapshot_id = Column(Integer, ForeignKey("property_snapshots.id"), nullable=False)
    algorithm_name = Column(String(100), default="OpenCV ORB Alignment + Differential SSIM + Contour Analysis")
    change_score = Column(Float, nullable=False) # 0.0 - 100.0%
    changed_area_percentage = Column(Float, default=0.0)
    diff_image_path = Column(String(300), nullable=True)
    heatmap_image_path = Column(String(300), nullable=True)
    contours_count = Column(Integer, default=0)
    analysis_result = Column(String(50), nullable=False) # Low, Moderate, High
    explanation = Column(Text, nullable=True)
    limitations = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="analyses")
    baseline_snapshot = relationship("PropertySnapshot", foreign_keys=[baseline_snapshot_id])
    comparison_snapshot = relationship("PropertySnapshot", foreign_keys=[comparison_snapshot_id])
    modifications = relationship("Modification", back_populates="analysis")


class AIModelRegistry(Base):
    __tablename__ = "ai_model_registry"

    id = Column(Integer, primary_key=True, index=True)
    model_key = Column(String(50), unique=True, index=True, nullable=False) # e.g. LEVIR-CD-Building-v2, Rooftop-Solar-v1
    name = Column(String(100), nullable=False)
    version = Column(String(30), nullable=False)
    task = Column(String(100), nullable=False) # Building Change Detection, Rooftop Small-Object Detection, Image Forensics, Damage Assessment
    provider = Column(String(100), nullable=False)
    is_available = Column(Boolean, default=True)
    confidence_threshold = Column(Float, default=0.65)
    limitations = Column(Text, nullable=True)
    metadata_info = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    inferences = relationship("ModelInference", back_populates="model")


class ModelInference(Base):
    __tablename__ = "model_inferences"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ai_model_registry.id"), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False) # Modification, Evidence, DamageAssessment, RooftopFeature
    entity_id = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=True)
    detected_features = Column(JSON, nullable=True) # Bounding boxes, labels, polygons
    result_summary = Column(Text, nullable=False)
    limitations_disclaimer = Column(Text, nullable=True)
    raw_output = Column(JSON, nullable=True)
    is_simulated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    model = relationship("AIModelRegistry", back_populates="inferences")


class Modification(Base):
    __tablename__ = "modifications"

    id = Column(Integer, primary_key=True, index=True)
    modification_alert_id = Column(String(50), unique=True, index=True, nullable=False) # Collision-resistant e.g. MOD-2026-0001
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    analysis_id = Column(Integer, ForeignKey("image_analyses.id"), nullable=True)
    suspected_category = Column(String(100), default="Potential Rooftop Modification") # Rooftop Solar Array, Building Extension, Swimming Pool, Outbuilding, Floor Addition
    description = Column(Text, nullable=False)
    status = Column(String(50), default="New", index=True) # New, Awaiting Evidence, Under Review, Additional Evidence Required, Verified, Not Confirmed, Closed
    change_score = Column(Float, default=0.0)
    detected_at = Column(DateTime, default=datetime.datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    decision_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="modifications")
    analysis = relationship("ImageAnalysis", back_populates="modifications")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    evidence_items = relationship("Evidence", back_populates="modification", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="modification", cascade="all, delete-orphan")
    declarations = relationship("OwnerDeclaration", back_populates="modification", cascade="all, delete-orphan")
    rule_executions = relationship("PolicyRuleExecution", back_populates="modification", cascade="all, delete-orphan")


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True)
    modification_id = Column(Integer, ForeignKey("modifications.id"), nullable=False, index=True)
    uploaded_by = Column(String(150), default="Property Manager")
    file_path = Column(String(300), nullable=False)
    original_filename = Column(String(200), nullable=False)
    file_type = Column(String(50), nullable=False) # image/jpeg, image/png, application/pdf
    file_size = Column(Integer, default=0) # bytes
    file_hash = Column(String(64), nullable=False) # SHA-256 for integrity & anti-tampering
    description = Column(String(300), nullable=True)
    category = Column(String(50), default="Photograph") # Photograph, Building Permit, Contractor Invoice, Architectural Drawing, Other
    capture_metadata = Column(JSON, nullable=True) # EXIF date, camera model, dimensions
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    modification = relationship("Modification", back_populates="evidence_items")
    authenticity_analyses = relationship("AuthenticityAnalysis", back_populates="evidence", cascade="all, delete-orphan")


class AuthenticityAnalysis(Base):
    __tablename__ = "authenticity_analyses"

    id = Column(Integer, primary_key=True, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=False, index=True)
    provider = Column(String(100), default="Local Heuristic & ELA Engine") # Local ELA / Metadata, AI Detector Provider, Demo Synthetic Signal
    model_name = Column(String(100), default="ELA-Artifact-Detector-v1")
    result = Column(String(100), nullable=False) # No AI-generation signal detected by the configured model, Potential AI-generation or manipulation signal, Inconclusive, Analysis unavailable
    score = Column(Float, nullable=True) # Confidence 0.0 - 1.0 (only if meaningful)
    explanation = Column(Text, nullable=True)
    raw_response = Column(JSON, nullable=True)
    is_demo = Column(Boolean, default=False)
    analyzed_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    evidence = relationship("Evidence", back_populates="authenticity_analyses")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    modification_id = Column(Integer, ForeignKey("modifications.id"), nullable=False, index=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    decision = Column(String(50), nullable=False) # Verified, Not Confirmed, Additional Evidence Required
    reason = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    modification = relationship("Modification", back_populates="reviews")
    reviewer = relationship("User", back_populates="reviews")


class OwnerDeclaration(Base):
    __tablename__ = "owner_declarations"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    modification_id = Column(Integer, ForeignKey("modifications.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    declaration_type = Column(String(50), nullable=False) # CONFIRM, DISPUTE, EXPLAIN
    statement = Column(Text, nullable=False)
    permit_number = Column(String(100), nullable=True)
    contractor_name = Column(String(150), nullable=True)
    completion_date = Column(DateTime, nullable=True)
    status = Column(String(50), default="Submitted") # Submitted, Under Review, Verified, Additional Info Requested
    reviewer_response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="declarations")
    modification = relationship("Modification", back_populates="declarations")
    user = relationship("User", back_populates="declarations")


class Claim(Base):
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    claim_reference = Column(String(50), unique=True, index=True, nullable=False) # CLM-2026-0001
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    policy_id = Column(Integer, ForeignKey("insurance_policies.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True) # owner user who registered claim
    incident_date = Column(DateTime, nullable=False, index=True)
    reported_cause = Column(String(100), nullable=False) # Severe Windstorm & Hail, Roof Collapse, Tree Impact, Water Intrusion, Fire, Structural Damage
    description = Column(Text, nullable=False)
    estimated_loss = Column(Float, nullable=False)
    loss_items = Column(JSON, nullable=True)  # [{"category": str, "amount": float}]
    status = Column(String(50), default="Submitted", index=True) # Submitted, Under Evaluation, Information Requested, Provisional Calculation Ready, Recommendation Recorded, Decision Recorded, Closed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="claims")
    policy = relationship("InsurancePolicy", back_populates="claims")
    user = relationship("User", back_populates="claims")
    evidence_items = relationship("ClaimEvidence", back_populates="claim", cascade="all, delete-orphan")
    damage_assessment = relationship("DamageAssessment", back_populates="claim", uselist=False, cascade="all, delete-orphan")
    calculations = relationship("ProvisionalCalculation", back_populates="claim", cascade="all, delete-orphan")
    recommendations = relationship("ClaimRecommendation", back_populates="claim", cascade="all, delete-orphan")
    decisions = relationship("ClaimDecision", back_populates="claim", cascade="all, delete-orphan")
    rule_executions = relationship("PolicyRuleExecution", back_populates="claim", cascade="all, delete-orphan")
    status_history = relationship("ClaimStatusHistory", back_populates="claim", cascade="all, delete-orphan")


class ClaimStatusHistory(Base):
    __tablename__ = "claim_status_history"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    from_status = Column(String(50), nullable=False)
    to_status = Column(String(50), nullable=False)
    changed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    claim = relationship("Claim", back_populates="status_history")
    changed_by = relationship("User", foreign_keys=[changed_by_user_id])


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_path = Column(String(300), nullable=False)
    original_filename = Column(String(200), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, default=0)
    file_hash = Column(String(64), nullable=False) # SHA-256
    category = Column(String(50), default="Damage Photograph") # Damage Photograph, Repair Estimate, Contractor Invoice, Inspection Report, Policy Document, Other
    description = Column(String(300), nullable=True)
    metadata_json = Column(JSON, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    claim = relationship("Claim", back_populates="evidence_items")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_user_id])


class DamageAssessment(Base):
    __tablename__ = "damage_assessments"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), unique=True, nullable=False, index=True)
    pre_event_snapshot_id = Column(Integer, ForeignKey("property_snapshots.id"), nullable=True)
    post_event_snapshot_id = Column(Integer, ForeignKey("property_snapshots.id"), nullable=True)
    observed_damage_indicators = Column(JSON, nullable=False) # ["Rooftop penetration / membrane breach", "Soffit detachment", "Backyard debris"]
    ai_damage_suggestions = Column(JSON, nullable=True) # {"severity_score": 72.5, "anomaly_area_pct": 14.2, "limitations": "..."}
    ai_model_name = Column(String(100), default="LEVIR-CD-Building-v2 + OpenCV Differencing")
    ai_confidence = Column(Float, nullable=True)
    human_findings = Column(Text, nullable=True)
    missing_evidence_flags = Column(JSON, default=list) # ["Detailed roofing contractor estimate needed", "Interior water intrusion photos requested"]
    unresolved_policy_terms_flags = Column(JSON, default=list) # ["Wind/hail deductible endorsement requires manual adjuster signoff"]
    assessment_status = Column(String(50), default="Provisional") # Provisional, Under Review, Completed
    assessed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    claim = relationship("Claim", back_populates="damage_assessment")
    pre_event_snapshot = relationship("PropertySnapshot", foreign_keys=[pre_event_snapshot_id])
    post_event_snapshot = relationship("PropertySnapshot", foreign_keys=[post_event_snapshot_id])
    assessor = relationship("User", foreign_keys=[assessed_by_user_id])


class ProvisionalCalculation(Base):
    __tablename__ = "provisional_calculations"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    damage_assessment_id = Column(Integer, ForeignKey("damage_assessments.id"), nullable=True)
    gross_claimed_loss = Column(Float, nullable=False)
    applicable_coverage_limit = Column(Float, nullable=False)
    limit_category = Column(String(100), default="Dwelling Coverage Limit (Coverage A)")
    non_covered_excluded_amount = Column(Float, default=0.0)
    applicable_deductible = Column(Float, default=0.0)
    deductible_type_applied = Column(String(100), default="Standard Policy Deductible")
    provisional_net_payout = Column(Float, nullable=False)
    calculation_method = Column(Text, nullable=False)
    assumptions = Column(Text, nullable=False)
    is_provisional = Column(Boolean, default=True)
    calculated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    claim = relationship("Claim", back_populates="calculations")
    calculated_by = relationship("User", foreign_keys=[calculated_by_user_id])


class ClaimRecommendation(Base):
    __tablename__ = "claim_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    recommendation_type = Column(String(50), nullable=False) # APPROVE_PROVISIONAL, REQUEST_MORE_DOCUMENTS, REQUEST_INSPECTION, REDUCE_AMOUNT, DENY_EXCLUDED
    recommended_amount = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=False)
    applicable_policy_clauses = Column(JSON, default=list) # ["Section I - Perils Insured Against: Windstorm", "Section I - Exclusions: Unpermitted additions"]
    evidence_references = Column(JSON, default=list) # ["EV-01: Storm damage photo", "MOD-2026-0001: Verified solar array"]
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    claim = relationship("Claim", back_populates="recommendations")
    reviewer = relationship("User", back_populates="claim_recommendations")


class ClaimDecision(Base):
    __tablename__ = "claim_decisions"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    decision_maker_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    decision = Column(String(50), nullable=False) # APPROVED, APPROVED_PARTIAL, MORE_INFO_REQUESTED, INSPECTION_ORDERED, DENIED
    authorized_amount = Column(Float, nullable=True)
    rationale = Column(Text, nullable=False)
    applicable_policy_clauses = Column(JSON, default=list)
    decision_version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    claim = relationship("Claim", back_populates="decisions")
    decision_maker = relationship("User", back_populates="claim_decisions")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), default="MODIFICATION_ALERT") # MODIFICATION_ALERT, RFI_REQUEST, CLAIM_STATUS_UPDATE, INSPECTION_SCHEDULED, POLICY_ALERT
    link = Column(String(200), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="notifications")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    entity_type = Column(String(50), nullable=False, index=True) # Property, Modification, Evidence, Review, Analysis, Policy, Claim, Decision
    entity_id = Column(String(50), nullable=False, index=True)
    action = Column(String(100), nullable=False) # CREATED, UPDATED, VERIFIED, REJECTED, EVIDENCE_UPLOADED, SATELLITE_RETRIEVED, POLICY_LINKED, CLAIM_REGISTERED, DECISION_COMMITTED
    previous_state = Column(JSON, nullable=True)
    new_state = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")


class PolicyClause(Base):
    """A clause identified in an uploaded policy PDF. Only reviewer-verified clauses feed policy terms."""
    __tablename__ = "policy_clauses"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("insurance_policies.id"), nullable=False, index=True)
    document_hash = Column(String(64), nullable=True)
    page_number = Column(Integer, nullable=True)
    clause_ref = Column(String(50), nullable=True)
    category = Column(String(40), nullable=False, index=True)  # sum_insured, insured_peril, exclusion, sub_limit, deductible, condition, endorsement, usage, other
    text = Column(Text, nullable=False)
    extracted_values = Column(JSON, nullable=True)
    status = Column(String(20), default="Extracted", index=True)  # Extracted, Verified, Rejected
    verified_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    reviewer_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ClaimSettlement(Base):
    __tablename__ = "claim_settlements"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    decision_id = Column(Integer, ForeignKey("claim_decisions.id"), nullable=False)
    settled_amount = Column(Float, nullable=False)
    payment_mode = Column(String(20), nullable=False)  # NEFT, RTGS, UPI, IMPS, CHEQUE
    payment_reference = Column(String(100), nullable=False)  # UTR / cheque number
    payment_date = Column(DateTime, nullable=False)
    settled_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

