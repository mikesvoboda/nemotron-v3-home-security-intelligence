# GitHub Configuration Directory - Agent Guide

## Purpose

This directory contains GitHub-specific configuration files for the Home Security Intelligence project, including CI/CD workflows, security scanning, dependency management, and AI-powered code review.

## Directory Structure

```
.github/
  workflows/              # GitHub Actions workflow definitions
    ci.yml                # Main CI pipeline (lint, test, build)
    deploy.yml            # Docker image build and push to GHCR
    ai-code-review.yml    # GPT-powered automated code review
    nightly.yml           # Nightly benchmarks and analysis
    gpu-tests.yml         # GPU integration tests on self-hosted runner
    sast.yml              # Static Application Security Testing
    codeql.yml            # CodeQL security analysis
    gitleaks.yml          # Secret detection scanning
    trivy.yml             # Container vulnerability scanning
  codeql/                 # CodeQL configuration
    codeql-config.yml     # Query configuration and path exclusions
  prompts/                # AI prompt templates
    code-review.prompt.md # System prompt for AI code review
  copilot-instructions.md # GitHub Copilot context
  dependabot.yml          # Automated dependency updates
```

## Key Files

### dependabot.yml

**Purpose:** Configures automated dependency update PRs.

**Ecosystems Monitored:**

| Ecosystem      | Directory | Schedule        | PR Limit |
| -------------- | --------- | --------------- | -------- |
| pip (Python)   | /backend  | Weekly (Monday) | 5        |
| npm (Node.js)  | /frontend | Weekly (Monday) | 5        |
| github-actions | /         | Weekly (Monday) | 3        |
| docker         | /backend  | Monthly         | -        |
| docker         | /frontend | Monthly         | -        |

**Labels Applied:**

- `dependencies` - All dependency PRs
- Language-specific: `python`, `javascript`, `github-actions`, `docker`
- Commit prefix: `chore(deps):`

### copilot-instructions.md

**Purpose:** Provides context to GitHub Copilot for better code suggestions.

**Contents:**

- Tech stack overview (FastAPI, React, RT-DETRv2, Nemotron)
- Coding conventions for Python and TypeScript
- Domain context (security monitoring concepts)
- What NOT to suggest (auth, cloud services, alternative frameworks)

### codeql/codeql-config.yml

**Purpose:** Configures CodeQL security analysis.

**Settings:**

- Uses `security-and-quality` query suite
- Excludes test files from analysis:
  - `**/*.test.ts`, `**/*.test.tsx`
  - `**/test_*.py`, `**/*_test.py`
  - `**/tests/**`, `**/node_modules/**`, `**/.venv/**`

### prompts/code-review.prompt.md

**Purpose:** System prompt for AI-powered code review in PRs.

**Review Focus Areas:**

- Security: Injection, XSS, secrets, path traversal
- Performance: N+1 queries, re-renders, async patterns
- Code Quality: Types, error handling, duplication
- Testing: Coverage and edge cases

## Workflow Overview

### CI Pipeline (ci.yml)

**Trigger:** Push/PR to main branch

**Jobs:**

| Job                | Runner        | Purpose                               |
| ------------------ | ------------- | ------------------------------------- |
| lint               | ubuntu-latest | Ruff linting and formatting           |
| typecheck          | ubuntu-latest | Mypy type checking                    |
| unit-tests         | ubuntu-latest | pytest unit tests with coverage       |
| integration-tests  | ubuntu-latest | pytest integration tests with Redis   |
| frontend-lint      | ubuntu-latest | ESLint                                |
| frontend-typecheck | ubuntu-latest | TypeScript checking                   |
| frontend-tests     | ubuntu-latest | Vitest with coverage                  |
| build              | ubuntu-latest | Docker image builds (after all tests) |

**Concurrency:** Cancels in-progress runs on same branch.

### Deploy Pipeline (deploy.yml)

**Trigger:** Push to main branch only

**Process:**

1. Login to GitHub Container Registry (GHCR)
2. Build Docker images (backend, frontend)
3. Scan with Trivy for vulnerabilities
4. Push to GHCR with tags: `sha-xxx`, `latest`

**Image Names:**

- `ghcr.io/{owner}/{repo}/backend:latest`
- `ghcr.io/{owner}/{repo}/frontend:latest`

### Security Workflows

| Workflow     | Tool            | Trigger                      | Purpose                   |
| ------------ | --------------- | ---------------------------- | ------------------------- |
| sast.yml     | Bandit, Semgrep | Push/PR                      | Python security + OWASP   |
| codeql.yml   | CodeQL          | Push/PR/Weekly               | Deep code analysis        |
| gitleaks.yml | Gitleaks        | Push/PR                      | Secret detection          |
| trivy.yml    | Trivy           | Push/PR (Dockerfile changes) | Container vulnerabilities |

### GPU Tests (gpu-tests.yml)

**Runner:** Self-hosted with `gpu, rtx-a5500` labels

**Requirements:**

- NVIDIA GPU available
- CUDA drivers installed
- Trusted source (fork protection enabled)

**Tests Run:**

- GPU-marked pytest tests (`-m gpu`)
- AI inference benchmarks

### Nightly Analysis (nightly.yml)

**Schedule:** 2am EST (7am UTC) daily

**Jobs:**

1. **Extended Benchmarks** (GPU runner)

   - Big-O complexity tests
   - Memory profiling with memray

2. **Complexity Trends** (ubuntu)

   - Wily code complexity analysis
   - Historical trend reports

3. **Security Audit** (ubuntu)
   - pip-audit for Python dependencies
   - npm audit for Node dependencies
   - Full Bandit scan

### AI Code Review (ai-code-review.yml)

**Trigger:** PR opened/synchronized (non-draft, non-dependabot)

**Process:**

1. Get PR diff (truncated to 20KB for token limits)
2. Run through GPT-4o via GitHub Models
3. Post review comment on PR

## Usage

### Running Workflows Manually

Some workflows support manual dispatch:

```bash
# Nightly analysis
gh workflow run nightly.yml

# View workflow runs
gh run list --workflow=ci.yml
```

### Viewing Workflow Results

```bash
# Latest CI run status
gh run view --workflow=ci.yml

# View specific run logs
gh run view <run-id> --log
```

### Adding New Workflows

1. Create new `.yml` file in `workflows/`
2. Define trigger (`on:`), jobs, steps
3. Use existing workflows as templates
4. Test with `workflow_dispatch` trigger first

## Important Patterns

### Job Dependencies

```yaml
build:
  needs:
    - lint
    - unit-tests
    - frontend-tests
```

### Service Containers

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - 6379:6379
```

### Caching

```yaml
- uses: actions/setup-python@v5
  with:
    cache: "pip"
    cache-dependency-path: backend/requirements*.txt
```

### Matrix Builds

```yaml
strategy:
  matrix:
    include:
      - context: ./backend
        image: backend
      - context: ./frontend
        image: frontend
```

### Self-Hosted Runner Labels

```yaml
runs-on: [self-hosted, gpu, rtx-a5500]
```

## Secrets Required

| Secret        | Purpose                          | Used In       |
| ------------- | -------------------------------- | ------------- |
| GITHUB_TOKEN  | Auto-provided, PR comments, GHCR | All workflows |
| CODECOV_TOKEN | (Optional) Coverage upload       | ci.yml        |

## Troubleshooting

### Workflow Not Running

1. Check branch protection rules
2. Verify trigger conditions match
3. Check concurrency settings (may be cancelled)

### GPU Tests Failing

1. Verify self-hosted runner is online
2. Check GPU availability: `nvidia-smi`
3. Ensure CUDA_VISIBLE_DEVICES is set

### Container Build Failing

1. Check Dockerfile syntax
2. Verify base images are available
3. Review Trivy scan results for vulnerabilities

## Related Files

- `CLAUDE.md` - Project instructions including CI requirements
- `.pre-commit-config.yaml` - Local pre-commit hooks
- `pyproject.toml` - Python tool configuration
- `frontend/package.json` - Frontend scripts
