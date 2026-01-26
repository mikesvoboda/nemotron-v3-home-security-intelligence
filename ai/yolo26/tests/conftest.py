"""Pytest configuration and fixtures for YOLO26 tests."""

import base64
import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

# Add the ai/yolo26 directory to sys.path to enable imports
# This handles both pytest from project root and running tests directly
_yolo26_dir = Path(__file__).parent.parent
if str(_yolo26_dir) not in sys.path:
    sys.path.insert(0, str(_yolo26_dir))


@pytest.fixture
def dummy_image():
    """Create a dummy PIL image for testing."""
    img_array = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    return Image.fromarray(img_array)


@pytest.fixture
def dummy_image_bytes(dummy_image):
    """Create dummy image bytes for testing."""
    img_bytes = io.BytesIO()
    dummy_image.save(img_bytes, format="JPEG")
    img_bytes.seek(0)
    return img_bytes.getvalue()


@pytest.fixture
def dummy_image_base64(dummy_image_bytes):
    """Create base64-encoded dummy image for testing."""
    return base64.b64encode(dummy_image_bytes).decode("utf-8")


@pytest.fixture
def mock_yolo_model():
    """Create a mock YOLO model for testing."""
    mock_model = MagicMock()

    # Mock predict method to return results
    mock_result = MagicMock()
    mock_boxes = MagicMock()

    # Mock a single detection (person)
    mock_box = MagicMock()
    mock_box.cls.item.return_value = 0  # person class
    mock_box.conf.item.return_value = 0.95  # high confidence
    # Mock xyxy to return a list that has a tolist() method (like a tensor)
    mock_xyxy_tensor = MagicMock()
    mock_xyxy_tensor.tolist.return_value = [100.0, 150.0, 300.0, 550.0]
    mock_box.xyxy = [mock_xyxy_tensor]  # x1, y1, x2, y2

    mock_boxes.__len__.return_value = 1
    mock_boxes.__iter__.return_value = iter([mock_box])

    mock_result.boxes = mock_boxes
    mock_model.predict.return_value = [mock_result]

    return mock_model


@pytest.fixture
def mock_empty_yolo_model():
    """Create a mock YOLO model that returns no detections."""
    mock_model = MagicMock()

    mock_result = MagicMock()
    mock_boxes = MagicMock()
    mock_boxes.__len__.return_value = 0
    mock_boxes.__iter__.return_value = iter([])

    mock_result.boxes = mock_boxes
    mock_model.predict.return_value = [mock_result]

    return mock_model
