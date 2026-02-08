"""Unit tests for the AI Gateway's Triton gRPC client wrapper.

Tests the TritonClient class at ai/gateway/triton_client.py, verifying:
- Lazy connection initialization and thread-safe singleton
- Server and model readiness checks
- Model metadata retrieval
- Inference with numpy-to-Triton dtype translation
- Timeout handling and error propagation
- Graceful connection close
- The _numpy_to_triton_dtype helper
- The get_triton_client singleton factory

All tests mock the underlying tritonclient.grpc.aio module so no real
Triton server is required.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from ai.gateway.triton_client import (
    TritonClient,
    TritonClientError,
    _numpy_to_triton_dtype,
    get_triton_client,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    """Reset the module-level singleton between tests."""
    import ai.gateway.triton_client as mod

    mod._client = None


def _build_mock_grpc_module() -> MagicMock:
    """Build a mock for the entire tritonclient.grpc.aio module hierarchy.

    This creates mock entries for ``tritonclient``, ``tritonclient.grpc``,
    and ``tritonclient.grpc.aio`` so that ``import tritonclient.grpc.aio``
    resolves correctly inside TritonClient methods.
    """
    mock_aio = MagicMock()

    # InferenceServerClient constructor
    mock_server_client = MagicMock()
    mock_server_client.is_server_ready = AsyncMock(return_value=True)
    mock_server_client.is_model_ready = AsyncMock(return_value=True)
    mock_server_client.close = AsyncMock()
    mock_server_client.get_model_metadata = AsyncMock()
    mock_server_client.infer = AsyncMock()

    mock_aio.InferenceServerClient = MagicMock(return_value=mock_server_client)

    # InferInput / InferRequestedOutput
    mock_infer_input = MagicMock()
    mock_infer_input.set_data_from_numpy = MagicMock()
    mock_aio.InferInput = MagicMock(return_value=mock_infer_input)
    mock_aio.InferRequestedOutput = MagicMock()

    return mock_aio


@contextmanager
def _patch_triton_modules(mock_aio: MagicMock) -> Generator[MagicMock]:
    """Context manager that patches sys.modules for the full tritonclient hierarchy.

    This ensures ``import tritonclient.grpc.aio as grpcclient`` resolves to
    our mock inside TritonClient._get_client() and TritonClient.infer().
    """
    mock_tritonclient = MagicMock()
    mock_grpc = MagicMock()
    mock_tritonclient.grpc = mock_grpc
    mock_grpc.aio = mock_aio

    modules_patch = {
        "tritonclient": mock_tritonclient,
        "tritonclient.grpc": mock_grpc,
        "tritonclient.grpc.aio": mock_aio,
    }
    with patch.dict(sys.modules, modules_patch):
        yield mock_aio


@pytest.fixture
def mock_grpc_module() -> MagicMock:
    """Fixture that returns a fresh mock aio module."""
    return _build_mock_grpc_module()


@pytest.fixture
def client() -> TritonClient:
    """Return a fresh TritonClient with default settings."""
    return TritonClient(url="localhost:8001", timeout=10.0)


# ---------------------------------------------------------------------------
# _numpy_to_triton_dtype
# ---------------------------------------------------------------------------


class TestNumpyToTritonDtype:
    """Tests for the dtype conversion helper."""

    @pytest.mark.parametrize(
        ("np_dtype", "expected"),
        [
            (np.float16, "FP16"),
            (np.float32, "FP32"),
            (np.float64, "FP64"),
            (np.int8, "INT8"),
            (np.int16, "INT16"),
            (np.int32, "INT32"),
            (np.int64, "INT64"),
            (np.uint8, "UINT8"),
            (np.uint16, "UINT16"),
            (np.uint32, "UINT32"),
            (np.uint64, "UINT64"),
            (np.bool_, "BOOL"),
        ],
    )
    def test_supported_dtypes(self, np_dtype: type, expected: str) -> None:
        """Each supported numpy dtype maps to the correct Triton string."""
        assert _numpy_to_triton_dtype(np.dtype(np_dtype)) == expected

    def test_object_dtype(self) -> None:
        """Object dtype maps to BYTES (used for string inputs)."""
        assert _numpy_to_triton_dtype(np.dtype("object")) == "BYTES"

    def test_unsupported_dtype_raises(self) -> None:
        """An unsupported dtype raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported numpy dtype"):
            _numpy_to_triton_dtype(np.dtype("complex128"))


# ---------------------------------------------------------------------------
# TritonClient.__init__ and lazy connection
# ---------------------------------------------------------------------------


class TestTritonClientInit:
    """Tests for client initialisation and lazy connection."""

    def test_default_attributes(self, client: TritonClient) -> None:
        """Client stores url, timeout, and starts with no underlying client."""
        assert client.url == "localhost:8001"
        assert client.timeout == 10.0
        assert client._client is None

    async def test_get_client_creates_connection(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """_get_client lazily creates the gRPC client on first access."""
        with _patch_triton_modules(mock_grpc_module):
            underlying = await client._get_client()
            assert underlying is not None
            # Second call returns the same object (cached)
            assert await client._get_client() is underlying

    async def test_get_client_raises_on_creation_failure(self, client: TritonClient) -> None:
        """TritonClientError is raised if the gRPC client cannot be created."""
        bad_mod = MagicMock()
        bad_mod.InferenceServerClient = MagicMock(side_effect=RuntimeError("gRPC unavailable"))
        with (
            _patch_triton_modules(bad_mod),
            pytest.raises(TritonClientError, match="Failed to create"),
        ):
            await client._get_client()


# ---------------------------------------------------------------------------
# is_server_ready / is_model_ready
# ---------------------------------------------------------------------------


class TestReadinessChecks:
    """Tests for server and model readiness probes."""

    async def test_is_server_ready_true(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """Returns True when the underlying client reports ready."""
        with _patch_triton_modules(mock_grpc_module):
            result = await client.is_server_ready()
            assert result is True

    async def test_is_server_ready_false(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """Returns False when underlying client reports not ready."""
        underlying = mock_grpc_module.InferenceServerClient.return_value
        underlying.is_server_ready = AsyncMock(return_value=False)
        with _patch_triton_modules(mock_grpc_module):
            assert await client.is_server_ready() is False

    async def test_is_server_ready_on_exception(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """Returns False (does not raise) on connectivity error."""
        underlying = mock_grpc_module.InferenceServerClient.return_value
        underlying.is_server_ready = AsyncMock(side_effect=Exception("conn refused"))
        with _patch_triton_modules(mock_grpc_module):
            assert await client.is_server_ready() is False

    async def test_is_model_ready_true(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """Returns True when a model is loaded."""
        with _patch_triton_modules(mock_grpc_module):
            assert await client.is_model_ready("yolo26") is True

    async def test_is_model_ready_false(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """Returns False when the model is not loaded."""
        underlying = mock_grpc_module.InferenceServerClient.return_value
        underlying.is_model_ready = AsyncMock(return_value=False)
        with _patch_triton_modules(mock_grpc_module):
            assert await client.is_model_ready("missing_model") is False

    async def test_is_model_ready_on_exception(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """Returns False on exception without raising."""
        underlying = mock_grpc_module.InferenceServerClient.return_value
        underlying.is_model_ready = AsyncMock(side_effect=Exception("boom"))
        with _patch_triton_modules(mock_grpc_module):
            assert await client.is_model_ready("yolo26") is False


# ---------------------------------------------------------------------------
# get_model_metadata
# ---------------------------------------------------------------------------


class TestGetModelMetadata:
    """Tests for model metadata retrieval."""

    async def test_returns_parsed_metadata(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """Metadata is parsed into the expected dict shape."""
        mock_input = MagicMock()
        mock_input.name = "images"
        mock_input.datatype = "FP32"
        mock_input.shape = [1, 3, 640, 640]

        mock_output = MagicMock()
        mock_output.name = "output0"
        mock_output.datatype = "FP32"
        mock_output.shape = [1, 84, 8400]

        mock_meta = MagicMock()
        mock_meta.name = "yolo26"
        mock_meta.versions = ["1"]
        mock_meta.platform = "tensorrt_plan"
        mock_meta.inputs = [mock_input]
        mock_meta.outputs = [mock_output]

        underlying = mock_grpc_module.InferenceServerClient.return_value
        underlying.get_model_metadata = AsyncMock(return_value=mock_meta)

        with _patch_triton_modules(mock_grpc_module):
            meta = await client.get_model_metadata("yolo26")

        assert meta["name"] == "yolo26"
        assert meta["versions"] == ["1"]
        assert meta["platform"] == "tensorrt_plan"
        assert len(meta["inputs"]) == 1
        assert meta["inputs"][0]["name"] == "images"
        assert meta["inputs"][0]["datatype"] == "FP32"
        assert meta["inputs"][0]["shape"] == [1, 3, 640, 640]
        assert len(meta["outputs"]) == 1
        assert meta["outputs"][0]["name"] == "output0"

    async def test_raises_on_failure(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """TritonClientError is raised when metadata fetch fails."""
        underlying = mock_grpc_module.InferenceServerClient.return_value
        underlying.get_model_metadata = AsyncMock(side_effect=Exception("model not found"))
        with (
            _patch_triton_modules(mock_grpc_module),
            pytest.raises(TritonClientError, match="Failed to get metadata"),
        ):
            await client.get_model_metadata("nonexistent")


# ---------------------------------------------------------------------------
# infer
# ---------------------------------------------------------------------------


class TestInfer:
    """Tests for the infer method."""

    async def test_successful_inference(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """Inference returns a dict of numpy arrays keyed by output name."""
        expected_output = np.random.rand(1, 84, 8400).astype(np.float32)

        mock_result = MagicMock()
        mock_result.as_numpy = MagicMock(return_value=expected_output)

        underlying = mock_grpc_module.InferenceServerClient.return_value
        underlying.infer = AsyncMock(return_value=mock_result)

        with _patch_triton_modules(mock_grpc_module):
            inputs = {"images": np.random.rand(1, 3, 640, 640).astype(np.float32)}
            result = await client.infer(
                model_name="yolo26",
                inputs=inputs,
                outputs=["output0"],
            )

        assert "output0" in result
        np.testing.assert_array_equal(result["output0"], expected_output)

    async def test_inference_builds_triton_inputs(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """Verifies InferInput and InferRequestedOutput are constructed correctly."""
        mock_result = MagicMock()
        mock_result.as_numpy = MagicMock(return_value=np.zeros((1,)))

        underlying = mock_grpc_module.InferenceServerClient.return_value
        underlying.infer = AsyncMock(return_value=mock_result)

        with _patch_triton_modules(mock_grpc_module):
            input_data = np.ones((1, 3, 224, 224), dtype=np.float32)
            await client.infer(
                model_name="clip",
                inputs={"input": input_data},
                outputs=["output"],
            )

        # InferInput was called with correct args
        mock_grpc_module.InferInput.assert_called_once_with("input", [1, 3, 224, 224], "FP32")
        # InferRequestedOutput was called for each output
        mock_grpc_module.InferRequestedOutput.assert_called_once_with("output")

    async def test_inference_timeout(self, mock_grpc_module: MagicMock) -> None:
        """TritonClientError is raised when inference times out."""

        async def slow_infer(*_args: object, **_kwargs: object) -> None:
            await asyncio.sleep(100)

        underlying = mock_grpc_module.InferenceServerClient.return_value
        underlying.infer = slow_infer

        short_client = TritonClient(url="localhost:8001", timeout=0.01)

        with (
            _patch_triton_modules(mock_grpc_module),
            pytest.raises(TritonClientError, match="timed out"),
        ):
            await short_client.infer(
                model_name="yolo26",
                inputs={"images": np.zeros((1, 3, 640, 640), dtype=np.float32)},
                outputs=["output0"],
                timeout=0.01,
            )

    async def test_inference_per_request_timeout_override(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """Per-request timeout overrides default client timeout."""

        async def slow_infer(*_args: object, **_kwargs: object) -> None:
            await asyncio.sleep(100)

        underlying = mock_grpc_module.InferenceServerClient.return_value
        underlying.infer = slow_infer

        with (
            _patch_triton_modules(mock_grpc_module),
            pytest.raises(TritonClientError, match="timed out"),
        ):
            await client.infer(
                model_name="clip",
                inputs={"input": np.zeros((1,), dtype=np.float32)},
                outputs=["output"],
                timeout=0.01,
            )

    async def test_inference_generic_exception(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """TritonClientError wraps unexpected exceptions during inference."""
        underlying = mock_grpc_module.InferenceServerClient.return_value
        underlying.infer = AsyncMock(side_effect=RuntimeError("GPU out of memory"))

        with (
            _patch_triton_modules(mock_grpc_module),
            pytest.raises(TritonClientError, match="Inference failed"),
        ):
            await client.infer(
                model_name="yolo26",
                inputs={"images": np.zeros((1, 3, 640, 640), dtype=np.float32)},
                outputs=["output0"],
            )

    async def test_inference_with_multiple_inputs_and_outputs(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """Supports multiple named inputs and outputs."""
        out_a = np.array([1.0, 2.0], dtype=np.float32)
        out_b = np.array([3.0, 4.0], dtype=np.float32)

        mock_result = MagicMock()
        mock_result.as_numpy = MagicMock(
            side_effect=lambda name: {"out_a": out_a, "out_b": out_b}[name]
        )

        underlying = mock_grpc_module.InferenceServerClient.return_value
        underlying.infer = AsyncMock(return_value=mock_result)

        with _patch_triton_modules(mock_grpc_module):
            result = await client.infer(
                model_name="test_model",
                inputs={
                    "in_a": np.zeros((1,), dtype=np.float32),
                    "in_b": np.ones((2,), dtype=np.int32),
                },
                outputs=["out_a", "out_b"],
            )

        assert len(result) == 2
        np.testing.assert_array_equal(result["out_a"], out_a)
        np.testing.assert_array_equal(result["out_b"], out_b)

    async def test_triton_client_error_passthrough(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """TritonClientError from _get_client is re-raised without wrapping."""
        underlying = mock_grpc_module.InferenceServerClient.return_value
        underlying.infer = AsyncMock(side_effect=TritonClientError("already a TritonClientError"))

        with (
            _patch_triton_modules(mock_grpc_module),
            pytest.raises(TritonClientError, match="already a TritonClientError"),
        ):
            await client.infer(
                model_name="yolo26",
                inputs={"images": np.zeros((1, 3, 640, 640), dtype=np.float32)},
                outputs=["output0"],
            )


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


class TestClose:
    """Tests for graceful shutdown."""

    async def test_close_calls_underlying(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """close() calls the underlying client's close and resets state."""
        with _patch_triton_modules(mock_grpc_module):
            # Force connection
            await client._get_client()
            assert client._client is not None

            await client.close()
            assert client._client is None

    async def test_close_when_not_connected(self, client: TritonClient) -> None:
        """close() is a no-op when never connected."""
        assert client._client is None
        await client.close()  # Should not raise
        assert client._client is None

    async def test_close_handles_exception(
        self, client: TritonClient, mock_grpc_module: MagicMock
    ) -> None:
        """close() logs but does not raise on underlying close error."""
        underlying = mock_grpc_module.InferenceServerClient.return_value
        underlying.close = AsyncMock(side_effect=Exception("channel broken"))

        with _patch_triton_modules(mock_grpc_module):
            await client._get_client()
            await client.close()  # Should not raise
            # Client is set to None even on error
            assert client._client is None


# ---------------------------------------------------------------------------
# get_triton_client singleton
# ---------------------------------------------------------------------------


class TestGetTritonClient:
    """Tests for the module-level singleton factory."""

    def test_returns_same_instance(self) -> None:
        """Repeated calls return the same TritonClient instance."""
        a = get_triton_client()
        b = get_triton_client()
        assert a is b

    def test_creates_client_with_defaults(self) -> None:
        """The singleton uses module-level TRITON_GRPC_URL and TRITON_TIMEOUT_S."""
        tc = get_triton_client()
        assert isinstance(tc, TritonClient)
        # Defaults from env or module constants
        assert isinstance(tc.url, str)
        assert isinstance(tc.timeout, float)
