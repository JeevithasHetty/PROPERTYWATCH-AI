# Policy Rules Catalogue

This catalogue describes the built-in deterministic checks. They are not universal insurance terms, coverage interpretations, or claim decisions. Each rule can be activated/deactivated by an administrator. Rule metadata and version are stored with each execution. The current API does not provide a general-purpose rule language; `rule_config` is metadata and is not a user-defined executable expression.

## Outcomes

- `PASS`: The recorded input satisfied the narrow check; it is not a coverage approval.
- `ALERT_CREATED`: A configured check found a potential policy-term mismatch; it is not a denial.
- `MORE_EVIDENCE_REQUIRED`: Evidence needed to assess the recorded term is missing.
- `PENDING_REVIEW`: Terms or inputs are recorded but not verified or not applicable enough to evaluate.
- `INCONCLUSIVE`: The available policy terms or inputs do not permit a conclusion.
- `SYSTEM_ERROR`: Execution failed; the failure is persisted in the execution history.

Every execution captures the policy, claim/modification references, rule ID/version, inputs, result, explanation, and timestamp. See `PolicyRuleExecution`. AI and rules cannot record an authorized decision.

## Built-in checks

| Rule code | Check | Required data | Missing or unverified data |
| --- | --- | --- | --- |
| `RULE-POL-PERIOD-01` | Compare incident date to recorded effective/expiry dates | Incident date and policy dates | `INCONCLUSIVE` for absent dates; `PENDING_REVIEW` for unverified terms |
| `RULE-COV-LIMIT-01` | Compare reported amount with the recorded dwelling limit | Claim amount and `coverage_limits.dwelling` | `INCONCLUSIVE` for absent amount; `PENDING_REVIEW` for absent/unverified limit |
| `RULE-DED-APPLY-01` | Compare amount with the recorded deductible for the reported cause | Claim amount and `standard` or `wind_hail` deductible | `PENDING_REVIEW` when the applicable verified deductible is absent; no fallback deductible is assumed |
| `RULE-EXCL-UNPERMITTED-01` | Evaluate a recorded unpermitted/unauthorized-construction exclusion against an alert and permit evidence | Explicit matching exclusion term, verified policy terms, modification, permit evidence/declaration | `INCONCLUSIVE` if no matching term; `PENDING_REVIEW` if unverified; `MORE_EVIDENCE_REQUIRED` if permit status is unknown |
| `RULE-EXCL-WATER-01` | Compare a flood/rising-water cause against a recorded water exclusion | Cause and explicit matching exclusion term | `INCONCLUSIVE` if no matching term; `PENDING_REVIEW` if the term is unverified |
| `RULE-ENDORSE-SOLAR-01` | Check recorded solar endorsement/exclusion terms when the claim or alert mentions solar | Relevant claim/alert text and recorded endorsement/exclusion terms | `INCONCLUSIVE` when no explicit term establishes a requirement or exclusion |
| `RULE-DECLARATION-TIMELY-01` | Check declaration evidence only when a declaration/alteration term is explicitly recorded | Explicit term, verified policy, alert and declaration | `INCONCLUSIVE` if no term; `PENDING_REVIEW` if unverified; `MORE_EVIDENCE_REQUIRED` if the declaration is absent |

The evaluator does not infer a universal exclusion from a missing endorsement, treat absent evidence as proof that a permit does not exist, or decide cause/coverage from imagery. The clause field is populated only from a matching recorded policy term where available; built-in generic clause text is not used as policy evidence.

## Provisional calculation

The claim-assistance endpoint uses this documented method:

`max(0, min(gross_claimed_loss - explicitly assessed non-covered amount, verified policy limit) - verified deductible)`

The limit and deductible keys must exist in the linked policy's terms and `terms_verified` must be true. An authorized reviewer supplies the explicitly assessed non-covered amount and assumptions. The amount is provisional only and does not approve or deny a claim. Missing or unverified required values block calculation.

## Configuration and limitations

- View active defaults at `GET /api/policies/{policy_id}/rules`.
- Administrators can update a rule's name, description, version, active flag, and JSON metadata via `PUT /api/policies/rules/{rule_id}`.
- Inactive built-in rules are skipped. New custom executable rules are not supported; this API does not execute arbitrary expressions stored in JSON.
- Version updates do not rewrite prior execution records.
- Policy document OCR/PDF extraction is not configured; uploads are retained privately and term verification is manual.

## Test coverage

`backend/tests/test_workflow_safety.py` checks that omitted policy terms remain absent at the API/schema boundary, missing terms do not produce automatic conclusions, and provisional inputs do not provide caller-supplied policy limits or deductibles.
