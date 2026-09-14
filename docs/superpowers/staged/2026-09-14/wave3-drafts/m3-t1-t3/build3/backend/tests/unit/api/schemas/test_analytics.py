"""Unit tests for analytics schemas."""

from datetime import date

import pytest
from pydantic import ValidationError

from backend.api.schemas.analytics import (
    CameraUptimeDataPoint,
    CameraUptimeResponse,
    DetectionTrendDataPoint,
    DetectionTrendsResponse,
    ObjectDistributionDataPoint,
    ObjectDistributionResponse,
    RiskHistoryDataPoint,
    RiskHistoryResponse,
)


class TestDetectionTrendDataPoint:
    """Tests for DetectionTrendDataPoint schema."""

    def test_valid_data_point(self) -> None:
        """Test creating a valid detection trend data point."""
        data_point = DetectionTrendDataPoint(date=date(2025, 1, 7), count=25)

        assert data_point.date == date(2025, 1, 7)
        assert data_point.count == 25

    def test_zero_count_valid(self) -> None:
        """Test that zero count is valid."""
        data_point = DetectionTrendDataPoint(date=date(2025, 1, 7), count=0)

        assert data_point.count == 0

    def test_negative_count_invalid(self) -> None:
        """Test that negative count is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DetectionTrendDataPoint(date=date(2025, 1, 7), count=-1)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("count",)


class TestDetectionTrendsResponse:
    """Tests for DetectionTrendsResponse schema."""

    def test_valid_trends_response(self) -> None:
        """Test creating a valid detection trends response."""
        response = DetectionTrendsResponse(
            data_points=[
                DetectionTrendDataPoint(date=date(2025, 1, 1), count=20),
                DetectionTrendDataPoint(date=date(2025, 1, 2), count=25),
            ],
            total_detections=45,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 2),
        )

        assert len(response.data_points) == 2
        assert response.total_detections == 45
        assert response.start_date == date(2025, 1, 1)
        assert response.end_date == date(2025, 1, 2)

    def test_empty_data_points_valid(self) -> None:
        """Test that empty data points list is valid."""
        response = DetectionTrendsResponse(
            data_points=[],
            total_detections=0,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 7),
        )

        assert len(response.data_points) == 0
        assert response.total_detections == 0


class TestRiskHistoryDataPoint:
    """Tests for RiskHistoryDataPoint schema."""

    def test_valid_risk_data_point(self) -> None:
        """Test creating a valid risk history data point."""
        data_point = RiskHistoryDataPoint(
            date=date(2025, 1, 7), low=10, medium=5, high=2, critical=1
        )

        assert data_point.date == date(2025, 1, 7)
        assert data_point.low == 10
        assert data_point.medium == 5
        assert data_point.high == 2
        assert data_point.critical == 1

    def test_default_values_zero(self) -> None:
        """Test that risk level counts default to zero."""
        data_point = RiskHistoryDataPoint(date=date(2025, 1, 7))

        assert data_point.low == 0
        assert data_point.medium == 0
        assert data_point.high == 0
        assert data_point.critical == 0

    def test_negative_counts_invalid(self) -> None:
        """Test that negative risk counts are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RiskHistoryDataPoint(date=date(2025, 1, 7), low=-1)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("low",)


class TestRiskHistoryResponse:
    """Tests for RiskHistoryResponse schema."""

    def test_valid_risk_history_response(self) -> None:
        """Test creating a valid risk history response."""
        response = RiskHistoryResponse(
            data_points=[
                RiskHistoryDataPoint(date=date(2025, 1, 1), low=10, medium=5, high=2, critical=1),
                RiskHistoryDataPoint(date=date(2025, 1, 2), low=12, medium=4, high=3, critical=0),
            ],
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 2),
        )

        assert len(response.data_points) == 2
        assert response.start_date == date(2025, 1, 1)
        assert response.end_date == date(2025, 1, 2)


class TestCameraUptimeDataPoint:
    """Tests for CameraUptimeDataPoint schema."""

    def test_valid_camera_uptime(self) -> None:
        """Test creating a valid camera uptime data point."""
        data_point = CameraUptimeDataPoint(
            camera_id="front_door",
            camera_name="Front Door",
            uptime_percentage=98.5,
            detection_count=150,
        )

        assert data_point.camera_id == "front_door"
        assert data_point.camera_name == "Front Door"
        assert data_point.uptime_percentage == 98.5
        assert data_point.detection_count == 150

    def test_uptime_100_percent_valid(self) -> None:
        """Test that 100% uptime is valid."""
        data_point = CameraUptimeDataPoint(
            camera_id="front_door",
            camera_name="Front Door",
            uptime_percentage=100.0,
            detection_count=200,
        )

        assert data_point.uptime_percentage == 100.0

    def test_uptime_0_percent_valid(self) -> None:
        """Test that 0% uptime is valid."""
        data_point = CameraUptimeDataPoint(
            camera_id="front_door",
            camera_name="Front Door",
            uptime_percentage=0.0,
            detection_count=0,
        )

        assert data_point.uptime_percentage == 0.0

    def test_uptime_over_100_invalid(self) -> None:
        """Test that uptime over 100% is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraUptimeDataPoint(
                camera_id="front_door",
                camera_name="Front Door",
                uptime_percentage=101.0,
                detection_count=150,
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("uptime_percentage",)

    def test_negative_uptime_invalid(self) -> None:
        """Test that negative uptime is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraUptimeDataPoint(
                camera_id="front_door",
                camera_name="Front Door",
                uptime_percentage=-1.0,
                detection_count=150,
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("uptime_percentage",)


class TestCameraUptimeResponse:
    """Tests for CameraUptimeResponse schema."""

    def test_valid_camera_uptime_response(self) -> None:
        """Test creating a valid camera uptime response."""
        response = CameraUptimeResponse(
            cameras=[
                CameraUptimeDataPoint(
                    camera_id="front_door",
                    camera_name="Front Door",
                    uptime_percentage=98.5,
                    detection_count=150,
                ),
                CameraUptimeDataPoint(
                    camera_id="back_door",
                    camera_name="Back Door",
                    uptime_percentage=95.2,
                    detection_count=120,
                ),
            ],
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 7),
        )

        assert len(response.cameras) == 2
        assert response.start_date == date(2025, 1, 1)
        assert response.end_date == date(2025, 1, 7)


class TestObjectDistributionDataPoint:
    """Tests for ObjectDistributionDataPoint schema."""

    def test_valid_object_distribution(self) -> None:
        """Test creating a valid object distribution data point."""
        data_point = ObjectDistributionDataPoint(object_type="person", count=120, percentage=45.5)

        assert data_point.object_type == "person"
        assert data_point.count == 120
        assert data_point.percentage == 45.5

    def test_percentage_100_valid(self) -> None:
        """Test that 100% percentage is valid."""
        data_point = ObjectDistributionDataPoint(object_type="person", count=100, percentage=100.0)

        assert data_point.percentage == 100.0

    def test_percentage_0_valid(self) -> None:
        """Test that 0% percentage is valid."""
        data_point = ObjectDistributionDataPoint(object_type="person", count=0, percentage=0.0)

        assert data_point.percentage == 0.0

    def test_percentage_over_100_invalid(self) -> None:
        """Test that percentage over 100% is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ObjectDistributionDataPoint(object_type="person", count=120, percentage=101.0)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("percentage",)

    def test_negative_percentage_invalid(self) -> None:
        """Test that negative percentage is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ObjectDistributionDataPoint(object_type="person", count=120, percentage=-1.0)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("percentage",)


class TestObjectDistributionResponse:
    """Tests for ObjectDistributionResponse schema."""

    def test_valid_object_distribution_response(self) -> None:
        """Test creating a valid object distribution response."""
        response = ObjectDistributionResponse(
            object_types=[
                ObjectDistributionDataPoint(object_type="person", count=120, percentage=45.5),
                ObjectDistributionDataPoint(object_type="car", count=80, percentage=30.3),
                ObjectDistributionDataPoint(object_type="dog", count=64, percentage=24.2),
            ],
            total_detections=264,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 7),
        )

        assert len(response.object_types) == 3
        assert response.total_detections == 264
        assert response.start_date == date(2025, 1, 1)
        assert response.end_date == date(2025, 1, 7)

    def test_empty_object_types_valid(self) -> None:
        """Test that empty object types list is valid."""
        response = ObjectDistributionResponse(
            object_types=[],
            total_detections=0,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 7),
        )

        assert len(response.object_types) == 0
        assert response.total_detections == 0
