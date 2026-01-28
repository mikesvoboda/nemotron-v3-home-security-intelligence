# CI/CD Pipeline Documentation

This document describes the GitHub Actions CI/CD pipeline for Home Security Intelligence.

---

## Overview

The CI/CD pipeline consists of multiple workflows that run on different triggers:

| Workflow               | Trigger         | Purpose                           |
| ---------------------- | --------------- | --------------------------------- |
| **CI**                 | Push/PR to main | Run tests, linting, type checking |
| **Deploy**             | Push to main    | Build and push container images   |
| **Release**            | Tag push (v\*)  | Create GitHub releases            |
| **SAST**               | Push/PR to main | Security static analysis          |
| **Test Coverage Gate** | PR to main      | Enforce coverage requirements     |

---

## Main CI Workflow

**File:** `.github/workflows/ci.yml`

The main CI workflow is the most comprehensive, running on every push to main and all pull requests.

### Workflow Triggers

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch: # Manual trigger
```

### Environment Configuration

```yaml
env:
  PYTHON_VERSION: '3.14'
  NODE_VERSION: '20'
  UV_VERSION: '0.9.18'
```

### Change Detection

The workflow uses intelligent change detection to only run relevant tests:

| Change Type           | Backend Tests | Frontend Tests |
| --------------------- | ------------- | -------------- |
| Backend files only    | Yes           | No             |
| Frontend files only   | No            | Yes            |
| Both changed          | Yes           | Yes            |
| Docs only             | No            | No             |
| Workflow file changes | Yes           | Yes            |
| Push to main          | Yes           | Yes            |

Detected file patterns:

- **Backend:** `backend/**`, `pyproject.toml`, `uv.lock`, `ai/**`, `scripts/**/*.py`
- **Frontend:** `frontend/**` (excluding `.md` files)
- **Docs only:** `docs/**`, `**/*.md`

### Backend Jobs

#### 1. Build Backend Dependencies

- **Purpose:** Shared dependency installation for all backend jobs
- **Caching:** Uses `uv` with cache suffix for optimization

#### 2. Backend Lint (Ruff)

- **Purpose:** Code style and formatting checks
- **Tools:**
  - `ruff check` - Linting
  - `ruff format --check` - Format verification
  - `radon cc/mi` - Complexity analysis

#### 3. Backend Type Check (Mypy)

- **Purpose:** Static type checking
- **Command:** `uv run mypy backend/ --ignore-missing-imports`

#### 4. Backend Unit Tests (4 Shards)

- **Purpose:** Fast, isolated unit tests
- **Parallelization:** 4 shards with pytest-split, xdist parallelization within shards
- **Coverage:** Collected per-shard, merged in coverage job
- **Services:** PostgreSQL 16
- **Threshold:** 85% (checked after merging)

#### 5. Integration Tests (4 Parallel Jobs)

| Job           | Tests Covered                                   |
| ------------- | ----------------------------------------------- |
| **API**       | Route handlers, HTTP endpoints, error scenarios |
| **WebSocket** | Real-time communication, pub/sub, broadcasting  |
| **Services**  | Business logic, batch processing, AI pipeline   |
| **Models**    | Database models, cascades, relationships        |

Each integration test job:

- Uses PostgreSQL and Redis services
- Runs with retry logic (3 attempts)
- Collects coverage separately
- Has 20-minute timeout

#### 6. Contract Tests (Main Branch Only)

- **Purpose:** Validate API schema consistency
- **Trigger:** Only on main branch pushes
- **Action on Failure:** Creates Linear issue automatically

#### 7. Dead Code Detection (Main Branch Only)

- **Purpose:** Identify unused code
- **Tool:** Vulture
- **Action on Failure:** Creates Linear issue automatically

### Frontend Jobs

#### 1. API Types Contract Check

- **Purpose:** Ensure frontend types match backend API
- **Validates:**
  - OpenAPI spec is current
  - WebSocket types are current
  - Generated types match API

#### 2. Frontend Lint (ESLint)

- **Purpose:** Code style and quality
- **Additional:** Knip dead code detection (non-blocking)

#### 3. Frontend Type Check (TypeScript)

- **Purpose:** Static type checking
- **Command:** `npm run typecheck`

#### 4. Frontend Tests (Vitest - 16 Shards)

- **Purpose:** Component and hook unit tests
- **Parallelization:** 16 shards for memory management
- **Memory:** 6GB heap per shard
- **Special Handling:** Early process termination to prevent OOM during cleanup

#### 5. E2E Tests (Playwright - 6 Shards)

- **Purpose:** End-to-end browser testing
- **Browser:** Chromium (primary, required for merge)
- **Parallelization:** 6 shards
- **Retry:** 3 attempts per shard

### Branch Protection

Summary jobs aggregate shard results for branch protection rules:

| Summary Job                 | Aggregates              |
| --------------------------- | ----------------------- |
| `Backend Unit Tests`        | 4 unit test shards      |
| `Backend Integration Tests` | 4 integration test jobs |
| `Frontend Tests (Vitest)`   | 16 Vitest shards        |
| `E2E Tests (Chromium)`      | 6 Playwright shards     |

---

## Deploy Workflow

**File:** `.github/workflows/deploy.yml`

Triggered on push to main branch. Builds and publishes container images.

### Build Stage

Builds images for multiple architectures:

| Image     | Dockerfile               | Target |
| --------- | ------------------------ | ------ |
| backend   | `./backend/Dockerfile`   | prod   |
| frontend  | `./frontend/Dockerfile`  | prod   |
| ai-yolo26 | `./ai/yolo26/Dockerfile` | -      |

**Platforms:**

- `linux/amd64` (ubuntu-latest runner)
- `linux/arm64` (ubuntu-24.04-arm runner)

### Multi-Arch Manifest Merge

After architecture-specific builds complete, creates multi-arch manifests for:

- `ghcr.io/{repo}/backend:latest`
- `ghcr.io/{repo}/frontend:latest`

### Smoke Tests

Validates deployed images:

1. Pulls latest images from GHCR
2. Starts services with `docker-compose.ci.yml`
3. Waits for health checks (backend: 120s, frontend: 60s)
4. Runs smoke test script
5. Validates health endpoints

### Supply Chain Security

#### SBOM Generation

- **Tool:** Anchore SBOM Action
- **Format:** SPDX JSON
- **Retention:** 90 days

#### Image Signing

- **Tool:** Sigstore Cosign
- **Method:** OIDC keyless signing
- **Signs:** Both `latest` and `sha` tags

#### SLSA Provenance

- **Level:** SLSA Level 3
- **Tool:** GitHub attestation API
- **Purpose:** Cryptographic build provenance

### Deployment Stages

```
build -> merge -> smoke-test -> sbom-and-sign -> staging-deployment
                      |
                      v
            post-deployment-validation
                      |
                      v
              slsa-provenance
```

---

## Release Workflow

**File:** `.github/workflows/release.yml`

Triggered on tag pushes matching `v*` pattern.

### Changelog Generation

Automatically categorizes commits:

| Prefix         | Category      |
| -------------- | ------------- |
| `feat:`        | Features      |
| `fix:`         | Bug Fixes     |
| `security:`    | Security      |
| `docs:`        | Documentation |
| `chore(deps):` | Dependencies  |
| `perf:`        | Performance   |
| `refactor:`    | Refactoring   |
| `test:`        | Tests         |
| `ci:`          | CI/CD         |
| `chore:`       | Other Changes |

### Linear Integration

Extracts and links Linear issue references (NEM-XXX pattern) in release notes.

### Pre-release Detection

Automatically marks as pre-release if tag contains:

- `-alpha`
- `-beta`
- `-rc`

---

## SAST Workflow

**File:** `.github/workflows/sast.yml`

Static Application Security Testing.

### Bandit (Python Security)

```bash
bandit -r backend/ \
  -c .bandit.yml \
  -b .bandit.baseline \
  -x "backend/tests/*" \
  --severity-level medium
```

- Fails on HIGH/CRITICAL issues
- Uses baseline file for known false positives

### Semgrep

Scans with rulesets:

- `p/python`
- `p/typescript`
- `p/react`
- `p/owasp-top-ten`
- Custom `semgrep.yml`

---

## Test Coverage Gate

**File:** `.github/workflows/test-coverage-gate.yml`

Enforces test coverage requirements on PRs.

### Coverage Requirements

| Layer               | Requirement        | Threshold |
| ------------------- | ------------------ | --------- |
| API Routes          | Unit + Integration | 95%       |
| Services            | Unit + Integration | 90%       |
| Models              | Unit tests         | 85%       |
| Frontend Components | Unit tests         | 80%       |

### Checks

1. **Test Coverage Gate:** Verifies new files have corresponding tests
2. **Integration Test Check:** Ensures API/service changes have integration tests
3. **API Test Generation:** Validates OpenAPI spec for test generation

---

## Other Workflows

### Security Scanning

| Workflow               | Tool          | Purpose                          |
| ---------------------- | ------------- | -------------------------------- |
| `codeql.yml`           | CodeQL        | Advanced security analysis       |
| `gitleaks.yml`         | Gitleaks      | Secret detection                 |
| `trivy.yml`            | Trivy         | Container vulnerability scanning |
| `zap-security.yml`     | OWASP ZAP     | Dynamic security testing         |
| `dependency-audit.yml` | npm/pip audit | Dependency vulnerabilities       |

### Quality & Testing

| Workflow                   | Purpose                   |
| -------------------------- | ------------------------- |
| `benchmarks.yml`           | Performance benchmarking  |
| `load-tests.yml`           | Load testing              |
| `flaky-test-detection.yml` | Identify unreliable tests |
| `mutation-testing.yml`     | Test quality analysis     |
| `visual-tests.yml`         | Visual regression testing |
| `accessibility-tests.yml`  | A11y compliance           |

### Documentation & Maintenance

| Workflow                | Purpose                       |
| ----------------------- | ----------------------------- |
| `docs.yml`              | Documentation building        |
| `docs-drift.yml`        | Detect outdated documentation |
| `agents-md.yml`         | Validate AGENTS.md files      |
| `api-compatibility.yml` | API backward compatibility    |
| `api-contract.yml`      | API schema validation         |

### Integrations

| Workflow                 | Purpose                       |
| ------------------------ | ----------------------------- |
| `linear-ci-status.yml`   | Sync CI status to Linear      |
| `linear-github-sync.yml` | Sync issues GitHub <-> Linear |
| `pr-review-bot.yml`      | Automated PR reviews          |
| `ai-code-review.yml`     | AI-assisted code review       |

### Scheduled

| Workflow                 | Schedule | Purpose             |
| ------------------------ | -------- | ------------------- |
| `nightly.yml`            | Daily    | Extended test suite |
| `weekly-audit.yml`       | Weekly   | Security audit      |
| `weekly-test-report.yml` | Weekly   | Test metrics report |

---

## Running Locally

### Simulate CI Checks

```bash
# Full validation (recommended before PRs)
./scripts/validate.sh

# Backend checks
uv run ruff check backend/
uv run ruff format --check backend/
uv run mypy backend/
uv run pytest backend/tests/unit/ -n auto

# Frontend checks
cd frontend
npm run lint
npm run typecheck
npm test
```

### Simulate Deploy Build

```bash
# Build images locally
podman-compose -f docker-compose.prod.yml build --no-cache backend
podman-compose -f docker-compose.prod.yml build --no-cache frontend

# Run smoke tests
./scripts/ci-smoke-test.sh \
  --backend-url http://localhost:8000 \
  --frontend-url http://localhost:3000
```

---

## Troubleshooting

### Common CI Failures

| Failure                  | Cause                  | Solution                                |
| ------------------------ | ---------------------- | --------------------------------------- |
| Unit test shard failed   | Test isolation issue   | Check for shared state between tests    |
| Integration test timeout | Database deadlock      | Tests may need `-n0` (serial execution) |
| Frontend OOM             | Memory leak in cleanup | Check for unclosed resources            |
| E2E flaky                | Timing issues          | Add explicit waits, check selectors     |
| Type check failed        | Schema changed         | Run `./scripts/generate-types.sh`       |

### Viewing Artifacts

Test results and coverage reports are uploaded as artifacts:

1. Go to Actions tab
2. Select workflow run
3. Scroll to "Artifacts" section
4. Download relevant artifacts

### Re-running Failed Jobs

1. Go to the failed workflow run
2. Click "Re-run jobs" dropdown
3. Select "Re-run failed jobs" to save time

---

## Related Documentation

- [Testing Guide](testing.md) - Test infrastructure and patterns
- [Testing Workflow](testing-workflow.md) - TDD practices
- [Git Workflow](git-workflow.md) - Branch and commit conventions
- [Code Quality](code-quality.md) - Linting and formatting tools
