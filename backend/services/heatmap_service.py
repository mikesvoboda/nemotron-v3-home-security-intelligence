"""HeatmapService for managing movement heatmap generation and storage.

This module provides the HeatmapService class for accumulating detection positions,
generating heatmap visualizations, and managing heatmap persistence.

The service maintains in-memory accumulators per camera and periodically saves
snapshots to the database at different resolutions (hourly, daily, weekly).
"""

from __future__ import annotations

import base64
import io
import zlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import numpy as np

from backend.core.logging import get_logger
from backend.models.heatmap import HeatmapData, HeatmapResolution

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# Default heatmap grid dimensions
DEFAULT_GRID_WIDTH = 64
DEFAULT_GRID_HEIGHT = 48

# Default colormap for visualization
DEFAULT_COLORMAP = "jet"


@dataclass
class HeatmapAccumulator:
    """In-memory accumulator for heatmap data.

    Attributes:
        camera_id: ID of the camera this accumulator belongs to.
        grid: 2D numpy array of detection counts per cell.
        width: Width of the source frame (for coordinate scaling).
        height: Height of the source frame (for coordinate scaling).
        grid_width: Width of the heatmap grid.
        grid_height: Height of the heatmap grid.
        total_detections: Total number of detections added.
        last_updated: Timestamp of the last update.
    """

    camera_id: str
    grid: np.ndarray
    width: int = 1920  # Source frame width
    height: int = 1080  # Source frame height
    grid_width: int = DEFAULT_GRID_WIDTH
    grid_height: int = DEFAULT_GRID_HEIGHT
    total_detections: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        camera_id: str,
        grid_width: int = DEFAULT_GRID_WIDTH,
        grid_height: int = DEFAULT_GRID_HEIGHT,
        source_width: int = 1920,
        source_height: int = 1080,
    ) -> HeatmapAccumulator:
        """Create a new heatmap accumulator.

        Args:
            camera_id: ID of the camera.
            grid_width: Width of the heatmap grid.
            grid_height: Height of the heatmap grid.
            source_width: Width of the source video frame.
            source_height: Height of the source video frame.

        Returns:
            New HeatmapAccumulator instance.
        """
        grid = np.zeros((grid_height, grid_width), dtype=np.float32)
        return cls(
            camera_id=camera_id,
            grid=grid,
            width=source_width,
            height=source_height,
            grid_width=grid_width,
            grid_height=grid_height,
        )

    def add_detection(self, x: int, y: int, weight: float = 1.0) -> None:
        """Add a detection point to the accumulator.

        Scales the detection coordinates to the grid and increments
        the corresponding cell.

        Args:
            x: X coordinate of the detection center in source frame pixels.
            y: Y coordinate of the detection center in source frame pixels.
            weight: Weight to add (default 1.0).
        """
        # Scale to grid coordinates
        grid_x = int(x * self.grid_width / self.width)
        grid_y = int(y * self.grid_height / self.height)

        # Clamp to valid range
        grid_x = max(0, min(grid_x, self.grid_width - 1))
        grid_y = max(0, min(grid_y, self.grid_height - 1))

        # Increment grid cell
        self.grid[grid_y, grid_x] += weight
        self.total_detections += 1
        self.last_updated = datetime.now(UTC)

    def reset(self) -> None:
        """Reset the accumulator to zero."""
        self.grid.fill(0)
        self.total_detections = 0
        self.last_updated = datetime.now(UTC)


class HeatmapService:
    """Service for managing movement heatmap generation and storage.

    This service provides methods for:
    - Adding detection points to in-memory accumulators
    - Generating colored heatmap images
    - Saving snapshots to the database
    - Querying historical heatmap data
    - Merging multiple heatmaps

    Attributes:
        accumulators: Dictionary of in-memory accumulators per camera.
        grid_width: Default width of heatmap grids.
        grid_height: Default height of heatmap grids.

    Example:
        service = HeatmapService()

        # Add detections from processing pipeline
        service.add_detection("front_door", x=500, y=300)

        # Get current heatmap image
        image_data = service.get_heatmap_image(
            "front_door",
            time_bucket=datetime.now(UTC).replace(minute=0, second=0, microsecond=0),
            resolution=HeatmapResolution.HOURLY,
        )

        # Save snapshot to database
        async with get_session() as session:
            await service.save_snapshot(session, "front_door", HeatmapResolution.HOURLY)
    """

    def __init__(
        self,
        grid_width: int = DEFAULT_GRID_WIDTH,
        grid_height: int = DEFAULT_GRID_HEIGHT,
    ) -> None:
        """Initialize the heatmap service.

        Args:
            grid_width: Default width of heatmap grids.
            grid_height: Default height of heatmap grids.
        """
        self.accumulators: dict[str, HeatmapAccumulator] = {}
        self.grid_width = grid_width
        self.grid_height = grid_height

    def _get_or_create_accumulator(
        self,
        camera_id: str,
        source_width: int = 1920,
        source_height: int = 1080,
    ) -> HeatmapAccumulator:
        """Get or create an accumulator for a camera.

        Args:
            camera_id: ID of the camera.
            source_width: Width of the source video frame.
            source_height: Height of the source video frame.

        Returns:
            HeatmapAccumulator for the camera.
        """
        if camera_id not in self.accumulators:
            self.accumulators[camera_id] = HeatmapAccumulator.create(
                camera_id=camera_id,
                grid_width=self.grid_width,
                grid_height=self.grid_height,
                source_width=source_width,
                source_height=source_height,
            )
        return self.accumulators[camera_id]

    def add_detection(
        self,
        camera_id: str,
        x: int,
        y: int,
        weight: float = 1.0,
        source_width: int = 1920,
        source_height: int = 1080,
    ) -> None:
        """Add a detection point to the accumulator for a camera.

        Args:
            camera_id: ID of the camera.
            x: X coordinate of the detection center.
            y: Y coordinate of the detection center.
            weight: Weight to add (default 1.0).
            source_width: Width of the source video frame.
            source_height: Height of the source video frame.
        """
        accumulator = self._get_or_create_accumulator(camera_id, source_width, source_height)
        accumulator.add_detection(x, y, weight)
        logger.debug(
            f"Added detection to heatmap for camera {camera_id}",
            extra={
                "camera_id": camera_id,
                "x": x,
                "y": y,
                "total_detections": accumulator.total_detections,
            },
        )

    def get_accumulator_data(self, camera_id: str) -> np.ndarray | None:
        """Get the current accumulator data for a camera.

        Args:
            camera_id: ID of the camera.

        Returns:
            Copy of the accumulator grid, or None if no accumulator exists.
        """
        if camera_id not in self.accumulators:
            return None
        return self.accumulators[camera_id].grid.copy()

    def get_heatmap_image(
        self,
        camera_id: str,
        output_width: int = 640,
        output_height: int = 480,
        colormap: str = DEFAULT_COLORMAP,
        alpha: float = 0.6,
    ) -> dict[str, Any]:
        """Generate a heatmap image for the current accumulator.

        Args:
            camera_id: ID of the camera.
            output_width: Width of the output image.
            output_height: Height of the output image.
            colormap: Matplotlib colormap name.
            alpha: Opacity of the heatmap (0-1).

        Returns:
            Dictionary containing:
            - image_base64: Base64-encoded PNG image
            - width: Image width
            - height: Image height
            - total_detections: Number of detections
            - colormap: Colormap used
        """
        accumulator = self.accumulators.get(camera_id)
        if accumulator is None or accumulator.total_detections == 0:
            # Return empty heatmap
            return self._create_empty_heatmap(output_width, output_height, colormap)

        return self._render_heatmap(
            accumulator.grid,
            output_width,
            output_height,
            colormap,
            alpha,
            accumulator.total_detections,
        )

    def _create_empty_heatmap(
        self,
        width: int,
        height: int,
        colormap: str,
    ) -> dict[str, Any]:
        """Create an empty (transparent) heatmap image.

        Args:
            width: Image width.
            height: Image height.
            colormap: Colormap name.

        Returns:
            Dictionary with empty heatmap data.
        """
        try:
            from PIL import Image
        except ImportError as e:
            logger.error("PIL not installed, cannot generate heatmap images")
            raise ImportError(
                "PIL (Pillow) required for heatmap generation. Install with: pip install Pillow"
            ) from e

        # Create transparent image
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        # Encode to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode("utf-8")

        return {
            "image_base64": image_base64,
            "width": width,
            "height": height,
            "total_detections": 0,
            "colormap": colormap,
        }

    def _render_heatmap(
        self,
        grid: np.ndarray,
        output_width: int,
        output_height: int,
        colormap: str,
        alpha: float,
        total_detections: int,
    ) -> dict[str, Any]:
        """Render a heatmap grid as a colored image.

        Args:
            grid: 2D numpy array of detection counts.
            output_width: Output image width.
            output_height: Output image height.
            colormap: Matplotlib colormap name.
            alpha: Opacity of the heatmap.
            total_detections: Total detections for metadata.

        Returns:
            Dictionary with rendered heatmap data.
        """
        try:
            import matplotlib
            from matplotlib import cm
            from PIL import Image
            from scipy.ndimage import gaussian_filter, zoom

            # Use non-interactive backend
            matplotlib.use("Agg")
        except ImportError as e:
            logger.error(f"Required library not installed: {e}")
            raise ImportError(
                "matplotlib, scipy, and Pillow required for heatmap rendering. "
                "Install with: pip install matplotlib scipy Pillow"
            ) from e

        # Apply Gaussian blur for smooth visualization
        smoothed = gaussian_filter(grid.astype(np.float32), sigma=1.5)

        # Normalize to 0-1 range
        max_val = smoothed.max()
        if max_val > 0:
            normalized = smoothed / max_val
        else:
            normalized = smoothed

        # Resize to output dimensions
        zoom_factors = (output_height / grid.shape[0], output_width / grid.shape[1])
        resized = zoom(normalized, zoom_factors, order=1)

        # Apply colormap
        cmap = cm.get_cmap(colormap)
        colored = cmap(resized)

        # Apply alpha channel based on intensity
        # More intense areas are more opaque
        colored[:, :, 3] = resized * alpha

        # Convert to 8-bit RGBA
        colored_8bit = (colored * 255).astype(np.uint8)

        # Create PIL image
        img = Image.fromarray(colored_8bit, mode="RGBA")

        # Encode to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode("utf-8")

        return {
            "image_base64": image_base64,
            "width": output_width,
            "height": output_height,
            "total_detections": total_detections,
            "colormap": colormap,
        }

    def compress_grid(self, grid: np.ndarray) -> bytes:
        """Compress a numpy array for storage.

        Args:
            grid: 2D numpy array.

        Returns:
            Compressed bytes.
        """
        # Convert to bytes and compress
        grid_bytes = grid.tobytes()
        compressed = zlib.compress(grid_bytes, level=6)
        return compressed

    def decompress_grid(
        self,
        data: bytes,
        width: int,
        height: int,
        dtype: type = np.float32,
    ) -> np.ndarray:
        """Decompress stored numpy array data.

        Args:
            data: Compressed bytes.
            width: Grid width.
            height: Grid height.
            dtype: Numpy dtype for the array.

        Returns:
            Decompressed 2D numpy array.
        """
        decompressed = zlib.decompress(data)
        grid: np.ndarray = np.frombuffer(decompressed, dtype=dtype)
        return grid.reshape((height, width))

    async def save_snapshot(
        self,
        session: AsyncSession,
        camera_id: str,
        resolution: HeatmapResolution,
        time_bucket: datetime | None = None,
    ) -> HeatmapData | None:
        """Save the current accumulator as a snapshot to the database.

        Args:
            session: Database session.
            camera_id: ID of the camera.
            resolution: Resolution level for the snapshot.
            time_bucket: Time bucket for the snapshot (defaults to current bucket).

        Returns:
            Created HeatmapData record, or None if accumulator is empty.
        """
        accumulator = self.accumulators.get(camera_id)
        if accumulator is None or accumulator.total_detections == 0:
            logger.debug(f"No heatmap data to save for camera {camera_id}")
            return None

        # Calculate time bucket if not provided
        if time_bucket is None:
            time_bucket = self._calculate_time_bucket(datetime.now(UTC), resolution)

        # Compress the grid data
        compressed_data = self.compress_grid(accumulator.grid)

        # Check if a record already exists for this bucket
        from sqlalchemy import select

        existing_query = select(HeatmapData).where(
            HeatmapData.camera_id == camera_id,
            HeatmapData.time_bucket == time_bucket,
            HeatmapData.resolution == resolution.value,
        )
        result = await session.execute(existing_query)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing record by merging grids
            existing_grid = self.decompress_grid(existing.data, existing.width, existing.height)
            merged_grid = existing_grid + accumulator.grid
            existing.data = self.compress_grid(merged_grid)
            existing.total_detections += accumulator.total_detections
            existing.updated_at = datetime.now(UTC)
            heatmap = existing
            logger.info(
                f"Updated heatmap snapshot for camera {camera_id}",
                extra={
                    "camera_id": camera_id,
                    "resolution": resolution.value,
                    "total_detections": existing.total_detections,
                },
            )
        else:
            # Create new record
            heatmap = HeatmapData(
                camera_id=camera_id,
                time_bucket=time_bucket,
                resolution=resolution.value,
                width=accumulator.grid_width,
                height=accumulator.grid_height,
                data=compressed_data,
                total_detections=accumulator.total_detections,
            )
            session.add(heatmap)
            logger.info(
                f"Created heatmap snapshot for camera {camera_id}",
                extra={
                    "camera_id": camera_id,
                    "resolution": resolution.value,
                    "total_detections": accumulator.total_detections,
                },
            )

        await session.commit()
        await session.refresh(heatmap)

        # Reset accumulator after saving
        accumulator.reset()

        return heatmap

    def _calculate_time_bucket(
        self,
        timestamp: datetime,
        resolution: HeatmapResolution,
    ) -> datetime:
        """Calculate the time bucket start for a given timestamp and resolution.

        Args:
            timestamp: The timestamp to calculate the bucket for.
            resolution: The resolution level.

        Returns:
            Start of the time bucket as a datetime.
        """
        if resolution == HeatmapResolution.HOURLY:
            return timestamp.replace(minute=0, second=0, microsecond=0)
        elif resolution == HeatmapResolution.DAILY:
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        elif resolution == HeatmapResolution.WEEKLY:
            # Start of week (Monday)
            days_since_monday = timestamp.weekday()
            week_start = timestamp - timedelta(days=days_since_monday)
            return week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"Unknown resolution: {resolution}")

    async def get_heatmap_data(
        self,
        session: AsyncSession,
        camera_id: str,
        start_time: datetime,
        end_time: datetime,
        resolution: HeatmapResolution | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[HeatmapData], int]:
        """Query historical heatmap data from the database.

        Args:
            session: Database session.
            camera_id: ID of the camera.
            start_time: Start of the time range.
            end_time: End of the time range.
            resolution: Optional resolution filter.
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            Tuple of (list of HeatmapData records, total count).
        """
        from sqlalchemy import func, select

        # Build base query
        base_query = select(HeatmapData).where(
            HeatmapData.camera_id == camera_id,
            HeatmapData.time_bucket >= start_time,
            HeatmapData.time_bucket <= end_time,
        )

        if resolution:
            base_query = base_query.where(HeatmapData.resolution == resolution.value)

        # Get total count
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await session.execute(count_query)
        total = count_result.scalar() or 0

        # Get paginated results
        data_query = base_query.order_by(HeatmapData.time_bucket.desc()).limit(limit).offset(offset)
        result = await session.execute(data_query)
        heatmaps = list(result.scalars().all())

        return heatmaps, total

    async def get_merged_heatmap(
        self,
        session: AsyncSession,
        camera_id: str,
        start_time: datetime,
        end_time: datetime,
        resolution: HeatmapResolution | None = None,
    ) -> dict[str, Any] | None:
        """Get a merged heatmap from multiple records in a time range.

        Args:
            session: Database session.
            camera_id: ID of the camera.
            start_time: Start of the time range.
            end_time: End of the time range.
            resolution: Optional resolution filter.

        Returns:
            Dictionary with merged heatmap data, or None if no data found.
        """
        heatmaps, total = await self.get_heatmap_data(
            session, camera_id, start_time, end_time, resolution, limit=1000, offset=0
        )

        if not heatmaps:
            return None

        return self.merge_heatmaps(heatmaps)

    def merge_heatmaps(self, heatmaps: list[HeatmapData]) -> dict[str, Any]:
        """Merge multiple heatmap records into one.

        Args:
            heatmaps: List of HeatmapData records to merge.

        Returns:
            Dictionary with merged heatmap data including a rendered image.
        """
        if not heatmaps:
            return self._create_empty_heatmap(640, 480, DEFAULT_COLORMAP)

        # Use dimensions from first heatmap
        width = heatmaps[0].width
        height = heatmaps[0].height

        # Initialize merged grid
        merged_grid = np.zeros((height, width), dtype=np.float32)
        total_detections = 0

        for heatmap in heatmaps:
            if heatmap.width != width or heatmap.height != height:
                logger.warning(
                    f"Heatmap dimension mismatch: expected {width}x{height}, "
                    f"got {heatmap.width}x{heatmap.height}"
                )
                continue

            grid = self.decompress_grid(heatmap.data, heatmap.width, heatmap.height)
            merged_grid += grid
            total_detections += heatmap.total_detections

        # Render the merged heatmap
        return self._render_heatmap(
            merged_grid,
            output_width=640,
            output_height=480,
            colormap=DEFAULT_COLORMAP,
            alpha=0.6,
            total_detections=total_detections,
        )

    def reset_accumulator(self, camera_id: str) -> bool:
        """Reset the accumulator for a camera.

        Args:
            camera_id: ID of the camera.

        Returns:
            True if accumulator was reset, False if it didn't exist.
        """
        if camera_id in self.accumulators:
            self.accumulators[camera_id].reset()
            return True
        return False

    def get_accumulator_stats(self, camera_id: str) -> dict[str, Any] | None:
        """Get statistics about an accumulator.

        Args:
            camera_id: ID of the camera.

        Returns:
            Dictionary with accumulator stats, or None if not found.
        """
        accumulator = self.accumulators.get(camera_id)
        if accumulator is None:
            return None

        return {
            "camera_id": camera_id,
            "total_detections": accumulator.total_detections,
            "grid_width": accumulator.grid_width,
            "grid_height": accumulator.grid_height,
            "source_width": accumulator.width,
            "source_height": accumulator.height,
            "last_updated": accumulator.last_updated.isoformat(),
            "max_intensity": float(accumulator.grid.max()),
            "mean_intensity": float(accumulator.grid.mean()),
        }


# Singleton instance for global access
_heatmap_service: HeatmapService | None = None


def get_heatmap_service() -> HeatmapService:
    """Get the global heatmap service instance.

    Returns:
        Global HeatmapService instance.
    """
    global _heatmap_service  # noqa: PLW0603
    if _heatmap_service is None:
        _heatmap_service = HeatmapService()
    return _heatmap_service


def reset_heatmap_service() -> None:
    """Reset the global heatmap service instance (for testing)."""
    global _heatmap_service  # noqa: PLW0603
    _heatmap_service = None
