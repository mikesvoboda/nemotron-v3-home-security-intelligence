"""Streaming extensions for NemotronAnalyzer (NEM-1665).

This module provides streaming methods for the NemotronAnalyzer class
to enable progressive LLM response updates during long inference times.
"""

import json
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy import select

from backend.api.schemas.streaming import (
    StreamingCompleteEvent,
    StreamingErrorCode,
    StreamingErrorEvent,
    StreamingProgressEvent,
)
from backend.core.config import get_settings
from backend.core.database import get_session
from backend.core.logging import get_logger
from backend.core.metrics import (
    observe_ai_request_duration,
    observe_stage_duration,
    record_event_by_camera,
    record_event_created,
)
from backend.models.camera import Camera
from backend.models.event import Event
from backend.models.event_detection import event_detections
from backend.models.llm_interaction import LLMInteraction
from backend.services.batch_fetch import batch_fetch_detections
from backend.services.enrichment_pipeline import EnrichmentResult
from backend.services.inference_semaphore import get_inference_semaphore

if TYPE_CHECKING:
    from backend.services.context_enricher import EnrichedContext

logger = get_logger(__name__)


async def call_llm_streaming(
    analyzer: Any,
    camera_name: str,
    start_time: str,
    end_time: str,
    detections_list: str,
    enriched_context: EnrichedContext | None = None,
    enrichment_result: EnrichmentResult | None = None,
    camera_health_context: str = "",
    detection_dicts: list[dict[str, Any]] | None = None,
    auto_tuning_context: str = "",
    household_context: str = "",
) -> AsyncGenerator[str]:
    """Call Nemotron LLM with streaming response for progressive updates."""
    from backend.services.prompt_sanitizer import (
        sanitize_camera_name,
        sanitize_detection_description,
    )

    camera_name = sanitize_camera_name(camera_name)
    detections_list = sanitize_detection_description(detections_list)

    prompt = analyzer._build_prompt(
        camera_name=camera_name,
        start_time=start_time,
        end_time=end_time,
        detections_list=detections_list,
        enriched_context=enriched_context,
        enrichment_result=enrichment_result,
        camera_health_context=camera_health_context,
        detection_dicts=detection_dicts,
        auto_tuning_context=auto_tuning_context,
        household_context=household_context,
    )
    prompt = analyzer._validate_and_truncate_prompt(prompt)

    settings = get_settings()
    payload = {
        "prompt": prompt,
        "temperature": 0.3,  # Aligned with non-streaming (NEM-4234 Phase 2)
        "top_p": 0.95,
        "max_tokens": settings.nemotron_max_output_tokens,
        "stop": ["<|im_end|>", "<|im_start|>"],
        "stream": True,
    }

    headers = {"Content-Type": "application/json"}
    headers.update(analyzer._get_auth_headers())

    inference_semaphore = get_inference_semaphore()
    async with inference_semaphore, httpx.AsyncClient(timeout=analyzer._timeout) as client:  # noqa: SIM117
        async with client.stream(
            "POST",
            f"{analyzer._llm_url}/completion",
            json=payload,
            headers=headers,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        content = data.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        logger.warning(f"Malformed SSE data: {data_str[:100]}")


async def analyze_batch_streaming(  # noqa: PLR0911
    analyzer: Any,
    batch_id: str,
    camera_id: str | None = None,
    detection_ids: list[int | str] | None = None,
) -> AsyncGenerator[dict[str, Any]]:
    """Analyze a batch with streaming progress updates (NEM-1665)."""
    if not analyzer._redis:
        yield StreamingErrorEvent(
            error_code=StreamingErrorCode.INTERNAL_ERROR,
            error_message="Redis client not initialized",
            recoverable=False,
        ).model_dump()
        return

    existing_event_id = await analyzer._check_idempotency(batch_id)
    if existing_event_id is not None:
        existing_event = await analyzer._get_existing_event(existing_event_id)
        if existing_event:
            yield StreamingCompleteEvent(
                event_id=existing_event.id,
                risk_score=existing_event.risk_score or 50,
                risk_level=existing_event.risk_level or "medium",
                summary=existing_event.summary or "No summary available",
                reasoning=existing_event.reasoning or "No reasoning available",
            ).model_dump()
            return

    if camera_id is None:
        camera_id = await analyzer._redis.get(f"batch:{batch_id}:camera_id")
        if not camera_id:
            yield StreamingErrorEvent(
                error_code=StreamingErrorCode.BATCH_NOT_FOUND,
                error_message=f"Batch {batch_id} not found in Redis",
                recoverable=False,
            ).model_dump()
            return

    if detection_ids is None:
        detections_data = await analyzer._redis.get(f"batch:{batch_id}:detections")
        detection_ids = json.loads(detections_data) if detections_data else []

    if not detection_ids:
        yield StreamingErrorEvent(
            error_code=StreamingErrorCode.NO_DETECTIONS,
            error_message=f"Batch {batch_id} has no detections",
            recoverable=False,
        ).model_dump()
        return

    analysis_start = time.time()
    logger.info(f"Streaming analysis for batch {batch_id}")

    async with get_session() as session:
        camera_result = await session.execute(select(Camera).where(Camera.id == camera_id))
        camera = camera_result.scalar_one_or_none()
        camera_name = camera.name if camera else camera_id

        try:
            int_detection_ids = [int(d) for d in detection_ids]
        except (ValueError, TypeError) as e:
            yield StreamingErrorEvent(
                error_code=StreamingErrorCode.INTERNAL_ERROR,
                error_message=f"Invalid detection_id: {e}",
                recoverable=False,
            ).model_dump()
            return

        detections = await batch_fetch_detections(session, int_detection_ids)
        if not detections:
            yield StreamingErrorEvent(
                error_code=StreamingErrorCode.NO_DETECTIONS,
                error_message=f"No detections found for batch {batch_id}",
                recoverable=False,
            ).model_dump()
            return

        detection_times = [d.detected_at for d in detections]
        start_time = min(detection_times)
        end_time = max(detection_times)
        detections_list = analyzer._format_detections(detections)

        enriched_context = await analyzer._get_enriched_context(
            batch_id, camera_id, int_detection_ids, session
        )
        enrichment_tracking = await analyzer._get_enrichment_result(
            batch_id, detections, camera_id=camera_id
        )
        enrichment_result: EnrichmentResult | None = None
        if enrichment_tracking is not None and enrichment_tracking.has_data:
            enrichment_result = enrichment_tracking.data

        # Fetch camera health context (NEM-3012)
        from backend.services.prompts import format_camera_health_context

        camera_health_context = ""
        try:
            recent_scene_changes = await analyzer._get_recent_scene_changes(camera_id, session)
            camera_health_context = format_camera_health_context(camera_id, recent_scene_changes)
        except Exception as e:
            logger.warning(
                "Failed to fetch camera health context for streaming",
                extra={"batch_id": batch_id, "error": str(e)},
            )

        # Fetch auto-tuning context from historical audit recommendations (NEM-3015)
        auto_tuning_context = ""
        try:
            auto_tuner = analyzer._get_facade().get_prompt_auto_tuner()
            auto_tuning_context = await auto_tuner.get_tuning_context(
                session=session,
                camera_id=camera_id,
            )
        except Exception as e:
            logger.warning(
                "Failed to fetch auto-tuning context for streaming",
                extra={"batch_id": batch_id, "error": str(e)},
            )

        # Fetch household context (NEM-3024)
        household_context = ""
        try:
            detections_for_household = [
                {
                    "id": d.id,
                    "object_type": d.object_type,
                    "confidence": d.confidence,
                    "file_path": d.file_path,
                    "bounding_box": {
                        "bbox_x": d.bbox_x,
                        "bbox_y": d.bbox_y,
                        "bbox_width": d.bbox_width,
                        "bbox_height": d.bbox_height,
                    }
                    if d.bbox_x is not None
                    else None,
                    "video_width": d.video_width,
                    "video_height": d.video_height,
                    "detected_at": d.detected_at,
                    "track_id": d.track_id,
                    "camera_id": d.camera_id,
                }
                for d in detections
            ]
            household_context = await analyzer._get_household_context(
                detections_for_household, enrichment_result
            )
        except Exception as e:
            logger.warning(
                "Failed to fetch household context for streaming",
                extra={"batch_id": batch_id, "error": str(e)},
            )

        # Build detection dicts for confidence quality summary (NEM-5525)
        detection_dicts = [
            {
                "confidence": d.confidence,
                "class_name": d.object_type or "unknown",
            }
            for d in detections
            if d.confidence is not None
        ]

        accumulated_text = ""
        llm_start = time.time()

        try:
            async for chunk in call_llm_streaming(
                analyzer=analyzer,
                camera_name=camera_name,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                detections_list=detections_list,
                enriched_context=enriched_context,
                enrichment_result=enrichment_result,
                camera_health_context=camera_health_context,
                detection_dicts=detection_dicts,
                auto_tuning_context=auto_tuning_context,
                household_context=household_context,
            ):
                accumulated_text += chunk
                yield StreamingProgressEvent(
                    content=chunk,
                    accumulated_text=accumulated_text,
                ).model_dump()

            observe_ai_request_duration("nemotron", time.time() - llm_start)
        except httpx.TimeoutException as e:
            yield StreamingErrorEvent(
                error_code=StreamingErrorCode.LLM_TIMEOUT,
                error_message=f"LLM timeout: {e}",
                recoverable=True,
            ).model_dump()
            return
        except httpx.ConnectError as e:
            yield StreamingErrorEvent(
                error_code=StreamingErrorCode.LLM_CONNECTION_ERROR,
                error_message=f"LLM connection error: {e}",
                recoverable=True,
            ).model_dump()
            return
        except Exception as e:
            logger.error(f"Streaming LLM error: {e}", exc_info=True)
            yield StreamingErrorEvent(
                error_code=StreamingErrorCode.LLM_SERVER_ERROR,
                error_message="LLM inference failed",
                recoverable=True,
            ).model_dump()
            return

        try:
            risk_data = analyzer._parse_llm_response(accumulated_text)
            risk_data = analyzer._validate_risk_data(risk_data)
        except ValueError:
            risk_data = {
                "risk_score": 50,
                "risk_level": "medium",
                "summary": "Analysis unavailable",
                "reasoning": "Could not parse LLM response",
            }

        event = Event(
            batch_id=batch_id,
            camera_id=camera_id,
            started_at=start_time,
            ended_at=end_time,
            risk_score=risk_data.get("risk_score", 50),
            risk_level=risk_data.get("risk_level", "medium"),
            summary=risk_data.get("summary", "No summary"),
            reasoning=risk_data.get("reasoning", "No reasoning"),
            reviewed=False,
        )

        session.add(event)
        await session.commit()
        await session.refresh(event)

        # Populate event_detections junction table (NEM-1592, NEM-2012, NEM-3350)
        # Uses bulk INSERT with ON CONFLICT DO NOTHING to prevent race conditions
        # and improve performance by reducing round-trips to the database.
        # This is safe because the composite primary key (event_id, detection_id)
        # enforces uniqueness at the database level.
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        if int_detection_ids:
            values = [
                {"event_id": event.id, "detection_id": detection_id}
                for detection_id in int_detection_ids
            ]
            stmt = (
                pg_insert(event_detections)
                .values(values)
                .on_conflict_do_nothing(index_elements=["event_id", "detection_id"])
            )
            await session.execute(stmt)

        # Create LLMInteraction record for AI pipeline observability (NEM-4234)
        # This captures what Nemotron received and responded for debugging accuracy issues
        try:
            # Build enrichment snapshot - frozen copy of what was passed to LLM
            enrichment_snapshot = analyzer._build_enrichment_snapshot(
                detection_ids=int_detection_ids,
                enrichment_result=enrichment_result,
                enriched_context=enriched_context,
            )

            # Build context sources - which enrichment fields were populated
            context_sources = analyzer._build_context_sources(
                enrichment_result=enrichment_result,
                enriched_context=enriched_context,
            )

            # Get household matches if available
            household_matches: dict[str, Any] | None = None
            if enrichment_result is not None:
                person_matches = enrichment_result.person_household_matches
                vehicle_matches = enrichment_result.vehicle_household_matches
                if person_matches or vehicle_matches:
                    household_matches = {
                        "persons": [
                            m.model_dump() if hasattr(m, "model_dump") else m
                            for m in (person_matches or [])
                        ],
                        "vehicles": [
                            m.model_dump() if hasattr(m, "model_dump") else m
                            for m in (vehicle_matches or [])
                        ],
                    }

            llm_interaction = LLMInteraction(
                event_id=event.id,
                raw_response=accumulated_text,  # Use accumulated text as raw response for streaming
                enrichment_snapshot=enrichment_snapshot,
                household_matches=household_matches,
                context_sources=context_sources,
            )
            session.add(llm_interaction)

        except Exception as e:
            # NEM-4234: LLMInteraction failures should not roll back Event creation
            # Observability is optional - we log a warning but continue
            logger.warning(
                "LLMInteraction creation failed",
                extra={
                    "action": "create_llm_interaction",
                    "resource_id": str(event.id),
                    "resource_type": "llm_interaction",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )

        await session.commit()

        await analyzer._set_idempotency(batch_id, event.id)
        observe_stage_duration("analyze", time.time() - analysis_start)
        record_event_created()
        record_event_by_camera(camera_id, camera_name)

        try:
            await analyzer._broadcast_event(event)
        except Exception as e:
            logger.warning(f"Failed to broadcast event: {e}")

        yield StreamingCompleteEvent(
            event_id=event.id,
            risk_score=event.risk_score or 50,
            risk_level=event.risk_level or "medium",
            summary=event.summary or "No summary",
            reasoning=event.reasoning or "No reasoning",
        ).model_dump()
