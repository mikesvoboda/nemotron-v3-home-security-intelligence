"""WebSocket contract tests for real-time event streaming.

This module tests WebSocket message formats to ensure frontend consumers
can reliably parse and handle real-time updates from the backend.

WebSocket Message Types Tested:
- event: Security event notifications
- service_status: Service health updates
- scene_change: Camera scene change alerts
- error: Error messages
- pong: Heartbeat responses

Contract Validation:
- Message structure matches documented schemas
- Required fields are always present
- Data types are correct
- Enum values match frontend expectations
- Risk scores are within valid ranges (0-100)
"""

from __future__ import annotations

import os

import pytest

# Set test environment before importing app
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/security_test",  # pragma: allowlist secret
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")


# =============================================================================
# WebSocket Schema Contract Tests
# =============================================================================


class TestWebSocketMessageSchemas:
    """Contract tests for WebSocket message schemas.

    These tests verify that the backend WebSocket message schemas match
    the documented frontend TypeScript contracts. They test schema structure
    rather than actual WebSocket connections.
    """

    def test_event_message_schema_contract(self):
        """Test WebSocketEventMessage schema matches frontend SecurityEventMessage."""
        from backend.api.schemas.websocket import WebSocketEventMessage

        # Get schema from the Pydantic model
        schema = WebSocketEventMessage.model_json_schema()

        # Verify top-level structure
        assert "properties" in schema
        properties = schema["properties"]

        # Required fields expected by frontend
        assert "type" in properties
        assert "data" in properties

        # Verify type discriminator
        assert properties["type"]["const"] == "event"

    def test_event_data_schema_contract(self):
        """Test WebSocketEventData schema matches frontend SecurityEventData."""
        from backend.api.schemas.websocket import WebSocketEventData

        schema = WebSocketEventData.model_json_schema()
        properties = schema["properties"]

        # Required fields expected by frontend SecurityEventData type
        required_fields = [
            "id",
            "event_id",
            "batch_id",
            "camera_id",
            "risk_score",
            "risk_level",
            "summary",
            "reasoning",
        ]

        for field in required_fields:
            assert field in properties, f"Missing required field: {field}"

        # Verify risk_score constraints (critical for frontend risk gauge)
        assert properties["risk_score"]["minimum"] == 0
        assert properties["risk_score"]["maximum"] == 100

    def test_service_status_message_schema_contract(self):
        """Test WebSocketServiceStatusMessage matches frontend ServiceStatusMessage."""
        from backend.api.schemas.websocket import WebSocketServiceStatusMessage

        schema = WebSocketServiceStatusMessage.model_json_schema()
        properties = schema["properties"]

        # Required fields
        assert "type" in properties
        assert "data" in properties
        assert "timestamp" in properties

        # Verify type discriminator
        assert properties["type"]["const"] == "service_status"

    def test_service_status_data_schema_contract(self):
        """Test WebSocketServiceStatusData matches frontend ServiceStatusData."""
        from backend.api.schemas.websocket import WebSocketServiceStatusData

        schema = WebSocketServiceStatusData.model_json_schema()
        properties = schema["properties"]

        # Required fields expected by frontend
        required_fields = ["service", "status"]

        for field in required_fields:
            assert field in properties, f"Missing required field: {field}"

        # Optional fields that frontend uses
        assert "message" in properties

    def test_scene_change_message_schema_contract(self):
        """Test WebSocketSceneChangeMessage matches frontend SceneChangeMessage."""
        from backend.api.schemas.websocket import WebSocketSceneChangeMessage

        schema = WebSocketSceneChangeMessage.model_json_schema()
        properties = schema["properties"]

        # Required fields
        assert "type" in properties
        assert "data" in properties

        # Verify type discriminator
        assert properties["type"]["const"] == "scene_change"

    def test_scene_change_data_schema_contract(self):
        """Test WebSocketSceneChangeData matches frontend SceneChangeData."""
        from backend.api.schemas.websocket import WebSocketSceneChangeData

        schema = WebSocketSceneChangeData.model_json_schema()
        properties = schema["properties"]

        # Required fields expected by frontend
        required_fields = [
            "id",
            "camera_id",
            "detected_at",
            "change_type",
            "similarity_score",
        ]

        for field in required_fields:
            assert field in properties, f"Missing required field: {field}"

        # Verify similarity_score constraints
        assert properties["similarity_score"]["minimum"] == 0.0
        assert properties["similarity_score"]["maximum"] == 1.0

    def test_error_response_schema_contract(self):
        """Test WebSocketErrorResponse matches frontend ErrorMessage."""
        from backend.api.schemas.websocket import WebSocketErrorResponse

        schema = WebSocketErrorResponse.model_json_schema()
        properties = schema["properties"]

        # Required fields expected by frontend ErrorMessage type
        assert "type" in properties
        assert "error" in properties
        assert "message" in properties

        # Verify type discriminator
        assert properties["type"]["const"] == "error"

    def test_pong_response_schema_contract(self):
        """Test WebSocketPongResponse matches frontend PongMessage."""
        from backend.api.schemas.websocket import WebSocketPongResponse

        schema = WebSocketPongResponse.model_json_schema()
        properties = schema["properties"]

        # Verify type discriminator
        assert "type" in properties
        assert properties["type"]["const"] == "pong"

    def test_risk_level_enum_contract(self):
        """Test RiskLevel enum values match frontend RiskLevel type."""
        from backend.api.schemas.websocket import RiskLevel

        # Frontend expects these exact values (lowercase)
        expected_values = {"low", "medium", "high", "critical"}
        actual_values = {level.value for level in RiskLevel}

        assert actual_values == expected_values, (
            f"RiskLevel enum mismatch. Expected: {expected_values}, Actual: {actual_values}"
        )


# =============================================================================
# WebSocket Message Serialization Contract Tests
# =============================================================================


class TestWebSocketMessageSerialization:
    """Contract tests for WebSocket message serialization.

    These tests verify that WebSocket messages can be correctly serialized
    to JSON and that the serialized format matches frontend expectations.
    """

    def test_event_message_serialization_contract(self):
        """Test that event messages serialize correctly for frontend consumption."""
        from datetime import UTC, datetime

        from backend.api.schemas.websocket import WebSocketEventData, WebSocketEventMessage

        # Create a sample event message
        event_data = WebSocketEventData(
            id=1,
            event_id=1,
            batch_id="batch_123",
            camera_id="front_door",
            risk_score=75,
            risk_level="high",
            summary="Person detected",
            reasoning="High confidence detection",
            detected_at=datetime.now(UTC),
        )

        message = WebSocketEventMessage(type="event", data=event_data)

        # Serialize to dict (as would be sent over WebSocket)
        serialized = message.model_dump(mode="json")

        # Verify structure matches frontend expectations
        assert serialized["type"] == "event"
        assert "data" in serialized

        data = serialized["data"]
        assert data["id"] == 1
        assert data["event_id"] == 1
        assert data["camera_id"] == "front_door"
        assert data["risk_score"] == 75
        assert data["risk_level"] == "high"
        assert 0 <= data["risk_score"] <= 100

    def test_service_status_message_serialization_contract(self):
        """Test that service status messages serialize correctly."""
        from datetime import UTC, datetime

        from backend.api.schemas.websocket import (
            WebSocketServiceStatusData,
            WebSocketServiceStatusMessage,
        )

        # Create a sample service status message
        status_data = WebSocketServiceStatusData(
            service="yolo26",
            status="healthy",
            message="Service is running normally",
        )

        # timestamp field expects ISO string, not datetime object
        message = WebSocketServiceStatusMessage(
            type="service_status",
            data=status_data,
            timestamp=datetime.now(UTC).isoformat(),
        )

        # Serialize to dict
        serialized = message.model_dump(mode="json")

        # Verify structure
        assert serialized["type"] == "service_status"
        assert "data" in serialized
        assert "timestamp" in serialized

        data = serialized["data"]
        assert data["service"] == "yolo26"
        assert data["status"] == "healthy"

    def test_error_response_serialization_contract(self):
        """Test that error responses serialize correctly."""
        from backend.api.schemas.websocket import WebSocketErrorResponse

        # Create a sample error response
        error = WebSocketErrorResponse(
            type="error",
            error="validation_error",
            message="Invalid subscription request",
        )

        # Serialize to dict
        serialized = error.model_dump(mode="json")

        # Verify structure
        assert serialized["type"] == "error"
        assert serialized["error"] == "validation_error"
        assert serialized["message"] == "Invalid subscription request"


# =============================================================================
# WebSocket Connection Contract Tests
# =============================================================================
#
# Note: WebSocket connection tests are handled in integration tests
# (backend/tests/integration/test_websocket.py) since httpx.AsyncClient
# doesn't support WebSocket connections. Contract tests focus on message
# schema validation rather than connection lifecycle.
#
# For WebSocket connection testing, see:
# - backend/tests/integration/test_websocket.py
# - frontend/tests/e2e/specs/websocket.spec.ts


# =============================================================================
# Risk Score Range Contract Tests
# =============================================================================


class TestRiskScoreRangeContract:
    """Contract tests for risk score validation.

    These tests ensure risk scores are always within the valid range (0-100),
    which is critical for frontend visualization and decision-making.
    """

    def test_risk_score_validation_contract(self):
        """Test that risk scores are validated to be within 0-100 range."""
        from pydantic import ValidationError

        from backend.api.schemas.websocket import WebSocketEventData

        # Valid risk scores should not raise errors
        valid_scores = [0, 25, 50, 75, 100]
        for score in valid_scores:
            data = WebSocketEventData(
                id=1,
                event_id=1,
                batch_id="test",
                camera_id="test",
                risk_score=score,
                risk_level="low",
                summary="test",
                reasoning="test",
            )
            assert data.risk_score == score

        # Invalid risk scores should raise validation errors
        invalid_scores = [-1, -100, 101, 200]
        for score in invalid_scores:
            with pytest.raises(ValidationError):
                WebSocketEventData(
                    id=1,
                    event_id=1,
                    batch_id="test",
                    camera_id="test",
                    risk_score=score,
                    risk_level="low",
                    summary="test",
                    reasoning="test",
                )

    def test_similarity_score_validation_contract(self):
        """Test that similarity scores are validated to be within 0.0-1.0 range."""
        from datetime import UTC, datetime

        from pydantic import ValidationError

        from backend.api.schemas.websocket import WebSocketSceneChangeData

        # detected_at field expects ISO string, not datetime object
        now_iso = datetime.now(UTC).isoformat()

        # Valid similarity scores should not raise errors
        valid_scores = [0.0, 0.25, 0.5, 0.75, 1.0]
        for score in valid_scores:
            data = WebSocketSceneChangeData(
                id=1,
                camera_id="test",
                detected_at=now_iso,
                change_type="content",
                similarity_score=score,
            )
            assert data.similarity_score == score

        # Invalid similarity scores should raise validation errors
        invalid_scores = [-0.1, -1.0, 1.1, 2.0]
        for score in invalid_scores:
            with pytest.raises(ValidationError):
                WebSocketSceneChangeData(
                    id=1,
                    camera_id="test",
                    detected_at=now_iso,
                    change_type="content",
                    similarity_score=score,
                )
