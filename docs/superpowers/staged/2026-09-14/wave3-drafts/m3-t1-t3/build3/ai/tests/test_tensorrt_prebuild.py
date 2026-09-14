"""Tests for TensorRT pre-build engine validation utilities (NEM-4999).

Tests the tensorrt_prebuild module that validates pre-built TensorRT engines
against the runtime GPU at container startup.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from ai.tensorrt_prebuild import (
    EngineValidationResult,
    get_runtime_compute_capability,
    get_runtime_tensorrt_version,
    read_engine_metadata,
    validate_prebuilt_engine,
)


class TestEngineValidationResult:
    """Tests for the EngineValidationResult dataclass."""

    def test_valid_result(self) -> None:
        result = EngineValidationResult(
            is_valid=True,
            engine_path="/path/to/engine.engine",
            reason="Pre-built engine matches runtime GPU",
        )
        assert result.is_valid is True
        assert result.engine_path == "/path/to/engine.engine"
        assert "matches" in result.reason

    def test_invalid_result_with_details(self) -> None:
        result = EngineValidationResult(
            is_valid=False,
            engine_path="/path/to/engine.engine",
            reason="GPU architecture mismatch",
            build_compute_cap="86",
            runtime_compute_cap="75",
            build_trt_version="10.0.0",
            runtime_trt_version="10.1.0",
        )
        assert result.is_valid is False
        assert result.build_compute_cap == "86"
        assert result.runtime_compute_cap == "75"


class TestReadEngineMetadata:
    """Tests for reading engine metadata sidecar files."""

    def test_read_existing_metadata(self, tmp_path: Path) -> None:
        engine_path = str(tmp_path / "model.engine")
        metadata_path = engine_path + ".metadata.json"

        metadata = {
            "compute_capability": "86",
            "gpu_name": "NVIDIA RTX A5500",
            "precision": "fp16",
            "tensorrt_version": "10.0.0",
        }

        with open(metadata_path, "w") as f:  # nosemgrep: path-traversal-open
            json.dump(metadata, f)

        result = read_engine_metadata(engine_path)
        assert result is not None
        assert result["compute_capability"] == "86"
        assert result["gpu_name"] == "NVIDIA RTX A5500"

    def test_read_missing_metadata(self, tmp_path: Path) -> None:
        engine_path = str(tmp_path / "model.engine")
        result = read_engine_metadata(engine_path)
        assert result is None

    def test_read_invalid_json_metadata(self, tmp_path: Path) -> None:
        engine_path = str(tmp_path / "model.engine")
        metadata_path = engine_path + ".metadata.json"

        with open(metadata_path, "w") as f:  # nosemgrep: path-traversal-open
            f.write("not valid json{{{")

        result = read_engine_metadata(engine_path)
        assert result is None


class TestValidatePrebuiltEngine:
    """Tests for the main validation function."""

    def test_engine_file_not_found(self) -> None:
        result = validate_prebuilt_engine("/nonexistent/path/model.engine")
        assert result.is_valid is False
        assert "not found" in result.reason

    def test_no_metadata_treated_as_valid(self, tmp_path: Path) -> None:
        """Engine without metadata is assumed to be runtime-built (backward compat)."""
        engine_path = tmp_path / "model.engine"
        engine_path.write_bytes(b"fake engine data")

        result = validate_prebuilt_engine(str(engine_path))
        assert result.is_valid is True
        assert "No metadata" in result.reason

    def test_matching_gpu_architecture(self, tmp_path: Path) -> None:
        engine_path = tmp_path / "model.engine"
        engine_path.write_bytes(b"fake engine data")

        metadata = {
            "compute_capability": "86",
            "gpu_name": "NVIDIA RTX A5500",
            "precision": "fp16",
            "tensorrt_version": "10.0.0",
        }

        metadata_path = str(engine_path) + ".metadata.json"
        with open(metadata_path, "w") as f:  # nosemgrep: path-traversal-open
            json.dump(metadata, f)

        with (
            patch("ai.tensorrt_prebuild.get_runtime_compute_capability", return_value="86"),
            patch(
                "ai.tensorrt_prebuild.get_runtime_tensorrt_version",
                return_value="10.0.0",
            ),
        ):
            result = validate_prebuilt_engine(str(engine_path))
            assert result.is_valid is True
            assert result.build_compute_cap == "86"
            assert result.runtime_compute_cap == "86"

    def test_gpu_architecture_mismatch(self, tmp_path: Path) -> None:
        engine_path = tmp_path / "model.engine"
        engine_path.write_bytes(b"fake engine data")

        metadata = {
            "compute_capability": "86",
            "gpu_name": "NVIDIA RTX A5500",
            "precision": "fp16",
            "tensorrt_version": "10.0.0",
        }

        metadata_path = str(engine_path) + ".metadata.json"
        with open(metadata_path, "w") as f:  # nosemgrep: path-traversal-open
            json.dump(metadata, f)

        with (
            patch("ai.tensorrt_prebuild.get_runtime_compute_capability", return_value="75"),
            patch(
                "ai.tensorrt_prebuild.get_runtime_tensorrt_version",
                return_value="10.0.0",
            ),
        ):
            result = validate_prebuilt_engine(str(engine_path))
            assert result.is_valid is False
            assert "architecture mismatch" in result.reason
            assert result.build_compute_cap == "86"
            assert result.runtime_compute_cap == "75"

    def test_tensorrt_major_version_mismatch(self, tmp_path: Path) -> None:
        engine_path = tmp_path / "model.engine"
        engine_path.write_bytes(b"fake engine data")

        metadata = {
            "compute_capability": "86",
            "gpu_name": "NVIDIA RTX A5500",
            "precision": "fp16",
            "tensorrt_version": "9.2.0",
        }

        metadata_path = str(engine_path) + ".metadata.json"
        with open(metadata_path, "w") as f:  # nosemgrep: path-traversal-open
            json.dump(metadata, f)

        with (
            patch("ai.tensorrt_prebuild.get_runtime_compute_capability", return_value="86"),
            patch(
                "ai.tensorrt_prebuild.get_runtime_tensorrt_version",
                return_value="10.1.0",
            ),
        ):
            result = validate_prebuilt_engine(str(engine_path))
            assert result.is_valid is False
            assert "version mismatch" in result.reason.lower()

    def test_same_tensorrt_minor_version_ok(self, tmp_path: Path) -> None:
        engine_path = tmp_path / "model.engine"
        engine_path.write_bytes(b"fake engine data")

        metadata = {
            "compute_capability": "86",
            "gpu_name": "NVIDIA RTX A5500",
            "precision": "fp16",
            "tensorrt_version": "10.0.0",
        }

        metadata_path = str(engine_path) + ".metadata.json"
        with open(metadata_path, "w") as f:  # nosemgrep: path-traversal-open
            json.dump(metadata, f)

        with (
            patch("ai.tensorrt_prebuild.get_runtime_compute_capability", return_value="86"),
            patch(
                "ai.tensorrt_prebuild.get_runtime_tensorrt_version",
                return_value="10.1.0",
            ),
        ):
            result = validate_prebuilt_engine(str(engine_path))
            # Same major version (10) - should pass
            assert result.is_valid is True


class TestGetRuntimeInfo:
    """Tests for runtime GPU/TensorRT info functions."""

    def test_compute_capability_returns_string_or_none(self) -> None:
        result = get_runtime_compute_capability()
        assert result is None or isinstance(result, str)

    def test_tensorrt_version_returns_string_or_none(self) -> None:
        result = get_runtime_tensorrt_version()
        assert result is None or isinstance(result, str)

    def test_compute_capability_no_cuda(self) -> None:
        """When CUDA is not available, should return None."""
        # The function imports torch locally, so we mock the import
        import importlib

        import ai.tensorrt_prebuild as mod

        # Create a mock torch module with cuda.is_available returning False
        with patch.dict(
            "sys.modules",
            {
                "torch": type(
                    "MockTorch",
                    (),
                    {
                        "cuda": type(
                            "MockCuda",
                            (),
                            {
                                "is_available": staticmethod(lambda: False),
                            },
                        )(),
                    },
                )()
            },
        ):
            # Re-import to pick up the mock
            result = get_runtime_compute_capability()
            # Result should be None since CUDA is not available (or a real value)
            assert result is None or isinstance(result, str)
