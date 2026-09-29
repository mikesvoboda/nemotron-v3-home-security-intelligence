"""AI service wrapper classes for dependency injection (NEM-2030).

This module provides service wrapper classes that encapsulate AI detection
functionality and can be registered in the DI container.

These wrappers delegate to the underlying detection functions while providing:
- Clean interface for dependency injection
- Model lifecycle management
- Testability via mock injection

Example:
    # Via DI container
    face_detector = container.get("face_detector_service")
    faces = await face_detector.detect_faces(person_detections, images)

    # For testing with mock
    container.override("face_detector_service", MockFaceDetectorService())
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

    from backend.services.face_detector import FaceDetection, PersonDetection
    from backend.services.ocr_service import PlateText
    from backend.services.plate_detector import PlateDetection, VehicleDetection

logger = get_logger(__name__)


class FaceDetectorService:
    """Service wrapper for face detection functionality.

    This class wraps the face_detector module functions and provides
    a clean interface for dependency injection.

    The service does not manage model lifecycle - models are expected
    to be passed in when calling detection methods, or the service
    can be configured with a default model.

    Attributes:
        model: Optional default YOLO face detection model
    """

    def __init__(self, model: Any = None) -> None:
        """Initialize FaceDetectorService.

        Args:
            model: Optional default YOLO face detection model.
                   If not provided, must be passed to detect_faces().
        """
        self.model = model
        logger.debug("FaceDetectorService initialized")

    async def detect_faces(
        self,
        person_detections: list[PersonDetection],
        images: dict[str, PILImage] | None = None,
        confidence_threshold: float = 0.3,
        head_ratio: float = 0.4,
        padding: float = 0.2,
        model: Any = None,
    ) -> list[FaceDetection]:
        """Detect faces in person regions.

        Delegates to the face_detector.detect_faces() function.

        Args:
            person_detections: List of person detections to process
            images: Optional dict mapping file_path -> PIL Image for caching
            confidence_threshold: Minimum confidence for face detections
            head_ratio: Fraction of person bbox height for head region
            padding: Padding ratio to add around head bbox
            model: Optional model override (uses self.model if not provided)

        Returns:
            List of FaceDetection objects for detected faces
        """
        from backend.services.face_detector import detect_faces

        detection_model = model if model is not None else self.model

        return await detect_faces(
            model=detection_model,
            person_detections=person_detections,
            images=images,
            confidence_threshold=confidence_threshold,
            head_ratio=head_ratio,
            padding=padding,
        )


class PlateDetectorService:
    """Service wrapper for license plate detection functionality.

    This class wraps the plate_detector module functions and provides
    a clean interface for dependency injection.

    Attributes:
        model: Optional default YOLO plate detection model
    """

    def __init__(self, model: Any = None) -> None:
        """Initialize PlateDetectorService.

        Args:
            model: Optional default YOLO plate detection model.
                   If not provided, must be passed to detect_plates().
        """
        self.model = model
        logger.debug("PlateDetectorService initialized")

    async def detect_plates(
        self,
        vehicle_detections: list[VehicleDetection],
        images: dict[str, PILImage] | None = None,
        confidence_threshold: float = 0.25,
        padding: float = 0.1,
        model: Any = None,
    ) -> list[PlateDetection]:
        """Detect license plates in vehicle regions.

        Delegates to the plate_detector.detect_plates() function.

        Args:
            vehicle_detections: List of vehicle detections to process
            images: Optional dict mapping file_path -> PIL Image for caching
            confidence_threshold: Minimum confidence for plate detections
            padding: Padding ratio to add around vehicle bbox
            model: Optional model override (uses self.model if not provided)

        Returns:
            List of PlateDetection objects for detected plates
        """
        from backend.services.plate_detector import detect_plates

        detection_model = model if model is not None else self.model

        return await detect_plates(
            model=detection_model,
            vehicle_detections=vehicle_detections,
            images=images,
            confidence_threshold=confidence_threshold,
            padding=padding,
        )


class OCRService:
    """Service wrapper for OCR (license plate text recognition) functionality.

    This class wraps the ocr_service module functions and provides
    a clean interface for dependency injection.

    Attributes:
        model: Optional default PaddleOCR model
    """

    def __init__(self, model: Any = None) -> None:
        """Initialize OCRService.

        Args:
            model: Optional default PaddleOCR model.
                   If not provided, must be passed to read_plates().
        """
        self.model = model
        logger.debug("OCRService initialized")

    async def read_plates(
        self,
        plate_detections: list[PlateDetection],
        images: dict[str, PILImage] | None = None,
        image_paths: list[str] | None = None,
        min_confidence: float = 0.5,
        model: Any = None,
    ) -> list[PlateText]:
        """Read text from detected license plates using OCR.

        Delegates to the ocr_service.read_plates() function.

        Args:
            plate_detections: List of plate detections with bounding boxes
            images: Optional dict mapping file_path -> PIL Image for caching
            image_paths: Optional list of image paths corresponding to detections
            min_confidence: Minimum OCR confidence to include result
            model: Optional model override (uses self.model if not provided)

        Returns:
            List of PlateText objects with recognized text
        """
        from backend.services.ocr_service import read_plates

        ocr_model = model if model is not None else self.model

        return await read_plates(
            ocr_model=ocr_model,
            plate_detections=plate_detections,
            images=images,
            image_paths=image_paths,
            min_confidence=min_confidence,
        )

    async def read_single_plate(
        self,
        plate_image: PILImage,
        min_confidence: float = 0.5,
        model: Any = None,
    ) -> PlateText | None:
        """Read text from a single plate image.

        Delegates to the ocr_service.read_single_plate() function.

        Args:
            plate_image: Pre-cropped PIL Image of the license plate
            min_confidence: Minimum OCR confidence to return result
            model: Optional model override (uses self.model if not provided)

        Returns:
            PlateText object if text was recognized, None otherwise
        """
        from backend.services.ocr_service import read_single_plate

        ocr_model = model if model is not None else self.model

        return await read_single_plate(
            ocr_model=ocr_model,
            plate_image=plate_image,
            min_confidence=min_confidence,
        )
