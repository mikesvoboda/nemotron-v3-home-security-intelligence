"""Integration tests for face recognition service.

Tests the FaceRecognitionService with a real database connection to verify:
- Known person CRUD operations
- Face embedding storage and retrieval
- Face matching against known persons
- Face detection event recording
- Unknown stranger detection

Implements NEM-3716: Face detection with InsightFace
Implements NEM-3717: Face quality assessment for recognition
"""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.face_identity import (
    FaceEmbedding,
)
from backend.services.face_recognition_service import (
    FaceRecognitionService,
    cosine_similarity,
    get_face_recognition_service,
    reset_face_recognition_service,
)


@pytest.fixture
def service() -> FaceRecognitionService:
    """Create a fresh service instance for each test."""
    reset_face_recognition_service()
    return get_face_recognition_service()


def generate_random_embedding(seed: int = 42) -> list[float]:
    """Generate a random 512-dimensional embedding for testing."""
    rng = np.random.default_rng(seed)
    emb = rng.standard_normal(512).astype(np.float32)
    # Normalize to unit vector
    emb = emb / np.linalg.norm(emb)
    return emb.tolist()


def generate_similar_embedding(
    base_embedding: list[float], noise_level: float = 0.1
) -> list[float]:
    """Generate an embedding similar to the base embedding.

    Args:
        base_embedding: The reference embedding
        noise_level: How much noise to add (lower = more similar)

    Returns:
        A new embedding similar to the base
    """
    rng = np.random.default_rng(123)
    base = np.array(base_embedding, dtype=np.float32)
    noise = rng.standard_normal(512).astype(np.float32) * noise_level
    new_emb = base + noise
    # Normalize
    new_emb = new_emb / np.linalg.norm(new_emb)
    return new_emb.tolist()


class TestCosineimilarity:
    """Tests for cosine similarity calculation."""

    def test_identical_vectors_have_similarity_one(self) -> None:
        """Identical normalized vectors should have similarity 1."""
        emb = generate_random_embedding(seed=1)
        a = np.array(emb, dtype=np.float32)
        b = np.array(emb, dtype=np.float32)
        similarity = cosine_similarity(a, b)
        assert similarity == pytest.approx(1.0, rel=1e-5)

    def test_orthogonal_vectors_have_similarity_zero(self) -> None:
        """Orthogonal vectors should have similarity 0."""
        # Create two orthogonal vectors
        a = np.zeros(512, dtype=np.float32)
        a[0] = 1.0
        b = np.zeros(512, dtype=np.float32)
        b[1] = 1.0
        similarity = cosine_similarity(a, b)
        assert similarity == pytest.approx(0.0, abs=1e-5)

    def test_opposite_vectors_have_similarity_negative_one(self) -> None:
        """Opposite vectors should have similarity -1."""
        emb = generate_random_embedding(seed=2)
        a = np.array(emb, dtype=np.float32)
        b = -a
        similarity = cosine_similarity(a, b)
        assert similarity == pytest.approx(-1.0, rel=1e-5)

    def test_similar_vectors_have_high_similarity(self) -> None:
        """Similar vectors should have high similarity."""
        base_emb = generate_random_embedding(seed=3)
        similar_emb = generate_similar_embedding(base_emb, noise_level=0.1)
        a = np.array(base_emb, dtype=np.float32)
        b = np.array(similar_emb, dtype=np.float32)
        similarity = cosine_similarity(a, b)
        assert similarity > 0.9

    def test_zero_vector_returns_zero(self) -> None:
        """Zero vector should return similarity 0."""
        a = np.zeros(512, dtype=np.float32)
        b = np.array(generate_random_embedding(seed=4), dtype=np.float32)
        similarity = cosine_similarity(a, b)
        assert similarity == 0.0


@pytest.mark.integration
@pytest.mark.db
class TestKnownPersonManagement:
    """Tests for known person CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_known_person(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test creating a new known person."""
        person = await service.create_known_person(
            db_session,
            name="John Doe",
            is_household_member=True,
            notes="Test person",
        )

        assert person.id is not None
        assert person.name == "John Doe"
        assert person.is_household_member is True
        assert person.notes == "Test person"
        assert person.created_at is not None
        assert person.updated_at is not None

    @pytest.mark.asyncio
    async def test_get_known_person(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test retrieving a known person by ID."""
        # Create person
        person = await service.create_known_person(
            db_session,
            name="Jane Smith",
            is_household_member=False,
        )

        # Retrieve
        retrieved = await service.get_known_person(db_session, person.id)

        assert retrieved is not None
        assert retrieved.id == person.id
        assert retrieved.name == "Jane Smith"

    @pytest.mark.asyncio
    async def test_get_nonexistent_person_returns_none(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test that getting a nonexistent person returns None."""
        result = await service.get_known_person(db_session, 99999)
        assert result is None

    @pytest.mark.asyncio
    async def test_list_known_persons(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test listing all known persons."""
        # Create multiple persons
        await service.create_known_person(db_session, name="Alice", is_household_member=True)
        await service.create_known_person(db_session, name="Bob", is_household_member=False)
        await service.create_known_person(db_session, name="Charlie", is_household_member=True)

        # List all
        persons = await service.list_known_persons(db_session)
        assert len(persons) >= 3

        # List household members only
        household = await service.list_known_persons(db_session, household_only=True)
        assert all(p.is_household_member for p in household)
        assert len(household) >= 2

    @pytest.mark.asyncio
    async def test_update_known_person(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test updating a known person."""
        # Create
        person = await service.create_known_person(
            db_session,
            name="Original Name",
            is_household_member=False,
        )

        # Update
        updated = await service.update_known_person(
            db_session,
            person.id,
            name="Updated Name",
            is_household_member=True,
            notes="Added notes",
        )

        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.is_household_member is True
        assert updated.notes == "Added notes"

    @pytest.mark.asyncio
    async def test_update_nonexistent_person_returns_none(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test that updating a nonexistent person returns None."""
        result = await service.update_known_person(
            db_session,
            99999,
            name="New Name",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_known_person(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test deleting a known person."""
        # Create
        person = await service.create_known_person(db_session, name="To Delete")

        # Delete
        deleted = await service.delete_known_person(db_session, person.id)
        assert deleted is True

        # Verify deleted
        result = await service.get_known_person(db_session, person.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_person_returns_false(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test that deleting a nonexistent person returns False."""
        result = await service.delete_known_person(db_session, 99999)
        assert result is False


@pytest.mark.integration
@pytest.mark.db
class TestFaceEmbeddingManagement:
    """Tests for face embedding storage and retrieval."""

    @pytest.mark.asyncio
    async def test_add_face_embedding(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test adding a face embedding for a known person."""
        # Create person
        person = await service.create_known_person(db_session, name="Test Person")

        # Add embedding
        embedding_vector = generate_random_embedding(seed=100)
        embedding = await service.add_face_embedding(
            db_session,
            person.id,
            embedding=embedding_vector,
            quality_score=0.95,
            source_image_path="/test/image.jpg",
        )

        assert embedding is not None
        assert embedding.person_id == person.id
        assert embedding.quality_score == pytest.approx(0.95)
        assert embedding.source_image_path == "/test/image.jpg"

    @pytest.mark.asyncio
    async def test_add_embedding_for_nonexistent_person_returns_none(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test that adding embedding for nonexistent person returns None."""
        embedding_vector = generate_random_embedding(seed=101)
        result = await service.add_face_embedding(
            db_session,
            99999,
            embedding=embedding_vector,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_person_embeddings(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test retrieving all embeddings for a person."""
        # Create person
        person = await service.create_known_person(db_session, name="Multi Embedding Person")

        # Add multiple embeddings
        for i in range(3):
            await service.add_face_embedding(
                db_session,
                person.id,
                embedding=generate_random_embedding(seed=200 + i),
                quality_score=0.8 + i * 0.05,
            )

        # Get embeddings
        embeddings = await service.get_person_embeddings(db_session, person.id)
        assert len(embeddings) == 3

    @pytest.mark.asyncio
    async def test_delete_face_embedding(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test deleting a face embedding."""
        # Create person and embedding
        person = await service.create_known_person(db_session, name="Delete Embedding Person")
        embedding = await service.add_face_embedding(
            db_session,
            person.id,
            embedding=generate_random_embedding(seed=300),
        )

        # Delete embedding
        deleted = await service.delete_face_embedding(db_session, embedding.id)
        assert deleted is True

        # Verify deleted
        embeddings = await service.get_person_embeddings(db_session, person.id)
        assert len(embeddings) == 0

    @pytest.mark.asyncio
    async def test_cascade_delete_embeddings_when_person_deleted(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test that embeddings are deleted when person is deleted."""
        # Create person with embeddings
        person = await service.create_known_person(db_session, name="Cascade Delete Person")
        for i in range(2):
            await service.add_face_embedding(
                db_session,
                person.id,
                embedding=generate_random_embedding(seed=400 + i),
            )

        # Delete person
        await service.delete_known_person(db_session, person.id)

        # Verify embeddings are also deleted (check via direct query)
        from sqlalchemy import select

        stmt = select(FaceEmbedding).where(FaceEmbedding.person_id == person.id)
        result = await db_session.execute(stmt)
        embeddings = result.scalars().all()
        assert len(embeddings) == 0


@pytest.mark.integration
@pytest.mark.db
class TestFaceMatching:
    """Tests for face matching against known persons."""

    @pytest.mark.asyncio
    async def test_match_face_finds_known_person(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test that matching returns the correct known person."""
        # Create person with embedding
        person = await service.create_known_person(
            db_session,
            name="Match Test Person",
            is_household_member=True,
        )
        base_embedding = generate_random_embedding(seed=500)
        await service.add_face_embedding(
            db_session,
            person.id,
            embedding=base_embedding,
        )

        # Match with similar embedding
        query_embedding = generate_similar_embedding(base_embedding, noise_level=0.05)
        result = await service.match_face(db_session, query_embedding)

        assert result["matched"] is True
        assert result["person_id"] == person.id
        assert result["person_name"] == "Match Test Person"
        assert result["is_household_member"] is True
        assert result["similarity"] > 0.68
        assert result["is_unknown"] is False

    @pytest.mark.asyncio
    async def test_match_face_no_match_returns_unknown(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test that non-matching face returns unknown."""
        # Create person with embedding
        person = await service.create_known_person(db_session, name="Known Person")
        await service.add_face_embedding(
            db_session,
            person.id,
            embedding=generate_random_embedding(seed=600),
        )

        # Match with very different embedding
        query_embedding = generate_random_embedding(seed=700)  # Different seed
        result = await service.match_face(db_session, query_embedding)

        assert result["matched"] is False
        assert result["person_id"] is None
        assert result["person_name"] is None
        assert result["is_unknown"] is True

    @pytest.mark.asyncio
    async def test_match_face_empty_database(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test matching when no known persons exist."""
        query_embedding = generate_random_embedding(seed=800)
        result = await service.match_face(db_session, query_embedding)

        assert result["matched"] is False
        assert result["is_unknown"] is True
        assert result["similarity"] == 0.0

    @pytest.mark.asyncio
    async def test_match_face_custom_threshold(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test matching with custom similarity threshold."""
        # Create person with embedding
        person = await service.create_known_person(db_session, name="Threshold Test")
        base_embedding = generate_random_embedding(seed=900)
        await service.add_face_embedding(
            db_session,
            person.id,
            embedding=base_embedding,
        )

        # Create moderately similar embedding
        query_embedding = generate_similar_embedding(base_embedding, noise_level=0.3)

        # With high threshold, should not match
        result_high = await service.match_face(db_session, query_embedding, threshold=0.95)
        assert result_high["matched"] is False

        # With low threshold, should match
        result_low = await service.match_face(db_session, query_embedding, threshold=0.5)
        assert result_low["matched"] is True

    @pytest.mark.asyncio
    async def test_match_face_returns_best_match(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
    ) -> None:
        """Test that matching returns the best match among multiple persons."""
        # Create multiple persons with different embeddings
        person1 = await service.create_known_person(db_session, name="Person 1")
        person2 = await service.create_known_person(db_session, name="Person 2")
        person3 = await service.create_known_person(db_session, name="Person 3")

        base_embedding = generate_random_embedding(seed=1000)
        await service.add_face_embedding(
            db_session, person1.id, embedding=generate_random_embedding(seed=1001)
        )
        await service.add_face_embedding(
            db_session,
            person2.id,
            embedding=base_embedding,  # This should be the best match
        )
        await service.add_face_embedding(
            db_session, person3.id, embedding=generate_random_embedding(seed=1003)
        )

        # Match with embedding very similar to person2
        query_embedding = generate_similar_embedding(base_embedding, noise_level=0.02)
        result = await service.match_face(db_session, query_embedding)

        assert result["matched"] is True
        assert result["person_id"] == person2.id
        assert result["person_name"] == "Person 2"


@pytest.mark.integration
@pytest.mark.db
class TestFaceDetectionEventRecording:
    """Tests for face detection event recording."""

    @pytest.fixture
    async def test_camera(self, db_session: AsyncSession) -> str:
        """Create a test camera for face detection events."""
        from backend.models.camera import Camera

        camera = Camera(
            id="test_face_camera",
            name="Test Face Camera",
            folder_path="/data/cameras/test_face_camera",
            status="online",
        )
        db_session.add(camera)
        await db_session.commit()
        return camera.id

    @pytest.mark.asyncio
    async def test_record_face_detection_unknown(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
        test_camera: str,
    ) -> None:
        """Test recording an unknown face detection."""
        event = await service.record_face_detection(
            db_session,
            camera_id=test_camera,
            timestamp=datetime.now(UTC),
            bbox=[100, 150, 200, 300],
            embedding=generate_random_embedding(seed=2000),
            quality_score=0.85,
            age_estimate=35,
            gender_estimate="M",
        )

        assert event.id is not None
        assert event.camera_id == test_camera
        assert event.is_unknown is True
        assert event.matched_person_id is None
        assert event.quality_score == pytest.approx(0.85)
        assert event.age_estimate == 35
        assert event.gender_estimate == "M"

    @pytest.mark.asyncio
    async def test_record_face_detection_with_auto_match(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
        test_camera: str,
    ) -> None:
        """Test recording a face detection that auto-matches a known person."""
        # Create known person with embedding
        person = await service.create_known_person(db_session, name="Auto Match Person")
        base_embedding = generate_random_embedding(seed=2100)
        await service.add_face_embedding(db_session, person.id, embedding=base_embedding)

        # Record face detection with similar embedding
        query_embedding = generate_similar_embedding(base_embedding, noise_level=0.05)
        event = await service.record_face_detection(
            db_session,
            camera_id=test_camera,
            timestamp=datetime.now(UTC),
            bbox=[100, 150, 200, 300],
            embedding=query_embedding,
            quality_score=0.9,
            auto_match=True,
        )

        assert event.is_unknown is False
        assert event.matched_person_id == person.id
        assert event.match_confidence is not None
        assert event.match_confidence > 0.68

    @pytest.mark.asyncio
    async def test_record_face_detection_without_auto_match(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
        test_camera: str,
    ) -> None:
        """Test recording without auto-matching."""
        # Create known person with embedding
        person = await service.create_known_person(db_session, name="No Auto Match Person")
        base_embedding = generate_random_embedding(seed=2200)
        await service.add_face_embedding(db_session, person.id, embedding=base_embedding)

        # Record with auto_match=False
        event = await service.record_face_detection(
            db_session,
            camera_id=test_camera,
            timestamp=datetime.now(UTC),
            bbox=[100, 150, 200, 300],
            embedding=base_embedding,  # Same embedding
            quality_score=0.9,
            auto_match=False,
        )

        # Should be unknown since auto_match is disabled
        assert event.is_unknown is True
        assert event.matched_person_id is None

    @pytest.mark.asyncio
    async def test_list_face_events(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
        test_camera: str,
    ) -> None:
        """Test listing face detection events."""
        # Create some events
        now = datetime.now(UTC)
        for i in range(5):
            await service.record_face_detection(
                db_session,
                camera_id=test_camera,
                timestamp=now - timedelta(hours=i),
                bbox=[100, 150, 200, 300],
                embedding=generate_random_embedding(seed=2300 + i),
                quality_score=0.8,
            )

        # List all events
        events, total = await service.list_face_events(db_session, limit=10)
        assert len(events) >= 5
        assert total >= 5

    @pytest.mark.asyncio
    async def test_list_face_events_with_filters(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
        test_camera: str,
    ) -> None:
        """Test listing events with various filters."""
        now = datetime.now(UTC)

        # Create events at different times
        for i in range(5):
            await service.record_face_detection(
                db_session,
                camera_id=test_camera,
                timestamp=now - timedelta(hours=i),
                bbox=[100, 150, 200, 300],
                embedding=generate_random_embedding(seed=2400 + i),
                quality_score=0.8,
            )

        # Filter by time range
        events, total = await service.list_face_events(
            db_session,
            start_time=now - timedelta(hours=2),
            end_time=now,
        )
        # Should get events from last 2 hours
        assert len(events) >= 2

        # Filter by camera
        events, total = await service.list_face_events(
            db_session,
            camera_id=test_camera,
        )
        assert all(e.camera_id == test_camera for e in events)

    @pytest.mark.asyncio
    async def test_get_unknown_strangers(
        self,
        service: FaceRecognitionService,
        db_session: AsyncSession,
        test_camera: str,
    ) -> None:
        """Test getting unknown stranger alerts."""
        now = datetime.now(UTC)

        # Create known person
        person = await service.create_known_person(db_session, name="Known")
        known_emb = generate_random_embedding(seed=2500)
        await service.add_face_embedding(db_session, person.id, embedding=known_emb)

        # Create a mix of known and unknown detections
        # Unknown face
        await service.record_face_detection(
            db_session,
            camera_id=test_camera,
            timestamp=now - timedelta(minutes=5),
            bbox=[100, 150, 200, 300],
            embedding=generate_random_embedding(seed=2501),  # Different, will be unknown
            quality_score=0.8,
            auto_match=True,
        )

        # Known face
        await service.record_face_detection(
            db_session,
            camera_id=test_camera,
            timestamp=now - timedelta(minutes=10),
            bbox=[100, 150, 200, 300],
            embedding=generate_similar_embedding(known_emb, noise_level=0.05),
            quality_score=0.9,
            auto_match=True,
        )

        # Low quality unknown (should be filtered out with min_quality)
        await service.record_face_detection(
            db_session,
            camera_id=test_camera,
            timestamp=now - timedelta(minutes=15),
            bbox=[100, 150, 200, 300],
            embedding=generate_random_embedding(seed=2503),
            quality_score=0.2,  # Low quality
            auto_match=True,
        )

        # Get unknown strangers with min_quality filter
        strangers = await service.get_unknown_strangers(
            db_session,
            min_quality=0.3,
        )

        # Should only get high-quality unknown faces
        assert all(s.is_unknown for s in strangers)
        assert all(s.quality_score >= 0.3 for s in strangers)


@pytest.mark.integration
@pytest.mark.db
class TestServiceSingleton:
    """Tests for service singleton pattern."""

    def test_get_service_returns_same_instance(self) -> None:
        """Test that get_face_recognition_service returns same instance."""
        reset_face_recognition_service()

        service1 = get_face_recognition_service()
        service2 = get_face_recognition_service()

        assert service1 is service2

    def test_reset_creates_new_instance(self) -> None:
        """Test that reset creates a new instance."""
        service1 = get_face_recognition_service()
        reset_face_recognition_service()
        service2 = get_face_recognition_service()

        assert service1 is not service2

    def test_default_threshold(self) -> None:
        """Test service uses default similarity threshold."""
        reset_face_recognition_service()
        service = get_face_recognition_service()

        assert service.similarity_threshold == pytest.approx(0.68)
