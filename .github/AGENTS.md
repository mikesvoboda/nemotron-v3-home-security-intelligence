# GitHub Configuration Directory - Agent Guide

## Purpose

This directory contains GitHub-specific configuration files for the Home Security Intelligence project, including CI/CD workflows, security scanning, dependency management, and AI-powered code review.

## Directory Structure

```
.github/
  AGENTS.md                   # This file
  dependabot.yml              # Automated dependency updates
  copilot-instructions.md     # GitHub Copilot context
  codeql/                     # CodeQL configuration
    codeql-config.yml         # Query configuration and path exclusions
  prompts/                    # AI prompt templates
    AGENTS.md                 # Prompts directory guide
    code-review.prompt.md     # System prompt for AI code review
  workflows/                  # GitHub Actions workflow definitions
    AGENTS.md                 # Workflows directory guide
    ci.yml                    # Main CI pipeline
    deploy.yml                # Docker image build and push
    ai-code-review.yml        # GPT-powered code review
    nightly.yml               # Nightly benchmarks and analysis
    gpu-tests.yml             # GPU integration tests
    sast.yml                  # Static Application Security Testing
    codeql.yml                # CodeQL security analysis
    gitleaks.yml              # Secret detection scanning
    trivy.yml                 # Container vulnerability scanning
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

| Job                | Runner        | Description                         |
| ------------------ | ------------- | ----------------------------------- |
| lint               | ubuntu-latest | Ruff linting and formatting         |
| typecheck          | ubuntu-latest | Mypy type checking                  |
| unit-tests         | ubuntu-latest | pytest unit tests with coverage     |
| integration-tests  | ubuntu-latest | pytest with Redis service container |
| api-types-check    | ubuntu-latest | API types contract verification     |
| frontend-lint      | ubuntu-latest | ESLint                              |
| frontend-typecheck | ubuntu-latest | TypeScript checking                 |
| frontend-tests     | ubuntu-latest | Vitest with coverage                |
| frontend-e2e       | ubuntu-latest | Playwright E2E tests                |
| build              | ubuntu-latest | Docker image builds (after tests)   |

**Environment:**

- Python 3.12
- Node.js 20
- Coverage uploaded to Codecov

### Deploy Pipeline (deploy.yml)

**Trigger:** Push to main branch only

**Process:**

1. Login to GitHub Container Registry (GHCR)
2. Build images with Buildx (multi-arch: amd64, arm64)
3. Scan with Trivy for vulnerabilities (fail on CRITICAL/HIGH)
4. Push with tags: `sha-{commit}`, `latest`

**Image Names:**

- `ghcr.io/{owner}/{repo}/backend:latest`
- `ghcr.io/{owner}/{repo}/frontend:latest`

### Security Workflows

| Workflow     | Tool            | Trigger              | Purpose                   |
| ------------ | --------------- | -------------------- | ------------------------- |
| sast.yml     | Bandit, Semgrep | Push/PR              | Python security + OWASP   |
| codeql.yml   | CodeQL          | Push/PR/Weekly       | Deep code analysis        |
| gitleaks.yml | Gitleaks        | Push/PR              | Secret detection          |
| trivy.yml    | Trivy           | Push/PR (Dockerfile) | Container vulnerabilities |

### GPU Tests (gpu-tests.yml)

**Runner:** Self-hosted with `gpu, rtx-a5500` labels

**Requirements:**

- NVIDIA GPU available
- CUDA drivers installed
- Trusted source (fork protection enabled)
- 30-minute timeout

**Tests Run:**

- GPU-marked pytest tests (`-m gpu`)
- AI inference benchmarks

### Nightly Analysis (nightly.yml)

**Schedule:** 2am EST (7am UTC) daily

**Jobs:**

1. **Extended Benchmarks** (GPU runner) - Big-O tests, memory profiling
2. **Complexity Trends** (ubuntu) - Wily code complexity reports
3. **Security Audit** (ubuntu) - pip-audit, npm audit, Bandit

### AI Code Review (ai-code-review.yml)

**Trigger:** PR opened/synchronized (non-draft, non-dependabot)

**Process:**

1. Get PR diff (truncated to 20KB)
2. Run through GPT-4o via GitHub Models
3. Post review as PR comment

## Usage

### Running Workflows Manually

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
3. Check concurrency settings

### GPU Tests Failing

1. Verify self-hosted runner is online
2. Check GPU availability: `nvidia-smi`
3. Ensure CUDA_VISIBLE_DEVICES is set

### Container Build Failing

1. Check Dockerfile syntax
2. Verify base images are available
3. Review Trivy scan results

## Related Files

- `CLAUDE.md` - Project instructions including CI requirements
- `.pre-commit-config.yaml` - Local pre-commit hooks
- `pyproject.toml` - Python tool configuration
- `frontend/package.json` - Frontend scripts
