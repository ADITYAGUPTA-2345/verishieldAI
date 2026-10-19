# Security feature validation

## Results

The completed implementation was checked locally with the original dataset and saved classifier present:

- `python -m pytest backend/tests ml/tests -q`: **115 passed**, one dependency deprecation warning from Starlette TestClient.
- `node --test extension/tests/popup.test.cjs`: **7 passed**.
- Isolated headless installed Chrome, controlled offline API/page fixtures: eight sections rendered, no page errors, zero external requests, no horizontal overflow, and a vertically scrolling main panel. This is a layout check, not a live website or employer verification.
- The Joblib SHA-256 matches `artifact_sha256` in `ml/reports/evaluation.json`. Neither the training pipeline nor saved model was modified.
- Mocked TinyFish regression exercised the existing three Search requests and one Fetch request, with domain/email enrichment adding no provider calls. No new live TinyFish investigation was performed for these local features.
- Ignore checks covered `backend/.env`, virtual environments, dataset, model artifacts, and local validation artifacts. An exact-value audit found no configured API secret in 69 publishable files. `backend/.env` was not modified. No browser permission was added.

## Reproduce automated checks on Windows

From the repository root after the existing README setup:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests ml/tests -q
node --test extension/tests/popup.test.cjs
git check-ignore backend/.env .venv/ ml/data/fake_job_postings.csv ml/artifacts/job_classifier.joblib
```

The new Python coverage is in `test_domain_security.py`, `test_email_security.py`, and `test_security_assessments.py`. It includes matching domains/subdomains, lookalikes, misleading subdomains, character substitution, IDNA, missing authority, platforms, public providers, recruitment-context filtering, real saved-model inference, and mocked investigation enrichment. Fictional employer fixtures do not establish real ownership.

## Manual application check

1. Start the existing backend with `.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`.
2. Open `chrome://extensions`, enable Developer mode, and reload the existing unpacked `extension` directory.
3. Open a public job listing and click **Scan This Page**. Check job information/time, separate ML output and rules, domain information, and any recruitment-context email. A missing reviewed domain must remain unavailable. A missing email must display **No recruitment email detected.**
4. Correct the employer name if needed and click **Investigate Employer** with the existing backend TinyFish configuration. Check existing source URLs and uncertainty disclosures, then sections 6–8. A supplied company website alone must not establish ownership. This action consumes normal provider credits; it is not required for the offline checks.
5. For an already independently verified employer, configure the existing reviewed registry using [TinyFish registry instructions](tinyfish_integration.md), then rescan. Inspect domain comparisons on an employer page versus a recognized recruitment platform. The latter must not become suspicious solely because of a mismatch.
6. Use controlled local job fixtures and the automated tests to demonstrate lookalikes and suspicious recruiter addresses. Do not navigate to hostile domains or promote fictional fixtures to production trust entries. Check long text/addresses scroll and wrap, and evidence links still open safely.

## Files added or changed

- New `backend/app/security/`: `__init__.py`, `schemas.py`, `domains.py`, `emails.py`, `advisory.py`, `assessment.py`.
- Updated backend API integration: `backend/app/main.py`, `backend/app/schemas.py`, `backend/app/investigation/schemas.py`.
- Added the three backend test modules above; updated `extension/tests/popup.test.cjs`.
- Updated `extension/popup.html`, `extension/popup.css`, and `extension/popup.js`.
- Added explicit `idna` requirement (already present at the same version in the dependency lock).
- Updated `README.md` and `docs/architecture.md`; added this report, `docs/domain_impersonation.md`, and `docs/recruitment_email_verification.md`.

Existing Git history, environment credentials, model/training files, manifest permissions, dataset, licensing files, and original investigation retrieval were preserved. No commit or push was made. Because this checkout has no initial commit, Git currently lists project files as untracked; this list describes this task's implementation rather than a committed diff.

## Remaining limits

Authority depends on a carefully reviewed registry. Domain similarity cannot establish fraud, website control, recruiter authorization, or factual offer authenticity. Known-platform/provider/confusable lists are partial. Private-interface and recruitment-context detection are conservative heuristics. There is no email authentication or delivery check. The popup must remain open during investigation; existing TinyFish network/credit limitations still apply.
