#!/usr/bin/env python3
"""Collect CI/CD workflow metrics from GitHub Actions API.

This script fetches workflow run data from GitHub Actions and generates
metrics for pipeline observability including:
- Workflow durations and success rates
- Job-level timing breakdown
- Bottleneck identification
- DORA metrics (deployment frequency, lead time, MTTR, change failure rate)

Usage:
    python scripts/ci-metrics-collector.py [--days=7] [--output=json|prometheus|summary]

Environment variables:
    GITHUB_TOKEN: GitHub personal access token with repo scope
    GITHUB_REPOSITORY: Repository in format "owner/repo"
    CI_METRICS_DAYS: Number of days to analyze (default: 7)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


@dataclass
class WorkflowRun:
    """Represents a single workflow run."""

    id: int
    name: str
    status: str
    conclusion: str | None
    created_at: datetime
    updated_at: datetime
    run_started_at: datetime | None
    head_branch: str
    event: str
    run_attempt: int
    html_url: str

    @property
    def duration_seconds(self) -> float | None:
        """Calculate run duration in seconds."""
        if self.run_started_at is None:
            return None
        return (self.updated_at - self.run_started_at).total_seconds()

    @property
    def is_success(self) -> bool:
        """Check if run was successful."""
        return self.conclusion == "success"

    @property
    def is_failure(self) -> bool:
        """Check if run failed."""
        return self.conclusion == "failure"


@dataclass
class JobTiming:
    """Timing information for a workflow job."""

    name: str
    started_at: datetime | None
    completed_at: datetime | None
    conclusion: str | None
    steps: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float | None:
        """Calculate job duration in seconds."""
        if self.started_at is None or self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()


@dataclass
class WorkflowMetrics:
    """Aggregated metrics for a workflow type."""

    name: str
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    durations: list[float] = field(default_factory=list)
    job_durations: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_runs == 0:
            return 0.0
        return (self.successful_runs / self.total_runs) * 100

    @property
    def avg_duration(self) -> float:
        """Calculate average duration in seconds."""
        if not self.durations:
            return 0.0
        return sum(self.durations) / len(self.durations)

    @property
    def p50_duration(self) -> float:
        """Calculate median (P50) duration."""
        if not self.durations:
            return 0.0
        sorted_durations = sorted(self.durations)
        mid = len(sorted_durations) // 2
        if len(sorted_durations) % 2 == 0:
            return (sorted_durations[mid - 1] + sorted_durations[mid]) / 2
        return sorted_durations[mid]

    @property
    def p95_duration(self) -> float:
        """Calculate P95 duration."""
        if not self.durations:
            return 0.0
        sorted_durations = sorted(self.durations)
        idx = int(len(sorted_durations) * 0.95)
        return sorted_durations[min(idx, len(sorted_durations) - 1)]

    @property
    def max_duration(self) -> float:
        """Get maximum duration."""
        if not self.durations:
            return 0.0
        return max(self.durations)


@dataclass
class DORAMetrics:
    """DORA (DevOps Research and Assessment) metrics."""

    deployment_frequency_per_day: float = 0.0
    lead_time_hours: float = 0.0
    mean_time_to_recovery_hours: float = 0.0
    change_failure_rate: float = 0.0


class GitHubActionsClient:
    """Client for GitHub Actions API."""

    def __init__(self, token: str, repo: str):
        """Initialize client with GitHub token and repository."""
        self.token = token
        self.repo = repo
        self.base_url = f"https://api.github.com/repos/{repo}"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _parse_datetime(self, dt_str: str | None) -> datetime | None:
        """Parse ISO datetime string."""
        if dt_str is None:
            return None
        # Handle both Z and +00:00 timezone formats
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)

    def get_workflow_runs(
        self,
        workflow_name: str | None = None,
        days: int = 7,
        per_page: int = 100,
    ) -> list[WorkflowRun]:
        """Fetch workflow runs from the last N days."""
        runs: list[WorkflowRun] = []
        cutoff = datetime.now(UTC) - timedelta(days=days)

        params: dict[str, Any] = {
            "per_page": per_page,
            "page": 1,
        }
        if workflow_name:
            params["workflow_id"] = workflow_name

        with httpx.Client(timeout=30.0) as client:
            while True:
                response = client.get(
                    f"{self.base_url}/actions/runs",
                    headers=self.headers,
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

                for run in data.get("workflow_runs", []):
                    created_at = self._parse_datetime(run["created_at"])
                    if created_at and created_at < cutoff:
                        return runs

                    runs.append(
                        WorkflowRun(
                            id=run["id"],
                            name=run["name"],
                            status=run["status"],
                            conclusion=run.get("conclusion"),
                            created_at=created_at or datetime.now(UTC),
                            updated_at=self._parse_datetime(run["updated_at"]) or datetime.now(UTC),
                            run_started_at=self._parse_datetime(run.get("run_started_at")),
                            head_branch=run["head_branch"],
                            event=run["event"],
                            run_attempt=run["run_attempt"],
                            html_url=run["html_url"],
                        )
                    )

                # Check pagination
                if len(data.get("workflow_runs", [])) < per_page:
                    break
                params["page"] += 1

        return runs

    def get_workflow_jobs(self, run_id: int) -> list[JobTiming]:
        """Fetch jobs for a specific workflow run."""
        jobs = []

        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{self.base_url}/actions/runs/{run_id}/jobs",
                headers=self.headers,
                params={"per_page": 100},
            )
            response.raise_for_status()
            data = response.json()

            for job in data.get("jobs", []):
                jobs.append(
                    JobTiming(
                        name=job["name"],
                        started_at=self._parse_datetime(job.get("started_at")),
                        completed_at=self._parse_datetime(job.get("completed_at")),
                        conclusion=job.get("conclusion"),
                        steps=[
                            {
                                "name": s["name"],
                                "status": s["status"],
                                "conclusion": s.get("conclusion"),
                                "started_at": s.get("started_at"),
                                "completed_at": s.get("completed_at"),
                            }
                            for s in job.get("steps", [])
                        ],
                    )
                )

        return jobs

    def get_workflows(self) -> list[dict[str, Any]]:
        """List all workflows in the repository."""
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{self.base_url}/actions/workflows",
                headers=self.headers,
            )
            response.raise_for_status()
            workflows: list[dict[str, Any]] = response.json().get("workflows", [])
            return workflows


class MetricsCollector:
    """Collects and aggregates CI/CD metrics."""

    def __init__(self, client: GitHubActionsClient):
        """Initialize collector with GitHub client."""
        self.client = client

    def collect_workflow_metrics(self, days: int = 7) -> dict[str, WorkflowMetrics]:
        """Collect metrics for all workflows."""
        runs = self.client.get_workflow_runs(days=days)
        metrics: dict[str, WorkflowMetrics] = {}

        for run in runs:
            if run.name not in metrics:
                metrics[run.name] = WorkflowMetrics(name=run.name)

            wf_metrics = metrics[run.name]
            wf_metrics.total_runs += 1

            if run.is_success:
                wf_metrics.successful_runs += 1
            elif run.is_failure:
                wf_metrics.failed_runs += 1

            if run.duration_seconds is not None:
                wf_metrics.durations.append(run.duration_seconds)

        return metrics

    def collect_job_level_metrics(
        self, run_ids: list[int], max_runs: int = 20
    ) -> dict[str, list[float]]:
        """Collect job-level timing for detailed analysis."""
        job_durations: dict[str, list[float]] = defaultdict(list)

        for run_id in run_ids[:max_runs]:
            try:
                jobs = self.client.get_workflow_jobs(run_id)
                for job in jobs:
                    if job.duration_seconds is not None:
                        job_durations[job.name].append(job.duration_seconds)
            except Exception as e:
                print(f"Warning: Could not fetch jobs for run {run_id}: {e}", file=sys.stderr)

        return dict(job_durations)

    def identify_bottlenecks(
        self, job_durations: dict[str, list[float]], top_n: int = 5
    ) -> list[tuple[str, float]]:
        """Identify slowest jobs (bottlenecks)."""
        avg_durations = []
        for job_name, durations in job_durations.items():
            if durations:
                avg = sum(durations) / len(durations)
                avg_durations.append((job_name, avg))

        avg_durations.sort(key=lambda x: x[1], reverse=True)
        return avg_durations[:top_n]

    def calculate_dora_metrics(self, runs: list[WorkflowRun], days: int) -> DORAMetrics:
        """Calculate DORA metrics from workflow runs."""
        # Filter to main branch and completed runs
        main_runs = [r for r in runs if r.head_branch == "main" and r.status == "completed"]

        if not main_runs:
            return DORAMetrics()

        # Deployment frequency (successful runs per day)
        successful_deploys = [r for r in main_runs if r.is_success]
        deployment_frequency = len(successful_deploys) / days if days > 0 else 0

        # Lead time (average time from run start to completion)
        lead_times = [r.duration_seconds for r in successful_deploys if r.duration_seconds]
        avg_lead_time_hours = (sum(lead_times) / len(lead_times) / 3600) if lead_times else 0

        # Mean time to recovery (time between failure and next success)
        recovery_times = []
        failed_at = None
        for run in sorted(main_runs, key=lambda r: r.created_at):
            if run.is_failure:
                failed_at = run.updated_at
            elif run.is_success and failed_at:
                recovery_time = (run.updated_at - failed_at).total_seconds() / 3600
                recovery_times.append(recovery_time)
                failed_at = None

        mttr = sum(recovery_times) / len(recovery_times) if recovery_times else 0

        # Change failure rate
        failed_runs = [r for r in main_runs if r.is_failure]
        change_failure_rate = (len(failed_runs) / len(main_runs) * 100) if main_runs else 0

        return DORAMetrics(
            deployment_frequency_per_day=deployment_frequency,
            lead_time_hours=avg_lead_time_hours,
            mean_time_to_recovery_hours=mttr,
            change_failure_rate=change_failure_rate,
        )


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def output_summary(
    workflow_metrics: dict[str, WorkflowMetrics],
    bottlenecks: list[tuple[str, float]],
    dora: DORAMetrics,
    days: int,
) -> None:
    """Output human-readable summary."""
    print("=" * 70)
    print(f"CI/CD METRICS REPORT (Last {days} days)")
    print("=" * 70)
    print()

    # Workflow summary
    print("WORKFLOW SUCCESS RATES:")
    print("-" * 50)
    for name, metrics in sorted(workflow_metrics.items()):
        status = (
            "OK" if metrics.success_rate >= 90 else "WARN" if metrics.success_rate >= 80 else "BAD"
        )
        print(
            f"  [{status}] {name}: {metrics.success_rate:.1f}% "
            f"({metrics.successful_runs}/{metrics.total_runs})"
        )
    print()

    # Duration analysis
    print("WORKFLOW DURATIONS (P50 / P95 / Max):")
    print("-" * 50)
    for name, metrics in sorted(workflow_metrics.items()):
        if metrics.durations:
            print(
                f"  {name}: {format_duration(metrics.p50_duration)} / "
                f"{format_duration(metrics.p95_duration)} / "
                f"{format_duration(metrics.max_duration)}"
            )
    print()

    # Bottlenecks
    if bottlenecks:
        print("TOP BOTTLENECK JOBS (avg duration):")
        print("-" * 50)
        for job_name, avg_duration in bottlenecks:
            print(f"  {format_duration(avg_duration)} - {job_name}")
        print()

    # DORA metrics
    print("DORA METRICS:")
    print("-" * 50)
    print(f"  Deployment Frequency: {dora.deployment_frequency_per_day:.2f}/day")
    print(f"  Lead Time: {dora.lead_time_hours:.1f} hours")
    print(f"  Mean Time to Recovery: {dora.mean_time_to_recovery_hours:.1f} hours")
    print(f"  Change Failure Rate: {dora.change_failure_rate:.1f}%")
    print()

    # Targets vs actuals
    print("TARGETS vs ACTUALS:")
    print("-" * 50)

    # Calculate overall CI success rate
    total_runs = sum(m.total_runs for m in workflow_metrics.values())
    total_success = sum(m.successful_runs for m in workflow_metrics.values())
    overall_success_rate = (total_success / total_runs * 100) if total_runs > 0 else 0

    # Calculate average CI time
    all_durations = []
    for m in workflow_metrics.values():
        all_durations.extend(m.durations)
    avg_ci_time = sum(all_durations) / len(all_durations) / 60 if all_durations else 0

    targets = [
        ("CI Success Rate", 95, overall_success_rate, "%"),
        ("Avg CI Time", 15, avg_ci_time, "min"),
        ("Change Failure Rate", 5, dora.change_failure_rate, "%"),
    ]

    for name, target, actual, unit in targets:
        if name == "Avg CI Time":
            status = "OK" if actual <= target else "WARN" if actual <= target * 1.33 else "BAD"
        elif name == "Change Failure Rate":
            status = "OK" if actual <= target else "WARN" if actual <= target * 2 else "BAD"
        else:
            status = "OK" if actual >= target else "WARN" if actual >= target * 0.9 else "BAD"
        print(f"  [{status}] {name}: {actual:.1f}{unit} (target: {target}{unit})")

    print()


def output_json(
    workflow_metrics: dict[str, WorkflowMetrics],
    bottlenecks: list[tuple[str, float]],
    dora: DORAMetrics,
    days: int,
) -> None:
    """Output metrics as JSON."""
    data = {
        "report_date": datetime.now(UTC).isoformat(),
        "period_days": days,
        "workflows": {
            name: {
                "total_runs": m.total_runs,
                "successful_runs": m.successful_runs,
                "failed_runs": m.failed_runs,
                "success_rate": m.success_rate,
                "avg_duration_seconds": m.avg_duration,
                "p50_duration_seconds": m.p50_duration,
                "p95_duration_seconds": m.p95_duration,
                "max_duration_seconds": m.max_duration,
            }
            for name, m in workflow_metrics.items()
        },
        "bottleneck_jobs": [
            {"name": name, "avg_duration_seconds": duration} for name, duration in bottlenecks
        ],
        "dora_metrics": {
            "deployment_frequency_per_day": dora.deployment_frequency_per_day,
            "lead_time_hours": dora.lead_time_hours,
            "mean_time_to_recovery_hours": dora.mean_time_to_recovery_hours,
            "change_failure_rate_percent": dora.change_failure_rate,
        },
    }
    print(json.dumps(data, indent=2))


def output_prometheus(
    workflow_metrics: dict[str, WorkflowMetrics],
    bottlenecks: list[tuple[str, float]],
    dora: DORAMetrics,
    days: int,
) -> None:
    """Output metrics in Prometheus format."""
    lines = [
        "# HELP ci_workflow_runs_total Total number of workflow runs",
        "# TYPE ci_workflow_runs_total counter",
    ]

    for name, m in workflow_metrics.items():
        safe_name = name.replace(" ", "_").replace("-", "_").lower()
        lines.append(f'ci_workflow_runs_total{{workflow="{safe_name}"}} {m.total_runs}')

    lines.extend(
        [
            "",
            "# HELP ci_workflow_success_rate Workflow success rate percentage",
            "# TYPE ci_workflow_success_rate gauge",
        ]
    )
    for name, m in workflow_metrics.items():
        safe_name = name.replace(" ", "_").replace("-", "_").lower()
        lines.append(f'ci_workflow_success_rate{{workflow="{safe_name}"}} {m.success_rate:.2f}')

    lines.extend(
        [
            "",
            "# HELP ci_workflow_duration_seconds Workflow duration statistics",
            "# TYPE ci_workflow_duration_seconds gauge",
        ]
    )
    for name, m in workflow_metrics.items():
        safe_name = name.replace(" ", "_").replace("-", "_").lower()
        lines.append(
            f'ci_workflow_duration_seconds{{workflow="{safe_name}",quantile="0.5"}} {m.p50_duration:.2f}'
        )
        lines.append(
            f'ci_workflow_duration_seconds{{workflow="{safe_name}",quantile="0.95"}} {m.p95_duration:.2f}'
        )

    lines.extend(
        [
            "",
            "# HELP ci_job_duration_seconds Average job duration",
            "# TYPE ci_job_duration_seconds gauge",
        ]
    )
    for job_name, avg_duration in bottlenecks:
        safe_name = (
            job_name.replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "").lower()
        )
        lines.append(f'ci_job_duration_seconds{{job="{safe_name}"}} {avg_duration:.2f}')

    lines.extend(
        [
            "",
            "# HELP ci_dora_deployment_frequency Deployments per day",
            "# TYPE ci_dora_deployment_frequency gauge",
            f"ci_dora_deployment_frequency {dora.deployment_frequency_per_day:.2f}",
            "",
            "# HELP ci_dora_lead_time_hours Lead time in hours",
            "# TYPE ci_dora_lead_time_hours gauge",
            f"ci_dora_lead_time_hours {dora.lead_time_hours:.2f}",
            "",
            "# HELP ci_dora_mttr_hours Mean time to recovery in hours",
            "# TYPE ci_dora_mttr_hours gauge",
            f"ci_dora_mttr_hours {dora.mean_time_to_recovery_hours:.2f}",
            "",
            "# HELP ci_dora_change_failure_rate Change failure rate percentage",
            "# TYPE ci_dora_change_failure_rate gauge",
            f"ci_dora_change_failure_rate {dora.change_failure_rate:.2f}",
        ]
    )

    print("\n".join(lines))


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Collect CI/CD workflow metrics from GitHub Actions"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=int(os.environ.get("CI_METRICS_DAYS", "7")),
        help="Number of days to analyze (default: 7)",
    )
    parser.add_argument(
        "--output",
        choices=["summary", "json", "prometheus"],
        default="summary",
        help="Output format (default: summary)",
    )
    parser.add_argument(
        "--sample-jobs",
        type=int,
        default=20,
        help="Number of runs to sample for job-level metrics (default: 20)",
    )
    args = parser.parse_args()

    # Get credentials from environment
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")

    if not token:
        print("Error: GITHUB_TOKEN environment variable required", file=sys.stderr)
        return 1

    if not repo:
        print("Error: GITHUB_REPOSITORY environment variable required", file=sys.stderr)
        return 1

    try:
        client = GitHubActionsClient(token, repo)
        collector = MetricsCollector(client)

        # Collect workflow metrics
        workflow_metrics = collector.collect_workflow_metrics(days=args.days)

        if not workflow_metrics:
            print("Warning: No workflow runs found", file=sys.stderr)
            return 0

        # Collect job-level metrics from recent runs
        recent_run_ids = []
        runs = client.get_workflow_runs(days=args.days)
        for run in runs:
            if run.status == "completed":
                recent_run_ids.append(run.id)

        job_durations = collector.collect_job_level_metrics(
            recent_run_ids, max_runs=args.sample_jobs
        )
        bottlenecks = collector.identify_bottlenecks(job_durations)

        # Calculate DORA metrics
        dora = collector.calculate_dora_metrics(runs, args.days)

        # Output results
        if args.output == "json":
            output_json(workflow_metrics, bottlenecks, dora, args.days)
        elif args.output == "prometheus":
            output_prometheus(workflow_metrics, bottlenecks, dora, args.days)
        else:
            output_summary(workflow_metrics, bottlenecks, dora, args.days)

        return 0

    except httpx.HTTPStatusError as e:
        print(f"Error: GitHub API request failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
