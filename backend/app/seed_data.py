import os
import hashlib
import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from PIL import Image, ImageDraw

from app.database import SessionLocal, Base, engine
from app.config import settings
from app.models import (
    User, Property, PropertySnapshot, ImageAnalysis, Modification, Evidence,
    AuthenticityAnalysis, Review, AuditLog,
    InsurancePolicy, PolicyVersion, PolicyRule, PolicyRuleExecution,
    Claim, ClaimEvidence, ClaimStatusHistory, DamageAssessment, ProvisionalCalculation,
    ClaimRecommendation, ClaimDecision, OwnerDeclaration, Notification,
    PropertyVersion
)
from app.auth import hash_password
from app.services.satellite_service import generate_synthetic_satellite_tile
from app.services.cv_service import run_image_comparison_pipeline
from app.services.policy_rules_engine import run_policy_rules_pipeline, init_policy_rules_in_db
from app.services.ai_models_service import init_ai_model_registry

def create_sample_permit_document(dest_path: Path, title: str, permit_no: str, address: str):
    """Generate a clean visual building permit document image for demo evidence."""
    img = Image.new("RGB", (700, 900), color=(253, 252, 248))
    draw = ImageDraw.Draw(img)

    # Municipal Seal / Header Border
    draw.rectangle([(20, 20), (680, 880)], outline=(30, 58, 138), width=3)
    draw.rectangle([(26, 26), (674, 874)], outline=(147, 197, 253), width=1)

    # Header text
    draw.text((60, 50), "MUNICIPAL CORPORATION - BUILDING / ROOFTOP PERMIT (DEMO SAMPLE)", fill=(30, 58, 138))
    draw.line([(60, 75), (640, 75)], fill=(30, 58, 138), width=2)

    # Details
    draw.text((60, 110), f"PERMIT NUMBER:   {permit_no}", fill=(15, 23, 42))
    draw.text((60, 140), f"ISSUE DATE:      {datetime.datetime.utcnow().strftime('%d %B %Y')}", fill=(15, 23, 42))
    draw.text((60, 170), f"PROPERTY ADDR:   {address}", fill=(15, 23, 42))
    draw.text((60, 200), f"PROJECT SCOPE:   {title}", fill=(15, 23, 42))
    draw.text((60, 230), f"INSPECTION:      PASSED / CODE COMPLIANT", fill=(22, 101, 52))

    # Watermark Stamp
    draw.ellipse([(450, 680), (620, 850)], outline=(185, 28, 28), width=3)
    draw.text((480, 750), "APPROVED", fill=(185, 28, 28))
    draw.text((475, 775), "MUNICIPAL CODE", fill=(185, 28, 28))

    img.save(dest_path)

def seed_database():
    """Seed comprehensive demo users, properties, snapshots, alerts, and audit logs."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        if not settings.DEMO_MODE:
            # Live mode: no demo users, properties or synthetic imagery. Optionally bootstrap one admin.
            email, pwd = os.getenv("BOOTSTRAP_ADMIN_EMAIL", ""), os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
            if email and pwd and db.query(User).count() == 0:
                db.add(User(name="Administrator", email=email, password_hash=hash_password(pwd), role="admin"))
                db.commit()
                print("Bootstrapped admin account from environment.")
            return
        # 1. Seed Users if not present
        if db.query(User).count() == 0:
            print("Seeding initial users...")
            users = [
                User(
                    name="System Administrator",
                    email="admin@propertywatch.ai",
                    password_hash=hash_password("AdminPass123!"),
                    role="admin"
                ),
                User(
                    name="Elena Rostova",
                    email="reviewer@propertywatch.ai",
                    password_hash=hash_password("ReviewerPass123!"),
                    role="reviewer"
                ),
                User(
                    name="Marcus Vance",
                    email="manager@propertywatch.ai",
                    password_hash=hash_password("ManagerPass123!"),
                    role="manager"
                )
            ]
            db.add_all(users)
            db.commit()

        admin_user = db.query(User).filter(User.email == "admin@propertywatch.ai").first()
        reviewer_user = db.query(User).filter(User.email == "reviewer@propertywatch.ai").first()

        # 2. Seed Properties if not present
        if db.query(Property).count() == 0:
            print("Seeding properties, satellite tiles, and CV comparisons...")
            # Property 1: Rooftop Solar Addition
            p1 = Property(
                property_reference="PROP-2026-1001",
                owner_name="Rohan & Meera Deshmukh",
                owner_contact="rohan.deshmukh@example.in | +91 98200 00142",
                address="Flat 1204, Sea Breeze Apartments, Pali Hill, Bandra West, Mumbai, Maharashtra 400050",
                city="Mumbai",
                state="Maharashtra",
                postal_code="400050",
                latitude=19.0596,
                longitude=72.8295,
                property_type="Residential Single Family",
                number_of_floors=2,
                built_up_area=2850.0,
                reference_policy_number="POL-MH-89210-V",
                monitoring_enabled=True,
                notes="DEMO RECORD. Top-floor apartment with terrace; rooftop solar potential."
            )

            # Property 2: Swimming Pool Excavation
            p2 = Property(
                property_reference="PROP-2026-1002",
                owner_name="Horizon Capital Estates Pvt Ltd",
                owner_contact="ops@horizonestates.example.in | +91 40 5550 0189",
                address="Plot 45, Road No. 36, Jubilee Hills, Hyderabad, Telangana 500033",
                city="Hyderabad",
                state="Telangana",
                postal_code="500033",
                latitude=17.4326,
                longitude=78.4071,
                property_type="Residential Luxury Villa",
                number_of_floors=2,
                built_up_area=4200.0,
                reference_policy_number="POL-TG-44012-L",
                monitoring_enabled=True,
                notes="DEMO RECORD. Large rear parcel suitable for pool and patio."
            )

            # Property 3: Building Extension Wing
            p3 = Property(
                property_reference="PROP-2026-1003",
                owner_name="Subramaniam Family Trust",
                owner_contact="realty@subramaniamtrust.example.in | +91 44 5550 0112",
                address="No. 742, Venkatanarayana Road, T. Nagar, Chennai, Tamil Nadu 600017",
                city="Chennai",
                state="Tamil Nadu",
                postal_code="600017",
                latitude=13.0418,
                longitude=80.2341,
                property_type="Residential Single Family",
                number_of_floors=1,
                built_up_area=1950.0,
                reference_policy_number="POL-TN-11093-B",
                monitoring_enabled=True,
                notes="DEMO RECORD. Registered as single-storey home. Owner requested permit evaluation."
            )

            # Property 4: Baseline Pristine Commercial Property
            p4 = Property(
                property_reference="PROP-2026-1004",
                owner_name="Indiranagar Commerce Group",
                owner_contact="contact@indiranagarcommerce.example.in | +91 80 5550 0199",
                address="100 Feet Road, Indiranagar, Bengaluru, Karnataka 560038",
                city="Bengaluru",
                state="Karnataka",
                postal_code="560038",
                latitude=12.9784,
                longitude=77.6408,
                property_type="Commercial Office",
                number_of_floors=4,
                built_up_area=15600.0,
                reference_policy_number="POL-KA-99120-C",
                monitoring_enabled=True,
                notes="DEMO RECORD. Commercial structure. Baseline registered; no modifications recorded."
            )

            for _p in (p1, p2, p3, p4):
                _p.is_demo = True
            db.add_all([p1, p2, p3, p4])
            db.commit()
            db.refresh(p1); db.refresh(p2); db.refresh(p3); db.refresh(p4)

            # 3. Generate Satellite Snapshots and Image Analysis for Property 1 (Solar Array)
            snap1_base_file = generate_synthetic_satellite_tile("2026-01-10", "baseline", p1.latitude, p1.longitude)
            snap1_mod_file = generate_synthetic_satellite_tile("2026-06-15", "solar", p1.latitude, p1.longitude)

            s1_base = PropertySnapshot(
                property_id=p1.id,
                image_path=f"/static/snapshots/{Path(snap1_base_file).name}",
                image_source="DEMO synthetic tile (not satellite data)",
                acquisition_date=datetime.datetime(2026, 1, 10),
                cloud_coverage=0.4,
                is_baseline=True,
                data_origin="DEMO_SYNTHETIC",
                capture_metadata={"sensor": "MSI MultiSpectral", "bands": ["B04", "B03", "B02"]}
            )
            s1_mod = PropertySnapshot(
                property_id=p1.id,
                image_path=f"/static/snapshots/{Path(snap1_mod_file).name}",
                image_source="DEMO synthetic tile (not satellite data)",
                acquisition_date=datetime.datetime(2026, 6, 15),
                cloud_coverage=0.8,
                is_baseline=False,
                data_origin="DEMO_SYNTHETIC",
                capture_metadata={"sensor": "MSI MultiSpectral", "bands": ["B04", "B03", "B02"]}
            )
            db.add_all([s1_base, s1_mod])
            db.commit()
            db.refresh(s1_base); db.refresh(s1_mod)

            p1.baseline_image_url = s1_base.image_path
            p1.last_monitoring_date = datetime.datetime(2026, 6, 15)

            # Run CV comparison for Property 1
            cv1 = run_image_comparison_pipeline(snap1_base_file, snap1_mod_file, p1.id)
            analysis1 = ImageAnalysis(
                property_id=p1.id,
                baseline_snapshot_id=s1_base.id,
                comparison_snapshot_id=s1_mod.id,
                algorithm_name=cv1["algorithm_name"],
                change_score=cv1["change_score"],
                changed_area_percentage=cv1["changed_area_percentage"],
                diff_image_path=cv1["diff_image_path"],
                heatmap_image_path=cv1["heatmap_image_path"],
                contours_count=cv1["contours_count"],
                analysis_result=cv1["analysis_result"],
                explanation=cv1["explanation"],
                limitations=cv1["limitations"]
            )
            db.add(analysis1)
            db.commit()
            db.refresh(analysis1)

            # Create Modification Alert 1 (Verified status)
            mod1 = Modification(
                modification_alert_id="MOD-2026-0001",
                property_id=p1.id,
                analysis_id=analysis1.id,
                suspected_category="Rooftop Solar Array",
                description="High-contrast rectangular grid pattern detected on south-facing rooftop slope.",
                status="Verified",
                change_score=cv1["change_score"],
                detected_at=datetime.datetime(2026, 6, 16),
                verified_at=datetime.datetime(2026, 6, 22),
                reviewer_id=reviewer_user.id if reviewer_user else None,
                reviewer_notes="Building permit and contractor invoice verified against DISCOM net-metering approval (demo).",
                decision_reason="Submitted electrical permit #SOL-2026-881 and rooftop photographs confirm 14.4kW solar PV array."
            )
            db.add(mod1)
            db.commit()
            db.refresh(mod1)

            # Generate sample permit evidence document
            permit1_path = settings.UPLOADS_DIR / f"permit_{mod1.id}_solar.png"
            create_sample_permit_document(
                permit1_path,
                title="14.4 kW Photovoltaic Solar Rooftop Installation",
                permit_no="ELEC-MH-2026-9041",
                address=p1.address
            )
            permit1_bytes = permit1_path.read_bytes()

            ev1 = Evidence(
                modification_id=mod1.id,
                uploaded_by="David Miller (Owner)",
                file_path=f"/static/uploads/{permit1_path.name}",
                original_filename="Electrical_Solar_Permit_2026.png",
                file_type="image/png",
                file_size=len(permit1_bytes),
                file_hash=hashlib.sha256(permit1_bytes).hexdigest(),
                description="Municipal corporation approved rooftop solar permit (demo sample).",
                category="Building Permit",
                uploaded_at=datetime.datetime(2026, 6, 18)
            )
            db.add(ev1)
            db.commit()
            db.refresh(ev1)

            # Authenticity record for permit
            auth1 = AuthenticityAnalysis(
                evidence_id=ev1.id,
                provider="PropertyWatch Local Forensic Engine",
                model_name="ELA-Artifact-Detector-v1",
                result="No AI-generation signal detected by the configured model",
                score=0.08,
                explanation="Consistent document typography and document scanning compression curve. Valid municipal header.",
                is_demo=False
            )
            db.add(auth1)

            # Review record for mod1
            rev1 = Review(
                modification_id=mod1.id,
                reviewer_id=reviewer_user.id if reviewer_user else 1,
                decision="Verified",
                reason="Permit documentation matches rooftop footprint. Confirmed physical installation.",
                notes="Property record updated with rooftop solar asset.",
                created_at=datetime.datetime(2026, 6, 22)
            )
            db.add(rev1)

            # Property 2: Swimming pool (Under Review)
            snap2_base_file = generate_synthetic_satellite_tile("2026-02-01", "baseline", p2.latitude, p2.longitude)
            snap2_mod_file = generate_synthetic_satellite_tile("2026-07-20", "pool", p2.latitude, p2.longitude)

            s2_base = PropertySnapshot(
                property_id=p2.id,
                image_path=f"/static/snapshots/{Path(snap2_base_file).name}",
                image_source="DEMO synthetic tile (not satellite data)",
                acquisition_date=datetime.datetime(2026, 2, 1),
                cloud_coverage=0.2,
                is_baseline=True,
                data_origin="DEMO_SYNTHETIC"
            )
            s2_mod = PropertySnapshot(
                property_id=p2.id,
                image_path=f"/static/snapshots/{Path(snap2_mod_file).name}",
                image_source="DEMO synthetic tile (not satellite data)",
                acquisition_date=datetime.datetime(2026, 7, 20),
                cloud_coverage=0.1,
                is_baseline=False,
                data_origin="DEMO_SYNTHETIC"
            )
            db.add_all([s2_base, s2_mod])
            db.commit()
            p2.baseline_image_url = s2_base.image_path
            p2.last_monitoring_date = datetime.datetime(2026, 7, 20)

            cv2_res = run_image_comparison_pipeline(snap2_base_file, snap2_mod_file, p2.id)
            analysis2 = ImageAnalysis(
                property_id=p2.id,
                baseline_snapshot_id=s2_base.id,
                comparison_snapshot_id=s2_mod.id,
                algorithm_name=cv2_res["algorithm_name"],
                change_score=cv2_res["change_score"],
                changed_area_percentage=cv2_res["changed_area_percentage"],
                diff_image_path=cv2_res["diff_image_path"],
                heatmap_image_path=cv2_res["heatmap_image_path"],
                contours_count=cv2_res["contours_count"],
                analysis_result=cv2_res["analysis_result"],
                explanation=cv2_res["explanation"],
                limitations=cv2_res["limitations"]
            )
            db.add(analysis2)
            db.commit()

            mod2 = Modification(
                modification_alert_id="MOD-2026-0002",
                property_id=p2.id,
                analysis_id=analysis2.id,
                suspected_category="Swimming Pool Construction",
                description="Rear lawn excavation and turquoise water spectral signature consistent with in-ground swimming pool.",
                status="Under Review",
                change_score=cv2_res["change_score"],
                detected_at=datetime.datetime(2026, 7, 21),
                reviewer_id=reviewer_user.id if reviewer_user else None,
                reviewer_notes="Excavation invoice uploaded. Awaiting final building safety fence sign-off."
            )
            db.add(mod2)
            db.commit()

            # Property 3: Building Extension Wing (Awaiting Evidence)
            snap3_base_file = generate_synthetic_satellite_tile("2026-03-05", "baseline", p3.latitude, p3.longitude)
            snap3_mod_file = generate_synthetic_satellite_tile("2026-08-12", "extension", p3.latitude, p3.longitude)

            s3_base = PropertySnapshot(
                property_id=p3.id,
                image_path=f"/static/snapshots/{Path(snap3_base_file).name}",
                image_source="DEMO synthetic tile (not satellite data)",
                acquisition_date=datetime.datetime(2026, 3, 5),
                cloud_coverage=0.0,
                is_baseline=True,
                data_origin="DEMO_SYNTHETIC"
            )
            s3_mod = PropertySnapshot(
                property_id=p3.id,
                image_path=f"/static/snapshots/{Path(snap3_mod_file).name}",
                image_source="DEMO synthetic tile (not satellite data)",
                acquisition_date=datetime.datetime(2026, 8, 12),
                cloud_coverage=1.2,
                is_baseline=False,
                data_origin="DEMO_SYNTHETIC"
            )
            db.add_all([s3_base, s3_mod])
            db.commit()
            p3.baseline_image_url = s3_base.image_path
            p3.last_monitoring_date = datetime.datetime(2026, 8, 12)

            cv3_res = run_image_comparison_pipeline(snap3_base_file, snap3_mod_file, p3.id)
            analysis3 = ImageAnalysis(
                property_id=p3.id,
                baseline_snapshot_id=s3_base.id,
                comparison_snapshot_id=s3_mod.id,
                algorithm_name=cv3_res["algorithm_name"],
                change_score=cv3_res["change_score"],
                changed_area_percentage=cv3_res["changed_area_percentage"],
                diff_image_path=cv3_res["diff_image_path"],
                heatmap_image_path=cv3_res["heatmap_image_path"],
                contours_count=cv3_res["contours_count"],
                analysis_result=cv3_res["analysis_result"],
                explanation=cv3_res["explanation"],
                limitations=cv3_res["limitations"]
            )
            db.add(analysis3)
            db.commit()

            mod3 = Modification(
                modification_alert_id="MOD-2026-0003",
                property_id=p3.id,
                analysis_id=analysis3.id,
                suspected_category="Building Extension / Additional Story",
                description="Perimeter footprint expansion detected along western elevation representing +650 sq ft structural addition.",
                status="Awaiting Evidence",
                change_score=cv3_res["change_score"],
                detected_at=datetime.datetime(2026, 8, 14)
            )
            db.add(mod3)
            db.commit()

            # Property 4: Baseline only
            snap4_base_file = generate_synthetic_satellite_tile("2026-04-10", "baseline", p4.latitude, p4.longitude)
            s4_base = PropertySnapshot(
                property_id=p4.id,
                image_path=f"/static/snapshots/{Path(snap4_base_file).name}",
                image_source="DEMO synthetic tile (not satellite data)",
                acquisition_date=datetime.datetime(2026, 4, 10),
                cloud_coverage=0.0,
                is_baseline=True,
                data_origin="DEMO_SYNTHETIC"
            )
            db.add(s4_base)
            db.commit()
            p4.baseline_image_url = s4_base.image_path
            p4.last_monitoring_date = datetime.datetime(2026, 4, 10)
            db.commit()

            # Audit Trail Entries
            audits = [
                AuditLog(
                    user_id=admin_user.id if admin_user else 1,
                    entity_type="Property",
                    entity_id=str(p1.id),
                    action="PROPERTY_REGISTERED",
                    notes="Registered property PROP-2026-1001",
                    timestamp=datetime.datetime(2026, 1, 10, 9, 30)
                ),
                AuditLog(
                    user_id=admin_user.id if admin_user else 1,
                    entity_type="PropertySnapshot",
                    entity_id=str(s1_mod.id),
                    action="SATELLITE_SNAPSHOT_RETRIEVED",
                    notes="Retrieved Sentinel-2 pass for 2026-06-15",
                    timestamp=datetime.datetime(2026, 6, 15, 14, 20)
                ),
                AuditLog(
                    user_id=reviewer_user.id if reviewer_user else 2,
                    entity_type="Modification",
                    entity_id=str(mod1.id),
                    action="MODIFICATION_VERIFIED",
                    notes="Reviewer confirmed rooftop solar array installation.",
                    timestamp=datetime.datetime(2026, 6, 22, 11, 45)
                )
            ]
            db.add_all(audits)
            db.commit()

            print("Database successfully seeded with realistic sample properties, satellite tiles, and alerts!")

        # 3. Ensure owner and decision maker accounts exist
        owner_user = db.query(User).filter(User.email == "owner@propertywatch.ai").first()
        if not owner_user:
            owner_user = User(
                name="David Miller (Property Owner)",
                email="owner@propertywatch.ai",
                password_hash=hash_password("OwnerPass123!"),
                role="owner"
            )
            db.add(owner_user)

        decisionmaker_user = db.query(User).filter(User.email == "decisionmaker@propertywatch.ai").first()
        if not decisionmaker_user:
            decisionmaker_user = User(
                name="Sarah Jenkins (Authorized Decision Maker)",
                email="decisionmaker@propertywatch.ai",
                password_hash=hash_password("DecisionPass123!"),
                role="decision_maker"
            )
            db.add(decisionmaker_user)
        db.commit()
        owner_user = db.query(User).filter(User.email == "owner@propertywatch.ai").first()
        decisionmaker_user = db.query(User).filter(User.email == "decisionmaker@propertywatch.ai").first()

        # Link Property 1 to owner_user
        p1 = db.query(Property).filter(Property.property_reference == "PROP-2026-1001").first()
        if p1 and not p1.owner_user_id and owner_user:
            p1.owner_user_id = owner_user.id
            db.commit()

        # 4. Seed Insurance Policies if not present
        if db.query(InsurancePolicy).count() == 0:
            print("Seeding insurance policies and linking to properties...")
            used_policy_numbers = set()
            props = db.query(Property).order_by(Property.id).all()
            for prop in props:
                base_no = prop.reference_policy_number or f"POL-{prop.property_reference.replace('PROP-', '')}-A"
                pol_no = base_no
                suffix = 1
                while pol_no in used_policy_numbers or db.query(InsurancePolicy).filter(InsurancePolicy.policy_number == pol_no).first():
                    pol_no = f"{base_no}-{suffix}"
                    suffix += 1
                used_policy_numbers.add(pol_no)
                prop.reference_policy_number = pol_no
                is_p1 = (prop.property_reference == "PROP-2026-1001")
                is_p2 = (prop.property_reference == "PROP-2026-1002")

                pol = InsurancePolicy(
                    policy_number=pol_no,
                    property_id=prop.id,
                    policy_type="Home Insurance (Bharat Griha Raksha style) - DEMO" if "Commercial" not in prop.property_type else "Standard Fire & Special Perils (SFSP) - DEMO",
                    status="Active",
                    effective_date=datetime.datetime(2026, 1, 1),
                    expiry_date=datetime.datetime(2027, 1, 1),
                    coverage_limits={
                        "dwelling": 8500000.0 if is_p1 else 12000000.0,
                        "personal_property": 500000.0,
                        "other_structures": 500000.0,
                        "loss_of_use": 300000.0,
                        "liability": 1000000.0
                    },
                    deductibles={
                        "standard": 10000.0,
                        "wind_hail": 25000.0,
                        "water_damage": 15000.0
                    },
                    exclusions=[
                        "Unpermitted structural additions",
                        "Flood and rising waters",
                        "Earth movement",
                        "Wear, tear, and gradual deterioration",
                        "Intentional acts"
                    ],
                    endorsements=[
                        "Solar Photovoltaic Endorsement #SP-401",
                        "Extended Replacement Cost 125%"
                    ] if is_p1 else (
                        ["In-ground Swimming Pool Liability Endorsement"] if is_p2 else ["Extended Replacement Cost 125%"]
                    ),
                    terms_verified=True,
                    notes=f"DEMO SAMPLE policy for {prop.property_reference}: illustrative terms, not a real insurer's wording.",
                    structured_terms={
                        "insured_perils": ["Fire", "Lightning", "Storm, cyclone, typhoon, tempest, hurricane, tornado", "Impact damage", "Bursting/overflowing of water tanks, apparatus, pipes"],
                        "sub_limits": {"Solar": 500000.0},
                        "sum_insured": 8500000.0 if is_p1 else 12000000.0,
                        "reinstatement_value": 8500000.0 if is_p1 else 12000000.0,
                        "average_clause": False,
                        "insured_usage": "Residential" if "Commercial" not in prop.property_type else "Commercial office",
                        "conditions": ["Material alterations to the insured property must be disclosed to the insurer."],
                    },
                    created_at=datetime.datetime(2026, 1, 1),
                    updated_at=datetime.datetime(2026, 1, 1)
                )
                db.add(pol)
                db.commit()

                # Add initial PolicyVersion
                db.add(PolicyVersion(
                    policy_id=pol.id,
                    version_number=1,
                    terms_snapshot={
                        "policy_number": pol.policy_number,
                        "policy_type": pol.policy_type,
                        "coverage_limits": pol.coverage_limits,
                        "deductibles": pol.deductibles,
                        "exclusions": pol.exclusions,
                        "endorsements": pol.endorsements
                    },
                    change_reason="Policy inception record",
                    changed_by_user_id=admin_user.id if admin_user else 1,
                    created_at=datetime.datetime(2026, 1, 1)
                ))

                # Add initial PropertyVersion
                db.add(PropertyVersion(
                    property_id=prop.id,
                    version_number=1,
                    attributes_snapshot={
                        "owner_name": prop.owner_name,
                        "address": prop.address,
                        "property_type": prop.property_type,
                        "number_of_floors": prop.number_of_floors,
                        "built_up_area": prop.built_up_area,
                        "reference_policy_number": prop.reference_policy_number
                    },
                    change_reason="Initial property registration baseline",
                    changed_by_user_id=admin_user.id if admin_user else 1,
                    created_at=prop.created_at
                ))
            db.commit()

        # 5. Seed Owner Declarations if not present
        if db.query(OwnerDeclaration).count() == 0:
            print("Seeding owner declarations...")
            p1 = db.query(Property).filter(Property.property_reference == "PROP-2026-1001").first()
            mod1 = db.query(Modification).filter(Modification.property_id == (p1.id if p1 else 1)).first()
            if p1 and owner_user:
                decl = OwnerDeclaration(
                    property_id=p1.id,
                    modification_id=mod1.id if mod1 else None,
                    user_id=owner_user.id,
                    declaration_type="CONFIRM",
                    statement="We contracted Sunrise Solar Solutions Pvt Ltd for a 15-panel residential rooftop solar installation under municipal electrical permit #E-2026-8812.",
                    permit_number="E-2026-8812",
                    contractor_name="Sunrise Solar Solutions Pvt Ltd",
                    completion_date=datetime.datetime(2026, 6, 20),
                    status="Verified",
                    reviewer_response="Permit verified with the municipal building-proposal portal (demo). Endorsement verified under policy.",
                    created_at=datetime.datetime(2026, 6, 21, 10, 0),
                    updated_at=datetime.datetime(2026, 6, 22, 11, 0)
                )
                db.add(decl)
                db.commit()

        # 6. Seed Claims, Evidence, Damage Assessment, Calculations & Recommendations
        if db.query(Claim).count() == 0:
            print("Seeding insurance claims and calculations...")
            p1 = db.query(Property).filter(Property.property_reference == "PROP-2026-1001").first()
            pol1 = db.query(InsurancePolicy).filter(InsurancePolicy.property_id == (p1.id if p1 else 1)).first()

            if p1 and pol1 and owner_user:
                claim = Claim(
                    claim_reference="CLM-2026-0001",
                    property_id=p1.id,
                    policy_id=pol1.id,
                    user_id=owner_user.id,
                    incident_date=datetime.datetime(2026, 7, 18, 16, 30),
                    reported_cause="Severe Windstorm & Hail",
                    description="Severe pre-monsoon thunderstorm with 100 km/h wind gusts caused heavy tree branch to puncture north slope of composite roof and cracked 2 photovoltaic solar modules. Water intrusion noted in attic and master bedroom ceiling.",
                    estimated_loss=450000.0,
                    loss_items=[{"category": "Roof repair", "amount": 300000.0}, {"category": "Solar", "amount": 150000.0}],
                    status="Provisional Calculation Ready",
                    created_at=datetime.datetime(2026, 7, 19, 9, 15),
                    updated_at=datetime.datetime(2026, 7, 20, 14, 0)
                )
                db.add(claim)
                db.commit()
                db.refresh(claim)

                # Status history
                db.add(ClaimStatusHistory(
                    claim_id=claim.id,
                    from_status="New",
                    to_status="Submitted",
                    changed_by_user_id=owner_user.id,
                    notes="Claim registered by owner with damage description",
                    timestamp=datetime.datetime(2026, 7, 19, 9, 15)
                ))
                db.add(ClaimStatusHistory(
                    claim_id=claim.id,
                    from_status="Submitted",
                    to_status="Provisional Calculation Ready",
                    changed_by_user_id=reviewer_user.id if reviewer_user else 2,
                    notes="Damage assessment and provisional settlement calculation completed",
                    timestamp=datetime.datetime(2026, 7, 20, 14, 0)
                ))

                # Evidence item
                claim_ev = ClaimEvidence(
                    claim_id=claim.id,
                    uploaded_by_user_id=owner_user.id,
                    file_path="/static/uploads/sample_damage_photo.jpg",
                    original_filename="storm_roof_damage_july18.jpg",
                    file_type="image/jpeg",
                    file_size=2458000,
                    file_hash=hashlib.sha256(b"storm_roof_damage_photo_hash_content_2026").hexdigest(),
                    category="Damage Photograph",
                    description="Rooftop puncture and cracked solar panel glass following July 18 windstorm",
                    metadata_json={"mime_type": "image/jpeg", "source": "Owner Camera Upload"},
                    uploaded_at=datetime.datetime(2026, 7, 19, 9, 30)
                )
                db.add(claim_ev)

                # Damage Assessment
                snaps = db.query(PropertySnapshot).filter(PropertySnapshot.property_id == p1.id).all()
                pre_s = snaps[0] if snaps else None
                post_s = snaps[1] if len(snaps) > 1 else pre_s

                dmg = DamageAssessment(
                    claim_id=claim.id,
                    pre_event_snapshot_id=pre_s.id if pre_s else None,
                    post_event_snapshot_id=post_s.id if post_s else None,
                    observed_damage_indicators=[
                        "Composite roof penetration on north-facing slope",
                        "Fractured glass cover on 2 photovoltaic solar modules",
                        "Attic ceiling water staining"
                    ],
                    ai_damage_suggestions={
                        "change_detected": True,
                        "change_area_percentage": 6.8,
                        "summary": "LEVIR-CD detected localized rooftop surface anomaly consistent with structural impact. Confidence 0.88.",
                        "limitations": "Optical resolution limits micro-tear detection; physical roof tarping visible."
                    },
                    ai_model_name="LEVIR-CD-Building-v2 + OpenCV Differencing",
                    ai_confidence=0.88,
                    human_findings="Examiner corroborated damage photograph and IMD weather records (98 km/h peak gust at the Santacruz observatory).",
                    missing_evidence_flags=[],
                    unresolved_policy_terms_flags=[],
                    assessment_status="Complete",
                    assessed_by_user_id=reviewer_user.id if reviewer_user else 2,
                    created_at=datetime.datetime(2026, 7, 20, 11, 0),
                    updated_at=datetime.datetime(2026, 7, 20, 11, 0)
                )
                db.add(dmg)
                db.commit()

                # Provisional Calculation
                calc = ProvisionalCalculation(
                    claim_id=claim.id,
                    damage_assessment_id=dmg.id,
                    gross_claimed_loss=450000.0,
                    applicable_coverage_limit=8500000.0,
                    limit_category="Dwelling Coverage Limit (Coverage A)",
                    non_covered_excluded_amount=0.0, # Solar is endorsed
                    applicable_deductible=25000.0, # Wind/Hail deductible
                    deductible_type_applied="Wind/Hail Deductible",
                    provisional_net_payout=425000.0,
                    calculation_method="Net Provisional = max(0, min(Gross - Excluded, Limit) - Deductible)",
                    assumptions="Solar Photovoltaic Endorsement #SP-401 verified. Deductible applied per Section I Schedule.",
                    is_provisional=True,
                    calculated_by_user_id=reviewer_user.id if reviewer_user else 2,
                    created_at=datetime.datetime(2026, 7, 20, 13, 30)
                )
                db.add(calc)

                # Reviewer Recommendation
                rec = ClaimRecommendation(
                    claim_id=claim.id,
                    reviewer_id=reviewer_user.id if reviewer_user else 2,
                    recommendation_type="APPROVE_PROVISIONAL",
                    recommended_amount=425000.0,
                    reasoning="All policy conditions satisfied. Solar array is verified under endorsement #SP-401. Deductible of ₹25,000 applied.",
                    applicable_policy_clauses=[
                        "Section I - Perils Insured Against: Windstorm or Hail",
                        "Endorsement SP-01: Solar Photovoltaic Systems"
                    ],
                    evidence_references=["storm_roof_damage_july18.jpg", "MOD-2026-0001"],
                    created_at=datetime.datetime(2026, 7, 20, 14, 0)
                )
                db.add(rec)
                db.commit()

                # Run Policy Rules Pipeline
                try:
                    run_policy_rules_pipeline(db=db, policy_id=pol1.id, claim_id=claim.id)
                except Exception as e:
                    print(f"Policy rules execution warning during seed: {e}")

                # Notifications
                db.add(Notification(
                    user_id=owner_user.id,
                    title="Provisional Claim Calculation Prepared",
                    message="Provisional calculation of ₹4,25,000.00 prepared for claim CLM-2026-0001 (Wind/Hail Deductible applied).",
                    type="CLAIM_STATUS_UPDATE",
                    link=f"/claims/{claim.id}",
                    created_at=datetime.datetime(2026, 7, 20, 14, 30)
                ))
                db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
