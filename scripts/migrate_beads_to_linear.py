#!/usr/bin/env python3
"""
Migrate beads issues to Linear.

Usage:
    export LINEAR_API_KEY="lin_api_..."
    python scripts/migrate_beads_to_linear.py

Or with explicit arguments:
    python scripts/migrate_beads_to_linear.py --api-key "lin_api_..." --team-id "..."
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

# Linear API endpoint
LINEAR_API_URL = "https://api.linear.app/graphql"

# Team configuration
DEFAULT_TEAM_ID = "998946a2-aa75-491b-a39d-189660131392"

# Priority mapping: beads priority (1-4) -> Linear priority (1=urgent, 2=high, 3=medium, 4=low, 0=none)
# Beads: P0=highest, P4=lowest (stored as 0-4)
# Linear: 1=urgent, 2=high, 3=medium, 4=low, 0=no priority
PRIORITY_MAP = {
    0: 1,  # P0 -> Urgent
    1: 2,  # P1 -> High
    2: 3,  # P2 -> Medium
    3: 4,  # P3 -> Low
    4: 0,  # P4 -> No priority
}

# State mapping based on Linear's workflow states
STATE_MAP = {
    "open": "50ef9730-7d5e-43d6-b5e0-d7cac07af58f",  # Todo
    "in_progress": "b88c8ae2-2545-4c1b-b83a-bf2dde2c03e7",  # In Progress
    "closed": "38267c1e-4458-4875-aa66-4b56381786e9",  # Done
}

# Issue type to label mapping
TYPE_LABEL_MAP = {
    "bug": "Bug",
    "feature": "Feature",
    "task": None,  # No special label for tasks
    "epic": None,  # Epics are handled via parent relationship
}


class LinearClient:
    """Simple Linear GraphQL API client with retry logic (NEM-1087)."""

    def __init__(
        self,
        api_key: str,
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
    ):
        """Initialize Linear client.

        Args:
            api_key: Linear API key for authentication
            max_retries: Maximum retry attempts for transient failures (default: 3)
            retry_base_delay: Base delay in seconds for exponential backoff (default: 1.0)
        """
        self.api_key = api_key
        self.client = httpx.Client(timeout=30.0)
        self.label_cache: dict[str, str] = {}  # name -> id
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay

    def _handle_retry(
        self, error_type: str, attempt: int, delay: float | None = None
    ) -> tuple[bool, float]:
        """Handle retry logic and return whether to continue retrying.

        Args:
            error_type: Description of the error type for logging
            attempt: Current attempt number (0-indexed)
            delay: Optional explicit delay (e.g., from Retry-After header)

        Returns:
            Tuple of (should_continue, delay_seconds)
        """
        actual_delay = delay if delay is not None else self.retry_base_delay * (2**attempt)
        if attempt < self.max_retries - 1:
            print(
                f"  {error_type}, retrying in {actual_delay:.1f}s "
                f"(attempt {attempt + 1}/{self.max_retries})..."
            )
            time.sleep(actual_delay)
            return True, actual_delay
        print(f"  {error_type} after {self.max_retries} attempts")
        return False, actual_delay

    def _request(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL request with retry logic.

        Implements exponential backoff retry for transient failures (NEM-1087):
        - Connection errors trigger retry
        - 429 rate limit responses trigger retry (respects Retry-After header)
        - 5xx server errors trigger retry
        - GraphQL errors are NOT retried (application-level errors)

        Args:
            query: GraphQL query string
            variables: Optional query variables

        Returns:
            GraphQL response data

        Raises:
            Exception: If request fails after all retries
        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = self.client.post(
                    LINEAR_API_URL,
                    json={"query": query, "variables": variables or {}},
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": self.api_key,
                    },
                )
                response.raise_for_status()
                data = response.json()

                # GraphQL errors are not retryable - they're application errors
                if "errors" in data:
                    raise Exception(f"GraphQL errors: {data['errors']}")

                result: dict[str, Any] = data["data"]
                return result

            except httpx.HTTPStatusError as e:
                last_exception = e
                status_code = e.response.status_code

                # Handle rate limiting (429)
                if status_code == 429:
                    retry_after = e.response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else None
                    should_continue, _ = self._handle_retry(
                        f"Rate limited ({status_code})", attempt, delay
                    )
                    if should_continue:
                        continue
                    raise

                # Retry on server errors (5xx)
                if status_code >= 500:
                    should_continue, _ = self._handle_retry(
                        f"Server error ({status_code})", attempt
                    )
                    if should_continue:
                        continue
                    raise

                # Don't retry on client errors (4xx except 429)
                raise

            except httpx.ConnectError as e:
                last_exception = e
                should_continue, _ = self._handle_retry("Connection error", attempt)
                if should_continue:
                    continue
                raise

            except httpx.TimeoutException as e:
                last_exception = e
                should_continue, _ = self._handle_retry("Timeout", attempt)
                if should_continue:
                    continue
                raise

        # Should never reach here, but just in case
        if last_exception:
            raise last_exception
        raise Exception("Request failed after all retries")

    def get_labels(self, team_id: str) -> dict[str, str]:
        """Get existing labels for a team."""
        query: str = """
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
        data = self._request(query, {"teamId": team_id})
        return {label["name"]: label["id"] for label in data["team"]["labels"]["nodes"]}

    def create_label(self, team_id: str, name: str, color: str = "#6B7280") -> str | None:
        """Create a new label and return its ID. Returns None if duplicate."""
        query = """
        mutation CreateLabel($teamId: String!, $name: String!, $color: String!) {
            issueLabelCreate(input: {teamId: $teamId, name: $name, color: $color}) {
                success
                issueLabel {
                    id
                    name
                }
            }
        }
        """
        try:
            data = self._request(query, {"teamId": team_id, "name": name, "color": color})
            if not data["issueLabelCreate"]["success"]:
                return None
            label_id: str = data["issueLabelCreate"]["issueLabel"]["id"]
            return label_id
        except Exception as e:
            error_str = str(e).lower()
            if "duplicate" in error_str:
                return None  # Will be handled by looking up existing labels
            if "reserved" in error_str:
                # Try with a prefix for reserved names
                return self.create_label(team_id, f"beads-{name}", color)
            raise

    def create_issue(
        self,
        team_id: str,
        title: str,
        description: str | None = None,
        priority: int = 0,
        state_id: str | None = None,
        label_ids: list[str] | None = None,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new issue."""
        query = """
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
            "teamId": team_id,
            "title": title,
            "priority": priority,
        }
        if description:
            input_data["description"] = description
        if state_id:
            input_data["stateId"] = state_id
        if label_ids:
            input_data["labelIds"] = label_ids
        if parent_id:
            input_data["parentId"] = parent_id

        data = self._request(query, {"input": input_data})
        if not data["issueCreate"]["success"]:
            raise Exception(f"Failed to create issue: {title}")
        issue: dict[str, Any] = data["issueCreate"]["issue"]
        return issue

    def ensure_labels(self, team_id: str, labels: set[str]) -> dict[str, str]:
        """Ensure all labels exist, creating missing ones."""
        existing = self.get_labels(team_id)
        self.label_cache.update(existing)

        # Build case-insensitive lookup
        existing_lower = {name.lower(): name for name in self.label_cache}

        # Color palette for new labels
        colors = [
            "#EF4444",
            "#F97316",
            "#F59E0B",
            "#EAB308",
            "#84CC16",
            "#22C55E",
            "#10B981",
            "#14B8A6",
            "#06B6D4",
            "#0EA5E9",
            "#3B82F6",
            "#6366F1",
            "#8B5CF6",
            "#A855F7",
            "#D946EF",
            "#EC4899",
            "#F43F5E",
        ]

        for i, label in enumerate(sorted(labels)):
            # Check case-insensitive match
            if label.lower() in existing_lower:
                # Map to the existing label's case
                existing_name = existing_lower[label.lower()]
                if label not in self.label_cache:
                    self.label_cache[label] = self.label_cache[existing_name]
                continue

            if label not in self.label_cache:
                color = colors[i % len(colors)]
                print(f"  Creating label: {label}")
                label_id = self.create_label(team_id, label, color)
                if label_id:
                    self.label_cache[label] = label_id
                    existing_lower[label.lower()] = label
                    # Check if it was renamed (prefixed)
                    existing = self.get_labels(team_id)
                    if f"beads-{label}" in existing:
                        self.label_cache[label] = existing[f"beads-{label}"]
                        print(f"    (renamed to beads-{label})")
                else:
                    # Refresh cache if creation failed (duplicate)
                    print(f"  Label '{label}' already exists, refreshing cache...")
                    existing = self.get_labels(team_id)
                    self.label_cache.update(existing)
                    existing_lower = {name.lower(): name for name in self.label_cache}
                    if label.lower() in existing_lower:
                        existing_name = existing_lower[label.lower()]
                        self.label_cache[label] = self.label_cache[existing_name]
                time.sleep(0.1)  # Rate limiting

        return self.label_cache


def load_beads(jsonl_path: Path) -> list[dict]:
    """Load beads from JSONL export."""
    beads = []
    with open(jsonl_path) as f:
        for line in f:
            if line.strip():
                beads.append(json.loads(line))
    return beads


def get_parent_id(bead: dict[str, Any]) -> str | None:
    """Extract parent bead ID from dependencies."""
    deps: list[dict[str, Any]] = bead.get("dependencies", [])
    for dep in deps:
        if dep.get("type") == "parent-child":
            # The depends_on_id is the parent
            parent_id: str | None = dep.get("depends_on_id")
            if parent_id and parent_id != bead["id"]:
                return parent_id
    return None


def build_description(bead: dict) -> str:
    """Build Linear description from bead data."""
    parts = []

    # Original description
    if bead.get("description"):
        parts.append(bead["description"])

    # Metadata footer
    parts.append("\n---")
    parts.append(f"*Migrated from beads: `{bead['id']}`*")

    if bead.get("created_at"):
        parts.append(f"*Original created: {bead['created_at'][:10]}*")

    if bead.get("closed_at"):
        parts.append(f"*Original closed: {bead['closed_at'][:10]}*")

    return "\n".join(parts)


def collect_labels(beads: list[dict]) -> set[str]:
    """Collect all unique labels from beads."""
    all_labels: set[str] = set()
    for bead in beads:
        all_labels.update(bead.get("labels", []))
        issue_type = bead.get("issue_type", "task")
        type_label = TYPE_LABEL_MAP.get(issue_type)
        if type_label:
            all_labels.add(type_label)
    return all_labels


def get_label_ids(bead: dict, label_map: dict[str, str]) -> list[str]:
    """Get Linear label IDs for a bead."""
    label_ids = [label_map[label] for label in bead.get("labels", []) if label in label_map]
    issue_type = bead.get("issue_type", "task")
    type_label = TYPE_LABEL_MAP.get(issue_type)
    if type_label and type_label in label_map:
        label_ids.append(label_map[type_label])
    return label_ids


def migrate_single_issue(
    client: LinearClient,
    team_id: str,
    bead: dict,
    label_map: dict[str, str],
    parent_map: dict[str, str | None],
    created: dict[str, str],
) -> dict:
    """Migrate a single bead to Linear and return the created issue."""
    bead_id = bead["id"]
    status = bead.get("status", "open")
    state_id = STATE_MAP.get(status, STATE_MAP["open"])
    priority = PRIORITY_MAP.get(bead.get("priority", 2), 3)
    label_ids = get_label_ids(bead, label_map)
    parent_bead_id = parent_map.get(bead_id)
    parent_linear_id = created.get(parent_bead_id) if parent_bead_id else None

    return client.create_issue(
        team_id=team_id,
        title=bead["title"],
        description=build_description(bead),
        priority=priority,
        state_id=state_id,
        label_ids=label_ids if label_ids else None,
        parent_id=parent_linear_id,
    )


def migrate(
    api_key: str,
    team_id: str,
    jsonl_path: Path,
    dry_run: bool = False,
    limit: int | None = None,
    resume: bool = False,
) -> None:
    """Run the migration."""
    print(f"Loading beads from {jsonl_path}...")
    beads = load_beads(jsonl_path)
    print(f"Loaded {len(beads)} beads")

    # Load existing mapping if resuming
    mapping_path = jsonl_path.parent / "beads_to_linear_mapping.json"
    existing_mapping: dict[str, str] = {}
    if resume and mapping_path.exists():
        with open(mapping_path) as f:
            existing_mapping = json.load(f)
        print(f"Resuming: {len(existing_mapping)} issues already migrated")

    if limit:
        beads = beads[:limit]
        print(f"Limited to {limit} beads for testing")

    all_labels = collect_labels(beads)
    print(f"\nFound {len(all_labels)} unique labels: {sorted(all_labels)}")

    if dry_run:
        print("\n[DRY RUN] Would create these issues:")
        for bead in beads[:10]:
            print(f"  - {bead['id']}: {bead['title'][:60]}...")
        if len(beads) > 10:
            print(f"  ... and {len(beads) - 10} more")
        return

    client = LinearClient(api_key)
    print("\nEnsuring labels exist...")
    label_map = client.ensure_labels(team_id, all_labels)
    print(f"Label cache: {len(label_map)} labels ready")

    # Build parent-child mapping and sort (parents first)
    parent_map: dict[str, str | None] = {bead["id"]: get_parent_id(bead) for bead in beads}
    beads_sorted = sorted(
        beads,
        key=lambda b: (1 if parent_map.get(b["id"]) else 0, len(b["id"]), b["id"]),
    )

    created: dict[str, str] = dict(existing_mapping)
    failed: list[tuple[str, str]] = []
    skipped = 0

    print(f"\nMigrating {len(beads_sorted)} issues...")
    for i, bead in enumerate(beads_sorted):
        bead_id = bead["id"]
        if bead_id in created:
            skipped += 1
            continue

        try:
            issue = migrate_single_issue(client, team_id, bead, label_map, parent_map, created)
            created[bead_id] = issue["id"]
            print(
                f"[{i + 1}/{len(beads_sorted)}] Created {issue['identifier']}: {bead['title'][:50]}..."
            )
            time.sleep(0.15)
        except Exception as e:
            failed.append((bead_id, str(e)))
            print(f"[{i + 1}/{len(beads_sorted)}] FAILED {bead_id}: {e}")

    # Summary
    print(f"\n{'=' * 60}")
    print("Migration complete!")
    print(f"  Created: {len(created) - len(existing_mapping)} new issues")
    print(f"  Skipped: {skipped} already migrated")
    print(f"  Failed: {len(failed)} issues")
    print(f"  Total in Linear: {len(created)} issues")

    if failed:
        print("\nFailed issues:")
        for bead_id, error in failed:
            print(f"  - {bead_id}: {error}")

    # Save mapping for reference
    mapping_path = jsonl_path.parent / "beads_to_linear_mapping.json"
    with open(mapping_path, "w") as f:
        json.dump(created, f, indent=2)
    print(f"\nMapping saved to: {mapping_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate beads to Linear")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("LINEAR_API_KEY"),
        help="Linear API key (or set LINEAR_API_KEY env var)",
    )
    parser.add_argument(
        "--team-id",
        default=os.environ.get("LINEAR_TEAM_ID", DEFAULT_TEAM_ID),
        help="Linear team ID",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to beads JSONL export (run 'bd export > beads.jsonl' first)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without creating issues",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of issues to migrate (for testing)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previous migration (skip already migrated issues)",
    )

    args = parser.parse_args()

    if not args.api_key:
        print("Error: LINEAR_API_KEY not set. Use --api-key or set the environment variable.")
        sys.exit(1)

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        print("Run 'bd export > /tmp/beads_export.jsonl' first")
        sys.exit(1)

    migrate(
        api_key=args.api_key,
        team_id=args.team_id,
        jsonl_path=args.input,
        dry_run=args.dry_run,
        limit=args.limit,
        resume=args.resume,
    )


if __name__ == "__main__":
    main()
