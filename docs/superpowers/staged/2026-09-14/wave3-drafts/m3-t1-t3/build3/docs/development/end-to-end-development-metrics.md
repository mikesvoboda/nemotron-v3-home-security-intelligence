# End-to-End Development Metrics Summary

**Project:** Home Security Intelligence (`mikesvoboda/nemotron-v3-home-security-intelligence`)
**Generated:** 2026-01-19
**Scope:** Comprehensive engineering “velocity + quality + delivery pipeline” snapshot, derived from repository state plus live Linear and GitHub Actions data.

---

## Executive summary

- **Delivery velocity (git)**: **906 commits** over **29 days** → **31.24 commits/day** average (peak in week 2).
- **Work management (Linear)**: **2,921 issues** total; **2,605 Done (89.2%)**, **243 Duplicate**, small backlog.
- **CI feedback loop (PR → CI)**: for the **15 most recent merged PRs** on `main`, **CI wall p50 = 11.33 min**, **p95 = 15.80 min**. E2E is the most variable stage (p95 12.58 min).
- **Testing scale (repo)**: backend tests remain heavier than source (backend test-to-source **2.28:1**, overall **1.70:1**).
- **Automation breadth**: **35 GitHub Actions workflows** spanning CI, security, performance, release, deployment, and Linear sync.
- **Local gates**: robust **pre-commit** and **pre-push** hook system (lint/typecheck on commit; parallel unit + E2E + API-type checks on push).

---

## Data sources and methodology

### Data sources

- **Git**: local repository history (`git log`), committer timestamps.
- **Linear**: Linear GraphQL API for team `998946a2-aa75-491b-a39d-189660131392`.
- **GitHub Actions**: workflow runs and job timings for merged PR head SHAs (via GitHub API).
- **Repo filesystem**: line counts by directory buckets.
- **Repo configuration**: `.pre-commit-config.yaml`, `docs/development/hooks.md`, `pyproject.toml`, `frontend/package.json`, `.github/workflows/*.yml`.

### Counting conventions

- **LoC**: reported as **non-empty lines**, with **total lines** in parentheses. “Code-ish files” include common text/code extensions and exclude typical build artifacts (`node_modules`, `dist`, `build`, `coverage`, `.venv`, `.git`).
- **Test counts**: test “case counts” are **static proxies** (e.g., `def test_` occurrences in Python; `it(`/`test(` occurrences in TS). They are **not equivalent** to runtime-collected cases (parametrization multiplies counts).
- **PR→CI timing**: “CI wall-clock” is computed as **(latest job completion - earliest job start)** within the selected CI run for that PR’s head SHA; stage timings use **max shard duration** for sharded stages.

---

## Development velocity (git-derived)

**Project age:** **29 days**
**First commit:** 2025-12-22
**Last commit:** 2026-01-19
**Total commits:** **906**
**Average:** **31.24 commits/day**

**Commits by week** (7-day buckets since first commit):

- **Week 1:** 248 (**35.4/day**)
- **Week 2:** 362 (**51.7/day**)
- **Week 3:** 178 (**25.4/day**)
- **Week 4:** 115 (**16.4/day**)
- **Week 5 (partial):** 3 (**0.4/day**)

---

## Work tracking metrics (Linear, live API)

Team: `998946a2-aa75-491b-a39d-189660131392`

- **Total issues:** **2,921**
- **Done:** **2,605** (**89.2%**)
- **Duplicate:** **243**
- **Backlog:** **31**
- **Canceled:** **37**
- **Todo:** **5**
- **In Progress:** **0**
- **In Review:** **0**

### Epic / subtask structure (API-compatible definition)

The Linear API for this workspace/team does **not** expose an `isEpic` field on `Issue`. To keep the metric reproducible, this report defines an “epic proxy” as:

- **Epic proxy = any issue that has ≥ 1 child issue** (i.e., appears as another issue’s `parent`)

With that definition:

- **Epic proxy count:** **81**
- **Total children attached:** **884**
- **Avg children per epic proxy:** **10.91**

> If you want this to match an “Epic” concept exactly, define epics as a specific **label** (e.g., `epic`) or **project/initiative** and we can compute it deterministically.

---

## Codebase statistics (repo-derived LoC)

Counts are **non-empty lines** (total lines in parentheses), with the directory buckets below.

### Backend

- **Source** (`backend/` excluding `backend/tests/`): **147,693** (**179,989**) lines, **2,356 files**
- **Unit tests** (`backend/tests/unit`): **255,578** (**323,913**) lines, **424 files**
- **Integration tests** (`backend/tests/integration`): **81,387** (**101,138**) lines, **152 files**

### Frontend

- **Source** (`frontend/src` excluding test-ish files/dirs): **158,105** (**173,046**) lines, **467 files**
- **Unit/integration tests (approx)**: **151,086** (**184,468**) lines, **418 files**
- **E2E tests** (`frontend/tests/e2e`): **32,031** (**38,178**) lines, **101 files**

### Total repo (code-ish files)

- **1,337,054** (**1,623,967**) lines, **18,127 files**

---

## Testing infrastructure

### Test-to-source ratios (non-empty LoC)

- **Backend:** **2.28:1**
- **Frontend:** **1.16:1**
- **Overall (backend+frontend):** **1.70:1**

### Test “case” counts (static proxies)

- **Backend**
  - **Unit** `def test_…`: **17,266** (388 files)
  - **Integration** `def test_…`: **3,192** (133 files)
- **Frontend**
  - **Unit** `it()/test()` calls (rough): **10,883** (410 files)
  - **E2E** specs: **64**, `it()/test()` calls (rough): **995**

### CI-enforced coverage thresholds (current repo)

- **Backend unit:** 85% minimum
- **Backend combined (unit + integration):** 95% minimum
- **Frontend:** statements 83%, branches 77%, functions 81%, lines 84%

---

## PR → CI feedback loop metrics (GitHub Actions job timings)

Repo: `mikesvoboda/nemotron-v3-home-security-intelligence`
Sample: **15 most recent merged PRs on `main`**

### Aggregates (minutes)

- **CI wall-clock (critical path)**: **p50 11.33**, **p95 15.80**, **max 15.80**
- **E2E (max shard duration)**: **p50 5.78**, **p95 12.58**, **max 12.58**
- **Vitest (max shard duration)**: **p50 7.43**, **p95 8.28**, **max 8.28**

> Notes:
>
> - “CI wall-clock” is measured from the earliest job start to the latest job completion in the selected CI run.
> - For sharded stages, max shard time is the gating value; sum-of-shards is a compute-cost metric, not a feedback-loop metric.

---

## Tooling snapshot (from repo configs)

### Backend (Python)

From `pyproject.toml` dev dependency groups:

- **Lint/format/type**: Ruff, Mypy
- **Test core**: pytest, pytest-asyncio, pytest-cov, pytest-xdist, pytest-timeout, pytest-rerunfailures, pytest-randomly, pytest-deadfixtures, pytest-split
- **Test utilities**: Hypothesis, factory-boy, fakeredis, testcontainers, freezegun
- **Perf**: pytest-benchmark, pytest-memray, snakeviz, big-o
- **Security**: bandit
- **Quality**: vulture, wily (radon via dependency)

### Frontend (TypeScript)

From `frontend/package.json`:

- **Unit tests**: Vitest + coverage
- **E2E**: Playwright (multiple projects; CI runs Chromium shards)
- **Testing utilities**: React Testing Library
- **Type/lint/format**: TypeScript, ESLint, Prettier (+ tailwind plugin)
- **Mutation testing**: Stryker
- **Accessibility testing**: `@axe-core/playwright`

---

## Git hooks (pre-commit + pre-push + commit-msg)

Hooks are managed via **pre-commit** configuration in `.pre-commit-config.yaml` and documented in `docs/development/hooks.md`.

### Installation

```bash
pre-commit install
pre-commit install --hook-type pre-push
```

The repo also provides:

```bash
./scripts/setup-hooks.sh
./scripts/setup-hooks.sh --check
```

### Pre-commit stage (runs on `git commit`)

**Purpose:** fast local quality gate (~10–30s typical) including:

- **General hygiene:** whitespace, EOF newline, YAML/JSON validation, merge-conflict markers, large file checks
- **Secret detection:** detect-secrets baseline + private key detection
- **Security scanning:** Semgrep (Python), plus other security-oriented linters
- **Python:** Ruff lint + format; Mypy
- **Frontend:** Prettier (frontend), ESLint, TypeScript typecheck
- **API spec:** auto-generate and stage `docs/openapi.json` on backend API/schema changes
- **Test-quality guardrails:** integration tests mock slow services; tests don’t include slow sleeps/timeouts; drift warnings for Pydantic vs Zod; integration tests required for API/service changes

### Commit-msg stage (runs on `git commit`)

**Purpose:** conventional commit message validation via `commitlint` (installed by `./scripts/setup-hooks.sh`).

### Pre-push stage (runs on `git push`)

**Purpose:** catch expensive failures before CI with minimal wall time.

- **Auto-rebase** (`scripts/pre-push-rebase.sh`): keeps feature branches rebased onto `origin/main` before pushing (skippable via `SKIP=auto-rebase git push`).
- **Parallel validations** (`scripts/pre-push-tests.sh`): runs 3 jobs concurrently:
  - Backend unit tests with 85% coverage
  - Playwright Chromium E2E + accessibility specs
  - API types contract check (OpenAPI → TS generated types check)

Skipping is supported but intended for emergencies only (see `docs/development/hooks.md` and `.pre-commit-config.yaml` for exact `SKIP=` targets).

---

## CI/CD pipeline (workflow catalog)

This repo has **35** GitHub Actions workflow files under `.github/workflows/`.

| Workflow                         | File                           | Triggers                                        | What it does                                                                                                                                                                 |
| -------------------------------- | ------------------------------ | ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Accessibility Tests              | `accessibility-tests.yml`      | push                                            | Playwright + axe-core accessibility checks (non-blocking), with reports/artifacts.                                                                                           |
| AI Code Review                   | `ai-code-review.yml`           | pull_request                                    | Automated AI-assisted review checks on PRs.                                                                                                                                  |
| API Compatibility                | `api-compatibility.yml`        | pull_request, push                              | API compatibility checks for schema/type drift and backwards-compatibility.                                                                                                  |
| API Contract Tests               | `api-contract.yml`             | pull_request                                    | PR contract testing: generate OpenAPI, compare against main using oasdiff, report breaking changes and changelog in PR comment.                                              |
| Benchmarks                       | `benchmarks.yml`               | pull_request, push, workflow_dispatch           | pytest-benchmark performance regression detection and memory profiling gates.                                                                                                |
| Bundle Size Tracking             | `bundle-size.yml`              | push                                            | Bundle size measurement/tracking for frontend builds (non-blocking).                                                                                                         |
| CI Analytics                     | `ci-analytics.yml`             | schedule, workflow_dispatch                     | Scheduled CI/CD metrics collection (workflow durations, success rate, bottlenecks; DORA-like summary) and alert threshold checks.                                            |
| CI                               | `ci.yml`                       | pull_request, push, workflow_dispatch           | Primary PR + main validation: backend lint/typecheck/unit+integration shards, frontend lint/typecheck/vitest shards, chromium E2E shards, coverage upload, and build checks. |
| CodeQL Security Analysis         | `codeql.yml`                   | push, schedule                                  | CodeQL security analysis (scheduled and/or main) with results in GitHub Security tab.                                                                                        |
| Dependency Audit                 | `dependency-audit.yml`         | pull_request, push, schedule                    | Dependency auditing and SBOM/vulnerability review automation.                                                                                                                |
| Deploy                           | `deploy.yml`                   | push                                            | Build and push multi-arch backend/frontend images to GHCR, run smoke tests, generate SBOM, sign images, and produce deployment readiness artifacts.                          |
| Documentation Drift Detection    | `docs-drift.yml`               | pull_request, push                              | Detect documentation drift between code and docs (PR/main).                                                                                                                  |
| Documentation                    | `docs.yml`                     | push, workflow_dispatch                         | Documentation build/publish checks.                                                                                                                                          |
| Secret Detection                 | `gitleaks.yml`                 | pull_request, push                              | Secret scanning using Gitleaks + TruffleHog.                                                                                                                                 |
| GPU Tests                        | `gpu-tests.yml`                | push                                            | GPU/self-hosted runner tests validating GPU pipeline and related hardware-dependent suites.                                                                                  |
| Lighthouse Performance Tests     | `lighthouse.yml`               | push                                            | Lighthouse performance/SEO/best-practices audit for frontend.                                                                                                                |
| Linear CI Status Sync            | `linear-ci-status.yml`         | push, workflow_dispatch, workflow_run           | Sync Linear issue states with CI outcomes and merges to main.                                                                                                                |
| Linear-GitHub Issue Sync         | `linear-github-sync.yml`       | schedule, workflow_dispatch                     | Scheduled sync between Linear and GitHub metadata.                                                                                                                           |
| Load Tests                       | `load-tests.yml`               | push, schedule, workflow_dispatch               | k6 load testing on main + scheduled runs; produces artifacts and summaries.                                                                                                  |
| Mutation Testing                 | `mutation-testing.yml`         | schedule, workflow_dispatch                     | Scheduled/on-demand mutation testing to measure test suite strength.                                                                                                         |
| Nightly Analysis                 | `nightly.yml`                  | schedule, workflow_dispatch                     | Nightly scheduled deeper analysis suite (non-PR) for regression detection.                                                                                                   |
| PR Review Bot - Test Enforcement | `pr-review-bot.yml`            | pull_request, workflow_dispatch                 | PR review bot / policy enforcement (e.g., test expectations, advisories).                                                                                                    |
| Preview Deploy                   | `preview-deploy.yml`           | workflow_dispatch                               | Manual preview deployment workflow (on-demand).                                                                                                                              |
| Release Drafter                  | `release-drafter.yml`          | push                                            | Maintains draft release notes based on merged PRs.                                                                                                                           |
| Release                          | `release.yml`                  | push                                            | Tag-triggered GitHub release creation and changelog generation.                                                                                                              |
| Automated Rollback               | `rollback.yml`                 | workflow_run                                    | Automated rollback workflow triggered from workflow_run events.                                                                                                              |
| SAST (Static Analysis)           | `sast.yml`                     | pull_request, push                              | Static analysis security scanning (Semgrep + other SAST tooling) on PR/main.                                                                                                 |
| Semantic Release                 | `semantic-release.yml`         | push, workflow_dispatch                         | Automated versioning + changelog + GitHub releases based on conventional commits.                                                                                            |
| Test Coverage Gate               | `test-coverage-gate.yml`       | pull_request, workflow_dispatch                 | PR gate enforcing test/coverage requirements and posting PR comments when requirements are missing.                                                                          |
| Trivy Security Scan              | `trivy.yml`                    | pull_request, push, schedule, workflow_dispatch | Trivy vulnerability scanning for deps and container configs/images.                                                                                                          |
| Visual Regression Tests          | `visual-tests.yml`             | push, workflow_dispatch                         | Playwright visual regression tests (non-blocking), with artifacts and optional baseline update.                                                                              |
| Vulnerability Management         | `vulnerability-management.yml` | schedule, workflow_dispatch                     | Scheduled vulnerability management reporting and follow-ups.                                                                                                                 |
| Weekly Audit                     | `weekly-audit.yml`             | schedule, workflow_dispatch                     | Weekly audit workflow (security/quality checks) to keep hygiene high.                                                                                                        |
| Weekly Test Report               | `weekly-test-report.yml`       | schedule, workflow_dispatch                     | Weekly test/coverage reporting artifacts and trend capture.                                                                                                                  |
| ZAP Security Scan                | `zap-security.yml`             | push, workflow_dispatch                         | OWASP ZAP dynamic scanning (scheduled/on-demand) and reporting.                                                                                                              |

---

## Known gaps / opportunities (from session findings)

1. **DORA correctness**: `scripts/ci-metrics-collector.py` currently computes DORA-like values based on workflow runs and durations, not true deploy-based DORA. For correctness, base DORA on successful runs of the `Deploy` workflow and map merges → deploys for lead time.
2. **CI metrics to Grafana**: the repo can generate Prometheus-format CI metrics, but Prometheus isn’t scraping them by default; consider pushgateway or backend ingestion so `ci_*` metrics appear in Grafana.
3. **Epic definition**: define epics explicitly (label/project/initiative) if you want stable epic/subtask metrics over time; “parent issue” proxy is deterministic but may not match prior reporting.
