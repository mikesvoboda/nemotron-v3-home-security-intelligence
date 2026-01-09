"""Integration tests for detection bulk API endpoints (NEM-1433).

Tests the bulk create, update, and delete endpoints for detections
including partial success handling with HTTP 207 Multi-Status responses.
"""

import uuid
from datetime import UTC, datetime

import pytest

from backend.api.schemas.bulk import BulkOperationStatus


@pytest.fixture
async def async_client(client):
    """Alias for shared client fixture for backward compatibility."""
    yield client


@pytest.fixture
async def clean_detections(integration_db):
    """Delete detections and cameras before test for isolation."""
    from sqlalchemy import text

    from backend.core.database import get_engine

    async with get_engine().begin() as conn:
        await conn.execute(text("DELETE FROM detections"))  # nosemgrep: avoid-sqlalchemy-text
        await conn.execute(text("DELETE FROM events"))  # nosemgrep: avoid-sqlalchemy-text
        await conn.execute(text("DELETE FROM cameras"))  # nosemgrep: avoid-sqlalchemy-text

    yield


@pytest.fixture
async def sample_camera(integration_db, clean_detections):
    """Create a sample camera for bulk operations."""
    from backend.core.database import get_session
    from backend.models.camera import Camera

    camera_id = f"bulk_det_test_{uuid.uuid4().hex[:8]}"
    async with get_session() as db:
        camera = Camera(
            id=camera_id,
            name="Bulk Detection Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
        )
        db.add(camera)
        await db.commit()
        await db.refresh(camera)
        yield camera


@pytest.fixture
async def sample_detections(integration_db, sample_camera):
    """Create sample detections for update and delete tests."""
    from backend.core.database import get_session
    from backend.models.detection import Detection

    detections = []
    async with get_session() as db:
        for i in range(5):
            detection = Detection(
                camera_id=sample_camera.id,
                file_path=f"/path/to/image_{i}.jpg",
                file_type="image/jpeg",
                detected_at=datetime.now(UTC),
                object_type="person",
                confidence=0.9 - (i * 0.05),
                bbox_x=100 + i * 10,
                bbox_y=200 + i * 10,
                bbox_width=150,
                bbox_height=300,
            )
            db.add(detection)
            detections.append(detection)
        await db.commit()
        for detection in detections:
            await db.refresh(detection)
        yield detections


class TestBulkCreateDetections:
    """Tests for POST /api/detections/bulk endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_create_detections_success(self, async_client, sample_camera):
        """Test successful bulk creation of detections."""
        detections_data = {
            "detections": [
                {
                    "camera_id": sample_camera.id,
                    "object_type": "person",
                    "confidence": 0.95,
                    "detected_at": datetime.now(UTC).isoformat(),
                    "file_path": "/path/to/image1.jpg",
                    "bbox_x": 100,
                    "bbox_y": 200,
                    "bbox_width": 150,
                    "bbox_height": 300,
                },
                {
                    "camera_id": sample_camera.id,
                    "object_type": "vehicle",
                    "confidence": 0.88,
                    "detected_at": datetime.now(UTC).isoformat(),
                    "file_path": "/path/to/image2.jpg",
                    "bbox_x": 50,
                    "bbox_y": 100,
                    "bbox_width": 200,
                    "bbox_height": 150,
                },
            ]
        }

        response = await async_client.post("/api/detections/bulk", json=detections_data)

        assert response.status_code == 207  # Multi-Status
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0
        assert len(data["results"]) == 2

        for result in data["results"]:
            assert result["status"] == BulkOperationStatus.SUCCESS
            assert result["id"] is not None
            assert result["error"] is None

    @pytest.mark.asyncio
    async def test_bulk_create_detections_partial_failure(self, async_client, sample_camera):
        """Test bulk create with partial failure (invalid camera_id)."""
        detections_data = {
            "detections": [
                {
                    "camera_id": sample_camera.id,
                    "object_type": "person",
                    "confidence": 0.95,
                    "detected_at": datetime.now(UTC).isoformat(),
                    "file_path": "/path/to/valid.jpg",
                    "bbox_x": 100,
                    "bbox_y": 200,
                    "bbox_width": 150,
                    "bbox_height": 300,
                },
                {
                    "camera_id": "nonexistent_camera",
                    "object_type": "vehicle",
                    "confidence": 0.88,
                    "detected_at": datetime.now(UTC).isoformat(),
                    "file_path": "/path/to/invalid.jpg",
                    "bbox_x": 50,
                    "bbox_y": 100,
                    "bbox_width": 200,
                    "bbox_height": 150,
                },
            ]
        }

        response = await async_client.post("/api/detections/bulk", json=detections_data)

        assert response.status_code == 207
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 1
        assert data["failed"] == 1

        # First detection should succeed
        assert data["results"][0]["status"] == BulkOperationStatus.SUCCESS
        assert data["results"][0]["id"] is not None

        # Second detection should fail
        assert data["results"][1]["status"] == BulkOperationStatus.FAILED
        assert "not found" in data["results"][1]["error"].lower()

    @pytest.mark.asyncio
    async def test_bulk_create_detections_with_enrichment_data(self, async_client, sample_camera):
        """Test bulk create with enrichment data."""
        detections_data = {
            "detections": [
                {
                    "camera_id": sample_camera.id,
                    "object_type": "person",
                    "confidence": 0.95,
                    "detected_at": datetime.now(UTC).isoformat(),
                    "file_path": "/path/to/enriched.jpg",
                    "bbox_x": 100,
                    "bbox_y": 200,
                    "bbox_width": 150,
                    "bbox_height": 300,
                    "enrichment_data": {
                        "faces": [{"confidence": 0.98}],
                        "clothing_classifications": {},
                    },
                },
            ]
        }

        response = await async_client.post("/api/detections/bulk", json=detections_data)

        assert response.status_code == 207
        data = response.json()
        assert data["succeeded"] == 1

    @pytest.mark.asyncio
    async def test_bulk_create_detections_validation_error(self, async_client):
        """Test validation error for invalid request format."""
        # Empty detections list should fail validation
        response = await async_client.post("/api/detections/bulk", json={"detections": []})
        assert response.status_code == 422


class TestBulkUpdateDetections:
    """Tests for PATCH /api/detections/bulk endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_update_detections_success(self, async_client, sample_detections):
        """Test successful bulk update of detections."""
        update_data = {
            "detections": [
                {"id": sample_detections[0].id, "object_type": "truck"},
                {"id": sample_detections[1].id, "confidence": 0.99},
            ]
        }

        response = await async_client.patch("/api/detections/bulk", json=update_data)

        assert response.status_code == 207
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0

        for result in data["results"]:
            assert result["status"] == BulkOperationStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_bulk_update_detections_not_found(self, async_client, sample_detections):
        """Test bulk update with some detections not found."""
        update_data = {
            "detections": [
                {"id": sample_detections[0].id, "object_type": "motorcycle"},
                {"id": 999999, "confidence": 0.75},  # Non-existent detection
            ]
        }

        response = await async_client.patch("/api/detections/bulk", json=update_data)

        assert response.status_code == 207
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 1
        assert data["failed"] == 1

        # First detection should succeed
        assert data["results"][0]["status"] == BulkOperationStatus.SUCCESS

        # Second detection should fail
        assert data["results"][1]["status"] == BulkOperationStatus.FAILED
        assert "not found" in data["results"][1]["error"].lower()

    @pytest.mark.asyncio
    async def test_bulk_update_detections_enrichment_data(self, async_client, sample_detections):
        """Test bulk update with enrichment data."""
        update_data = {
            "detections": [
                {
                    "id": sample_detections[0].id,
                    "enrichment_data": {"license_plates": [{"text": "ABC123", "confidence": 0.95}]},
                },
            ]
        }

        response = await async_client.patch("/api/detections/bulk", json=update_data)

        assert response.status_code == 207
        data = response.json()
        assert data["succeeded"] == 1


class TestBulkDeleteDetections:
    """Tests for DELETE /api/detections/bulk endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_delete_detections_success(self, async_client, sample_detections):
        """Test successful bulk delete of detections."""
        delete_data = {
            "detection_ids": [sample_detections[0].id, sample_detections[1].id],
        }

        response = await async_client.request("DELETE", "/api/detections/bulk", json=delete_data)

        assert response.status_code == 207
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0

        # Verify detections are actually deleted
        check_response = await async_client.get(f"/api/detections/{sample_detections[0].id}")
        assert check_response.status_code == 404

    @pytest.mark.asyncio
    async def test_bulk_delete_detections_not_found(self, async_client, sample_detections):
        """Test bulk delete with some detections not found."""
        delete_data = {
            "detection_ids": [sample_detections[2].id, 999999],
        }

        response = await async_client.request("DELETE", "/api/detections/bulk", json=delete_data)

        assert response.status_code == 207
        data = response.json()
        assert data["succeeded"] == 1
        assert data["failed"] == 1

        # Check results
        success_result = next(r for r in data["results"] if r["id"] == sample_detections[2].id)
        assert success_result["status"] == BulkOperationStatus.SUCCESS

        failed_result = next(r for r in data["results"] if r["id"] == 999999)
        assert failed_result["status"] == BulkOperationStatus.FAILED

    @pytest.mark.asyncio
    async def test_bulk_delete_all_not_found(self, async_client):
        """Test bulk delete when all detections not found."""
        delete_data = {
            "detection_ids": [999997, 999998, 999999],
        }

        response = await async_client.request("DELETE", "/api/detections/bulk", json=delete_data)

        assert response.status_code == 207
        data = response.json()
        assert data["total"] == 3
        assert data["succeeded"] == 0
        assert data["failed"] == 3

        for result in data["results"]:
            assert result["status"] == BulkOperationStatus.FAILED
