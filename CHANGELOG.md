# Changelog

## Unreleased

### Implemented

- Added property-policy linking, dated policy and property versions, private policy document handling, and reviewer verification of policy terms without inventing absent coverage details.
- Added owner-scoped claim registration and evidence workflows, modification declarations, damage assessments, policy-rule executions, provisional calculations, reviewer recommendations, authorized decisions, and claim reports.
- Added file size/type/signature validation, SHA-256 duplicate checks, image metadata capture, audit records, and authenticated downloads for private documents and evidence.
- Secured owner-uploaded baseline photographs in private storage. Baseline retrieval now checks property access, legacy baseline URLs are rewritten to authenticated API URLs, and baseline-named images are blocked from the public snapshots route. Property inventory, detail, satellite, and image-comparison views load private imagery through authenticated requests.
- Added owner checks to property image comparison and analysis retrieval, and verified both comparison snapshots belong to the requested property.
- Marked building-change and rooftop-object inference unavailable unless actual model weights are configured; retained OpenCV visual differencing without presenting it as an ML prediction.
- Made policy-rule outcomes pending or inconclusive when policy terms are missing or unverified; provisional calculations require verified policy-derived inputs.
- Added Windows PowerShell setup guidance and policy-rule documentation.

### Files added

- `CHANGELOG.md`
- `backend/app/services/file_validation.py`
- `backend/app/services/datetime_utils.py`
- `backend/tests/test_workflow_safety.py`
- `frontend/src/components/AuthenticatedImage.jsx`
- `frontend/src/pages/ClaimsPage.jsx`

### Files modified

- Backend configuration and application: `backend/app/config.py`, `backend/app/main.py`, `backend/app/models.py`, `backend/app/schemas.py`
- Backend routers: `backend/app/routers/analysis.py`, `backend/app/routers/claims.py`, `backend/app/routers/decisions.py`, `backend/app/routers/declarations.py`, `backend/app/routers/evidence.py`, `backend/app/routers/evaluations.py`, `backend/app/routers/models_registry.py`, `backend/app/routers/modifications.py`, `backend/app/routers/policies.py`, `backend/app/routers/properties.py`, `backend/app/routers/reports.py`
- Backend services: `backend/app/services/ai_models_service.py`, `backend/app/services/policy_rules_engine.py`, `backend/app/services/report_service.py`
- Backend tests: `backend/tests/test_backend.py`
- Frontend: `frontend/src/api/client.js`, `frontend/src/App.jsx`, `frontend/src/components/ImageSlider.jsx`, `frontend/src/components/Sidebar.jsx`, `frontend/src/pages/LoginPage.jsx`, `frontend/src/pages/PropertyDetailPage.jsx`, `frontend/src/pages/PropertyInventoryPage.jsx`, `frontend/src/pages/ReviewerWorkspacePage.jsx`
- Configuration and documentation: `.env.example`, `backend/.env.example`, `README.md`, `docs/policy_rules_catalogue.md`

### Validation performed

- `backend\venv\Scripts\python.exe -m pytest -q tests\test_backend.py tests\test_workflow_safety.py` — **26 passed**; one Starlette/httpx deprecation warning.
- `backend\venv\Scripts\python.exe -m compileall -q app tests` — passed.
- `frontend\npm run build` — passed; Vite reports the existing large-bundle advisory.
- `frontend\npm run lint -- --quiet` — exited successfully; Oxlint reports unused-import warnings in the project.

### Remaining limitations

- No trained LEVIR-CD building-change or rooftop-object model weights are supplied; those inference operations report unavailable and do not fabricate detections.
- Policy document OCR/PDF term extraction is not configured. An authorized reviewer must verify terms against the uploaded source document.
- The configurable rules currently support the existing catalog and its stored metadata/version/active settings, not a general-purpose user-authored executable rule language.
- Owner declarations can be recorded, but a separate declaration-specific multi-file evidence-submission workflow is not complete; claim and modification evidence uploads remain available.
- Satellite availability and suitable resolution depend on configured providers and their returned catalogue data. A visual difference does not establish change cause or timing.
- Validation did not include a browser-driven end-to-end session or external live-provider credentials. Existing SQLite records were preserved; no database reset or migration was run.
