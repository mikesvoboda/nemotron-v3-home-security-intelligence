# GitHub Workflows Directory - Agent Guide

## Purpose

This directory contains GitHub Actions workflow definitions for the Home Security Intelligence project. Workflows automate CI/CD, testing, security scanning, and code quality checks.

## Directory Contents

```
workflows/
  AGENTS.md              # This file
  ci.yml                 # Main CI pipeline
  deploy.yml             # Docker image build and push to GHCR
  ai-code-review.yml     # GPT-powered automated code review
  nightly.yml            # Nightly benchmarks and analysis
  gpu-tests.yml          # GPU integration tests
  sast.yml               # Static Application Security Testing
  codeql.yml             # CodeQL security analysis
  gitleaks.yml           # Secret detection scanning
  trivy.yml              # Container vulnerability scanning
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

- Python 3.14
- Node.js 20
- PostgreSQL 16 (service container)
- Redis 7 (service container for integration tests)
- Coverage uploaded to Codecov

**Concurrency:** Only one run per branch at a time.

### deploy.yml - Container Deployment

**Trigger:** Push to main branch only

**Purpose:** Build and push Docker images to GitHub Container Registry.

**Process:**

1. Authenticate to GHCR
2. Build images with Buildx (multi-arch: amd64, arm64)
3. Scan with Trivy (fail on CRITICAL/HIGH)
4. Push with tags: `sha-{commit}`, `latest`

**Matrix Build:**

- Backend: `./backend/Dockerfile.prod`
- Frontend: `./frontend/Dockerfile.prod`

**Permissions:**

- `contents: read`
- `packages: write`

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
- `backend/requirements.txt`
- `frontend/package.json`

**Severity Filter:** CRITICAL, HIGH (fails build)

**Output:** SARIF format uploaded to GitHub Security tab

## Common Patterns

### Caching Dependencies

**Python:**

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: '3.12'
    cache: 'pip'
    cache-dependency-path: backend/requirements*.txt
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

- `../.github/AGENTS.md` - Parent directory overview
- `../codeql/AGENTS.md` - CodeQL directory guide
- `../codeql/codeql-config.yml` - CodeQL configuration
- `../prompts/code-review.prompt.md` - AI review prompt
- `../dependabot.yml` - Dependency automation
- `CLAUDE.md` - Project CI/CD requirements
