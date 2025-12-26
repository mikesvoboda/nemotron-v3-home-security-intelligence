# GitHub CI/CD Pipeline Design

**Date:** 2025-12-26
**Status:** Approved

## Overview

Extend the existing pre-commit infrastructure with GitHub Actions CI/CD for security scanning, performance analysis, and container deployment.

## Architecture

### Three-Phase Rollout

| Phase   | Focus                | Status                             |
| ------- | -------------------- | ---------------------------------- |
| Phase 1 | Security Scanning    | Planned                            |
| Phase 2 | Performance Analysis | Planned                            |
| Phase 3 | Claude Code Review   | Deferred (pending enterprise auth) |

### Runner Strategy

| Runner Type               | Purpose                                                          | When Used                          |
| ------------------------- | ---------------------------------------------------------------- | ---------------------------------- |
| `ubuntu-latest`           | Security scans, linting, unit tests, container builds            | All PRs, main commits              |
| `self-hosted` (RTX A5500) | GPU integration tests, AI inference benchmarks, memory profiling | PRs to main, main commits, nightly |

### Workflow Triggers

| Event                | Security      | Performance  | GPU Tests | Deploy |
| -------------------- | ------------- | ------------ | --------- | ------ |
| PR to main           | ✓             | ✓            | ✓         | ✗      |
| Push to main         | ✓             | ✓            | ✓         | ✓      |
| Push to other branch | ✓ (fast only) | ✗            | ✗         | ✗      |
| Nightly (2am)        | ✓             | ✓ (extended) | ✓         | ✗      |

## Phase 1: Security Scanning

### Tools

| Tool       | Target                             | Catches                                                   |
| ---------- | ---------------------------------- | --------------------------------------------------------- |
| Dependabot | `requirements.txt`, `package.json` | Vulnerable dependencies, auto-creates PRs                 |
| CodeQL     | Python, TypeScript                 | SQL injection, XSS, code injection, insecure patterns     |
| Trivy      | Docker images                      | CVEs in base images, OS packages, app dependencies        |
| Bandit     | Python code                        | Hardcoded passwords, unsafe YAML loading, shell injection |
| Semgrep    | Python + TypeScript                | OWASP Top 10, custom rules                                |
| Gitleaks   | Git history                        | Leaked secrets, API keys, credentials                     |

### Fail Conditions

- HIGH or CRITICAL vulnerability: **Block merge**
- MEDIUM vulnerability: Warning only
- Secrets detected: **Block merge**

### Estimated Run Time

3-5 minutes on GitHub-hosted runners

## Phase 2: Performance Analysis

### Backend Performance

| Metric               | Tool             | Threshold                         | Runs On         |
| -------------------- | ---------------- | --------------------------------- | --------------- |
| API response time    | pytest-benchmark | Fail if >20% slower than baseline | GitHub-hosted   |
| Memory per endpoint  | pytest-memray    | Fail if >500MB peak               | GitHub-hosted   |
| AI inference latency | pytest-benchmark | Fail if >20% slower               | Self-hosted GPU |
| AI memory usage      | pytest-memray    | Warn if >20GB                     | Self-hosted GPU |

### Frontend Performance (Lighthouse CI)

| Metric                 | Threshold             |
| ---------------------- | --------------------- |
| Performance score      | ≥80                   |
| First Contentful Paint | <2s                   |
| Bundle size            | Warn if >10% increase |

### Complexity Analysis

| Tool             | Purpose                            | Trigger                               |
| ---------------- | ---------------------------------- | ------------------------------------- |
| radon            | Cyclomatic complexity per function | Every PR - fail if any function >15   |
| wily             | Complexity trend over time         | Nightly - report in PR comment        |
| big-o benchmarks | Empirical scaling analysis         | Nightly + PRs touching critical paths |

### Critical Paths for Big-O Analysis

- `backend/services/batch_aggregator.py` - processes detection batches
- `backend/services/file_watcher.py` - handles FTP uploads
- `backend/api/routes/events.py` - event queries with filters

### Estimated Run Times

- GitHub-hosted checks: 5-8 minutes
- Self-hosted GPU checks: 10-15 minutes (includes model loading)

## Self-Hosted Runner Setup

### Installation

```bash
./config.sh --url https://github.com/USER/nemotron-v3-home-security-intelligence \
            --token <runner-token-from-github>
sudo ./svc.sh install
sudo ./svc.sh start
```

### Labels

```yaml
labels: [self-hosted, linux, gpu, rtx-a5500]
```

### Security (for future public repo)

| Risk                              | Mitigation                                                 |
| --------------------------------- | ---------------------------------------------------------- |
| Malicious PR runs code on machine | Only trigger GPU jobs on PRs from collaborators, not forks |
| Secrets exposed to workflows      | Use GitHub environment protection rules                    |
| Resource exhaustion               | Set job timeouts, limit concurrent jobs to 1               |

### Fork Protection

```yaml
if: github.event.pull_request.head.repo.full_name == github.repository || github.event_name == 'push'
```

## File Structure

```
.github/
├── workflows/
│   ├── ci.yml              # Main CI - orchestrates all checks
│   ├── security.yml        # Security scans (reusable)
│   ├── performance.yml     # Performance benchmarks (reusable)
│   ├── gpu-tests.yml       # GPU-specific tests (self-hosted)
│   ├── nightly.yml         # Extended analysis (scheduled)
│   └── deploy.yml          # Build & push containers (main only)
├── dependabot.yml          # Auto-update dependencies
├── codeql/
│   └── codeql-config.yml   # CodeQL custom config
└── actions/
    └── setup-python/       # Reusable composite action
        └── action.yml
```

## Container Strategy

- All services containerized (including GPU runtime)
- Models mounted as volumes (not baked into images)
- Trivy scans all images before merge
- Images pushed to GitHub Container Registry (ghcr.io)
- Tags: `:latest` and `:sha-<commit>`

## PR Status Checks (Required to Merge)

- `security` - all scans pass
- `performance` - no regressions >20%
- `gpu-tests` - AI pipeline works
- `complexity` - no function >15 cyclomatic complexity

## Phase 3: Claude Code Review (Deferred)

Pending resolution of enterprise OAuth authentication for CI environments. Options to revisit:

1. Self-hosted runner with persistent auth session
2. Enterprise service account token (check with admin)
3. Separate direct Anthropic API for CI only

## Dependencies to Add

### Python (dev)

```
pytest-benchmark
pytest-memray
bandit
radon
wily
big-o
```

### Node (dev)

```
@lhci/cli
```
