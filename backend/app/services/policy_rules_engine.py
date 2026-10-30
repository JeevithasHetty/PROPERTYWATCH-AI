import os
import re
import json
import datetime
import logging
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models import InsurancePolicy, PolicyRule, PolicyRuleExecution, Claim, Modification, OwnerDeclaration
from app.database import SessionLocal

logger = logging.getLogger(__name__)

# Predefined standard rules catalogue
DEFAULT_POLICY_RULES = [
    {
        "rule_code": "RULE-POL-PERIOD-01",
        "name": "Policy Effective Period & Incident Date Verification",
        "category": "Policy Period",
        "version": "1.0",
        "description": "Verifies that the reported incident date falls strictly within the active policy effective and expiration dates.",
        "rule_config": {"strict_expiry_check": True}
    },
    {
        "rule_code": "RULE-COV-LIMIT-01",
        "name": "Dwelling Coverage Limit & Sublimit Validation",
        "category": "Coverage Limit",
        "version": "1.0",
        "description": "Validates claimed loss against the dwelling coverage limit (Coverage A) and applicable sublimits.",
        "rule_config": {"enforce_dwelling_cap": True}
    },
    {
        "rule_code": "RULE-DED-APPLY-01",
        "name": "Peril-Specific Deductible Determination",
        "category": "Deductible",
        "version": "1.0",
        "description": "Determines the appropriate deductible (Standard vs Wind/Hail vs Water) and confirms claimed loss exceeds the deductible threshold.",
        "rule_config": {"min_loss_above_deductible": True}
    },
    {
        "rule_code": "RULE-EXCL-UNPERMITTED-01",
        "name": "Unpermitted Modification & Code Compliance Exclusion",
        "category": "Exclusion",
        "version": "1.0",
        "description": "Checks whether damage relates to an unpermitted structural addition or uncorroborated modification flagged by satellite monitoring.",
        "rule_config": {"require_permit_for_additions": True}
    },
    {
        "rule_code": "RULE-EXCL-WATER-01",
        "name": "Surface Water & Flood Exclusion Rule",
        "category": "Exclusion",
        "version": "1.0",
        "description": "Verifies whether the claimed cause involves excluded rising flood/surface waters versus covered sudden wind-driven water intrusion.",
        "rule_config": {"exclude_rising_water": True}
    },
    {
        "rule_code": "RULE-ENDORSE-SOLAR-01",
        "name": "Rooftop Solar Photovoltaic Endorsement Requirement",
        "category": "Declaration",
        "version": "1.0",
        "description": "Checks whether rooftop solar arrays are endorsed when solar or rooftop damage is claimed.",
        "rule_config": {"mandatory_solar_endorsement": True}
    },
    {
        "rule_code": "RULE-DECLARATION-TIMELY-01",
        "name": "Owner Material Alteration Declaration Rule",
        "category": "Declaration",
        "version": "1.0",
        "description": "Checks whether the owner submitted a timely declaration and corroborating documentation for detected physical property alterations.",
        "rule_config": {"flag_unreported_modifications": True}
    }
]

def init_policy_rules_in_db():
    """Seed policy rules catalogue in database if not present."""
    db = SessionLocal()
    try:
        for r_data in DEFAULT_POLICY_RULES:
            existing = db.query(PolicyRule).filter(PolicyRule.rule_code == r_data["rule_code"]).first()
            if not existing:
                rule = PolicyRule(
                    rule_code=r_data["rule_code"],
                    name=r_data["name"],
                    category=r_data["category"],
                    version=r_data["version"],
                    description=r_data["description"],
                    rule_config=r_data["rule_config"],
                    is_active=True
                )
                db.add(rule)
        db.commit()
    except Exception as e:
        logger.error(f"Error initializing policy rules: {e}")
        db.rollback()
    finally:
        db.close()


def extract_policy_terms_from_text(raw_text: str) -> Dict[str, Any]:
    """
    Extract structured insurance policy terms from document text using regex patterns.
    Never invents missing terms; returns None for unextracted values.
    """
    extracted = {
        "policy_number": None,
        "policy_type": None,
        "effective_date": None,
        "expiry_date": None,
        "coverage_limits": {},
        "deductibles": {},
        "exclusions": [],
        "endorsements": [],
        "confidence": 0.0
    }

    if not raw_text:
        return extracted

    # 1. Policy Number
    pol_match = re.search(r"(?:Policy\s*(?:Number|No\.?|#)\s*:?\s*)([A-Z0-9\-]+)", raw_text, re.IGNORECASE)
    if pol_match:
        extracted["policy_number"] = pol_match.group(1).strip()

    # 2. Policy Type
    type_match = re.search(r"(?:Policy\s*Type|Form)\s*:?\s*([A-Za-z0-9\s\-]+?)(?:\n|\r|;|$)", raw_text, re.IGNORECASE)
    if type_match:
        extracted["policy_type"] = type_match.group(1).strip()

    # 3. Dates
    eff_match = re.search(r"(?:Effective\s*Date|From)\s*:?\s*([0-9]{4}[-/][0-9]{2}[-/][0-9]{2}|[0-9]{2}[-/][0-9]{2}[-/][0-9]{4})", raw_text, re.IGNORECASE)
    if eff_match:
        extracted["effective_date"] = eff_match.group(1).strip()

    exp_match = re.search(r"(?:Expiration\s*Date|Expiry\s*Date|To|Until)\s*:?\s*([0-9]{4}[-/][0-9]{2}[-/][0-9]{2}|[0-9]{2}[-/][0-9]{2}[-/][0-9]{4})", raw_text, re.IGNORECASE)
    if exp_match:
        extracted["expiry_date"] = exp_match.group(1).strip()

    # 4. Coverage Limits
    dwelling_match = re.search(r"(?:Coverage\s*A|Dwelling(?:\s*Limit)?)\s*:?\s*\$?([0-9,]+)", raw_text, re.IGNORECASE)
    if dwelling_match:
        try:
            extracted["coverage_limits"]["dwelling"] = float(dwelling_match.group(1).replace(",", ""))
        except ValueError:
            pass

    personal_prop_match = re.search(r"(?:Coverage\s*C|Personal\s*Property)\s*:?\s*\$?([0-9,]+)", raw_text, re.IGNORECASE)
    if personal_prop_match:
        try:
            extracted["coverage_limits"]["personal_property"] = float(personal_prop_match.group(1).replace(",", ""))
        except ValueError:
            pass

    other_struct_match = re.search(r"(?:Coverage\s*B|Other\s*Structures)\s*:?\s*\$?([0-9,]+)", raw_text, re.IGNORECASE)
    if other_struct_match:
        try:
            extracted["coverage_limits"]["other_structures"] = float(other_struct_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # 5. Deductibles
    std_ded_match = re.search(r"(?:Standard|All\s*Perils?|Policy)\s*Deductible\s*:?\s*\$?([0-9,]+)", raw_text, re.IGNORECASE)
    if std_ded_match:
        try:
            extracted["deductibles"]["standard"] = float(std_ded_match.group(1).replace(",", ""))
        except ValueError:
            pass

    wind_ded_match = re.search(r"(?:Wind(?:storm)?(?:\s*/\s*Hail)?)\s*Deductible\s*:?\s*\$?([0-9,]+)", raw_text, re.IGNORECASE)
    if wind_ded_match:
        try:
            extracted["deductibles"]["wind_hail"] = float(wind_ded_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # 6. Endorsements scan
    if re.search(r"solar|photovoltaic", raw_text, re.IGNORECASE):
        extracted["endorsements"].append("Solar Photovoltaic Endorsement")
    if re.search(r"pool|swimming\s*pool", raw_text, re.IGNORECASE):
        extracted["endorsements"].append("Swimming Pool Liability Endorsement")
    if re.search(r"extended\s*replacement", raw_text, re.IGNORECASE):
        extracted["endorsements"].append("Extended Dwelling Replacement Endorsement")

    # 7. Exclusions scan
    if re.search(r"unpermitted|unauthorized\s*construction", raw_text, re.IGNORECASE):
        extracted["exclusions"].append("Unpermitted structural additions")
    if re.search(r"flood|surface\s*water", raw_text, re.IGNORECASE):
        extracted["exclusions"].append("Flood and rising waters")
    if re.search(r"wear\s*and\s*tear", raw_text, re.IGNORECASE):
        extracted["exclusions"].append("Wear, tear, and gradual deterioration")

    # Score confidence based on number of extracted fields
    fields_found = sum([
        1 if extracted["policy_number"] else 0,
        1 if extracted["effective_date"] else 0,
        1 if extracted["expiry_date"] else 0,
        1 if extracted["coverage_limits"].get("dwelling") else 0,
        1 if extracted["deductibles"].get("standard") else 0,
    ])
    extracted["confidence"] = round(fields_found / 5.0, 2)
    return extracted


class PolicyRulesEngine:
    """
    Deterministic insurance policy rules evaluation engine.
    Strictly evaluates configured policy terms, deductibles, exclusions, and endorsements.
    Logs execution history and reasons without guessing or inventing universal terms.
    """

    @staticmethod
    def evaluate_rule_pol_period(
        policy: InsurancePolicy,
        claim: Optional[Claim] = None,
        incident_date: Optional[datetime.datetime] = None
    ) -> Dict[str, Any]:
        """RULE-POL-PERIOD-01: Policy Effective Period & Incident Date Verification"""
        rule_code = "RULE-POL-PERIOD-01"
        rule_name = "Policy Effective Period & Incident Date Verification"
        clause = None

        dt = incident_date or (claim.incident_date if claim else None)
        if not dt:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "INCONCLUSIVE",
                "explanation": "No incident date provided; cannot verify policy effective period.",
                "applicable_clause": clause,
                "inputs": {"incident_date": None}
            }

        if not policy.effective_date or not policy.expiry_date:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "INCONCLUSIVE",
                "explanation": "Policy effective or expiry date is missing from verified policy terms.",
                "applicable_clause": clause,
                "inputs": {"effective_date": None, "expiry_date": None}
            }

        inputs = {
            "incident_date": dt.isoformat(),
            "policy_effective_date": policy.effective_date.isoformat(),
            "policy_expiry_date": policy.expiry_date.isoformat()
        }

        if not policy.terms_verified:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PENDING_REVIEW",
                "explanation": "Recorded policy dates have not been verified against the policy document.",
                "applicable_clause": None,
                "inputs": inputs
            }

        if policy.effective_date <= dt <= policy.expiry_date:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PASS",
                "explanation": f"Incident date ({dt.strftime('%Y-%m-%d')}) is within active policy term ({policy.effective_date.strftime('%Y-%m-%d')} to {policy.expiry_date.strftime('%Y-%m-%d')}).",
                "applicable_clause": clause,
                "inputs": inputs
            }
        else:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "ALERT_CREATED",
                "explanation": f"Incident date ({dt.strftime('%Y-%m-%d')}) is OUTSIDE the policy term ({policy.effective_date.strftime('%Y-%m-%d')} to {policy.expiry_date.strftime('%Y-%m-%d')}). Potential lack of coverage.",
                "applicable_clause": clause,
                "inputs": inputs
            }

    @staticmethod
    def evaluate_rule_cov_limit(
        policy: InsurancePolicy,
        claim: Optional[Claim] = None,
        claimed_amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """RULE-COV-LIMIT-01: Dwelling Coverage Limit & Sublimit Validation"""
        rule_code = "RULE-COV-LIMIT-01"
        rule_name = "Dwelling Coverage Limit & Sublimit Validation"
        clause = None

        amt = claimed_amount if claimed_amount is not None else (claim.estimated_loss if claim else None)
        if amt is None:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "INCONCLUSIVE",
                "explanation": "Claimed loss amount not specified; limit check inconclusive.",
                "applicable_clause": clause,
                "inputs": {"claimed_amount": None}
            }

        limits = policy.coverage_limits or {}
        dwelling_limit = limits.get("dwelling")

        if dwelling_limit is None:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PENDING_REVIEW",
                "explanation": "Dwelling coverage limit (Coverage A) is missing from policy record. Human adjuster verification required.",
                "applicable_clause": clause,
                "inputs": {"claimed_amount": amt, "coverage_limits": limits}
            }
        if not policy.terms_verified:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PENDING_REVIEW",
                "explanation": "A dwelling limit is recorded but has not been verified against the policy document.",
                "applicable_clause": None,
                "inputs": {"claimed_amount": amt, "dwelling_limit": dwelling_limit}
            }

        inputs = {"claimed_amount": amt, "dwelling_limit": dwelling_limit}
        if amt <= dwelling_limit:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PASS",
                "explanation": f"Claimed amount (${amt:,.2f}) is within the verified dwelling limit (${dwelling_limit:,.2f}).",
                "applicable_clause": clause,
                "inputs": inputs
            }
        else:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "ALERT_CREATED",
                "explanation": f"Claimed amount (${amt:,.2f}) exceeds policy dwelling limit (${dwelling_limit:,.2f}) by ${amt - dwelling_limit:,.2f}. Provisional payout must be capped.",
                "applicable_clause": clause,
                "inputs": inputs
            }

    @staticmethod
    def evaluate_rule_deductible(
        policy: InsurancePolicy,
        claim: Optional[Claim] = None,
        claimed_amount: Optional[float] = None,
        cause_of_loss: Optional[str] = None
    ) -> Dict[str, Any]:
        """RULE-DED-APPLY-01: Peril-Specific Deductible Determination"""
        rule_code = "RULE-DED-APPLY-01"
        rule_name = "Peril-Specific Deductible Determination"
        clause = None

        amt = claimed_amount if claimed_amount is not None else (claim.estimated_loss if claim else None)
        cause = cause_of_loss or (claim.reported_cause if claim else "")

        deductibles = policy.deductibles or {}
        std_ded = deductibles.get("standard")
        wind_ded = deductibles.get("wind_hail")

        is_wind = any(w in cause.lower() for w in ["wind", "hail", "tornado", "hurricane"])
        if not policy.terms_verified:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PENDING_REVIEW",
                "explanation": "Deductible terms have not been verified against the policy document.",
                "applicable_clause": None,
                "inputs": {"deductibles": deductibles}
            }
        if (is_wind and wind_ded is None) or (not is_wind and std_ded is None):
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PENDING_REVIEW",
                "explanation": "No applicable deductible is recorded for the reported cause. Human policy review is required.",
                "applicable_clause": None,
                "inputs": {"deductibles": deductibles, "cause_of_loss": cause}
            }

        applicable_ded = wind_ded if is_wind else std_ded
        ded_type = "wind_hail" if is_wind else "standard"

        inputs = {"claimed_amount": amt, "applicable_deductible": applicable_ded, "deductible_type": ded_type, "cause_of_loss": cause}

        if amt is None:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "INCONCLUSIVE",
                "explanation": f"Applicable deductible determined as ${applicable_ded:,.2f} ({ded_type}), but loss amount is missing.",
                "applicable_clause": clause,
                "inputs": inputs
            }

        if amt <= applicable_ded:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "ALERT_CREATED",
                "explanation": f"Claimed loss (${amt:,.2f}) is below or equal to the applicable {ded_type} (${applicable_ded:,.2f}). No net provisional payment.",
                "applicable_clause": clause,
                "inputs": inputs
            }
        else:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PASS",
                "explanation": f"Claimed loss (${amt:,.2f}) exceeds {ded_type} (${applicable_ded:,.2f}). Net provisional loss base: ${amt - applicable_ded:,.2f}.",
                "applicable_clause": clause,
                "inputs": inputs
            }

    @staticmethod
    def evaluate_rule_unpermitted_exclusion(
        policy: InsurancePolicy,
        modification: Optional[Modification] = None,
        declaration: Optional[OwnerDeclaration] = None,
        has_permit: Optional[bool] = None
    ) -> Dict[str, Any]:
        """RULE-EXCL-UNPERMITTED-01: Unpermitted Modification & Code Compliance Exclusion"""
        rule_code = "RULE-EXCL-UNPERMITTED-01"
        rule_name = "Unpermitted Modification & Code Compliance Exclusion"
        exclusions = policy.exclusions or []
        clause = next(
            (term for term in exclusions if "unpermitted" in term.lower() or "unauthorized" in term.lower()),
            None
        )

        if not clause:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "INCONCLUSIVE",
                "explanation": "No explicit unpermitted-construction term is recorded; applicability is inconclusive.",
                "applicable_clause": None,
                "inputs": {"exclusions": policy.exclusions}
            }
        if not policy.terms_verified:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PENDING_REVIEW",
                "explanation": "A possible unpermitted-construction term is recorded but has not been verified against the policy document.",
                "applicable_clause": clause,
                "inputs": {"exclusions": exclusions}
            }

        if modification is None:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PASS",
                "explanation": "No suspected unpermitted modification alerts active on this property.",
                "applicable_clause": clause,
                "inputs": {"active_modifications": 0}
            }

        # Check permit presence
        permit_present = has_permit
        if permit_present is None:
            if declaration and declaration.permit_number:
                permit_present = True
            elif any(ev.category == "Building Permit" for ev in modification.evidence_items):
                permit_present = True

        inputs = {
            "modification_alert_id": modification.modification_alert_id,
            "category": modification.suspected_category,
            "permit_present": permit_present,
            "modification_status": modification.status
        }

        if modification.status == "Verified" and permit_present:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PASS",
                "explanation": f"Modification {modification.modification_alert_id} ({modification.suspected_category}) has verified permit compliance on file.",
                "applicable_clause": clause,
                "inputs": inputs
            }
        elif permit_present is None or modification.status in ["New", "Awaiting Evidence", "Under Review", "Additional Evidence Required"]:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "MORE_EVIDENCE_REQUIRED",
                "explanation": f"Permit status for modification {modification.modification_alert_id} ({modification.suspected_category}) is unverified. Request evidence before evaluating the recorded policy term.",
                "applicable_clause": clause,
                "inputs": inputs
            }
        elif not permit_present:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "ALERT_CREATED",
                "explanation": f"Unpermitted structural alteration detected ({modification.suspected_category}) without permit. Exclusion clause may apply to damage in altered sector.",
                "applicable_clause": clause,
                "inputs": inputs
            }
        else:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PENDING_REVIEW",
                "explanation": "Status of modification permit is pending review by human examiner.",
                "applicable_clause": clause,
                "inputs": inputs
            }

    @staticmethod
    def evaluate_rule_solar_endorsement(
        policy: InsurancePolicy,
        claim: Optional[Claim] = None,
        modification: Optional[Modification] = None
    ) -> Dict[str, Any]:
        """RULE-ENDORSE-SOLAR-01: Rooftop Solar Photovoltaic Endorsement Requirement"""
        rule_code = "RULE-ENDORSE-SOLAR-01"
        rule_name = "Rooftop Solar Photovoltaic Endorsement Requirement"
        clause = None

        endorsements_str = str(policy.endorsements or []).lower()
        has_solar_endorsement = "solar" in endorsements_str or "photovoltaic" in endorsements_str

        # Check if claim or modification involves solar
        claim_text = (claim.description + " " + claim.reported_cause).lower() if claim else ""
        mod_text = (modification.suspected_category + " " + modification.description).lower() if modification else ""

        is_solar_relevant = "solar" in claim_text or "photovoltaic" in claim_text or "solar" in mod_text

        inputs = {
            "has_solar_endorsement": has_solar_endorsement,
            "solar_relevant": is_solar_relevant,
            "endorsements": policy.endorsements
        }

        if not is_solar_relevant:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "INCONCLUSIVE",
                "explanation": "No solar-related exposure was identified; this rule does not determine coverage for other causes.",
                "applicable_clause": None,
                "inputs": inputs
            }

        if has_solar_endorsement:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PASS",
                "explanation": "A solar/photovoltaic endorsement is recorded in the policy schedule.",
                "applicable_clause": None,
                "inputs": inputs
            }
        else:
            explicit_exclusion = next(
                (term for term in (policy.exclusions or [])
                 if ("solar" in term.lower() or "photovoltaic" in term.lower())
                 and any(word in term.lower() for word in ["exclude", "not covered", "not insured"])),
                None
            )
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "ALERT_CREATED" if explicit_exclusion and policy.terms_verified else "INCONCLUSIVE",
                "explanation": (
                    "The verified policy terms explicitly exclude this solar/photovoltaic exposure."
                    if explicit_exclusion and policy.terms_verified
                    else "No verified term establishes that a solar endorsement is required; human review is needed."
                ),
                "applicable_clause": explicit_exclusion,
                "inputs": inputs
            }

    @staticmethod
    def evaluate_rule_flood_exclusion(
        policy: InsurancePolicy,
        claim: Optional[Claim] = None,
        cause_of_loss: Optional[str] = None
    ) -> Dict[str, Any]:
        """RULE-EXCL-WATER-01: Surface Water & Flood Exclusion Rule"""
        rule_code = "RULE-EXCL-WATER-01"
        rule_name = "Surface Water & Flood Exclusion Rule"
        clause = None

        cause = (cause_of_loss or (claim.reported_cause if claim else "")).lower()
        desc = (claim.description if claim else "").lower()

        inputs = {"cause_of_loss": cause, "description": desc}

        flood_cause = any(f in cause for f in ["flood", "rising water", "storm surge", "tsunami"])
        flood_term = next(
            (term for term in (policy.exclusions or [])
             if any(word in term.lower() for word in ["flood", "rising water", "surface water", "storm surge"])),
            None
        )
        if flood_cause and not flood_term:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "INCONCLUSIVE",
                "explanation": "The reported cause refers to flood or rising water, but no matching policy exclusion is recorded.",
                "applicable_clause": None,
                "inputs": inputs
            }
        if flood_cause and flood_term and policy.terms_verified:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "ALERT_CREATED",
                "explanation": f"Reported cause '{cause}' matches a recorded policy exclusion term.",
                "applicable_clause": flood_term,
                "inputs": inputs
            }
        if flood_cause:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PENDING_REVIEW",
                "explanation": "A matching water exclusion is recorded but has not been verified against the policy document.",
                "applicable_clause": flood_term,
                "inputs": inputs
            }
        elif "water" in cause or "water" in desc:
            if any(w in cause or w in desc for w in ["wind", "roof", "shingle", "penetration", "breach"]):
                return {
                    "rule_code": rule_code,
                    "rule_name": rule_name,
                    "result": "INCONCLUSIVE",
                    "explanation": "Reported details mention wind or roof damage, but this rule cannot establish damage cause or coverage.",
                    "applicable_clause": None,
                    "inputs": inputs
                }
            else:
                return {
                    "rule_code": rule_code,
                    "rule_name": rule_name,
                    "result": "MORE_EVIDENCE_REQUIRED",
                    "explanation": "Water damage source is ambiguous. Distinguishing between wind-driven rain and groundwater intrusion requires plumbing/restoration invoice.",
                    "applicable_clause": clause,
                    "inputs": inputs
                }
        else:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "INCONCLUSIVE",
                "explanation": "This rule does not determine coverage for the reported cause.",
                "applicable_clause": None,
                "inputs": inputs
            }

    @staticmethod
    def evaluate_rule_declaration_timely(
        policy: InsurancePolicy,
        modification: Optional[Modification] = None,
        declaration: Optional[OwnerDeclaration] = None
    ) -> Dict[str, Any]:
        """RULE-DECLARATION-TIMELY-01: Owner Material Alteration Declaration Rule"""
        rule_code = "RULE-DECLARATION-TIMELY-01"
        rule_name = "Owner Material Alteration Declaration Rule"
        policy_terms = (policy.exclusions or []) + (policy.endorsements or [])
        declaration_term = next(
            (str(term) for term in policy_terms
             if "declaration" in str(term).lower() or "alteration" in str(term).lower()),
            None
        )
        clause = declaration_term

        if not declaration_term:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "INCONCLUSIVE",
                "explanation": "No explicit policy term about declarations or alterations is recorded.",
                "applicable_clause": None,
                "inputs": {"policy_terms": policy_terms}
            }
        if not policy.terms_verified:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PENDING_REVIEW",
                "explanation": "A declaration-related term is recorded but has not been verified against the policy document.",
                "applicable_clause": declaration_term,
                "inputs": {"policy_terms": policy_terms}
            }

        if not modification:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PASS",
                "explanation": "No modification alert on property requiring declaration.",
                "applicable_clause": clause,
                "inputs": {}
            }

        inputs = {
            "modification_id": modification.id,
            "has_declaration": declaration is not None,
            "declaration_status": declaration.status if declaration else None
        }

        if declaration:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "PASS",
                "explanation": f"Owner submitted formal {declaration.declaration_type} declaration regarding alteration on {declaration.created_at.strftime('%Y-%m-%d')}.",
                "applicable_clause": clause,
                "inputs": inputs
            }
        else:
            return {
                "rule_code": rule_code,
                "rule_name": rule_name,
                "result": "MORE_EVIDENCE_REQUIRED",
                "explanation": f"Modification {modification.modification_alert_id} ({modification.suspected_category}) has no linked owner declaration; request information before drawing a conclusion.",
                "applicable_clause": clause,
                "inputs": inputs
            }


def run_policy_rules_pipeline(
    db: Session,
    policy_id: int,
    claim_id: Optional[int] = None,
    modification_id: Optional[int] = None,
    custom_inputs: Optional[Dict[str, Any]] = None
) -> List[PolicyRuleExecution]:
    """
    Run complete policy rules evaluation pipeline and store execution logs in DB.
    """
    policy = db.query(InsurancePolicy).filter(InsurancePolicy.id == policy_id).first()
    if not policy:
        raise ValueError(f"InsurancePolicy with ID {policy_id} not found.")

    claim = db.query(Claim).filter(Claim.id == claim_id).first() if claim_id else None
    modification = db.query(Modification).filter(Modification.id == modification_id).first() if modification_id else None

    # Check for active declaration
    declaration = None
    if modification:
        declaration = db.query(OwnerDeclaration).filter(OwnerDeclaration.modification_id == modification.id).first()
    elif claim:
        # Check property's recent modification
        mod_rec = db.query(Modification).filter(Modification.property_id == claim.property_id).first()
        if mod_rec:
            modification = mod_rec
            declaration = db.query(OwnerDeclaration).filter(OwnerDeclaration.modification_id == mod_rec.id).first()

    ci = custom_inputs or {}

    rule_evaluators = [
        ("RULE-POL-PERIOD-01", "Policy Effective Period & Incident Date Verification", lambda: PolicyRulesEngine.evaluate_rule_pol_period(
            policy, claim, ci.get("incident_date")
        )),
        ("RULE-COV-LIMIT-01", "Dwelling Coverage Limit & Sublimit Validation", lambda: PolicyRulesEngine.evaluate_rule_cov_limit(
            policy, claim, ci.get("claimed_amount")
        )),
        ("RULE-DED-APPLY-01", "Peril-Specific Deductible Determination", lambda: PolicyRulesEngine.evaluate_rule_deductible(
            policy, claim, ci.get("claimed_amount"), ci.get("cause_of_loss")
        )),
        ("RULE-EXCL-UNPERMITTED-01", "Unpermitted Modification & Code Compliance Exclusion", lambda: PolicyRulesEngine.evaluate_rule_unpermitted_exclusion(
            policy, modification, declaration, ci.get("has_permit")
        )),
        ("RULE-ENDORSE-SOLAR-01", "Rooftop Solar Photovoltaic Endorsement Requirement", lambda: PolicyRulesEngine.evaluate_rule_solar_endorsement(
            policy, claim, modification
        )),
        ("RULE-EXCL-WATER-01", "Surface Water & Flood Exclusion Rule", lambda: PolicyRulesEngine.evaluate_rule_flood_exclusion(
            policy, claim, ci.get("cause_of_loss")
        )),
        ("RULE-DECLARATION-TIMELY-01", "Owner Material Alteration Declaration Rule", lambda: PolicyRulesEngine.evaluate_rule_declaration_timely(
            policy, modification, declaration
        ))
    ]

    executions = []
    for rule_code, rule_name, eval_fn in rule_evaluators:
        rule_entry = db.query(PolicyRule).filter(PolicyRule.rule_code == rule_code).first()
        if rule_entry and not rule_entry.is_active:
            continue
        try:
            res = eval_fn()

            exec_record = PolicyRuleExecution(
                policy_id=policy.id,
                claim_id=claim.id if claim else None,
                modification_id=modification.id if modification else None,
                rule_id=rule_entry.id if rule_entry else None,
                rule_code=res["rule_code"],
                rule_name=res["rule_name"],
                rule_version=rule_entry.version if rule_entry else "unregistered",
                inputs_snapshot=res.get("inputs", {}),
                result=res["result"],
                explanation=res["explanation"],
                applicable_clause=res.get("applicable_clause"),
                execution_timestamp=datetime.datetime.utcnow()
            )
            db.add(exec_record)
            executions.append(exec_record)
        except Exception as exc:
            logger.exception("Rule evaluation failed: %s", rule_code)
            executions.append(PolicyRuleExecution(
                policy_id=policy.id,
                claim_id=claim.id if claim else None,
                modification_id=modification.id if modification else None,
                rule_id=rule_entry.id if rule_entry else None,
                rule_code=rule_code,
                rule_name=rule_name,
                rule_version=rule_entry.version if rule_entry else "unregistered",
                inputs_snapshot=ci,
                result="SYSTEM_ERROR",
                explanation=f"Rule execution failed: {exc.__class__.__name__}",
                execution_timestamp=datetime.datetime.utcnow()
            ))
            db.add(executions[-1])

    db.commit()
    for e in executions:
        db.refresh(e)
    return executions
