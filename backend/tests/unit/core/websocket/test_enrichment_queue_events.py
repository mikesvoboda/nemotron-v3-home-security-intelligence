"""Unit tests for enrichment and queue metrics WebSocket event types.

NEM-3627: Enrichment WebSocket events
NEM-3637: Queue metrics WebSocket events

Tests for the new enrichment and queue-related WebSocket event types
including validation, metadata, and channel routing.
"""

from backend.core.websocket import (
    EVENT_TYPE_METADATA,
    WebSocketEventType,
    create_event,
    get_event_channel,
    get_required_payload_fields,
    validate_event_type,
)


class TestEnrichmentEventTypes:
    """Tests for enrichment WebSocket event types (NEM-3627)."""

    def test_enrichment_started_event_type_exists(self):
        """Verify ENRICHMENT_STARTED event type is defined."""
        assert hasattr(WebSocketEventType, "ENRICHMENT_STARTED")
        assert WebSocketEventType.ENRICHMENT_STARTED.value == "enrichment.started"

    def test_enrichment_progress_event_type_exists(self):
        """Verify ENRICHMENT_PROGRESS event type is defined."""
        assert hasattr(WebSocketEventType, "ENRICHMENT_PROGRESS")
        assert WebSocketEventType.ENRICHMENT_PROGRESS.value == "enrichment.progress"

    def test_enrichment_completed_event_type_exists(self):
        """Verify ENRICHMENT_COMPLETED event type is defined."""
        assert hasattr(WebSocketEventType, "ENRICHMENT_COMPLETED")
        assert WebSocketEventType.ENRICHMENT_COMPLETED.value == "enrichment.completed"

    def test_enrichment_failed_event_type_exists(self):
        """Verify ENRICHMENT_FAILED event type is defined."""
        assert hasattr(WebSocketEventType, "ENRICHMENT_FAILED")
        assert WebSocketEventType.ENRICHMENT_FAILED.value == "enrichment.failed"

    def test_enrichment_events_follow_naming_convention(self):
        """Verify all enrichment events follow domain.action pattern."""
        enrichment_types = [
            WebSocketEventType.ENRICHMENT_STARTED,
            WebSocketEventType.ENRICHMENT_PROGRESS,
            WebSocketEventType.ENRICHMENT_COMPLETED,
            WebSocketEventType.ENRICHMENT_FAILED,
        ]
        for event_type in enrichment_types:
            assert event_type.value.startswith("enrichment.")

    def test_enrichment_events_have_metadata(self):
        """Verify all enrichment event types have metadata entries."""
        enrichment_types = [
            WebSocketEventType.ENRICHMENT_STARTED,
            WebSocketEventType.ENRICHMENT_PROGRESS,
            WebSocketEventType.ENRICHMENT_COMPLETED,
            WebSocketEventType.ENRICHMENT_FAILED,
        ]
        for event_type in enrichment_types:
            assert event_type in EVENT_TYPE_METADATA, f"Missing metadata for {event_type}"

    def test_enrichment_events_have_enrichment_channel(self):
        """Verify enrichment events return enrichment channel."""
        assert get_event_channel(WebSocketEventType.ENRICHMENT_STARTED) == "enrichment"
        assert get_event_channel(WebSocketEventType.ENRICHMENT_PROGRESS) == "enrichment"
        assert get_event_channel(WebSocketEventType.ENRICHMENT_COMPLETED) == "enrichment"
        assert get_event_channel(WebSocketEventType.ENRICHMENT_FAILED) == "enrichment"

    def test_enrichment_started_has_required_fields(self):
        """Verify ENRICHMENT_STARTED has expected required fields."""
        fields = get_required_payload_fields(WebSocketEventType.ENRICHMENT_STARTED)
        assert "batch_id" in fields
        assert "camera_id" in fields
        assert "detection_count" in fields

    def test_enrichment_progress_has_required_fields(self):
        """Verify ENRICHMENT_PROGRESS has expected required fields."""
        fields = get_required_payload_fields(WebSocketEventType.ENRICHMENT_PROGRESS)
        assert "batch_id" in fields
        assert "progress" in fields
        assert "current_step" in fields

    def test_enrichment_completed_has_required_fields(self):
        """Verify ENRICHMENT_COMPLETED has expected required fields."""
        fields = get_required_payload_fields(WebSocketEventType.ENRICHMENT_COMPLETED)
        assert "batch_id" in fields
        assert "status" in fields
        assert "enriched_count" in fields

    def test_enrichment_failed_has_required_fields(self):
        """Verify ENRICHMENT_FAILED has expected required fields."""
        fields = get_required_payload_fields(WebSocketEventType.ENRICHMENT_FAILED)
        assert "batch_id" in fields
        assert "error" in fields

    def test_validate_enrichment_event_types(self):
        """Verify enrichment event type strings can be validated."""
        assert validate_event_type("enrichment.started") == WebSocketEventType.ENRICHMENT_STARTED
        assert validate_event_type("enrichment.progress") == WebSocketEventType.ENRICHMENT_PROGRESS
        assert (
            validate_event_type("enrichment.completed") == WebSocketEventType.ENRICHMENT_COMPLETED
        )
        assert validate_event_type("enrichment.failed") == WebSocketEventType.ENRICHMENT_FAILED

    def test_create_enrichment_started_event(self):
        """Test creating an enrichment started event."""
        event = create_event(
            WebSocketEventType.ENRICHMENT_STARTED,
            {
                "batch_id": "batch-123",
                "camera_id": "front_door",
                "detection_count": 5,
            },
        )
        assert event["type"] == WebSocketEventType.ENRICHMENT_STARTED
        assert event["payload"]["batch_id"] == "batch-123"
        assert event["payload"]["detection_count"] == 5

    def test_create_enrichment_progress_event(self):
        """Test creating an enrichment progress event."""
        event = create_event(
            WebSocketEventType.ENRICHMENT_PROGRESS,
            {
                "batch_id": "batch-123",
                "progress": 50,
                "current_step": "license_plate_detection",
                "total_steps": 4,
            },
        )
        assert event["type"] == WebSocketEventType.ENRICHMENT_PROGRESS
        assert event["payload"]["progress"] == 50


class TestQueueMetricsEventTypes:
    """Tests for queue metrics WebSocket event types (NEM-3637)."""

    def test_queue_status_event_type_exists(self):
        """Verify QUEUE_STATUS event type is defined."""
        assert hasattr(WebSocketEventType, "QUEUE_STATUS")
        assert WebSocketEventType.QUEUE_STATUS.value == "queue.status"

    def test_pipeline_throughput_event_type_exists(self):
        """Verify PIPELINE_THROUGHPUT event type is defined."""
        assert hasattr(WebSocketEventType, "PIPELINE_THROUGHPUT")
        assert WebSocketEventType.PIPELINE_THROUGHPUT.value == "pipeline.throughput"

    def test_queue_events_follow_naming_convention(self):
        """Verify queue events follow domain.action pattern."""
        assert WebSocketEventType.QUEUE_STATUS.value.startswith("queue.")
        assert WebSocketEventType.PIPELINE_THROUGHPUT.value.startswith("pipeline.")

    def test_queue_events_have_metadata(self):
        """Verify queue event types have metadata entries."""
        assert WebSocketEventType.QUEUE_STATUS in EVENT_TYPE_METADATA
        assert WebSocketEventType.PIPELINE_THROUGHPUT in EVENT_TYPE_METADATA

    def test_queue_events_have_system_channel(self):
        """Verify queue events return system channel (broadcast with system status)."""
        assert get_event_channel(WebSocketEventType.QUEUE_STATUS) == "system"
        assert get_event_channel(WebSocketEventType.PIPELINE_THROUGHPUT) == "system"

    def test_queue_status_has_required_fields(self):
        """Verify QUEUE_STATUS has expected required fields."""
        fields = get_required_payload_fields(WebSocketEventType.QUEUE_STATUS)
        assert "queues" in fields
        assert "total_queued" in fields
        assert "total_processing" in fields

    def test_pipeline_throughput_has_required_fields(self):
        """Verify PIPELINE_THROUGHPUT has expected required fields."""
        fields = get_required_payload_fields(WebSocketEventType.PIPELINE_THROUGHPUT)
        assert "detections_per_minute" in fields
        assert "events_per_minute" in fields

    def test_validate_queue_event_types(self):
        """Verify queue event type strings can be validated."""
        assert validate_event_type("queue.status") == WebSocketEventType.QUEUE_STATUS
        assert validate_event_type("pipeline.throughput") == WebSocketEventType.PIPELINE_THROUGHPUT

    def test_create_queue_status_event(self):
        """Test creating a queue status event."""
        event = create_event(
            WebSocketEventType.QUEUE_STATUS,
            {
                "queues": [
                    {"name": "detection", "depth": 5, "workers": 2},
                    {"name": "analysis", "depth": 3, "workers": 1},
                ],
                "total_queued": 8,
                "total_processing": 3,
                "overall_status": "healthy",
            },
        )
        assert event["type"] == WebSocketEventType.QUEUE_STATUS
        assert event["payload"]["total_queued"] == 8

    def test_create_pipeline_throughput_event(self):
        """Test creating a pipeline throughput event."""
        event = create_event(
            WebSocketEventType.PIPELINE_THROUGHPUT,
            {
                "detections_per_minute": 120.5,
                "events_per_minute": 15.2,
                "enrichments_per_minute": 12.0,
            },
        )
        assert event["type"] == WebSocketEventType.PIPELINE_THROUGHPUT
        assert event["payload"]["detections_per_minute"] == 120.5


class TestEnrichmentChannelInRegistry:
    """Tests to verify enrichment channel is added to registry."""

    def test_enrichment_channel_in_all_channels(self):
        """Verify enrichment channel is included in get_all_channels."""
        from backend.core.websocket import get_all_channels

        channels = get_all_channels()
        assert "enrichment" in channels

    def test_metadata_channels_include_enrichment(self):
        """Verify enrichment is a valid channel in metadata."""
        valid_channels = set()
        for metadata in EVENT_TYPE_METADATA.values():
            channel = metadata.get("channel")
            if channel is not None:
                valid_channels.add(channel)
        assert "enrichment" in valid_channels
