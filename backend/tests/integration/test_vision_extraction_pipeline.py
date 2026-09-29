"""Integration tests for the re-identification and scene-change services.

R8 S2b scope note: the EnrichmentPipeline/VisionExtractor harness this file
was built around is retired with the legacy enrichment path, so the
pipeline-level suites (vision extraction wiring, the EnrichmentResult
carrier, full-pipeline context strings, edge cases that drove enrich_batch)
are gone with it. What survives is the two services the pipeline used to
drive and that the shipped product still owns:

  * ReIdentificationService - embedding store/match against REAL Redis
    (D-3 model_id partitioning, same-detection exclusion, cross-camera match)
  * SceneChangeDetector - per-camera baseline tracking and SSIM similarity

Tests cover:
- Re-identification with real Redis storage
- Scene change detection across frames
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import numpy as np
import pytest
from PIL import Image

from backend.services.reid_service import (
    EntityEmbedding,
    get_reid_service,
    reset_reid_service,
)
from backend.services.scene_change_detector import (
    get_scene_change_detector,
    reset_scene_change_detector,
)

# A named OSNet-space belt for the fixtures (grammar from osnet_model_id(),
# ledger item 20). D-3 partitions Redis by model_id, so a fixture that wants
# its rows found has to store AND search under ONE name.
_TEST_REID_MODEL_ID = "osnet-ain-x1-0@test-weights@testsha0000"

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def test_image() -> Image.Image:
    """Create a test RGB image for processing."""
    return Image.new("RGB", (640, 480), color=(128, 128, 128))


@pytest.fixture
def test_image_variant() -> Image.Image:
    """Create a variant test image (different content for scene change)."""
    return Image.new("RGB", (640, 480), color=(200, 100, 50))


@pytest.fixture(autouse=True)
def reset_global_services():
    """Reset global service instances before and after each test."""
    reset_reid_service()
    reset_scene_change_detector()
    yield
    reset_reid_service()
    reset_scene_change_detector()


# =============================================================================
# Re-Identification Integration Tests
# =============================================================================


class TestReIdentificationIntegration:
    """Integration tests for ReIdentificationService with real Redis."""

    @pytest.fixture(autouse=True)
    async def cleanup_reid_keys(self, real_redis):
        """Clean up entity embedding keys before and after each test."""
        redis_client = real_redis._ensure_connected()

        async def _cleanup():
            # Delete all entity_embeddings keys to ensure test isolation
            keys = await redis_client.keys("entity_embeddings:*")
            if keys:
                await redis_client.delete(*keys)

        await _cleanup()
        yield
        await _cleanup()

    @pytest.mark.asyncio
    async def test_reid_service_stores_and_matches_embeddings(
        self, real_redis, test_image: Image.Image
    ):
        """Test re-id service can store and match embeddings using Redis."""
        reid_service = get_reid_service()
        # Use RedisClient wrapper (which uses 'expire=' parameter) instead of raw Redis
        redis_client = real_redis

        # A named OSNet-space test vector (512-d, ledger item 20): D-3 reads
        # ONLY the partition named by the probe's model_id, so the belt is
        # part of the fixture, not decoration.
        test_embedding = [float(i % 100) / 100.0 for i in range(512)]
        # Normalize it
        norm = sum(x * x for x in test_embedding) ** 0.5
        test_embedding = [x / norm for x in test_embedding]

        # Store the embedding
        entity = EntityEmbedding(
            entity_type="person",
            embedding=test_embedding,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="det_001",
            model_id=_TEST_REID_MODEL_ID,
            attributes={"clothing": "blue jacket"},
        )
        await reid_service.store_embedding(redis_client, entity)

        # Try to match with a similar embedding (same vector should match perfectly)
        matches = await reid_service.find_matching_entities(
            redis_client,
            test_embedding,
            entity_type="person",
            threshold=0.9,
            exclude_detection_id="det_002",  # Different detection
            model_id=_TEST_REID_MODEL_ID,
        )

        assert len(matches) == 1
        assert matches[0].similarity > 0.99  # Should be near-perfect match
        assert matches[0].entity.detection_id == "det_001"
        assert matches[0].entity.attributes["clothing"] == "blue jacket"

    @pytest.mark.asyncio
    async def test_reid_service_excludes_same_detection(self, real_redis, test_image: Image.Image):
        """Test re-id service excludes the same detection from matches."""
        reid_service = get_reid_service()
        # Use RedisClient wrapper (which uses 'expire=' parameter) instead of raw Redis
        redis_client = real_redis

        test_embedding = [float(i % 100) / 100.0 for i in range(512)]
        norm = sum(x * x for x in test_embedding) ** 0.5
        test_embedding = [x / norm for x in test_embedding]

        # Store the embedding
        entity = EntityEmbedding(
            entity_type="person",
            embedding=test_embedding,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="det_same",
            model_id=_TEST_REID_MODEL_ID,
            attributes={},
        )
        await reid_service.store_embedding(redis_client, entity)

        # Search excluding the same detection ID
        matches = await reid_service.find_matching_entities(
            redis_client,
            test_embedding,
            entity_type="person",
            threshold=0.5,
            exclude_detection_id="det_same",  # Same detection
            model_id=_TEST_REID_MODEL_ID,
        )

        # Should not find any matches
        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_reid_matches_across_cameras(self, real_redis, test_image: Image.Image):
        """Test re-id can match the same entity across different cameras."""
        reid_service = get_reid_service()
        # Use RedisClient wrapper (which uses 'expire=' parameter) instead of raw Redis
        redis_client = real_redis

        # Create embedding for person at front door
        base_embedding = [float(i % 100) / 100.0 for i in range(512)]
        norm = sum(x * x for x in base_embedding) ** 0.5
        base_embedding = [x / norm for x in base_embedding]

        entity1 = EntityEmbedding(
            entity_type="person",
            embedding=base_embedding,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="det_front_001",
            model_id=_TEST_REID_MODEL_ID,
            attributes={"clothing": "red shirt"},
        )
        await reid_service.store_embedding(redis_client, entity1)

        # Slightly perturbed embedding (same person, different angle)
        perturbed = [x + 0.01 * ((i % 3) - 1) for i, x in enumerate(base_embedding)]
        norm = sum(x * x for x in perturbed) ** 0.5
        perturbed = [x / norm for x in perturbed]

        # Search from garage camera
        matches = await reid_service.find_matching_entities(
            redis_client,
            perturbed,
            entity_type="person",
            threshold=0.85,
            exclude_detection_id="det_garage_001",
            model_id=_TEST_REID_MODEL_ID,
        )

        assert len(matches) >= 1
        assert matches[0].entity.camera_id == "front_door"
        assert matches[0].similarity > 0.9


# =============================================================================
# Scene Change Detection Integration Tests
# =============================================================================


class TestSceneChangeIntegration:
    """Integration tests for SceneChangeDetector."""

    @pytest.mark.asyncio
    async def test_scene_detector_detects_significant_change(
        self, test_image: Image.Image, test_image_variant: Image.Image
    ):
        """Test scene detector identifies significant scene changes."""
        detector = get_scene_change_detector()
        camera_id = f"test_cam_{uuid.uuid4().hex[:8]}"

        # First frame - establishes baseline
        frame1 = np.array(test_image)
        result1 = detector.detect_changes(camera_id, frame1)
        assert not result1.change_detected  # First frame, no previous

        # Second frame - very different content
        frame2 = np.array(test_image_variant)
        result2 = detector.detect_changes(camera_id, frame2)

        # Should detect change since images are different colors
        assert result2.similarity_score < 1.0

    @pytest.mark.asyncio
    async def test_scene_detector_no_change_same_frame(self, test_image: Image.Image):
        """Test scene detector shows no change for identical frames."""
        detector = get_scene_change_detector()
        camera_id = f"test_cam_{uuid.uuid4().hex[:8]}"

        frame = np.array(test_image)

        # First frame
        detector.detect_changes(camera_id, frame)

        # Same frame again
        result = detector.detect_changes(camera_id, frame)

        # SSIM of identical images should be 1.0
        assert result.similarity_score > 0.99
        assert not result.change_detected

    @pytest.mark.asyncio
    async def test_scene_detector_tracks_per_camera(
        self, test_image: Image.Image, test_image_variant: Image.Image
    ):
        """Test scene detector tracks state independently per camera."""
        detector = get_scene_change_detector()
        cam1 = f"cam1_{uuid.uuid4().hex[:8]}"
        cam2 = f"cam2_{uuid.uuid4().hex[:8]}"

        frame1 = np.array(test_image)
        frame2 = np.array(test_image_variant)

        # Establish baseline for cam1 with frame1
        detector.detect_changes(cam1, frame1)

        # Establish baseline for cam2 with frame2
        detector.detect_changes(cam2, frame2)

        # Now cam1 sees frame1 again - no change
        result1 = detector.detect_changes(cam1, frame1)
        assert result1.similarity_score > 0.99

        # cam2 sees frame2 again - no change
        result2 = detector.detect_changes(cam2, frame2)
        assert result2.similarity_score > 0.99
