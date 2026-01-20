"""Integration tests for enrichment result SQLAlchemy models.

Tests use PostgreSQL via the session fixture since models use
PostgreSQL-specific features like JSONB.

Related Linear issue: NEM-3042
"""

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.models import (
    ActionResult,
    Camera,
    DemographicsResult,
    Detection,
    PoseResult,
    ReIDEmbedding,
    ThreatDetection,
)
from backend.tests.conftest import unique_id

# Mark as integration since these tests require real PostgreSQL database
pytestmark = pytest.mark.integration


class TestPoseResultModel:
    """Tests for the PoseResult model."""

    @pytest.mark.asyncio
    async def test_create_pose_result(self, session):
        """Test creating a pose result with required fields."""
        camera_id = unique_id("cam_pose")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_001.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        pose_result = PoseResult(
            detection_id=detection.id,
            pose_class="standing",
            confidence=0.95,
            is_suspicious=False,
        )
        session.add(pose_result)
        await session.flush()

        assert pose_result.id is not None
        assert pose_result.detection_id == detection.id
        assert pose_result.pose_class == "standing"
        assert pose_result.confidence == 0.95
        assert pose_result.is_suspicious is False
        assert isinstance(pose_result.created_at, datetime)

    @pytest.mark.asyncio
    async def test_pose_result_with_keypoints(self, session):
        """Test creating a pose result with COCO keypoints."""
        camera_id = unique_id("cam_pose_kp")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_002.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        # 17 COCO keypoints as [x, y, confidence]
        keypoints = [[100, 200, 0.9]] * 17

        pose_result = PoseResult(
            detection_id=detection.id,
            keypoints=keypoints,
            pose_class="crouching",
            confidence=0.88,
            is_suspicious=True,
        )
        session.add(pose_result)
        await session.flush()

        assert pose_result.keypoints == keypoints
        assert pose_result.is_suspicious is True

    @pytest.mark.asyncio
    async def test_pose_result_detection_relationship(self, session):
        """Test the relationship between PoseResult and Detection."""
        camera_id = unique_id("cam_pose_rel")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_003.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        pose_result = PoseResult(
            detection_id=detection.id,
            pose_class="standing",
            confidence=0.92,
        )
        session.add(pose_result)
        await session.flush()

        # Test forward relationship
        await session.refresh(pose_result, ["detection"])
        assert pose_result.detection is not None
        assert pose_result.detection.id == detection.id

        # Test reverse relationship
        await session.refresh(detection, ["pose_result"])
        assert detection.pose_result is not None
        assert detection.pose_result.id == pose_result.id

    @pytest.mark.asyncio
    async def test_pose_result_unique_detection(self, session):
        """Test that each detection can only have one pose result."""
        camera_id = unique_id("cam_pose_uniq")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_004.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        pose_result1 = PoseResult(
            detection_id=detection.id,
            pose_class="standing",
            confidence=0.9,
        )
        session.add(pose_result1)
        await session.flush()

        # Try to add another pose result for the same detection
        pose_result2 = PoseResult(
            detection_id=detection.id,
            pose_class="crouching",
            confidence=0.85,
        )
        session.add(pose_result2)

        with pytest.raises(IntegrityError):
            await session.flush()

    @pytest.mark.asyncio
    async def test_pose_result_repr(self, session):
        """Test pose result string representation."""
        camera_id = unique_id("cam_pose_repr")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_005.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        pose_result = PoseResult(
            detection_id=detection.id,
            pose_class="arms_raised",
            is_suspicious=True,
        )
        session.add(pose_result)
        await session.flush()

        repr_str = repr(pose_result)
        assert "PoseResult" in repr_str
        assert "arms_raised" in repr_str
        assert "is_suspicious=True" in repr_str


class TestThreatDetectionModel:
    """Tests for the ThreatDetection model."""

    @pytest.mark.asyncio
    async def test_create_threat_detection(self, session):
        """Test creating a threat detection with required fields."""
        camera_id = unique_id("cam_threat")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_001.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        threat = ThreatDetection(
            detection_id=detection.id,
            threat_type="knife",
            confidence=0.87,
            severity="high",
        )
        session.add(threat)
        await session.flush()

        assert threat.id is not None
        assert threat.detection_id == detection.id
        assert threat.threat_type == "knife"
        assert threat.confidence == 0.87
        assert threat.severity == "high"
        assert isinstance(threat.created_at, datetime)

    @pytest.mark.asyncio
    async def test_threat_detection_with_bbox(self, session):
        """Test creating a threat detection with bounding box."""
        camera_id = unique_id("cam_threat_bbox")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_002.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        bbox = [100, 150, 200, 250]  # [x1, y1, x2, y2]
        threat = ThreatDetection(
            detection_id=detection.id,
            threat_type="gun",
            confidence=0.96,
            severity="critical",
            bbox=bbox,
        )
        session.add(threat)
        await session.flush()

        assert threat.bbox == bbox
        assert threat.severity == "critical"

    @pytest.mark.asyncio
    async def test_multiple_threats_per_detection(self, session):
        """Test that a detection can have multiple threat detections."""
        camera_id = unique_id("cam_threat_multi")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_003.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        threat1 = ThreatDetection(
            detection_id=detection.id,
            threat_type="gun",
            confidence=0.92,
            severity="critical",
        )
        threat2 = ThreatDetection(
            detection_id=detection.id,
            threat_type="knife",
            confidence=0.78,
            severity="high",
        )
        session.add_all([threat1, threat2])
        await session.flush()

        # Query all threats for this detection
        await session.refresh(detection, ["threat_detections"])
        assert len(detection.threat_detections) == 2
        threat_types = {t.threat_type for t in detection.threat_detections}
        assert threat_types == {"gun", "knife"}

    @pytest.mark.asyncio
    async def test_threat_detection_repr(self, session):
        """Test threat detection string representation."""
        camera_id = unique_id("cam_threat_repr")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_004.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        threat = ThreatDetection(
            detection_id=detection.id,
            threat_type="weapon",
            confidence=0.85,
            severity="high",
        )
        session.add(threat)
        await session.flush()

        repr_str = repr(threat)
        assert "ThreatDetection" in repr_str
        assert "weapon" in repr_str
        assert "high" in repr_str


class TestDemographicsResultModel:
    """Tests for the DemographicsResult model."""

    @pytest.mark.asyncio
    async def test_create_demographics_result(self, session):
        """Test creating a demographics result with required fields."""
        camera_id = unique_id("cam_demo")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_001.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        demographics = DemographicsResult(
            detection_id=detection.id,
            age_range="31-40",
            age_confidence=0.78,
            gender="male",
            gender_confidence=0.92,
        )
        session.add(demographics)
        await session.flush()

        assert demographics.id is not None
        assert demographics.detection_id == detection.id
        assert demographics.age_range == "31-40"
        assert demographics.age_confidence == 0.78
        assert demographics.gender == "male"
        assert demographics.gender_confidence == 0.92
        assert isinstance(demographics.created_at, datetime)

    @pytest.mark.asyncio
    async def test_demographics_result_detection_relationship(self, session):
        """Test the relationship between DemographicsResult and Detection."""
        camera_id = unique_id("cam_demo_rel")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_002.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        demographics = DemographicsResult(
            detection_id=detection.id,
            age_range="21-30",
            gender="female",
        )
        session.add(demographics)
        await session.flush()

        # Test forward relationship
        await session.refresh(demographics, ["detection"])
        assert demographics.detection is not None
        assert demographics.detection.id == detection.id

        # Test reverse relationship
        await session.refresh(detection, ["demographics_result"])
        assert detection.demographics_result is not None
        assert detection.demographics_result.id == demographics.id

    @pytest.mark.asyncio
    async def test_demographics_result_repr(self, session):
        """Test demographics result string representation."""
        camera_id = unique_id("cam_demo_repr")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_003.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        demographics = DemographicsResult(
            detection_id=detection.id,
            age_range="51-60",
            gender="male",
        )
        session.add(demographics)
        await session.flush()

        repr_str = repr(demographics)
        assert "DemographicsResult" in repr_str
        assert "51-60" in repr_str
        assert "male" in repr_str


class TestReIDEmbeddingModel:
    """Tests for the ReIDEmbedding model."""

    @pytest.mark.asyncio
    async def test_create_reid_embedding(self, session):
        """Test creating a ReID embedding with required fields."""
        camera_id = unique_id("cam_reid")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_001.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        # 512-dimensional embedding vector
        embedding = [0.1] * 512

        reid = ReIDEmbedding(
            detection_id=detection.id,
            embedding=embedding,
            embedding_hash="abc123def456",  # pragma: allowlist secret
        )
        session.add(reid)
        await session.flush()

        assert reid.id is not None
        assert reid.detection_id == detection.id
        assert reid.embedding == embedding
        assert reid.embedding_hash == "abc123def456"  # pragma: allowlist secret
        assert isinstance(reid.created_at, datetime)

    @pytest.mark.asyncio
    async def test_reid_embedding_detection_relationship(self, session):
        """Test the relationship between ReIDEmbedding and Detection."""
        camera_id = unique_id("cam_reid_rel")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_002.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        embedding = [0.2] * 512
        reid = ReIDEmbedding(
            detection_id=detection.id,
            embedding=embedding,
        )
        session.add(reid)
        await session.flush()

        # Test forward relationship
        await session.refresh(reid, ["detection"])
        assert reid.detection is not None
        assert reid.detection.id == detection.id

        # Test reverse relationship
        await session.refresh(detection, ["reid_embedding"])
        assert detection.reid_embedding is not None
        assert detection.reid_embedding.id == reid.id

    @pytest.mark.asyncio
    async def test_query_by_embedding_hash(self, session):
        """Test querying ReID embeddings by hash for quick lookup."""
        camera_id = unique_id("cam_reid_hash")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_003.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        target_hash = "unique_hash_12345"
        reid = ReIDEmbedding(
            detection_id=detection.id,
            embedding=[0.3] * 512,
            embedding_hash=target_hash,
        )
        session.add(reid)
        await session.flush()

        # Query by hash
        stmt = select(ReIDEmbedding).where(ReIDEmbedding.embedding_hash == target_hash)
        result = await session.execute(stmt)
        found = result.scalar_one_or_none()

        assert found is not None
        assert found.id == reid.id

    @pytest.mark.asyncio
    async def test_reid_embedding_repr(self, session):
        """Test ReID embedding string representation."""
        camera_id = unique_id("cam_reid_repr")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_004.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        reid = ReIDEmbedding(
            detection_id=detection.id,
            embedding=[0.5678] * 512,
        )
        session.add(reid)
        await session.flush()

        repr_str = repr(reid)
        assert "ReIDEmbedding" in repr_str
        assert "0.5678" in repr_str


class TestActionResultModel:
    """Tests for the ActionResult model."""

    @pytest.mark.asyncio
    async def test_create_action_result(self, session):
        """Test creating an action result with required fields."""
        camera_id = unique_id("cam_action")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_001.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        action_result = ActionResult(
            detection_id=detection.id,
            action="walking",
            confidence=0.89,
            is_suspicious=False,
        )
        session.add(action_result)
        await session.flush()

        assert action_result.id is not None
        assert action_result.detection_id == detection.id
        assert action_result.action == "walking"
        assert action_result.confidence == 0.89
        assert action_result.is_suspicious is False
        assert isinstance(action_result.created_at, datetime)

    @pytest.mark.asyncio
    async def test_action_result_with_all_scores(self, session):
        """Test creating an action result with all candidate scores."""
        camera_id = unique_id("cam_action_scores")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_002.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        all_scores = {
            "climbing over fence": 0.85,
            "running": 0.10,
            "walking": 0.05,
        }

        action_result = ActionResult(
            detection_id=detection.id,
            action="climbing over fence",
            confidence=0.85,
            is_suspicious=True,
            all_scores=all_scores,
        )
        session.add(action_result)
        await session.flush()

        assert action_result.all_scores == all_scores
        assert action_result.is_suspicious is True

    @pytest.mark.asyncio
    async def test_action_result_detection_relationship(self, session):
        """Test the relationship between ActionResult and Detection."""
        camera_id = unique_id("cam_action_rel")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_003.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        action_result = ActionResult(
            detection_id=detection.id,
            action="running",
            confidence=0.92,
        )
        session.add(action_result)
        await session.flush()

        # Test forward relationship
        await session.refresh(action_result, ["detection"])
        assert action_result.detection is not None
        assert action_result.detection.id == detection.id

        # Test reverse relationship
        await session.refresh(detection, ["action_result"])
        assert detection.action_result is not None
        assert detection.action_result.id == action_result.id

    @pytest.mark.asyncio
    async def test_action_result_repr(self, session):
        """Test action result string representation."""
        camera_id = unique_id("cam_action_repr")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_004.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        action_result = ActionResult(
            detection_id=detection.id,
            action="picking lock",
            is_suspicious=True,
        )
        session.add(action_result)
        await session.flush()

        repr_str = repr(action_result)
        assert "ActionResult" in repr_str
        assert "picking lock" in repr_str
        assert "is_suspicious=True" in repr_str


class TestEnrichmentCascadeDelete:
    """Tests for cascade delete behavior of enrichment models."""

    @pytest.mark.asyncio
    async def test_cascade_delete_on_detection_delete(self, session):
        """Test that all enrichment results are deleted when detection is deleted."""
        camera_id = unique_id("cam_cascade")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/image_001.jpg",
            object_type="person",
        )
        session.add(detection)
        await session.flush()

        detection_id = detection.id

        # Add all enrichment types
        pose = PoseResult(detection_id=detection_id, pose_class="standing")
        threat = ThreatDetection(
            detection_id=detection_id,
            threat_type="knife",
            confidence=0.8,
            severity="high",
        )
        demographics = DemographicsResult(detection_id=detection_id, age_range="21-30")
        reid = ReIDEmbedding(detection_id=detection_id, embedding=[0.1] * 512)
        action = ActionResult(detection_id=detection_id, action="walking")

        session.add_all([pose, threat, demographics, reid, action])
        await session.flush()

        pose_id = pose.id
        threat_id = threat.id
        demographics_id = demographics.id
        reid_id = reid.id
        action_id = action.id

        # Delete the detection
        await session.delete(detection)
        await session.flush()

        # Verify all enrichment results are deleted
        assert await session.get(PoseResult, pose_id) is None
        assert await session.get(ThreatDetection, threat_id) is None
        assert await session.get(DemographicsResult, demographics_id) is None
        assert await session.get(ReIDEmbedding, reid_id) is None
        assert await session.get(ActionResult, action_id) is None
