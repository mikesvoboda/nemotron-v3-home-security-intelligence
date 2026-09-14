"""Tests for batch inference utilities (NEM-3372).

These tests verify the batch_utils module for efficient multi-image processing.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch
from PIL import Image


class TestBatchConfig:
    """Tests for BatchConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        from batch_utils import BatchConfig

        config = BatchConfig()

        assert config.batch_size == 8
        assert config.max_batch_size == 32
        assert config.pad_to_same_size is True
        assert config.target_size is None
        assert config.fill_value == 128

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        from batch_utils import BatchConfig

        config = BatchConfig(
            batch_size=16,
            max_batch_size=64,
            pad_to_same_size=False,
            target_size=(640, 480),
            fill_value=0,
        )

        assert config.batch_size == 16
        assert config.max_batch_size == 64
        assert config.pad_to_same_size is False
        assert config.target_size == (640, 480)
        assert config.fill_value == 0

    def test_invalid_batch_size_raises(self) -> None:
        """Test that invalid batch size raises ValueError."""
        from batch_utils import BatchConfig

        with pytest.raises(ValueError, match="batch_size must be >= 1"):
            BatchConfig(batch_size=0)

    def test_batch_size_clamped_to_max(self) -> None:
        """Test that batch_size is clamped to max_batch_size."""
        from batch_utils import BatchConfig

        config = BatchConfig(batch_size=100, max_batch_size=32)
        assert config.batch_size == 32


class TestChunkList:
    """Tests for chunk_list function."""

    def test_even_chunks(self) -> None:
        """Test chunking with even division."""
        from batch_utils import chunk_list

        items = [1, 2, 3, 4, 5, 6]
        chunks = list(chunk_list(items, 2))

        assert len(chunks) == 3
        assert chunks[0] == [1, 2]
        assert chunks[1] == [3, 4]
        assert chunks[2] == [5, 6]

    def test_uneven_chunks(self) -> None:
        """Test chunking with uneven division."""
        from batch_utils import chunk_list

        items = [1, 2, 3, 4, 5]
        chunks = list(chunk_list(items, 2))

        assert len(chunks) == 3
        assert chunks[0] == [1, 2]
        assert chunks[1] == [3, 4]
        assert chunks[2] == [5]

    def test_single_chunk(self) -> None:
        """Test when all items fit in one chunk."""
        from batch_utils import chunk_list

        items = [1, 2, 3]
        chunks = list(chunk_list(items, 10))

        assert len(chunks) == 1
        assert chunks[0] == [1, 2, 3]


class TestGetImageSize:
    """Tests for get_image_size function."""

    def test_pil_image(self) -> None:
        """Test with PIL Image."""
        from batch_utils import get_image_size

        image = Image.new("RGB", (640, 480))
        width, height = get_image_size(image)

        assert width == 640
        assert height == 480

    def test_numpy_array(self) -> None:
        """Test with numpy array (H, W, C format)."""
        from batch_utils import get_image_size

        array = np.zeros((480, 640, 3), dtype=np.uint8)
        width, height = get_image_size(array)

        assert width == 640
        assert height == 480


class TestComputeBatchTargetSize:
    """Tests for compute_batch_target_size function."""

    def test_fixed_size(self) -> None:
        """Test with fixed target size."""
        from batch_utils import compute_batch_target_size

        images = [Image.new("RGB", (100, 100)), Image.new("RGB", (200, 200))]
        result = compute_batch_target_size(images, fixed_size=(640, 480))

        assert result == (640, 480)

    def test_max_dimensions(self) -> None:
        """Test computing max dimensions from images."""
        from batch_utils import compute_batch_target_size

        images = [
            Image.new("RGB", (100, 200)),
            Image.new("RGB", (300, 150)),
            Image.new("RGB", (200, 250)),
        ]
        result = compute_batch_target_size(images)

        # Max width = 300, max height = 250
        assert result == (300, 250)

    def test_empty_list_raises(self) -> None:
        """Test that empty list raises ValueError."""
        from batch_utils import compute_batch_target_size

        with pytest.raises(ValueError, match="Cannot compute target size for empty"):
            compute_batch_target_size([])


class TestPadImage:
    """Tests for pad_image function."""

    def test_pad_smaller_image(self) -> None:
        """Test padding a smaller image."""
        from batch_utils import pad_image

        image = Image.new("RGB", (100, 100), color=(255, 0, 0))
        padded, original_size = pad_image(image, target_size=(200, 200), fill_value=128)

        assert padded.size == (200, 200)
        assert original_size == (100, 100)

    def test_same_size_no_change(self) -> None:
        """Test that same-size image is unchanged."""
        from batch_utils import pad_image

        image = Image.new("RGB", (200, 200))
        padded, original_size = pad_image(image, target_size=(200, 200))

        assert padded.size == (200, 200)
        assert original_size == (200, 200)

    def test_numpy_input(self) -> None:
        """Test with numpy array input."""
        from batch_utils import pad_image

        array = np.zeros((100, 100, 3), dtype=np.uint8)
        padded, original_size = pad_image(array, target_size=(200, 200))

        assert isinstance(padded, Image.Image)
        assert padded.size == (200, 200)
        assert original_size == (100, 100)


class TestPadImagesToBatch:
    """Tests for pad_images_to_batch function."""

    def test_pad_multiple_images(self) -> None:
        """Test padding multiple images to same size."""
        from batch_utils import pad_images_to_batch

        images = [
            Image.new("RGB", (100, 100)),
            Image.new("RGB", (200, 150)),
            Image.new("RGB", (150, 200)),
        ]
        padded, original_sizes = pad_images_to_batch(images)

        # All images should have same size (max dimensions)
        assert all(img.size == (200, 200) for img in padded)
        assert original_sizes == [(100, 100), (200, 150), (150, 200)]

    def test_empty_list(self) -> None:
        """Test with empty list."""
        from batch_utils import pad_images_to_batch

        padded, original_sizes = pad_images_to_batch([])
        assert padded == []
        assert original_sizes == []


class TestUnpadResult:
    """Tests for unpad_result function."""

    def test_adjust_bbox_dict(self) -> None:
        """Test adjusting bounding box in dict format."""
        from batch_utils import unpad_result

        result = {"bbox": {"x": 100, "y": 100, "width": 50, "height": 50}}
        adjusted = unpad_result(result, original_size=(200, 200), padded_size=(300, 300))

        # Padding offset should be (300-200)/2 = 50
        assert adjusted["bbox"]["x"] == 50
        assert adjusted["bbox"]["y"] == 50

    def test_adjust_bbox_list(self) -> None:
        """Test adjusting bounding box in list format."""
        from batch_utils import unpad_result

        result = {"bbox": [100, 100, 150, 150]}  # [x1, y1, x2, y2]
        adjusted = unpad_result(result, original_size=(200, 200), padded_size=(300, 300))

        # Padding offset should be 50
        assert adjusted["bbox"] == [50, 50, 100, 100]

    def test_no_bbox_unchanged(self) -> None:
        """Test that result without bbox is unchanged."""
        from batch_utils import unpad_result

        result = {"score": 0.95, "class": "person"}
        adjusted = unpad_result(result, original_size=(200, 200), padded_size=(300, 300))

        assert adjusted == result


class TestBatchProcessor:
    """Tests for BatchProcessor class."""

    def test_process_empty_batch(self) -> None:
        """Test processing empty batch."""
        from batch_utils import BatchProcessor

        processor = BatchProcessor(batch_size=4)

        def inference_fn(images: list[Image.Image]) -> list[str]:
            return ["result"] * len(images)

        result = processor.process_batch([], inference_fn)

        assert result.results == []
        assert result.batch_count == 0
        assert result.total_items == 0

    def test_process_single_batch(self) -> None:
        """Test processing a single batch."""
        from batch_utils import BatchProcessor

        processor = BatchProcessor(batch_size=4)
        images = [Image.new("RGB", (100, 100)) for _ in range(3)]

        def inference_fn(imgs: list[Image.Image]) -> list[str]:
            return [f"result_{i}" for i in range(len(imgs))]

        result = processor.process_batch(images, inference_fn, pad_images=False)

        assert len(result.results) == 3
        assert result.batch_count == 1
        assert result.total_items == 3

    def test_process_multiple_batches(self) -> None:
        """Test processing multiple batches."""
        from batch_utils import BatchProcessor

        processor = BatchProcessor(batch_size=2)
        images = [Image.new("RGB", (100, 100)) for _ in range(5)]

        def inference_fn(imgs: list[Image.Image]) -> list[str]:
            return [f"result_{i}" for i in range(len(imgs))]

        result = processor.process_batch(images, inference_fn, pad_images=False)

        assert len(result.results) == 5
        assert result.batch_count == 3  # 2 + 2 + 1
        assert result.total_items == 5

    def test_process_with_padding(self) -> None:
        """Test processing with image padding."""
        from batch_utils import BatchProcessor

        processor = BatchProcessor(batch_size=4)
        images = [
            Image.new("RGB", (100, 100)),
            Image.new("RGB", (200, 150)),
        ]

        def inference_fn(imgs: list[Image.Image]) -> list[dict]:
            # Check all images are padded to same size
            sizes = [img.size for img in imgs]
            assert len(set(sizes)) == 1  # All same size
            return [{"class": "person", "bbox": [0, 0, 10, 10]}] * len(imgs)

        result = processor.process_batch(images, inference_fn, pad_images=True)

        assert len(result.results) == 2


class TestCreateBatchInferenceFn:
    """Tests for create_batch_inference_fn function."""

    def test_creates_callable(self) -> None:
        """Test that it creates a callable function."""
        from batch_utils import create_batch_inference_fn

        # Create mock model and processor
        model = torch.nn.Linear(10, 5)

        class MockProcessor:
            def __call__(self, images: list, **_kwargs: object) -> dict[str, torch.Tensor]:
                return {"pixel_values": torch.randn(len(images), 3, 224, 224)}

        processor = MockProcessor()
        inference_fn = create_batch_inference_fn(model, processor, device="cpu")

        assert callable(inference_fn)

    def test_handles_empty_input(self) -> None:
        """Test handling empty input."""
        from batch_utils import create_batch_inference_fn

        model = torch.nn.Linear(10, 5)

        class MockProcessor:
            def __call__(self, images: list, **_kwargs: object) -> dict[str, torch.Tensor]:
                return {"pixel_values": torch.randn(len(images), 3, 224, 224)}

        processor = MockProcessor()
        inference_fn = create_batch_inference_fn(model, processor, device="cpu")

        result = inference_fn([])
        assert result == []
