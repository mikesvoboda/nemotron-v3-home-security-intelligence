#!/usr/bin/env python3
"""
Audit Linear-GitHub issue sync status.

This script compares GitHub issues with Linear tasks to identify:
1. GitHub issues that have matching Linear tasks (by title similarity)
2. GitHub issues that should be closed (Linear task is Done)
3. Orphaned GitHub issues with no Linear counterpart

Usage:
    export LINEAR_API_KEY="lin_api_..."  # pragma: allowlist secret
    export GITHUB_TOKEN="ghp_..."  # or use gh auth
    python scripts/audit-linear-github-sync.py

Options:
    --close-matched     Actually close GitHub issues that match Done Linear tasks
    --no-dry-run       Actually make changes (default is dry-run)
    --min-similarity   Minimum title similarity score (0-100, default: 80)
    --limit            Max GitHub issues to process (default: all)
    --batch-size       Number of issues to close per batch (default: 100)
    --batch-delay      Seconds to wait between batches (default: 60)
    --rate-limit       Seconds between individual API calls (default: 1)
    --output           Output format: table, json, csv (default: table)

Examples:
    # Audit only (dry run)
    python scripts/audit-linear-github-sync.py

    # Close first 100 matched issues
    python scripts/audit-linear-github-sync.py --close-matched --no-dry-run --limit 100

    # Close all in batches of 100 with 60s pause between batches
    python scripts/audit-linear-github-sync.py --close-matched --no-dry-run --batch-size 100
"""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

import httpx

# Linear API endpoint
LINEAR_API_URL = "https://api.linear.app/graphql"

# Team configuration
DEFAULT_TEAM_ID = "998946a2-aa75-491b-a39d-189660131392"


@dataclass
class GitHubIssue:
    """GitHub issue data."""

    number: int
    title: str
    state: str
    body: str | None = None
    labels: list[str] = field(default_factory=list)
    created_at: str = ""
    url: str = ""


@dataclass
class LinearTask:
    """Linear task data."""

    id: str
    identifier: str
    title: str
    status: str
    url: str
    completed_at: str | None = None


@dataclass
class MatchResult:
    """Result of matching a GitHub issue to Linear tasks."""

    github_issue: GitHubIssue
    linear_task: LinearTask | None
    similarity: float
    action: str  # "close", "keep_open", "no_match", "already_closed"


class LinearClient:
    """Linear GraphQL API client."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.Client(timeout=30.0)

    def query(self, query: str, variables: dict[str, Any] | None = None) -> dict:
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
        return data["data"]

    def get_all_issues(self, team_id: str) -> list[LinearTask]:
        """Fetch all issues from Linear for a team."""
        query = """
        query($teamId: String!, $after: String) {
            team(id: $teamId) {
                issues(first: 100, after: $after) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    nodes {
                        id
                        identifier
                        title
                        state {
                            name
                            type
                        }
                        url
                        completedAt
                    }
                }
            }
        }
        """
        all_issues = []
        after = None

        while True:
            result = self.query(query, {"teamId": team_id, "after": after})
            issues_data = result["team"]["issues"]

            for node in issues_data["nodes"]:
                all_issues.append(
                    LinearTask(
                        id=node["id"],
                        identifier=node["identifier"],
                        title=node["title"],
                        status=node["state"]["name"],
                        url=node["url"],
                        completed_at=node.get("completedAt"),
                    )
                )

            if not issues_data["pageInfo"]["hasNextPage"]:
                break
            after = issues_data["pageInfo"]["endCursor"]

        return all_issues


def get_github_issues(limit: int | None = None) -> list[GitHubIssue]:
    """Fetch all open GitHub issues using gh CLI."""
    cmd = [
        "gh",
        "issue",
        "list",
        "--state",
        "open",
        "--json",
        "number,title,state,body,labels,createdAt,url",
    ]
    if limit:
        cmd.extend(["--limit", str(limit)])
    else:
        cmd.extend(["--limit", "1000"])  # Get all

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)  # noqa: S603
    issues_data = json.loads(result.stdout)

    return [
        GitHubIssue(
            number=issue["number"],
            title=issue["title"],
            state=issue["state"],
            body=issue.get("body"),
            labels=[label.get("name", "") for label in issue.get("labels", [])],
            created_at=issue.get("createdAt", ""),
            url=issue.get("url", ""),
        )
        for issue in issues_data
    ]


def close_github_issue(issue_number: int, reason: str, rate_limit: float = 1.0) -> bool:
    """Close a GitHub issue with a comment.

    Args:
        issue_number: GitHub issue number to close
        reason: Reason for closing (will be added as comment)
        rate_limit: Seconds to wait after API calls to avoid rate limiting

    Returns:
        True if successful, False otherwise
    """
    try:
        # Add comment explaining the closure
        comment = f"Closing: {reason}\n\nThis issue has been migrated to Linear for tracking."
        subprocess.run(  # noqa: S603
            ["gh", "issue", "comment", str(issue_number), "--body", comment],  # noqa: S607
            capture_output=True,
            check=True,
        )
        time.sleep(rate_limit / 2)  # Small delay between comment and close

        # Close the issue
        subprocess.run(  # noqa: S603
            ["gh", "issue", "close", str(issue_number), "--reason", "completed"],  # noqa: S607
            capture_output=True,
            check=True,
        )
        time.sleep(rate_limit)  # Rate limit delay after close
        return True
    except subprocess.CalledProcessError as e:
        # Check for rate limiting
        if b"rate limit" in e.stderr.lower() if e.stderr else False:
            print("    Rate limited! Waiting 60s...")
            time.sleep(60)
            return close_github_issue(issue_number, reason, rate_limit)
        raise


def close_issues_in_batches(
    results: list[MatchResult],
    batch_size: int = 100,
    batch_delay: float = 60.0,
    rate_limit: float = 1.0,
) -> tuple[int, int]:
    """Close GitHub issues in batches with rate limiting.

    Args:
        results: List of MatchResult with action="close"
        batch_size: Number of issues to close per batch
        batch_delay: Seconds to wait between batches
        rate_limit: Seconds between individual API calls

    Returns:
        Tuple of (closed_count, failed_count)
    """
    to_close = [r for r in results if r.action == "close"]
    total = len(to_close)
    closed = 0
    failed = 0

    print(f"\nClosing {total} GitHub issues in batches of {batch_size}...")
    print(f"Rate limit: {rate_limit}s between calls, {batch_delay}s between batches")
    print("-" * 60)

    for batch_num, i in enumerate(range(0, total, batch_size)):
        batch = to_close[i : i + batch_size]
        batch_start = i + 1
        batch_end = min(i + batch_size, total)

        print(f"\nBatch {batch_num + 1}: Issues {batch_start}-{batch_end} of {total}")

        for _j, r in enumerate(batch):
            issue_num = r.github_issue.number
            linear_id = r.linear_task.identifier if r.linear_task else "N/A"

            try:
                reason = f"Matched to {linear_id} (status: {r.linear_task.status})"
                close_github_issue(issue_num, reason, rate_limit)
                closed += 1
                print(f"  [{closed}/{total}] Closed #{issue_num} -> {linear_id}")
            except Exception as e:
                failed += 1
                print(f"  [{closed}/{total}] FAILED #{issue_num}: {e}")

        # Pause between batches (except after last batch)
        if batch_end < total:
            print(f"\n  Batch complete. Waiting {batch_delay}s before next batch...")
            time.sleep(batch_delay)

    print("-" * 60)
    print(f"Complete: {closed} closed, {failed} failed")
    return closed, failed


def similarity_score(s1: str, s2: str) -> float:
    """Calculate similarity between two strings (0-100)."""
    # Normalize strings for comparison
    s1_norm = s1.lower().strip()
    s2_norm = s2.lower().strip()

    # Use SequenceMatcher for fuzzy matching
    ratio = SequenceMatcher(None, s1_norm, s2_norm).ratio()
    return ratio * 100


def find_best_match(
    github_issue: GitHubIssue,
    linear_tasks: list[LinearTask],
    min_similarity: float = 80.0,
) -> tuple[LinearTask | None, float]:
    """Find the best matching Linear task for a GitHub issue."""
    best_match = None
    best_score = 0.0

    for task in linear_tasks:
        score = similarity_score(github_issue.title, task.title)

        # Also check if GitHub issue body contains Linear identifier
        if github_issue.body and task.identifier in github_issue.body:
            score = 100.0  # Exact match via identifier reference

        if score > best_score:
            best_score = score
            best_match = task

    if best_score >= min_similarity:
        return best_match, best_score
    return None, best_score


def audit_issues(
    github_issues: list[GitHubIssue],
    linear_tasks: list[LinearTask],
    min_similarity: float = 80.0,
) -> list[MatchResult]:
    """Audit GitHub issues against Linear tasks."""
    results = []

    # Create a set of completed Linear task statuses
    completed_statuses = {"Done", "Canceled", "Duplicate"}

    for gh_issue in github_issues:
        match, score = find_best_match(gh_issue, linear_tasks, min_similarity)

        if match is None:
            action = "no_match"
        elif match.status in completed_statuses:
            action = "close"
        else:
            action = "keep_open"

        results.append(
            MatchResult(
                github_issue=gh_issue,
                linear_task=match,
                similarity=score,
                action=action,
            )
        )

    return results


def print_table(results: list[MatchResult]) -> None:
    """Print results as a formatted table."""
    # Group by action
    to_close = [r for r in results if r.action == "close"]
    no_match = [r for r in results if r.action == "no_match"]
    keep_open = [r for r in results if r.action == "keep_open"]

    print("\n" + "=" * 80)
    print("AUDIT SUMMARY")
    print("=" * 80)
    print(f"Total GitHub issues:        {len(results)}")
    print(f"  - Should close (Done):    {len(to_close)}")
    print(f"  - Keep open (In Progress):{len(keep_open)}")
    print(f"  - No Linear match:        {len(no_match)}")

    if to_close:
        print("\n" + "-" * 80)
        print("ISSUES TO CLOSE (Linear task is Done)")
        print("-" * 80)
        print(f"{'GH#':<8} {'Similarity':<12} {'Linear ID':<12} {'Title':<46}")
        print("-" * 80)
        for r in sorted(to_close, key=lambda x: -x.similarity):
            title = (
                r.github_issue.title[:44] + ".."
                if len(r.github_issue.title) > 46
                else r.github_issue.title
            )
            linear_id = r.linear_task.identifier if r.linear_task else "N/A"
            print(f"#{r.github_issue.number:<7} {r.similarity:>6.1f}%      {linear_id:<12} {title}")

    if no_match:
        print("\n" + "-" * 80)
        print("NO LINEAR MATCH (may need manual review)")
        print("-" * 80)
        print(f"{'GH#':<8} {'Best Score':<12} {'Title':<58}")
        print("-" * 80)
        for r in sorted(no_match, key=lambda x: x.github_issue.number)[:20]:  # Show first 20
            title = (
                r.github_issue.title[:56] + ".."
                if len(r.github_issue.title) > 58
                else r.github_issue.title
            )
            print(f"#{r.github_issue.number:<7} {r.similarity:>6.1f}%      {title}")
        if len(no_match) > 20:
            print(f"  ... and {len(no_match) - 20} more")


def print_json(results: list[MatchResult]) -> None:
    """Print results as JSON."""
    output = []
    for r in results:
        output.append(
            {
                "github_issue": {
                    "number": r.github_issue.number,
                    "title": r.github_issue.title,
                    "url": r.github_issue.url,
                },
                "linear_task": {
                    "identifier": r.linear_task.identifier,
                    "title": r.linear_task.title,
                    "status": r.linear_task.status,
                    "url": r.linear_task.url,
                }
                if r.linear_task
                else None,
                "similarity": r.similarity,
                "action": r.action,
            }
        )
    print(json.dumps(output, indent=2))


def print_csv(results: list[MatchResult]) -> None:
    """Print results as CSV."""
    print("github_number,github_title,linear_id,linear_status,similarity,action")
    for r in results:
        gh_title = r.github_issue.title.replace('"', '""')
        linear_id = r.linear_task.identifier if r.linear_task else ""
        linear_status = r.linear_task.status if r.linear_task else ""
        print(
            f'{r.github_issue.number},"{gh_title}",{linear_id},{linear_status},{r.similarity:.1f},{r.action}'
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit Linear-GitHub issue sync status",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--close-matched",
        action="store_true",
        help="Close GitHub issues that match Done Linear tasks",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Actually make changes (default is dry-run mode)",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=80.0,
        help="Minimum title similarity score (0-100, default: 80)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Max GitHub issues to process",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of issues to close per batch (default: 100)",
    )
    parser.add_argument(
        "--batch-delay",
        type=float,
        default=60.0,
        help="Seconds to wait between batches (default: 60)",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=1.0,
        help="Seconds between individual API calls (default: 1.0)",
    )
    parser.add_argument(
        "--output",
        choices=["table", "json", "csv"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--team-id",
        default=DEFAULT_TEAM_ID,
        help="Linear team ID",
    )

    args = parser.parse_args()

    # Get API keys
    linear_api_key = os.environ.get("LINEAR_API_KEY")
    if not linear_api_key:
        print("Error: LINEAR_API_KEY environment variable not set", file=sys.stderr)
        print("Get your API key from: https://linear.app/settings/api", file=sys.stderr)
        return 1

    # Verify gh CLI is available
    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)  # noqa: S607
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: gh CLI not found or not authenticated", file=sys.stderr)
        print("Install: https://cli.github.com/", file=sys.stderr)
        return 1

    print("Fetching GitHub issues...")
    github_issues = get_github_issues(args.limit)
    print(f"  Found {len(github_issues)} open GitHub issues")

    print("Fetching Linear tasks...")
    linear_client = LinearClient(linear_api_key)
    linear_tasks = linear_client.get_all_issues(args.team_id)
    print(f"  Found {len(linear_tasks)} Linear tasks")

    print("Analyzing matches...")
    results = audit_issues(github_issues, linear_tasks, args.min_similarity)

    # Output results
    if args.output == "json":
        print_json(results)
    elif args.output == "csv":
        print_csv(results)
    else:
        print_table(results)

    # Close issues if requested
    if args.close_matched:
        to_close = [r for r in results if r.action == "close"]
        if not to_close:
            print("\nNo issues to close.")
        elif args.no_dry_run:
            _closed, failed = close_issues_in_batches(
                results,
                batch_size=args.batch_size,
                batch_delay=args.batch_delay,
                rate_limit=args.rate_limit,
            )
            return 1 if failed > 0 else 0
        else:
            print(f"\n[DRY RUN] Would close {len(to_close)} GitHub issues")
            print(f"  Batch size: {args.batch_size}")
            print(f"  Batch delay: {args.batch_delay}s")
            print(f"  Rate limit: {args.rate_limit}s")
            est_time = (
                len(to_close) * args.rate_limit
                + (len(to_close) // args.batch_size) * args.batch_delay
            )
            print(f"  Estimated time: {est_time / 60:.1f} minutes")
            print("\nRun with --close-matched --no-dry-run to actually close them")

    return 0


if __name__ == "__main__":
    sys.exit(main())
