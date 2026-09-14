# Documentation Drift Detection Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automatically detect when code changes require documentation updates and create detailed Linear tasks in backlog.

**Architecture:** CI/CD pipeline analyzes git diffs against configurable rules, identifies documentation gaps, and creates non-blocking Linear tasks with full context for agents to address later.

**Tech Stack:** Python detection script, Linear API, GitHub Actions, YAML configuration

---

## Overview

This system detects documentation drift when code changes and creates detailed Linear tasks without blocking development. Tasks contain enough context for AI agents (or humans) to update documentation accurately.

### Design Principles

- **Non-blocking**: Development velocity unaffected
- **Detailed**: Tasks have full context for agents
- **Deduplicated**: Won't create duplicate tasks for same drift
- **Configurable**: Rules in YAML, not hardcoded
- **Integrated**: Uses existing Linear workflow

---

## Detection Strategy

### Trigger Categories

| Trigger                | Detection Method                                     | Priority |
| ---------------------- | ---------------------------------------------------- | -------- |
| New API endpoint       | New route decorator in `backend/api/routes/*.py`     | High     |
| Modified API schema    | Changes to `backend/api/schemas/*.py`                | Medium   |
| New frontend component | New `.tsx` file in `frontend/src/components/`        | Medium   |
| New React hook         | New `use*.ts` file in `frontend/src/hooks/`          | Low      |
| New service            | New `.py` file in `backend/services/`                | Medium   |
| Environment variable   | New `getenv()` or `settings.` in Python              | High     |
| Config schema changed  | Changes to `pyproject.toml` or `docker-compose*.yml` | Medium   |
| Broken doc links       | Markdown link targets that don't exist               | High     |

### Detection Script

**File:** `scripts/check-docs-drift.py`

```python
#!/usr/bin/env python3
"""
Documentation drift detection script.

Analyzes git changes and identifies documentation that may need updating.
Outputs structured JSON for Linear task creation.

Usage:
    uv run python scripts/check-docs-drift.py --output drift-report.json
    uv run python scripts/check-docs-drift.py --base main --head HEAD
"""

DRIFT_RULES = [
    {
        "id": "new-api-endpoint",
        "pattern": r"@router\.(get|post|put|patch|delete)\(",
        "files": "backend/api/routes/*.py",
        "priority": "high",
        "docs_required": [
            "backend/api/routes/AGENTS.md",
            "docs/developer/api/*.md",
        ],
        "suggestion_template": "Document new {method} endpoint at {path}",
    },
    {
        "id": "new-frontend-component",
        "pattern": r"^export (default )?function \w+",
        "files": "frontend/src/components/**/*.tsx",
        "priority": "medium",
        "docs_required": [
            "{dir}/AGENTS.md",
            "docs/ui/*.md",
        ],
        "suggestion_template": "Document new component {name} in {file}",
    },
    {
        "id": "new-env-variable",
        "pattern": r"(os\.getenv|settings\.)\w+",
        "files": "backend/**/*.py",
        "priority": "high",
        "docs_required": [
            "docs/reference/config/env-reference.md",
        ],
        "suggestion_template": "Document environment variable {var_name}",
    },
    {
        "id": "new-hook",
        "pattern": r"^export function use\w+",
        "files": "frontend/src/hooks/*.ts",
        "priority": "low",
        "docs_required": [
            "frontend/src/hooks/AGENTS.md",
        ],
        "suggestion_template": "Document hook {name}",
    },
    {
        "id": "schema-change",
        "pattern": r"class \w+\(BaseModel\)",
        "files": "backend/api/schemas/*.py",
        "priority": "medium",
        "docs_required": [
            "docs/developer/api/*.md",
        ],
        "suggestion_template": "Verify API documentation reflects schema changes",
    },
]


def detect_drift(base: str, head: str) -> list[dict]:
    """Analyze git diff and detect documentation drift."""

    # 1. Get changed files
    changed_files = get_changed_files(base, head)

    # 2. Categorize changes by drift rules
    drift_items = []
    for file_path, diff_content in changed_files.items():
        for rule in DRIFT_RULES:
            if matches_file_pattern(file_path, rule["files"]):
                if is_new_file(file_path, base):
                    # New file - definitely needs docs
                    drift_items.append(create_drift_item(
                        rule, file_path, diff_content, "new_file"
                    ))
                elif has_pattern_match(diff_content, rule["pattern"]):
                    # Existing file with significant changes
                    drift_items.append(create_drift_item(
                        rule, file_path, diff_content, "modified"
                    ))

    # 3. Check if required docs exist and are current
    for item in drift_items:
        item["missing_docs"] = find_missing_docs(item)
        item["outdated_docs"] = find_outdated_docs(item)

    # 4. Deduplicate and group related items
    return group_related_drift(drift_items)
```

### Output Format

**File:** `drift-report.json`

```json
{
  "detected_at": "2026-01-18T15:30:00Z",
  "base_ref": "main",
  "head_ref": "abc1234",
  "pr_number": 142,
  "drift_items": [
    {
      "id": "new-api-endpoint",
      "priority": "high",
      "source_file": "backend/api/routes/system.py",
      "line_range": [892, 945],
      "change_type": "new_file",
      "description": "New GET /api/system/circuit-breakers endpoint",
      "diff_excerpt": "@router.get('/circuit-breakers')...",
      "missing_docs": ["docs/developer/api/system-advanced.md"],
      "outdated_docs": ["backend/api/routes/AGENTS.md"],
      "suggested_updates": [
        "Add endpoint to AGENTS.md table",
        "Create system-advanced.md with circuit breaker documentation"
      ]
    }
  ],
  "summary": {
    "high_priority": 1,
    "medium_priority": 2,
    "low_priority": 0,
    "total": 3
  }
}
```

---

## Linear Task Creation

### Task Template

```markdown
## Documentation Update Required

**Trigger:** {trigger_type}
**Detected:** {detected_at} in commit `{commit_sha}`
**PR:** #{pr_number}

### What Changed

\`\`\`diff
{diff_excerpt}
\`\`\`

**Source:** `{source_file}:{line_start}-{line_end}`

### Documentation Impact

{docs_checklist}

### Suggested Updates

{suggestions}

### Acceptance Criteria

- [ ] Documentation accurately reflects implementation
- [ ] Links from hub documents work
- [ ] AGENTS.md updated if new file added
- [ ] `./scripts/validate.sh` passes

---

_Auto-generated by docs-drift detection_
```

### Creation Script

**File:** `scripts/create-docs-tasks.py`

```python
#!/usr/bin/env python3
"""
Create Linear tasks from documentation drift report.

Usage:
    uv run python scripts/create-docs-tasks.py drift-report.json

Environment:
    LINEAR_API_KEY: Linear API key with write access
"""

import json
import hashlib

# Linear configuration (from docs/development/linear-integration.md)
TEAM_ID = "998946a2-aa75-491b-a39d-189660131392"
BACKLOG_STATE_ID = "88b50a4e-75a1-4f34-a3b0-598bfd118aac"

PRIORITY_MAP = {
    "high": 2,    # High priority in Linear
    "medium": 3,  # Medium
    "low": 4,     # Low
}


def generate_task_id(drift_item: dict) -> str:
    """Generate deterministic ID for deduplication."""
    key = f"{drift_item['source_file']}:{drift_item['id']}:{drift_item['description']}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def task_already_exists(task_id: str) -> bool:
    """Check if task with this drift ID already exists in Linear."""
    existing = linear_search_issues(f"drift-id:{task_id}")
    return len(existing) > 0


def create_linear_task(item: dict, report: dict) -> str | None:
    """Create a Linear task and return the issue ID."""

    task_id = generate_task_id(item)

    # Skip if already exists
    if task_already_exists(task_id):
        print(f"Skipping duplicate: {item['description']}")
        return None

    title = f"docs: {item['description']}"
    description = create_task_description(item, report)
    description += f"\n\n`drift-id:{task_id}`"  # For deduplication

    issue = linear_create_issue(
        title=title,
        team_id=TEAM_ID,
        description=description,
        priority=PRIORITY_MAP[item["priority"]],
        labels=["documentation", "auto-generated"],
        state_id=BACKLOG_STATE_ID,
    )

    return issue["id"]
```

### Deduplication Strategy

The script uses a deterministic hash (`drift-id:abc123`) embedded in task descriptions:

```
PR #100 changes system.py → Creates NEM-500 with drift-id:abc123
PR #101 changes system.py again → Finds existing drift-id:abc123, skips
PR #102 changes different endpoint → Creates NEM-501 with drift-id:def456
```

### Batch Grouping

Related drift items are grouped into single tasks:

```python
def group_related_drift(items: list) -> list:
    """Group drift items that should be one task."""
    groups = {}
    for item in items:
        # Group by target documentation file
        key = tuple(sorted(item["missing_docs"] + item["outdated_docs"]))
        if key not in groups:
            groups[key] = []
        groups[key].append(item)

    # Merge grouped items into single drift items
    return [merge_drift_items(group) for group in groups.values()]
```

---

## CI/CD Integration

### GitHub Workflow

**File:** `.github/workflows/docs-drift.yml`

```yaml
name: Documentation Drift Detection

on:
  pull_request:
    branches: [main]
    types: [opened, synchronize]
  push:
    branches: [main]

jobs:
  detect-drift:
    name: Check Documentation Drift
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up uv
        uses: astral-sh/setup-uv@v4
        with:
          version: '0.9.18'

      - name: Analyze changes for doc drift
        run: uv run python scripts/check-docs-drift.py --output drift-report.json

      - name: Create Linear tasks for drift
        if: hashFiles('drift-report.json') != ''
        env:
          LINEAR_API_KEY: ${{ secrets.LINEAR_API_KEY }}
        run: uv run python scripts/create-docs-tasks.py drift-report.json

      - name: Comment on PR with drift summary
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            if (!fs.existsSync('drift-report.json')) return;

            const report = JSON.parse(fs.readFileSync('drift-report.json'));
            if (report.drift_items.length === 0) return;

            let body = '## Documentation Drift Detected\n\n';
            body += 'This PR introduces changes that may require documentation updates.\n\n';
            body += '| Priority | Description | Status |\n';
            body += '|----------|-------------|--------|\n';

            for (const item of report.drift_items) {
              const icon = item.priority === 'high' ? '🔴' : item.priority === 'medium' ? '🟡' : '🟢';
              body += `| ${icon} ${item.priority} | ${item.description} | Task created |\n`;
            }

            body += '\n---\n<sub>Auto-generated by documentation drift detection. Tasks are non-blocking.</sub>';

            github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: body
            });
```

### Execution Flow

```
PR Opened/Updated
       │
       ▼
┌─────────────────────┐
│ check-docs-drift.py │  Analyze git diff, detect triggers
└─────────────────────┘
       │
       ▼ (drift-report.json)
┌──────────────────────┐
│ create-docs-tasks.py │  Create Linear tasks via API
└──────────────────────┘
       │
       ▼
┌─────────────────────┐
│  PR Comment Posted  │  Summary with links to tasks
└─────────────────────┘
```

---

## Configuration

### Rules Configuration

**File:** `scripts/docs-drift-rules.yml`

```yaml
# Documentation drift detection rules
# Add/modify rules without changing Python code

rules:
  - id: new-api-endpoint
    description: 'New API endpoint added'
    file_patterns:
      - 'backend/api/routes/*.py'
    content_patterns:
      - '@router\.(get|post|put|patch|delete)\('
    priority: high
    required_docs:
      - '{dir}/AGENTS.md'
      - 'docs/developer/api/*.md'

  - id: new-service
    description: 'New backend service'
    file_patterns:
      - 'backend/services/*.py'
    new_file_only: true
    priority: medium
    required_docs:
      - 'backend/services/AGENTS.md'

  - id: docker-compose-change
    description: 'Docker service configuration changed'
    file_patterns:
      - 'docker-compose*.yml'
    priority: medium
    required_docs:
      - 'docs/operator/deployment/README.md'

  - id: new-frontend-page
    description: 'New frontend page added'
    file_patterns:
      - 'frontend/src/pages/*.tsx'
    new_file_only: true
    priority: high
    required_docs:
      - 'frontend/src/pages/AGENTS.md'
      - 'docs/ui/*.md'
      - 'docs/user-guide/*.md'

# Files to always ignore
ignore_patterns:
  - '**/test_*.py'
  - '**/*.test.ts'
  - '**/*.test.tsx'
  - '**/conftest.py'
  - 'mutants/**'
  - '.venv/**'
```

---

## File Structure

```
scripts/
├── check-docs-drift.py      # Detection logic (new)
├── create-docs-tasks.py     # Linear task creation (new)
└── docs-drift-rules.yml     # Configurable rules (new)

.github/workflows/
└── docs-drift.yml           # CI workflow (new)

docs/development/
└── docs-maintenance.md      # How this system works (new)
```

---

## Implementation Tasks

### Task 1: Create Detection Script

**Files:**

- Create: `scripts/check-docs-drift.py`
- Create: `scripts/docs-drift-rules.yml`

**Steps:**

1. Implement git diff analysis
2. Implement rule matching logic
3. Implement documentation existence checking
4. Implement JSON output generation
5. Add CLI argument parsing
6. Write unit tests

### Task 2: Create Linear Task Script

**Files:**

- Create: `scripts/create-docs-tasks.py`

**Steps:**

1. Implement Linear API integration
2. Implement deduplication logic
3. Implement task template rendering
4. Implement batch grouping
5. Write unit tests

### Task 3: Create CI Workflow

**Files:**

- Create: `.github/workflows/docs-drift.yml`

**Steps:**

1. Create workflow file
2. Add PR comment generation
3. Test on feature branch
4. Add LINEAR_API_KEY to repository secrets

### Task 4: Documentation

**Files:**

- Create: `docs/development/docs-maintenance.md`

**Steps:**

1. Document how the system works
2. Document how to add new rules
3. Document how to handle generated tasks

---

## Summary

| Component              | Purpose                               | Blocking? |
| ---------------------- | ------------------------------------- | --------- |
| `check-docs-drift.py`  | Analyze git diff, detect doc gaps     | No        |
| `create-docs-tasks.py` | Create detailed Linear tasks          | No        |
| `docs-drift.yml`       | CI workflow triggered on PRs          | No        |
| `docs-drift-rules.yml` | Configurable detection rules          | N/A       |
| PR Comment             | Links to created tasks for visibility | No        |
