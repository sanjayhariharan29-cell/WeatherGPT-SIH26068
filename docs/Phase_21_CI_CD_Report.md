# Phase 21 — CI/CD Pipeline Implementation Report

**Developer:** Person 2
**Date:** 2026-09-09
**Branch:** `main`
**Status:** ✅ COMPLETE

---

## Overview

Phase 21 establishes and maintains an automated, safe, and reproducible Continuous Integration (CI) pipeline for the WeatherGPT SIH26068 project using GitHub Actions.

The CI pipeline automatically validates backend logic, AI integration contracts, frontend asset builds, and repository security health on every push and pull request to `main`. It is the foundational quality gate that protects the shared `main` branch for all three developers (Person 1 — AI, Person 2 — Backend/Frontend, Person 3 — Mobile/Release).

---

## Workflow File & Structure

- **File**: [`.github/workflows/ci.yml`](file:///c:/WeatherGPT-SIH26068/.github/workflows/ci.yml)
- **Workflow Name**: `WeatherGPT CI`

### Trigger Conditions

| Trigger | Branch | Description |
|---------|--------|-------------|
| `push` | `main` | Every commit merged or pushed to `main` |
| `pull_request` | `main` | Every PR opened or updated targeting `main` |

---

## Execution Stages & Jobs

The workflow runs three parallel jobs. Each job is independent, providing fast feedback and clear failure isolation.

---

### Job 1: `backend-and-ai` — Backend & AI Test Suite

| Property | Value |
|----------|-------|
| **Runner** | `ubuntu-latest` |
| **Python** | `3.11` (via `actions/setup-python@v5`, pip cache enabled) |
| **Dependencies** | `pip install -r requirements.txt` |
| **Test Command** | `python -m pytest -v --tb=short --timeout=60 -x -q` |
| **Database** | `sqlite:///./test_ci.db` (file-backed, isolated per CI run) |

**Steps:**
1. `actions/checkout@v4` — checkout repository.
2. `actions/setup-python@v5` — Python 3.11, pip cache.
3. Install `requirements.txt` — FastAPI, Pydantic, SQLAlchemy, HTTPX, Pytest, pytest-timeout, bcrypt, PyJWT, email-validator.
4. Run full pytest suite with 60-second per-test timeout to catch hanging network calls.
5. Cleanup — remove `test_ci.db` artifact after run (always runs, even on failure).

**Test Coverage (as of Phase 21 completion):** 657 tests across 45 modules — 657 passed, 0 failed.

**Database Safety:** All tests run against an ephemeral file-backed SQLite database (`test_ci.db`), completely isolated from any production or development database. The CI environment never touches the project's `weathergpt.db` production file.

**Timeout Safety:** `--timeout=60` (via `pytest-timeout`) prevents individual tests from hanging indefinitely on mock API calls with CI placeholder keys, protecting CI feedback loop time.

---

### Job 2: `frontend-and-assets` — Frontend Assets & Build

| Property | Value |
|----------|-------|
| **Runner** | `ubuntu-latest` |
| **Node.js** | `20` (via `actions/setup-node@v4`, npm cache enabled) |
| **Package Manager** | npm (`npm ci || npm install`) |

**Steps:**
1. `actions/checkout@v4`.
2. `actions/setup-node@v4` — Node.js 20 with npm cache.
3. `npm ci || npm install` — installs `@capacitor/cli`, `@capacitor/core`, `@capacitor/android`.
4. `npm run lint` — frontend asset lint check.
5. `npm run build:web` — verifies static web bundle readiness.
6. `npm test` — frontend asset verification suite.
7. Static asset integrity check — verifies presence of all 5 required files:

| Asset | Path |
|-------|------|
| Main HTML | `frontend/index.html` |
| App Logic | `frontend/app.js` |
| Styles | `frontend/styles.css` |
| PWA Manifest | `frontend/manifest.json` |
| Service Worker | `frontend/sw.js` |

---

### Job 3: `repository-health` — Repository & Docker Health

**Steps:**

| Step | What It Checks |
|------|---------------|
| `.env.example` validation | File exists and contains only template placeholders |
| `.env` secret audit | Confirms no `.env` credential file is tracked in git |
| `Dockerfile` security check | `HEALTHCHECK` directive + `USER appuser` non-root enforcement |
| `.env.example` credential pattern scan | Python regex scan for real `AIzaSy...` Gemini or `sk-proj-...` OpenAI key patterns |

---

## Environment Assumptions & Secret Handling

### CI Placeholder Keys

| Variable | CI Value | Purpose |
|----------|----------|---------|
| `ENVIRONMENT` | `testing` | Enables test mode in settings |
| `DATABASE_URL` | `sqlite:///./test_ci.db` | Ephemeral isolated test DB |
| `SECRET_KEY` | `ci-testing-secret-key-12345-do-not-use-in-prod` | JWT signing for auth tests |
| `IMD_API_KEY` | `ci-mock-imd-api-key` | Triggers mock adapter logic |
| `OPENAI_API_KEY` | `ci-mock-openai-api-key` | Satisfies validation schemas, no real call |
| `GEMINI_API_KEY` | `ci-mock-gemini-api-key` | Falls back to `MockLLMProvider` |

### Production Secrets (Never in CI config)

Real production keys (`IMD_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `SECRET_KEY`, `DATABASE_URL`) are stored only in GitHub Repository Secrets and injected at deployment time via environment variables. They are never committed to the repository or workflow files.

---

## Requirements — Python Dependencies for CI

**File:** [`requirements.txt`](file:///c:/WeatherGPT-SIH26068/requirements.txt)

```
fastapi>=0.110.0
uvicorn>=0.28.0
sqlalchemy>=2.0.0
pydantic>=2.6.0
email-validator>=2.1.0
PyJWT>=2.8.0
bcrypt>=4.0.0
httpx>=0.27.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-timeout>=2.3.0
python-multipart>=0.0.9
```

`pytest-timeout>=2.3.0` was added during Phase 21 to prevent hanging tests (e.g., tests that make real HTTP calls using CI mock keys which have no upstream server to respond to).

---

## Command Reference — Replicating CI Locally

```bash
# 1. Backend & AI full test suite (replicates CI Job 1)
pip install -r requirements.txt
ENVIRONMENT=testing DATABASE_URL="sqlite:///./test_ci.db" python -m pytest -v --tb=short

# 2. Frontend validation (replicates CI Job 2)
npm install
npm run lint
npm run build:web
npm test

# 3. Static asset integrity check (replicates CI Job 2 step 7)
ls frontend/index.html frontend/app.js frontend/styles.css frontend/manifest.json frontend/sw.js

# 4. CI-specific pipeline audit tests
python -m pytest tests/test_ci_pipeline.py -v

# 5. Repository health checks
test -f .env.example
test ! -f .env
grep -q "HEALTHCHECK" Dockerfile
grep -q "USER appuser" Dockerfile
```

---

## CI Audit Test Suite

**File:** [`tests/test_ci_pipeline.py`](file:///c:/WeatherGPT-SIH26068/tests/test_ci_pipeline.py)

8 automated tests that the CI pipeline itself is correctly configured:

| Test | Description |
|------|-------------|
| `test_01_ci_workflow_file_exists` | `.github/workflows/ci.yml` exists and is non-trivially sized |
| `test_02_ci_workflow_yaml_syntax` | Valid YAML with required jobs (`backend-and-ai`, `frontend-and-assets`, `repository-health`) |
| `test_03_ci_triggers` | Confirms `push:` + `pull_request:` + `main` branch targeting |
| `test_04_ci_secret_isolation_and_no_hardcoded_credentials` | Mock keys in CI config; no real key patterns present |
| `test_05_ci_frontend_package_json_scripts` | `package.json` contains `build:web`, `lint`, `test` scripts |
| `test_06_env_example_safety_audit` | `.env.example` has no real credentials in secret key fields |
| `test_07_frontend_local_command_execution` | `npm run lint`, `npm run build:web`, `npm test` all exit 0 |
| `test_08_no_committed_env_file` | `.env` is not committed to git |

---

## CI Fix History

The following commits resolved issues discovered when the initial CI ran on GitHub Actions:

| Commit | Fix |
|--------|-----|
| `0544299` | Added `email-validator` and `PyJWT` to `requirements.txt`; fixed `Any` import in `prompts.py` |
| `36f9b73` | Added `bcrypt` to `requirements.txt`; fixed `Any` import in `generator.py` |
| `1a8ca1d` | Switched from `sqlite:///:memory:` to file-backed `sqlite:///./test_ci.db` for shared SQLAlchemy connection safety |
| `b02dffc` | Converted `subprocess.run()` list-form to string-form with `shell=True` for Linux CI cross-platform compatibility |
| `044fc87` | Patched `GeminiLLMProvider` in `test_11` to prevent real Gemini API timeout (504) with CI mock keys |

---

## Local Test Results (Phase 21 Final Verification)

### Python (pytest)

```
657 passed, 14 warnings in 48.94s
```

**Total modules:** 45 test files across Backend, AI, Mobile, Integration, and CI pipeline audit categories.

### Frontend (npm)

```
npm run lint      → Frontend asset linting passed cleanly.      [EXIT 0]
npm run build:web → Production web assets ready in frontend/   [EXIT 0]
npm test          → Frontend asset verification passed cleanly. [EXIT 0]
```

### Static Assets

```
frontend/index.html   ✅
frontend/app.js       ✅
frontend/styles.css   ✅
frontend/manifest.json ✅
frontend/sw.js        ✅
```

### Repository Health

```
.env.example exists:  ✅
.env not committed:   ✅
Dockerfile HEALTHCHECK: ✅
Dockerfile USER appuser: ✅
```

---

## Limitations & Scope Boundaries

| Limitation | Reason |
|------------|--------|
| **Android APK Gradle build** not in CI | `gradlew assembleRelease` is heavy and requires Android SDK; handled separately in release workflow by Person 3 |
| **Real IMD / Gemini API calls** not in CI | CI uses mock keys and mock providers to guarantee deterministic, fast, network-independent tests |
| **Production database** not tested in CI | CI exclusively uses SQLite test isolation; PostgreSQL migration testing is a deployment-time check |
| **Docker image build** not in CI | Full Docker build tested manually (Phase 20); Docker CI can be added in a later phase if needed |

---

## Files Changed in Phase 21

| File | Status | Description |
|------|--------|-------------|
| [`.github/workflows/ci.yml`](file:///c:/WeatherGPT-SIH26068/.github/workflows/ci.yml) | Created/Improved | 3-job GitHub Actions workflow |
| [`requirements.txt`](file:///c:/WeatherGPT-SIH26068/requirements.txt) | Modified | Added `email-validator`, `PyJWT`, `bcrypt`, `pytest-timeout` |
| [`package.json`](file:///c:/WeatherGPT-SIH26068/package.json) | Modified | Added `lint`, `build:web`, `test` npm scripts |
| [`tests/test_ci_pipeline.py`](file:///c:/WeatherGPT-SIH26068/tests/test_ci_pipeline.py) | Created | 8-test CI audit suite |
| [`tests/test_performance_reliability.py`](file:///c:/WeatherGPT-SIH26068/tests/test_performance_reliability.py) | Modified | Patched test_11 to prevent GeminiLLMProvider timeout in CI |
| [`docs/Phase_21_CI_CD_Report.md`](file:///c:/WeatherGPT-SIH26068/docs/Phase_21_CI_CD_Report.md) | This document | CI/CD documentation |
