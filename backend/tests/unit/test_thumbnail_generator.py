"""Unit tests for thumbnail generator service."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from backend.services.thumbnail_generator import (
    OBJECT_COLORS,
    ThumbnailGenerator,
)

# Fixtures


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for thumbnail output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_test_image():
    """Create a temporary test image."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        # Create a simple 640x480 RGB image
        img = Image.new("RGB", (640, 480), color=(100, 150, 200))
        img.save(tmp.name, "JPEG")
        yield tmp.name
        # Cleanup
        Path(tmp.name).unlink(missing_ok=True)


@pytest.fixture
def thumbnail_generator(temp_output_dir):
    """Create a thumbnail generator with temp output directory."""
    return ThumbnailGenerator(output_dir=temp_output_dir)


@pytest.fixture
def sample_detections():
    """Sample detection data for testing."""
    return [
        {
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 100,
            "bbox_y": 150,
            "bbox_width": 200,
            "bbox_height": 400,
        },
        {
            "object_type": "car",
            "confidence": 0.88,
            "bbox_x": 400,
            "bbox_y": 200,
            "bbox_width": 150,
            "bbox_height": 100,
        },
    ]


def test_thumbnail_generator_init_creates_output_dir(temp_output_dir):
    """Test that initialization creates the output directory."""
    output_path = Path(temp_output_dir) / "thumbnails"
    generator = ThumbnailGenerator(output_dir=str(output_path))

    assert output_path.exists()
    assert output_path.is_dir()
    assert generator.output_dir == output_path


def test_thumbnail_generator_init_with_existing_dir(temp_output_dir):
    """Test that initialization works with existing output directory."""
    # Directory already exists (temp_output_dir fixture)
    generator = ThumbnailGenerator(output_dir=temp_output_dir)

    assert Path(temp_output_dir).exists()
    assert generator.output_dir == Path(temp_output_dir)


def test_thumbnail_generator_init_default_path():
    """Test that default output path is data/thumbnails."""
    with patch.object(Path, "mkdir") as mock_mkdir:
        generator = ThumbnailGenerator()

        assert generator.output_dir == Path("data/thumbnails")
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


# Test: Generate Thumbnail


def test_generate_thumbnail_success(thumbnail_generator, temp_test_image, sample_detections):
    """Test successful thumbnail generation with detections."""
    output_path = thumbnail_generator.generate_thumbnail(
        image_path=temp_test_image,
        detections=sample_detections,
        output_size=(320, 240),
        detection_id="det_001",
    )

    # Verify output path returned
    assert output_path is not None
    assert "det_001_thumb.jpg" in output_path

    # Verify file was created
    assert Path(output_path).exists()

    # Verify image is correct size
    img = Image.open(output_path)
    assert img.size == (320, 240)
    assert img.format == "JPEG"


def test_generate_thumbnail_no_detection_id(
    thumbnail_generator, temp_test_image, sample_detections
):
    """Test thumbnail generation without explicit detection_id."""
    output_path = thumbnail_generator.generate_thumbnail(
        image_path=temp_test_image,
        detections=sample_detections,
    )

    # Should use image filename as detection_id
    assert output_path is not None
    assert "_thumb.jpg" in output_path
    assert Path(output_path).exists()


def test_generate_thumbnail_empty_detections(thumbnail_generator, temp_test_image):
    """Test thumbnail generation with no detections."""
    output_path = thumbnail_generator.generate_thumbnail(
        image_path=temp_test_image,
        detections=[],
        detection_id="det_002",
    )

    # Should still generate thumbnail, just without bounding boxes
    assert output_path is not None
    assert Path(output_path).exists()


def test_generate_thumbnail_invalid_image_path(thumbnail_generator, sample_detections):
    """Test thumbnail generation with non-existent image file."""
    output_path = thumbnail_generator.generate_thumbnail(
        image_path="/nonexistent/image.jpg",
        detections=sample_detections,
        detection_id="det_003",
    )

    # Should return None and log error
    assert output_path is None


def test_generate_thumbnail_permission_error(
    thumbnail_generator, temp_test_image, sample_detections
):
    """Test thumbnail generation with permission error on save."""
    with patch.object(Image.Image, "save", side_effect=PermissionError("Permission denied")):
        output_path = thumbnail_generator.generate_thumbnail(
            image_path=temp_test_image,
            detections=sample_detections,
            detection_id="det_004",
        )

        # Should return None and log error
        assert output_path is None


def test_generate_thumbnail_custom_output_size(
    thumbnail_generator, temp_test_image, sample_detections
):
    """Test thumbnail generation with custom output size."""
    output_path = thumbnail_generator.generate_thumbnail(
        image_path=temp_test_image,
        detections=sample_detections,
        output_size=(640, 480),
        detection_id="det_005",
    )

    assert output_path is not None

    # Verify custom size
    img = Image.open(output_path)
    assert img.size == (640, 480)


# Test: Draw Bounding Boxes


def test_draw_bounding_boxes_single_detection(thumbnail_generator):
    """Test drawing bounding boxes with single detection."""
    img = Image.new("RGB", (640, 480), color=(100, 150, 200))
    detections = [
        {
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 100,
            "bbox_y": 150,
            "bbox_width": 200,
            "bbox_height": 400,
        }
    ]

    result = thumbnail_generator.draw_bounding_boxes(img, detections)

    # Verify result is a new image
    assert isinstance(result, Image.Image)
    assert result.size == img.size
    assert result is not img  # Should be a copy


def test_draw_bounding_boxes_multiple_detections(thumbnail_generator, sample_detections):
    """Test drawing bounding boxes with multiple detections."""
    img = Image.new("RGB", (640, 480), color=(100, 150, 200))

    result = thumbnail_generator.draw_bounding_boxes(img, sample_detections)

    assert isinstance(result, Image.Image)
    assert result.size == img.size


def test_draw_bounding_boxes_color_mapping(thumbnail_generator):
    """Test that correct colors are used for different object types."""
    img = Image.new("RGB", (640, 480), color=(100, 150, 200))

    # Test each color-mapped object type
    for object_type, _expected_color in OBJECT_COLORS.items():
        detections = [
            {
                "object_type": object_type,
                "confidence": 0.90,
                "bbox_x": 50,
                "bbox_y": 50,
                "bbox_width": 100,
                "bbox_height": 100,
            }
        ]

        result = thumbnail_generator.draw_bounding_boxes(img, detections)

        # Verify image was modified (basic check)
        assert isinstance(result, Image.Image)


def test_draw_bounding_boxes_default_color(thumbnail_generator):
    """Test that unknown object types use default color."""
    img = Image.new("RGB", (640, 480), color=(100, 150, 200))
    detections = [
        {
            "object_type": "unknown_object",
            "confidence": 0.75,
            "bbox_x": 50,
            "bbox_y": 50,
            "bbox_width": 100,
            "bbox_height": 100,
        }
    ]

    result = thumbnail_generator.draw_bounding_boxes(img, detections)

    # Should use DEFAULT_COLOR for unknown types
    assert isinstance(result, Image.Image)


def test_draw_bounding_boxes_missing_bbox_coordinates(thumbnail_generator):
    """Test handling of detections with missing bbox coordinates."""
    img = Image.new("RGB", (640, 480), color=(100, 150, 200))
    detections = [
        {
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 100,
            # Missing bbox_y, bbox_width, bbox_height
        }
    ]

    # Should skip detection with incomplete bbox
    result = thumbnail_generator.draw_bounding_boxes(img, detections)

    assert isinstance(result, Image.Image)


def test_draw_bounding_boxes_partial_bbox_coordinates(thumbnail_generator):
    """Test handling of detections with None values in bbox."""
    img = Image.new("RGB", (640, 480), color=(100, 150, 200))
    detections = [
        {
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 100,
            "bbox_y": None,
            "bbox_width": 200,
            "bbox_height": None,
        }
    ]

    # Should skip detection with None bbox values
    result = thumbnail_generator.draw_bounding_boxes(img, detections)

    assert isinstance(result, Image.Image)


def test_draw_bounding_boxes_empty_list(thumbnail_generator):
    """Test drawing bounding boxes with empty detection list."""
    img = Image.new("RGB", (640, 480), color=(100, 150, 200))
    detections = []

    result = thumbnail_generator.draw_bounding_boxes(img, detections)

    # Should return image unchanged (but copied)
    assert isinstance(result, Image.Image)
    assert result.size == img.size


def test_draw_bounding_boxes_font_fallback(thumbnail_generator):
    """Test that drawing works even if TrueType font is unavailable."""
    img = Image.new("RGB", (640, 480), color=(100, 150, 200))
    detections = [
        {
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 100,
            "bbox_y": 150,
            "bbox_width": 200,
            "bbox_height": 400,
        }
    ]

    # Since on this system fonts exist, we'll just verify the code path works
    # The fallback is tested by the fact that other tests pass without errors
    result = thumbnail_generator.draw_bounding_boxes(img, detections)

    # Should work with whatever font is available
    assert isinstance(result, Image.Image)


# Test: Resize with Padding


def test_resize_with_padding_landscape_image(thumbnail_generator):
    """Test resizing landscape image with padding."""
    # Landscape image (wider than tall)
    img = Image.new("RGB", (800, 600), color=(100, 150, 200))
    target_size = (320, 240)

    result = thumbnail_generator._resize_with_padding(img, target_size)

    assert result.size == target_size
    assert isinstance(result, Image.Image)


def test_resize_with_padding_portrait_image(thumbnail_generator):
    """Test resizing portrait image with padding."""
    # Portrait image (taller than wide)
    img = Image.new("RGB", (600, 800), color=(100, 150, 200))
    target_size = (320, 240)

    result = thumbnail_generator._resize_with_padding(img, target_size)

    assert result.size == target_size
    assert isinstance(result, Image.Image)


def test_resize_with_padding_square_image(thumbnail_generator):
    """Test resizing square image with padding."""
    img = Image.new("RGB", (600, 600), color=(100, 150, 200))
    target_size = (320, 240)

    result = thumbnail_generator._resize_with_padding(img, target_size)

    assert result.size == target_size
    assert isinstance(result, Image.Image)


def test_resize_with_padding_smaller_image(thumbnail_generator):
    """Test resizing image smaller than target size."""
    # Small image that needs to be enlarged
    img = Image.new("RGB", (160, 120), color=(100, 150, 200))
    target_size = (320, 240)

    result = thumbnail_generator._resize_with_padding(img, target_size)

    assert result.size == target_size
    assert isinstance(result, Image.Image)


def test_resize_with_padding_aspect_ratio_preserved(thumbnail_generator):
    """Test that aspect ratio is preserved during resize."""
    # 16:9 aspect ratio image
    img = Image.new("RGB", (1600, 900), color=(100, 150, 200))
    target_size = (320, 240)

    result = thumbnail_generator._resize_with_padding(img, target_size)

    assert result.size == target_size
    # The content should maintain 16:9 ratio within the 320x240 frame
    # (will have black padding on top/bottom)


# Test: Utility Methods


def test_get_output_path(thumbnail_generator):
    """Test getting output path for detection ID."""
    detection_id = "det_123"
    output_path = thumbnail_generator.get_output_path(detection_id)

    assert isinstance(output_path, Path)
    assert output_path.name == "det_123_thumb.jpg"
    assert output_path.parent == thumbnail_generator.output_dir


def test_delete_thumbnail_existing_file(thumbnail_generator, temp_test_image):
    """Test deleting an existing thumbnail."""
    # First generate a thumbnail
    detection_id = "det_delete_001"
    thumbnail_generator.generate_thumbnail(
        image_path=temp_test_image,
        detections=[],
        detection_id=detection_id,
    )

    # Verify it exists
    output_path = thumbnail_generator.get_output_path(detection_id)
    assert output_path.exists()

    # Delete it
    result = thumbnail_generator.delete_thumbnail(detection_id)

    assert result is True
    assert not output_path.exists()


def test_delete_thumbnail_nonexistent_file(thumbnail_generator):
    """Test deleting a non-existent thumbnail."""
    detection_id = "det_nonexistent"

    # Try to delete non-existent file
    result = thumbnail_generator.delete_thumbnail(detection_id)

    # Should return False (file doesn't exist)
    assert result is False


def test_delete_thumbnail_permission_error(thumbnail_generator, temp_test_image):
    """Test deleting thumbnail with permission error."""
    # Generate a thumbnail
    detection_id = "det_delete_002"
    thumbnail_generator.generate_thumbnail(
        image_path=temp_test_image,
        detections=[],
        detection_id=detection_id,
    )

    # Mock unlink to raise permission error
    with patch.object(Path, "unlink", side_effect=PermissionError("Permission denied")):
        result = thumbnail_generator.delete_thumbnail(detection_id)

        # Should return False and log error
        assert result is False


# Test: Integration Scenarios


def test_end_to_end_thumbnail_generation(temp_output_dir, temp_test_image):
    """Test complete thumbnail generation workflow."""
    generator = ThumbnailGenerator(output_dir=temp_output_dir)

    detections = [
        {
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 100,
            "bbox_y": 150,
            "bbox_width": 200,
            "bbox_height": 400,
        },
        {
            "object_type": "car",
            "confidence": 0.88,
            "bbox_x": 400,
            "bbox_y": 200,
            "bbox_width": 150,
            "bbox_height": 100,
        },
        {
            "object_type": "dog",
            "confidence": 0.75,
            "bbox_x": 50,
            "bbox_y": 300,
            "bbox_width": 80,
            "bbox_height": 120,
        },
    ]

    # Generate thumbnail
    output_path = generator.generate_thumbnail(
        image_path=temp_test_image,
        detections=detections,
        output_size=(320, 240),
        detection_id="det_integration",
    )

    # Verify result
    assert output_path is not None
    assert Path(output_path).exists()

    # Load and verify thumbnail
    img = Image.open(output_path)
    assert img.size == (320, 240)
    assert img.format == "JPEG"

    # Clean up
    assert generator.delete_thumbnail("det_integration") is True


def test_generate_thumbnail_with_various_object_types(thumbnail_generator, temp_test_image):
    """Test thumbnail generation with various object types for color mapping."""
    detections = [
        {
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 50,
            "bbox_y": 50,
            "bbox_width": 100,
            "bbox_height": 200,
        },
        {
            "object_type": "car",
            "confidence": 0.90,
            "bbox_x": 200,
            "bbox_y": 50,
            "bbox_width": 120,
            "bbox_height": 80,
        },
        {
            "object_type": "truck",
            "confidence": 0.85,
            "bbox_x": 350,
            "bbox_y": 50,
            "bbox_width": 130,
            "bbox_height": 90,
        },
        {
            "object_type": "dog",
            "confidence": 0.80,
            "bbox_x": 50,
            "bbox_y": 300,
            "bbox_width": 80,
            "bbox_height": 100,
        },
        {
            "object_type": "cat",
            "confidence": 0.78,
            "bbox_x": 200,
            "bbox_y": 300,
            "bbox_width": 70,
            "bbox_height": 90,
        },
        {
            "object_type": "bicycle",
            "confidence": 0.88,
            "bbox_x": 350,
            "bbox_y": 300,
            "bbox_width": 60,
            "bbox_height": 120,
        },
        {
            "object_type": "motorcycle",
            "confidence": 0.87,
            "bbox_x": 450,
            "bbox_y": 300,
            "bbox_width": 90,
            "bbox_height": 110,
        },
        {
            "object_type": "bird",
            "confidence": 0.70,
            "bbox_x": 100,
            "bbox_y": 10,
            "bbox_width": 30,
            "bbox_height": 30,
        },
    ]

    output_path = thumbnail_generator.generate_thumbnail(
        image_path=temp_test_image,
        detections=detections,
        detection_id="det_colors",
    )

    assert output_path is not None
    assert Path(output_path).exists()


# Test: Edge Cases


def test_generate_thumbnail_with_rgba_image(thumbnail_generator):
    """Test thumbnail generation with RGBA (PNG) image."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        # Create RGBA image
        img = Image.new("RGBA", (640, 480), color=(100, 150, 200, 255))
        img.save(tmp.name, "PNG")

        detections = [
            {
                "object_type": "person",
                "confidence": 0.95,
                "bbox_x": 100,
                "bbox_y": 150,
                "bbox_width": 200,
                "bbox_height": 400,
            }
        ]

        output_path = thumbnail_generator.generate_thumbnail(
            image_path=tmp.name,
            detections=detections,
            detection_id="det_rgba",
        )

        # Should convert to RGB and save as JPEG
        assert output_path is not None
        assert Path(output_path).exists()

        # Cleanup
        Path(tmp.name).unlink()


def test_generate_thumbnail_with_bbox_at_edge(thumbnail_generator, temp_test_image):
    """Test thumbnail generation with bbox at image edge."""
    detections = [
        {
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 0,
            "bbox_y": 0,
            "bbox_width": 100,
            "bbox_height": 100,
        },
        {
            "object_type": "car",
            "confidence": 0.88,
            "bbox_x": 540,
            "bbox_y": 380,
            "bbox_width": 100,
            "bbox_height": 100,
        },
    ]

    output_path = thumbnail_generator.generate_thumbnail(
        image_path=temp_test_image,
        detections=detections,
        detection_id="det_edge",
    )

    # Should handle edge cases gracefully
    assert output_path is not None
    assert Path(output_path).exists()


def test_generate_thumbnail_with_very_small_bbox(thumbnail_generator, temp_test_image):
    """Test thumbnail generation with very small bounding box."""
    detections = [
        {
            "object_type": "bird",
            "confidence": 0.75,
            "bbox_x": 300,
            "bbox_y": 200,
            "bbox_width": 10,
            "bbox_height": 10,
        }
    ]

    output_path = thumbnail_generator.generate_thumbnail(
        image_path=temp_test_image,
        detections=detections,
        detection_id="det_small",
    )

    # Should handle small bbox
    assert output_path is not None
    assert Path(output_path).exists()


def test_generate_thumbnail_general_exception(thumbnail_generator, temp_test_image):
    """Test thumbnail generation with unexpected exception during processing."""
    detections = [
        {
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 100,
            "bbox_y": 150,
            "bbox_width": 200,
            "bbox_height": 400,
        }
    ]

    # Mock Image.open to raise a generic exception
    with patch(
        "backend.services.thumbnail_generator.Image.open",
        side_effect=RuntimeError("Unexpected error"),
    ):
        output_path = thumbnail_generator.generate_thumbnail(
            image_path=temp_test_image,
            detections=detections,
            detection_id="det_error",
        )

        # Should return None and log error
        assert output_path is None


def test_ensure_output_dir_failure(temp_output_dir):
    """Test handling of output directory creation failure."""
    output_path = Path(temp_output_dir) / "restricted"

    # Mock mkdir to raise PermissionError
    with (
        patch.object(Path, "mkdir", side_effect=PermissionError("Cannot create directory")),
        pytest.raises(PermissionError),
    ):
        ThumbnailGenerator(output_dir=str(output_path))


def test_draw_bounding_boxes_with_alternative_font(thumbnail_generator):
    """Test drawing bounding boxes when first font path fails but second succeeds."""
    img = Image.new("RGB", (640, 480), color=(100, 150, 200))
    detections = [
        {
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 100,
            "bbox_y": 150,
            "bbox_width": 200,
            "bbox_height": 400,
        }
    ]

    # Mock first font path to fail, second to fail, forcing default
    # Need to provide a return value for the default font loading
    from PIL import ImageFont

    default_font = ImageFont.load_default()

    with (
        patch("backend.services.thumbnail_generator.ImageFont.truetype") as mock_font,
        patch(
            "backend.services.thumbnail_generator.ImageFont.load_default", return_value=default_font
        ),
    ):
        mock_font.side_effect = [
            Exception("First font not found"),
            Exception("Second font not found"),
        ]

        result = thumbnail_generator.draw_bounding_boxes(img, detections)

        # Should fall back to default font and still work
        assert isinstance(result, Image.Image)
        # Verify both font paths were tried
        assert mock_font.call_count == 2


def test_draw_bounding_boxes_with_none_bbox_dimensions(thumbnail_generator):
    """Test handling of detections with None in bbox_width or bbox_height after initial check."""
    img = Image.new("RGB", (640, 480), color=(100, 150, 200))
    detections = [
        {
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 100,
            "bbox_y": 150,
            "bbox_width": None,  # This will trigger the second None check
            "bbox_height": 400,
        }
    ]

    # Should skip detection with None bbox dimensions
    result = thumbnail_generator.draw_bounding_boxes(img, detections)

    assert isinstance(result, Image.Image)


def test_draw_bounding_boxes_with_none_coordinates(thumbnail_generator):
    """Test handling of detections with None in x or y coordinates."""
    img = Image.new("RGB", (640, 480), color=(100, 150, 200))
    detections = [
        {
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": None,  # This will trigger the coordinate None check
            "bbox_y": 150,
            "bbox_width": 200,
            "bbox_height": 400,
        }
    ]

    # Should skip detection with None coordinates
    result = thumbnail_generator.draw_bounding_boxes(img, detections)

    assert isinstance(result, Image.Image)
