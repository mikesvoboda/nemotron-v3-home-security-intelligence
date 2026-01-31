#!/usr/bin/env python3
"""AI Pipeline Quality Analysis.

Local CLI tool for analyzing AI pipeline quality metrics with optional
subagent judge for deep reasoning analysis.

Usage:
    uv run python scripts/ai-quality-analysis.py              # Quick report
    uv run python scripts/ai-quality-analysis.py --judge      # With AI judge
    uv run python scripts/ai-quality-analysis.py --capture-baseline
    uv run python scripts/ai-quality-analysis.py --compare
    uv run python scripts/ai-quality-analysis.py --create-linear-task

Modes:
    default           - Quick metrics report with pass/fail assessment
    --judge           - Spawn Claude subagent to evaluate reasoning quality
    --capture-baseline - Save current metrics to config/ai-quality-baseline.yaml
    --compare         - Compare current metrics against baseline, flag regressions
    --create-linear-task - Create Linear backlog task for regressions found

Examples:
    # Run basic quality check
    uv run python scripts/ai-quality-analysis.py

    # Full analysis with AI judge evaluation
    uv run python scripts/ai-quality-analysis.py --judge --samples 10

    # Capture baseline after successful deployment
    uv run python scripts/ai-quality-analysis.py --capture-baseline

    # Check for regressions before PR merge
    uv run python scripts/ai-quality-analysis.py --compare --tolerance 0.05

    # Create Linear task if regressions found
    uv run python scripts/ai-quality-analysis.py --compare --create-linear-task
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _load_env_and_fix_database_url() -> None:
    """Load .env file and fix DATABASE_URL for local execution.

    When running outside containers, the DATABASE_URL uses container hostnames
    (e.g., 'postgres:5432') which don't resolve. This function:
    1. Loads .env from the project root
    2. Checks for DATABASE_URL_EXTERNAL (explicit local config)
    3. Detects if running locally (hostname doesn't resolve)
    4. Converts container hostname to localhost for local execution
    """
    from dotenv import load_dotenv

    # Find project root (parent of scripts/)
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"

    if env_file.exists():
        load_dotenv(env_file)
        print(f"Loaded environment from {env_file}")

    # Check for explicit external DATABASE_URL first
    external_url = os.environ.get("DATABASE_URL_EXTERNAL")
    if external_url:
        os.environ["DATABASE_URL"] = external_url
        print("Using DATABASE_URL_EXTERNAL for local execution")
        return

    # Check if DATABASE_URL needs transformation for local execution
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("Warning: DATABASE_URL not set in environment")
        return

    # Extract hostname and port from DATABASE_URL
    match = re.search(r"@([^:/@]+):(\d+)/", database_url)
    if not match:
        return

    hostname, port = match.groups()

    # Check if hostname resolves (i.e., we're inside container network)
    try:
        socket.gethostbyname(hostname)
        print(f"Database hostname '{hostname}' resolves - using container network")
    except socket.gaierror:
        # Hostname doesn't resolve - we're running locally
        external_port = os.environ.get("POSTGRES_EXTERNAL_PORT", "5432")

        # Replace container hostname with localhost and optionally fix port
        new_url = database_url.replace(f"@{hostname}:", "@localhost:")
        if port != external_port:
            new_url = new_url.replace(f"@localhost:{port}/", f"@localhost:{external_port}/")
            print(
                f"Database hostname '{hostname}' doesn't resolve - using localhost:{external_port}"
            )
        else:
            print(f"Database hostname '{hostname}' doesn't resolve - using localhost:{port}")
        os.environ["DATABASE_URL"] = new_url


# Load .env before importing backend modules
_load_env_and_fix_database_url()

import yaml  # noqa: E402, I001

from backend.core.database import get_session, init_db  # noqa: E402
from backend.services.ai_quality_metrics import (  # noqa: E402
    AIQualityAnalyzer,
    QualityLevel,
    QualityReport,
)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
BASELINE_FILE = PROJECT_ROOT / "config" / "ai-quality-baseline.yaml"
LINEAR_TEAM_ID = "998946a2-aa75-491b-a39d-189660131392"


@dataclass
class RegressionResult:
    """Result of comparing current metrics against baseline."""

    metric_name: str
    baseline_value: float | int | bool
    current_value: float | int | bool
    tolerance: float
    is_regression: bool
    severity: str  # "critical", "warning", "info"
    details: str = ""


@dataclass
class ComparisonReport:
    """Full comparison report between current and baseline metrics."""

    baseline_timestamp: str
    current_timestamp: str
    regressions: list[RegressionResult] = field(default_factory=list)
    improvements: list[RegressionResult] = field(default_factory=list)

    @property
    def has_critical_regressions(self) -> bool:
        """Check if any critical regressions were found."""
        return any(r.is_regression and r.severity == "critical" for r in self.regressions)

    @property
    def total_regressions(self) -> int:
        """Count total number of regressions."""
        return sum(1 for r in self.regressions if r.is_regression)


@dataclass
class JudgeEvaluation:
    """Result from AI judge evaluation of reasoning quality."""

    reasoning_coherence_score: int  # 0-100
    detection_grounding_score: int  # 0-100
    risk_calibration_score: int  # 0-100
    overall_score: int  # 0-100
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    sample_evaluations: list[dict] = field(default_factory=list)


async def fetch_sample_reasoning(limit: int = 10) -> list[dict]:
    """Fetch sample LLM reasoning from database for judge evaluation.

    Args:
        limit: Maximum number of samples to fetch

    Returns:
        List of dicts with event context and LLM response
    """
    from sqlalchemy import select  # noqa: I001
    from sqlalchemy.orm import selectinload

    from backend.models.llm_interaction import LLMInteraction

    samples = []

    async with get_session() as session:
        stmt = (
            select(LLMInteraction)
            .options(selectinload(LLMInteraction.event))
            .order_by(LLMInteraction.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        interactions = list(result.scalars().all())

        for interaction in interactions:
            event = interaction.event
            if not event:
                continue

            # Parse raw_response if it's a string
            raw_response = interaction.raw_response
            if isinstance(raw_response, str):
                try:
                    raw_response = json.loads(raw_response)
                except json.JSONDecodeError:
                    raw_response = {"raw_text": raw_response}

            samples.append(
                {
                    "event_id": event.id,
                    "camera_id": event.camera_id,
                    "risk_score": event.risk_score,
                    "risk_level": event.risk_level,
                    "object_types": event.object_types,
                    "summary": event.summary,
                    "reasoning": raw_response.get("reasoning", ""),
                    "enrichment_snapshot": interaction.enrichment_snapshot,
                    "context_sources": interaction.context_sources,
                }
            )

    return samples


def build_judge_prompt(samples: list[dict]) -> str:
    """Build prompt for AI judge to evaluate reasoning quality.

    Args:
        samples: List of sample reasoning from the database

    Returns:
        Formatted prompt for Claude to evaluate
    """
    prompt_parts = [
        """You are an AI quality judge evaluating the reasoning quality of a home security
AI system. Analyze the following sample reasoning outputs and provide a comprehensive
evaluation.

For each sample, evaluate:
1. **Reasoning Coherence**: Does the reasoning make logical sense? Is it well-structured?
2. **Detection Grounding**: Does it reference actual detections from the enrichment data?
3. **Risk Calibration**: Is the risk score appropriate given the reasoning and context?

After analyzing all samples, provide:
- Overall scores (0-100) for each dimension
- Key strengths observed
- Key weaknesses identified
- Specific suggestions for improvement

---
SAMPLE REASONING TO EVALUATE:
""",
    ]

    for i, sample in enumerate(samples, 1):
        prompt_parts.append(f"""
--- SAMPLE {i} ---
Event ID: {sample["event_id"]}
Camera: {sample["camera_id"]}
Object Types: {sample["object_types"]}
Risk Score: {sample["risk_score"]}
Risk Level: {sample["risk_level"]}

Reasoning:
{sample["reasoning"][:2000]}

Context Sources: {json.dumps(sample.get("context_sources", {}), indent=2)[:500]}

Summary: {sample["summary"]}
""")

    prompt_parts.append("""
---
EVALUATION FORMAT:
Please provide your evaluation in the following JSON format:
```json
{
  "reasoning_coherence_score": <0-100>,
  "detection_grounding_score": <0-100>,
  "risk_calibration_score": <0-100>,
  "overall_score": <0-100>,
  "strengths": ["strength 1", "strength 2", ...],
  "weaknesses": ["weakness 1", "weakness 2", ...],
  "suggestions": ["suggestion 1", "suggestion 2", ...],
  "sample_evaluations": [
    {"event_id": <id>, "coherence": <0-100>, "grounding": <0-100>, "calibration": <0-100>, "notes": "..."},
    ...
  ]
}
```
""")

    return "".join(prompt_parts)


def run_judge_analysis(prompt: str) -> JudgeEvaluation:
    """Spawn Claude subagent to perform judge analysis.

    Args:
        prompt: The evaluation prompt to send to Claude

    Returns:
        JudgeEvaluation with scores and feedback
    """
    print("\nSpawning Claude subagent for reasoning evaluation...")

    # Write prompt to temp file (using TMPDIR which defaults to /tmp/claude)
    temp_dir = Path(os.environ.get("TMPDIR", "/tmp/claude"))  # noqa: S108
    temp_prompt_file = temp_dir / "ai-quality-judge-prompt.txt"
    temp_prompt_file.parent.mkdir(parents=True, exist_ok=True)
    temp_prompt_file.write_text(prompt)

    try:
        # Run Claude CLI as subagent
        result = subprocess.run(
            [
                "claude",
                "--print",
                "--dangerously-skip-permissions",
                "-p",
                f"Read the prompt from {temp_prompt_file} and provide your evaluation. "
                "Output ONLY the JSON evaluation, no other text.",
            ],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            check=False,  # We handle return code manually
        )

        if result.returncode != 0:
            print(f"Claude CLI error: {result.stderr}")
            return JudgeEvaluation(
                reasoning_coherence_score=0,
                detection_grounding_score=0,
                risk_calibration_score=0,
                overall_score=0,
                weaknesses=["Judge analysis failed: " + result.stderr[:200]],
            )

        # Parse JSON from Claude's response
        response_text = result.stdout.strip()

        # Extract JSON from response (may have markdown code blocks)
        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            # Try to find raw JSON
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
            else:
                json_text = response_text

        data = json.loads(json_text)

        return JudgeEvaluation(
            reasoning_coherence_score=data.get("reasoning_coherence_score", 0),
            detection_grounding_score=data.get("detection_grounding_score", 0),
            risk_calibration_score=data.get("risk_calibration_score", 0),
            overall_score=data.get("overall_score", 0),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            suggestions=data.get("suggestions", []),
            sample_evaluations=data.get("sample_evaluations", []),
        )

    except subprocess.TimeoutExpired:
        print("Claude CLI timed out after 5 minutes")
        return JudgeEvaluation(
            reasoning_coherence_score=0,
            detection_grounding_score=0,
            risk_calibration_score=0,
            overall_score=0,
            weaknesses=["Judge analysis timed out"],
        )
    except json.JSONDecodeError as e:
        print(f"Failed to parse judge response as JSON: {e}")
        return JudgeEvaluation(
            reasoning_coherence_score=0,
            detection_grounding_score=0,
            risk_calibration_score=0,
            overall_score=0,
            weaknesses=[f"Failed to parse judge response: {e}"],
        )
    except FileNotFoundError:
        print("Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code")
        return JudgeEvaluation(
            reasoning_coherence_score=0,
            detection_grounding_score=0,
            risk_calibration_score=0,
            overall_score=0,
            weaknesses=["Claude CLI not installed"],
        )
    finally:
        # Cleanup temp file
        if temp_prompt_file.exists():
            temp_prompt_file.unlink()


def report_to_dict(report: QualityReport) -> dict[str, Any]:
    """Convert QualityReport to dictionary for YAML serialization."""
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "field_completeness": {
            "total_records": report.field_completeness.total_records,
            "raw_response_rate": report.field_completeness.raw_response_rate,
            "enrichment_snapshot_rate": report.field_completeness.enrichment_snapshot_rate,
            "context_sources_rate": report.field_completeness.context_sources_rate,
            "household_matches_rate": report.field_completeness.household_matches_rate,
        },
        "risk_distribution": {
            "total_events": report.risk_distribution.total_events,
            "mean_score": report.risk_distribution.mean_score,
            "std_dev": report.risk_distribution.std_dev,
            "min_score": report.risk_distribution.min_score,
            "max_score": report.risk_distribution.max_score,
            "levels_covered": report.risk_distribution.levels_covered,
            "level_counts": report.risk_distribution.level_counts,
        },
        "reasoning_quality": {
            "avg_reasoning_length": report.reasoning_quality.avg_reasoning_length,
            "avg_summary_length": report.reasoning_quality.avg_summary_length,
            "min_reasoning_length": report.reasoning_quality.min_reasoning_length,
            "max_reasoning_length": report.reasoning_quality.max_reasoning_length,
            "detection_reference_rate": report.reasoning_quality.detection_reference_rate,
            "risk_keyword_rate": report.reasoning_quality.risk_keyword_rate,
        },
        "serialization": {
            "python_repr_count": report.serialization.python_repr_count,
            "invalid_array_count": report.serialization.invalid_array_count,
            "weather_serialization_ok": report.serialization.weather_serialization_ok,
            "faces_serialization_ok": report.serialization.faces_serialization_ok,
            "plates_serialization_ok": report.serialization.plates_serialization_ok,
        },
        "linkage": {
            "total_events": report.linkage.total_events,
            "events_with_interaction": report.linkage.events_with_interaction,
            "orphan_interactions": report.linkage.orphan_interactions,
            "coverage_rate": report.linkage.coverage_rate,
        },
        "results": [
            {
                "name": r.name,
                "value": r.value,
                "expected": r.expected,
                "level": r.level.value,
                "details": r.details,
            }
            for r in report.results
        ],
    }


def capture_baseline(report: QualityReport) -> Path:
    """Save current metrics as baseline to YAML file.

    Args:
        report: Current quality report

    Returns:
        Path to saved baseline file
    """
    baseline_data = report_to_dict(report)
    baseline_data["baseline_captured_at"] = datetime.now(UTC).isoformat()

    # Ensure config directory exists
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with BASELINE_FILE.open("w") as f:
        yaml.safe_dump(baseline_data, f, default_flow_style=False, sort_keys=False)

    return BASELINE_FILE


def load_baseline() -> dict[str, Any] | None:
    """Load baseline metrics from YAML file.

    Returns:
        Baseline data dictionary or None if not found
    """
    if not BASELINE_FILE.exists():
        return None

    with BASELINE_FILE.open() as f:
        return yaml.safe_load(f)


def compare_with_baseline(report: QualityReport, tolerance: float = 0.05) -> ComparisonReport:
    """Compare current metrics against baseline.

    Args:
        report: Current quality report
        tolerance: Acceptable deviation from baseline (default 5%)

    Returns:
        ComparisonReport with regressions and improvements
    """
    baseline = load_baseline()
    if not baseline:
        raise FileNotFoundError(f"Baseline not found at {BASELINE_FILE}")

    current = report_to_dict(report)
    comparison = ComparisonReport(
        baseline_timestamp=baseline.get("timestamp", "unknown"),
        current_timestamp=current["timestamp"],
    )

    # Define metrics to compare with severity levels
    metrics_to_compare = [
        # Critical metrics (failures block deployment)
        ("field_completeness.raw_response_rate", "critical", True),  # higher is better
        ("field_completeness.enrichment_snapshot_rate", "critical", True),
        ("linkage.coverage_rate", "critical", True),
        ("serialization.python_repr_count", "critical", False),  # lower is better
        # Warning metrics (should be investigated)
        ("reasoning_quality.avg_reasoning_length", "warning", True),
        ("reasoning_quality.detection_reference_rate", "warning", True),
        ("risk_distribution.std_dev", "warning", True),
        ("risk_distribution.levels_covered", "warning", True),
        # Info metrics (informational only)
        ("risk_distribution.mean_score", "info", None),  # neither direction is better
        ("linkage.orphan_interactions", "info", False),
    ]

    for metric_path, severity, higher_is_better in metrics_to_compare:
        parts = metric_path.split(".")
        try:
            baseline_val = baseline[parts[0]][parts[1]]
            current_val = current[parts[0]][parts[1]]
        except (KeyError, TypeError):
            continue

        # Skip non-numeric values
        if not isinstance(baseline_val, int | float) or not isinstance(current_val, int | float):
            continue

        # Calculate if regression occurred
        if higher_is_better is None:
            # No direction preference, just note the change
            is_regression = False
            is_improvement = False
        elif higher_is_better:
            # Higher is better, so regression is when current < baseline - tolerance
            threshold = baseline_val * (1 - tolerance)
            is_regression = current_val < threshold
            is_improvement = current_val > baseline_val * (1 + tolerance)
        else:
            # Lower is better, so regression is when current > baseline + tolerance
            threshold = baseline_val * (1 + tolerance) if baseline_val > 0 else tolerance
            is_regression = current_val > threshold
            is_improvement = current_val < baseline_val * (1 - tolerance)

        result = RegressionResult(
            metric_name=metric_path,
            baseline_value=baseline_val,
            current_value=current_val,
            tolerance=tolerance,
            is_regression=is_regression,
            severity=severity,
            details=f"{'Higher' if higher_is_better else 'Lower'} is better"
            if higher_is_better is not None
            else "Informational",
        )

        if is_regression:
            comparison.regressions.append(result)
        elif is_improvement:
            comparison.improvements.append(result)

    return comparison


def create_linear_task(comparison: ComparisonReport) -> str | None:
    """Create a Linear task for regressions found.

    Uses the Linear MCP tool via subprocess to create a backlog task.

    Args:
        comparison: Comparison report with regressions

    Returns:
        Task URL if created, None if no regressions or creation failed
    """
    if comparison.total_regressions == 0:
        print("No regressions found, skipping Linear task creation")
        return None

    # Build task description
    description_parts = [
        "## AI Quality Regressions Detected",
        "",
        f"**Comparison Time:** {comparison.current_timestamp}",
        f"**Baseline Time:** {comparison.baseline_timestamp}",
        "",
        "### Regressions Found",
        "",
    ]

    critical_regressions = [r for r in comparison.regressions if r.severity == "critical"]
    warning_regressions = [r for r in comparison.regressions if r.severity == "warning"]

    if critical_regressions:
        description_parts.append("#### Critical (blocking)")
        for r in critical_regressions:
            description_parts.append(
                f"- **{r.metric_name}**: {r.baseline_value} -> {r.current_value} ({r.details})"
            )
        description_parts.append("")

    if warning_regressions:
        description_parts.append("#### Warnings")
        for r in warning_regressions:
            description_parts.append(
                f"- **{r.metric_name}**: {r.baseline_value} -> {r.current_value} ({r.details})"
            )
        description_parts.append("")

    description_parts.extend(
        [
            "### Next Steps",
            "1. Review the regression data to identify root cause",
            "2. Check recent changes to AI pipeline components",
            "3. Run `uv run python scripts/ai-quality-analysis.py --judge` for deeper analysis",
            "4. Fix issues and re-run comparison before merging",
        ]
    )

    description = "\n".join(description_parts)
    title = f"AI Quality Regression: {comparison.total_regressions} metrics degraded"

    # Use Claude CLI to interact with Linear MCP
    # This is a workaround since we can't directly call MCP tools from Python
    print("\nCreating Linear task for regressions...")
    print(f"Title: {title}")
    print(f"Team ID: {LINEAR_TEAM_ID}")

    try:
        result = subprocess.run(
            [
                "claude",
                "--print",
                "--dangerously-skip-permissions",
                "-p",
                f"""Use the Linear MCP tool to create a new issue with:
- Title: "{title}"
- Team ID: {LINEAR_TEAM_ID}
- Description: {json.dumps(description)}
- Priority: 2 (high)

After creating, output ONLY the issue URL.""",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,  # We handle return code manually
        )

        if result.returncode == 0:
            # Extract URL from response
            response = result.stdout.strip()
            url_match = re.search(r"https://linear\.app/[^\s]+", response)
            if url_match:
                return url_match.group(0)
            return response
        else:
            print(f"Failed to create Linear task: {result.stderr}")
            return None

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Failed to create Linear task: {e}")
        return None


def print_report(report: QualityReport) -> None:
    """Print formatted quality report to console."""
    print("\n" + "=" * 70)
    print("AI PIPELINE QUALITY ANALYSIS REPORT")
    print("=" * 70)

    print(f"\nGenerated: {datetime.now(UTC).isoformat()}")

    # Summary
    passed = sum(1 for r in report.results if r.level == QualityLevel.PASS)
    warnings = sum(1 for r in report.results if r.level == QualityLevel.WARNING)
    failed = sum(1 for r in report.results if r.level == QualityLevel.FAIL)
    total = len(report.results)

    print(f"\nOverall: {passed}/{total} passed, {warnings} warnings, {failed} failures")

    # Field Completeness
    print("\n--- FIELD COMPLETENESS ---")
    fc = report.field_completeness
    print(f"Total LLM Interactions:    {fc.total_records}")
    print(f"Raw Response Rate:         {fc.raw_response_rate:.1%}")
    print(f"Enrichment Snapshot Rate:  {fc.enrichment_snapshot_rate:.1%}")
    print(f"Context Sources Rate:      {fc.context_sources_rate:.1%}")
    print(f"Household Matches Rate:    {fc.household_matches_rate:.1%}")

    # Risk Distribution
    print("\n--- RISK DISTRIBUTION ---")
    rd = report.risk_distribution
    print(f"Total Events:     {rd.total_events}")
    print(f"Mean Score:       {rd.mean_score:.1f}")
    print(f"Std Dev:          {rd.std_dev:.1f}")
    print(f"Range:            {rd.min_score:.0f} - {rd.max_score:.0f}")
    print(f"Levels Covered:   {rd.levels_covered}")
    if rd.level_counts:
        print("Level Distribution:")
        for level, count in sorted(rd.level_counts.items()):
            pct = count / rd.total_events * 100 if rd.total_events > 0 else 0
            print(f"  {level:12} {count:>5} ({pct:>5.1f}%)")

    # Reasoning Quality
    print("\n--- REASONING QUALITY ---")
    rq = report.reasoning_quality
    print(f"Avg Reasoning Length:      {rq.avg_reasoning_length:.0f} chars")
    print(f"Avg Summary Length:        {rq.avg_summary_length:.0f} chars")
    print(f"Reasoning Range:           {rq.min_reasoning_length} - {rq.max_reasoning_length}")
    print(f"Detection Reference Rate:  {rq.detection_reference_rate:.1%}")
    print(f"Risk Keyword Rate:         {rq.risk_keyword_rate:.1%}")

    # Serialization
    print("\n--- SERIALIZATION HEALTH ---")
    ser = report.serialization
    print(f"Python Repr Strings:       {ser.python_repr_count}")
    print(f"Invalid Arrays:            {ser.invalid_array_count}")
    print(f"Weather Serialization:     {'OK' if ser.weather_serialization_ok else 'FAIL'}")
    print(f"Faces Serialization:       {'OK' if ser.faces_serialization_ok else 'FAIL'}")
    print(f"Plates Serialization:      {'OK' if ser.plates_serialization_ok else 'FAIL'}")

    # Linkage
    print("\n--- EVENT LINKAGE ---")
    lk = report.linkage
    print(f"Total Events:              {lk.total_events}")
    print(f"With LLM Interaction:      {lk.events_with_interaction}")
    print(f"Coverage Rate:             {lk.coverage_rate:.1%}")
    print(f"Orphan Interactions:       {lk.orphan_interactions}")

    # Metric Results
    print("\n--- METRIC RESULTS ---")
    for result in report.results:
        icon = (
            "[PASS]"
            if result.level == QualityLevel.PASS
            else ("[WARN]" if result.level == QualityLevel.WARNING else "[FAIL]")
        )
        print(f"{icon} {result.name}: {result.value} (expected: {result.expected})")
        if result.details and result.level != QualityLevel.PASS:
            print(f"       {result.details}")

    print("\n" + "=" * 70)


def print_comparison_report(comparison: ComparisonReport) -> None:
    """Print formatted comparison report to console."""
    print("\n" + "=" * 70)
    print("AI QUALITY BASELINE COMPARISON")
    print("=" * 70)

    print(f"\nBaseline: {comparison.baseline_timestamp}")
    print(f"Current:  {comparison.current_timestamp}")

    if comparison.regressions:
        print(f"\n--- REGRESSIONS ({len(comparison.regressions)}) ---")
        for r in sorted(
            comparison.regressions, key=lambda x: (x.severity != "critical", x.metric_name)
        ):
            severity_icon = (
                "[CRITICAL]"
                if r.severity == "critical"
                else ("[WARNING]" if r.severity == "warning" else "[INFO]")
            )
            print(f"{severity_icon} {r.metric_name}")
            print(f"    Baseline: {r.baseline_value}")
            print(f"    Current:  {r.current_value}")
            print(f"    Note:     {r.details}")
    else:
        print("\nNo regressions detected!")

    if comparison.improvements:
        print(f"\n--- IMPROVEMENTS ({len(comparison.improvements)}) ---")
        for r in comparison.improvements:
            print(f"[OK] {r.metric_name}")
            print(f"    Baseline: {r.baseline_value} -> Current: {r.current_value}")

    print("\n" + "=" * 70)


def print_judge_report(evaluation: JudgeEvaluation) -> None:
    """Print formatted judge evaluation report to console."""
    print("\n" + "=" * 70)
    print("AI JUDGE REASONING EVALUATION")
    print("=" * 70)

    print("\n--- SCORES ---")
    print(f"Reasoning Coherence:    {evaluation.reasoning_coherence_score}/100")
    print(f"Detection Grounding:    {evaluation.detection_grounding_score}/100")
    print(f"Risk Calibration:       {evaluation.risk_calibration_score}/100")
    print(f"Overall Score:          {evaluation.overall_score}/100")

    if evaluation.strengths:
        print("\n--- STRENGTHS ---")
        for s in evaluation.strengths:
            print(f"  + {s}")

    if evaluation.weaknesses:
        print("\n--- WEAKNESSES ---")
        for w in evaluation.weaknesses:
            print(f"  - {w}")

    if evaluation.suggestions:
        print("\n--- SUGGESTIONS ---")
        for i, s in enumerate(evaluation.suggestions, 1):
            print(f"  {i}. {s}")

    if evaluation.sample_evaluations:
        print("\n--- SAMPLE EVALUATIONS ---")
        for sample in evaluation.sample_evaluations[:5]:
            print(
                f"  Event {sample.get('event_id')}: "
                f"Coherence={sample.get('coherence', 'N/A')}, "
                f"Grounding={sample.get('grounding', 'N/A')}, "
                f"Calibration={sample.get('calibration', 'N/A')}"
            )
            if sample.get("notes"):
                print(f"    Notes: {sample['notes'][:100]}")

    print("\n" + "=" * 70)


async def main() -> int:
    """Main entry point for AI quality analysis."""
    parser = argparse.ArgumentParser(
        description="AI Pipeline Quality Analysis Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Spawn Claude subagent for deep reasoning analysis",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=10,
        help="Number of samples to analyze with judge (default: 10)",
    )
    parser.add_argument(
        "--capture-baseline",
        action="store_true",
        help="Save current metrics as baseline",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare current metrics against baseline",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.05,
        help="Tolerance for regression detection (default: 0.05 = 5%%)",
    )
    parser.add_argument(
        "--create-linear-task",
        action="store_true",
        help="Create Linear task if regressions found",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for JSON report",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Minimal output (only errors and summary)",
    )

    args = parser.parse_args()

    # Initialize database connection
    try:
        await init_db()
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        print("Ensure the database is running and DATABASE_URL is correctly configured.")
        return 1

    # Collect metrics
    if not args.quiet:
        print("Collecting AI pipeline quality metrics...")

    async with get_session() as session:
        analyzer = AIQualityAnalyzer(session)
        report = await analyzer.collect_all_metrics()

    # Print basic report unless quiet
    if not args.quiet:
        print_report(report)

    exit_code = 0

    # Handle --capture-baseline
    if args.capture_baseline:
        baseline_path = capture_baseline(report)
        print(f"\nBaseline saved to: {baseline_path}")

    # Handle --compare
    if args.compare:
        try:
            comparison = compare_with_baseline(report, args.tolerance)
            if not args.quiet:
                print_comparison_report(comparison)

            if comparison.has_critical_regressions:
                print("\n[FAIL] Critical regressions detected!")
                exit_code = 1

            # Handle --create-linear-task
            if args.create_linear_task and comparison.total_regressions > 0:
                task_url = create_linear_task(comparison)
                if task_url:
                    print(f"\nLinear task created: {task_url}")

        except FileNotFoundError as e:
            print(f"\n[ERROR] {e}")
            print("Run with --capture-baseline first to create a baseline.")
            return 1

    # Handle --judge
    if args.judge:
        samples = await fetch_sample_reasoning(args.samples)
        if not samples:
            print("\n[WARN] No LLM interactions found for judge analysis")
        else:
            prompt = build_judge_prompt(samples)
            evaluation = run_judge_analysis(prompt)
            if not args.quiet:
                print_judge_report(evaluation)

            # Fail if overall score is too low
            if evaluation.overall_score < 50:
                print(f"\n[FAIL] Judge overall score too low: {evaluation.overall_score}/100")
                exit_code = 1

    # Handle --output
    if args.output:
        output_data = report_to_dict(report)
        output_path = Path(args.output).resolve()
        with output_path.open("w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nReport saved to: {output_path}")

    # Final summary
    if not report.passed:
        print("\n[FAIL] Quality check failed - see failures above")
        exit_code = 1
    elif exit_code == 0:
        print("\n[PASS] All quality checks passed")

    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
