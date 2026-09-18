"""Auto-enrollment service for high-confidence face detections.

This service automatically enrolls faces from high-confidence detections
into the known persons database, with options for:
- Queue-based review workflow (default)
- Fully automatic enrollment mode
- Duplicate detection to prevent re-enrolling known faces
- Linking to existing household members when possible

Implements NEM-4941: Face Auto-Enrollment from High-Confidence Detections
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.core.logging import get_logger
from backend.models.face_identity import (
    EnrollmentCandidate,
    EnrollmentStatus,
    FaceDetectionEvent,
    FaceEmbedding,
    KnownPerson,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# Default thresholds for auto-enrollment
DEFAULT_CONFIDENCE_THRESHOLD = 0.95  # Minimum detection confidence
DEFAULT_QUALITY_THRESHOLD = 0.8  # Minimum face quality score
DEFAULT_SIMILARITY_THRESHOLD = 0.85  # Threshold for duplicate detection


from mutmut.mutation.trampoline import wrap_in_trampoline as _mutmut_mutated, MutantDict
mutants_x_cosine_similarity__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_cosine_similarity__mutmut)
def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


def x_cosine_similarity__mutmut_orig(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


def x_cosine_similarity__mutmut_1(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = None
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


def x_cosine_similarity__mutmut_2(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(None)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


def x_cosine_similarity__mutmut_3(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = None

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


def x_cosine_similarity__mutmut_4(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(None)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


def x_cosine_similarity__mutmut_5(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 and norm_b == 0:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


def x_cosine_similarity__mutmut_6(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a != 0 or norm_b == 0:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


def x_cosine_similarity__mutmut_7(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 1 or norm_b == 0:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


def x_cosine_similarity__mutmut_8(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b != 0:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


def x_cosine_similarity__mutmut_9(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 1:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


def x_cosine_similarity__mutmut_10(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(None)


def x_cosine_similarity__mutmut_11(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(a, b) * (norm_a * norm_b))


def x_cosine_similarity__mutmut_12(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(None, b) / (norm_a * norm_b))


def x_cosine_similarity__mutmut_13(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(a, None) / (norm_a * norm_b))


def x_cosine_similarity__mutmut_14(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(b) / (norm_a * norm_b))


def x_cosine_similarity__mutmut_15(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(a, ) / (norm_a * norm_b))


def x_cosine_similarity__mutmut_16(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(a, b) / (norm_a / norm_b))

mutants_x_cosine_similarity__mutmut['_mutmut_orig'] = x_cosine_similarity__mutmut_orig # type: ignore # mutmut generated
mutants_x_cosine_similarity__mutmut['x_cosine_similarity__mutmut_1'] = x_cosine_similarity__mutmut_1 # type: ignore # mutmut generated
mutants_x_cosine_similarity__mutmut['x_cosine_similarity__mutmut_2'] = x_cosine_similarity__mutmut_2 # type: ignore # mutmut generated
mutants_x_cosine_similarity__mutmut['x_cosine_similarity__mutmut_3'] = x_cosine_similarity__mutmut_3 # type: ignore # mutmut generated
mutants_x_cosine_similarity__mutmut['x_cosine_similarity__mutmut_4'] = x_cosine_similarity__mutmut_4 # type: ignore # mutmut generated
mutants_x_cosine_similarity__mutmut['x_cosine_similarity__mutmut_5'] = x_cosine_similarity__mutmut_5 # type: ignore # mutmut generated
mutants_x_cosine_similarity__mutmut['x_cosine_similarity__mutmut_6'] = x_cosine_similarity__mutmut_6 # type: ignore # mutmut generated
mutants_x_cosine_similarity__mutmut['x_cosine_similarity__mutmut_7'] = x_cosine_similarity__mutmut_7 # type: ignore # mutmut generated
mutants_x_cosine_similarity__mutmut['x_cosine_similarity__mutmut_8'] = x_cosine_similarity__mutmut_8 # type: ignore # mutmut generated
mutants_x_cosine_similarity__mutmut['x_cosine_similarity__mutmut_9'] = x_cosine_similarity__mutmut_9 # type: ignore # mutmut generated
mutants_x_cosine_similarity__mutmut['x_cosine_similarity__mutmut_10'] = x_cosine_similarity__mutmut_10 # type: ignore # mutmut generated
mutants_x_cosine_similarity__mutmut['x_cosine_similarity__mutmut_11'] = x_cosine_similarity__mutmut_11 # type: ignore # mutmut generated
mutants_x_cosine_similarity__mutmut['x_cosine_similarity__mutmut_12'] = x_cosine_similarity__mutmut_12 # type: ignore # mutmut generated
mutants_x_cosine_similarity__mutmut['x_cosine_similarity__mutmut_13'] = x_cosine_similarity__mutmut_13 # type: ignore # mutmut generated
mutants_x_cosine_similarity__mutmut['x_cosine_similarity__mutmut_14'] = x_cosine_similarity__mutmut_14 # type: ignore # mutmut generated
mutants_x_cosine_similarity__mutmut['x_cosine_similarity__mutmut_15'] = x_cosine_similarity__mutmut_15 # type: ignore # mutmut generated
mutants_x_cosine_similarity__mutmut['x_cosine_similarity__mutmut_16'] = x_cosine_similarity__mutmut_16 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁ__init____mutmut: MutantDict = {}  # type: ignore
mutants_xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut: MutantDict = {}  # type: ignore
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut: MutantDict = {}  # type: ignore
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut: MutantDict = {}  # type: ignore
mutants_xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut: MutantDict = {}  # type: ignore
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut: MutantDict = {}  # type: ignore
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut: MutantDict = {}  # type: ignore
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut: MutantDict = {}  # type: ignore
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut: MutantDict = {}  # type: ignore


class AutoEnrollmentService:
    """Service for automatic face enrollment from high-confidence detections.

    This service provides methods to:
    - Evaluate faces for auto-enrollment eligibility
    - Detect duplicate faces to prevent re-enrollment
    - Add eligible faces to an enrollment queue for review
    - Automatically enroll faces when enabled
    - Approve or reject enrollment candidates

    Usage:
        service = AutoEnrollmentService()

        # Process a face detection event
        result = await service.process_event(session, face_event)
        if result["action"] == "queued":
            print(f"Added to queue: {result['candidate_id']}")
        elif result["action"] == "enrolled":
            print(f"Auto-enrolled as: {result['person_id']}")

    Attributes:
        confidence_threshold: Minimum detection confidence for eligibility
        quality_threshold: Minimum face quality score for eligibility
        similarity_threshold: Threshold for duplicate detection
        auto_approve: If True, skip queue and auto-enroll immediately
    """

    @_mutmut_mutated(mutants_xǁAutoEnrollmentServiceǁ__init____mutmut)
    def __init__(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        auto_approve: bool = False,
    ) -> None:
        """Initialize the auto-enrollment service.

        Args:
            confidence_threshold: Minimum confidence for enrollment (0-1)
            quality_threshold: Minimum quality score for enrollment (0-1)
            similarity_threshold: Similarity threshold for duplicate detection (0-1)
            auto_approve: If True, automatically enroll without queue review
        """
        self._confidence_threshold = confidence_threshold
        self._quality_threshold = quality_threshold
        self._similarity_threshold = similarity_threshold
        self._auto_approve = auto_approve

        logger.info(
            "AutoEnrollmentService initialized: "
            f"confidence={self._confidence_threshold}, "
            f"quality={self._quality_threshold}, "
            f"similarity={self._similarity_threshold}, "
            f"auto_approve={self._auto_approve}"
        )

    def xǁAutoEnrollmentServiceǁ__init____mutmut_orig(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        auto_approve: bool = False,
    ) -> None:
        """Initialize the auto-enrollment service.

        Args:
            confidence_threshold: Minimum confidence for enrollment (0-1)
            quality_threshold: Minimum quality score for enrollment (0-1)
            similarity_threshold: Similarity threshold for duplicate detection (0-1)
            auto_approve: If True, automatically enroll without queue review
        """
        self._confidence_threshold = confidence_threshold
        self._quality_threshold = quality_threshold
        self._similarity_threshold = similarity_threshold
        self._auto_approve = auto_approve

        logger.info(
            "AutoEnrollmentService initialized: "
            f"confidence={self._confidence_threshold}, "
            f"quality={self._quality_threshold}, "
            f"similarity={self._similarity_threshold}, "
            f"auto_approve={self._auto_approve}"
        )

    def xǁAutoEnrollmentServiceǁ__init____mutmut_1(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        auto_approve: bool = True,
    ) -> None:
        """Initialize the auto-enrollment service.

        Args:
            confidence_threshold: Minimum confidence for enrollment (0-1)
            quality_threshold: Minimum quality score for enrollment (0-1)
            similarity_threshold: Similarity threshold for duplicate detection (0-1)
            auto_approve: If True, automatically enroll without queue review
        """
        self._confidence_threshold = confidence_threshold
        self._quality_threshold = quality_threshold
        self._similarity_threshold = similarity_threshold
        self._auto_approve = auto_approve

        logger.info(
            "AutoEnrollmentService initialized: "
            f"confidence={self._confidence_threshold}, "
            f"quality={self._quality_threshold}, "
            f"similarity={self._similarity_threshold}, "
            f"auto_approve={self._auto_approve}"
        )

    def xǁAutoEnrollmentServiceǁ__init____mutmut_2(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        auto_approve: bool = False,
    ) -> None:
        """Initialize the auto-enrollment service.

        Args:
            confidence_threshold: Minimum confidence for enrollment (0-1)
            quality_threshold: Minimum quality score for enrollment (0-1)
            similarity_threshold: Similarity threshold for duplicate detection (0-1)
            auto_approve: If True, automatically enroll without queue review
        """
        self._confidence_threshold = None
        self._quality_threshold = quality_threshold
        self._similarity_threshold = similarity_threshold
        self._auto_approve = auto_approve

        logger.info(
            "AutoEnrollmentService initialized: "
            f"confidence={self._confidence_threshold}, "
            f"quality={self._quality_threshold}, "
            f"similarity={self._similarity_threshold}, "
            f"auto_approve={self._auto_approve}"
        )

    def xǁAutoEnrollmentServiceǁ__init____mutmut_3(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        auto_approve: bool = False,
    ) -> None:
        """Initialize the auto-enrollment service.

        Args:
            confidence_threshold: Minimum confidence for enrollment (0-1)
            quality_threshold: Minimum quality score for enrollment (0-1)
            similarity_threshold: Similarity threshold for duplicate detection (0-1)
            auto_approve: If True, automatically enroll without queue review
        """
        self._confidence_threshold = confidence_threshold
        self._quality_threshold = None
        self._similarity_threshold = similarity_threshold
        self._auto_approve = auto_approve

        logger.info(
            "AutoEnrollmentService initialized: "
            f"confidence={self._confidence_threshold}, "
            f"quality={self._quality_threshold}, "
            f"similarity={self._similarity_threshold}, "
            f"auto_approve={self._auto_approve}"
        )

    def xǁAutoEnrollmentServiceǁ__init____mutmut_4(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        auto_approve: bool = False,
    ) -> None:
        """Initialize the auto-enrollment service.

        Args:
            confidence_threshold: Minimum confidence for enrollment (0-1)
            quality_threshold: Minimum quality score for enrollment (0-1)
            similarity_threshold: Similarity threshold for duplicate detection (0-1)
            auto_approve: If True, automatically enroll without queue review
        """
        self._confidence_threshold = confidence_threshold
        self._quality_threshold = quality_threshold
        self._similarity_threshold = None
        self._auto_approve = auto_approve

        logger.info(
            "AutoEnrollmentService initialized: "
            f"confidence={self._confidence_threshold}, "
            f"quality={self._quality_threshold}, "
            f"similarity={self._similarity_threshold}, "
            f"auto_approve={self._auto_approve}"
        )

    def xǁAutoEnrollmentServiceǁ__init____mutmut_5(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        auto_approve: bool = False,
    ) -> None:
        """Initialize the auto-enrollment service.

        Args:
            confidence_threshold: Minimum confidence for enrollment (0-1)
            quality_threshold: Minimum quality score for enrollment (0-1)
            similarity_threshold: Similarity threshold for duplicate detection (0-1)
            auto_approve: If True, automatically enroll without queue review
        """
        self._confidence_threshold = confidence_threshold
        self._quality_threshold = quality_threshold
        self._similarity_threshold = similarity_threshold
        self._auto_approve = None

        logger.info(
            "AutoEnrollmentService initialized: "
            f"confidence={self._confidence_threshold}, "
            f"quality={self._quality_threshold}, "
            f"similarity={self._similarity_threshold}, "
            f"auto_approve={self._auto_approve}"
        )

    def xǁAutoEnrollmentServiceǁ__init____mutmut_6(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        auto_approve: bool = False,
    ) -> None:
        """Initialize the auto-enrollment service.

        Args:
            confidence_threshold: Minimum confidence for enrollment (0-1)
            quality_threshold: Minimum quality score for enrollment (0-1)
            similarity_threshold: Similarity threshold for duplicate detection (0-1)
            auto_approve: If True, automatically enroll without queue review
        """
        self._confidence_threshold = confidence_threshold
        self._quality_threshold = quality_threshold
        self._similarity_threshold = similarity_threshold
        self._auto_approve = auto_approve

        logger.info(
            None
        )

    def xǁAutoEnrollmentServiceǁ__init____mutmut_7(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        auto_approve: bool = False,
    ) -> None:
        """Initialize the auto-enrollment service.

        Args:
            confidence_threshold: Minimum confidence for enrollment (0-1)
            quality_threshold: Minimum quality score for enrollment (0-1)
            similarity_threshold: Similarity threshold for duplicate detection (0-1)
            auto_approve: If True, automatically enroll without queue review
        """
        self._confidence_threshold = confidence_threshold
        self._quality_threshold = quality_threshold
        self._similarity_threshold = similarity_threshold
        self._auto_approve = auto_approve

        logger.info(
            "XXAutoEnrollmentService initialized: XX"
            f"confidence={self._confidence_threshold}, "
            f"quality={self._quality_threshold}, "
            f"similarity={self._similarity_threshold}, "
            f"auto_approve={self._auto_approve}"
        )

    def xǁAutoEnrollmentServiceǁ__init____mutmut_8(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        auto_approve: bool = False,
    ) -> None:
        """Initialize the auto-enrollment service.

        Args:
            confidence_threshold: Minimum confidence for enrollment (0-1)
            quality_threshold: Minimum quality score for enrollment (0-1)
            similarity_threshold: Similarity threshold for duplicate detection (0-1)
            auto_approve: If True, automatically enroll without queue review
        """
        self._confidence_threshold = confidence_threshold
        self._quality_threshold = quality_threshold
        self._similarity_threshold = similarity_threshold
        self._auto_approve = auto_approve

        logger.info(
            "autoenrollmentservice initialized: "
            f"confidence={self._confidence_threshold}, "
            f"quality={self._quality_threshold}, "
            f"similarity={self._similarity_threshold}, "
            f"auto_approve={self._auto_approve}"
        )

    def xǁAutoEnrollmentServiceǁ__init____mutmut_9(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        auto_approve: bool = False,
    ) -> None:
        """Initialize the auto-enrollment service.

        Args:
            confidence_threshold: Minimum confidence for enrollment (0-1)
            quality_threshold: Minimum quality score for enrollment (0-1)
            similarity_threshold: Similarity threshold for duplicate detection (0-1)
            auto_approve: If True, automatically enroll without queue review
        """
        self._confidence_threshold = confidence_threshold
        self._quality_threshold = quality_threshold
        self._similarity_threshold = similarity_threshold
        self._auto_approve = auto_approve

        logger.info(
            "AUTOENROLLMENTSERVICE INITIALIZED: "
            f"confidence={self._confidence_threshold}, "
            f"quality={self._quality_threshold}, "
            f"similarity={self._similarity_threshold}, "
            f"auto_approve={self._auto_approve}"
        )

    @property
    def confidence_threshold(self) -> float:
        """Get the confidence threshold."""
        return self._confidence_threshold

    @property
    def quality_threshold(self) -> float:
        """Get the quality threshold."""
        return self._quality_threshold

    @property
    def similarity_threshold(self) -> float:
        """Get the similarity threshold for duplicate detection."""
        return self._similarity_threshold

    @property
    def auto_approve(self) -> bool:
        """Get the auto-approve setting."""
        return self._auto_approve

    # =========================================================================
    # Quality Threshold Validation
    # =========================================================================

    @_mutmut_mutated(mutants_xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut)
    def should_auto_enroll(self, quality_score: float, is_unknown: bool) -> bool:
        """Check if a face detection should be auto-enrolled.

        Args:
            quality_score: Face quality score (0-1)
            is_unknown: Whether the face is currently unknown

        Returns:
            True if the face meets auto-enrollment criteria
        """
        if not is_unknown:
            # Already matched to a known person
            return False

        # Quality must meet threshold
        return quality_score >= self._quality_threshold

    # =========================================================================
    # Quality Threshold Validation
    # =========================================================================

    def xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut_orig(self, quality_score: float, is_unknown: bool) -> bool:
        """Check if a face detection should be auto-enrolled.

        Args:
            quality_score: Face quality score (0-1)
            is_unknown: Whether the face is currently unknown

        Returns:
            True if the face meets auto-enrollment criteria
        """
        if not is_unknown:
            # Already matched to a known person
            return False

        # Quality must meet threshold
        return quality_score >= self._quality_threshold

    # =========================================================================
    # Quality Threshold Validation
    # =========================================================================

    def xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut_1(self, quality_score: float, is_unknown: bool) -> bool:
        """Check if a face detection should be auto-enrolled.

        Args:
            quality_score: Face quality score (0-1)
            is_unknown: Whether the face is currently unknown

        Returns:
            True if the face meets auto-enrollment criteria
        """
        if is_unknown:
            # Already matched to a known person
            return False

        # Quality must meet threshold
        return quality_score >= self._quality_threshold

    # =========================================================================
    # Quality Threshold Validation
    # =========================================================================

    def xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut_2(self, quality_score: float, is_unknown: bool) -> bool:
        """Check if a face detection should be auto-enrolled.

        Args:
            quality_score: Face quality score (0-1)
            is_unknown: Whether the face is currently unknown

        Returns:
            True if the face meets auto-enrollment criteria
        """
        if not is_unknown:
            # Already matched to a known person
            return True

        # Quality must meet threshold
        return quality_score >= self._quality_threshold

    # =========================================================================
    # Quality Threshold Validation
    # =========================================================================

    def xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut_3(self, quality_score: float, is_unknown: bool) -> bool:
        """Check if a face detection should be auto-enrolled.

        Args:
            quality_score: Face quality score (0-1)
            is_unknown: Whether the face is currently unknown

        Returns:
            True if the face meets auto-enrollment criteria
        """
        if not is_unknown:
            # Already matched to a known person
            return False

        # Quality must meet threshold
        return quality_score > self._quality_threshold

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    @_mutmut_mutated(mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut)
    async def is_duplicate(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_orig(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_1(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = None
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_2(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(None)
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_3(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(None).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_4(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(None))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_5(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = None
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_6(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(None)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_7(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = None

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_8(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_9(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return True, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_10(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = None
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_11(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(None, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_12(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=None)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_13(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_14(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, )
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_15(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = None
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_16(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(None)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_17(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm >= 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_18(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 1:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_19(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = None

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_20(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding * norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_21(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = None
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_22(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = +1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_23(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -2.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_24(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = ""

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_25(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is not None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_26(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = None
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_27(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(None, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_28(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=None)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_29(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_30(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, )
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_31(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = None

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_32(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(None, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_33(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, None)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_34(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_35(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, )

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_36(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity >= best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_37(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = None
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_38(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = None

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_39(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity > self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_40(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                None
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_41(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return False, best_person_id

        return False, None

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁis_duplicate__mutmut_42(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return True, None

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    @_mutmut_mutated(mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut)
    async def add_to_queue(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_orig(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_1(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = None

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_2(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(None, face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_3(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, None)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_4(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_5(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, )

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_6(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.info(
                None
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_7(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = None

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_8(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=None,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_9(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=None,
            quality_score=face_event.quality_score,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_10(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=face_event.embedding,
            quality_score=None,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_11(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
            status=None,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_12(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_13(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            quality_score=face_event.quality_score,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_14(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=face_event.embedding,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_15(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
            )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_16(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(None)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_17(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(None)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_18(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            None
        )

        return candidate

    @_mutmut_mutated(mutants_xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut)
    async def list_pending_candidates(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EnrollmentCandidate]:
        """List pending enrollment candidates.

        Args:
            session: Database session
            limit: Maximum number of candidates to return
            offset: Number of candidates to skip

        Returns:
            List of pending EnrollmentCandidate objects
        """
        stmt = (
            select(EnrollmentCandidate)
            .where(EnrollmentCandidate.status == EnrollmentStatus.PENDING.value)
            .options(selectinload(EnrollmentCandidate.face_event))
            .order_by(EnrollmentCandidate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_orig(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EnrollmentCandidate]:
        """List pending enrollment candidates.

        Args:
            session: Database session
            limit: Maximum number of candidates to return
            offset: Number of candidates to skip

        Returns:
            List of pending EnrollmentCandidate objects
        """
        stmt = (
            select(EnrollmentCandidate)
            .where(EnrollmentCandidate.status == EnrollmentStatus.PENDING.value)
            .options(selectinload(EnrollmentCandidate.face_event))
            .order_by(EnrollmentCandidate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_1(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EnrollmentCandidate]:
        """List pending enrollment candidates.

        Args:
            session: Database session
            limit: Maximum number of candidates to return
            offset: Number of candidates to skip

        Returns:
            List of pending EnrollmentCandidate objects
        """
        stmt = None

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_2(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EnrollmentCandidate]:
        """List pending enrollment candidates.

        Args:
            session: Database session
            limit: Maximum number of candidates to return
            offset: Number of candidates to skip

        Returns:
            List of pending EnrollmentCandidate objects
        """
        stmt = (
            select(EnrollmentCandidate)
            .where(EnrollmentCandidate.status == EnrollmentStatus.PENDING.value)
            .options(selectinload(EnrollmentCandidate.face_event))
            .order_by(EnrollmentCandidate.created_at.desc())
            .limit(limit)
            .offset(None)
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_3(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EnrollmentCandidate]:
        """List pending enrollment candidates.

        Args:
            session: Database session
            limit: Maximum number of candidates to return
            offset: Number of candidates to skip

        Returns:
            List of pending EnrollmentCandidate objects
        """
        stmt = (
            select(EnrollmentCandidate)
            .where(EnrollmentCandidate.status == EnrollmentStatus.PENDING.value)
            .options(selectinload(EnrollmentCandidate.face_event))
            .order_by(EnrollmentCandidate.created_at.desc())
            .limit(None)
            .offset(offset)
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_4(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EnrollmentCandidate]:
        """List pending enrollment candidates.

        Args:
            session: Database session
            limit: Maximum number of candidates to return
            offset: Number of candidates to skip

        Returns:
            List of pending EnrollmentCandidate objects
        """
        stmt = (
            select(EnrollmentCandidate)
            .where(EnrollmentCandidate.status == EnrollmentStatus.PENDING.value)
            .options(selectinload(EnrollmentCandidate.face_event))
            .order_by(None)
            .limit(limit)
            .offset(offset)
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_5(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EnrollmentCandidate]:
        """List pending enrollment candidates.

        Args:
            session: Database session
            limit: Maximum number of candidates to return
            offset: Number of candidates to skip

        Returns:
            List of pending EnrollmentCandidate objects
        """
        stmt = (
            select(EnrollmentCandidate)
            .where(EnrollmentCandidate.status == EnrollmentStatus.PENDING.value)
            .options(None)
            .order_by(EnrollmentCandidate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_6(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EnrollmentCandidate]:
        """List pending enrollment candidates.

        Args:
            session: Database session
            limit: Maximum number of candidates to return
            offset: Number of candidates to skip

        Returns:
            List of pending EnrollmentCandidate objects
        """
        stmt = (
            select(EnrollmentCandidate)
            .where(None)
            .options(selectinload(EnrollmentCandidate.face_event))
            .order_by(EnrollmentCandidate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_7(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EnrollmentCandidate]:
        """List pending enrollment candidates.

        Args:
            session: Database session
            limit: Maximum number of candidates to return
            offset: Number of candidates to skip

        Returns:
            List of pending EnrollmentCandidate objects
        """
        stmt = (
            select(None)
            .where(EnrollmentCandidate.status == EnrollmentStatus.PENDING.value)
            .options(selectinload(EnrollmentCandidate.face_event))
            .order_by(EnrollmentCandidate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_8(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EnrollmentCandidate]:
        """List pending enrollment candidates.

        Args:
            session: Database session
            limit: Maximum number of candidates to return
            offset: Number of candidates to skip

        Returns:
            List of pending EnrollmentCandidate objects
        """
        stmt = (
            select(EnrollmentCandidate)
            .where(EnrollmentCandidate.status != EnrollmentStatus.PENDING.value)
            .options(selectinload(EnrollmentCandidate.face_event))
            .order_by(EnrollmentCandidate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_9(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EnrollmentCandidate]:
        """List pending enrollment candidates.

        Args:
            session: Database session
            limit: Maximum number of candidates to return
            offset: Number of candidates to skip

        Returns:
            List of pending EnrollmentCandidate objects
        """
        stmt = (
            select(EnrollmentCandidate)
            .where(EnrollmentCandidate.status == EnrollmentStatus.PENDING.value)
            .options(selectinload(None))
            .order_by(EnrollmentCandidate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_10(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EnrollmentCandidate]:
        """List pending enrollment candidates.

        Args:
            session: Database session
            limit: Maximum number of candidates to return
            offset: Number of candidates to skip

        Returns:
            List of pending EnrollmentCandidate objects
        """
        stmt = (
            select(EnrollmentCandidate)
            .where(EnrollmentCandidate.status == EnrollmentStatus.PENDING.value)
            .options(selectinload(EnrollmentCandidate.face_event))
            .order_by(EnrollmentCandidate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = None
        return list(result.scalars().all())

    async def xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_11(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EnrollmentCandidate]:
        """List pending enrollment candidates.

        Args:
            session: Database session
            limit: Maximum number of candidates to return
            offset: Number of candidates to skip

        Returns:
            List of pending EnrollmentCandidate objects
        """
        stmt = (
            select(EnrollmentCandidate)
            .where(EnrollmentCandidate.status == EnrollmentStatus.PENDING.value)
            .options(selectinload(EnrollmentCandidate.face_event))
            .order_by(EnrollmentCandidate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await session.execute(None)
        return list(result.scalars().all())

    async def xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_12(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EnrollmentCandidate]:
        """List pending enrollment candidates.

        Args:
            session: Database session
            limit: Maximum number of candidates to return
            offset: Number of candidates to skip

        Returns:
            List of pending EnrollmentCandidate objects
        """
        stmt = (
            select(EnrollmentCandidate)
            .where(EnrollmentCandidate.status == EnrollmentStatus.PENDING.value)
            .options(selectinload(EnrollmentCandidate.face_event))
            .order_by(EnrollmentCandidate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await session.execute(stmt)
        return list(None)

    async def get_candidate(
        self,
        session: AsyncSession,
        candidate_id: int,
    ) -> EnrollmentCandidate | None:
        """Get a specific enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate

        Returns:
            EnrollmentCandidate or None if not found
        """
        stmt = (
            select(EnrollmentCandidate)
            .where(EnrollmentCandidate.id == candidate_id)
            .options(selectinload(EnrollmentCandidate.face_event))
        )

        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    @_mutmut_mutated(mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut)
    async def auto_enroll(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_orig(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_1(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = None
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_2(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            None
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_3(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(None).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_4(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(None)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_5(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like(None)
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_6(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("XXUnknown Person %XX")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_7(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("unknown person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_8(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("UNKNOWN PERSON %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_9(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = None
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_10(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(None)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_11(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = None

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_12(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() and 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_13(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 1

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_14(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = None

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_15(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count - 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_16(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 2}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_17(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = None
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_18(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=None,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_19(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=None,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_20(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=None,
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_21(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_22(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_23(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_24(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=True,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_25(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(None)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_26(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = None
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_27(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=None,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_28(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=None,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_29(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=None,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_30(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_31(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_32(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_33(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(None)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_34(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(None)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁauto_enroll__mutmut_35(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            None
        )

        return person

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    @_mutmut_mutated(mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut)
    async def process_event(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_orig(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_1(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_2(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=None,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_3(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=None,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_4(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_5(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_6(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = None

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_7(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(None, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_8(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, None)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_9(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_10(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, )

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_11(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = None
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_12(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(None, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_13(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, None)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_14(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_15(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, )
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_16(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "XXactionXX": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_17(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "ACTION": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_18(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "XXenrolledXX",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_19(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "ENROLLED",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_20(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "XXperson_idXX": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_21(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "PERSON_ID": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_22(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "XXperson_nameXX": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_23(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "PERSON_NAME": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_24(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = None
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_25(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(None, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_26(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, None)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_27(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_28(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, )
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_29(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "XXactionXX": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_30(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "ACTION": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_31(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "XXqueuedXX",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_32(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "QUEUED",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_33(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "XXcandidate_idXX": candidate.id,
                }
            return None

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁprocess_event__mutmut_34(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "CANDIDATE_ID": candidate.id,
                }
            return None

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    @_mutmut_mutated(mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut)
    async def approve_candidate(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_orig(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_1(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = None
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_2(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(None)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_3(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(None).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_4(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id != candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_5(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = None
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_6(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(None)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_7(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = None

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_8(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is not None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_9(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status == EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_10(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = None
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_11(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            None
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_12(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(None).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_13(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id != candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_14(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = None
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_15(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(None)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_16(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = None

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_17(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is not None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_18(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_19(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = None
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_20(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(None)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_21(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(None).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_22(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id != person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_23(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = None
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_24(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(None)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_25(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = None

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_26(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is not None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_27(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_28(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = None
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_29(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=None,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_30(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=None,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_31(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_32(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_33(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(None)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_34(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = None
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_35(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=None,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_36(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=None,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_37(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=None,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_38(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_39(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_40(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_41(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(None)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_42(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = None
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_43(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_44(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if (person_id) and False else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_45(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if (person_id) or True else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_46(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = None

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_47(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(None)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_48(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = None
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_49(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = None

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_50(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = True

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_51(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(None)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_52(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            None
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_53(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "XXsuccessXX": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_54(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "SUCCESS": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_55(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": False,
            "person_id": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_56(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "XXperson_idXX": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_57(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "PERSON_ID": person.id,
            "person_name": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_58(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "XXperson_nameXX": person.name,
        }

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_59(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "PERSON_NAME": person.name,
        }

    @_mutmut_mutated(mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut)
    async def reject_candidate(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_orig(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_1(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = None
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_2(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(None)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_3(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(None).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_4(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id != candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_5(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = None
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_6(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(None)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_7(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = None

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_8(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is not None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_9(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(None)
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_10(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return True

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_11(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = None
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_12(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = None
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_13(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = None

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_14(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(None)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_15(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            None
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_16(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" - (f" (reason: {reason})" if reason else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_17(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if (reason) and False else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_18(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if (reason) or True else "")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_19(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "XXXX")
        )

        return True

    async def xǁAutoEnrollmentServiceǁreject_candidate__mutmut_20(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return False

mutants_xǁAutoEnrollmentServiceǁ__init____mutmut['_mutmut_orig'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁ__init____mutmut_orig # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁ__init____mutmut['xǁAutoEnrollmentServiceǁ__init____mutmut_1'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁ__init____mutmut_1 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁ__init____mutmut['xǁAutoEnrollmentServiceǁ__init____mutmut_2'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁ__init____mutmut_2 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁ__init____mutmut['xǁAutoEnrollmentServiceǁ__init____mutmut_3'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁ__init____mutmut_3 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁ__init____mutmut['xǁAutoEnrollmentServiceǁ__init____mutmut_4'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁ__init____mutmut_4 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁ__init____mutmut['xǁAutoEnrollmentServiceǁ__init____mutmut_5'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁ__init____mutmut_5 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁ__init____mutmut['xǁAutoEnrollmentServiceǁ__init____mutmut_6'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁ__init____mutmut_6 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁ__init____mutmut['xǁAutoEnrollmentServiceǁ__init____mutmut_7'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁ__init____mutmut_7 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁ__init____mutmut['xǁAutoEnrollmentServiceǁ__init____mutmut_8'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁ__init____mutmut_8 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁ__init____mutmut['xǁAutoEnrollmentServiceǁ__init____mutmut_9'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁ__init____mutmut_9 # type: ignore # mutmut generated

mutants_xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut['_mutmut_orig'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut_orig # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut['xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut_1'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut_1 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut['xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut_2'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut_2 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut['xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut_3'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁshould_auto_enroll__mutmut_3 # type: ignore # mutmut generated

mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['_mutmut_orig'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_orig # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_1'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_1 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_2'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_2 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_3'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_3 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_4'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_4 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_5'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_5 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_6'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_6 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_7'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_7 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_8'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_8 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_9'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_9 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_10'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_10 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_11'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_11 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_12'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_12 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_13'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_13 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_14'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_14 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_15'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_15 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_16'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_16 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_17'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_17 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_18'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_18 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_19'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_19 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_20'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_20 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_21'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_21 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_22'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_22 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_23'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_23 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_24'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_24 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_25'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_25 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_26'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_26 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_27'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_27 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_28'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_28 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_29'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_29 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_30'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_30 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_31'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_31 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_32'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_32 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_33'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_33 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_34'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_34 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_35'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_35 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_36'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_36 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_37'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_37 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_38'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_38 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_39'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_39 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_40'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_40 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_41'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_41 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁis_duplicate__mutmut['xǁAutoEnrollmentServiceǁis_duplicate__mutmut_42'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁis_duplicate__mutmut_42 # type: ignore # mutmut generated

mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['_mutmut_orig'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_orig # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_1'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_1 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_2'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_2 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_3'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_3 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_4'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_4 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_5'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_5 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_6'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_6 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_7'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_7 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_8'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_8 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_9'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_9 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_10'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_10 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_11'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_11 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_12'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_12 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_13'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_13 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_14'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_14 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_15'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_15 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_16'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_16 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_17'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_17 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁadd_to_queue__mutmut['xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_18'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁadd_to_queue__mutmut_18 # type: ignore # mutmut generated

mutants_xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut['_mutmut_orig'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_orig # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut['xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_1'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_1 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut['xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_2'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_2 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut['xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_3'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_3 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut['xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_4'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_4 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut['xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_5'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_5 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut['xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_6'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_6 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut['xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_7'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_7 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut['xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_8'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_8 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut['xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_9'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_9 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut['xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_10'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_10 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut['xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_11'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_11 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut['xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_12'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁlist_pending_candidates__mutmut_12 # type: ignore # mutmut generated

mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['_mutmut_orig'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_orig # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_1'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_1 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_2'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_2 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_3'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_3 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_4'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_4 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_5'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_5 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_6'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_6 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_7'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_7 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_8'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_8 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_9'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_9 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_10'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_10 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_11'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_11 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_12'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_12 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_13'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_13 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_14'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_14 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_15'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_15 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_16'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_16 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_17'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_17 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_18'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_18 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_19'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_19 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_20'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_20 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_21'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_21 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_22'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_22 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_23'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_23 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_24'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_24 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_25'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_25 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_26'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_26 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_27'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_27 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_28'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_28 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_29'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_29 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_30'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_30 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_31'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_31 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_32'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_32 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_33'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_33 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_34'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_34 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁauto_enroll__mutmut['xǁAutoEnrollmentServiceǁauto_enroll__mutmut_35'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁauto_enroll__mutmut_35 # type: ignore # mutmut generated

mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['_mutmut_orig'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_orig # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_1'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_1 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_2'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_2 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_3'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_3 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_4'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_4 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_5'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_5 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_6'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_6 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_7'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_7 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_8'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_8 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_9'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_9 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_10'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_10 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_11'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_11 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_12'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_12 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_13'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_13 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_14'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_14 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_15'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_15 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_16'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_16 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_17'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_17 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_18'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_18 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_19'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_19 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_20'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_20 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_21'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_21 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_22'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_22 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_23'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_23 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_24'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_24 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_25'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_25 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_26'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_26 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_27'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_27 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_28'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_28 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_29'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_29 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_30'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_30 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_31'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_31 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_32'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_32 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_33'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_33 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁprocess_event__mutmut['xǁAutoEnrollmentServiceǁprocess_event__mutmut_34'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁprocess_event__mutmut_34 # type: ignore # mutmut generated

mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['_mutmut_orig'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_orig # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_1'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_1 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_2'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_2 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_3'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_3 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_4'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_4 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_5'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_5 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_6'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_6 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_7'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_7 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_8'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_8 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_9'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_9 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_10'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_10 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_11'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_11 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_12'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_12 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_13'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_13 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_14'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_14 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_15'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_15 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_16'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_16 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_17'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_17 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_18'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_18 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_19'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_19 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_20'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_20 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_21'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_21 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_22'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_22 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_23'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_23 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_24'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_24 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_25'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_25 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_26'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_26 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_27'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_27 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_28'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_28 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_29'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_29 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_30'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_30 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_31'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_31 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_32'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_32 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_33'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_33 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_34'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_34 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_35'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_35 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_36'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_36 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_37'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_37 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_38'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_38 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_39'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_39 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_40'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_40 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_41'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_41 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_42'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_42 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_43'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_43 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_44'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_44 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_45'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_45 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_46'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_46 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_47'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_47 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_48'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_48 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_49'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_49 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_50'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_50 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_51'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_51 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_52'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_52 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_53'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_53 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_54'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_54 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_55'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_55 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_56'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_56 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_57'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_57 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_58'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_58 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁapprove_candidate__mutmut['xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_59'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁapprove_candidate__mutmut_59 # type: ignore # mutmut generated

mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['_mutmut_orig'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_orig # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_1'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_1 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_2'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_2 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_3'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_3 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_4'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_4 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_5'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_5 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_6'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_6 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_7'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_7 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_8'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_8 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_9'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_9 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_10'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_10 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_11'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_11 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_12'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_12 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_13'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_13 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_14'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_14 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_15'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_15 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_16'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_16 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_17'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_17 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_18'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_18 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_19'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_19 # type: ignore # mutmut generated
mutants_xǁAutoEnrollmentServiceǁreject_candidate__mutmut['xǁAutoEnrollmentServiceǁreject_candidate__mutmut_20'] = AutoEnrollmentService.xǁAutoEnrollmentServiceǁreject_candidate__mutmut_20 # type: ignore # mutmut generated


# =============================================================================
# Global Service Instance (Singleton Pattern)
# =============================================================================

_auto_enrollment_service: AutoEnrollmentService | None = None
mutants_x_get_auto_enrollment_service__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_get_auto_enrollment_service__mutmut)
def get_auto_enrollment_service() -> AutoEnrollmentService:
    """Get or create the global AutoEnrollmentService instance.

    Returns:
        Global AutoEnrollmentService instance
    """
    global _auto_enrollment_service  # noqa: PLW0603
    if _auto_enrollment_service is None:
        _auto_enrollment_service = AutoEnrollmentService()
    return _auto_enrollment_service


def x_get_auto_enrollment_service__mutmut_orig() -> AutoEnrollmentService:
    """Get or create the global AutoEnrollmentService instance.

    Returns:
        Global AutoEnrollmentService instance
    """
    global _auto_enrollment_service  # noqa: PLW0603
    if _auto_enrollment_service is None:
        _auto_enrollment_service = AutoEnrollmentService()
    return _auto_enrollment_service


def x_get_auto_enrollment_service__mutmut_1() -> AutoEnrollmentService:
    """Get or create the global AutoEnrollmentService instance.

    Returns:
        Global AutoEnrollmentService instance
    """
    global _auto_enrollment_service  # noqa: PLW0603
    if _auto_enrollment_service is not None:
        _auto_enrollment_service = AutoEnrollmentService()
    return _auto_enrollment_service


def x_get_auto_enrollment_service__mutmut_2() -> AutoEnrollmentService:
    """Get or create the global AutoEnrollmentService instance.

    Returns:
        Global AutoEnrollmentService instance
    """
    global _auto_enrollment_service  # noqa: PLW0603
    if _auto_enrollment_service is None:
        _auto_enrollment_service = None
    return _auto_enrollment_service

mutants_x_get_auto_enrollment_service__mutmut['_mutmut_orig'] = x_get_auto_enrollment_service__mutmut_orig # type: ignore # mutmut generated
mutants_x_get_auto_enrollment_service__mutmut['x_get_auto_enrollment_service__mutmut_1'] = x_get_auto_enrollment_service__mutmut_1 # type: ignore # mutmut generated
mutants_x_get_auto_enrollment_service__mutmut['x_get_auto_enrollment_service__mutmut_2'] = x_get_auto_enrollment_service__mutmut_2 # type: ignore # mutmut generated
mutants_x_reset_auto_enrollment_service__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_reset_auto_enrollment_service__mutmut)
def reset_auto_enrollment_service() -> None:
    """Reset the global AutoEnrollmentService instance (for testing)."""
    global _auto_enrollment_service  # noqa: PLW0603
    _auto_enrollment_service = None


def x_reset_auto_enrollment_service__mutmut_orig() -> None:
    """Reset the global AutoEnrollmentService instance (for testing)."""
    global _auto_enrollment_service  # noqa: PLW0603
    _auto_enrollment_service = None


def x_reset_auto_enrollment_service__mutmut_1() -> None:
    """Reset the global AutoEnrollmentService instance (for testing)."""
    global _auto_enrollment_service  # noqa: PLW0603
    _auto_enrollment_service = ""

mutants_x_reset_auto_enrollment_service__mutmut['_mutmut_orig'] = x_reset_auto_enrollment_service__mutmut_orig # type: ignore # mutmut generated
mutants_x_reset_auto_enrollment_service__mutmut['x_reset_auto_enrollment_service__mutmut_1'] = x_reset_auto_enrollment_service__mutmut_1 # type: ignore # mutmut generated
