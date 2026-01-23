#!/usr/bin/env python3
"""Replay historical events through the new prompt pipeline (NEM-3339).

This script provides infrastructure to replay historical events through the
new prompt pipeline and validate score distribution shifts. Part of NEM-3008
(Nemotron Prompt Improvements) Phase 7.3.

Usage:
    # Analyze all events from the last 30 days (dry-run, no LLM calls)
    python scripts/replay-historical-events.py --dry-run --days 30

    # Replay events through the new pipeline (requires running Nemotron service)
    python scripts/replay-historical-events.py --days 7 --limit 100

    # Analyze only high-risk events
    python scripts/replay-historical-events.py --risk-level high --days 14

    # Export results to JSON
    python scripts/replay-historical-events.py --output results.json --limit 50

Target Score Distribution:
    - LOW (score < 40): 50-60%
    - MEDIUM (40 <= score < 70): 30-40%
    - HIGH (score >= 70): 15-20%

Edge Cases that should maintain HIGH scores:
    - Weapon detections
    - Unknown person loitering
    - Nighttime activity
    - Multiple unknown persons
"""

import argparse
import asyncio
import json
import statistics
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class ReplayResult:
    """Result from replaying a single event through the new pipeline."""

    event_id: int
    camera_id: str
    camera_name: str
    original_risk_score: int | None
    original_risk_level: str | None
    new_risk_score: int | None
    new_risk_level: str | None
    score_diff: int
    detection_count: int
    object_types: str | None
    started_at: str
    summary: str | None
    replayed: bool
    error: str | None = None

    @property
    def score_decreased(self) -> bool:
        """Check if the new score is lower than the original."""
        if self.original_risk_score is None or self.new_risk_score is None:
            return False
        return self.new_risk_score < self.original_risk_score

    @property
    def score_increased(self) -> bool:
        """Check if the new score is higher than the original."""
        if self.original_risk_score is None or self.new_risk_score is None:
            return False
        return self.new_risk_score > self.original_risk_score


@dataclass
class ReplayStatistics:
    """Aggregated statistics from replaying multiple events."""

    total_events: int
    replayed_events: int
    failed_events: int
    low_count: int  # score < 40
    medium_count: int  # 40 <= score < 70
    high_count: int  # score >= 70
    mean_score: float
    median_score: float
    std_dev: float
    mean_score_diff: float
    scores_decreased_count: int
    scores_increased_count: int
    scores_unchanged_count: int
    object_type_distribution: dict[str, int]
    camera_distribution: dict[str, int]

    @property
    def low_percentage(self) -> float:
        """Percentage of events scoring LOW."""
        if self.replayed_events == 0:
            return 0.0
        return self.low_count / self.replayed_events * 100

    @property
    def medium_percentage(self) -> float:
        """Percentage of events scoring MEDIUM."""
        if self.replayed_events == 0:
            return 0.0
        return self.medium_count / self.replayed_events * 100

    @property
    def high_percentage(self) -> float:
        """Percentage of events scoring HIGH."""
        if self.replayed_events == 0:
            return 0.0
        return self.high_count / self.replayed_events * 100


def classify_risk_level(score: int) -> str:
    """Classify risk level based on score thresholds."""
    if score < 40:
        return "low"
    elif score < 70:
        return "medium"
    elif score < 90:
        return "high"
    else:
        return "critical"


def calculate_statistics(results: list[ReplayResult]) -> ReplayStatistics:
    """Calculate aggregate statistics from replay results."""
    replayed = [r for r in results if r.replayed and r.new_risk_score is not None]
    failed = [r for r in results if not r.replayed or r.error]

    if not replayed:
        return ReplayStatistics(
            total_events=len(results),
            replayed_events=0,
            failed_events=len(failed),
            low_count=0,
            medium_count=0,
            high_count=0,
            mean_score=0.0,
            median_score=0.0,
            std_dev=0.0,
            mean_score_diff=0.0,
            scores_decreased_count=0,
            scores_increased_count=0,
            scores_unchanged_count=0,
            object_type_distribution={},
            camera_distribution={},
        )

    scores = [r.new_risk_score for r in replayed if r.new_risk_score is not None]
    score_diffs = [
        r.score_diff
        for r in replayed
        if r.original_risk_score is not None and r.new_risk_score is not None
    ]

    low_count = sum(1 for s in scores if s < 40)
    medium_count = sum(1 for s in scores if 40 <= s < 70)
    high_count = sum(1 for s in scores if s >= 70)

    decreased = sum(1 for r in replayed if r.score_decreased)
    increased = sum(1 for r in replayed if r.score_increased)
    unchanged = len(replayed) - decreased - increased

    # Count object types
    object_types: Counter[str] = Counter()
    for r in replayed:
        if r.object_types:
            for obj in r.object_types.split(","):
                object_types[obj.strip()] += 1

    # Count cameras
    cameras: Counter[str] = Counter()
    for r in replayed:
        cameras[r.camera_name] += 1

    return ReplayStatistics(
        total_events=len(results),
        replayed_events=len(replayed),
        failed_events=len(failed),
        low_count=low_count,
        medium_count=medium_count,
        high_count=high_count,
        mean_score=statistics.mean(scores) if scores else 0.0,
        median_score=statistics.median(scores) if scores else 0.0,
        std_dev=statistics.stdev(scores) if len(scores) > 1 else 0.0,
        mean_score_diff=statistics.mean(score_diffs) if score_diffs else 0.0,
        scores_decreased_count=decreased,
        scores_increased_count=increased,
        scores_unchanged_count=unchanged,
        object_type_distribution=dict(object_types),
        camera_distribution=dict(cameras),
    )


async def fetch_historical_events(
    days: int = 30,
    limit: int | None = None,
    risk_level: str | None = None,
    camera_id: str | None = None,
) -> list[dict]:
    """Fetch historical events from the database.

    Args:
        days: Number of days to look back
        limit: Maximum number of events to fetch
        risk_level: Filter by risk level (low, medium, high, critical)
        camera_id: Filter by specific camera ID

    Returns:
        List of event dictionaries with related data
    """
    from backend.core.database import get_session
    from backend.models.event import Event
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    cutoff = datetime.now(UTC) - timedelta(days=days)
    events_data = []

    async with get_session() as session:
        # Build query
        stmt = (
            select(Event)
            .options(selectinload(Event.detections), selectinload(Event.camera))
            .where(Event.started_at >= cutoff)
            .where(Event.deleted_at.is_(None))  # Exclude soft-deleted
        )

        if risk_level:
            stmt = stmt.where(Event.risk_level == risk_level)

        if camera_id:
            stmt = stmt.where(Event.camera_id == camera_id)

        stmt = stmt.order_by(Event.started_at.desc())

        if limit:
            stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        events = list(result.scalars().all())

        for event in events:
            # Extract detection data
            detection_ids = [d.id for d in event.detections]

            events_data.append(
                {
                    "id": event.id,
                    "batch_id": event.batch_id,
                    "camera_id": event.camera_id,
                    "camera_name": event.camera.name if event.camera else event.camera_id,
                    "started_at": event.started_at.isoformat(),
                    "ended_at": event.ended_at.isoformat() if event.ended_at else None,
                    "risk_score": event.risk_score,
                    "risk_level": event.risk_level,
                    "summary": event.summary,
                    "object_types": event.object_types,
                    "detection_count": len(detection_ids),
                    "detection_ids": detection_ids,
                }
            )

    return events_data


async def replay_event(
    event_data: dict,
    analyzer,
    dry_run: bool = False,
) -> ReplayResult:
    """Replay a single event through the new prompt pipeline.

    Args:
        event_data: Event data dictionary from fetch_historical_events
        analyzer: NemotronAnalyzer instance
        dry_run: If True, don't actually call the LLM

    Returns:
        ReplayResult with comparison data
    """
    import uuid

    if dry_run:
        # In dry-run mode, return original scores
        return ReplayResult(
            event_id=event_data["id"],
            camera_id=event_data["camera_id"],
            camera_name=event_data["camera_name"],
            original_risk_score=event_data["risk_score"],
            original_risk_level=event_data["risk_level"],
            new_risk_score=event_data["risk_score"],  # Same as original in dry-run
            new_risk_level=event_data["risk_level"],
            score_diff=0,
            detection_count=event_data["detection_count"],
            object_types=event_data["object_types"],
            started_at=event_data["started_at"],
            summary=event_data["summary"],
            replayed=False,
        )

    try:
        # Create a new batch ID for the replay
        replay_batch_id = f"replay_{event_data['id']}_{uuid.uuid4().hex[:8]}"

        # Run analysis with the same detection IDs
        new_event = await analyzer.analyze_batch(
            batch_id=replay_batch_id,
            camera_id=event_data["camera_id"],
            detection_ids=event_data["detection_ids"],
        )

        original_score = event_data["risk_score"] or 0
        new_score = new_event.risk_score or 0
        score_diff = abs(new_score - original_score)

        return ReplayResult(
            event_id=event_data["id"],
            camera_id=event_data["camera_id"],
            camera_name=event_data["camera_name"],
            original_risk_score=event_data["risk_score"],
            original_risk_level=event_data["risk_level"],
            new_risk_score=new_event.risk_score,
            new_risk_level=new_event.risk_level,
            score_diff=score_diff,
            detection_count=event_data["detection_count"],
            object_types=event_data["object_types"],
            started_at=event_data["started_at"],
            summary=new_event.summary,
            replayed=True,
        )

    except Exception as e:
        return ReplayResult(
            event_id=event_data["id"],
            camera_id=event_data["camera_id"],
            camera_name=event_data["camera_name"],
            original_risk_score=event_data["risk_score"],
            original_risk_level=event_data["risk_level"],
            new_risk_score=None,
            new_risk_level=None,
            score_diff=0,
            detection_count=event_data["detection_count"],
            object_types=event_data["object_types"],
            started_at=event_data["started_at"],
            summary=None,
            replayed=False,
            error=str(e),
        )


def print_report(stats: ReplayStatistics, results: list[ReplayResult]) -> None:
    """Print a formatted report of replay results."""
    print("\n" + "=" * 60)
    print("HISTORICAL EVENT REPLAY ANALYSIS REPORT")
    print("=" * 60)

    print(f"\nTotal Events Analyzed: {stats.total_events}")
    print(f"Successfully Replayed: {stats.replayed_events}")
    print(f"Failed/Skipped:        {stats.failed_events}")

    print("\n--- SCORE DISTRIBUTION (Target: 50-60% LOW, 30-40% MED, 15-20% HIGH) ---")
    print(f"LOW    (< 40):  {stats.low_count:>4} ({stats.low_percentage:>5.1f}%)")
    print(f"MEDIUM (40-69): {stats.medium_count:>4} ({stats.medium_percentage:>5.1f}%)")
    print(f"HIGH   (>= 70): {stats.high_count:>4} ({stats.high_percentage:>5.1f}%)")

    # Target validation
    print("\n--- TARGET VALIDATION ---")
    low_ok = 50 <= stats.low_percentage <= 60
    med_ok = 30 <= stats.medium_percentage <= 40
    high_ok = 15 <= stats.high_percentage <= 20

    print(f"LOW in range:    {'PASS' if low_ok else 'FAIL'} (target: 50-60%)")
    print(f"MEDIUM in range: {'PASS' if med_ok else 'FAIL'} (target: 30-40%)")
    print(f"HIGH in range:   {'PASS' if high_ok else 'FAIL'} (target: 15-20%)")

    print("\n--- SCORE STATISTICS ---")
    print(f"Mean Score:   {stats.mean_score:.1f}")
    print(f"Median Score: {stats.median_score:.1f}")
    print(f"Std Dev:      {stats.std_dev:.1f}")
    print(f"Mean Diff:    {stats.mean_score_diff:.1f}")

    print("\n--- SCORE CHANGES ---")
    print(f"Decreased: {stats.scores_decreased_count:>4}")
    print(f"Increased: {stats.scores_increased_count:>4}")
    print(f"Unchanged: {stats.scores_unchanged_count:>4}")

    print("\n--- TOP OBJECT TYPES ---")
    sorted_objects = sorted(
        stats.object_type_distribution.items(), key=lambda x: x[1], reverse=True
    )
    for obj, count in sorted_objects[:10]:
        print(f"  {obj}: {count}")

    print("\n--- TOP CAMERAS ---")
    sorted_cameras = sorted(stats.camera_distribution.items(), key=lambda x: x[1], reverse=True)
    for cam, count in sorted_cameras[:10]:
        print(f"  {cam}: {count}")

    # Show edge cases (events that increased in score or remained HIGH)
    edge_cases = [
        r for r in results if r.replayed and r.new_risk_score is not None and r.new_risk_score >= 70
    ]
    if edge_cases:
        print(f"\n--- HIGH SCORE EDGE CASES ({len(edge_cases)} events) ---")
        for ec in edge_cases[:10]:
            print(
                f"  Event {ec.event_id}: {ec.original_risk_score} -> {ec.new_risk_score} "
                f"({ec.object_types})"
            )

    print("\n" + "=" * 60)


async def main():
    """Main entry point for the replay script."""
    parser = argparse.ArgumentParser(
        description="Replay historical events through new prompt pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to look back (default: 30)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of events to analyze",
    )
    parser.add_argument(
        "--risk-level",
        type=str,
        choices=["low", "medium", "high", "critical"],
        help="Filter by risk level",
    )
    parser.add_argument(
        "--camera-id",
        type=str,
        help="Filter by camera ID",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't call LLM, just analyze existing scores",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for JSON results",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    print(f"Fetching events from last {args.days} days...")
    events = await fetch_historical_events(
        days=args.days,
        limit=args.limit,
        risk_level=args.risk_level,
        camera_id=args.camera_id,
    )

    if not events:
        print("No events found matching criteria.")
        return 1

    print(f"Found {len(events)} events to analyze")

    # Setup analyzer for non-dry-run mode
    analyzer = None
    if not args.dry_run:
        from backend.core.redis import get_redis_client
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        redis_client = await get_redis_client()
        analyzer = NemotronAnalyzer(redis_client=redis_client)

    # Replay events
    results: list[ReplayResult] = []
    for i, event in enumerate(events, 1):
        if args.verbose:
            print(f"Processing event {i}/{len(events)} (ID: {event['id']})...", end=" ")

        result = await replay_event(event, analyzer, dry_run=args.dry_run)
        results.append(result)

        if args.verbose:
            if result.replayed:
                print(f"OK (score: {result.original_risk_score} -> {result.new_risk_score})")
            elif result.error:
                print(f"ERROR: {result.error}")
            else:
                print("SKIPPED")

    # Calculate statistics
    stats = calculate_statistics(results)

    # Print report
    print_report(stats, results)

    # Save to file if requested
    if args.output:
        output_data = {
            "generated_at": datetime.now(UTC).isoformat(),
            "parameters": {
                "days": args.days,
                "limit": args.limit,
                "risk_level": args.risk_level,
                "camera_id": args.camera_id,
                "dry_run": args.dry_run,
            },
            "statistics": {
                "total_events": stats.total_events,
                "replayed_events": stats.replayed_events,
                "failed_events": stats.failed_events,
                "low_count": stats.low_count,
                "low_percentage": stats.low_percentage,
                "medium_count": stats.medium_count,
                "medium_percentage": stats.medium_percentage,
                "high_count": stats.high_count,
                "high_percentage": stats.high_percentage,
                "mean_score": stats.mean_score,
                "median_score": stats.median_score,
                "std_dev": stats.std_dev,
                "mean_score_diff": stats.mean_score_diff,
                "scores_decreased": stats.scores_decreased_count,
                "scores_increased": stats.scores_increased_count,
                "scores_unchanged": stats.scores_unchanged_count,
                "object_type_distribution": stats.object_type_distribution,
                "camera_distribution": stats.camera_distribution,
            },
            "results": [asdict(r) for r in results],
        }

        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults saved to: {args.output}")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
