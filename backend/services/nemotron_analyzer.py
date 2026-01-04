"""Nemotron analyzer service for LLM-based risk assessment.

This service analyzes batches of detections using the Nemotron LLM
via llama.cpp server to generate risk scores and natural language summaries.

Analysis Flow:
    1. Fetch batch detections from Redis/database
    2. Enrich context with zones, baselines, and cross-camera activity
    3. Run enrichment pipeline for license plates, faces, OCR (optional)
    4. Format prompt with enriched detection details
    5. POST to llama.cpp completion endpoint
    6. Parse JSON response
    7. Create Event with risk assessment
    8. Store Event in database
    9. Broadcast via WebSocket (if available)
"""

import json
import re
import time
from typing import Any

import httpx
from pydantic import ValidationError
from sqlalchemy import select

from backend.api.schemas.llm_response import LLMRawResponse, LLMRiskResponse
from backend.core.config import get_settings
from backend.core.database import get_session
from backend.core.logging import get_logger, sanitize_error
from backend.core.metrics import (
    observe_ai_request_duration,
    observe_risk_score,
    observe_stage_duration,
    record_event_by_camera,
    record_event_by_risk_level,
    record_event_created,
    record_pipeline_error,
    record_prompt_template_used,
)
from backend.core.redis import RedisClient
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.context_enricher import ContextEnricher, EnrichedContext, get_context_enricher
from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentPipeline,
    EnrichmentResult,
    get_enrichment_pipeline,
)
from backend.services.prompts import (
    ENRICHED_RISK_ANALYSIS_PROMPT,
    FULL_ENRICHED_RISK_ANALYSIS_PROMPT,
    MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
    RISK_ANALYSIS_PROMPT,
    VISION_ENHANCED_RISK_ANALYSIS_PROMPT,
    format_action_recognition_context,
    format_clothing_analysis_context,
    format_depth_context,
    format_detections_with_all_enrichment,
    format_image_quality_context,
    format_pet_classification_context,
    format_pose_analysis_context,
    format_vehicle_classification_context,
    format_vehicle_damage_context,
    format_violence_context,
    format_weather_context,
)

logger = get_logger(__name__)

# Timeout configuration for Nemotron LLM service
# - connect_timeout: Maximum time to establish connection (10s)
# - read_timeout: Maximum time to wait for LLM response (120s for complex inference)
NEMOTRON_CONNECT_TIMEOUT = 10.0
NEMOTRON_READ_TIMEOUT = 120.0
NEMOTRON_HEALTH_TIMEOUT = 5.0


class NemotronAnalyzer:
    """Analyzes detection batches using Nemotron LLM for risk assessment.

    This service coordinates with the batch aggregator to receive completed
    batches, queries the database for detection details, formats a prompt
    for the LLM, and creates Events with risk scores and summaries.

    With context enrichment enabled, the analyzer will include zone information,
    baseline deviation data, and cross-camera activity in the prompt.

    With the enrichment pipeline enabled, the analyzer will also extract:
    - License plates from vehicle detections (with OCR)
    - Faces from person detections
    """

    def __init__(
        self,
        redis_client: RedisClient | None = None,
        context_enricher: ContextEnricher | None = None,
        enrichment_pipeline: EnrichmentPipeline | None = None,
        use_enriched_context: bool = True,
        use_enrichment_pipeline: bool = True,
    ):
        """Initialize Nemotron analyzer with Redis client.

        Args:
            redis_client: Redis client instance for queue and cache operations.
            context_enricher: Optional context enricher for enhanced prompts.
                If not provided and use_enriched_context is True, will use the
                global singleton.
            enrichment_pipeline: Optional enrichment pipeline for license plates,
                faces, and OCR. If not provided and use_enrichment_pipeline is True,
                will use the global singleton.
            use_enriched_context: Whether to use enriched context in prompts.
                Set to False for basic analysis without zone/baseline data.
            use_enrichment_pipeline: Whether to run the enrichment pipeline for
                license plates and faces. Set to False to skip this step.
        """
        self._redis = redis_client
        settings = get_settings()
        self._llm_url = settings.nemotron_url
        # Security: Store API key for authentication (None if not configured)
        self._api_key = settings.nemotron_api_key
        # Use httpx.Timeout for proper timeout configuration from Settings
        # connect: time to establish connection, read: time to wait for LLM response
        self._timeout = httpx.Timeout(
            connect=settings.ai_connect_timeout,
            read=settings.nemotron_read_timeout,
            write=settings.nemotron_read_timeout,
            pool=settings.ai_connect_timeout,
        )
        self._health_timeout = httpx.Timeout(
            connect=settings.ai_health_timeout,
            read=settings.ai_health_timeout,
            write=settings.ai_health_timeout,
            pool=settings.ai_health_timeout,
        )
        self._use_enriched_context = use_enriched_context
        self._use_enrichment_pipeline = use_enrichment_pipeline
        self._context_enricher = context_enricher
        self._enrichment_pipeline = enrichment_pipeline

    def _get_context_enricher(self) -> ContextEnricher:
        """Get the context enricher, creating global singleton if needed.

        Returns:
            ContextEnricher instance
        """
        if self._context_enricher is None:
            self._context_enricher = get_context_enricher()
        return self._context_enricher

    def _get_enrichment_pipeline(self) -> EnrichmentPipeline:
        """Get the enrichment pipeline, creating global singleton if needed.

        Returns:
            EnrichmentPipeline instance
        """
        if self._enrichment_pipeline is None:
            self._enrichment_pipeline = get_enrichment_pipeline()
        return self._enrichment_pipeline

    async def _get_enriched_context(
        self,
        batch_id: str,
        camera_id: str,
        detection_ids: list[int],
        session: Any,
    ) -> EnrichedContext | None:
        """Get enriched context for a batch if enabled.

        Args:
            batch_id: Batch identifier
            camera_id: Camera identifier
            detection_ids: List of detection IDs
            session: Database session

        Returns:
            EnrichedContext or None if enrichment is disabled or fails
        """
        if not self._use_enriched_context:
            return None

        try:
            enricher = self._get_context_enricher()
            context = await enricher.enrich(
                batch_id=batch_id,
                camera_id=camera_id,
                detection_ids=detection_ids,
                session=session,
            )
            logger.debug(
                f"Context enriched for batch {batch_id}: "
                f"{len(context.zones)} zones, "
                f"{len(context.cross_camera)} cross-camera activities"
            )
            return context
        except Exception as e:
            logger.warning(
                f"Context enrichment failed for batch {batch_id}, "
                f"falling back to basic prompt: {e}",
                exc_info=True,
            )
            return None

    async def _get_enrichment_result(
        self,
        batch_id: str,
        detections: list[Detection],
        camera_id: str | None = None,
    ) -> EnrichmentResult | None:
        """Get enrichment result (plates, faces) for detections if enabled.

        Args:
            batch_id: Batch identifier (for logging)
            detections: List of Detection objects
            camera_id: Camera ID for scene change detection and re-id

        Returns:
            EnrichmentResult or None if enrichment is disabled or fails
        """
        if not self._use_enrichment_pipeline:
            return None

        try:
            result = await self._run_enrichment_pipeline(detections, camera_id=camera_id)
            if result:
                logger.debug(
                    f"Enrichment pipeline for batch {batch_id}: "
                    f"{len(result.license_plates)} plates, "
                    f"{len(result.faces)} faces, "
                    f"{result.processing_time_ms:.1f}ms"
                )
            return result
        except Exception as e:
            logger.warning(
                f"Enrichment pipeline failed for batch {batch_id}, "
                f"continuing without enrichment: {e}",
                exc_info=True,
            )
            return None

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests.

        Security: Returns X-API-Key header if API key is configured.

        Returns:
            Dictionary of headers to include in requests
        """
        if self._api_key:
            return {"X-API-Key": self._api_key}
        return {}

    async def analyze_batch(  # noqa: PLR0912 - Complex orchestration method
        self,
        batch_id: str,
        camera_id: str | None = None,
        detection_ids: list[int | str] | None = None,
    ) -> Event:
        """Analyze a batch of detections and create Event.

        If camera_id and detection_ids are provided (from queue payload), uses them
        directly. Otherwise, fetches batch metadata from Redis (legacy behavior).

        Args:
            batch_id: Batch identifier to analyze
            camera_id: Camera identifier (optional, from queue payload)
            detection_ids: List of detection IDs (optional, from queue payload)

        Returns:
            Event object with risk assessment

        Raises:
            ValueError: If batch not found or has no detections
            RuntimeError: If Redis client not initialized
        """
        if not self._redis:
            raise RuntimeError("Redis client not initialized")

        # Use provided values or fall back to Redis lookup
        if camera_id is None:
            camera_id = await self._redis.get(f"batch:{batch_id}:camera_id")
            if not camera_id:
                raise ValueError(f"Batch {batch_id} not found in Redis")

        if detection_ids is None:
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
            # Convert detection_ids to integers (may come as strings from queue payload)
            try:
                int_detection_ids = [int(d) for d in detection_ids]
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Invalid detection_id in batch {batch_id}: {e}. "
                    f"Detection IDs must be numeric (got: {detection_ids})"
                ) from None
            detections_result = await session.execute(
                select(Detection).where(Detection.id.in_(int_detection_ids))
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

            # Enrich context if enabled (zone, baseline, cross-camera)
            enriched_context = await self._get_enriched_context(
                batch_id, camera_id, int_detection_ids, session
            )

            # Run enrichment pipeline for license plates, faces, OCR
            enrichment_result = await self._get_enrichment_result(
                batch_id, detections, camera_id=camera_id
            )

            # Persist enrichment data to each detection
            if enrichment_result is not None:
                for detection in detections:
                    det_enrichment = enrichment_result.get_enrichment_for_detection(detection.id)
                    if det_enrichment:
                        detection.enrichment_data = det_enrichment
                        logger.debug(
                            f"Persisted enrichment data for detection {detection.id}",
                            extra={
                                "detection_id": detection.id,
                                "enrichment_keys": list(det_enrichment.keys()),
                            },
                        )

            # Call LLM for risk analysis
            llm_start = time.time()
            try:
                risk_data = await self._call_llm(
                    camera_name=camera_name,
                    start_time=start_time.isoformat(),
                    end_time=end_time.isoformat(),
                    detections_list=detections_list,
                    enriched_context=enriched_context,
                    enrichment_result=enrichment_result,
                )
                llm_duration_ms = int((time.time() - llm_start) * 1000)
                llm_duration_seconds = time.time() - llm_start
                # Record Nemotron AI request duration
                observe_ai_request_duration("nemotron", llm_duration_seconds)
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
                llm_duration_seconds = time.time() - llm_start
                # Record duration even on failure
                observe_ai_request_duration("nemotron", llm_duration_seconds)
                record_pipeline_error("nemotron_analysis_error")
                sanitized_error = sanitize_error(e)
                logger.error(
                    f"LLM analysis failed for batch {batch_id}: {sanitized_error}",
                    extra={
                        "camera_id": camera_id,
                        "batch_id": batch_id,
                        "duration_ms": llm_duration_ms,
                    },
                    exc_info=True,
                )
                # Create fallback risk data - use sanitized error for user-facing content
                risk_data = {
                    "risk_score": 50,
                    "risk_level": "medium",
                    "summary": "Analysis unavailable - LLM service error",
                    "reasoning": "Failed to analyze detections due to service error",
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
                llm_prompt=risk_data.get("llm_prompt"),
                detection_ids=json.dumps(int_detection_ids),
                reviewed=False,
            )

            session.add(event)
            await session.commit()
            await session.refresh(event)

            # Create partial audit record for model contribution tracking
            try:
                from backend.services.audit_service import get_audit_service

                audit_service = get_audit_service()
                audit = audit_service.create_partial_audit(
                    event_id=event.id,
                    llm_prompt=risk_data.get("llm_prompt"),
                    enriched_context=enriched_context,
                    enrichment_result=enrichment_result,
                )
                session.add(audit)
                await session.commit()
                await session.refresh(audit)
                logger.debug(f"Created audit {audit.id} for event {event.id}")
            except Exception as e:
                logger.warning(f"Failed to create audit for event {event.id}: {e}")

            total_duration_ms = int((time.time() - analysis_start) * 1000)
            total_duration_seconds = time.time() - analysis_start

            # Record stage duration and event creation metrics
            observe_stage_duration("analyze", total_duration_seconds)
            record_event_created()
            record_event_by_camera(camera_id, camera_name)

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
                logger.warning(f"Failed to broadcast event {event.id}: {e}", exc_info=True)

            return event

    async def analyze_detection_fast_path(self, camera_id: str, detection_id: int | str) -> Event:
        """Analyze a single detection via fast path (high-priority).

        This method is called for high-confidence critical detections that bypass
        the normal batch aggregation process. Creates an Event immediately for
        the single detection.

        Args:
            camera_id: Camera identifier
            detection_id: Detection identifier (int or string, normalized to int internally)

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

            # Enrich context if enabled (zone, baseline, cross-camera)
            enriched_context = await self._get_enriched_context(
                batch_id, camera_id, [detection_id_int], session
            )

            # Run enrichment pipeline for license plates, faces, OCR
            enrichment_result = await self._get_enrichment_result(
                batch_id, [detection], camera_id=camera_id
            )

            # Persist enrichment data to the detection
            if enrichment_result is not None:
                det_enrichment = enrichment_result.get_enrichment_for_detection(detection.id)
                if det_enrichment:
                    detection.enrichment_data = det_enrichment
                    logger.debug(
                        f"Persisted enrichment data for fast path detection {detection.id}",
                        extra={
                            "detection_id": detection.id,
                            "enrichment_keys": list(det_enrichment.keys()),
                        },
                    )

            # Call LLM for risk analysis
            llm_start = time.time()
            try:
                risk_data = await self._call_llm(
                    camera_name=camera_name,
                    start_time=detection_time.isoformat(),
                    end_time=detection_time.isoformat(),
                    detections_list=detections_list,
                    enriched_context=enriched_context,
                    enrichment_result=enrichment_result,
                )
                llm_duration_ms = int((time.time() - llm_start) * 1000)
                llm_duration_seconds = time.time() - llm_start
                # Record Nemotron AI request duration
                observe_ai_request_duration("nemotron", llm_duration_seconds)
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
                llm_duration_seconds = time.time() - llm_start
                # Record duration even on failure
                observe_ai_request_duration("nemotron", llm_duration_seconds)
                record_pipeline_error("nemotron_fast_path_error")
                sanitized_error = sanitize_error(e)
                logger.error(
                    f"LLM analysis failed for fast path detection {detection_id}: {sanitized_error}",
                    extra={
                        "camera_id": camera_id,
                        "detection_id": detection_id_int,
                        "duration_ms": llm_duration_ms,
                    },
                    exc_info=True,
                )
                # Create fallback risk data - use generic message for user-facing content
                risk_data = {
                    "risk_score": 50,
                    "risk_level": "medium",
                    "summary": "Analysis unavailable - LLM service error",
                    "reasoning": "Failed to analyze detection due to service error",
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
                llm_prompt=risk_data.get("llm_prompt"),
                detection_ids=json.dumps([detection_id_int]),
                reviewed=False,
                is_fast_path=True,
            )

            session.add(event)
            await session.commit()
            await session.refresh(event)

            # Create partial audit record for model contribution tracking
            try:
                from backend.services.audit_service import get_audit_service

                audit_service = get_audit_service()
                audit = audit_service.create_partial_audit(
                    event_id=event.id,
                    llm_prompt=risk_data.get("llm_prompt"),
                    enriched_context=enriched_context,
                    enrichment_result=enrichment_result,
                )
                session.add(audit)
                await session.commit()
                await session.refresh(audit)
                logger.debug(f"Created audit {audit.id} for event {event.id}")
            except Exception as e:
                logger.warning(f"Failed to create audit for event {event.id}: {e}")

            total_duration_ms = int((time.time() - analysis_start) * 1000)
            total_duration_seconds = time.time() - analysis_start

            # Record stage duration and event creation metrics
            observe_stage_duration("analyze", total_duration_seconds)
            record_event_created()
            record_event_by_camera(camera_id, camera_name)

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
                logger.warning(
                    f"Failed to broadcast fast path event {event.id}: {e}", exc_info=True
                )

            return event

    async def health_check(self) -> bool:
        """Check if LLM server is healthy.

        Sends a simple health check request to the LLM endpoint.

        Returns:
            True if LLM server is responding, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self._health_timeout) as client:
                # Include auth headers in health check
                response = await client.get(
                    f"{self._llm_url}/health",
                    headers=self._get_auth_headers(),
                )
                return bool(response.status_code == 200)
        except Exception as e:
            logger.warning(f"LLM health check failed: {e}", exc_info=True)
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

    async def _run_enrichment_pipeline(
        self, detections: list[Detection], camera_id: str | None = None
    ) -> EnrichmentResult | None:
        """Run the enrichment pipeline on detections.

        Converts Detection models to DetectionInput format and runs the
        enrichment pipeline to extract license plates, faces, and OCR.

        Args:
            detections: List of Detection models from the database
            camera_id: Camera ID for scene change detection and re-id

        Returns:
            EnrichmentResult with plates and faces, or None if no enrichment
        """
        if not detections:
            return None

        pipeline = self._get_enrichment_pipeline()

        # Convert Detection models to DetectionInput format
        detection_inputs: list[DetectionInput] = []
        from pathlib import Path

        from PIL import Image

        # Type annotation matches EnrichmentPipeline.enrich_batch signature
        images: dict[int | None, Image.Image | Path | str] = {}

        for det in detections:
            # Skip detections without bounding boxes or object types
            if (
                det.bbox_x is None
                or det.bbox_y is None
                or det.bbox_width is None
                or det.bbox_height is None
                or det.object_type is None
            ):
                continue

            # Create DetectionInput with bounding box
            detection_input = DetectionInput(
                id=det.id,
                class_name=det.object_type,
                confidence=det.confidence or 0.0,
                bbox=BoundingBox(
                    x1=float(det.bbox_x),
                    y1=float(det.bbox_y),
                    x2=float(det.bbox_x + det.bbox_width),
                    y2=float(det.bbox_y + det.bbox_height),
                ),
            )
            detection_inputs.append(detection_input)

            # Map detection ID to image path
            if det.file_path:
                images[det.id] = det.file_path

        if not detection_inputs:
            return None

        # Set shared image for full-frame analysis (use first detection's image)
        # This enables vision extraction, scene change detection, and re-id
        if detections and detections[0].file_path:
            images[None] = detections[0].file_path

        # Run the enrichment pipeline with camera_id for scene change and re-id
        result = await pipeline.enrich_batch(detection_inputs, images, camera_id=camera_id)

        return result

    async def _call_llm(
        self,
        camera_name: str,
        start_time: str,
        end_time: str,
        detections_list: str,
        enriched_context: EnrichedContext | None = None,
        enrichment_result: EnrichmentResult | None = None,
    ) -> dict[str, Any]:
        """Call Nemotron LLM for risk analysis.

        Args:
            camera_name: Name of the camera
            start_time: Start of detection window (ISO format)
            end_time: End of detection window (ISO format)
            detections_list: Formatted list of detections
            enriched_context: Optional enriched context for enhanced prompts
            enrichment_result: Optional enrichment result with plates/faces

        Returns:
            Dictionary with risk_score, risk_level, summary, and reasoning

        Raises:
            httpx.HTTPError: If LLM request fails
            ValueError: If response cannot be parsed
        """
        # Format the prompt based on available context
        has_enriched_context = (
            enriched_context is not None and enriched_context.baselines is not None
        )
        has_enrichment_result = enrichment_result is not None and (
            enrichment_result.has_license_plates or enrichment_result.has_faces
        )
        has_vision_extraction = (
            enrichment_result is not None and enrichment_result.has_vision_extraction
        )

        # Check for full model zoo enrichment (clothing, violence, vehicle analysis, etc.)
        has_model_zoo_enrichment = enrichment_result is not None and (
            enrichment_result.has_violence
            or enrichment_result.has_clothing_classifications
            or enrichment_result.has_vehicle_classifications
            or enrichment_result.has_vehicle_damage
            or enrichment_result.has_pet_classifications
            or enrichment_result.has_image_quality
        )

        # Track which template is used for metrics
        template_name: str = "basic"  # Default, will be overwritten

        if has_model_zoo_enrichment and has_enriched_context:
            # Use MODEL_ZOO_ENHANCED prompt with full enrichment from all models
            template_name = "model_zoo"
            from backend.services.reid_service import format_full_reid_context
            from backend.services.vision_extractor import (
                format_scene_analysis,
            )

            assert enriched_context is not None
            assert enriched_context.baselines is not None
            assert enrichment_result is not None

            enricher = self._get_context_enricher()

            # Determine time of day from environment context or vision extraction
            time_of_day = "day"
            if (
                enrichment_result.vision_extraction
                and enrichment_result.vision_extraction.environment_context
            ):
                time_of_day = enrichment_result.vision_extraction.environment_context.time_of_day

            # Format scene analysis
            scene_text = "No scene analysis available."
            if (
                enrichment_result.vision_extraction
                and enrichment_result.vision_extraction.scene_analysis
            ):
                scene_text = format_scene_analysis(
                    enrichment_result.vision_extraction.scene_analysis
                )

            # Format re-id context
            reid_text = format_full_reid_context(
                enrichment_result.person_reid_matches,
                enrichment_result.vehicle_reid_matches,
            )

            # Format all model zoo enrichment contexts
            prompt = MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT.format(
                camera_name=camera_name,
                timestamp=f"{start_time} to {end_time}",
                day_of_week=enriched_context.baselines.day_of_week,
                time_of_day=time_of_day,
                # Environmental context
                weather_context=format_weather_context(enrichment_result.weather_classification),
                image_quality_context=format_image_quality_context(
                    enrichment_result.image_quality,
                    enrichment_result.quality_change_detected,
                    enrichment_result.quality_change_description,
                ),
                # Detections with all enrichment
                detections_with_all_attributes=format_detections_with_all_enrichment(
                    [],  # Will use enrichment_result.to_context_string() for now
                    enrichment_result,
                    enrichment_result.vision_extraction,
                )
                if enrichment_result.vision_extraction
                else enrichment_result.to_context_string(),
                # Violence analysis
                violence_context=format_violence_context(enrichment_result.violence_detection),
                # Behavioral analysis (future: ViTPose, X-CLIP)
                pose_analysis=format_pose_analysis_context(None),  # TODO: Add pose results
                action_recognition=format_action_recognition_context(
                    None
                ),  # TODO: Add action results
                # Vehicle analysis
                vehicle_classification_context=format_vehicle_classification_context(
                    enrichment_result.vehicle_classifications
                ),
                vehicle_damage_context=format_vehicle_damage_context(
                    enrichment_result.vehicle_damage,
                    time_of_day=time_of_day,
                ),
                # Person analysis
                clothing_analysis_context=format_clothing_analysis_context(
                    enrichment_result.clothing_classifications,
                    enrichment_result.clothing_segmentation,
                ),
                # Pet detection
                pet_classification_context=format_pet_classification_context(
                    enrichment_result.pet_classifications
                ),
                # Spatial context (future: Depth Anything V2)
                depth_context=format_depth_context(None),  # TODO: Add depth results
                # Re-identification
                reid_context=reid_text,
                # Zone, baseline, cross-camera
                zone_analysis=enricher.format_zone_analysis(enriched_context.zones),
                baseline_comparison=enricher.format_baseline_comparison(enriched_context.baselines),
                deviation_score=f"{enriched_context.baselines.deviation_score:.2f}",
                cross_camera_summary=enricher.format_cross_camera_summary(
                    enriched_context.cross_camera
                ),
                scene_analysis=scene_text,
            )
        elif has_vision_extraction and has_enriched_context:
            # Use vision-enhanced prompt with Florence-2 attributes, re-id, and scene analysis
            template_name = "vision"
            from backend.services.reid_service import format_full_reid_context
            from backend.services.vision_extractor import (
                format_scene_analysis,
            )

            assert enriched_context is not None
            assert enriched_context.baselines is not None
            assert enrichment_result is not None
            assert enrichment_result.vision_extraction is not None

            enricher = self._get_context_enricher()

            # Determine time of day from environment context
            time_of_day = "day"
            if enrichment_result.vision_extraction.environment_context:
                time_of_day = enrichment_result.vision_extraction.environment_context.time_of_day

            # Format scene analysis
            scene_text = "No scene analysis available."
            if enrichment_result.vision_extraction.scene_analysis:
                scene_text = format_scene_analysis(
                    enrichment_result.vision_extraction.scene_analysis
                )

            # Format re-id context
            reid_text = format_full_reid_context(
                enrichment_result.person_reid_matches,
                enrichment_result.vehicle_reid_matches,
            )

            prompt = VISION_ENHANCED_RISK_ANALYSIS_PROMPT.format(
                camera_name=camera_name,
                timestamp=f"{start_time} to {end_time}",
                day_of_week=enriched_context.baselines.day_of_week,
                time_of_day=time_of_day,
                detections_with_attributes=enrichment_result.to_context_string(),
                reid_context=reid_text,
                zone_analysis=enricher.format_zone_analysis(enriched_context.zones),
                baseline_comparison=enricher.format_baseline_comparison(enriched_context.baselines),
                deviation_score=f"{enriched_context.baselines.deviation_score:.2f}",
                cross_camera_summary=enricher.format_cross_camera_summary(
                    enriched_context.cross_camera
                ),
                scene_analysis=scene_text,
            )
        elif has_enriched_context and has_enrichment_result:
            # Use full enriched prompt with zone, baseline, cross-camera, and pipeline context
            template_name = "full_enriched"
            # These assertions help mypy understand type narrowing
            assert enriched_context is not None
            assert enriched_context.baselines is not None
            assert enrichment_result is not None
            enricher = self._get_context_enricher()
            prompt = FULL_ENRICHED_RISK_ANALYSIS_PROMPT.format(
                camera_name=camera_name,
                start_time=start_time,
                end_time=end_time,
                day_of_week=enriched_context.baselines.day_of_week,
                zone_analysis=enricher.format_zone_analysis(enriched_context.zones),
                hour=enriched_context.baselines.hour_of_day,
                baseline_comparison=enricher.format_baseline_comparison(enriched_context.baselines),
                deviation_score=f"{enriched_context.baselines.deviation_score:.2f}",
                cross_camera_summary=enricher.format_cross_camera_summary(
                    enriched_context.cross_camera
                ),
                enrichment_context=enrichment_result.to_context_string(),
                detections_list=detections_list,
            )
        elif has_enriched_context:
            # Use enriched prompt with zone, baseline, and cross-camera context (no pipeline)
            template_name = "enriched"
            # These assertions help mypy understand type narrowing
            assert enriched_context is not None
            assert enriched_context.baselines is not None
            enricher = self._get_context_enricher()
            prompt = ENRICHED_RISK_ANALYSIS_PROMPT.format(
                camera_name=camera_name,
                start_time=start_time,
                end_time=end_time,
                day_of_week=enriched_context.baselines.day_of_week,
                zone_analysis=enricher.format_zone_analysis(enriched_context.zones),
                hour=enriched_context.baselines.hour_of_day,
                baseline_comparison=enricher.format_baseline_comparison(enriched_context.baselines),
                deviation_score=f"{enriched_context.baselines.deviation_score:.2f}",
                cross_camera_summary=enricher.format_cross_camera_summary(
                    enriched_context.cross_camera
                ),
                detections_list=detections_list,
            )
        else:
            # Fall back to basic prompt
            prompt = RISK_ANALYSIS_PROMPT.format(
                camera_name=camera_name,
                start_time=start_time,
                end_time=end_time,
                detections_list=detections_list,
            )

        # Call llama.cpp completion endpoint
        # Nemotron-3-Nano uses ChatML format with <|im_end|> as message terminator
        payload = {
            "prompt": prompt,
            "temperature": 0.7,  # Slightly creative for detailed reasoning
            "top_p": 0.95,
            "max_tokens": 1536,  # Extra room for detailed explanations
            "stop": ["<|im_end|>", "<|im_start|>"],
        }

        # Merge auth headers with JSON content-type
        headers = {"Content-Type": "application/json"}
        headers.update(self._get_auth_headers())

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._llm_url}/completion",
                json=payload,
                headers=headers,
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

        # Record risk analysis metrics (NEM-769)
        observe_risk_score(risk_data["risk_score"])
        record_event_by_risk_level(risk_data["risk_level"])
        record_prompt_template_used(template_name)

        # Include the prompt in the response for debugging/improvement
        risk_data["llm_prompt"] = prompt

        return risk_data

    def _parse_llm_response(self, text: str) -> dict[str, Any]:
        """Parse JSON response from LLM completion.

        Handles Nemotron-3-Nano output which includes <think>...</think> reasoning
        blocks before the actual JSON response.

        Args:
            text: LLM completion text

        Returns:
            Parsed dictionary with risk assessment

        Raises:
            ValueError: If JSON cannot be extracted or parsed
        """
        # Strip <think>...</think> reasoning blocks (Nemotron-3-Nano format)
        # The model outputs reasoning in <think> tags before the JSON
        think_pattern = r"<think>.*?</think>"
        cleaned_text = re.sub(think_pattern, "", text, flags=re.DOTALL).strip()

        # Also handle incomplete think blocks (model may not close the tag)
        if "<think>" in cleaned_text:
            # Find content after the last </think> or after <think>...
            parts = cleaned_text.split("</think>")
            if len(parts) > 1:
                cleaned_text = parts[-1].strip()
            else:
                # No closing tag, try to find JSON after <think> block
                think_start = cleaned_text.find("<think>")
                # Look for JSON start after think
                json_start = cleaned_text.find("{", think_start)
                if json_start != -1:
                    cleaned_text = cleaned_text[json_start:]

        # Handle "thinking out loud" without <think> tags
        # If text starts with non-JSON content, skip to first {
        first_brace = cleaned_text.find("{")
        if first_brace > 0:
            # Check if there's preamble text before the JSON
            preamble = cleaned_text[:first_brace].strip()
            if preamble and not preamble.startswith("{"):
                logger.debug(f"Skipping LLM preamble: {preamble[:100]}...")
                cleaned_text = cleaned_text[first_brace:]

        # Try to extract JSON from the cleaned text
        # Look for JSON object pattern (handles nested objects)
        json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        matches = re.findall(json_pattern, cleaned_text, re.DOTALL)

        # If no matches in cleaned text, try original text as fallback
        if not matches:
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
        """Validate and normalize risk assessment data using Pydantic schemas.

        Uses LLMRawResponse for lenient parsing, then converts to validated
        LLMRiskResponse via to_validated_response(). This ensures:
        - risk_score is clamped to 0-100
        - risk_level is valid (inferred from score if invalid)
        - summary and reasoning have defaults if missing

        Args:
            data: Raw risk data dictionary from LLM JSON response

        Returns:
            Validated and normalized risk data dictionary

        Note:
            This method uses the default severity thresholds from the schema.
            For dynamic thresholds based on Settings, the SeverityService can
            still be used as a fallback when risk_level inference is needed.
        """
        try:
            # First try strict validation with LLMRiskResponse
            # This handles well-formed LLM responses directly
            validated = LLMRiskResponse.model_validate(data)
            return validated.model_dump()
        except ValidationError:
            # Fall back to lenient parsing with LLMRawResponse
            # This handles malformed responses (out-of-range scores, invalid levels)
            pass

        try:
            # Parse with lenient schema, then normalize
            raw = LLMRawResponse.model_validate(data)
            validated = raw.to_validated_response()
            return validated.model_dump()
        except ValidationError as e:
            # If even lenient parsing fails, use defaults with any available data
            logger.warning(
                f"Failed to validate LLM response, using defaults: {e}",
                extra={"validation_errors": str(e.errors())},
            )

            # Extract what we can from the raw data
            risk_score = 50  # Default
            if "risk_score" in data:
                try:
                    score = data["risk_score"]
                    if isinstance(score, (int, float)):
                        risk_score = max(0, min(100, int(score)))
                    elif isinstance(score, str):
                        risk_score = max(0, min(100, int(float(score))))
                except (ValueError, TypeError):
                    pass

            # Infer risk_level from score using SeverityService for consistency
            from backend.services.severity import get_severity_service

            severity_service = get_severity_service()
            severity = severity_service.risk_score_to_severity(risk_score)

            return {
                "risk_score": risk_score,
                "risk_level": severity.value,
                "summary": data.get("summary", "Risk analysis completed"),
                "reasoning": data.get("reasoning", "No detailed reasoning provided"),
            }

    async def _broadcast_event(self, event: Event) -> None:
        """Broadcast event via WebSocket (optional).

        Publishes to the canonical 'security_events' Redis channel with the standard
        message envelope format: {"type": "event", "data": {...}}.

        This allows EventBroadcaster (which subscribes to 'security_events') to forward
        the event to all connected /ws/events WebSocket clients.

        Args:
            event: Event to broadcast
        """
        if not self._redis:
            return

        try:
            # Use the canonical message envelope format expected by EventBroadcaster
            # and frontend WebSocket clients: {"type": "event", "data": {...}}
            message = {
                "type": "event",
                "data": {
                    "id": event.id,
                    "event_id": event.id,  # Legacy field for compatibility
                    "batch_id": event.batch_id,
                    "camera_id": event.camera_id,
                    "risk_score": event.risk_score,
                    "risk_level": event.risk_level,
                    "summary": event.summary,
                    "reasoning": event.reasoning,
                    "started_at": event.started_at.isoformat() if event.started_at else None,
                },
            }

            # Use EventBroadcaster API instead of direct Redis publish
            from backend.services.event_broadcaster import get_broadcaster

            broadcaster = await get_broadcaster(self._redis)
            await broadcaster.broadcast_event(message)
            logger.debug(f"Broadcasted event {event.id} via WebSocket")
        except Exception as e:  # pragma: no cover
            logger.warning(f"Failed to broadcast event: {e}", exc_info=True)  # pragma: no cover
