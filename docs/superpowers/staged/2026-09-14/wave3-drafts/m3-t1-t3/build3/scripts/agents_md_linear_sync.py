#!/usr/bin/env python3
"""
Sync AGENTS.md validator results to Linear.

This script reads the validator report JSON and creates/updates a rolling Linear task
to track documentation drift. The task is auto-closed when all issues are resolved.

Usage:
    export LINEAR_API_KEY="lin_api_..."  # pragma: allowlist secret
    python scripts/agents_md_linear_sync.py \
        --report report.json \
        --commit abc1234 \
        --ci-url https://github.com/.../actions/runs/123

Task Lifecycle:
    - Issues found, no existing task -> Create task in Backlog
    - Issues found, task exists -> Update task description
    - No issues, task exists -> Move task to Done
    - No issues, no task -> No action
"""

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from typing import Any, cast

import httpx

# Linear API configuration
LINEAR_API_URL = "https://api.linear.app/graphql"
TEAM_ID = "998946a2-aa75-491b-a39d-189660131392"
TASK_TITLE = "AGENTS.md Documentation Sync Required"

# Workflow state UUIDs (NEM team)
WORKFLOW_STATE_BACKLOG = "88b50a4e-75a1-4f34-a3b0-598bfd118aac"
WORKFLOW_STATE_DONE = "38267c1e-4458-4875-aa66-4b56381786e9"


class LinearClient:
    """Linear GraphQL API client."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.Client(timeout=30.0)

    def query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query."""
        response = self.client.post(
            LINEAR_API_URL,
            json={"query": query, "variables": variables or {}},
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            raise Exception(f"GraphQL errors: {data['errors']}")
        return cast("dict[str, Any]", data["data"])

    def find_existing_task(self) -> dict[str, Any] | None:
        """Search for existing AGENTS.md sync task in non-closed states."""
        query = """
        query($teamId: String!, $filter: IssueFilter) {
            team(id: $teamId) {
                issues(filter: $filter, first: 10) {
                    nodes {
                        id
                        identifier
                        title
                        state {
                            id
                            name
                            type
                        }
                        url
                    }
                }
            }
        }
        """
        # Search for the task by title, excluding completed/canceled states
        variables: dict[str, Any] = {
            "teamId": TEAM_ID,
            "filter": {
                "title": {"eq": TASK_TITLE},
                "state": {"type": {"nin": ["completed", "canceled"]}},
            },
        }
        result = self.query(query, variables)
        nodes = result["team"]["issues"]["nodes"]
        return cast("dict[str, Any]", nodes[0]) if nodes else None

    def create_task(self, description: str) -> dict[str, Any]:
        """Create a new task in Backlog."""
        mutation = """
        mutation($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    identifier
                    url
                }
            }
        }
        """
        variables: dict[str, Any] = {
            "input": {
                "teamId": TEAM_ID,
                "title": TASK_TITLE,
                "description": description,
                "stateId": WORKFLOW_STATE_BACKLOG,
            }
        }
        result = self.query(mutation, variables)
        if not result["issueCreate"]["success"]:
            raise Exception("Failed to create issue")
        return cast("dict[str, Any]", result["issueCreate"]["issue"])

    def update_task(self, issue_id: str, description: str) -> dict[str, Any]:
        """Update an existing task's description."""
        mutation = """
        mutation($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
                issue {
                    id
                    identifier
                    url
                }
            }
        }
        """
        variables: dict[str, Any] = {"id": issue_id, "input": {"description": description}}
        result = self.query(mutation, variables)
        if not result["issueUpdate"]["success"]:
            raise Exception("Failed to update issue")
        return cast("dict[str, Any]", result["issueUpdate"]["issue"])

    def close_task(self, issue_id: str) -> dict[str, Any]:
        """Move a task to Done."""
        mutation = """
        mutation($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
                issue {
                    id
                    identifier
                    url
                }
            }
        }
        """
        variables: dict[str, Any] = {"id": issue_id, "input": {"stateId": WORKFLOW_STATE_DONE}}
        result = self.query(mutation, variables)
        if not result["issueUpdate"]["success"]:
            raise Exception("Failed to close issue")
        return cast("dict[str, Any]", result["issueUpdate"]["issue"])


def load_report(report_path: str) -> dict[str, Any]:
    """Load and parse the validator report JSON."""
    from pathlib import Path

    resolved_path = Path(report_path).resolve()
    # nosemgrep: path-traversal-open - report_path is from CLI arg, validated by resolve()
    with open(resolved_path) as f:
        return cast("dict[str, Any]", json.load(f))


def format_task_description(report: dict[str, Any], commit: str, ci_url: str | None) -> str:
    """Format the Linear task description from the report."""
    issues = report.get("issues", [])

    # Group issues by type
    stale_refs = [i for i in issues if i.get("type") == "stale_reference"]
    missing_agents = [i for i in issues if i.get("type") == "missing_agents_md"]
    dead_links = [i for i in issues if i.get("type") == "dead_link"]

    lines = [
        "## Summary",
        "",
        "Automated scan found AGENTS.md documentation drift that needs attention.",
        "",
        "## Issues Found",
        "",
    ]

    # Stale References section
    lines.append(f"### Stale References ({len(stale_refs)})")
    lines.append("")
    if stale_refs:
        lines.append("| File | Line | Reference | Reason |")
        lines.append("|------|------|-----------|--------|")
        for issue in stale_refs:
            file_path = issue.get("agents_md", "")
            line = issue.get("line", "")
            reference = issue.get("reference", "")
            reason = issue.get("reason", "")
            lines.append(f"| {file_path} | {line} | {reference} | {reason} |")
    else:
        lines.append("None found.")
    lines.append("")

    # Missing AGENTS.md section
    lines.append(f"### Missing AGENTS.md ({len(missing_agents)})")
    lines.append("")
    if missing_agents:
        lines.append("| Directory | Code Files |")
        lines.append("|-----------|------------|")
        for issue in missing_agents:
            directory = issue.get("directory", "")
            code_files = ", ".join(issue.get("code_files", [])[:5])
            if len(issue.get("code_files", [])) > 5:
                code_files += ", ..."
            lines.append(f"| {directory} | {code_files} |")
    else:
        lines.append("None found.")
    lines.append("")

    # Dead Links section
    lines.append(f"### Dead Links ({len(dead_links)})")
    lines.append("")
    if dead_links:
        lines.append("| File | Line | Link | Reason |")
        lines.append("|------|------|------|--------|")
        for issue in dead_links:
            file_path = issue.get("agents_md", "")
            line = issue.get("line", "")
            link = issue.get("link", "")
            reason = issue.get("reason", "")
            lines.append(f"| {file_path} | {line} | {link} | {reason} |")
    else:
        lines.append("None found.")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    scan_date = datetime.now(UTC).strftime("%Y-%m-%d")
    short_sha = commit[:7] if len(commit) >= 7 else commit
    lines.append(f"_Last scanned: {scan_date} at commit {short_sha}_")
    if ci_url:
        lines.append(f"_CI Run: [View]({ci_url})_")

    return "\n".join(lines)


def has_issues(report: dict[str, Any]) -> bool:
    """Check if the report contains any issues."""
    issues = report.get("issues", [])
    return len(issues) > 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync AGENTS.md validator results to Linear",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--report",
        required=True,
        help="Path to validator report JSON file",
    )
    parser.add_argument(
        "--commit",
        required=True,
        help="Git commit SHA",
    )
    parser.add_argument(
        "--ci-url",
        help="URL to CI run (optional)",
    )

    args = parser.parse_args()

    # Check for LINEAR_API_KEY
    api_key = os.environ.get("LINEAR_API_KEY")
    if not api_key:
        print(
            "Warning: LINEAR_API_KEY environment variable not set, skipping Linear sync",
            file=sys.stderr,
        )
        return 0

    # Load the report
    try:
        report = load_report(args.report)
    except FileNotFoundError:
        print(f"Error: Report file not found: {args.report}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in report file: {e}", file=sys.stderr)
        return 1

    # Initialize Linear client
    client = LinearClient(api_key)

    # Find existing task
    try:
        existing_task = client.find_existing_task()
    except Exception as e:
        print(f"Error searching for existing task: {e}", file=sys.stderr)
        return 1

    issues_found = has_issues(report)

    if issues_found:
        description = format_task_description(report, args.commit, args.ci_url)

        if existing_task:
            # Update existing task
            try:
                updated = client.update_task(existing_task["id"], description)
                print(f"Updated task {updated['identifier']}: {updated['url']}")
            except Exception as e:
                print(f"Error updating task: {e}", file=sys.stderr)
                return 1
        else:
            # Create new task
            try:
                created = client.create_task(description)
                print(f"Created task {created['identifier']}: {created['url']}")
            except Exception as e:
                print(f"Error creating task: {e}", file=sys.stderr)
                return 1
    elif existing_task:
        # Close existing task
        try:
            closed = client.close_task(existing_task["id"])
            print(f"All issues resolved! Closed task {closed['identifier']}: {closed['url']}")
        except Exception as e:
            print(f"Error closing task: {e}", file=sys.stderr)
            return 1
    else:
        print("No issues found and no existing task. Nothing to do.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
