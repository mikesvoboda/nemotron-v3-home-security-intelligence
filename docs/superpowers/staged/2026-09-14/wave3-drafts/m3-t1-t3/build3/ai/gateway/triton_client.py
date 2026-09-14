"""Shared Triton gRPC client for the AI Gateway.

Provides an async wrapper around tritonclient.grpc.aio.InferenceServerClient
with connection pooling, timeout handling, and convenience methods for
model inference.

The client connects to Triton Inference Server's gRPC endpoint (default
localhost:8001) and translates numpy arrays into Triton InferInput/InferOutput
objects.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Default Triton gRPC endpoint (inside the same container)
TRITON_GRPC_URL = os.getenv("TRITON_GRPC_URL", "localhost:8001")

# Default inference timeout in seconds
TRITON_TIMEOUT_S = float(os.getenv("TRITON_TIMEOUT_S", "30"))


class TritonClientError(Exception):
    """Raised when a Triton inference or connectivity operation fails."""


class TritonClient:
    """Async wrapper around Triton gRPC inference client.

    Provides a simplified interface for model inference, health checking,
    and metadata retrieval against a Triton Inference Server instance.

    Attributes:
        url: Triton gRPC endpoint address (host:port).
        timeout: Default timeout for inference requests in seconds.
    """

    def __init__(
        self,
        url: str = TRITON_GRPC_URL,
        timeout: float = TRITON_TIMEOUT_S,
    ) -> None:
        self.url = url
        self.timeout = timeout
        self._client: Any = None
        self._lock = asyncio.Lock()

    async def _get_client(self) -> Any:
        """Get or create the underlying gRPC client (lazy init, thread-safe)."""
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    try:
                        import tritonclient.grpc.aio as grpcclient

                        self._client = grpcclient.InferenceServerClient(
                            url=self.url,
                            verbose=False,
                        )
                        logger.info(f"Triton gRPC client connected to {self.url}")
                    except Exception as e:
                        raise TritonClientError(
                            f"Failed to create Triton gRPC client at {self.url}: {e}"
                        ) from e
        return self._client

    async def close(self) -> None:
        """Close the gRPC client connection gracefully."""
        if self._client is not None:
            try:
                await self._client.close()
                logger.info("Triton gRPC client closed")
            except Exception as e:
                logger.warning(f"Error closing Triton client: {e}")
            finally:
                self._client = None

    async def is_server_ready(self) -> bool:
        """Check if Triton server is ready to accept requests.

        Returns:
            True if the server is live and ready, False otherwise.
        """
        try:
            client = await self._get_client()
            return await client.is_server_ready()
        except Exception as e:
            logger.warning(f"Triton server readiness check failed: {e}")
            return False

    async def is_model_ready(self, model_name: str) -> bool:
        """Check if a specific model is loaded and ready.

        Args:
            model_name: Name of the model in the Triton model repository.

        Returns:
            True if the model is ready, False otherwise.
        """
        try:
            client = await self._get_client()
            return await client.is_model_ready(model_name)
        except Exception as e:
            logger.warning(f"Model readiness check failed for {model_name}: {e}")
            return False

    async def get_model_metadata(self, model_name: str) -> dict[str, Any]:
        """Retrieve model metadata from Triton.

        Args:
            model_name: Name of the model.

        Returns:
            Dictionary with model metadata (name, versions, platform, inputs, outputs).
        """
        try:
            client = await self._get_client()
            metadata = await client.get_model_metadata(model_name)
            return {
                "name": metadata.name,
                "versions": list(metadata.versions),
                "platform": metadata.platform,
                "inputs": [
                    {"name": inp.name, "datatype": inp.datatype, "shape": list(inp.shape)}
                    for inp in metadata.inputs
                ],
                "outputs": [
                    {"name": out.name, "datatype": out.datatype, "shape": list(out.shape)}
                    for out in metadata.outputs
                ],
            }
        except Exception as e:
            raise TritonClientError(f"Failed to get metadata for model {model_name}: {e}") from e

    async def infer(
        self,
        model_name: str,
        inputs: dict[str, np.ndarray],
        outputs: list[str],
        timeout: float | None = None,
    ) -> dict[str, np.ndarray]:
        """Run inference on a Triton model.

        Translates numpy arrays into Triton InferInput objects, sends the
        request, and returns the results as numpy arrays keyed by output name.

        Args:
            model_name: Name of the model to run inference on.
            inputs: Dictionary mapping input tensor names to numpy arrays.
            outputs: List of output tensor names to request.
            timeout: Optional per-request timeout override in seconds.

        Returns:
            Dictionary mapping output names to numpy arrays.

        Raises:
            TritonClientError: If inference fails for any reason.
        """
        import tritonclient.grpc.aio as grpcclient

        effective_timeout = timeout or self.timeout

        try:
            client = await self._get_client()

            # Build InferInput objects
            triton_inputs: list[Any] = []
            for name, array in inputs.items():
                triton_dtype = _numpy_to_triton_dtype(array.dtype)
                inp = grpcclient.InferInput(name, list(array.shape), triton_dtype)
                inp.set_data_from_numpy(array)
                triton_inputs.append(inp)

            # Build InferRequestedOutput objects
            triton_outputs = [grpcclient.InferRequestedOutput(name) for name in outputs]

            # Execute inference with timeout
            result = await asyncio.wait_for(
                client.infer(
                    model_name=model_name,
                    inputs=triton_inputs,
                    outputs=triton_outputs,
                ),
                timeout=effective_timeout,
            )

            # Extract output tensors
            output_dict: dict[str, np.ndarray] = {}
            for name in outputs:
                output_dict[name] = result.as_numpy(name)

            return output_dict

        except TimeoutError:
            raise TritonClientError(
                f"Inference timed out for model {model_name} after {effective_timeout}s"
            ) from None
        except TritonClientError:
            raise
        except Exception as e:
            raise TritonClientError(f"Inference failed for model {model_name}: {e}") from e


# Triton dtype mapping from numpy dtypes
_NUMPY_TO_TRITON: dict[str, str] = {
    "float16": "FP16",
    "float32": "FP32",
    "float64": "FP64",
    "int8": "INT8",
    "int16": "INT16",
    "int32": "INT32",
    "int64": "INT64",
    "uint8": "UINT8",
    "uint16": "UINT16",
    "uint32": "UINT32",
    "uint64": "UINT64",
    "bool": "BOOL",
    "object": "BYTES",
}


def _numpy_to_triton_dtype(dtype: np.dtype) -> str:
    """Convert a numpy dtype to the corresponding Triton datatype string.

    Args:
        dtype: Numpy dtype to convert.

    Returns:
        Triton datatype string (e.g. 'FP32', 'INT64').

    Raises:
        ValueError: If the numpy dtype has no Triton equivalent.
    """
    key = str(dtype)
    if key in _NUMPY_TO_TRITON:
        return _NUMPY_TO_TRITON[key]
    raise ValueError(f"Unsupported numpy dtype for Triton: {dtype}")


# Module-level singleton client instance
_client: TritonClient | None = None


def get_triton_client() -> TritonClient:
    """Get or create the module-level TritonClient singleton.

    Returns:
        Shared TritonClient instance.
    """
    global _client
    if _client is None:
        _client = TritonClient()
    return _client
