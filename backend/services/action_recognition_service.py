"""Action recognition service for X-CLIP video action classification.

This module provides the ActionRecognitionService class that integrates
X-CLIP action recognition with the database layer. It handles:
- Analyzing video frames for action classification
- Creating and retrieving ActionEvent records
- Filtering suspicious actions
- Configurable confidence thresholds

Linear issue: NEM-3714
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging import get_logger
from backend.models.action_event import ActionEvent
from backend.services.xclip_loader import (
    SECURITY_ACTION_PROMPTS,
    classify_actions,
    is_suspicious_action,
    load_xclip_model,
    sample_frames_from_batch,
)

logger = get_logger(__name__)

# Default confidence threshold for saving action events
DEFAULT_CONFIDENCE_THRESHOLD = 0.5

# Default number of frames for action recognition
DEFAULT_FRAME_COUNT = 8


class ActionRecognitionService:
    """Service for X-CLIP video action recognition and database operations.

    This service wraps the X-CLIP model loader and provides methods for:
    - Analyzing frames to detect actions
    - Creating action events in the database
    - Querying action events with filtering and pagination
    - Retrieving suspicious actions

    The service manages model loading/unloading and integrates with the
    async database session for persistence.

    Example usage:
        async with get_session() as session:
            service = ActionRecognitionService(session)

            # Analyze frames
            result = await service.analyze_frames(
                camera_id="front_door",
                frame_paths=["/path/to/frame1.jpg", "/path/to/frame2.jpg"],
                track_id=42,
            )

            # Get suspicious actions
            suspicious = await service.get_suspicious_actions(limit=10)
    """

    def __init__(
        self,
        session: AsyncSession,
        model_dict: dict[str, Any] | None = None,
        model_path: str = "microsoft/xclip-base-patch32",
    ):
        """Initialize the action recognition service.

        Args:
            session: Async database session for persistence operations
            model_dict: Optional pre-loaded X-CLIP model dictionary.
                       If None, model will be loaded on first use.
            model_path: Path to X-CLIP model (HuggingFace or local path)
        """
        self.session = session
        self._model_dict = model_dict
        self._model_path = model_path
        self._model_loaded = model_dict is not None

    async def _ensure_model_loaded(self) -> dict[str, Any]:
        """Ensure the X-CLIP model is loaded.

        Returns:
            Model dictionary containing model and processor.

        Raises:
            RuntimeError: If model loading fails.
        """
        if self._model_dict is None:
            logger.info(f"Loading X-CLIP model from {self._model_path}")
            self._model_dict = await load_xclip_model(self._model_path)
            self._model_loaded = True
        return self._model_dict

    async def analyze_frames(
        self,
        camera_id: str,
        frame_paths: list[str],
        track_id: int | None = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        save_event: bool = True,
        custom_prompts: list[str] | None = None,
    ) -> dict[str, Any]:
        """Analyze video frames for action recognition.

        Loads frames from disk, runs X-CLIP classification, and optionally
        saves the result to the database.

        Args:
            camera_id: Camera ID where frames were captured
            frame_paths: List of paths to frame image files
            track_id: Optional track ID to associate with the action
            confidence_threshold: Minimum confidence to save event (0.0 to 1.0)
            save_event: Whether to persist the action event to database
            custom_prompts: Optional custom action prompts for classification

        Returns:
            Dictionary containing:
                - action: Detected action label
                - confidence: Confidence score
                - is_suspicious: Whether action is suspicious
                - all_scores: All action scores
                - frame_count: Number of frames analyzed
                - event_id: Database event ID (if saved)
                - saved: Whether event was saved

        Raises:
            ValueError: If frame_paths is empty
            RuntimeError: If model loading or classification fails
            FileNotFoundError: If frame files don't exist
        """
        if not frame_paths:
            raise ValueError("At least one frame path is required")

        # Sample frames if we have more than needed
        sampled_paths = sample_frames_from_batch(frame_paths, target_count=DEFAULT_FRAME_COUNT)

        # Load frames from disk
        frames: list[Image.Image] = []
        for path in sampled_paths:
            try:
                img_file = Image.open(path)
                # Convert to RGB to ensure consistent format
                img: Image.Image = img_file.convert("RGB") if img_file.mode != "RGB" else img_file
                frames.append(img)
            except Exception as e:
                logger.warning(f"Failed to load frame {path}: {e}")
                # Continue with remaining frames

        if not frames:
            raise ValueError("No valid frames could be loaded from the provided paths")

        # Load model if needed
        model_dict = await self._ensure_model_loaded()

        # Run classification
        prompts = custom_prompts if custom_prompts else SECURITY_ACTION_PROMPTS
        result = await classify_actions(
            model_dict=model_dict,
            frames=frames,
            prompts=prompts,
            top_k=3,
        )

        # Determine if suspicious
        detected_action = result["detected_action"]
        confidence = result["confidence"]
        suspicious = is_suspicious_action(detected_action)

        # Build response
        response = {
            "action": detected_action,
            "confidence": confidence,
            "is_suspicious": suspicious,
            "all_scores": result["all_scores"],
            "frame_count": len(frames),
            "event_id": None,
            "saved": False,
        }

        # Save to database if confidence meets threshold
        if save_event and confidence >= confidence_threshold:
            event = await self.create_action_event(
                camera_id=camera_id,
                track_id=track_id,
                action=detected_action,
                confidence=confidence,
                is_suspicious=suspicious,
                frame_count=len(frames),
                all_scores=result["all_scores"],
            )
            response["event_id"] = event.id
            response["saved"] = True

        return response

    async def create_action_event(
        self,
        camera_id: str,
        action: str,
        confidence: float,
        track_id: int | None = None,
        is_suspicious: bool | None = None,
        timestamp: datetime | None = None,
        frame_count: int = DEFAULT_FRAME_COUNT,
        all_scores: dict[str, float] | None = None,
    ) -> ActionEvent:
        """Create a new action event in the database.

        Args:
            camera_id: Camera ID where action was detected
            action: Detected action label
            confidence: Classification confidence score
            track_id: Optional track ID for the detected person
            is_suspicious: Whether action is suspicious (auto-determined if None)
            timestamp: When action was detected (defaults to now)
            frame_count: Number of frames analyzed
            all_scores: Dictionary of all action scores

        Returns:
            Created ActionEvent instance

        Raises:
            sqlalchemy.exc.IntegrityError: If foreign key constraints are violated
        """
        if is_suspicious is None:
            is_suspicious = is_suspicious_action(action)

        if timestamp is None:
            timestamp = datetime.now(UTC)

        event = ActionEvent(
            camera_id=camera_id,
            track_id=track_id,
            action=action,
            confidence=confidence,
            is_suspicious=is_suspicious,
            timestamp=timestamp,
            frame_count=frame_count,
            all_scores=all_scores,
        )

        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)

        logger.info(
            f"Created action event: {event.id} - {action} "
            f"(confidence: {confidence:.2%}, suspicious: {is_suspicious})"
        )

        return event

    async def get_action_event(self, event_id: int) -> ActionEvent | None:
        """Get an action event by ID.

        Args:
            event_id: Action event ID

        Returns:
            ActionEvent if found, None otherwise
        """
        return await self.session.get(ActionEvent, event_id)

    async def get_action_events(
        self,
        camera_id: str | None = None,
        track_id: int | None = None,
        action: str | None = None,
        is_suspicious: bool | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        min_confidence: float | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ActionEvent], int]:
        """Get action events with filtering and pagination.

        Args:
            camera_id: Filter by camera ID
            track_id: Filter by track ID
            action: Filter by action label (exact match)
            is_suspicious: Filter by suspicious flag
            start_time: Filter by timestamp >= start_time
            end_time: Filter by timestamp <= end_time
            min_confidence: Filter by confidence >= min_confidence
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Tuple of (list of ActionEvent, total count)
        """
        # Build base query
        query = select(ActionEvent)
        count_query = select(func.count(ActionEvent.id))

        # Apply filters
        if camera_id is not None:
            query = query.where(ActionEvent.camera_id == camera_id)
            count_query = count_query.where(ActionEvent.camera_id == camera_id)

        if track_id is not None:
            query = query.where(ActionEvent.track_id == track_id)
            count_query = count_query.where(ActionEvent.track_id == track_id)

        if action is not None:
            query = query.where(ActionEvent.action == action)
            count_query = count_query.where(ActionEvent.action == action)

        if is_suspicious is not None:
            query = query.where(ActionEvent.is_suspicious == is_suspicious)
            count_query = count_query.where(ActionEvent.is_suspicious == is_suspicious)

        if start_time is not None:
            query = query.where(ActionEvent.timestamp >= start_time)
            count_query = count_query.where(ActionEvent.timestamp >= start_time)

        if end_time is not None:
            query = query.where(ActionEvent.timestamp <= end_time)
            count_query = count_query.where(ActionEvent.timestamp <= end_time)

        if min_confidence is not None:
            query = query.where(ActionEvent.confidence >= min_confidence)
            count_query = count_query.where(ActionEvent.confidence >= min_confidence)

        # Get total count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Apply ordering and pagination
        query = query.order_by(ActionEvent.timestamp.desc())
        query = query.limit(limit).offset(offset)

        # Execute query
        result = await self.session.execute(query)
        events = list(result.scalars().all())

        return events, total

    async def get_action_events_for_camera(
        self,
        camera_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ActionEvent], int]:
        """Get action events for a specific camera.

        Convenience method for camera-specific queries.

        Args:
            camera_id: Camera ID to filter by
            start_time: Filter by timestamp >= start_time
            end_time: Filter by timestamp <= end_time
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Tuple of (list of ActionEvent, total count)
        """
        return await self.get_action_events(
            camera_id=camera_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )

    async def get_suspicious_actions(
        self,
        camera_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        min_confidence: float | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ActionEvent], int, int]:
        """Get suspicious action events.

        Args:
            camera_id: Optional camera ID filter
            start_time: Filter by timestamp >= start_time
            end_time: Filter by timestamp <= end_time
            min_confidence: Filter by confidence >= min_confidence
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Tuple of (list of suspicious ActionEvent, suspicious count, total count)
        """
        # Get suspicious events
        suspicious_events, suspicious_count = await self.get_action_events(
            camera_id=camera_id,
            is_suspicious=True,
            start_time=start_time,
            end_time=end_time,
            min_confidence=min_confidence,
            limit=limit,
            offset=offset,
        )

        # Get total count (all events matching time/camera filters)
        _, total_count = await self.get_action_events(
            camera_id=camera_id,
            start_time=start_time,
            end_time=end_time,
            min_confidence=min_confidence,
            limit=1,  # We only need the count
            offset=0,
        )

        return suspicious_events, suspicious_count, total_count

    async def delete_action_event(self, event_id: int) -> bool:
        """Delete an action event by ID.

        Args:
            event_id: Action event ID to delete

        Returns:
            True if deleted, False if not found
        """
        event = await self.get_action_event(event_id)
        if event is None:
            return False

        await self.session.delete(event)
        await self.session.flush()

        logger.info(f"Deleted action event: {event_id}")
        return True

    async def get_action_statistics(
        self,
        camera_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get statistics about action events.

        Args:
            camera_id: Optional camera ID filter
            start_time: Filter by timestamp >= start_time
            end_time: Filter by timestamp <= end_time

        Returns:
            Dictionary containing:
                - total_events: Total number of events
                - suspicious_events: Number of suspicious events
                - action_counts: Dict mapping action -> count
                - avg_confidence: Average confidence score
        """
        events, total = await self.get_action_events(
            camera_id=camera_id,
            start_time=start_time,
            end_time=end_time,
            limit=10000,  # Get all for statistics
            offset=0,
        )

        if not events:
            return {
                "total_events": 0,
                "suspicious_events": 0,
                "action_counts": {},
                "avg_confidence": 0.0,
            }

        # Calculate statistics
        action_counts: dict[str, int] = {}
        suspicious_count = 0
        total_confidence = 0.0

        for event in events:
            action_counts[event.action] = action_counts.get(event.action, 0) + 1
            if event.is_suspicious:
                suspicious_count += 1
            total_confidence += event.confidence

        return {
            "total_events": total,
            "suspicious_events": suspicious_count,
            "action_counts": action_counts,
            "avg_confidence": total_confidence / len(events) if events else 0.0,
        }


# Factory function for creating service instances
async def get_action_recognition_service(
    session: AsyncSession,
    model_path: str = "microsoft/xclip-base-patch32",
) -> ActionRecognitionService:
    """Factory function to create an ActionRecognitionService.

    Args:
        session: Async database session
        model_path: Path to X-CLIP model

    Returns:
        ActionRecognitionService instance
    """
    return ActionRecognitionService(session=session, model_path=model_path)
