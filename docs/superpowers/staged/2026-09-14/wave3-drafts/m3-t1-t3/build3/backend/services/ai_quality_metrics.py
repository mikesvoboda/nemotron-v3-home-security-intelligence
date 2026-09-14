"""AI Pipeline Quality Metrics Library.

Shared metrics collection and analysis for AI pipeline quality testing.
Used by CI smoke tests, nightly regression suites, and local analysis scripts.

Metrics Categories:
    - Field completeness: Required fields populated
    - Risk distribution: Score spread across severity levels
    - Reasoning quality: Length, structure, content patterns
    - Serialization: Proper JSON, no Python repr strings
    - Linkage: Event-to-LLMInteraction integrity
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.event import Event
from backend.models.llm_interaction import LLMInteraction


class QualityLevel(Enum):
    """Quality assessment levels."""

    PASS = "pass"  # noqa: S105 - not a password, it's an enum value
    WARNING = "warning"
    FAIL = "fail"


@dataclass
class MetricResult:
    """Result of a single metric evaluation."""

    name: str
    value: float | int | bool
    expected: float | int | bool | None = None
    level: QualityLevel = QualityLevel.PASS
    details: str = ""

    @property
    def passed(self) -> bool:
        return self.level == QualityLevel.PASS


@dataclass
class FieldCompletenessMetrics:
    """Metrics for required field population rates."""

    total_records: int = 0
    raw_response_rate: float = 0.0
    enrichment_snapshot_rate: float = 0.0
    context_sources_rate: float = 0.0
    household_matches_rate: float = 0.0  # Often null, not required


@dataclass
class RiskDistributionMetrics:
    """Metrics for risk score distribution."""

    total_events: int = 0
    mean_score: float = 0.0
    std_dev: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0
    levels_covered: int = 0
    level_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class ReasoningQualityMetrics:
    """Metrics for LLM reasoning quality."""

    avg_reasoning_length: float = 0.0
    avg_summary_length: float = 0.0
    min_reasoning_length: int = 0
    max_reasoning_length: int = 0
    detection_reference_rate: float = 0.0  # % that reference detections
    risk_keyword_rate: float = 0.0  # % with risk/threat keywords


@dataclass
class SerializationMetrics:
    """Metrics for proper JSON serialization."""

    python_repr_count: int = 0  # Count of "ClassName(...)" strings
    invalid_array_count: int = 0  # Arrays stored as strings
    weather_serialization_ok: bool = True
    faces_serialization_ok: bool = True
    plates_serialization_ok: bool = True


@dataclass
class LinkageMetrics:
    """Metrics for event-to-LLMInteraction linkage."""

    total_events: int = 0
    events_with_interaction: int = 0
    orphan_interactions: int = 0  # LLMInteractions without valid event
    coverage_rate: float = 0.0


@dataclass
class QualityReport:
    """Complete quality analysis report."""

    field_completeness: FieldCompletenessMetrics
    risk_distribution: RiskDistributionMetrics
    reasoning_quality: ReasoningQualityMetrics
    serialization: SerializationMetrics
    linkage: LinkageMetrics
    results: list[MetricResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Check if all critical metrics passed."""
        return all(r.passed for r in self.results if r.level != QualityLevel.WARNING)

    @property
    def summary(self) -> str:
        """Generate human-readable summary."""
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        failed = [r for r in self.results if r.level == QualityLevel.FAIL]
        warnings = [r for r in self.results if r.level == QualityLevel.WARNING]

        lines = [
            f"Quality Report: {passed}/{total} checks passed",
            "",
        ]

        if failed:
            lines.append("FAILURES:")
            for r in failed:
                lines.append(f"  - {r.name}: {r.value} (expected {r.expected})")
                if r.details:
                    lines.append(f"    {r.details}")
            lines.append("")

        if warnings:
            lines.append("WARNINGS:")
            for r in warnings:
                lines.append(f"  - {r.name}: {r.value}")
                if r.details:
                    lines.append(f"    {r.details}")

        return "\n".join(lines)


class AIQualityAnalyzer:
    """Analyzes AI pipeline quality metrics from database."""

    # Patterns for reasoning quality analysis
    DETECTION_PATTERNS: ClassVar[list[str]] = [
        r"detection\s*(id|ID)?\s*\d+",
        r"ID\s*\d+",
        r"person|vehicle|animal",
    ]
    RISK_KEYWORDS: ClassVar[list[str]] = [
        r"risk",
        r"threat",
        r"suspicious",
        r"concern",
        r"danger",
        r"warning",
        r"alert",
    ]
    PYTHON_REPR_PATTERN: ClassVar[str] = r"[A-Z][a-zA-Z]+Result\s*\("

    def __init__(self, session: AsyncSession):
        self.session = session

    async def collect_all_metrics(self) -> QualityReport:
        """Collect all quality metrics and generate report."""
        field_metrics = await self.collect_field_completeness()
        risk_metrics = await self.collect_risk_distribution()
        reasoning_metrics = await self.collect_reasoning_quality()
        serialization_metrics = await self.collect_serialization_metrics()
        linkage_metrics = await self.collect_linkage_metrics()

        report = QualityReport(
            field_completeness=field_metrics,
            risk_distribution=risk_metrics,
            reasoning_quality=reasoning_metrics,
            serialization=serialization_metrics,
            linkage=linkage_metrics,
        )

        # Evaluate against thresholds
        report.results = self._evaluate_metrics(report)

        return report

    async def collect_field_completeness(self) -> FieldCompletenessMetrics:
        """Collect field population metrics."""
        query = select(
            func.count().label("total"),
            func.count(LLMInteraction.raw_response).label("has_response"),
            func.count(LLMInteraction.enrichment_snapshot).label("has_snapshot"),
            func.count(LLMInteraction.context_sources).label("has_context"),
            func.count(LLMInteraction.household_matches).label("has_matches"),
        )
        result = await self.session.execute(query)
        row = result.one()

        total = row.total or 1  # Avoid division by zero

        return FieldCompletenessMetrics(
            total_records=row.total,
            raw_response_rate=row.has_response / total,
            enrichment_snapshot_rate=row.has_snapshot / total,
            context_sources_rate=row.has_context / total,
            household_matches_rate=row.has_matches / total,
        )

    async def collect_risk_distribution(self) -> RiskDistributionMetrics:
        """Collect risk score distribution metrics."""
        query = select(Event.risk_score, Event.risk_level).where(Event.deleted_at.is_(None))
        result = await self.session.execute(query)
        rows = result.all()

        if not rows:
            return RiskDistributionMetrics()

        scores = [r.risk_score for r in rows if r.risk_score is not None]
        levels = [r.risk_level for r in rows if r.risk_level]

        level_counts: dict[str, int] = {}
        for level in levels:
            level_counts[level] = level_counts.get(level, 0) + 1

        return RiskDistributionMetrics(
            total_events=len(rows),
            mean_score=statistics.mean(scores) if scores else 0.0,
            std_dev=statistics.stdev(scores) if len(scores) > 1 else 0.0,
            min_score=min(scores) if scores else 0.0,
            max_score=max(scores) if scores else 0.0,
            levels_covered=len(level_counts),
            level_counts=level_counts,
        )

    async def collect_reasoning_quality(self) -> ReasoningQualityMetrics:
        """Collect reasoning quality metrics."""
        query = select(LLMInteraction.raw_response)
        result = await self.session.execute(query)
        rows = result.all()

        if not rows:
            return ReasoningQualityMetrics()

        reasoning_lengths: list[int] = []
        summary_lengths: list[int] = []
        detection_refs = 0
        risk_keywords = 0

        for row in rows:
            if not row.raw_response:
                continue

            response = row.raw_response
            if isinstance(response, str):
                import json

                try:
                    response = json.loads(response)
                except json.JSONDecodeError:
                    continue

            reasoning = response.get("reasoning", "")
            summary = response.get("summary", "")

            reasoning_lengths.append(len(reasoning))
            summary_lengths.append(len(summary))

            # Check for detection references
            if any(re.search(p, reasoning, re.IGNORECASE) for p in self.DETECTION_PATTERNS):
                detection_refs += 1

            # Check for risk keywords
            if any(re.search(p, reasoning, re.IGNORECASE) for p in self.RISK_KEYWORDS):
                risk_keywords += 1

        total = len(rows) or 1

        return ReasoningQualityMetrics(
            avg_reasoning_length=statistics.mean(reasoning_lengths) if reasoning_lengths else 0.0,
            avg_summary_length=statistics.mean(summary_lengths) if summary_lengths else 0.0,
            min_reasoning_length=min(reasoning_lengths) if reasoning_lengths else 0,
            max_reasoning_length=max(reasoning_lengths) if reasoning_lengths else 0,
            detection_reference_rate=detection_refs / total,
            risk_keyword_rate=risk_keywords / total,
        )

    async def collect_serialization_metrics(self) -> SerializationMetrics:
        """Check for serialization issues (Python repr strings, etc)."""
        query = select(LLMInteraction.enrichment_snapshot)
        result = await self.session.execute(query)
        rows = result.all()

        python_repr_count = 0
        invalid_array_count = 0
        weather_ok = True
        faces_ok = True
        plates_ok = True

        for row in rows:
            snapshot = row.enrichment_snapshot
            if not snapshot:
                continue

            # Check weather field for Python repr
            weather = snapshot.get("weather")
            if weather and isinstance(weather, str):
                if re.search(self.PYTHON_REPR_PATTERN, weather):
                    python_repr_count += 1
                    weather_ok = False

            # Check faces array
            faces = snapshot.get("faces")
            if faces is not None and not isinstance(faces, list):
                invalid_array_count += 1
                faces_ok = False

            # Check license_plates array
            plates = snapshot.get("license_plates")
            if plates is not None and not isinstance(plates, list):
                invalid_array_count += 1
                plates_ok = False

        return SerializationMetrics(
            python_repr_count=python_repr_count,
            invalid_array_count=invalid_array_count,
            weather_serialization_ok=weather_ok,
            faces_serialization_ok=faces_ok,
            plates_serialization_ok=plates_ok,
        )

    async def collect_linkage_metrics(self) -> LinkageMetrics:
        """Check event-to-LLMInteraction linkage integrity."""
        # Count events
        event_count_query = (
            select(func.count()).select_from(Event).where(Event.deleted_at.is_(None))
        )
        event_result = await self.session.execute(event_count_query)
        total_events = event_result.scalar() or 0

        # Count events with LLMInteraction
        linked_query = text("""
            SELECT COUNT(DISTINCT e.id)
            FROM events e
            INNER JOIN llm_interactions l ON e.id = l.event_id
            WHERE e.deleted_at IS NULL
        """)
        linked_result = await self.session.execute(linked_query)
        events_with_interaction = linked_result.scalar() or 0

        # Count orphan LLMInteractions
        orphan_query = text("""
            SELECT COUNT(*)
            FROM llm_interactions l
            LEFT JOIN events e ON l.event_id = e.id
            WHERE e.id IS NULL OR e.deleted_at IS NOT NULL
        """)
        orphan_result = await self.session.execute(orphan_query)
        orphan_count = orphan_result.scalar() or 0

        coverage = events_with_interaction / total_events if total_events > 0 else 0.0

        return LinkageMetrics(
            total_events=total_events,
            events_with_interaction=events_with_interaction,
            orphan_interactions=orphan_count,
            coverage_rate=coverage,
        )

    def _evaluate_metrics(self, report: QualityReport) -> list[MetricResult]:
        """Evaluate metrics against quality thresholds."""
        results = []

        # Field completeness checks
        results.append(
            MetricResult(
                name="raw_response_rate",
                value=report.field_completeness.raw_response_rate,
                expected=1.0,
                level=(
                    QualityLevel.PASS
                    if report.field_completeness.raw_response_rate >= 1.0
                    else QualityLevel.FAIL
                ),
                details="All LLMInteraction records must have raw_response",
            )
        )

        results.append(
            MetricResult(
                name="enrichment_snapshot_rate",
                value=report.field_completeness.enrichment_snapshot_rate,
                expected=1.0,
                level=(
                    QualityLevel.PASS
                    if report.field_completeness.enrichment_snapshot_rate >= 1.0
                    else QualityLevel.FAIL
                ),
                details="All LLMInteraction records must have enrichment_snapshot",
            )
        )

        # Risk distribution checks
        results.append(
            MetricResult(
                name="risk_levels_covered",
                value=report.risk_distribution.levels_covered,
                expected=3,
                level=(
                    QualityLevel.PASS
                    if report.risk_distribution.levels_covered >= 3
                    else QualityLevel.WARNING
                ),
                details=f"Levels present: {list(report.risk_distribution.level_counts.keys())}",
            )
        )

        results.append(
            MetricResult(
                name="risk_score_std_dev",
                value=round(report.risk_distribution.std_dev, 2),
                expected=15.0,
                level=(
                    QualityLevel.PASS
                    if report.risk_distribution.std_dev >= 15.0
                    else QualityLevel.WARNING
                ),
                details="Risk scores should have meaningful spread",
            )
        )

        # Reasoning quality checks
        results.append(
            MetricResult(
                name="avg_reasoning_length",
                value=int(report.reasoning_quality.avg_reasoning_length),
                expected=200,
                level=(
                    QualityLevel.PASS
                    if report.reasoning_quality.avg_reasoning_length >= 200
                    else QualityLevel.WARNING
                ),
                details="Reasoning should be substantive",
            )
        )

        results.append(
            MetricResult(
                name="detection_reference_rate",
                value=round(report.reasoning_quality.detection_reference_rate, 2),
                expected=0.5,
                level=(
                    QualityLevel.PASS
                    if report.reasoning_quality.detection_reference_rate >= 0.5
                    else QualityLevel.WARNING
                ),
                details="Reasoning should reference specific detections",
            )
        )

        # Serialization checks
        results.append(
            MetricResult(
                name="python_repr_count",
                value=report.serialization.python_repr_count,
                expected=0,
                level=(
                    QualityLevel.PASS
                    if report.serialization.python_repr_count == 0
                    else QualityLevel.FAIL
                ),
                details="No Python repr strings in JSON fields",
            )
        )

        results.append(
            MetricResult(
                name="weather_serialization",
                value=report.serialization.weather_serialization_ok,
                expected=True,
                level=(
                    QualityLevel.PASS
                    if report.serialization.weather_serialization_ok
                    else QualityLevel.FAIL
                ),
                details="Weather must be proper JSON object, not string",
            )
        )

        # Linkage checks
        results.append(
            MetricResult(
                name="event_coverage_rate",
                value=round(report.linkage.coverage_rate, 2),
                expected=1.0,
                level=(
                    QualityLevel.PASS if report.linkage.coverage_rate >= 1.0 else QualityLevel.FAIL
                ),
                details="All events should have LLMInteraction record",
            )
        )

        results.append(
            MetricResult(
                name="orphan_interactions",
                value=report.linkage.orphan_interactions,
                expected=0,
                level=(
                    QualityLevel.PASS
                    if report.linkage.orphan_interactions == 0
                    else QualityLevel.WARNING
                ),
                details="LLMInteractions should have valid event references",
            )
        )

        return results


async def analyze_quality(session: AsyncSession) -> QualityReport:
    """Convenience function to run full quality analysis."""
    analyzer = AIQualityAnalyzer(session)
    return await analyzer.collect_all_metrics()
