"""Unit tests for UserCalibration API schemas.

Tests cover:
- UserCalibrationCreate validation (user_id defaults, optional thresholds)
- UserCalibrationUpdate validation (threshold ordering constraint)
- UserCalibrationResponse serialization
- CalibrationAdjustRequest validation (feedback type, event risk score)

NEM-2314: Create UserCalibration Pydantic schemas
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# UserCalibrationCreate Tests
# =============================================================================


class TestUserCalibrationCreate:
    """Tests for UserCalibrationCreate schema."""

    def test_create_with_defaults(self):
        """Test creating calibration with default user_id."""
        from backend.api.schemas.calibration import UserCalibrationCreate

        calibration = UserCalibrationCreate()

        assert calibration.user_id == "default"
        assert calibration.low_threshold is None
        assert calibration.medium_threshold is None
        assert calibration.high_threshold is None
        assert calibration.decay_factor is None

    def test_create_with_custom_user_id(self):
        """Test creating calibration with custom user_id."""
        from backend.api.schemas.calibration import UserCalibrationCreate

        calibration = UserCalibrationCreate(user_id="custom_user")

        assert calibration.user_id == "custom_user"

    def test_create_with_threshold_overrides(self):
        """Test creating calibration with threshold overrides."""
        from backend.api.schemas.calibration import UserCalibrationCreate

        calibration = UserCalibrationCreate(
            user_id="test_user",
            low_threshold=25,
            medium_threshold=55,
            high_threshold=80,
            decay_factor=0.15,
        )

        assert calibration.user_id == "test_user"
        assert calibration.low_threshold == 25
        assert calibration.medium_threshold == 55
        assert calibration.high_threshold == 80
        assert calibration.decay_factor == 0.15

    def test_create_threshold_valid_range(self):
        """Test thresholds accept values in valid range 0-100."""
        from backend.api.schemas.calibration import UserCalibrationCreate

        calibration = UserCalibrationCreate(
            low_threshold=0,
            medium_threshold=50,
            high_threshold=100,
        )

        assert calibration.low_threshold == 0
        assert calibration.medium_threshold == 50
        assert calibration.high_threshold == 100

    def test_create_threshold_below_zero_invalid(self):
        """Test threshold below 0 raises validation error."""
        from backend.api.schemas.calibration import UserCalibrationCreate

        with pytest.raises(ValidationError) as exc_info:
            UserCalibrationCreate(low_threshold=-1)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("low_threshold",) for e in errors)

    def test_create_threshold_above_100_invalid(self):
        """Test threshold above 100 raises validation error."""
        from backend.api.schemas.calibration import UserCalibrationCreate

        with pytest.raises(ValidationError) as exc_info:
            UserCalibrationCreate(high_threshold=101)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("high_threshold",) for e in errors)

    def test_create_decay_factor_valid_range(self):
        """Test decay_factor accepts values in valid range 0.0-1.0."""
        from backend.api.schemas.calibration import UserCalibrationCreate

        calibration = UserCalibrationCreate(decay_factor=0.5)
        assert calibration.decay_factor == 0.5

        calibration_zero = UserCalibrationCreate(decay_factor=0.0)
        assert calibration_zero.decay_factor == 0.0

        calibration_one = UserCalibrationCreate(decay_factor=1.0)
        assert calibration_one.decay_factor == 1.0

    def test_create_decay_factor_below_zero_invalid(self):
        """Test decay_factor below 0.0 raises validation error."""
        from backend.api.schemas.calibration import UserCalibrationCreate

        with pytest.raises(ValidationError) as exc_info:
            UserCalibrationCreate(decay_factor=-0.1)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("decay_factor",) for e in errors)

    def test_create_decay_factor_above_one_invalid(self):
        """Test decay_factor above 1.0 raises validation error."""
        from backend.api.schemas.calibration import UserCalibrationCreate

        with pytest.raises(ValidationError) as exc_info:
            UserCalibrationCreate(decay_factor=1.1)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("decay_factor",) for e in errors)

    def test_create_has_json_schema_example(self):
        """Test schema has OpenAPI example."""
        from backend.api.schemas.calibration import UserCalibrationCreate

        schema = UserCalibrationCreate.model_json_schema()

        # Should have example configuration
        assert UserCalibrationCreate.model_config.get("json_schema_extra") is not None


# =============================================================================
# UserCalibrationUpdate Tests
# =============================================================================


class TestUserCalibrationUpdate:
    """Tests for UserCalibrationUpdate schema."""

    def test_update_all_fields_optional(self):
        """Test all update fields are optional."""
        from backend.api.schemas.calibration import UserCalibrationUpdate

        update = UserCalibrationUpdate()

        assert update.low_threshold is None
        assert update.medium_threshold is None
        assert update.high_threshold is None
        assert update.decay_factor is None

    def test_update_single_threshold(self):
        """Test updating a single threshold."""
        from backend.api.schemas.calibration import UserCalibrationUpdate

        update = UserCalibrationUpdate(low_threshold=25)

        assert update.low_threshold == 25
        assert update.medium_threshold is None
        assert update.high_threshold is None

    def test_update_all_thresholds_valid_order(self):
        """Test updating all thresholds with valid ordering."""
        from backend.api.schemas.calibration import UserCalibrationUpdate

        update = UserCalibrationUpdate(
            low_threshold=20,
            medium_threshold=50,
            high_threshold=80,
        )

        assert update.low_threshold == 20
        assert update.medium_threshold == 50
        assert update.high_threshold == 80

    def test_update_thresholds_equal_invalid(self):
        """Test thresholds cannot be equal."""
        from backend.api.schemas.calibration import UserCalibrationUpdate

        with pytest.raises(ValidationError) as exc_info:
            UserCalibrationUpdate(
                low_threshold=50,
                medium_threshold=50,
                high_threshold=80,
            )

        errors = exc_info.value.errors()
        assert len(errors) >= 1

    def test_update_low_greater_than_medium_invalid(self):
        """Test low_threshold must be less than medium_threshold."""
        from backend.api.schemas.calibration import UserCalibrationUpdate

        with pytest.raises(ValidationError) as exc_info:
            UserCalibrationUpdate(
                low_threshold=60,
                medium_threshold=50,
                high_threshold=80,
            )

        errors = exc_info.value.errors()
        assert len(errors) >= 1

    def test_update_medium_greater_than_high_invalid(self):
        """Test medium_threshold must be less than high_threshold."""
        from backend.api.schemas.calibration import UserCalibrationUpdate

        with pytest.raises(ValidationError) as exc_info:
            UserCalibrationUpdate(
                low_threshold=20,
                medium_threshold=85,
                high_threshold=80,
            )

        errors = exc_info.value.errors()
        assert len(errors) >= 1

    def test_update_low_greater_than_high_invalid(self):
        """Test low_threshold must be less than high_threshold."""
        from backend.api.schemas.calibration import UserCalibrationUpdate

        with pytest.raises(ValidationError) as exc_info:
            UserCalibrationUpdate(
                low_threshold=90,
                medium_threshold=50,
                high_threshold=80,
            )

        errors = exc_info.value.errors()
        assert len(errors) >= 1

    def test_update_threshold_range_0_to_100(self):
        """Test thresholds must be in range 0-100."""
        from backend.api.schemas.calibration import UserCalibrationUpdate

        with pytest.raises(ValidationError) as exc_info:
            UserCalibrationUpdate(low_threshold=-5)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("low_threshold",) for e in errors)

        with pytest.raises(ValidationError) as exc_info:
            UserCalibrationUpdate(high_threshold=105)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("high_threshold",) for e in errors)

    def test_update_decay_factor_valid(self):
        """Test updating decay_factor with valid value."""
        from backend.api.schemas.calibration import UserCalibrationUpdate

        update = UserCalibrationUpdate(decay_factor=0.2)

        assert update.decay_factor == 0.2

    def test_update_decay_factor_range(self):
        """Test decay_factor must be in range 0.0-1.0."""
        from backend.api.schemas.calibration import UserCalibrationUpdate

        with pytest.raises(ValidationError) as exc_info:
            UserCalibrationUpdate(decay_factor=-0.1)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("decay_factor",) for e in errors)

        with pytest.raises(ValidationError) as exc_info:
            UserCalibrationUpdate(decay_factor=1.5)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("decay_factor",) for e in errors)

    def test_update_partial_thresholds_skips_ordering_validation(self):
        """Test partial threshold updates skip ordering validation.

        When only some thresholds are provided, ordering cannot be validated
        until combined with existing values.
        """
        from backend.api.schemas.calibration import UserCalibrationUpdate

        # Should not raise when only one threshold provided
        update = UserCalibrationUpdate(low_threshold=90)
        assert update.low_threshold == 90

        update = UserCalibrationUpdate(high_threshold=10)
        assert update.high_threshold == 10

    def test_update_has_json_schema_example(self):
        """Test schema has OpenAPI example."""
        from backend.api.schemas.calibration import UserCalibrationUpdate

        assert UserCalibrationUpdate.model_config.get("json_schema_extra") is not None


# =============================================================================
# UserCalibrationResponse Tests
# =============================================================================


class TestUserCalibrationResponse:
    """Tests for UserCalibrationResponse schema."""

    def test_response_contains_all_fields(self):
        """Test response schema has all expected fields."""
        from backend.api.schemas.calibration import UserCalibrationResponse

        now = datetime.now(UTC)
        response = UserCalibrationResponse(
            id=1,
            user_id="default",
            low_threshold=30,
            medium_threshold=60,
            high_threshold=85,
            decay_factor=0.1,
            false_positive_count=5,
            missed_detection_count=3,
            created_at=now,
            updated_at=now,
        )

        assert response.id == 1
        assert response.user_id == "default"
        assert response.low_threshold == 30
        assert response.medium_threshold == 60
        assert response.high_threshold == 85
        assert response.decay_factor == 0.1
        assert response.false_positive_count == 5
        assert response.missed_detection_count == 3
        assert response.created_at == now
        assert response.updated_at == now

    def test_response_from_attributes(self):
        """Test response can be created from ORM model attributes."""
        from backend.api.schemas.calibration import UserCalibrationResponse

        now = datetime.now(UTC)

        # Simulate ORM model
        mock_model = MagicMock()
        mock_model.id = 2
        mock_model.user_id = "test_user"
        mock_model.low_threshold = 25
        mock_model.medium_threshold = 55
        mock_model.high_threshold = 80
        mock_model.decay_factor = 0.15
        mock_model.false_positive_count = 10
        mock_model.missed_detection_count = 5
        mock_model.created_at = now
        mock_model.updated_at = now

        response = UserCalibrationResponse.model_validate(mock_model)

        assert response.id == 2
        assert response.user_id == "test_user"
        assert response.low_threshold == 25
        assert response.medium_threshold == 55
        assert response.high_threshold == 80
        assert response.decay_factor == 0.15
        assert response.false_positive_count == 10
        assert response.missed_detection_count == 5

    def test_response_serialization(self):
        """Test response serializes correctly to JSON-compatible dict."""
        from backend.api.schemas.calibration import UserCalibrationResponse

        response = UserCalibrationResponse(
            id=3,
            user_id="default",
            low_threshold=30,
            medium_threshold=60,
            high_threshold=85,
            decay_factor=0.1,
            false_positive_count=0,
            missed_detection_count=0,
            created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        )

        data = response.model_dump(mode="json")

        assert data["id"] == 3
        assert data["user_id"] == "default"
        assert data["low_threshold"] == 30
        assert data["medium_threshold"] == 60
        assert data["high_threshold"] == 85
        assert data["decay_factor"] == 0.1
        assert data["false_positive_count"] == 0
        assert data["missed_detection_count"] == 0
        assert "created_at" in data
        assert "updated_at" in data

    def test_response_has_json_schema_example(self):
        """Test response schema has OpenAPI example."""
        from backend.api.schemas.calibration import UserCalibrationResponse

        assert UserCalibrationResponse.model_config.get("json_schema_extra") is not None


# =============================================================================
# CalibrationAdjustRequest Tests
# =============================================================================


class TestCalibrationAdjustRequest:
    """Tests for CalibrationAdjustRequest schema."""

    def test_adjust_request_with_valid_data(self):
        """Test creating adjust request with valid data."""
        from backend.api.schemas.calibration import CalibrationAdjustRequest
        from backend.api.schemas.feedback import FeedbackType

        request = CalibrationAdjustRequest(
            feedback_type=FeedbackType.FALSE_POSITIVE,
            event_risk_score=75,
        )

        assert request.feedback_type == FeedbackType.FALSE_POSITIVE
        assert request.event_risk_score == 75

    def test_adjust_request_with_string_feedback_type(self):
        """Test creating adjust request with string feedback type."""
        from backend.api.schemas.calibration import CalibrationAdjustRequest
        from backend.api.schemas.feedback import FeedbackType

        request = CalibrationAdjustRequest(
            feedback_type="missed_detection",
            event_risk_score=45,
        )

        assert request.feedback_type == FeedbackType.MISSED_DETECTION
        assert request.event_risk_score == 45

    def test_adjust_request_all_feedback_types(self):
        """Test adjust request works with all valid feedback types."""
        from backend.api.schemas.calibration import CalibrationAdjustRequest
        from backend.api.schemas.feedback import FeedbackType

        for feedback_type in FeedbackType:
            request = CalibrationAdjustRequest(
                feedback_type=feedback_type,
                event_risk_score=50,
            )
            assert request.feedback_type == feedback_type

    def test_adjust_request_missing_feedback_type_invalid(self):
        """Test missing feedback_type raises validation error."""
        from backend.api.schemas.calibration import CalibrationAdjustRequest

        with pytest.raises(ValidationError) as exc_info:
            CalibrationAdjustRequest(event_risk_score=50)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("feedback_type",) for e in errors)

    def test_adjust_request_missing_event_risk_score_invalid(self):
        """Test missing event_risk_score raises validation error."""
        from backend.api.schemas.calibration import CalibrationAdjustRequest
        from backend.api.schemas.feedback import FeedbackType

        with pytest.raises(ValidationError) as exc_info:
            CalibrationAdjustRequest(feedback_type=FeedbackType.FALSE_POSITIVE)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("event_risk_score",) for e in errors)

    def test_adjust_request_invalid_feedback_type(self):
        """Test invalid feedback_type raises validation error."""
        from backend.api.schemas.calibration import CalibrationAdjustRequest

        with pytest.raises(ValidationError) as exc_info:
            CalibrationAdjustRequest(
                feedback_type="invalid_type",
                event_risk_score=50,
            )

        errors = exc_info.value.errors()
        assert len(errors) >= 1

    def test_adjust_request_event_risk_score_range(self):
        """Test event_risk_score must be in range 0-100."""
        from backend.api.schemas.calibration import CalibrationAdjustRequest
        from backend.api.schemas.feedback import FeedbackType

        # Valid boundary values
        request_zero = CalibrationAdjustRequest(
            feedback_type=FeedbackType.CORRECT,
            event_risk_score=0,
        )
        assert request_zero.event_risk_score == 0

        request_hundred = CalibrationAdjustRequest(
            feedback_type=FeedbackType.CORRECT,
            event_risk_score=100,
        )
        assert request_hundred.event_risk_score == 100

    def test_adjust_request_event_risk_score_below_zero_invalid(self):
        """Test event_risk_score below 0 raises validation error."""
        from backend.api.schemas.calibration import CalibrationAdjustRequest
        from backend.api.schemas.feedback import FeedbackType

        with pytest.raises(ValidationError) as exc_info:
            CalibrationAdjustRequest(
                feedback_type=FeedbackType.FALSE_POSITIVE,
                event_risk_score=-1,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("event_risk_score",) for e in errors)

    def test_adjust_request_event_risk_score_above_100_invalid(self):
        """Test event_risk_score above 100 raises validation error."""
        from backend.api.schemas.calibration import CalibrationAdjustRequest
        from backend.api.schemas.feedback import FeedbackType

        with pytest.raises(ValidationError) as exc_info:
            CalibrationAdjustRequest(
                feedback_type=FeedbackType.FALSE_POSITIVE,
                event_risk_score=101,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("event_risk_score",) for e in errors)

    def test_adjust_request_has_json_schema_example(self):
        """Test schema has OpenAPI example."""
        from backend.api.schemas.calibration import CalibrationAdjustRequest

        assert CalibrationAdjustRequest.model_config.get("json_schema_extra") is not None

    def test_adjust_request_serialization(self):
        """Test adjust request serializes correctly."""
        from backend.api.schemas.calibration import CalibrationAdjustRequest
        from backend.api.schemas.feedback import FeedbackType

        request = CalibrationAdjustRequest(
            feedback_type=FeedbackType.WRONG_SEVERITY,
            event_risk_score=65,
        )

        data = request.model_dump(mode="json")

        assert data["feedback_type"] == "wrong_severity"
        assert data["event_risk_score"] == 65
