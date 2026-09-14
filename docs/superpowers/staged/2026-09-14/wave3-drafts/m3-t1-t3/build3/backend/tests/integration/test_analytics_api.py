"""Integration tests for analytics API endpoints."""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.tests.factories import CameraFactory, DetectionFactory, EventFactory


class TestDetectionTrendsEndpoint:
    """Tests for GET /api/analytics/detection-trends endpoint."""

    @pytest.mark.asyncio
    async def test_detection_trends_returns_data(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test that detection trends endpoint returns aggregated data."""
        # Create test data
        camera = CameraFactory.build()
        session.add(camera)
        for i in range(5):
            detection = DetectionFactory.build(camera_id=camera.id)
            session.add(detection)
        await session.commit()

        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        response = await client.get(
            "/api/analytics/detection-trends",
            params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "data_points" in data
        assert "total_detections" in data
        assert "start_date" in data
        assert "end_date" in data
        assert isinstance(data["data_points"], list)
        assert isinstance(data["total_detections"], int)
        assert data["total_detections"] >= 0

    @pytest.mark.asyncio
    async def test_detection_trends_validates_date_range(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test that endpoint validates date range (start before end)."""
        start_date = date.today()
        end_date = date.today() - timedelta(days=7)

        response = await client.get(
            "/api/analytics/detection-trends",
            params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )

        assert response.status_code == 400
        response_data = response.json()
        # Check error is present (could be in 'detail' or 'error' field depending on middleware)
        error_text = str(response_data).lower()
        assert "start" in error_text or "date" in error_text

    @pytest.mark.asyncio
    async def test_detection_trends_requires_dates(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test that endpoint requires both start_date and end_date."""
        response = await client.get("/api/analytics/detection-trends")

        assert response.status_code == 422  # Validation error


class TestRiskHistoryEndpoint:
    """Tests for GET /api/analytics/risk-history endpoint."""

    @pytest.mark.asyncio
    async def test_risk_history_returns_data(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test that risk history endpoint returns aggregated data."""
        # Create test data
        camera = CameraFactory.build()
        session.add(camera)
        event = EventFactory.build(camera_id=camera.id, risk_level="high")
        session.add(event)
        await session.commit()

        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        response = await client.get(
            "/api/analytics/risk-history",
            params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "data_points" in data
        assert "start_date" in data
        assert "end_date" in data
        assert isinstance(data["data_points"], list)

        # Validate data point structure if present
        if len(data["data_points"]) > 0:
            point = data["data_points"][0]
            assert "date" in point
            assert "low" in point
            assert "medium" in point
            assert "high" in point
            assert "critical" in point
            assert all(
                isinstance(point[level], int) for level in ["low", "medium", "high", "critical"]
            )

    @pytest.mark.asyncio
    async def test_risk_history_validates_date_range(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test that endpoint validates date range (start before end)."""
        start_date = date.today()
        end_date = date.today() - timedelta(days=7)

        response = await client.get(
            "/api/analytics/risk-history",
            params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_risk_history_requires_dates(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test that endpoint requires both start_date and end_date."""
        response = await client.get("/api/analytics/risk-history")

        assert response.status_code == 422  # Validation error


class TestCameraUptimeEndpoint:
    """Tests for GET /api/analytics/camera-uptime endpoint."""

    @pytest.mark.asyncio
    async def test_camera_uptime_returns_data(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test that camera uptime endpoint returns per-camera data."""
        # Create test data
        camera = CameraFactory.build()
        session.add(camera)
        await session.commit()

        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        response = await client.get(
            "/api/analytics/camera-uptime",
            params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "cameras" in data
        assert "start_date" in data
        assert "end_date" in data
        assert isinstance(data["cameras"], list)

        # Validate camera data structure if present
        if len(data["cameras"]) > 0:
            camera_data = data["cameras"][0]
            assert "camera_id" in camera_data
            assert "camera_name" in camera_data
            assert "uptime_percentage" in camera_data
            assert "detection_count" in camera_data
            assert 0.0 <= camera_data["uptime_percentage"] <= 100.0
            assert camera_data["detection_count"] >= 0

    @pytest.mark.asyncio
    async def test_camera_uptime_validates_date_range(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test that endpoint validates date range (start before end)."""
        start_date = date.today()
        end_date = date.today() - timedelta(days=7)

        response = await client.get(
            "/api/analytics/camera-uptime",
            params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_camera_uptime_requires_dates(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test that endpoint requires both start_date and end_date."""
        response = await client.get("/api/analytics/camera-uptime")

        assert response.status_code == 422  # Validation error


class TestObjectDistributionEndpoint:
    """Tests for GET /api/analytics/object-distribution endpoint."""

    @pytest.mark.asyncio
    async def test_object_distribution_returns_data(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test that object distribution endpoint returns aggregated data."""
        # Create test data
        camera = CameraFactory.build()
        session.add(camera)
        detection1 = DetectionFactory.build(camera_id=camera.id, object_type="person")
        detection2 = DetectionFactory.build(camera_id=camera.id, object_type="car")
        session.add(detection1)
        session.add(detection2)
        await session.commit()

        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        response = await client.get(
            "/api/analytics/object-distribution",
            params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "object_types" in data
        assert "total_detections" in data
        assert "start_date" in data
        assert "end_date" in data
        assert isinstance(data["object_types"], list)
        assert isinstance(data["total_detections"], int)
        assert data["total_detections"] >= 0

        # Validate object type structure if present
        if len(data["object_types"]) > 0:
            obj_type = data["object_types"][0]
            assert "object_type" in obj_type
            assert "count" in obj_type
            assert "percentage" in obj_type
            assert obj_type["count"] >= 0
            assert 0.0 <= obj_type["percentage"] <= 100.0

    @pytest.mark.asyncio
    async def test_object_distribution_validates_date_range(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test that endpoint validates date range (start before end)."""
        start_date = date.today()
        end_date = date.today() - timedelta(days=7)

        response = await client.get(
            "/api/analytics/object-distribution",
            params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_object_distribution_requires_dates(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test that endpoint requires both start_date and end_date."""
        response = await client.get("/api/analytics/object-distribution")

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_object_distribution_percentages_sum_to_100(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test that object distribution percentages sum to approximately 100%."""
        # Create test data with multiple object types
        camera = CameraFactory.build()
        session.add(camera)
        detection1 = DetectionFactory.build(camera_id=camera.id, object_type="person")
        detection2 = DetectionFactory.build(camera_id=camera.id, object_type="car")
        session.add(detection1)
        session.add(detection2)
        await session.commit()

        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        response = await client.get(
            "/api/analytics/object-distribution",
            params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )

        assert response.status_code == 200
        data = response.json()

        # If there are object types, percentages should sum to ~100%
        if len(data["object_types"]) > 0:
            total_percentage = sum(obj["percentage"] for obj in data["object_types"])
            # Allow for rounding errors (within 0.1%)
            assert 99.9 <= total_percentage <= 100.1


class TestAnalyticsEndpointsEmptyData:
    """Tests for analytics endpoints with empty database."""

    @pytest.mark.asyncio
    async def test_detection_trends_empty_database(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test detection trends with no detections in database."""
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        response = await client.get(
            "/api/analytics/detection-trends",
            params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_detections"] == 0
        # Data points should still be present (one per day with count=0)
        expected_days = (end_date - start_date).days + 1
        assert len(data["data_points"]) == expected_days

    @pytest.mark.asyncio
    async def test_risk_history_empty_database(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test risk history with no events in database."""
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        response = await client.get(
            "/api/analytics/risk-history",
            params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )

        assert response.status_code == 200
        data = response.json()
        # Data points should still be present (one per day with all counts=0)
        expected_days = (end_date - start_date).days + 1
        assert len(data["data_points"]) == expected_days

    @pytest.mark.asyncio
    async def test_camera_uptime_empty_database(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test camera uptime with no cameras in database."""
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        response = await client.get(
            "/api/analytics/camera-uptime",
            params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["cameras"]) == 0

    @pytest.mark.asyncio
    async def test_object_distribution_empty_database(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Test object distribution with no detections in database."""
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        response = await client.get(
            "/api/analytics/object-distribution",
            params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_detections"] == 0
        assert len(data["object_types"]) == 0
