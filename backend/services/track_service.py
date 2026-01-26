"""Track service for managing object track trajectories.

This module provides the TrackService class for managing track lifecycle,
including creating/updating tracks with new positions, calculating movement
metrics, and querying track history.

Tracks represent the movement path of detected objects across video frames,
enabling motion analysis, trajectory prediction, and behavioral analysis.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.track import (
    MovementMetrics,
    TrackHistoryResponse,
    TrackListResponse,
    TrackResponse,
    TrajectoryPoint,
)
from backend.core.logging import get_logger
from backend.models.track import Track

logger = get_logger(__name__)

# Default configuration for track management
DEFAULT_MAX_TRAJECTORY_POINTS = 100
DEFAULT_TRACK_RETENTION_HOURS = 24


class TrackService:
    """Service for managing object tracks and trajectories.

    This service provides methods for:
    - Creating new tracks or updating existing ones with new positions
    - Retrieving track history with full trajectory data
    - Querying tracks with filters and pagination
    - Calculating movement metrics from trajectory points
    - Managing trajectory buffer size and pruning old tracks

    Attributes:
        db: The async database session for operations.
        max_trajectory_points: Maximum number of points to keep in trajectory buffer.
        track_retention_hours: How long to keep tracks before pruning.
    """

    def __init__(
        self,
        db: AsyncSession,
        max_trajectory_points: int = DEFAULT_MAX_TRAJECTORY_POINTS,
        track_retention_hours: int = DEFAULT_TRACK_RETENTION_HOURS,
    ) -> None:
        """Initialize the track service.

        Args:
            db: An async SQLAlchemy session for database operations.
            max_trajectory_points: Maximum number of points to keep in trajectory
                buffer. Older points are pruned when limit is exceeded. Default: 100.
            track_retention_hours: Hours to retain tracks before they can be pruned.
                Default: 24 hours.
        """
        self.db = db
        self.max_trajectory_points = max_trajectory_points
        self.track_retention_hours = track_retention_hours

    async def create_or_update_track(
        self,
        track_id: int,
        camera_id: str,
        object_class: str,
        position: tuple[float, float],
        timestamp: datetime,
        reid_embedding: bytes | None = None,
    ) -> Track:
        """Create a new track or update existing one with a new position.

        This method handles the upsert logic for tracks:
        - If no track exists for (track_id, camera_id), creates a new one
        - If a track exists, appends the new position to the trajectory

        The trajectory buffer is automatically pruned to keep only the last
        N points (configurable via max_trajectory_points).

        Args:
            track_id: Track ID from the tracker (unique within a camera session).
            camera_id: ID of the camera that captured this track.
            object_class: Detected object class (e.g., 'person', 'car').
            position: Tuple of (x, y) coordinates in pixels.
            timestamp: Timestamp of the position observation.
            reid_embedding: Optional re-identification embedding bytes for
                cross-camera tracking.

        Returns:
            The created or updated Track instance.

        Example:
            track = await service.create_or_update_track(
                track_id=42,
                camera_id="front_door",
                object_class="person",
                position=(640.5, 480.2),
                timestamp=datetime.now(UTC),
            )
        """
        x, y = position
        trajectory_point = {
            "x": x,
            "y": y,
            "timestamp": timestamp.isoformat(),
        }

        # Try to find existing track
        stmt = select(Track).where(
            Track.track_id == track_id,
            Track.camera_id == camera_id,
        )
        result = await self.db.execute(stmt)
        existing_track = result.scalar_one_or_none()

        if existing_track is None:
            # Create new track
            track = Track(
                track_id=track_id,
                camera_id=camera_id,
                object_class=object_class,
                first_seen=timestamp,
                last_seen=timestamp,
                trajectory=[trajectory_point],
                reid_embedding=reid_embedding,
            )
            self.db.add(track)
            await self.db.flush()
            await self.db.refresh(track)

            logger.debug(
                f"Created new track {track_id} for camera {camera_id}",
                extra={
                    "track_id": track_id,
                    "camera_id": camera_id,
                    "object_class": object_class,
                },
            )
            return track

        # Update existing track
        trajectory = list(existing_track.trajectory)
        trajectory.append(trajectory_point)

        # Prune trajectory if it exceeds the maximum points
        if len(trajectory) > self.max_trajectory_points:
            trajectory = trajectory[-self.max_trajectory_points :]
            logger.debug(
                f"Pruned trajectory for track {track_id} to {self.max_trajectory_points} points",
                extra={"track_id": track_id, "camera_id": camera_id},
            )

        existing_track.trajectory = trajectory
        existing_track.last_seen = timestamp

        # Update re-id embedding if provided (newer embedding takes precedence)
        if reid_embedding is not None:
            existing_track.reid_embedding = reid_embedding

        # Recalculate metrics with updated trajectory
        metrics = self.calculate_metrics(trajectory)
        existing_track.total_distance = metrics.total_distance
        existing_track.avg_speed = metrics.avg_speed

        await self.db.flush()
        await self.db.refresh(existing_track)

        logger.debug(
            f"Updated track {track_id} with new position, total points: {len(trajectory)}",
            extra={
                "track_id": track_id,
                "camera_id": camera_id,
                "trajectory_length": len(trajectory),
                "total_distance": metrics.total_distance,
            },
        )

        return existing_track

    async def get_track(self, track_id: int, camera_id: str) -> Track | None:
        """Get a track by track_id and camera_id.

        Args:
            track_id: Track ID from the tracker.
            camera_id: Camera ID where the track was observed.

        Returns:
            The Track if found, None otherwise.

        Example:
            track = await service.get_track(track_id=42, camera_id="front_door")
            if track:
                print(f"Track has {len(track.trajectory)} points")
        """
        stmt = select(Track).where(
            Track.track_id == track_id,
            Track.camera_id == camera_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_track_history(
        self,
        track_id: int,
        camera_id: str,
    ) -> TrackHistoryResponse | None:
        """Get full track history with trajectory and metrics.

        This method returns the complete trajectory data and computed
        movement metrics, suitable for visualization and analysis.

        Args:
            track_id: Track ID from the tracker.
            camera_id: Camera ID where the track was observed.

        Returns:
            TrackHistoryResponse with full trajectory and metrics,
            or None if track not found.

        Example:
            history = await service.get_track_history(
                track_id=42, camera_id="front_door"
            )
            if history:
                for point in history.trajectory:
                    print(f"({point.x}, {point.y}) at {point.timestamp}")
        """
        track = await self.get_track(track_id, camera_id)
        if track is None:
            return None

        # Convert trajectory to TrajectoryPoint objects
        trajectory_points = [
            TrajectoryPoint(
                x=point["x"],
                y=point["y"],
                timestamp=datetime.fromisoformat(point["timestamp"]),
            )
            for point in track.trajectory
        ]

        # Calculate metrics from trajectory
        metrics = self.calculate_metrics(track.trajectory)

        return TrackHistoryResponse(
            id=track.id,
            track_id=track.track_id,
            camera_id=track.camera_id,
            object_class=track.object_class,
            first_seen=track.first_seen,
            last_seen=track.last_seen,
            trajectory=trajectory_points,
            metrics=metrics,
        )

    async def get_tracks_by_camera(
        self,
        camera_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        object_class: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> TrackListResponse:
        """Get paginated tracks for a camera with optional filters.

        Args:
            camera_id: Camera ID to filter by.
            start_time: Optional start time filter (inclusive).
            end_time: Optional end time filter (inclusive).
            object_class: Optional filter by object class (e.g., 'person').
            page: Page number (1-indexed). Default: 1.
            page_size: Number of items per page. Default: 50, max: 1000.

        Returns:
            TrackListResponse with paginated tracks and total count.

        Example:
            response = await service.get_tracks_by_camera(
                camera_id="front_door",
                start_time=datetime.now(UTC) - timedelta(hours=1),
                object_class="person",
                page=1,
                page_size=25,
            )
            print(f"Found {response.total} tracks")
        """
        # Validate pagination parameters
        page = max(1, page)
        page_size = max(1, min(page_size, 1000))
        offset = (page - 1) * page_size

        # Build base query with filters
        base_query = select(Track).where(Track.camera_id == camera_id)

        if start_time is not None:
            base_query = base_query.where(Track.first_seen >= start_time)

        if end_time is not None:
            base_query = base_query.where(Track.first_seen <= end_time)

        if object_class is not None:
            base_query = base_query.where(Track.object_class == object_class)

        # Count total matching tracks
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Fetch paginated tracks ordered by first_seen descending (newest first)
        paginated_query = (
            base_query.order_by(Track.first_seen.desc()).offset(offset).limit(page_size)
        )
        result = await self.db.execute(paginated_query)
        tracks = list(result.scalars().all())

        # Convert to response models
        track_responses = []
        for track in tracks:
            metrics = None
            if track.total_distance is not None and track.avg_speed is not None:
                # Use stored metrics if available
                trajectory = track.trajectory or []
                metrics = self.calculate_metrics(trajectory)
            elif track.trajectory:
                # Calculate metrics on the fly
                metrics = self.calculate_metrics(track.trajectory)

            track_responses.append(
                TrackResponse(
                    id=track.id,
                    track_id=track.track_id,
                    camera_id=track.camera_id,
                    object_class=track.object_class,
                    first_seen=track.first_seen,
                    last_seen=track.last_seen,
                    metrics=metrics,
                )
            )

        return TrackListResponse(
            tracks=track_responses,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def prune_old_tracks(self, retention_hours: int | None = None) -> int:
        """Prune tracks older than the retention period.

        This method deletes tracks where last_seen is older than the
        specified retention period. Use this for periodic cleanup.

        Args:
            retention_hours: Hours to retain tracks. If None, uses the
                instance's track_retention_hours setting.

        Returns:
            Number of tracks deleted.

        Example:
            deleted_count = await service.prune_old_tracks(retention_hours=48)
            print(f"Pruned {deleted_count} old tracks")
        """
        if retention_hours is None:
            retention_hours = self.track_retention_hours

        cutoff_time = datetime.now(UTC) - timedelta(hours=retention_hours)

        stmt = delete(Track).where(Track.last_seen < cutoff_time)
        result = await self.db.execute(stmt)
        deleted_count: int = result.rowcount or 0  # type: ignore[attr-defined]

        if deleted_count > 0:
            logger.info(
                f"Pruned {deleted_count} tracks older than {retention_hours} hours",
                extra={
                    "deleted_count": deleted_count,
                    "retention_hours": retention_hours,
                    "cutoff_time": cutoff_time.isoformat(),
                },
            )

        return deleted_count

    @staticmethod
    def calculate_metrics(trajectory: list[dict]) -> MovementMetrics:
        """Calculate movement metrics from trajectory points.

        This static method computes aggregate statistics from a list
        of trajectory points, useful for behavioral analysis.

        Calculations:
        - total_distance: Sum of Euclidean distances between consecutive points
        - avg_speed: total_distance / duration (pixels per second)
        - direction: Angle in degrees from first to last point (0=right, 90=down)
        - duration_seconds: Time span from first to last point

        Args:
            trajectory: List of trajectory point dictionaries with keys:
                - x: float - X coordinate
                - y: float - Y coordinate
                - timestamp: str - ISO 8601 timestamp

        Returns:
            MovementMetrics with calculated statistics.

        Example:
            trajectory = [
                {"x": 100.0, "y": 200.0, "timestamp": "2026-01-26T12:00:00Z"},
                {"x": 150.0, "y": 250.0, "timestamp": "2026-01-26T12:00:05Z"},
                {"x": 200.0, "y": 300.0, "timestamp": "2026-01-26T12:00:10Z"},
            ]
            metrics = TrackService.calculate_metrics(trajectory)
            print(f"Distance: {metrics.total_distance} pixels")
        """
        if not trajectory:
            return MovementMetrics(
                total_distance=0.0,
                avg_speed=0.0,
                direction=None,
                duration_seconds=0.0,
            )

        if len(trajectory) == 1:
            return MovementMetrics(
                total_distance=0.0,
                avg_speed=0.0,
                direction=None,
                duration_seconds=0.0,
            )

        # Parse timestamps and calculate duration
        def parse_timestamp(ts: str | datetime) -> datetime:
            if isinstance(ts, datetime):
                return ts
            return datetime.fromisoformat(ts)

        first_point = trajectory[0]
        last_point = trajectory[-1]

        first_time = parse_timestamp(first_point["timestamp"])
        last_time = parse_timestamp(last_point["timestamp"])
        duration_seconds = (last_time - first_time).total_seconds()

        # Calculate total distance (sum of consecutive point distances)
        total_distance = 0.0
        for i in range(1, len(trajectory)):
            prev_point = trajectory[i - 1]
            curr_point = trajectory[i]

            dx = curr_point["x"] - prev_point["x"]
            dy = curr_point["y"] - prev_point["y"]
            distance = math.sqrt(dx * dx + dy * dy)
            total_distance += distance

        # Calculate average speed (pixels per second)
        avg_speed = total_distance / duration_seconds if duration_seconds > 0 else 0.0

        # Calculate overall direction (angle from first to last point)
        # Direction in degrees: 0 = right, 90 = down, 180 = left, 270 = up
        direction: float | None = None
        dx_total = last_point["x"] - first_point["x"]
        dy_total = last_point["y"] - first_point["y"]

        if dx_total != 0 or dy_total != 0:
            # atan2 returns angle in radians, convert to degrees
            # Note: atan2 uses standard math convention (counter-clockwise from positive x)
            # We convert to clockwise from positive x (right) to match image coordinates
            angle_rad = math.atan2(dy_total, dx_total)
            direction = math.degrees(angle_rad)
            # Normalize to 0-360 range
            if direction < 0:
                direction += 360

        return MovementMetrics(
            total_distance=round(total_distance, 2),
            avg_speed=round(avg_speed, 2),
            direction=round(direction, 1) if direction is not None else None,
            duration_seconds=round(duration_seconds, 2),
        )


class _TrackServiceSingleton:
    """Singleton holder for TrackService factory.

    Since TrackService requires a database session, we don't maintain
    a true singleton. Instead, this provides the factory function pattern.

    This class-based approach avoids using global statements,
    which are discouraged by PLW0603 linter rule.
    """

    _default_max_trajectory_points: int = DEFAULT_MAX_TRAJECTORY_POINTS
    _default_track_retention_hours: int = DEFAULT_TRACK_RETENTION_HOURS

    @classmethod
    def configure(
        cls,
        max_trajectory_points: int | None = None,
        track_retention_hours: int | None = None,
    ) -> None:
        """Configure default settings for TrackService instances.

        Args:
            max_trajectory_points: Default max trajectory points for new instances.
            track_retention_hours: Default retention hours for new instances.
        """
        if max_trajectory_points is not None:
            cls._default_max_trajectory_points = max_trajectory_points
        if track_retention_hours is not None:
            cls._default_track_retention_hours = track_retention_hours

    @classmethod
    def create(cls, db: AsyncSession) -> TrackService:
        """Create a TrackService instance with default configuration.

        Args:
            db: An async SQLAlchemy session for database operations.

        Returns:
            A TrackService instance.
        """
        return TrackService(
            db=db,
            max_trajectory_points=cls._default_max_trajectory_points,
            track_retention_hours=cls._default_track_retention_hours,
        )

    @classmethod
    def reset(cls) -> None:
        """Reset default configuration to initial values (for testing)."""
        cls._default_max_trajectory_points = DEFAULT_MAX_TRAJECTORY_POINTS
        cls._default_track_retention_hours = DEFAULT_TRACK_RETENTION_HOURS


def get_track_service(db: AsyncSession) -> TrackService:
    """Get a TrackService instance for the given session.

    This creates a new TrackService bound to the provided session.
    Each request/transaction should use its own session and service.

    Args:
        db: An async SQLAlchemy session for database operations.

    Returns:
        A TrackService instance bound to the session.

    Example:
        async with get_session() as session:
            service = get_track_service(session)
            track = await service.create_or_update_track(
                track_id=42,
                camera_id="front_door",
                object_class="person",
                position=(640.5, 480.2),
                timestamp=datetime.now(UTC),
            )
    """
    return _TrackServiceSingleton.create(db)


def configure_track_service(
    max_trajectory_points: int | None = None,
    track_retention_hours: int | None = None,
) -> None:
    """Configure default settings for TrackService instances.

    Use this to set application-wide defaults before creating instances.

    Args:
        max_trajectory_points: Default max trajectory points for new instances.
        track_retention_hours: Default retention hours for new instances.

    Example:
        # At application startup
        configure_track_service(max_trajectory_points=200, track_retention_hours=48)
    """
    _TrackServiceSingleton.configure(
        max_trajectory_points=max_trajectory_points,
        track_retention_hours=track_retention_hours,
    )


def reset_track_service() -> None:
    """Reset TrackService configuration to defaults (for testing)."""
    _TrackServiceSingleton.reset()
