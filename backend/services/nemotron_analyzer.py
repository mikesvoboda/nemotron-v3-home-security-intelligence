"""Nemotron analyzer service for LLM-based risk assessment.

This service analyzes batches of detections using the Nemotron LLM
via llama.cpp server to generate risk scores and natural language summaries.

Analysis Flow:
    1. Fetch batch detections from Redis/database
    2. Format prompt with detection details
    3. POST to llama.cpp completion endpoint
    4. Parse JSON response
    5. Create Event with risk assessment
    6. Store Event in database
    7. Broadcast via WebSocket (if available)
"""

import json
import re
import time
from typing import Any

import httpx
from sqlalchemy import select

from backend.core.config import get_settings
from backend.core.database import get_session
from backend.core.logging import get_logger
from backend.core.redis import RedisClient
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.prompts import RISK_ANALYSIS_PROMPT

logger = get_logger(__name__)


class NemotronAnalyzer:
    """Analyzes detection batches using Nemotron LLM for risk assessment.

    This service coordinates with the batch aggregator to receive completed
    batches, queries the database for detection details, formats a prompt
    for the LLM, and creates Events with risk scores and summaries.
    """

    def __init__(self, redis_client: RedisClient | None = None):
        """Initialize Nemotron analyzer with Redis client.

        Args:
            redis_client: Redis client instance for queue and cache operations.
        """
        self._redis = redis_client
        settings = get_settings()
        self._llm_url = settings.nemotron_url
        self._timeout = 60.0  # LLM request timeout in seconds

    async def analyze_batch(self, batch_id: str) -> Event:
        """Analyze a batch of detections and create Event.

        Fetches batch metadata from Redis, retrieves detection details from
        database, calls LLM for risk analysis, and creates an Event record.

        Args:
            batch_id: Batch identifier to analyze

        Returns:
            Event object with risk assessment

        Raises:
            ValueError: If batch not found or has no detections
            RuntimeError: If Redis client not initialized
        """
        if not self._redis:
            raise RuntimeError("Redis client not initialized")

        # Get batch metadata from Redis
        camera_id = await self._redis.get(f"batch:{batch_id}:camera_id")
        if not camera_id:
            raise ValueError(f"Batch {batch_id} not found in Redis")

        detections_data = await self._redis.get(f"batch:{batch_id}:detections")
        detection_ids = json.loads(detections_data) if detections_data else []

        if not detection_ids:
            raise ValueError(f"Batch {batch_id} has no detections")

        analysis_start = time.time()

        logger.info(
            f"Analyzing batch {batch_id} for camera {camera_id} "
            f"with {len(detection_ids)} detections",
            extra={
                "camera_id": camera_id,
                "batch_id": batch_id,
                "detection_count": len(detection_ids),
            },
        )

        # Fetch detection details from database
        async with get_session() as session:
            # Get camera details
            camera_result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = camera_result.scalar_one_or_none()
            if not camera:
                logger.warning(
                    f"Camera {camera_id} not found, using ID as name"
                )  # pragma: no cover
                camera_name = camera_id  # pragma: no cover
            else:
                camera_name = camera.name

            # Get detection details
            detections_result = await session.execute(
                select(Detection).where(Detection.id.in_(detection_ids))
            )
            detections = list(detections_result.scalars().all())

            if not detections:
                logger.warning(
                    f"No detections found in database for batch {batch_id}, "
                    f"detection_ids: {detection_ids}"
                )
                raise ValueError(f"No detections found for batch {batch_id}")

            # Determine time window
            detection_times = [d.detected_at for d in detections]
            start_time = min(detection_times)
            end_time = max(detection_times)

            # Format detections for prompt
            detections_list = self._format_detections(detections)

            # Call LLM for risk analysis
            llm_start = time.time()
            try:
                risk_data = await self._call_llm(
                    camera_name=camera_name,
                    start_time=start_time.isoformat(),
                    end_time=end_time.isoformat(),
                    detections_list=detections_list,
                )
                llm_duration_ms = int((time.time() - llm_start) * 1000)
                logger.debug(
                    f"LLM analysis completed for batch {batch_id}",
                    extra={
                        "camera_id": camera_id,
                        "batch_id": batch_id,
                        "duration_ms": llm_duration_ms,
                    },
                )
            except Exception as e:
                llm_duration_ms = int((time.time() - llm_start) * 1000)
                logger.error(
                    f"LLM analysis failed for batch {batch_id}: {e}",
                    extra={
                        "camera_id": camera_id,
                        "batch_id": batch_id,
                        "duration_ms": llm_duration_ms,
                    },
                    exc_info=True,
                )
                # Create fallback risk data
                risk_data = {
                    "risk_score": 50,
                    "risk_level": "medium",
                    "summary": "Analysis unavailable - LLM service error",
                    "reasoning": f"Failed to analyze detections: {e!s}",
                }

            # Create Event record
            event = Event(
                batch_id=batch_id,
                camera_id=camera_id,
                started_at=start_time,
                ended_at=end_time,
                risk_score=risk_data.get("risk_score", 50),
                risk_level=risk_data.get("risk_level", "medium"),
                summary=risk_data.get("summary", "No summary available"),
                reasoning=risk_data.get("reasoning", "No reasoning available"),
                detection_ids=json.dumps(detection_ids),
                reviewed=False,
            )

            session.add(event)
            await session.commit()
            await session.refresh(event)

            total_duration_ms = int((time.time() - analysis_start) * 1000)
            logger.info(
                f"Created event {event.id} for batch {batch_id}: "
                f"risk_score={event.risk_score}, risk_level={event.risk_level}",
                extra={
                    "camera_id": camera_id,
                    "event_id": event.id,
                    "batch_id": batch_id,
                    "risk_score": event.risk_score,
                    "risk_level": event.risk_level,
                    "duration_ms": total_duration_ms,
                },
            )

            # Broadcast via WebSocket if available (optional)
            try:
                await self._broadcast_event(event)
            except Exception as e:
                logger.warning(f"Failed to broadcast event {event.id}: {e}")

            return event

    async def analyze_detection_fast_path(self, camera_id: str, detection_id: str) -> Event:
        """Analyze a single detection via fast path (high-priority).

        This method is called for high-confidence critical detections that bypass
        the normal batch aggregation process. Creates an Event immediately for
        the single detection.

        Args:
            camera_id: Camera identifier
            detection_id: Detection identifier (as int or string)

        Returns:
            Event object with risk assessment and is_fast_path=True

        Raises:
            ValueError: If detection not found
            RuntimeError: If Redis client not initialized
        """
        if not self._redis:
            raise RuntimeError("Redis client not initialized")

        # Convert detection_id to int if needed
        try:
            detection_id_int = int(detection_id)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid detection_id: {detection_id}") from None

        analysis_start = time.time()

        logger.info(
            f"Fast path analysis for detection {detection_id} on camera {camera_id}",
            extra={"camera_id": camera_id, "detection_id": detection_id_int},
        )

        # Fetch detection details from database
        async with get_session() as session:
            # Get camera details
            camera_result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = camera_result.scalar_one_or_none()
            if not camera:
                logger.warning(
                    f"Camera {camera_id} not found, using ID as name"
                )  # pragma: no cover
                camera_name = camera_id  # pragma: no cover
            else:
                camera_name = camera.name

            # Get detection details
            detection_result = await session.execute(
                select(Detection).where(Detection.id == detection_id_int)
            )
            detection = detection_result.scalar_one_or_none()

            if not detection:
                raise ValueError(f"Detection {detection_id} not found in database")

            # Create single-detection list for analysis
            detection_time = detection.detected_at
            detections_list = self._format_detections([detection])

            # Generate batch ID for fast path
            batch_id = f"fast_path_{detection_id}"

            # Call LLM for risk analysis
            llm_start = time.time()
            try:
                risk_data = await self._call_llm(
                    camera_name=camera_name,
                    start_time=detection_time.isoformat(),
                    end_time=detection_time.isoformat(),
                    detections_list=detections_list,
                )
                llm_duration_ms = int((time.time() - llm_start) * 1000)
                logger.debug(
                    f"Fast path LLM analysis completed for detection {detection_id}",
                    extra={
                        "camera_id": camera_id,
                        "detection_id": detection_id_int,
                        "duration_ms": llm_duration_ms,
                    },
                )
            except Exception as e:
                llm_duration_ms = int((time.time() - llm_start) * 1000)
                logger.error(
                    f"LLM analysis failed for fast path detection {detection_id}: {e}",
                    extra={
                        "camera_id": camera_id,
                        "detection_id": detection_id_int,
                        "duration_ms": llm_duration_ms,
                    },
                    exc_info=True,
                )
                # Create fallback risk data
                risk_data = {
                    "risk_score": 50,
                    "risk_level": "medium",
                    "summary": "Analysis unavailable - LLM service error",
                    "reasoning": f"Failed to analyze detection: {e!s}",
                }

            # Create Event record with is_fast_path=True
            event = Event(
                batch_id=batch_id,
                camera_id=camera_id,
                started_at=detection_time,
                ended_at=detection_time,
                risk_score=risk_data.get("risk_score", 50),
                risk_level=risk_data.get("risk_level", "medium"),
                summary=risk_data.get("summary", "No summary available"),
                reasoning=risk_data.get("reasoning", "No reasoning available"),
                detection_ids=json.dumps([detection_id_int]),
                reviewed=False,
                is_fast_path=True,
            )

            session.add(event)
            await session.commit()
            await session.refresh(event)

            total_duration_ms = int((time.time() - analysis_start) * 1000)
            logger.info(
                f"Created fast path event {event.id} for detection {detection_id}: "
                f"risk_score={event.risk_score}, risk_level={event.risk_level}",
                extra={
                    "camera_id": camera_id,
                    "event_id": event.id,
                    "detection_id": detection_id_int,
                    "risk_score": event.risk_score,
                    "risk_level": event.risk_level,
                    "duration_ms": total_duration_ms,
                },
            )

            # Broadcast via WebSocket if available (optional)
            try:
                await self._broadcast_event(event)
            except Exception as e:
                logger.warning(f"Failed to broadcast fast path event {event.id}: {e}")

            return event

    async def health_check(self) -> bool:
        """Check if LLM server is healthy.

        Sends a simple health check request to the LLM endpoint.

        Returns:
            True if LLM server is responding, False otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._llm_url}/health",
                    timeout=5.0,
                )
                return bool(response.status_code == 200)
        except Exception as e:
            logger.warning(f"LLM health check failed: {e}")
            return False

    def _format_detections(self, detections: list[Detection]) -> str:
        """Format detections into a human-readable list for the prompt.

        Args:
            detections: List of Detection objects

        Returns:
            Formatted string with detection details
        """
        lines = []
        for i, det in enumerate(detections, 1):
            time_str = det.detected_at.strftime("%H:%M:%S")
            obj_type = det.object_type or "unknown"
            confidence = f"{det.confidence:.2f}" if det.confidence else "N/A"
            lines.append(f"  {i}. {time_str} - {obj_type} (confidence: {confidence})")

        return "\n".join(lines)

    async def _call_llm(
        self,
        camera_name: str,
        start_time: str,
        end_time: str,
        detections_list: str,
    ) -> dict[str, Any]:
        """Call Nemotron LLM for risk analysis.

        Args:
            camera_name: Name of the camera
            start_time: Start of detection window (ISO format)
            end_time: End of detection window (ISO format)
            detections_list: Formatted list of detections

        Returns:
            Dictionary with risk_score, risk_level, summary, and reasoning

        Raises:
            httpx.HTTPError: If LLM request fails
            ValueError: If response cannot be parsed
        """
        # Format the prompt
        prompt = RISK_ANALYSIS_PROMPT.format(
            camera_name=camera_name,
            start_time=start_time,
            end_time=end_time,
            detections_list=detections_list,
        )

        # Call llama.cpp completion endpoint
        payload = {
            "prompt": prompt,
            "temperature": 0.7,
            "max_tokens": 500,
            "stop": ["\n\n"],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._llm_url}/completion",
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            result = response.json()

        # Extract completion text
        completion_text = result.get("content", "")
        if not completion_text:
            raise ValueError("Empty completion from LLM")

        # Parse JSON from completion
        risk_data = self._parse_llm_response(completion_text)

        # Validate and normalize risk data
        risk_data = self._validate_risk_data(risk_data)

        return risk_data

    def _parse_llm_response(self, text: str) -> dict[str, Any]:
        """Parse JSON response from LLM completion.

        Handles cases where LLM output may include extra text or formatting.

        Args:
            text: LLM completion text

        Returns:
            Parsed dictionary with risk assessment

        Raises:
            ValueError: If JSON cannot be extracted or parsed
        """
        # Try to extract JSON from the text
        # Look for JSON object pattern
        json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        matches = re.findall(json_pattern, text, re.DOTALL)

        if not matches:
            raise ValueError(f"No JSON found in LLM response: {text[:200]}")

        # Try each match until we get valid JSON
        for match in matches:
            try:
                data = json.loads(match)
                if "risk_score" in data and "risk_level" in data:
                    return dict(data)  # Ensure we return a dict
            except json.JSONDecodeError:  # pragma: no cover
                continue  # pragma: no cover

        raise ValueError(f"Could not parse valid risk JSON from: {text[:200]}")

    def _validate_risk_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize risk assessment data.

        Ensures risk_score is 0-100, risk_level is valid, and required
        fields are present.

        Args:
            data: Raw risk data from LLM

        Returns:
            Validated and normalized risk data
        """
        # Validate risk_score
        risk_score = data.get("risk_score", 50)
        if not isinstance(risk_score, int | float):
            try:
                risk_score = int(risk_score)
            except (ValueError, TypeError):
                risk_score = 50
        risk_score = max(0, min(100, int(risk_score)))

        # Validate risk_level
        valid_levels = ["low", "medium", "high", "critical"]
        risk_level = str(data.get("risk_level", "medium")).lower()
        if risk_level not in valid_levels:
            # Infer from risk_score
            if risk_score <= 25:
                risk_level = "low"
            elif risk_score <= 50:
                risk_level = "medium"
            elif risk_score <= 75:
                risk_level = "high"
            else:
                risk_level = "critical"

        # Ensure summary and reasoning exist
        summary = data.get("summary", "Risk analysis completed")
        reasoning = data.get("reasoning", "No detailed reasoning provided")

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "summary": summary,
            "reasoning": reasoning,
        }

    async def _broadcast_event(self, event: Event) -> None:
        """Broadcast event via WebSocket (optional).

        Args:
            event: Event to broadcast
        """
        if not self._redis:
            return

        try:
            message = {
                "type": "event_created",
                "event_id": event.id,
                "batch_id": event.batch_id,
                "camera_id": event.camera_id,
                "risk_score": event.risk_score,
                "risk_level": event.risk_level,
                "summary": event.summary,
                "started_at": event.started_at.isoformat() if event.started_at else None,
            }

            await self._redis.publish("events", message)
            logger.debug(f"Broadcasted event {event.id} via WebSocket")
        except Exception as e:  # pragma: no cover
            logger.warning(f"Failed to broadcast event: {e}")  # pragma: no cover
