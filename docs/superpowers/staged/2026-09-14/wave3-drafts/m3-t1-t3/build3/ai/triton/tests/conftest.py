"""Pytest fixtures for Triton client tests."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

from ai.triton.client import TritonConfig, TritonProtocol


@pytest.fixture
def triton_config() -> TritonConfig:
    """Create a test Triton configuration."""
    return TritonConfig(
        enabled=True,
        grpc_url="localhost:8001",
        http_url="localhost:8000",
        protocol=TritonProtocol.GRPC,
        timeout=60.0,
        default_model="yolo26",
        max_retries=3,
        retry_delay=0.1,  # Fast retries for tests
        verbose=False,
        confidence_threshold=0.5,
    )


@pytest.fixture
def triton_config_disabled() -> TritonConfig:
    """Create a disabled Triton configuration."""
    return TritonConfig(
        enabled=False,
        grpc_url="localhost:8001",
        http_url="localhost:8000",
    )


@pytest.fixture
def sample_image_bytes() -> bytes:
    """Create sample image bytes for testing."""
    import io

    from PIL import Image

    # Create a simple RGB test image
    img = Image.new("RGB", (640, 480), color=(128, 128, 128))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def sample_image_array() -> np.ndarray:
    """Create sample image numpy array for testing."""
    return np.random.randint(0, 255, size=(480, 640, 3), dtype=np.uint8)


@pytest.fixture
def mock_yolo26_outputs() -> dict[str, np.ndarray]:
    """Create mock YOLO26 model outputs."""
    num_detections = 300

    return {
        "labels": np.array([[0, 2, 16, 0, 0] + [0] * (num_detections - 5)]),  # person, car, dog
        "boxes": np.array(
            [
                [
                    [100, 100, 200, 200],  # person
                    [300, 150, 450, 300],  # car
                    [50, 50, 100, 100],  # dog
                    [0, 0, 0, 0],  # empty
                    [0, 0, 0, 0],  # empty
                ]
                + [[0, 0, 0, 0]] * (num_detections - 5)
            ],
            dtype=np.float32,
        ),
        "scores": np.array(
            [[0.95, 0.87, 0.72, 0.1, 0.05] + [0.0] * (num_detections - 5)], dtype=np.float32
        ),
    }


@pytest.fixture
def mock_yolo_outputs() -> dict[str, np.ndarray]:
    """Create mock YOLO26 model outputs."""
    # YOLO output format: [batch, num_dets, 6] where 6 = [x1, y1, x2, y2, confidence, class_id]
    return {
        "output0": np.array(
            [
                [
                    [100, 100, 200, 200, 0.95, 0],  # person
                    [300, 150, 450, 300, 0.87, 2],  # car
                    [50, 50, 100, 100, 0.72, 16],  # dog
                    [200, 200, 300, 300, 0.3, 0],  # below threshold
                ]
            ],
            dtype=np.float32,
        ),
    }


@pytest.fixture
def mock_grpc_client() -> Generator[MagicMock]:
    """Create a mock gRPC Triton client."""
    mock_client = MagicMock()
    mock_client.is_server_live = AsyncMock(return_value=True)
    mock_client.is_server_ready = AsyncMock(return_value=True)
    mock_client.is_model_ready = AsyncMock(return_value=True)
    mock_client.close = AsyncMock()

    # Mock inference result
    mock_result = MagicMock()
    mock_result.as_numpy = MagicMock(
        side_effect=lambda name: {
            "labels": np.array([[0, 2, 16] + [0] * 297]),
            "boxes": np.array(
                [
                    [[100, 100, 200, 200], [300, 150, 450, 300], [50, 50, 100, 100]]
                    + [[0, 0, 0, 0]] * 297
                ],
                dtype=np.float32,
            ),
            "scores": np.array([[0.95, 0.87, 0.72] + [0.0] * 297], dtype=np.float32),
        }.get(name, np.array([]))
    )
    mock_client.infer = AsyncMock(return_value=mock_result)

    # Mock model metadata
    mock_metadata = MagicMock()
    mock_metadata.name = "yolo26"
    mock_metadata.versions = ["1"]
    mock_metadata.inputs = []
    mock_metadata.outputs = []
    mock_client.get_model_metadata = AsyncMock(return_value=mock_metadata)

    with patch(
        "ai.triton.client.TritonClient._connect_grpc", new_callable=AsyncMock
    ) as mock_connect:
        mock_connect.return_value = None
        yield mock_client


@pytest.fixture
def mock_http_client() -> Generator[MagicMock]:
    """Create a mock HTTP Triton client."""
    mock_client = MagicMock()
    mock_client.is_server_live = AsyncMock(return_value=True)
    mock_client.is_server_ready = AsyncMock(return_value=True)
    mock_client.is_model_ready = AsyncMock(return_value=True)
    mock_client.close = AsyncMock()

    with patch(
        "ai.triton.client.TritonClient._connect_http", new_callable=AsyncMock
    ) as mock_connect:
        mock_connect.return_value = None
        yield mock_client


@pytest.fixture
def mock_triton_grpc_module() -> Generator[MagicMock]:
    """Mock the tritonclient.grpc.aio module."""
    mock_module = MagicMock()
    mock_client_class = MagicMock()

    # Create mock client instance
    mock_instance = MagicMock()
    mock_instance.is_server_live = AsyncMock(return_value=True)
    mock_instance.is_server_ready = AsyncMock(return_value=True)
    mock_instance.is_model_ready = AsyncMock(return_value=True)
    mock_instance.close = AsyncMock()

    mock_client_class.return_value = mock_instance
    mock_module.InferenceServerClient = mock_client_class

    # Mock InferInput
    mock_infer_input = MagicMock()
    mock_infer_input.set_data_from_numpy = MagicMock()
    mock_module.InferInput = MagicMock(return_value=mock_infer_input)

    # Mock InferRequestedOutput
    mock_module.InferRequestedOutput = MagicMock()

    with patch.dict("sys.modules", {"tritonclient.grpc.aio": mock_module}):
        yield mock_module
