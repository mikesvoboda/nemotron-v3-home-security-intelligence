#!/usr/bin/env python3
"""Create Linear tasks from documentation drift report.

This script reads a drift report (JSON) and creates Linear tasks for each
detected documentation drift item. It implements deduplication using a
deterministic hash embedded in task descriptions.

Usage:
    uv run python scripts/create-docs-tasks.py drift-report.json
    uv run python scripts/create-docs-tasks.py < drift-report.json
    cat drift-report.json | uv run python scripts/create-docs-tasks.py

Environment:
    LINEAR_API_KEY: Linear API key with write access (required)

Exit codes:
    0 - Success (tasks created or skipped due to deduplication)
    1 - Error (missing API key, API failure, invalid input)

Related:
    - docs/plans/2026-01-18-docs-drift-detection-design.md
    - docs/development/linear-integration.md
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

import httpx

# =============================================================================
# Linear Configuration
# =============================================================================
# From docs/development/linear-integration.md

TEAM_ID = "998946a2-aa75-491b-a39d-189660131392"
BACKLOG_STATE_ID = "88b50a4e-75a1-4f34-a3b0-598bfd118aac"

# Priority mapping: drift priority -> Linear priority
# Linear: 0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low
PRIORITY_MAP: dict[str, int] = {
    "high": 2,
    "medium": 3,
    "low": 4,
}

# Linear API configuration
LINEAR_API_URL = "https://api.linear.app/graphql"
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
RETRY_DELAY = 2.0  # seconds

# Labels to apply to created tasks
TASK_LABELS = ["documentation", "auto-generated"]


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class DriftItem:
    """Represents a single documentation drift item from the report."""

    id: str
    priority: str
    source_file: str
    line_range: list[int]
    change_type: str
    description: str
    diff_excerpt: str
    missing_docs: list[str]
    outdated_docs: list[str]
    suggested_updates: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DriftItem:
        """Create a DriftItem from a dictionary."""
        return cls(
            id=data.get("id", "unknown"),
            priority=data.get("priority", "medium"),
            source_file=data.get("source_file", ""),
            line_range=data.get("line_range", [0, 0]),
            change_type=data.get("change_type", "modified"),
            description=data.get("description", ""),
            diff_excerpt=data.get("diff_excerpt", ""),
            missing_docs=data.get("missing_docs", []),
            outdated_docs=data.get("outdated_docs", []),
            suggested_updates=data.get("suggested_updates", []),
        )


@dataclass
class DriftReport:
    """Represents a complete drift detection report."""

    detected_at: str
    base_ref: str
    head_ref: str
    pr_number: int | None
    drift_items: list[DriftItem]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DriftReport:
        """Create a DriftReport from a dictionary."""
        return cls(
            detected_at=data.get("detected_at", ""),
            base_ref=data.get("base_ref", ""),
            head_ref=data.get("head_ref", ""),
            pr_number=data.get("pr_number"),
            drift_items=[DriftItem.from_dict(item) for item in data.get("drift_items", [])],
        )


@dataclass
class CreatedTask:
    """Represents a successfully created Linear task."""

    issue_id: str
    identifier: str
    title: str
    url: str


# =============================================================================
# Linear API Client
# =============================================================================


class LinearAPIError(Exception):
    """Raised when Linear API returns an error."""

    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


class LinearClient:
    """HTTP client for Linear GraphQL API."""

    def __init__(self, api_key: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        """Initialize the Linear API client.

        Args:
            api_key: Linear API key with write access
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self._label_cache: dict[str, str] = {}

    def _make_request(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a GraphQL request to Linear API with retry logic.

        Args:
            query: GraphQL query string
            variables: Optional query variables

        Returns:
            Response data dictionary

        Raises:
            LinearAPIError: If API returns errors after retries
            httpx.HTTPError: If network error after retries
        """
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        LINEAR_API_URL,
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()

                    if "errors" in result:
                        raise LinearAPIError(
                            f"GraphQL errors: {result['errors']}",
                            errors=result["errors"],
                        )

                    data: dict[str, Any] = result.get("data", {})
                    return data

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in (429, 500, 502, 503, 504):
                    # Retryable errors
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY * (attempt + 1))
                        continue
                raise

            except httpx.HTTPError as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise

        # Should not reach here, but just in case
        if last_error:
            raise last_error
        raise LinearAPIError("Request failed after retries")

    def search_issues(self, query: str) -> list[dict[str, Any]]:
        """Search for issues by text query.

        Args:
            query: Search query text

        Returns:
            List of matching issues
        """
        graphql_query = """
        query SearchIssues($query: String!) {
            issueSearch(query: $query, first: 50) {
                nodes {
                    id
                    identifier
                    title
                    description
                    url
                }
            }
        }
        """
        result = self._make_request(graphql_query, {"query": query})
        nodes: list[dict[str, Any]] = result.get("issueSearch", {}).get("nodes", [])
        return nodes

    def get_labels(self, team_id: str) -> dict[str, str]:
        """Get all labels for a team.

        Args:
            team_id: Team UUID

        Returns:
            Dictionary mapping label name to label ID
        """
        if self._label_cache:
            return self._label_cache

        graphql_query = """
        query GetLabels($teamId: String!) {
            team(id: $teamId) {
                labels {
                    nodes {
                        id
                        name
                    }
                }
            }
        }
        """
        result = self._make_request(graphql_query, {"teamId": team_id})
        labels = result.get("team", {}).get("labels", {}).get("nodes", [])

        self._label_cache = {label["name"]: label["id"] for label in labels}
        return self._label_cache

    def create_issue(
        self,
        title: str,
        team_id: str,
        description: str,
        priority: int,
        state_id: str,
        label_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new issue in Linear.

        Args:
            title: Issue title
            team_id: Team UUID
            description: Issue description (markdown)
            priority: Priority level (0-4)
            state_id: Workflow state UUID
            label_ids: Optional list of label UUIDs to apply

        Returns:
            Created issue data including id, identifier, title, url
        """
        graphql_mutation = """
        mutation CreateIssue($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    identifier
                    title
                    url
                }
            }
        }
        """

        input_data: dict[str, Any] = {
            "title": title,
            "teamId": team_id,
            "description": description,
            "priority": priority,
            "stateId": state_id,
        }

        if label_ids:
            input_data["labelIds"] = label_ids

        result = self._make_request(graphql_mutation, {"input": input_data})
        issue_create = result.get("issueCreate", {})

        if not issue_create.get("success"):
            raise LinearAPIError("Failed to create issue")

        issue: dict[str, Any] = issue_create.get("issue", {})
        return issue


# =============================================================================
# Task Creation Logic
# =============================================================================


def generate_drift_id(item: DriftItem) -> str:
    """Generate a deterministic ID for deduplication.

    Creates a hash from source file, drift type, and description to ensure
    the same drift item always gets the same ID.

    Args:
        item: Drift item to generate ID for

    Returns:
        12-character hexadecimal hash
    """
    key = f"{item.source_file}:{item.id}:{item.description}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def task_already_exists(client: LinearClient, drift_id: str) -> bool:
    """Check if a task with this drift ID already exists.

    Searches Linear for issues containing the drift-id marker in their
    description.

    Args:
        client: Linear API client
        drift_id: Drift ID to search for

    Returns:
        True if task already exists, False otherwise
    """
    search_query = f"drift-id:{drift_id}"
    existing = client.search_issues(search_query)
    return len(existing) > 0


def create_docs_checklist(item: DriftItem) -> str:
    """Create the documentation impact checklist.

    Args:
        item: Drift item

    Returns:
        Markdown checklist of documentation files to update
    """
    lines = []

    if item.missing_docs:
        lines.append("**Missing documentation:**")
        for doc in item.missing_docs:
            lines.append(f"- [ ] Create `{doc}`")
        lines.append("")

    if item.outdated_docs:
        lines.append("**Outdated documentation:**")
        for doc in item.outdated_docs:
            lines.append(f"- [ ] Update `{doc}`")
        lines.append("")

    if not lines:
        lines.append("- [ ] Review and update relevant documentation")

    return "\n".join(lines)


def create_suggestions(item: DriftItem) -> str:
    """Create the suggested updates section.

    Args:
        item: Drift item

    Returns:
        Markdown list of suggested updates
    """
    if not item.suggested_updates:
        return "- Review implementation and document key behaviors"

    return "\n".join(f"- {update}" for update in item.suggested_updates)


def create_task_description(item: DriftItem, report: DriftReport) -> str:
    """Create the full task description from template.

    Args:
        item: Drift item to create description for
        report: Full drift report for context

    Returns:
        Markdown formatted task description
    """
    # Format line range
    line_info = ""
    if item.line_range and len(item.line_range) == 2:
        line_start, line_end = item.line_range
        line_info = f":{line_start}-{line_end}"

    # Format PR reference
    pr_ref = f"#{report.pr_number}" if report.pr_number else "N/A"

    # Build description from template
    description = f"""## Documentation Update Required

**Trigger:** {item.id}
**Detected:** {report.detected_at} in commit `{report.head_ref}`
**PR:** {pr_ref}

### What Changed

```diff
{item.diff_excerpt}
```

**Source:** `{item.source_file}{line_info}`

### Documentation Impact

{create_docs_checklist(item)}

### Suggested Updates

{create_suggestions(item)}

### Acceptance Criteria

- [ ] Documentation accurately reflects implementation
- [ ] Links from hub documents work
- [ ] AGENTS.md updated if new file added
- [ ] `./scripts/validate.sh` passes

---

_Auto-generated by docs-drift detection_"""

    return description


def resolve_label_ids(client: LinearClient, label_names: list[str]) -> list[str]:
    """Resolve label names to IDs, creating labels if needed.

    Args:
        client: Linear API client
        label_names: List of label names to resolve

    Returns:
        List of label IDs
    """
    labels = client.get_labels(TEAM_ID)
    label_ids = []

    for name in label_names:
        if name in labels:
            label_ids.append(labels[name])
        else:
            # Label doesn't exist - skip it rather than failing
            print(f"Warning: Label '{name}' not found in Linear, skipping", file=sys.stderr)

    return label_ids


def create_linear_task(
    client: LinearClient,
    item: DriftItem,
    report: DriftReport,
    label_ids: list[str],
) -> CreatedTask | None:
    """Create a Linear task for a drift item.

    Args:
        client: Linear API client
        item: Drift item to create task for
        report: Full drift report for context
        label_ids: Label IDs to apply

    Returns:
        CreatedTask if successful, None if skipped (duplicate)
    """
    drift_id = generate_drift_id(item)

    # Check for duplicates
    if task_already_exists(client, drift_id):
        print(f"Skipping duplicate: {item.description} (drift-id:{drift_id})")
        return None

    # Create task title
    title = f"docs: {item.description}"

    # Create description with drift ID for deduplication
    description = create_task_description(item, report)
    description += f"\n\n`drift-id:{drift_id}`"

    # Create the issue
    priority = PRIORITY_MAP.get(item.priority, 3)  # Default to medium

    issue = client.create_issue(
        title=title,
        team_id=TEAM_ID,
        description=description,
        priority=priority,
        state_id=BACKLOG_STATE_ID,
        label_ids=label_ids if label_ids else None,
    )

    return CreatedTask(
        issue_id=issue["id"],
        identifier=issue["identifier"],
        title=title,
        url=issue["url"],
    )


def process_drift_report(report: DriftReport, api_key: str) -> list[CreatedTask]:
    """Process a drift report and create Linear tasks.

    Args:
        report: Drift report to process
        api_key: Linear API key

    Returns:
        List of created tasks
    """
    client = LinearClient(api_key)
    created_tasks: list[CreatedTask] = []

    # Resolve labels once
    label_ids = resolve_label_ids(client, TASK_LABELS)

    for item in report.drift_items:
        try:
            task = create_linear_task(client, item, report, label_ids)
            if task:
                created_tasks.append(task)
                print(f"Created: {task.identifier} - {task.title}")
                print(f"  URL: {task.url}")
        except LinearAPIError as e:
            print(f"Error creating task for '{item.description}': {e}", file=sys.stderr)
        except httpx.HTTPError as e:
            print(f"Network error creating task for '{item.description}': {e}", file=sys.stderr)

    return created_tasks


# =============================================================================
# Input Handling
# =============================================================================


def read_drift_report(file_path: str | None) -> DriftReport:
    """Read drift report from file or stdin.

    Args:
        file_path: Path to drift report file, or None to read from stdin

    Returns:
        Parsed drift report

    Raises:
        json.JSONDecodeError: If JSON is invalid
        KeyError: If required fields are missing
    """
    if file_path:
        # nosemgrep: path-traversal-open - file_path is from CLI arg, user-controlled by design
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    return DriftReport.from_dict(data)


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> int:
    """Main entry point.

    Returns:
        0 on success, 1 on error
    """
    # Check for API key
    api_key = os.environ.get("LINEAR_API_KEY")
    if not api_key:
        # pragma: allowlist secret (example API key format in help text)
        print(
            "Error: LINEAR_API_KEY environment variable is not set.\n"
            "\n"
            "To obtain an API key:\n"
            "  1. Go to https://linear.app/settings/api\n"
            "  2. Create a new Personal API Key\n"
            "  3. Set it in your environment: export LINEAR_API_KEY='...'\n"
            "\n"
            "For CI/CD, add LINEAR_API_KEY to your repository secrets.",
            file=sys.stderr,
        )
        return 1

    # Determine input source
    file_path: str | None = None
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            return 1

    # Read and process the report
    try:
        report = read_drift_report(file_path)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in drift report: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Check for empty report
    if not report.drift_items:
        print("No drift items found in report. No tasks to create.")
        return 0

    # Process the report
    print(f"Processing drift report with {len(report.drift_items)} items...")
    print(f"  Base: {report.base_ref}")
    print(f"  Head: {report.head_ref}")
    if report.pr_number:
        print(f"  PR: #{report.pr_number}")
    print()

    created_tasks = process_drift_report(report, api_key)

    # Summary
    print()
    print(
        f"Summary: Created {len(created_tasks)} tasks, "
        f"skipped {len(report.drift_items) - len(created_tasks)} duplicates"
    )

    # Output task URLs for CI integration
    if created_tasks:
        print()
        print("Created task URLs:")
        for task in created_tasks:
            print(f"  {task.url}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
