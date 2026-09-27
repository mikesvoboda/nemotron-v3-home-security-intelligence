"""Household matching service for person and vehicle recognition.

This module provides functionality for matching detected persons and vehicles
against known household members and registered vehicles. This enables risk
score reduction for known individuals and vehicles.

The service uses:
- Person re-identification via embedding cosine similarity
- Vehicle license plate matching (exact, case-insensitive)
- Vehicle visual matching via embedding similarity (fallback)

Cached Embeddings (NEM-4234 Phase 3):
- extract_person_embedding(): Read person_reid from enrichment_data
- extract_vehicle_embedding(): Read vehicle_visual from enrichment_data

Implements NEM-3017: Implement HouseholdMatcher service for person/vehicle recognition.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.logging import get_logger
from backend.core.vector_provenance import LEGACY_MODEL_ID
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
        member_role: Role of the member (resident, family, service_worker, frequent_visitor)
                    Optional, used for enhanced prompt context display (NEM-3315)
        schedule_status: Schedule check result (True=within schedule, False=outside,
                        None=no schedule defined). Optional, used for risk calculation
                        in format_household_context (NEM-3315)
    """

    member_id: int | None = None
    member_name: str | None = None
    vehicle_id: int | None = None
    vehicle_description: str | None = None
    similarity: float = 0.0
    match_type: str = ""
    # NEM-3315: Optional fields for schedule and role display
    member_role: str | None = None
    schedule_status: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary containing all HouseholdMatch fields for storage.
        """
        return {
            "member_id": self.member_id,
            "member_name": self.member_name,
            "vehicle_id": self.vehicle_id,
            "vehicle_description": self.vehicle_description,
            "similarity": self.similarity,
            "match_type": self.match_type,
            "member_role": self.member_role,
            "schedule_status": self.schedule_status,
        }


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


class PersonMatchOutcome(enum.Enum):
    """What a person-gallery comparison DECIDED, not just a score (F11).

    The two states a bare score gives (match / no match) cannot express the
    truth of a half-migrated or untrusted gallery, and folding those into
    "no match" tells the VLM nobody is home when the real answer is "the
    gallery cannot answer yet" (ledger item 20: the full re-ID swap).
    """

    MATCH = "match"
    NO_MATCH = "no_match"
    #: Nothing in the gallery can be compared — untrusted (sentinel) rows,
    #: a probe of unknown provenance, or only cross-space rows. The honest
    #: line is "unavailable (re-enroll)", never a similarity.
    UNAVAILABLE_REENROLL = "unavailable_reenroll"
    #: The household has no stored vectors at all (never enrolled).
    NO_GALLERY = "no_gallery"


@dataclass(slots=True)
class PersonComparisonResult:
    outcome: PersonMatchOutcome
    match: HouseholdMatch | None = None
    #: Rows skipped for provenance/dimension (counted debug; never scored).
    skipped: int = 0


def compare_person_vectors(
    probe: np.ndarray,
    probe_model_id: str | None,
    gallery: list[tuple[int, str, np.ndarray, str]],
    *,
    threshold: float,
) -> PersonComparisonResult:
    """The F11 person-gallery decision as a PURE function (item 20).

    ``gallery`` rows are ``(member_id, member_name, vector, model_id)`` —
    both readers (the DB matcher and the VLM re-ID leg) feed the same
    decision through it, so "cross-space never scores" holds exactly once.

    Rules, in order:
    * a probe that never named its weights (None or the sentinel) is
      UNTRUSTED — the answer is re-enroll, whatever the gallery holds;
    * a row is scored ONLY when its model_id equals the probe's — not the
      threshold, not the vector bytes: the SAME bytes under another id are
      still a different space's claim;
    * an uncomparable row (foreign id, sentinel, mismatched length) is
      skipped and counted, never a raise — one stale 768-d row must not
      kill the pass over every comparable row (reid_service's helper
      raises mid-search; this is the guard replacing that failure);
    * nothing comparable is "unavailable (re-enroll)", not "no match";
      an empty gallery is its own state (never enrolled at all).
    """
    if not gallery:
        return PersonComparisonResult(PersonMatchOutcome.NO_GALLERY)

    if probe_model_id is None or probe_model_id == LEGACY_MODEL_ID:
        # A probe of unknown provenance cannot vouch for ANY comparison.
        return PersonComparisonResult(PersonMatchOutcome.UNAVAILABLE_REENROLL)

    best_id: int | None = None
    best_name: str = ""
    best_similarity = 0.0
    comparable = 0
    skipped = 0

    for member_id, member_name, vector, model_id in gallery:
        if model_id != probe_model_id:
            # Cross-space or untrusted: never scored, even byte-identical.
            skipped += 1
            continue
        if len(vector) != len(probe):
            # Same claimed space, different shape: a stale row, not a
            # score. Skip loudly-counted instead of raising mid-pass.
            skipped += 1
            continue
        comparable += 1
        similarity = cosine_similarity(probe, vector)
        if similarity > threshold and similarity > best_similarity:
            best_id, best_name, best_similarity = member_id, member_name, similarity

    if comparable == 0:
        return PersonComparisonResult(PersonMatchOutcome.UNAVAILABLE_REENROLL, skipped=skipped)

    if best_id is None:
        return PersonComparisonResult(PersonMatchOutcome.NO_MATCH, skipped=skipped)

    return PersonComparisonResult(
        PersonMatchOutcome.MATCH,
        match=HouseholdMatch(
            member_id=best_id,
            member_name=best_name,
            similarity=best_similarity,
            match_type="person",
        ),
        skipped=skipped,
    )


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
        model_id: str | None = None,
    ) -> HouseholdMatch | None:
        """Find matching household member for a person embedding.

        The comparison is F11's: a stored vector scores ONLY against a
        probe from the SAME weights (``model_id``), and a gallery with
        nothing comparable answers None like a no-match while the outcome
        says "unavailable (re-enroll)" — see
        :func:`compare_person_vectors` for the full table.

        Args:
            embedding: Person re-identification embedding vector
            session: Database session for queries
            model_id: Which weights computed ``embedding``. A caller that
                cannot say (None) is treated as untrusted — the same
                sentinel posture as a stored row that never named its
                producer, so callers must thread the producer's id to get
                a score at all.

        Returns:
            HouseholdMatch with member details if a match is found,
            None otherwise (no match, untrusted gallery, or empty gallery).
        """
        members = await self._get_all_member_embeddings(session)
        result = compare_person_vectors(
            embedding, model_id, members, threshold=self._similarity_threshold
        )

        if result.outcome is PersonMatchOutcome.MATCH and result.match is not None:
            logger.debug(
                "Person matched to %s (id=%d) with similarity %.3f",
                result.match.member_name,
                result.match.member_id,
                result.match.similarity,
            )
        else:
            logger.debug(
                "No person match (outcome=%s, %d rows skipped for provenance/dimension)",
                result.outcome.value,
                result.skipped,
            )

        return result.match

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
    ) -> list[tuple[int, str, np.ndarray, str]]:
        """Get all person embeddings with member info AND provenance.

        Queries all PersonEmbedding records joined with their HouseholdMember
        and returns them as (member_id, member_name, embedding, model_id)
        quads — the row's model_id rides along so the comparison can refuse
        cross-space pairs (F11/item 20); the gallery's shape is
        :func:`compare_person_vectors`'s input contract.

        Args:
            session: Database session for queries

        Returns:
            List of tuples (member_id, member_name, embedding_array, model_id)
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
                        person_embedding.model_id,
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

    async def match_detections(
        self,
        detections: list,
        enrichment_data: dict[int, dict],
        session: AsyncSession,
    ) -> tuple[dict[int, HouseholdMatch], dict[int, HouseholdMatch]]:
        """Match each detection individually, returning per-detection matches.

        This method implements detection-attributed household matching (NEM-4234 Phase 2)
        to prevent household context from one detection bleeding into risk assessment
        of other detections in the same batch.

        Args:
            detections: List of Detection objects to match
            enrichment_data: Dict mapping detection_id to enrichment data containing
                            cached embeddings in the "embeddings" key
            session: Database session for queries

        Returns:
            Tuple of (person_matches, vehicle_matches) where each is a dict mapping
            detection_id to HouseholdMatch. Detections without matches are not included.

        Example:
            >>> matcher = HouseholdMatcher()
            >>> person_matches, vehicle_matches = await matcher.match_detections(
            ...     detections=[det1, det2, det3],
            ...     enrichment_data={1: {...}, 2: {...}, 3: {...}},
            ...     session=session,
            ... )
            >>> # person_matches = {1: HouseholdMatch(member_name="Mike", ...)}
            >>> # vehicle_matches = {3: HouseholdMatch(vehicle_description="Honda", ...)}
        """
        person_matches: dict[int, HouseholdMatch] = {}
        vehicle_matches: dict[int, HouseholdMatch] = {}

        for detection in detections:
            det_id = detection.id
            enrichment = enrichment_data.get(det_id)
            if not enrichment:
                continue

            # Person matching via cached embedding. The payload's belt
            # rides along (A6, F11): a pre-swap cache entry has none and
            # compare_person_vectors answers re-enroll for it — never a
            # cross-space score.
            if detection.object_type == "person":
                person_embedding, probe_model_id = extract_person_embedding_with_provenance(
                    enrichment
                )
                if person_embedding:
                    embedding_array = np.array(person_embedding, dtype=np.float32)
                    match = await self.match_person(
                        embedding_array, session, model_id=probe_model_id
                    )
                    if match and match.similarity >= self._similarity_threshold:
                        person_matches[det_id] = match

            # Vehicle matching via plate or visual embedding
            elif detection.object_type in ("car", "truck", "motorcycle", "vehicle"):
                # Try license plate match first
                license_plates = enrichment.get("license_plates", [])
                plate_text = None
                if license_plates and len(license_plates) > 0:
                    first_plate = license_plates[0]
                    if isinstance(first_plate, dict):
                        plate_text = first_plate.get("text")
                    elif hasattr(first_plate, "text"):
                        plate_text = first_plate.text

                vehicle_embedding = extract_vehicle_embedding(enrichment)
                embedding_array = None
                if vehicle_embedding:
                    embedding_array = np.array(vehicle_embedding, dtype=np.float32)

                match = await self.match_vehicle(
                    license_plate=plate_text,
                    vehicle_embedding=embedding_array,
                    vehicle_type=detection.object_type,
                    color=enrichment.get("color"),
                    session=session,
                )
                if match:
                    vehicle_matches[det_id] = match

        logger.debug(
            "Matched %d detections: %d person matches, %d vehicle matches",
            len(detections),
            len(person_matches),
            len(vehicle_matches),
        )

        return person_matches, vehicle_matches


# =============================================================================
# Cached Embedding Extraction Functions (NEM-4234 Phase 3)
# =============================================================================


def extract_person_embedding(enrichment_data: dict[str, Any] | None) -> list[float] | None:
    """Extract person_reid embedding from enrichment_data.

    Reads the cached person re-identification embedding from the enrichment_data
    structure, enabling reuse across services without recomputing.

    Args:
        enrichment_data: The enrichment_data dict from a Detection, or None.

    Returns:
        List of floats representing the 512-dim OSNet embedding, or None if not available.

    Example:
        enrichment_data = {
            "embeddings": {
                "person_reid": [0.1, 0.2, ...],  # 512-dim
            }
        }
        embedding = extract_person_embedding(enrichment_data)
    """
    if enrichment_data is None:
        return None

    embeddings = enrichment_data.get("embeddings")
    if embeddings is None:
        return None

    person_reid = embeddings.get("person_reid")
    if person_reid is None:
        return None

    # Empty list means no valid embedding
    if isinstance(person_reid, list) and len(person_reid) == 0:
        return None

    # Cast to list[float] for type safety
    return list(person_reid) if isinstance(person_reid, list) else None


def extract_person_embedding_with_provenance(
    enrichment_data: dict[str, Any] | None,
) -> tuple[list[float] | None, str | None]:
    """Extract (person_reid embedding, model_id) from enrichment_data.

    The A6 twin of extract_person_embedding: since the full swap the cached
    payload carries the belt its producer stamped (F11 — every stored or
    relayed vector names the weights that computed it). A payload written
    BEFORE the swap has no belt and this reports None honestly; the reader
    must NOT launder it — compare_person_vectors answers
    UNAVAILABLE_REENROLL for an unprovenanced probe, which is the drop-and-
    re-enroll ruling expressed at read time.
    """
    if enrichment_data is None:
        return None, None

    embeddings = enrichment_data.get("embeddings")
    if embeddings is None:
        return None, None

    embedding = extract_person_embedding(enrichment_data)
    raw_model_id = embeddings.get("model_id")
    return embedding, str(raw_model_id) if raw_model_id else None


def extract_vehicle_embedding(enrichment_data: dict[str, Any] | None) -> list[float] | None:
    """Extract vehicle_visual embedding from enrichment_data.

    Reads the cached vehicle visual embedding from the enrichment_data
    structure, enabling reuse across services without recomputing.

    Args:
        enrichment_data: The enrichment_data dict from a Detection, or None.

    Returns:
        List of floats representing the 768-dim CLIP embedding, or None if not available.

    Example:
        enrichment_data = {
            "embeddings": {
                "vehicle_visual": [0.3, 0.4, ...],  # 768-dim
            }
        }
        embedding = extract_vehicle_embedding(enrichment_data)
    """
    if enrichment_data is None:
        return None

    embeddings = enrichment_data.get("embeddings")
    if embeddings is None:
        return None

    vehicle_visual = embeddings.get("vehicle_visual")
    if vehicle_visual is None:
        return None

    # Empty list means no valid embedding
    if isinstance(vehicle_visual, list) and len(vehicle_visual) == 0:
        return None

    # Cast to list[float] for type safety
    return list(vehicle_visual) if isinstance(vehicle_visual, list) else None


def extract_face_embedding(enrichment_data: dict[str, Any] | None) -> list[float] | None:
    """Extract face_clip embedding from enrichment_data.

    Reads the cached face CLIP embedding from the enrichment_data
    structure, enabling reuse across services without recomputing.

    Args:
        enrichment_data: The enrichment_data dict from a Detection, or None.

    Returns:
        List of floats representing the 768-dim CLIP embedding, or None if not available.

    Example:
        enrichment_data = {
            "embeddings": {
                "face_clip": [0.5, 0.6, ...],  # 768-dim
            }
        }
        embedding = extract_face_embedding(enrichment_data)
    """
    if enrichment_data is None:
        return None

    embeddings = enrichment_data.get("embeddings")
    if embeddings is None:
        return None

    face_clip = embeddings.get("face_clip")
    if face_clip is None:
        return None

    # Empty list means no valid embedding
    if isinstance(face_clip, list) and len(face_clip) == 0:
        return None

    # Cast to list[float] for type safety
    return list(face_clip) if isinstance(face_clip, list) else None


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
