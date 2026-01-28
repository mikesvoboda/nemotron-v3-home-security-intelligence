# GitHub Workflows Directory - Agent Guide

## Purpose

This directory contains GitHub Actions workflow definitions for the Home Security Intelligence project. Workflows automate CI/CD, testing, security scanning, and code quality checks.

## Directory Contents

```
workflows/
  AGENTS.md                   # This file
  # Core CI/CD
  ci.yml                      # Main CI pipeline
  deploy.yml                  # Docker image build and push to GHCR
  preview-deploy.yml          # PR preview container builds
  release.yml                 # Release workflow
  rollback.yml                # Deployment rollback
  semantic-release.yml        # Semantic versioning releases
  release-drafter.yml         # Draft release notes
  # API
  api-compatibility.yml       # API backward compatibility checks
  api-contract.yml            # API contract testing
  # Testing
  gpu-tests.yml               # GPU integration tests
  load-tests.yml              # Load and performance testing
  mutation-testing.yml        # Mutation testing for test quality
  benchmarks.yml              # Performance benchmarks
  test-coverage-gate.yml      # PR gate for test coverage requirements
  pr-review-bot.yml           # PR review bot for missing tests
  weekly-test-report.yml      # Weekly test coverage and quality report
  # Security
  sast.yml                    # Static Application Security Testing
  codeql.yml                  # CodeQL security analysis
  gitleaks.yml                # Secret detection scanning
  trivy.yml                   # Container vulnerability scanning
  zap-security.yml            # OWASP ZAP security scanning
  dependency-audit.yml        # Dependency vulnerability audit
  vulnerability-management.yml # CVE tracking and management
  weekly-audit.yml            # Weekly security and code quality audits
  # Quality & Analysis
  ai-code-review.yml          # GPT-powered code review
  bundle-size.yml             # Frontend bundle size tracking
  ci-analytics.yml            # CI metrics and analytics
  docs.yml                    # Documentation generation
  docs-drift.yml              # Documentation drift detection
  nightly.yml                 # Nightly benchmarks and analysis
  # Frontend Quality
  accessibility-tests.yml     # Accessibility (a11y) testing
  lighthouse.yml              # Lighthouse performance audits
  visual-tests.yml            # Visual regression testing
  # Integrations
  linear-ci-status.yml        # Linear issue status sync from CI/CD events
  linear-github-sync.yml      # Linear to GitHub issue sync
```

## Workflow Files

### ci.yml - Main CI Pipeline

**Trigger:** Push/PR to main branch

**Purpose:** Primary continuous integration - linting, type checking, testing, building.

**Jobs:**

| Job                | Duration | Description                         |
| ------------------ | -------- | ----------------------------------- |
| lint               | ~1m      | Ruff check and format verification  |
| typecheck          | ~2m      | Mypy static type analysis           |
| unit-tests         | ~3m      | pytest unit tests with coverage     |
| integration-tests  | ~4m      | pytest with Redis service container |
| api-types-check    | ~2m      | API types contract verification     |
| frontend-lint      | ~1m      | ESLint checking                     |
| frontend-typecheck | ~1m      | TypeScript compilation check        |
| frontend-tests     | ~2m      | Vitest with coverage                |
| frontend-e2e       | ~5m      | Playwright E2E tests                |
| build              | ~5m      | Docker image builds (after tests)   |
| build-prod         | ~5m      | Production Docker image builds      |

**Environment:**

- Python 3.11
- Node.js 20
- PostgreSQL 16 (service container)
- Redis 7 (service container for integration tests)
- Coverage uploaded to Codecov

**Concurrency:** Only one run per branch at a time.

### docs.yml - Documentation Generation

**Trigger:** Push/PR to main, manual dispatch

**Purpose:** Generate and deploy API and TypeScript documentation.

**Jobs:**

| Job             | Duration | Description                        |
| --------------- | -------- | ---------------------------------- |
| openapi         | ~1m      | Extract OpenAPI spec from FastAPI  |
| typedoc         | ~2m      | Generate TypeScript documentation  |
| redoc           | ~1m      | Generate Redoc HTML from OpenAPI   |
| build-docs      | ~1m      | Assemble documentation site        |
| deploy          | ~1m      | Deploy to GitHub Pages (main only) |
| archive-openapi | ~1m      | Version and archive OpenAPI spec   |

**Outputs:**

- OpenAPI specification (`openapi.json`)
- Redoc HTML API documentation
- TypeDoc markdown documentation
- Documentation site deployed to GitHub Pages

**Artifacts:**

- `openapi-spec` - Raw OpenAPI JSON
- `typedoc-output` - TypeDoc markdown files
- `redoc-html` - Redoc HTML documentation
- `docs-site` - Complete documentation site
- `openapi-versioned-{sha}` - Versioned OpenAPI archive

**Local Generation:**

```bash
# Generate all documentation
./scripts/generate-docs.sh

# Generate and serve locally
./scripts/generate-docs.sh --serve

# Generate API docs only
./scripts/generate-docs.sh --api-only

# Generate TypeScript docs only
./scripts/generate-docs.sh --ts-only
```

**Frontend TypeDoc:**

```bash
cd frontend
npm run docs        # Generate TypeDoc
npm run docs:watch  # Watch mode
```

**Configuration Files:**

- `frontend/typedoc.json` - TypeDoc configuration

### docs-drift.yml - Documentation Drift Detection

**Trigger:** Push/PR to main branch

**Purpose:** Automatically detect when code changes may require documentation updates.

**Jobs:**

| Job          | Duration | Description                                    |
| ------------ | -------- | ---------------------------------------------- |
| detect-drift | ~2m      | Analyze changes and detect documentation drift |

**Features:**

- Compares base and head commits to identify changed files
- Runs `scripts/check-docs-drift.py` to analyze if docs need updating
- Creates Linear tasks for detected drift items (if `LINEAR_API_KEY` is set)
- Posts summary comment on PRs with drift details
- Uploads drift report as artifact (30-day retention)

**Drift Detection Categories:**

- High priority: API changes, schema changes, configuration changes
- Medium priority: Service logic changes, component changes
- Low priority: Minor refactoring, test changes

**Outputs:**

- PR comment with drift summary table (priorities, descriptions)
- Linear tasks created for documentation work
- `drift-report.json` artifact

**Related Scripts:**

- `scripts/check-docs-drift.py` - Drift detection logic
- `scripts/create-docs-tasks.py` - Linear task creation

### deploy.yml - Container Deployment

**Trigger:** Push to main branch only

**Purpose:** Build and push Docker images to GitHub Container Registry.

**Process:**

1. Authenticate to GHCR
2. Build images with Buildx (multi-arch: amd64, arm64)
3. Scan with Trivy (fail on CRITICAL/HIGH)
4. Push with tags: `sha-{commit}`, `latest`

**Matrix Build:**

- Backend: `./backend/Dockerfile` (target: `prod`)
- Frontend: `./frontend/Dockerfile` (target: `prod`)

**Permissions:**

- `contents: read`
- `packages: write`

### preview-deploy.yml - PR Preview Containers

**Trigger:** Pull request events (opened, synchronize, reopened, closed)

**Purpose:** Build preview containers for PRs to enable local testing before merge.

**Jobs:**

| Job             | Condition         | Description                            |
| --------------- | ----------------- | -------------------------------------- |
| build-preview   | PR opened/updated | Build and push containers with PR tags |
| comment-preview | After build       | Post docker-compose instructions to PR |
| cleanup-preview | PR closed         | Delete preview images from GHCR        |

**Image Tags:**

- `ghcr.io/{owner}/{repo}/backend:pr-{number}`
- `ghcr.io/{owner}/{repo}/frontend:pr-{number}`

**Workflow:**

1. Open PR against main
2. Workflow builds backend and frontend containers with PR-specific tags
3. Comment posted with docker-compose.preview.yml snippet
4. Testers pull images and run locally
5. On PR close, cleanup job marks images for deletion

**Permissions:**

- `contents: read`
- `packages: write`
- `pull-requests: write`

**Features:**

- Builds in parallel (backend and frontend)
- Uses GHA cache for faster rebuilds
- Comments update on subsequent pushes (not duplicated)
- Graceful cleanup (non-blocking if deletion fails)

**Local Testing:**

```bash
# Pull preview images
docker pull ghcr.io/{owner}/{repo}/backend:pr-123
docker pull ghcr.io/{owner}/{repo}/frontend:pr-123

# Run with docker-compose (see PR comment for snippet)
docker compose -f docker-compose.preview.yml up -d
```

### ai-code-review.yml - AI-Powered Review

**Trigger:** PR opened/synchronized (excludes drafts and dependabot)

**Purpose:** Automated code review using GPT-4o via GitHub Models.

**Process:**

1. Extract PR diff (limited to 20KB for token limits)
2. Install `gh-models` extension
3. Run diff through GPT-4o (falls back to gpt-4o-mini)
4. Post review as PR comment

**Review Focus:**

- Security vulnerabilities
- Performance issues
- Best practices
- Potential bugs

### linear-ci-status.yml - Linear CI Status Sync

**Trigger:** CI workflow completion, push to main, manual dispatch

**Purpose:** Automatically update Linear issue status based on CI/CD events.

**Jobs:**

| Job            | Trigger                   | Action                     |
| -------------- | ------------------------- | -------------------------- |
| ci-completion  | CI workflow_run completed | Move issue to "In Review"  |
| pr-merged      | Push to main              | Move issue to "Done"       |
| manual-trigger | workflow_dispatch         | Check/move issues manually |

**Features:**

- Extracts Linear issue IDs from PR title and branch name (e.g., `NEM-123`, `nem-123`)
- On CI success: Moves issues from "Todo" or "In Progress" to "In Review"
- On CI failure: Adds a comment to the issue with workflow link
- On PR merge: Moves issues to "Done"
- Handles multiple issues in a single PR
- Skips gracefully when no issue ID found
- Non-blocking (informational) - doesn't fail CI if Linear update fails

**Issue ID Patterns Recognized:**

- `NEM-123` - Standard format
- `nem-123` - Lowercase
- `NEM_123` - Underscore separator
- Multiple IDs in same PR title/branch

**Manual Actions:**

- `check` - Display current status of linked issues
- `move-to-review` - Move issues to "In Review"
- `move-to-done` - Move issues to "Done"

### linear-github-sync.yml - Linear-GitHub Issue Sync

**Trigger:** Daily schedule (6am UTC), manual dispatch, Linear webhook

**Purpose:** Sync Linear task completions to GitHub issues.

**Modes:**

- `audit` - Report matching issues without closing
- `close` - Close matched GitHub issues

**Process:**

1. Query Linear for completed issues
2. Match to GitHub issues by title similarity
3. Close matched GitHub issues (in close mode)

### nightly.yml - Nightly Analysis

**Trigger:** 2am EST daily (cron: `0 7 * * *`) + manual dispatch

**Purpose:** Extended analysis that takes too long for CI.

**Jobs:**

| Job                 | Runner          | Purpose                       |
| ------------------- | --------------- | ----------------------------- |
| extended-benchmarks | self-hosted GPU | Big-O tests, memory profiling |
| complexity-trends   | ubuntu-latest   | Wily code complexity reports  |
| security-audit      | ubuntu-latest   | pip-audit, npm audit, Bandit  |

**Artifacts Generated:**

- `memory-profile` - Memray profiling data
- `wily-report` - HTML complexity report
- `security-audit` - Bandit JSON report

### gpu-tests.yml - GPU Integration Tests

**Trigger:** Push/PR to main branch

**Purpose:** Run tests requiring GPU hardware.

**Requirements:**

- Self-hosted runner with labels: `gpu`, `rtx-a5500`
- Fork protection (only runs for trusted sources)
- 30-minute timeout

**Tests:**

- pytest tests marked with `@pytest.mark.gpu`
- AI inference benchmarks

**Output:** GPU benchmark results as artifact.

### sast.yml - Static Analysis Security Testing

**Trigger:** Push/PR to main branch

**Purpose:** Security-focused static analysis.

**Tools:**

| Tool    | Language        | Focus                    |
| ------- | --------------- | ------------------------ |
| Bandit  | Python          | Security vulnerabilities |
| Semgrep | Python/TS/React | OWASP Top 10, patterns   |

**Semgrep Rulesets:**

- `p/python` - Python security rules
- `p/typescript` - TypeScript rules
- `p/react` - React-specific rules
- `p/owasp-top-ten` - OWASP vulnerabilities

### codeql.yml - CodeQL Analysis

**Trigger:** Push/PR to main, Weekly (Monday 6am UTC)

**Purpose:** Deep semantic code analysis for security vulnerabilities.

**Languages:** Python, JavaScript/TypeScript

**Configuration:** Uses `.github/codeql/codeql-config.yml`

**Permissions:**

- `security-events: write` - Required for uploading results

### gitleaks.yml - Secret Detection

**Trigger:** Push/PR to main branch

**Purpose:** Scan for accidentally committed secrets.

**Configuration:** `.gitleaks.toml` in project root

**Detects:**

- API keys
- Passwords
- Private keys
- AWS credentials

### trivy.yml - Container Scanning

**Trigger:** Push/PR to main when Dockerfiles or dependencies change

**Purpose:** Scan Docker images for vulnerabilities.

**Path Filters:**

- `**/Dockerfile*`
- `pyproject.toml` (Python dependencies)
- `frontend/package.json`

**Severity Filter:** CRITICAL, HIGH (fails build)

**Output:** SARIF format uploaded to GitHub Security tab

### weekly-audit.yml - Weekly Audit

**Trigger:** Monday 9 AM UTC (cron: `0 9 * * 1`) + manual dispatch

**Purpose:** Weekly comprehensive security and code quality audit.

**Jobs:**

| Job              | Runner        | Purpose                          |
| ---------------- | ------------- | -------------------------------- |
| security-audit   | ubuntu-latest | Semgrep security scan, pip-audit |
| code-quality     | ubuntu-latest | Vulture, Radon complexity        |
| frontend-quality | ubuntu-latest | Knip dead code detection         |
| audit-summary    | ubuntu-latest | Generate summary report          |

**Tools Used:**

- Semgrep (security patterns)
- pip-audit (Python dependency vulnerabilities)
- Vulture (Python dead code)
- Radon (cyclomatic complexity)
- Knip (TypeScript/JS dead code)

### test-coverage-gate.yml - Test Coverage Enforcement (NEM-2102)

**Trigger:** Pull request to main branch (opened, synchronized, reopened)

**Purpose:** Enforce test coverage requirements on new/modified code to prevent untested features from merging.

**Jobs:**

| Job                     | Duration | Description                                       |
| ----------------------- | -------- | ------------------------------------------------- |
| test-coverage-gate      | ~2m      | Detect files without tests, coverage checks       |
| check-integration-tests | ~1m      | Verify API/service changes have integration tests |
| api-test-generation     | ~1m      | Check if tests can be generated from OpenAPI      |
| test-coverage-summary   | ~30s     | Summarize test coverage results                   |

**Requirements Enforced:**

| Component Type     | Required Tests     | Min Coverage | Enforcement        |
| ------------------ | ------------------ | ------------ | ------------------ |
| API Route          | Unit + Integration | 95%          | Blocks PR (strict) |
| Service            | Unit + Integration | 90%          | Blocks PR (strict) |
| ORM Model          | Unit               | 85%          | Warning            |
| Frontend Component | Unit               | 80%          | Warning            |

**How It Works:**

1. Gets list of changed files in PR
2. For each file type, checks if corresponding test file exists
3. Validates coverage requirements are met
4. Generates helpful PR comment if tests are missing
5. Blocks merge if strict requirements not met

**PR Comment:**

When tests are missing, the workflow posts a helpful comment with:

- List of files without tests
- Links to test generation tools
- Examples of test patterns
- Links to testing documentation

**For Developers:**

If your PR is blocked:

```bash
# Generate test stubs for new files
./scripts/generate-test-stubs.py path/to/new_file.py

# Or generate from OpenAPI spec
./scripts/generate-api-tests.py

# Run full validation
./scripts/validate.sh
```

### pr-review-bot.yml - PR Review Bot (NEM-2102)

**Trigger:** Pull request events (opened, synchronized)

**Purpose:** Automated PR review bot that checks for test coverage and provides helpful guidance.

**Jobs:**

| Job                    | Description                           |
| ---------------------- | ------------------------------------- |
| check-missing-tests    | Review test files in PR changes       |
| test-naming-convention | Validate test file naming conventions |
| summary                | Post summary comment on PR            |

**Features:**

- **Test Detection**: Identifies source files without corresponding test files
- **Helpful Comments**: Posts interactive comments with test generation tips
- **Naming Convention**: Ensures test files follow project patterns
  - Backend: `test_<name>.py`
  - Frontend: `<name>.test.tsx` or `<name>.test.ts`
- **Comment Updates**: Updates PR comment on each push (no duplicates)

**Test Categories Identified:**

- **Backend API routes**: `backend/api/routes/*.py`
- **Backend services**: `backend/services/*.py`
- **Frontend components**: `frontend/src/components/*.tsx`
- **Frontend hooks**: `frontend/src/hooks/*.ts`

**Example PR Comment:**

```
🧪 Test Coverage Review

Backend Changes
- `backend/api/routes/events.py`
- `backend/services/detector.py`

⚠️ No test files found - Please add tests for your changes

📝 How to Add Tests

1. Generate test stubs:
   ./scripts/generate-test-stubs.py backend/api/routes/events.py

2. Implement test cases - Replace TODO comments

3. Verify coverage:
   ./scripts/validate.sh
```

### weekly-test-report.yml - Weekly Test Report (NEM-2102)

**Trigger:** Weekly schedule (Monday 9 AM UTC) + manual dispatch

**Purpose:** Generate comprehensive weekly test coverage and quality metrics report.

**Jobs:**

| Job                      | Duration | Description                             |
| ------------------------ | -------- | --------------------------------------- |
| weekly-report            | ~15m     | Run full test suite and collect metrics |
| analyze-flaky-tests      | ~2m      | Detect intermittently failing tests     |
| coverage-threshold-check | ~1m      | Verify coverage meets thresholds        |
| cleanup-old-reports      | ~1m      | Delete artifacts older than 90 days     |

**Metrics Collected:**

- **Coverage**: Backend unit, integration, combined coverage %
- **Test Counts**: Total, passed, failed, skipped by suite
- **Execution Time**: Duration of each test suite
- **Flaky Tests**: Tests with variable pass/fail rates
- **Coverage Gaps**: Code paths with <80% coverage
- **Performance**: Test execution time trends

**What Gets Generated:**

1. **Console Summary**: Formatted output with key metrics
2. **JSON Report**: Machine-readable report for trend analysis
3. **Test Artifacts**: Coverage data, test reports, logs
4. **Slack Integration**: Optional notification to team channel (requires webhook)

**Report Locations:**

- Console output: GitHub Actions job summary
- JSON report: `weekly-test-report.json` (artifact)
- Coverage data: `.coverage` file (artifact)
- Test reports: `backend-unit-report.json`, `backend-integration-report.json`

**Report Contents:**

```json
{
  "timestamp": "2026-01-13T09:00:00Z",
  "backend_coverage": {
    "coverage_percentage": 92.5,
    "covered_lines": 4250,
    "total_lines": 4600,
    "missing_lines": 350
  },
  "backend_metrics": {
    "total_tests": 1234,
    "passed_tests": 1230,
    "failed_tests": 0,
    "skipped_tests": 4
  },
  "flaky_tests": [...],
  "test_gaps": [...],
  "summary": {...}
}
```

**Accessing Reports:**

1. View in GitHub Actions: Artifacts section of weekly-test-report job
2. Download JSON: Use GitHub CLI: `gh run download <run-id> -n test-reports`
3. Analyze trends: Compare weekly reports over time

**Automatic Cleanup:**

- Reports older than 90 days automatically deleted
- Keeps storage costs manageable
- Latest 12 weeks of reports always available

## Common Patterns

### Caching Dependencies

**Python:**

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: '3.11'
    cache: 'pip'
    cache-dependency-path: pyproject.toml
```

**Node.js:**

```yaml
- uses: actions/setup-node@v4
  with:
    node-version: '20'
    cache: 'npm'
    cache-dependency-path: frontend/package-lock.json
```

### Service Containers

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - 6379:6379
    options: >-
      --health-cmd "redis-cli ping"
      --health-interval 10s
```

### Job Dependencies

```yaml
build:
  needs:
    - lint
    - unit-tests
    - frontend-tests
```

### Conditional Execution

```yaml
# Only run for non-fork PRs
if: >
  github.event.pull_request.head.repo.full_name == github.repository ||
  github.event_name == 'push'
```

### Matrix Strategy

```yaml
strategy:
  matrix:
    language: [python, javascript-typescript]
```

### Artifact Upload

```yaml
- uses: actions/upload-artifact@v6
  with:
    name: benchmark-results
    path: gpu-benchmark.json
```

## Self-Hosted Runner Setup

GPU tests require a self-hosted runner with specific labels.

### Runner Labels Required

```yaml
runs-on: [self-hosted, gpu, rtx-a5500]
```

### Setup Script

See `scripts/setup-gpu-runner.sh` for runner configuration.

### Requirements

- NVIDIA RTX A5500 or compatible GPU
- CUDA drivers installed
- Docker (optional, for container tests)
- Python 3.11+

## Troubleshooting

### CI Takes Too Long

1. Use caching for pip/npm
2. Parallelize independent jobs
3. Consider splitting slow tests

### Tests Pass Locally But Fail in CI

1. Check environment differences (Python version, OS)
2. Verify Redis service is healthy
3. Check for hardcoded paths

### GPU Tests Not Running

1. Verify runner is online: `gh runner list`
2. Check runner labels match workflow
3. Ensure fork protection allows the PR source

### Security Scan False Positives

1. Add to `.gitleaks.toml` allowlist
2. Use `# nosec` comments for Bandit
3. Configure Semgrep exclusions

### Docker Build Failures

1. Check base image availability
2. Review multi-stage build order
3. Verify COPY paths are correct

## Best Practices

### Adding New Workflows

1. Use existing workflows as templates
2. Start with `workflow_dispatch` for manual testing
3. Add to CI once stable
4. Document in this AGENTS.md

### Workflow Naming

- Use descriptive names: `ci.yml`, `deploy.yml`
- Prefix security workflows: `sast.yml`, `codeql.yml`
- Use clear job names in workflow files

### Secrets Management

- Use GitHub Secrets for sensitive values
- Prefer GITHUB_TOKEN when possible
- Document required secrets

## Related Files

- `../AGENTS.md` - Parent directory overview
- `../codeql/AGENTS.md` - CodeQL directory guide
- `../codeql/codeql-config.yml` - CodeQL configuration
- `../prompts/code-review.prompt.md` - AI review prompt
- `../dependabot.yml` - Dependency automation
- `CLAUDE.md` - Project CI/CD requirements
