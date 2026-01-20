"""Household matching service for person and vehicle recognition.

This module provides functionality for matching detected persons and vehicles
against known household members and registered vehicles. This enables risk
score reduction for known individuals and vehicles.

The service uses:
- Person re-identification via embedding cosine similarity
- Vehicle license plate matching (exact, case-insensitive)
- Vehicle visual matching via embedding similarity (fallback)

Implements NEM-3017: Implement HouseholdMatcher service for person/vehicle recognition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.logging import get_logger
from backend.models.household import (
    PersonEmbedding,
    RegisteredVehicle,
    VehicleType,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


@dataclass(slots=True)
class HouseholdMatch:
    """Result of household matching.

    Attributes:
        member_id: ID of the matched household member (for person matches)
        member_name: Name of the matched household member
        vehicle_id: ID of the matched registered vehicle
        vehicle_description: Description of the matched vehicle
        similarity: Cosine similarity score (0-1, or 1.0 for exact plate match)
        match_type: Type of match ("person", "license_plate", "vehicle_visual")
    """

    member_id: int | None = None
    member_name: str | None = None
    vehicle_id: int | None = None
    vehicle_description: str | None = None
    similarity: float = 0.0
    match_type: str = ""


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1

    Note:
        Returns 0.0 if either vector has zero magnitude.
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    # Avoid division by zero
    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


class HouseholdMatcher:
    """Match detections against known household members and vehicles.

    This service provides methods to match:
    - Person detections against household members via embedding similarity
    - Vehicle detections against registered vehicles via license plate or visual

    The matching uses configurable similarity thresholds to determine matches.
    Higher thresholds reduce false positives but may miss legitimate matches.

    Usage:
        matcher = HouseholdMatcher()

        # Match a person
        embedding = np.array([...])  # Person re-ID embedding
        match = await matcher.match_person(embedding, session)
        if match:
            print(f"Matched: {match.member_name} (similarity: {match.similarity:.2f})")

        # Match a vehicle
        match = await matcher.match_vehicle(
            license_plate="ABC123",
            vehicle_embedding=embedding,
            vehicle_type="car",
            color="silver",
            session=session,
        )
        if match:
            print(f"Matched: {match.vehicle_description}")
    """

    # Default similarity threshold for matching
    SIMILARITY_THRESHOLD = 0.85

    def __init__(self, similarity_threshold: float | None = None) -> None:
        """Initialize the HouseholdMatcher.

        Args:
            similarity_threshold: Minimum cosine similarity for a match.
                                  Defaults to 0.85 if not provided.
        """
        self._similarity_threshold = (
            similarity_threshold if similarity_threshold is not None else self.SIMILARITY_THRESHOLD
        )
        logger.info(
            "HouseholdMatcher initialized with similarity_threshold=%.2f",
            self._similarity_threshold,
        )

    @property
    def similarity_threshold(self) -> float:
        """Get the similarity threshold for matching.

        Returns:
            The configured similarity threshold (0-1).
        """
        return self._similarity_threshold

    async def match_person(
        self,
        embedding: np.ndarray,
        session: AsyncSession,
    ) -> HouseholdMatch | None:
        """Find matching household member for a person embedding.

        Compares the provided embedding against all stored person embeddings
        and returns the best match if it exceeds the similarity threshold.

        Args:
            embedding: Person re-identification embedding vector
            session: Database session for queries

        Returns:
            HouseholdMatch with member details if a match is found,
            None if no match exceeds the threshold.
        """
        members = await self._get_all_member_embeddings(session)

        if not members:
            logger.debug("No member embeddings found in database")
            return None

        best_match: HouseholdMatch | None = None
        best_similarity = 0.0

        for member_id, member_name, member_embedding in members:
            similarity = cosine_similarity(embedding, member_embedding)

            if similarity > self._similarity_threshold and similarity > best_similarity:
                best_match = HouseholdMatch(
                    member_id=member_id,
                    member_name=member_name,
                    similarity=similarity,
                    match_type="person",
                )
                best_similarity = similarity

        if best_match:
            logger.debug(
                "Person matched to %s (id=%d) with similarity %.3f",
                best_match.member_name,
                best_match.member_id,
                best_match.similarity,
            )
        else:
            logger.debug(
                "No person match found (best similarity below threshold %.2f)",
                self._similarity_threshold,
            )

        return best_match

    async def match_vehicle(
        self,
        license_plate: str | None,
        vehicle_embedding: np.ndarray | None,
        vehicle_type: str,
        color: str | None,
        session: AsyncSession,
    ) -> HouseholdMatch | None:
        """Find matching registered vehicle.

        Matching priority:
        1. License plate match (exact, case-insensitive) - returns similarity 1.0
        2. Visual embedding match (if plate doesn't match or isn't provided)

        Args:
            license_plate: Detected license plate text (optional)
            vehicle_embedding: Vehicle re-ID embedding vector (optional)
            vehicle_type: Type of vehicle (car, truck, etc.)
            color: Detected vehicle color (optional)
            session: Database session for queries

        Returns:
            HouseholdMatch with vehicle details if a match is found,
            None if no match is found.
        """
        # Try license plate match first (exact, case-insensitive)
        if license_plate:
            vehicle = await self._find_by_plate(license_plate, session)
            if vehicle:
                logger.debug(
                    "Vehicle matched by license plate '%s' to '%s' (id=%d)",
                    license_plate,
                    vehicle.description,
                    vehicle.id,
                )
                return HouseholdMatch(
                    vehicle_id=vehicle.id,
                    vehicle_description=vehicle.description,
                    similarity=1.0,
                    match_type="license_plate",
                )

        # Fall back to visual matching if embedding provided
        if vehicle_embedding is not None:
            return await self._match_vehicle_visual(vehicle_embedding, vehicle_type, color, session)

        logger.debug("No vehicle match found (no plate or embedding provided)")
        return None

    async def _get_all_member_embeddings(
        self, session: AsyncSession
    ) -> list[tuple[int, str, np.ndarray]]:
        """Get all person embeddings with member info.

        Queries all PersonEmbedding records joined with their HouseholdMember
        and returns them as tuples of (member_id, member_name, embedding).

        Args:
            session: Database session for queries

        Returns:
            List of tuples (member_id, member_name, embedding_array)
        """
        result = []

        # Query PersonEmbedding with eager loading of member relationship
        stmt = select(PersonEmbedding).options(selectinload(PersonEmbedding.member))
        query_result = await session.execute(stmt)
        embeddings = query_result.scalars().all()

        for person_embedding in embeddings:
            if person_embedding.member is None:
                continue

            # Deserialize embedding from bytes to numpy array
            try:
                embedding_array = np.frombuffer(person_embedding.embedding, dtype=np.float32)
                result.append(
                    (
                        person_embedding.member.id,
                        person_embedding.member.name,
                        embedding_array,
                    )
                )
            except Exception as e:
                logger.warning(
                    "Failed to deserialize embedding for member %d: %s",
                    person_embedding.member_id,
                    str(e),
                )

        return result

    async def _find_by_plate(self, plate: str, session: AsyncSession) -> RegisteredVehicle | None:
        """Find vehicle by license plate (case-insensitive).

        Args:
            plate: License plate text to search for
            session: Database session for queries

        Returns:
            RegisteredVehicle if found, None otherwise.
        """
        # Normalize plate to uppercase for comparison
        plate_upper = plate.upper()

        # Query vehicles where license plate matches (case-insensitive)
        stmt = select(RegisteredVehicle).where(
            RegisteredVehicle.license_plate.isnot(None),
            RegisteredVehicle.trusted.is_(True),
        )
        query_result = await session.execute(stmt)
        vehicles = query_result.scalars().all()

        for vehicle in vehicles:
            if vehicle.license_plate and vehicle.license_plate.upper() == plate_upper:
                return vehicle

        return None

    async def _match_vehicle_visual(
        self,
        embedding: np.ndarray,
        vehicle_type: str,  # noqa: ARG002 - reserved for future filtering
        color: str | None,  # noqa: ARG002 - reserved for future filtering
        session: AsyncSession,
    ) -> HouseholdMatch | None:
        """Match vehicle by visual embedding similarity.

        Compares the provided vehicle embedding against all stored vehicle
        embeddings and returns the best match if it exceeds the threshold.

        Args:
            embedding: Vehicle re-ID embedding vector
            vehicle_type: Type of detected vehicle (for filtering, not yet used)
            color: Detected color (for filtering, not yet used)
            session: Database session for queries

        Returns:
            HouseholdMatch with vehicle details if a match is found,
            None if no match exceeds the threshold.
        """
        vehicles = await self._get_vehicles_with_embeddings(session)

        if not vehicles:
            logger.debug("No vehicle embeddings found in database")
            return None

        best_match: HouseholdMatch | None = None
        best_similarity = 0.0

        for vehicle_id, description, _v_type, _v_color, vehicle_embedding in vehicles:
            similarity = cosine_similarity(embedding, vehicle_embedding)

            if similarity > self._similarity_threshold and similarity > best_similarity:
                best_match = HouseholdMatch(
                    vehicle_id=vehicle_id,
                    vehicle_description=description,
                    similarity=similarity,
                    match_type="vehicle_visual",
                )
                best_similarity = similarity

        if best_match:
            logger.debug(
                "Vehicle matched visually to '%s' (id=%d) with similarity %.3f",
                best_match.vehicle_description,
                best_match.vehicle_id,
                best_match.similarity,
            )
        else:
            logger.debug(
                "No visual vehicle match found (best similarity below threshold %.2f)",
                self._similarity_threshold,
            )

        return best_match

    async def _get_vehicles_with_embeddings(
        self, session: AsyncSession
    ) -> list[tuple[int, str, VehicleType, str | None, np.ndarray]]:
        """Get all vehicles that have visual embeddings.

        Args:
            session: Database session for queries

        Returns:
            List of tuples (vehicle_id, description, vehicle_type, color, embedding)
        """
        result = []

        # Query trusted vehicles with embeddings
        stmt = select(RegisteredVehicle).where(
            RegisteredVehicle.reid_embedding.isnot(None),
            RegisteredVehicle.trusted.is_(True),
        )
        query_result = await session.execute(stmt)
        vehicles = query_result.scalars().all()

        for vehicle in vehicles:
            if vehicle.reid_embedding is None:
                continue

            # Deserialize embedding from bytes to numpy array
            try:
                embedding_array = np.frombuffer(vehicle.reid_embedding, dtype=np.float32)
                result.append(
                    (
                        vehicle.id,
                        vehicle.description,
                        vehicle.vehicle_type,
                        vehicle.color,
                        embedding_array,
                    )
                )
            except Exception as e:
                logger.warning(
                    "Failed to deserialize embedding for vehicle %d: %s",
                    vehicle.id,
                    str(e),
                )

        return result


# =============================================================================
# Global Service Instance (Singleton Pattern)
# =============================================================================

_household_matcher: HouseholdMatcher | None = None


def get_household_matcher() -> HouseholdMatcher:
    """Get or create the global HouseholdMatcher instance.

    Returns:
        Global HouseholdMatcher instance
    """
    global _household_matcher  # noqa: PLW0603
    if _household_matcher is None:
        _household_matcher = HouseholdMatcher()
    return _household_matcher


def reset_household_matcher() -> None:
    """Reset the global HouseholdMatcher instance (for testing)."""
    global _household_matcher  # noqa: PLW0603
    _household_matcher = None
