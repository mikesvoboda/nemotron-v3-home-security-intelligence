"""InsightFace-based Face Recognition Model.

This module provides the FaceRecognizer class for face detection and recognition
using InsightFace's FaceAnalysis module with ArcFace embeddings.

Features:
- Face detection in security camera frames
- 512-dimensional ArcFace embedding generation
- Face quality assessment for recognition reliability
- Cosine similarity matching against known persons

Reference:
- Model: InsightFace buffalo_l (RetinaFace + ArcFace)
- Paper: ArcFace: Additive Angular Margin Loss for Deep Face Recognition
- GitHub: https://github.com/deepinsight/insightface

VRAM Usage: ~1.5GB (buffalo_l model)

Implements NEM-3716: Face detection with InsightFace
Implements NEM-3717: Face quality assessment for recognition
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ArcFace embedding dimension (fixed by the model architecture)
EMBEDDING_DIMENSION = 512

# Default similarity threshold for face matching
# Higher values reduce false positives but may miss legitimate matches
DEFAULT_MATCH_THRESHOLD = 0.68

# Minimum face quality score for reliable recognition
# Below this threshold, recognition results may be unreliable
MIN_QUALITY_THRESHOLD = 0.3

# Quality score thresholds for categorization
QUALITY_LOW = 0.3
QUALITY_MEDIUM = 0.5
QUALITY_HIGH = 0.7


@dataclass
class FaceResult:
    """Result from face detection and embedding extraction.

    Attributes:
        bbox: Bounding box [x1, y1, x2, y2] in pixel coordinates
        embedding: 512-dimensional normalized ArcFace embedding
        embedding_hash: SHA-256 hash prefix for quick lookup
        quality_score: Face quality score (0-1), higher is better
        detection_score: Face detection confidence (0-1)
        age: Estimated age (optional, if demographics model loaded)
        gender: Estimated gender 'M' or 'F' (optional)
        landmark_5: 5-point facial landmarks (optional)
    """

    bbox: list[float]
    embedding: list[float]
    embedding_hash: str
    quality_score: float
    detection_score: float
    age: int | None = None
    gender: str | None = None
    landmark_5: list[list[float]] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "bbox": self.bbox,
            "embedding": self.embedding,
            "embedding_hash": self.embedding_hash,
            "quality_score": self.quality_score,
            "detection_score": self.detection_score,
            "age": self.age,
            "gender": self.gender,
            "landmark_5": self.landmark_5,
        }


@dataclass
class MatchResult:
    """Result from face matching against known persons.

    Attributes:
        matched: Whether a match was found above threshold
        person_id: ID of matched person (None if no match)
        person_name: Name of matched person (None if no match)
        similarity: Cosine similarity score (-1 to 1)
        is_unknown: True if face is unknown (no match found)
    """

    matched: bool
    person_id: int | None
    person_name: str | None
    similarity: float
    is_unknown: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "matched": self.matched,
            "person_id": self.person_id,
            "person_name": self.person_name,
            "similarity": self.similarity,
            "is_unknown": self.is_unknown,
        }


class FaceRecognizer:
    """InsightFace-based face detection and recognition model.

    This model uses InsightFace's FaceAnalysis module to detect faces,
    extract 512-dimensional ArcFace embeddings, and assess face quality
    for reliable recognition in security camera footage.

    The quality assessment considers:
    - Face size (larger faces are more reliable)
    - Face pose (frontal faces are more reliable)
    - Detection confidence
    - Image blur/sharpness

    Example usage:
        >>> recognizer = FaceRecognizer(model_name='buffalo_l')
        >>> recognizer.load_model()
        >>> faces = recognizer.detect_faces(frame)
        >>> for face in faces:
        ...     print(f"Face at {face.bbox}, quality: {face.quality_score:.2f}")
        ...     if face.quality_score > 0.5:
        ...         match = recognizer.match_face(face.embedding, known_embeddings)
        ...         if match.matched:
        ...             print(f"Matched: {match.person_name}")

    Attributes:
        model_name: InsightFace model name (buffalo_l, buffalo_s, etc.)
        device: Device to run inference on (cuda:0, cpu)
        det_size: Detection input size (default 640x640)
    """

    def __init__(
        self,
        model_name: str = "buffalo_l",
        device: str = "cuda:0",
        det_size: tuple[int, int] = (640, 640),
    ):
        """Initialize face recognizer.

        Args:
            model_name: InsightFace model name. Options:
                - buffalo_l: Large model, highest accuracy (~1.5GB VRAM)
                - buffalo_s: Small model, faster but less accurate (~500MB VRAM)
                - buffalo_sc: Small model for CPU
            device: Device to run inference on (default: "cuda:0")
            det_size: Face detection input size (default: (640, 640))
        """
        self.model_name = model_name
        self.device = device
        self.det_size = det_size
        self.app: Any = None

        logger.info(f"Initializing FaceRecognizer with model={model_name}, device={device}")

    def load_model(self) -> FaceRecognizer:
        """Load the InsightFace model into memory.

        Returns:
            Self for method chaining.

        Raises:
            ImportError: If insightface is not installed.
            RuntimeError: If model loading fails.
        """
        try:
            from insightface.app import FaceAnalysis
        except ImportError as e:
            raise ImportError(
                "InsightFace is required for face recognition. "
                "Install with: pip install insightface>=0.7.3"
            ) from e

        logger.info(f"Loading InsightFace model: {self.model_name}")

        # Determine context ID (GPU index or -1 for CPU)
        if "cuda" in self.device:
            try:
                ctx_id = int(self.device.split(":")[1])
            except (IndexError, ValueError):
                ctx_id = 0
        else:
            ctx_id = -1

        # Initialize FaceAnalysis with detection and recognition models
        self.app = FaceAnalysis(
            name=self.model_name,
            providers=["CUDAExecutionProvider" if ctx_id >= 0 else "CPUExecutionProvider"],
        )

        # Prepare model with detection size
        self.app.prepare(ctx_id=ctx_id, det_size=self.det_size)

        logger.info(
            f"FaceRecognizer loaded on {'GPU' if ctx_id >= 0 else 'CPU'} "
            f"(ctx_id={ctx_id}, det_size={self.det_size})"
        )

        return self

    def detect_faces(
        self,
        frame: np.ndarray | Image.Image,
        max_faces: int = 10,
    ) -> list[FaceResult]:
        """Detect faces in a frame and extract embeddings.

        Args:
            frame: Input image as numpy array (BGR) or PIL Image (RGB).
            max_faces: Maximum number of faces to detect.

        Returns:
            List of FaceResult objects for each detected face.

        Raises:
            RuntimeError: If model is not loaded.
        """
        if self.app is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        # Convert PIL Image to numpy array if needed
        if isinstance(frame, Image.Image):
            frame = np.array(frame)
            # Convert RGB to BGR for InsightFace
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                frame = frame[:, :, ::-1]

        # Run face detection
        faces = self.app.get(frame, max_num=max_faces)

        results = []
        for face in faces:
            # Extract bounding box
            bbox = face.bbox.tolist()

            # Extract embedding (512-dim ArcFace)
            embedding = face.embedding
            if embedding is None:
                logger.warning("Face detected but no embedding extracted")
                continue

            # Normalize embedding
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            # Calculate quality score
            quality_score = self._assess_quality(face, frame.shape)

            # Generate embedding hash for quick lookup
            embedding_hash = hashlib.sha256(embedding.tobytes()).hexdigest()[:16]

            # Extract optional attributes
            age = int(face.age) if hasattr(face, "age") and face.age is not None else None
            gender = face.gender if hasattr(face, "gender") else None
            if gender is not None:
                gender = "M" if gender == 1 else "F"

            landmark_5 = (
                face.kps.tolist() if hasattr(face, "kps") and face.kps is not None else None
            )

            results.append(
                FaceResult(
                    bbox=bbox,
                    embedding=embedding.tolist(),
                    embedding_hash=embedding_hash,
                    quality_score=quality_score,
                    detection_score=float(face.det_score),
                    age=age,
                    gender=gender,
                    landmark_5=landmark_5,
                )
            )

        logger.debug(f"Detected {len(results)} faces in frame")
        return results

    def get_embedding(
        self,
        face_crop: np.ndarray | Image.Image,
    ) -> np.ndarray | None:
        """Extract embedding from a pre-cropped face image.

        Args:
            face_crop: Cropped face image (should be aligned if possible).

        Returns:
            512-dimensional normalized embedding, or None if extraction fails.
        """
        if self.app is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        # Convert PIL Image to numpy array if needed
        if isinstance(face_crop, Image.Image):
            face_crop = np.array(face_crop)
            if len(face_crop.shape) == 3 and face_crop.shape[2] == 3:
                face_crop = face_crop[:, :, ::-1]

        # Detect face in crop and get embedding
        faces = self.app.get(face_crop, max_num=1)

        if not faces or faces[0].embedding is None:
            logger.warning("Could not extract embedding from face crop")
            return None

        embedding = faces[0].embedding
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding  # type: ignore[no-any-return]

    def _assess_quality(self, face: Any, frame_shape: tuple[int, ...]) -> float:
        """Assess face quality for recognition reliability.

        Quality factors:
        1. Detection confidence (higher is better)
        2. Face size relative to frame (larger is better)
        3. Face pose/alignment (frontal is better)
        4. Landmark visibility (all landmarks visible is better)

        Args:
            face: InsightFace face object with detection info.
            frame_shape: Shape of the input frame (H, W, C).

        Returns:
            Quality score between 0 and 1.
        """
        scores = []

        # 1. Detection confidence (0-1)
        det_score = float(face.det_score) if hasattr(face, "det_score") else 0.5
        scores.append(det_score)

        # 2. Face size score (larger faces are more reliable)
        bbox = face.bbox
        face_width = bbox[2] - bbox[0]
        face_height = bbox[3] - bbox[1]
        face_area = face_width * face_height
        frame_area = frame_shape[0] * frame_shape[1]

        # Ideal face area is 5-20% of frame
        area_ratio = face_area / frame_area
        if area_ratio > 0.20:
            size_score = 1.0
        elif area_ratio > 0.05:
            size_score = 0.8 + (area_ratio - 0.05) / 0.15 * 0.2
        elif area_ratio > 0.01:
            size_score = 0.4 + (area_ratio - 0.01) / 0.04 * 0.4
        else:
            size_score = area_ratio / 0.01 * 0.4

        scores.append(size_score)

        # 3. Face pose score (based on landmark positions if available)
        if hasattr(face, "kps") and face.kps is not None:
            kps = face.kps  # 5-point landmarks
            # Check symmetry of eyes (indices 0 and 1)
            if len(kps) >= 2:
                left_eye = kps[0]
                right_eye = kps[1]
                eye_center_x = (left_eye[0] + right_eye[0]) / 2
                face_center_x = (bbox[0] + bbox[2]) / 2
                # Calculate horizontal alignment
                alignment = 1.0 - min(abs(eye_center_x - face_center_x) / face_width, 1.0)
                scores.append(alignment * 0.8 + 0.2)  # Scale to 0.2-1.0
            else:
                scores.append(0.5)
        else:
            scores.append(0.5)

        # 4. Aspect ratio score (normal face aspect ratio is ~0.7-0.85)
        aspect_ratio = face_width / max(face_height, 1)
        if 0.7 <= aspect_ratio <= 0.85:
            aspect_score = 1.0
        elif 0.5 <= aspect_ratio <= 1.0:
            # Distance from ideal range
            if aspect_ratio < 0.7:
                aspect_score = 0.7 + (aspect_ratio - 0.5) / 0.2 * 0.3
            else:
                aspect_score = 0.7 + (1.0 - aspect_ratio) / 0.15 * 0.3
        else:
            aspect_score = 0.3

        scores.append(aspect_score)

        # Weighted average of all scores
        weights = [0.3, 0.3, 0.25, 0.15]
        quality = sum(s * w for s, w in zip(scores, weights, strict=False))

        return min(max(quality, 0.0), 1.0)

    @staticmethod
    def compute_similarity(emb1: list[float], emb2: list[float]) -> float:
        """Compute cosine similarity between two embeddings.

        Since embeddings are already L2 normalized, cosine similarity
        is simply the dot product.

        Args:
            emb1: First embedding vector (512-dim).
            emb2: Second embedding vector (512-dim).

        Returns:
            Cosine similarity in range [-1, 1]. Higher values indicate
            more similar faces.
        """
        a = np.array(emb1)
        b = np.array(emb2)

        # Normalize for robustness (embeddings should already be normalized)
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)

        if a_norm == 0 or b_norm == 0:
            return 0.0

        return float(np.dot(a, b) / (a_norm * b_norm))

    def match_face(
        self,
        embedding: list[float],
        known_embeddings: dict[int, tuple[str, list[float]]],
        threshold: float = DEFAULT_MATCH_THRESHOLD,
    ) -> MatchResult:
        """Match a face embedding against known persons.

        Args:
            embedding: 512-dim embedding of the face to match.
            known_embeddings: Dict mapping person_id to (name, embedding).
            threshold: Minimum similarity for a match (default: 0.68).

        Returns:
            MatchResult with match details.
        """
        if not known_embeddings:
            return MatchResult(
                matched=False,
                person_id=None,
                person_name=None,
                similarity=0.0,
                is_unknown=True,
            )

        best_match_id = None
        best_match_name = None
        best_similarity = -1.0

        for person_id, (name, known_emb) in known_embeddings.items():
            similarity = self.compute_similarity(embedding, known_emb)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match_id = person_id
                best_match_name = name

        if best_similarity >= threshold:
            logger.debug(
                f"Face matched to {best_match_name} (id={best_match_id}) "
                f"with similarity {best_similarity:.3f}"
            )
            return MatchResult(
                matched=True,
                person_id=best_match_id,
                person_name=best_match_name,
                similarity=best_similarity,
                is_unknown=False,
            )
        else:
            logger.debug(
                f"No match found (best similarity: {best_similarity:.3f}, threshold: {threshold})"
            )
            return MatchResult(
                matched=False,
                person_id=None,
                person_name=None,
                similarity=best_similarity,
                is_unknown=True,
            )

    def unload(self) -> None:
        """Unload the model from memory.

        Useful for freeing VRAM when the model is no longer needed.
        """
        if self.app is not None:
            del self.app
            self.app = None

            # Try to free GPU memory
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

            logger.info("FaceRecognizer model unloaded")


def load_face_recognizer(
    model_name: str = "buffalo_l",
    device: str = "cuda:0",
) -> FaceRecognizer:
    """Factory function for model registry.

    Creates and loads a FaceRecognizer model. This function is intended
    to be used with the OnDemandModelManager.

    Args:
        model_name: InsightFace model name.
        device: Device to run inference on.

    Returns:
        Loaded FaceRecognizer model instance.
    """
    recognizer = FaceRecognizer(model_name=model_name, device=device)
    recognizer.load_model()
    return recognizer
