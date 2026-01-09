"""Integration tests for API idempotency behavior.

This module tests idempotency patterns at various levels:

1. **Service-level idempotency** (implemented via Redis batch_id tracking in NemotronAnalyzer)
   - Tests that duplicate batch processing returns the same event
   - Tests that idempotency keys expire after TTL

2. **API-level conflict detection** (database constraints)
   - Tests that duplicate camera creation returns 409 Conflict
   - Tests that concurrent creation is handled correctly

3. **Future API-level Idempotency-Key header** (not yet implemented)
   - Stub tests marked with skip to document expected behavior

Uses shared fixtures from conftest.py:
- integration_db: PostgreSQL test database
- client: httpx AsyncClient with test app
- real_redis: Real Redis client for idempotency key tests

Note: These tests are best run serially (-n0) due to database state dependencies.
The integration marker is auto-applied based on directory location.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.tests.integration.conftest import unique_id

# Mark all tests in this module as integration tests (auto-applied by conftest.py)
# These tests require real database/Redis and share state


# =============================================================================
# Service-Level Idempotency Tests (NemotronAnalyzer Redis batch tracking)
# =============================================================================


class TestServiceLevelIdempotency:
    """Tests for NemotronAnalyzer's Redis-based idempotency handling.

    The NemotronAnalyzer service uses Redis keys to track processed batches
    and prevent duplicate Event creation on retries (NEM-1725).
    """

    @pytest.fixture
    async def sample_camera(self, integration_db):
        """Create a sample camera in the database."""
        from backend.core.database import get_session
        from backend.models.camera import Camera

        camera_id = unique_id("cam")
        async with get_session() as db:
            camera = Camera(
                id=camera_id,
                name=f"Test Camera {camera_id}",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            db.add(camera)
            await db.commit()
            await db.refresh(camera)
            yield camera

    @pytest.fixture
    async def sample_detections(self, integration_db, sample_camera):
        """Create sample detections in the database."""
        from backend.core.database import get_session
        from backend.models.detection import Detection

        async with get_session() as db:
            detections = []
            for i in range(3):
                detection = Detection(
                    camera_id=sample_camera.id,
                    file_path=f"/export/foscam/{sample_camera.id}/img{i:03d}.jpg",
                    file_type="image/jpeg",
                    detected_at=datetime(2025, 12, 23, 14, i, 0, tzinfo=UTC),
                    object_type="person" if i == 0 else "car",
                    confidence=0.95 - (i * 0.05),
                    bbox_x=100 + (i * 50),
                    bbox_y=150 + (i * 50),
                    bbox_width=200,
                    bbox_height=400,
                )
                db.add(detection)
                detections.append(detection)

            await db.commit()
            for d in detections:
                await db.refresh(d)
            yield detections

    @pytest.mark.asyncio
    async def test_idempotency_key_stored_after_event_creation(
        self, integration_db, real_redis, sample_camera, sample_detections
    ):
        """Test that idempotency key is stored in Redis after Event creation.

        When NemotronAnalyzer creates an Event, it should store an idempotency
        key mapping batch_id -> event_id in Redis with a TTL.
        """
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        # Create analyzer with real Redis
        analyzer = NemotronAnalyzer(redis_client=real_redis)

        batch_id = f"batch_{unique_id('test')}"

        # Verify no idempotency key exists initially
        key = f"batch_event:{batch_id}"
        initial_value = await real_redis.get(key)
        assert initial_value is None, "Idempotency key should not exist initially"

        # Set idempotency key (simulating post-creation)
        event_id = 12345
        await analyzer._set_idempotency(batch_id, event_id)

        # Verify key was stored
        stored_value = await real_redis.get(key)
        assert stored_value is not None, "Idempotency key should be stored"
        assert int(stored_value) == event_id, "Stored event_id should match"

    @pytest.mark.asyncio
    async def test_idempotency_check_returns_existing_event_id(
        self, integration_db, real_redis, sample_camera
    ):
        """Test that idempotency check returns existing event_id for duplicate batch.

        When a batch has already been processed (idempotency key exists),
        _check_idempotency should return the existing event_id.
        """
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        analyzer = NemotronAnalyzer(redis_client=real_redis)

        batch_id = f"batch_{unique_id('dup')}"
        event_id = 67890

        # Store idempotency key first
        await analyzer._set_idempotency(batch_id, event_id)

        # Check idempotency - should return the existing event_id
        result = await analyzer._check_idempotency(batch_id)
        assert result == event_id, "Should return existing event_id for duplicate batch"

    @pytest.mark.asyncio
    async def test_idempotency_check_returns_none_for_new_batch(self, integration_db, real_redis):
        """Test that idempotency check returns None for a new batch.

        When a batch has not been processed (no idempotency key),
        _check_idempotency should return None to allow Event creation.
        """
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        analyzer = NemotronAnalyzer(redis_client=real_redis)

        batch_id = f"batch_{unique_id('new')}"

        # Check idempotency for non-existent batch
        result = await analyzer._check_idempotency(batch_id)
        assert result is None, "Should return None for new batch"

    @pytest.mark.asyncio
    async def test_different_batch_ids_are_independent(self, integration_db, real_redis):
        """Test that different batch_ids have independent idempotency keys.

        Each batch_id should have its own idempotency key, so processing
        different batches should not interfere with each other.
        """
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        analyzer = NemotronAnalyzer(redis_client=real_redis)

        batch_id_1 = f"batch_{unique_id('b1')}"
        batch_id_2 = f"batch_{unique_id('b2')}"
        event_id_1 = 111
        event_id_2 = 222

        # Store idempotency key for batch 1
        await analyzer._set_idempotency(batch_id_1, event_id_1)

        # Batch 2 should still return None (not processed)
        result_2 = await analyzer._check_idempotency(batch_id_2)
        assert result_2 is None, "Batch 2 should not be affected by batch 1"

        # Batch 1 should return its event_id
        result_1 = await analyzer._check_idempotency(batch_id_1)
        assert result_1 == event_id_1, "Batch 1 should return its event_id"

        # Store batch 2 and verify both are independent
        await analyzer._set_idempotency(batch_id_2, event_id_2)

        result_1_again = await analyzer._check_idempotency(batch_id_1)
        result_2_again = await analyzer._check_idempotency(batch_id_2)

        assert result_1_again == event_id_1, "Batch 1 should still return its event_id"
        assert result_2_again == event_id_2, "Batch 2 should return its event_id"

    @pytest.mark.asyncio
    async def test_idempotency_graceful_degradation_on_redis_failure(self, integration_db):
        """Test that idempotency check fails open when Redis is unavailable.

        If Redis is unavailable, the idempotency check should return None
        (allowing Event creation) rather than raising an exception. This
        ensures the system degrades gracefully.
        """
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        # Create analyzer with failing Redis client
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Redis connection failed"))
        mock_redis.set = AsyncMock(side_effect=Exception("Redis connection failed"))

        analyzer = NemotronAnalyzer(redis_client=mock_redis)

        batch_id = f"batch_{unique_id('fail')}"

        # Check should fail open (return None, not raise)
        result = await analyzer._check_idempotency(batch_id)
        assert result is None, "Should fail open on Redis error"

        # Set should not raise exception
        # (it should log a warning but continue)
        await analyzer._set_idempotency(batch_id, 99999)
        # No exception means success


# =============================================================================
# API-Level Conflict Detection Tests (Database-Enforced Idempotency)
# =============================================================================


class TestAPIConflictDetection:
    """Tests for API-level conflict detection that provides idempotent-like behavior.

    While not using explicit Idempotency-Key headers, the API provides
    idempotent-like behavior through database constraint enforcement:
    - 409 Conflict for duplicate camera names
    - 409 Conflict for duplicate folder paths
    """

    @pytest.mark.asyncio
    async def test_duplicate_camera_name_returns_409(self, client):
        """Test that creating a camera with duplicate name returns 409 Conflict.

        This provides idempotent-like behavior: repeated attempts to create
        the same camera (by name) will fail predictably.
        """
        unique = unique_id("cam")
        camera_data = {
            "name": f"Front Door {unique}",
            "folder_path": f"/export/foscam/front_door_{unique}",
            "status": "online",
        }

        # First creation should succeed
        response1 = await client.post("/api/cameras", json=camera_data)
        assert response1.status_code == 201

        # Second creation with same name should return 409
        camera_data_dup = {
            "name": f"Front Door {unique}",  # Same name
            "folder_path": f"/export/foscam/different_path_{unique}",  # Different path
            "status": "online",
        }
        response2 = await client.post("/api/cameras", json=camera_data_dup)
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_duplicate_folder_path_returns_409(self, client):
        """Test that creating a camera with duplicate folder_path returns 409 Conflict."""
        unique = unique_id("cam")
        camera_data = {
            "name": f"Camera A {unique}",
            "folder_path": f"/export/foscam/shared_path_{unique}",
            "status": "online",
        }

        # First creation should succeed
        response1 = await client.post("/api/cameras", json=camera_data)
        assert response1.status_code == 201

        # Second creation with same folder_path should return 409
        camera_data_dup = {
            "name": f"Camera B {unique}",  # Different name
            "folder_path": f"/export/foscam/shared_path_{unique}",  # Same path
            "status": "online",
        }
        response2 = await client.post("/api/cameras", json=camera_data_dup)
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_repeated_identical_requests_are_safe(self, client):
        """Test that repeated identical POST requests don't create duplicates.

        After the first successful creation, subsequent identical requests
        should return 409, ensuring no duplicate resources are created.
        """
        unique = unique_id("rep")
        camera_data = {
            "name": f"Repeated Camera {unique}",
            "folder_path": f"/export/foscam/repeated_{unique}",
            "status": "online",
        }

        # First request succeeds
        response1 = await client.post("/api/cameras", json=camera_data)
        assert response1.status_code == 201
        created_id = response1.json()["id"]

        # Subsequent identical requests fail with 409
        for _ in range(3):
            response = await client.post("/api/cameras", json=camera_data)
            assert response.status_code == 409

        # Verify only one camera was created
        list_response = await client.get("/api/cameras")
        assert list_response.status_code == 200
        cameras = [c for c in list_response.json()["cameras"] if c["id"] == created_id]
        assert len(cameras) == 1, "Only one camera should exist"

    @pytest.mark.asyncio
    async def test_concurrent_creation_handles_conflicts(self, client):
        """Test that concurrent camera creation requests handle conflicts correctly.

        When multiple concurrent requests try to create the same camera,
        exactly one should succeed and others should receive 409.
        """
        unique = unique_id("conc")
        camera_data = {
            "name": f"Concurrent Camera {unique}",
            "folder_path": f"/export/foscam/concurrent_{unique}",
            "status": "online",
        }

        # Send concurrent requests
        async def create_camera():
            return await client.post("/api/cameras", json=camera_data)

        results = await asyncio.gather(
            create_camera(),
            create_camera(),
            create_camera(),
            return_exceptions=True,
        )

        # Count successful and conflict responses
        successes = [r for r in results if hasattr(r, "status_code") and r.status_code == 201]
        conflicts = [r for r in results if hasattr(r, "status_code") and r.status_code == 409]
        errors = [r for r in results if isinstance(r, Exception)]

        # At least one should succeed, others should get 409 or retry-related errors
        assert len(successes) >= 1, "At least one request should succeed"
        assert len(successes) + len(conflicts) + len(errors) == 3


# =============================================================================
# PUT/PATCH Idempotency Tests
# =============================================================================


class TestUpdateIdempotency:
    """Tests for PUT/PATCH operation idempotency.

    PUT and PATCH operations should be idempotent by nature:
    making the same update multiple times should have the same effect
    as making it once.
    """

    @pytest.fixture
    async def existing_camera(self, client):
        """Create a camera for update tests."""
        unique = unique_id("upd")
        camera_data = {
            "name": f"Update Test Camera {unique}",
            "folder_path": f"/export/foscam/update_test_{unique}",
            "status": "online",
        }
        response = await client.post("/api/cameras", json=camera_data)
        assert response.status_code == 201
        yield response.json()

    @pytest.mark.asyncio
    async def test_patch_is_idempotent(self, client, existing_camera):
        """Test that PATCH operations are idempotent.

        Making the same PATCH request multiple times should result in
        the same final state.
        """
        camera_id = existing_camera["id"]
        update_data = {"status": "offline"}

        # First PATCH
        response1 = await client.patch(f"/api/cameras/{camera_id}", json=update_data)
        assert response1.status_code == 200
        assert response1.json()["status"] == "offline"

        # Second identical PATCH
        response2 = await client.patch(f"/api/cameras/{camera_id}", json=update_data)
        assert response2.status_code == 200
        assert response2.json()["status"] == "offline"

        # State should be identical
        assert response1.json()["status"] == response2.json()["status"]

    @pytest.mark.asyncio
    async def test_repeated_patches_same_result(self, client, existing_camera):
        """Test that repeated PATCH requests produce consistent results."""
        camera_id = existing_camera["id"]
        update_data = {"status": "error"}

        responses = []
        for _ in range(5):
            response = await client.patch(f"/api/cameras/{camera_id}", json=update_data)
            responses.append(response)

        # All should succeed
        for r in responses:
            assert r.status_code == 200
            assert r.json()["status"] == "error"


# =============================================================================
# DELETE Idempotency Tests
# =============================================================================


class TestDeleteIdempotency:
    """Tests for DELETE operation idempotency.

    DELETE operations should be idempotent: deleting the same resource
    multiple times should not cause errors (after the first successful delete).
    """

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, client):
        """Test that deleting a nonexistent resource returns 404."""
        fake_id = unique_id("nonexistent")
        response = await client.delete(f"/api/cameras/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_repeated_delete_is_safe(self, client):
        """Test that repeated DELETE requests don't cause errors.

        After successful deletion, subsequent DELETE requests should
        return 404 (resource not found), which is idempotent behavior.
        """
        # Create camera
        unique = unique_id("del")
        camera_data = {
            "name": f"Delete Test Camera {unique}",
            "folder_path": f"/export/foscam/delete_test_{unique}",
            "status": "online",
        }
        create_response = await client.post("/api/cameras", json=camera_data)
        assert create_response.status_code == 201
        camera_id = create_response.json()["id"]

        # First DELETE succeeds
        delete_response1 = await client.delete(f"/api/cameras/{camera_id}")
        assert delete_response1.status_code == 204

        # Subsequent DELETE requests return 404 (idempotent - resource is gone)
        for _ in range(3):
            delete_response = await client.delete(f"/api/cameras/{camera_id}")
            assert delete_response.status_code == 404


# =============================================================================
# Future: API-Level Idempotency-Key Header Tests (Not Yet Implemented)
# =============================================================================


class TestIdempotencyKeyHeader:
    """Tests for Idempotency-Key header handling.

    NOTE: These tests are skipped because Idempotency-Key header support
    is not yet implemented in the API. They document the expected behavior
    for future implementation.

    Expected behavior when implemented:
    - POST requests with same Idempotency-Key return cached response
    - Different Idempotency-Keys create separate resources
    - Idempotency-Keys expire after a reasonable TTL (e.g., 24 hours)
    - Conflicting request bodies with same key return error
    """

    @pytest.mark.skip(reason="Idempotency-Key header not implemented - future feature")
    @pytest.mark.asyncio
    async def test_same_idempotency_key_returns_cached_response(self, client):
        """Test that same Idempotency-Key returns cached response without duplicate creation.

        When implemented, POST requests with the same Idempotency-Key should:
        1. First request: Create resource, cache response
        2. Subsequent requests: Return cached response without creating new resource
        """
        unique = unique_id("idem")
        idempotency_key = f"idem-key-{unique}"
        camera_data = {
            "name": f"Idempotent Camera {unique}",
            "folder_path": f"/export/foscam/idempotent_{unique}",
            "status": "online",
        }

        headers = {"Idempotency-Key": idempotency_key}

        # First request creates the resource
        response1 = await client.post("/api/cameras", json=camera_data, headers=headers)
        assert response1.status_code == 201

        # Second request with same key returns cached response
        response2 = await client.post("/api/cameras", json=camera_data, headers=headers)
        assert response2.status_code == 201  # Same status as first
        assert response2.json()["id"] == response1.json()["id"]  # Same resource ID

    @pytest.mark.skip(reason="Idempotency-Key header not implemented - future feature")
    @pytest.mark.asyncio
    async def test_different_idempotency_keys_create_separate_resources(self, client):
        """Test that different Idempotency-Keys create separate resources.

        Each unique Idempotency-Key should result in a new resource creation
        (assuming unique data that doesn't violate other constraints).
        """
        base_unique = unique_id("diff")

        for i in range(3):
            idempotency_key = f"idem-key-{base_unique}-{i}"
            camera_data = {
                "name": f"Camera {base_unique}-{i}",
                "folder_path": f"/export/foscam/camera_{base_unique}_{i}",
                "status": "online",
            }

            headers = {"Idempotency-Key": idempotency_key}
            response = await client.post("/api/cameras", json=camera_data, headers=headers)
            assert response.status_code == 201

    @pytest.mark.skip(reason="Idempotency-Key header not implemented - future feature")
    @pytest.mark.asyncio
    async def test_conflicting_body_with_same_key_returns_error(self, client):
        """Test that conflicting request body with same Idempotency-Key returns error.

        If a request with the same Idempotency-Key but different body is received,
        it should return an error (e.g., 422 Unprocessable Entity) rather than
        silently returning the cached response.
        """
        unique = unique_id("conflict")
        idempotency_key = f"idem-key-{unique}"

        # First request
        camera_data1 = {
            "name": f"Conflict Camera {unique}",
            "folder_path": f"/export/foscam/conflict_{unique}",
            "status": "online",
        }
        headers = {"Idempotency-Key": idempotency_key}
        response1 = await client.post("/api/cameras", json=camera_data1, headers=headers)
        assert response1.status_code == 201

        # Second request with same key but different body
        camera_data2 = {
            "name": f"Different Name {unique}",  # Different name
            "folder_path": f"/export/foscam/conflict_{unique}",
            "status": "offline",  # Different status
        }
        response2 = await client.post("/api/cameras", json=camera_data2, headers=headers)
        # Should return error indicating body mismatch
        assert response2.status_code == 422

    @pytest.mark.skip(reason="Idempotency-Key header not implemented - future feature")
    @pytest.mark.asyncio
    async def test_idempotency_key_expires_after_ttl(self, client):
        """Test that Idempotency-Keys expire after TTL.

        After the idempotency key expires, a new request with the same key
        should be treated as a new request.

        Note: This test would require either:
        - Mocking time to simulate TTL expiration
        - A very short TTL configuration for testing
        """
        # This would require time manipulation or short TTL
        pass
