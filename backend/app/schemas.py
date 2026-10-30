from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

# ----------------- Auth Schemas -----------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str # admin, reviewer, manager, owner, decision_maker
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- Geocoding Schemas -----------------
class GeocodeRequest(BaseModel):
    address: str

class GeocodeResponse(BaseModel):
    query: str
    display_name: str
    latitude: float
    longitude: float
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    source: str = "OpenStreetMap Nominatim"

# ----------------- Property Schemas -----------------
class PropertyCreate(BaseModel):
    property_reference: Optional[str] = None
    owner_name: str
    owner_contact: Optional[str] = None
    owner_user_id: Optional[int] = None
    address: str
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    property_type: str = "Residential Single Family"
    number_of_floors: int = 1
    built_up_area: Optional[float] = None
    reference_policy_number: Optional[str] = None
    monitoring_enabled: bool = True
    notes: Optional[str] = None

class PropertyUpdate(BaseModel):
    owner_name: Optional[str] = None
    owner_contact: Optional[str] = None
    owner_user_id: Optional[int] = None
    address: Optional[str] = None
    property_type: Optional[str] = None
    number_of_floors: Optional[int] = None
    built_up_area: Optional[float] = None
    monitoring_enabled: Optional[bool] = None
    reference_policy_number: Optional[str] = None
    notes: Optional[str] = None

class PropertySnapshotOut(BaseModel):
    id: int
    property_id: int
    image_path: str
    image_source: str
    acquisition_date: datetime
    capture_metadata: Optional[Dict[str, Any]] = None
    cloud_coverage: float
    is_baseline: bool
    created_at: datetime

    class Config:
        from_attributes = True

class PropertyVersionOut(BaseModel):
    id: int
    property_id: int
    version_number: int
    attributes_snapshot: Dict[str, Any]
    change_reason: str
    changed_by_user_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PropertyOut(BaseModel):
    id: int
    property_reference: str
    owner_name: str
    owner_contact: Optional[str] = None
    owner_user_id: Optional[int] = None
    address: str
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: float
    longitude: float
    property_type: str
    number_of_floors: int
    built_up_area: Optional[float] = None
    reference_policy_number: Optional[str] = None
    monitoring_enabled: bool
    baseline_image_url: Optional[str] = None
    last_monitoring_date: Optional[datetime] = None
    verified_modifications_count: int = 0
    open_alerts_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ----------------- Satellite Search & Retrieval -----------------
class SatelliteSearchQuery(BaseModel):
    property_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    start_date: str # YYYY-MM-DD
    end_date: str # YYYY-MM-DD
    max_cloud_cover: float = 20.0

class SatelliteSearchResultItem(BaseModel):
    catalog_id: str
    satellite_name: str
    acquisition_date: str
    cloud_coverage: float
    thumbnail_url: Optional[str] = None
    resolution_meters: float
    mode: str # Live Copernicus or Demo Sentinel Hub

class SatelliteRetrieveRequest(BaseModel):
    property_id: int
    catalog_id: str
    acquisition_date: str
    satellite_name: str
    cloud_coverage: float = 0.0
    is_baseline: bool = False

# ----------------- Image Analysis Schemas -----------------
class ImageComparisonRequest(BaseModel):
    property_id: int
    baseline_snapshot_id: int
    comparison_snapshot_id: int
    suspected_category: Optional[str] = None

class ImageAnalysisOut(BaseModel):
    id: int
    property_id: int
    baseline_snapshot_id: int
    comparison_snapshot_id: int
    algorithm_name: str
    change_score: float
    changed_area_percentage: float
    diff_image_path: Optional[str] = None
    heatmap_image_path: Optional[str] = None
    contours_count: int
    analysis_result: str
    explanation: Optional[str] = None
    limitations: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- Evidence & Authenticity Schemas -----------------
class AuthenticityAnalysisOut(BaseModel):
    id: int
    evidence_id: int
    provider: str
    model_name: str
    result: str
    score: Optional[float] = None
    explanation: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None
    is_demo: bool
    analyzed_at: datetime

    class Config:
        from_attributes = True

class EvidenceOut(BaseModel):
    id: int
    modification_id: int
    uploaded_by: str
    file_path: str
    original_filename: str
    file_type: str
    file_size: int
    file_hash: str
    description: Optional[str] = None
    category: str
    capture_metadata: Optional[Dict[str, Any]] = None
    uploaded_at: datetime
    authenticity_analyses: List[AuthenticityAnalysisOut] = []

    class Config:
        from_attributes = True

# ----------------- Review Schemas -----------------
class ReviewDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(Verified|Not Confirmed|Additional Evidence Required)$")
    reason: str
    notes: Optional[str] = None
    updated_floors: Optional[int] = None
    updated_area: Optional[float] = None
    updated_property_type: Optional[str] = None

class ReviewOut(BaseModel):
    id: int
    modification_id: int
    reviewer_id: int
    decision: str
    reason: str
    notes: Optional[str] = None
    created_at: datetime
    reviewer_name: Optional[str] = None

    class Config:
        from_attributes = True

# ----------------- Modification Schemas -----------------
class ModificationCreate(BaseModel):
    property_id: int
    analysis_id: Optional[int] = None
    suspected_category: str
    description: str
    change_score: Optional[float] = 0.0

class ModificationUpdate(BaseModel):
    status: Optional[str] = None
    reviewer_id: Optional[int] = None
    reviewer_notes: Optional[str] = None
    suspected_category: Optional[str] = None

class ModificationOut(BaseModel):
    id: int
    modification_alert_id: str
    property_id: int
    analysis_id: Optional[int] = None
    suspected_category: str
    description: str
    status: str
    change_score: float
    detected_at: datetime
    verified_at: Optional[datetime] = None
    reviewer_id: Optional[int] = None
    reviewer_name: Optional[str] = None
    reviewer_notes: Optional[str] = None
    decision_reason: Optional[str] = None
    property_reference: Optional[str] = None
    property_address: Optional[str] = None
    evidence_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ModificationDetailOut(ModificationOut):
    analysis: Optional[ImageAnalysisOut] = None
    evidence_items: List[EvidenceOut] = []
    reviews: List[ReviewOut] = []

# ----------------- Insurance Policy Schemas -----------------
class PolicyCreate(BaseModel):
    property_id: int
    policy_number: str
    policy_type: Optional[str] = None
    effective_date: datetime
    expiry_date: datetime
    coverage_limits: Optional[Dict[str, float]] = None
    deductibles: Optional[Dict[str, float]] = None
    exclusions: Optional[List[str]] = None
    endorsements: Optional[List[Union[str, Dict[str, Any]]]] = None
    notes: Optional[str] = None

class PolicyUpdate(BaseModel):
    policy_type: Optional[str] = None
    status: Optional[str] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    coverage_limits: Optional[Dict[str, float]] = None
    deductibles: Optional[Dict[str, float]] = None
    exclusions: Optional[List[str]] = None
    endorsements: Optional[List[Union[str, Dict[str, Any]]]] = None
    terms_verified: Optional[bool] = None
    notes: Optional[str] = None
    change_reason: Optional[str] = "Policy terms updated"

class PolicyVerificationRequest(BaseModel):
    verified_terms: Dict[str, Any]
    verification_notes: Optional[str] = None

class PolicyOut(BaseModel):
    id: int
    property_id: int
    policy_number: str
    policy_type: Optional[str] = None
    status: str
    effective_date: datetime
    expiry_date: datetime
    coverage_limits: Optional[Dict[str, float]] = None
    deductibles: Optional[Dict[str, float]] = None
    exclusions: Optional[List[str]] = None
    endorsements: Optional[List[Union[str, Dict[str, Any]]]] = None
    terms_verified: bool
    document_path: Optional[str] = None
    document_filename: Optional[str] = None
    document_hash: Optional[str] = None
    extracted_terms: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    property_reference: Optional[str] = None
    property_address: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PolicyVersionOut(BaseModel):
    id: int
    policy_id: int
    version_number: int
    terms_snapshot: Dict[str, Any]
    change_reason: str
    changed_by_user_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- Policy Rules & Executions -----------------
class PolicyRuleOut(BaseModel):
    id: int
    rule_code: str
    name: str
    category: str
    description: str
    version: str
    is_active: bool
    rule_config: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PolicyRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    is_active: Optional[bool] = None
    rule_config: Optional[Dict[str, Any]] = None

class PolicyRuleExecutionOut(BaseModel):
    id: int
    policy_id: int
    claim_id: Optional[int] = None
    modification_id: Optional[int] = None
    rule_id: Optional[int] = None
    rule_code: str
    rule_name: str
    rule_version: str
    inputs_snapshot: Dict[str, Any]
    result: str # PASS, ALERT_CREATED, MORE_EVIDENCE_REQUIRED, PENDING_REVIEW, INCONCLUSIVE, SYSTEM_ERROR
    explanation: str
    applicable_clause: Optional[str] = None
    execution_timestamp: datetime

    class Config:
        from_attributes = True

class PolicyRuleEvaluationRequest(BaseModel):
    policy_id: int
    claim_id: Optional[int] = None
    modification_id: Optional[int] = None
    incident_date: Optional[datetime] = None
    claimed_amount: Optional[float] = None
    cause_of_loss: Optional[str] = None
    modification_category: Optional[str] = None
    has_permit: Optional[bool] = None

# ----------------- Owner Declaration Schemas -----------------
class OwnerDeclarationCreate(BaseModel):
    property_id: int
    modification_id: Optional[int] = None
    declaration_type: str = Field(..., pattern="^(CONFIRM|DISPUTE|EXPLAIN)$")
    statement: str
    permit_number: Optional[str] = None
    contractor_name: Optional[str] = None
    completion_date: Optional[datetime] = None

class OwnerDeclarationUpdate(BaseModel):
    status: Optional[str] = None
    reviewer_response: Optional[str] = None

class OwnerDeclarationOut(BaseModel):
    id: int
    property_id: int
    modification_id: Optional[int] = None
    user_id: int
    user_name: Optional[str] = None
    declaration_type: str
    statement: str
    permit_number: Optional[str] = None
    contractor_name: Optional[str] = None
    completion_date: Optional[datetime] = None
    status: str
    reviewer_response: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ----------------- Claim Schemas -----------------
class ClaimCreate(BaseModel):
    property_id: int
    incident_date: datetime
    reported_cause: str # Severe Windstorm & Hail, Roof Collapse, Tree Impact, Water Intrusion, Fire, Structural Damage
    description: str = Field(..., min_length=1)
    estimated_loss: float = Field(..., ge=0)

class ClaimUpdate(BaseModel):
    status: Optional[str] = None
    description: Optional[str] = None
    estimated_loss: Optional[float] = None
    notes: Optional[str] = None

class ClaimStatusUpdate(BaseModel):
    to_status: str
    notes: Optional[str] = None

class ClaimEvidenceOut(BaseModel):
    id: int
    claim_id: int
    uploaded_by_user_id: int
    uploaded_by_name: Optional[str] = None
    file_path: str
    original_filename: str
    file_type: str
    file_size: int
    file_hash: str
    category: str
    description: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True

class DamageAssessmentOut(BaseModel):
    id: int
    claim_id: int
    pre_event_snapshot_id: Optional[int] = None
    post_event_snapshot_id: Optional[int] = None
    observed_damage_indicators: List[str]
    ai_damage_suggestions: Optional[Dict[str, Any]] = None
    ai_model_name: Optional[str] = None
    ai_confidence: Optional[float] = None
    human_findings: Optional[str] = None
    missing_evidence_flags: List[str]
    unresolved_policy_terms_flags: List[str]
    assessment_status: str
    assessed_by_user_id: Optional[int] = None
    assessed_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DamageAssessmentCreate(BaseModel):
    claim_id: int
    pre_event_snapshot_id: Optional[int] = None
    post_event_snapshot_id: Optional[int] = None
    observed_damage_indicators: List[str]
    human_findings: Optional[str] = None
    missing_evidence_flags: Optional[List[str]] = None
    unresolved_policy_terms_flags: Optional[List[str]] = None
    assessment_status: Optional[str] = "Provisional"

class ProvisionalCalculationCreate(BaseModel):
    claim_id: int
    damage_assessment_id: Optional[int] = None
    gross_claimed_loss: float = Field(..., ge=0)
    limit_category: str
    non_covered_excluded_amount: float = Field(..., ge=0)
    deductible_type_applied: str
    calculation_method: str
    assumptions: str

class ProvisionalCalculationOut(BaseModel):
    id: int
    claim_id: int
    damage_assessment_id: Optional[int] = None
    gross_claimed_loss: float
    applicable_coverage_limit: float
    limit_category: str
    non_covered_excluded_amount: float
    applicable_deductible: float
    deductible_type_applied: str
    provisional_net_payout: float
    calculation_method: str
    assumptions: str
    is_provisional: bool
    calculated_by_user_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ClaimRecommendationCreate(BaseModel):
    recommendation_type: str = Field(..., pattern="^(APPROVE_PROVISIONAL|REQUEST_MORE_DOCUMENTS|REQUEST_INSPECTION|REDUCE_AMOUNT|DENY_EXCLUDED)$")
    recommended_amount: Optional[float] = None
    reasoning: str
    applicable_policy_clauses: List[str] = []
    evidence_references: List[str] = []

class ClaimRecommendationOut(BaseModel):
    id: int
    claim_id: int
    reviewer_id: int
    reviewer_name: Optional[str] = None
    recommendation_type: str
    recommended_amount: Optional[float] = None
    reasoning: str
    applicable_policy_clauses: List[str]
    evidence_references: List[str]
    created_at: datetime

    class Config:
        from_attributes = True

class ClaimDecisionCreate(BaseModel):
    decision: str = Field(..., pattern="^(APPROVED|APPROVED_PARTIAL|MORE_INFO_REQUESTED|INSPECTION_ORDERED|DENIED)$")
    authorized_amount: Optional[float] = None
    rationale: str
    applicable_policy_clauses: List[str] = []

class ClaimDecisionOut(BaseModel):
    id: int
    claim_id: int
    decision_maker_id: int
    decision_maker_name: Optional[str] = None
    decision: str
    authorized_amount: Optional[float] = None
    rationale: str
    applicable_policy_clauses: List[str]
    decision_version: int
    created_at: datetime

    class Config:
        from_attributes = True

class ClaimStatusHistoryOut(BaseModel):
    id: int
    claim_id: int
    from_status: str
    to_status: str
    changed_by_user_id: Optional[int] = None
    changed_by_name: Optional[str] = None
    notes: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True

class ClaimOut(BaseModel):
    id: int
    claim_reference: str
    property_id: int
    policy_id: int
    user_id: int
    incident_date: datetime
    reported_cause: str
    description: str
    estimated_loss: float
    status: str
    property_reference: Optional[str] = None
    property_address: Optional[str] = None
    policy_number: Optional[str] = None
    owner_name: Optional[str] = None
    evidence_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ClaimDetailOut(ClaimOut):
    policy: Optional[PolicyOut] = None
    evidence_items: List[ClaimEvidenceOut] = []
    damage_assessment: Optional[DamageAssessmentOut] = None
    calculations: List[ProvisionalCalculationOut] = []
    recommendations: List[ClaimRecommendationOut] = []
    decisions: List[ClaimDecisionOut] = []
    rule_executions: List[PolicyRuleExecutionOut] = []
    status_history: List[ClaimStatusHistoryOut] = []
    related_modifications: List[ModificationOut] = []
    related_declarations: List[OwnerDeclarationOut] = []

# ----------------- AI Model Registry & Inference Schemas -----------------
class AIModelRegistryOut(BaseModel):
    id: int
    model_key: str
    name: str
    version: str
    task: str
    provider: str
    is_available: bool
    confidence_threshold: float
    limitations: Optional[str] = None
    metadata_info: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ModelInferenceOut(BaseModel):
    id: int
    model_id: int
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    entity_type: str
    entity_id: str
    confidence: Optional[float] = None
    detected_features: Optional[Dict[str, Any]] = None
    result_summary: str
    limitations_disclaimer: Optional[str] = None
    is_simulated: bool
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- Notification Schemas -----------------
class NotificationOut(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    type: str
    link: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- Audit Log Schemas -----------------
class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    entity_type: str
    entity_id: str
    action: str
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True

# ----------------- Property Detail Schemas -----------------
class PropertyDetailOut(PropertyOut):
    snapshots: List[PropertySnapshotOut] = []
    modifications: List[ModificationOut] = []
    audit_logs: List[AuditLogOut] = []
    policy: Optional[PolicyOut] = None
    versions: List[PropertyVersionOut] = []
    declarations: List[OwnerDeclarationOut] = []

# ----------------- Dashboard Metrics Schema -----------------
class DashboardMetricsOut(BaseModel):
    total_properties: int
    monitored_properties: int
    active_policies_count: int = 0
    total_claims_count: int = 0
    open_claims_count: int = 0
    new_alerts_count: int
    awaiting_review_count: int
    confirmed_modifications_count: int
    additional_evidence_count: int
    alerts_by_month: List[Dict[str, Any]]
    modification_categories: List[Dict[str, Any]]
    recent_cases: List[ModificationOut]
    recent_claims: List[ClaimOut] = []
    recent_activity: List[AuditLogOut]

# ----------------- Settings / Status Schemas -----------------
class ServiceStatusOut(BaseModel):
    geocoding: Dict[str, Any]
    satellite_service: Dict[str, Any]
    authenticity_service: Dict[str, Any]
    llm_service: Dict[str, Any]
    policy_rules_engine: Optional[Dict[str, Any]] = None
    ai_models_registry: Optional[Dict[str, Any]] = None
    database: Dict[str, Any]
    demo_mode: bool
    last_checked: datetime
