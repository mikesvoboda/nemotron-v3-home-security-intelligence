"""Unit tests for privacy masking service (NEM-3912).

Tests for:
- Privacy masking using segmentation masks
- Various masking strategies (blur, solid color, pixelate)
- Mask inversion for background removal
- Integration with detection results
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image


class TestPrivacyMaskingServiceImport:
    """Test that PrivacyMaskingService can be imported."""

    def test_import_service(self):
        """Test that the service can be imported."""
        from backend.services.privacy_masking_service import PrivacyMaskingService

        assert PrivacyMaskingService is not None

    def test_import_masking_strategy(self):
        """Test that MaskingStrategy enum can be imported."""
        from backend.services.privacy_masking_service import MaskingStrategy

        assert MaskingStrategy is not None
        assert hasattr(MaskingStrategy, "BLUR")
        assert hasattr(MaskingStrategy, "SOLID")
        assert hasattr(MaskingStrategy, "PIXELATE")


class TestPrivacyMaskingServiceInitialization:
    """Test service initialization."""

    def test_default_initialization(self):
        """Test initialization with default parameters."""
        from backend.services.privacy_masking_service import (
            MaskingStrategy,
            PrivacyMaskingService,
        )

        service = PrivacyMaskingService()
        assert service.default_strategy == MaskingStrategy.BLUR
        assert service.blur_radius == 25
        assert service.pixelate_size == 10

    def test_custom_initialization(self):
        """Test initialization with custom parameters."""
        from backend.services.privacy_masking_service import (
            MaskingStrategy,
            PrivacyMaskingService,
        )

        service = PrivacyMaskingService(
            default_strategy=MaskingStrategy.PIXELATE,
            blur_radius=50,
            pixelate_size=20,
        )
        assert service.default_strategy == MaskingStrategy.PIXELATE
        assert service.blur_radius == 50
        assert service.pixelate_size == 20


class TestMaskApplication:
    """Test mask application to images."""

    @pytest.fixture
    def service(self):
        """Create privacy masking service instance."""
        from backend.services.privacy_masking_service import PrivacyMaskingService

        return PrivacyMaskingService()

    @pytest.fixture
    def test_image(self):
        """Create a test image."""
        return Image.new("RGB", (640, 480), color=(255, 0, 0))  # Red image

    @pytest.fixture
    def test_mask(self):
        """Create a test binary mask."""
        mask = np.zeros((480, 640), dtype=np.uint8)
        mask[100:300, 200:400] = 255  # Rectangle in the center
        return mask

    def test_apply_blur_mask(self, service, test_image, test_mask):
        """Test applying blur mask to an image."""
        from backend.services.privacy_masking_service import MaskingStrategy

        result = service.apply_mask(
            image=test_image,
            mask=test_mask,
            strategy=MaskingStrategy.BLUR,
        )

        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.size == test_image.size

    def test_apply_solid_mask(self, service, test_image, test_mask):
        """Test applying solid color mask to an image."""
        from backend.services.privacy_masking_service import MaskingStrategy

        result = service.apply_mask(
            image=test_image,
            mask=test_mask,
            strategy=MaskingStrategy.SOLID,
            fill_color=(0, 0, 0),  # Black
        )

        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.size == test_image.size

        # Check that the masked area is black
        result_array = np.array(result)
        masked_region = result_array[100:300, 200:400]
        assert np.all(masked_region == 0)

    def test_apply_pixelate_mask(self, service, test_image, test_mask):
        """Test applying pixelation mask to an image."""
        from backend.services.privacy_masking_service import MaskingStrategy

        result = service.apply_mask(
            image=test_image,
            mask=test_mask,
            strategy=MaskingStrategy.PIXELATE,
        )

        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.size == test_image.size

    def test_apply_default_strategy(self, service, test_image, test_mask):
        """Test applying mask with default strategy."""
        result = service.apply_mask(
            image=test_image,
            mask=test_mask,
        )

        assert result is not None
        assert isinstance(result, Image.Image)

    def test_empty_mask(self, service, test_image):
        """Test applying empty mask (no masked regions)."""
        empty_mask = np.zeros((480, 640), dtype=np.uint8)

        result = service.apply_mask(
            image=test_image,
            mask=empty_mask,
        )

        # Result should be identical to input when mask is empty
        assert result is not None
        assert result.size == test_image.size

    def test_full_mask(self, service, test_image):
        """Test applying full mask (entire image masked)."""
        from backend.services.privacy_masking_service import MaskingStrategy

        full_mask = np.ones((480, 640), dtype=np.uint8) * 255

        result = service.apply_mask(
            image=test_image,
            mask=full_mask,
            strategy=MaskingStrategy.SOLID,
            fill_color=(0, 0, 0),
        )

        assert result is not None
        # Entire image should be black
        result_array = np.array(result)
        assert np.all(result_array == 0)


class TestMaskInversion:
    """Test mask inversion for background removal."""

    @pytest.fixture
    def service(self):
        """Create privacy masking service instance."""
        from backend.services.privacy_masking_service import PrivacyMaskingService

        return PrivacyMaskingService()

    def test_invert_mask(self, service):
        """Test inverting a binary mask."""
        # Create mask with some foreground
        original_mask = np.zeros((100, 100), dtype=np.uint8)
        original_mask[25:75, 25:75] = 255

        inverted = service.invert_mask(original_mask)

        # Check inversion
        assert np.array_equal(inverted[25:75, 25:75], np.zeros((50, 50), dtype=np.uint8))
        assert np.all(inverted[0:25, 0:25] == 255)

    def test_apply_inverted_mask(self, service):
        """Test applying mask to background instead of foreground."""
        from backend.services.privacy_masking_service import MaskingStrategy

        image = Image.new("RGB", (100, 100), color=(255, 0, 0))  # Red
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[25:75, 25:75] = 255  # Center square is foreground

        # Mask the background (invert mask)
        result = service.apply_mask(
            image=image,
            mask=mask,
            strategy=MaskingStrategy.SOLID,
            fill_color=(0, 0, 0),
            invert=True,  # Mask background, keep foreground
        )

        assert result is not None
        result_array = np.array(result)

        # Background should be black (0, 0, 0)
        assert np.all(result_array[0:25, 0:25] == 0)
        # Foreground (center) should remain red
        assert np.all(result_array[25:75, 25:75, 0] == 255)


class TestRLEMaskDecoding:
    """Test decoding RLE masks from detection results."""

    @pytest.fixture
    def service(self):
        """Create privacy masking service instance."""
        from backend.services.privacy_masking_service import PrivacyMaskingService

        return PrivacyMaskingService()

    def test_decode_rle_mask(self, service):
        """Test decoding RLE-encoded mask."""
        # Create a simple RLE encoding for a 10x10 mask
        # First 50 zeros, then 20 ones, then 30 zeros = 100 pixels
        rle = {
            "counts": [50, 20, 30],
            "size": [10, 10],
        }

        mask = service.decode_rle_mask(rle)

        assert mask is not None
        assert mask.shape == (10, 10)
        # Check that ones are in the right place
        assert mask.sum() == 20

    def test_decode_empty_rle(self, service):
        """Test decoding RLE for empty mask."""
        rle = {
            "counts": [100],  # All zeros
            "size": [10, 10],
        }

        mask = service.decode_rle_mask(rle)

        assert mask is not None
        assert mask.shape == (10, 10)
        assert mask.sum() == 0


class TestBatchMasking:
    """Test batch processing of multiple detections."""

    @pytest.fixture
    def service(self):
        """Create privacy masking service instance."""
        from backend.services.privacy_masking_service import PrivacyMaskingService

        return PrivacyMaskingService()

    def test_combine_masks(self, service):
        """Test combining multiple masks into one."""
        masks = [
            np.zeros((100, 100), dtype=np.uint8),
            np.zeros((100, 100), dtype=np.uint8),
        ]
        masks[0][10:30, 10:30] = 255  # First mask
        masks[1][40:60, 40:60] = 255  # Second mask

        combined = service.combine_masks(masks)

        assert combined.shape == (100, 100)
        assert combined[20, 20] == 255  # From first mask
        assert combined[50, 50] == 255  # From second mask
        assert combined[70, 70] == 0  # Unmasked area

    def test_mask_detections(self, service):
        """Test masking multiple detections at once."""
        from backend.services.privacy_masking_service import MaskingStrategy

        image = Image.new("RGB", (640, 480), color=(255, 255, 255))

        # Simulate detection results with mask data
        detections = [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": {"x": 100, "y": 100, "width": 100, "height": 200},
                "mask_rle": {"counts": [0, 100 * 200], "size": [200, 100]},
            },
            {
                "class": "car",
                "confidence": 0.88,
                "bbox": {"x": 300, "y": 200, "width": 150, "height": 100},
                "mask_rle": {"counts": [0, 150 * 100], "size": [100, 150]},
            },
        ]

        result = service.mask_detections(
            image=image,
            detections=detections,
            strategy=MaskingStrategy.BLUR,
        )

        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.size == image.size


class TestFilteredMasking:
    """Test masking with class filtering."""

    @pytest.fixture
    def service(self):
        """Create privacy masking service instance."""
        from backend.services.privacy_masking_service import PrivacyMaskingService

        return PrivacyMaskingService()

    def test_mask_only_persons(self, service):
        """Test masking only person detections."""
        from backend.services.privacy_masking_service import MaskingStrategy

        image = Image.new("RGB", (640, 480), color=(255, 255, 255))

        detections = [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": {"x": 100, "y": 100, "width": 100, "height": 200},
                "mask_rle": {"counts": [0, 100 * 200], "size": [200, 100]},
            },
            {
                "class": "car",
                "confidence": 0.88,
                "bbox": {"x": 300, "y": 200, "width": 150, "height": 100},
                "mask_rle": {"counts": [0, 150 * 100], "size": [100, 150]},
            },
        ]

        result = service.mask_detections(
            image=image,
            detections=detections,
            strategy=MaskingStrategy.BLUR,
            class_filter=["person"],
        )

        assert result is not None
        assert isinstance(result, Image.Image)


class TestMaskForReID:
    """Test mask generation for Re-ID improvement."""

    @pytest.fixture
    def service(self):
        """Create privacy masking service instance."""
        from backend.services.privacy_masking_service import PrivacyMaskingService

        return PrivacyMaskingService()

    def test_extract_foreground_for_reid(self, service):
        """Test extracting only foreground (person) for Re-ID embedding."""
        image = Image.new("RGB", (640, 480), color=(200, 200, 200))  # Gray background

        # Create a person mask
        person_mask = np.zeros((480, 640), dtype=np.uint8)
        person_mask[100:400, 200:400] = 255

        # Extract foreground with transparent background
        result = service.extract_foreground(
            image=image,
            mask=person_mask,
            background_color=(0, 0, 0),  # Black background
        )

        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.size == image.size

        # Check that background is black
        result_array = np.array(result)
        assert np.all(result_array[0:100, 0:200] == 0)

    def test_crop_masked_region(self, service):
        """Test cropping just the masked region for Re-ID."""
        image = Image.new("RGB", (640, 480), color=(128, 128, 128))

        # Create a person mask
        person_mask = np.zeros((480, 640), dtype=np.uint8)
        person_mask[100:300, 200:400] = 255

        # Crop just the masked region
        cropped = service.crop_masked_region(
            image=image,
            mask=person_mask,
            padding=0,
        )

        assert cropped is not None
        assert isinstance(cropped, Image.Image)
        # Should be cropped to the mask bounds
        assert cropped.size == (200, 200)  # 400-200, 300-100

    def test_crop_masked_region_with_padding(self, service):
        """Test cropping with padding around the mask."""
        image = Image.new("RGB", (640, 480), color=(128, 128, 128))

        person_mask = np.zeros((480, 640), dtype=np.uint8)
        person_mask[100:300, 200:400] = 255

        cropped = service.crop_masked_region(
            image=image,
            mask=person_mask,
            padding=10,
        )

        assert cropped is not None
        # Should include padding
        assert cropped.size == (220, 220)  # (400-200)+20, (300-100)+20


class TestGlobalServiceInstance:
    """Test global service instance management."""

    def test_get_privacy_masking_service(self):
        """Test getting the global service instance."""
        from backend.services.privacy_masking_service import get_privacy_masking_service

        service1 = get_privacy_masking_service()
        service2 = get_privacy_masking_service()

        assert service1 is service2

    def test_reset_privacy_masking_service(self):
        """Test resetting the global service instance."""
        from backend.services.privacy_masking_service import (
            get_privacy_masking_service,
            reset_privacy_masking_service,
        )

        service1 = get_privacy_masking_service()
        reset_privacy_masking_service()
        service2 = get_privacy_masking_service()

        assert service1 is not service2
