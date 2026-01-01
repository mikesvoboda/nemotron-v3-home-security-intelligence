# Claude Code Tooling Enhancement Design

**Date:** 2026-01-01
**Status:** Approved
**Author:** Brainstorming session

## Overview

Enhance the development workflow with targeted Claude Code tooling additions that complement existing CI/CD infrastructure without duplicating coverage.

## Goals

1. **Faster feedback loops** - Catch security and Docker issues at commit time
2. **Architecture enforcement** - Leverage existing superpowers for code review
3. **Code quality visibility** - Dead code and complexity metrics in CI
4. **Feature parity** - Ensure backend endpoints are consumed by frontend

## Non-Goals

- Building custom architecture review skills (use existing superpowers)
- Adding MCP servers (overhead not justified)
- Real-time hooks on every edit (too much friction)

## Existing Infrastructure (Do Not Duplicate)

| Tool      | Location            | Coverage                   |
| --------- | ------------------- | -------------------------- |
| Semgrep   | CI (`sast.yml`)     | Python/TypeScript security |
| Bandit    | CI (`sast.yml`)     | Python security            |
| Gitleaks  | CI (`gitleaks.yml`) | Secret detection           |
| CodeQL    | CI (`codeql.yml`)   | Python + TypeScript        |
| Trivy     | CI (`trivy.yml`)    | Container vulnerabilities  |
| API types | Pre-push + CI       | OpenAPI → TypeScript sync  |
| Ruff/mypy | Pre-commit          | Python lint + types        |
| ESLint    | Pre-commit          | TypeScript lint            |

## Design

### 1. Hadolint Pre-commit Hook

**Purpose:** Fill Docker linting gap. Would have caught missing ffmpeg, unpinned versions, missing healthchecks.

**Configuration (`.pre-commit-config.yaml`):**

```yaml
- repo: https://github.com/hadolint/hadolint
  rev: v2.12.0
  hooks:
    - id: hadolint-docker
      name: Hadolint Dockerfile Linting
      entry: hadolint
      language: docker_image
      types: [dockerfile]
```

**Historical bugs this catches:**

- DL3008: Missing ffmpeg in backend image
- DL3006: Unpinned base images
- DL3055: Missing HEALTHCHECK

### 2. Semgrep Pre-commit Hook (Shift-Left)

**Purpose:** Give 2-5 second local security feedback instead of waiting for CI.

**Configuration (`.pre-commit-config.yaml`):**

```yaml
- repo: https://github.com/semgrep/semgrep
  rev: v1.96.0
  hooks:
    - id: semgrep
      name: Semgrep Security Scan
      args:
        - --config=semgrep.yml
        - --config=p/python
        - --error
      types: [python]
```

**Notes:**

- Reuses existing `semgrep.yml` custom rules
- Only scans changed Python files
- Can skip with `SKIP=semgrep git commit` in emergencies

### 3. Dead Code Detection (CI)

#### Python: Vulture

```yaml
# .github/workflows/ci.yml - new job
dead-code:
  name: Dead Code Detection
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: astral-sh/setup-uv@v4
    - run: uv python install 3.14
    - run: uv sync --extra dev --frozen
    - run: uv run vulture backend/ --min-confidence 80
```

#### TypeScript: Knip

```yaml
# Add to frontend jobs
- name: Dead code detection (knip)
  run: cd frontend && npx knip
```

**What these catch:**

- Unused functions, classes, variables, imports
- Unused exports and dependencies
- Unreachable code
- Orphaned files

### 4. Complexity Metrics (CI)

**Purpose:** Flag complexity hotspots before they become unmaintainable.

```yaml
# Add to lint job
- name: Complexity check
  run: |
    uv run radon cc backend/ -a -nc
    uv run radon mi backend/ -nc
```

**Thresholds:**

- Cyclomatic complexity: Fail on grade C or worse (11-20)
- Maintainability index: Warn below 20

### 5. Backend→Frontend Feature Parity (CI)

**Purpose:** Detect backend endpoints with no frontend consumers.

**New script (`scripts/check-api-coverage.sh`):**

```bash
#!/bin/bash
# Finds backend API endpoints with no frontend consumers

# Extract all route paths from backend
BACKEND_ROUTES=$(grep -rh "@router\.\(get\|post\|put\|delete\|patch\)" backend/api/routes/ \
  | sed -n 's/.*"\([^"]*\)".*/\1/p' | sort -u)

# Search frontend for each route
UNUSED=()
for route in $BACKEND_ROUTES; do
  normalized=$(echo "$route" | sed 's/{[^}]*}/<param>/g')
  if ! grep -rq "$normalized\|$route" frontend/src/; then
    UNUSED+=("$route")
  fi
done

if [ ${#UNUSED[@]} -gt 0 ]; then
  echo "Unused backend endpoints (no frontend consumer found):"
  printf '  - %s\n' "${UNUSED[@]}"
  exit 1
fi
echo "All backend endpoints have frontend consumers"
```

**CI integration:**

```yaml
- name: API coverage check
  run: ./scripts/check-api-coverage.sh
```

### 6. Architecture Review (Existing Tools)

**No new implementation needed.** Use existing superpowers:

| Concern             | Superpowers Tool                     |
| ------------------- | ------------------------------------ |
| Scope creep         | `superpowers:requesting-code-review` |
| Over-engineering    | `superpowers:code-reviewer` agent    |
| Pattern violations  | `superpowers:code-reviewer` agent    |
| SOLID principles    | `superpowers:code-reviewer` agent    |
| Architectural drift | `superpowers:code-reviewer` agent    |

**Invocation:** Run `/code-review` before significant commits.

## Dependencies

### Python (`pyproject.toml`)

```toml
[project.optional-dependencies]
dev = [
    # ... existing deps ...
    "vulture>=2.11",
    "radon>=6.0",
]
```

### TypeScript (`frontend/package.json`)

```json
{
  "devDependencies": {
    "knip": "^5.0.0"
  }
}
```

## Implementation Checklist

- [ ] Add Hadolint to `.pre-commit-config.yaml`
- [ ] Add Semgrep to `.pre-commit-config.yaml`
- [ ] Add vulture and radon to `pyproject.toml`
- [ ] Add knip to `frontend/package.json`
- [ ] Create `scripts/check-api-coverage.sh`
- [ ] Add dead-code job to `.github/workflows/ci.yml`
- [ ] Add complexity check to lint job in CI
- [ ] Add API coverage check to CI
- [ ] Update `CLAUDE.md` with new tooling documentation
- [ ] Test all hooks locally
- [ ] Verify CI passes

## Estimated Effort

| Task                   | Time           |
| ---------------------- | -------------- |
| Hadolint setup         | 10 min         |
| Semgrep pre-commit     | 15 min         |
| Vulture CI job         | 15 min         |
| Knip CI job            | 15 min         |
| Radon CI job           | 10 min         |
| API coverage script    | 20 min         |
| Testing & verification | 20 min         |
| **Total**              | **~1.5 hours** |

## Expected Outcomes

- Docker issues caught at commit time (was: CI only)
- Security issues caught at commit time (was: CI only)
- Dead code caught at PR time (was: never)
- Complexity hotspots flagged at PR time (was: never)
- Backend→Frontend drift caught at PR time (was: never)
- Architecture concerns addressed on-demand via existing superpowers

## References

- [Superpowers Plugin](https://github.com/obra/superpowers)
- [Hadolint](https://github.com/hadolint/hadolint)
- [Vulture](https://github.com/jendrikseipp/vulture)
- [Knip](https://github.com/webpro/knip)
- [Radon](https://github.com/rubik/radon)
