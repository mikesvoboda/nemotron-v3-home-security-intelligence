"""Unit tests for setup_lib.model_downloader module.

Tests AI model download functionality including model existence checks,
HuggingFace downloads, download script execution, size calculations,
and interactive prompt handling.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from setup_lib.model_downloader import ModelSpec


class TestModelSpecConstants:
    """Tests for model specification constants."""

    def test_required_models_exists(self) -> None:
        """REQUIRED_MODELS should be a list of ModelSpec objects."""
        from setup_lib.model_downloader import REQUIRED_MODELS

        assert isinstance(REQUIRED_MODELS, list)
        assert len(REQUIRED_MODELS) > 0

    def test_required_models_have_required_flag(self) -> None:
        """All REQUIRED_MODELS should have required=True."""
        from setup_lib.model_downloader import REQUIRED_MODELS

        for model in REQUIRED_MODELS:
            assert model.required is True, f"Model {model.name} should have required=True"

    def test_required_models_contain_essential_models(self) -> None:
        """REQUIRED_MODELS should contain essential models for the system."""
        from setup_lib.model_downloader import REQUIRED_MODELS

        model_names = [m.name for m in REQUIRED_MODELS]
        # Florence-2 and CLIP are essential for the AI pipeline
        assert "florence-2-large" in model_names
        assert "clip-vit-l" in model_names

    def test_phase1_models_exists(self) -> None:
        """PHASE1_MODELS should be a list."""
        from setup_lib.model_downloader import PHASE1_MODELS

        assert isinstance(PHASE1_MODELS, list)

    def test_phase1_models_have_phase_1(self) -> None:
        """All PHASE1_MODELS should have phase=1."""
        from setup_lib.model_downloader import PHASE1_MODELS

        for model in PHASE1_MODELS:
            assert model.phase == 1, f"Model {model.name} should have phase=1"

    def test_phase1_models_are_optional(self) -> None:
        """PHASE1_MODELS should all be optional (required=False)."""
        from setup_lib.model_downloader import PHASE1_MODELS

        for model in PHASE1_MODELS:
            assert model.required is False, f"Model {model.name} should be optional"

    def test_phase2_models_exists(self) -> None:
        """PHASE2_MODELS should be a list."""
        from setup_lib.model_downloader import PHASE2_MODELS

        assert isinstance(PHASE2_MODELS, list)

    def test_phase2_models_have_phase_2(self) -> None:
        """All PHASE2_MODELS should have phase=2."""
        from setup_lib.model_downloader import PHASE2_MODELS

        for model in PHASE2_MODELS:
            assert model.phase == 2, f"Model {model.name} should have phase=2"

    def test_phase2_models_contain_enrichment_models(self) -> None:
        """PHASE2_MODELS should contain context enrichment models."""
        from setup_lib.model_downloader import PHASE2_MODELS

        model_names = [m.name for m in PHASE2_MODELS]
        # These are context enrichment models
        assert "fashion-clip" in model_names or "xclip-base" in model_names

    def test_phase3_models_exists(self) -> None:
        """PHASE3_MODELS should be a list."""
        from setup_lib.model_downloader import PHASE3_MODELS

        assert isinstance(PHASE3_MODELS, list)

    def test_phase3_models_have_phase_3(self) -> None:
        """All PHASE3_MODELS should have phase=3."""
        from setup_lib.model_downloader import PHASE3_MODELS

        for model in PHASE3_MODELS:
            assert model.phase == 3, f"Model {model.name} should have phase=3"

    def test_all_models_have_valid_size(self) -> None:
        """All models should have positive size_mb."""
        from setup_lib.model_downloader import (
            PHASE1_MODELS,
            PHASE2_MODELS,
            PHASE3_MODELS,
            REQUIRED_MODELS,
        )

        all_models = REQUIRED_MODELS + PHASE1_MODELS + PHASE2_MODELS + PHASE3_MODELS
        for model in all_models:
            assert model.size_mb > 0, f"Model {model.name} should have positive size"

    def test_all_models_have_description(self) -> None:
        """All models should have a non-empty description."""
        from setup_lib.model_downloader import (
            PHASE1_MODELS,
            PHASE2_MODELS,
            PHASE3_MODELS,
            REQUIRED_MODELS,
        )

        all_models = REQUIRED_MODELS + PHASE1_MODELS + PHASE2_MODELS + PHASE3_MODELS
        for model in all_models:
            assert model.description, f"Model {model.name} should have a description"

    def test_model_spec_is_named_tuple(self) -> None:
        """ModelSpec should be a NamedTuple with expected fields."""
        from setup_lib.model_downloader import ModelSpec

        # Create a test instance
        spec = ModelSpec(
            name="test",
            hf_repo="test/repo",
            phase=1,
            size_mb=100,
            description="Test model",
            required=False,
        )

        assert spec.name == "test"
        assert spec.hf_repo == "test/repo"
        assert spec.phase == 1
        assert spec.size_mb == 100
        assert spec.description == "Test model"
        assert spec.required is False


class TestCheckModelExists:
    """Tests for check_model_exists() function."""

    def test_model_exists_with_safetensors(self) -> None:
        """Should return True when model dir has .safetensors files."""
        from setup_lib.model_downloader import check_model_exists

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "rglob") as mock_rglob:
                # Simulate finding safetensors files for .safetensors extension
                def rglob_side_effect(pattern: str) -> list[Path]:
                    if ".safetensors" in pattern:
                        return [Path("model.safetensors")]
                    return []

                mock_rglob.side_effect = rglob_side_effect

                result = check_model_exists(Path("/ai"), "test-model")
                assert result is True

    def test_model_exists_with_pytorch_weights(self) -> None:
        """Should return True when model dir has .pt files."""
        from setup_lib.model_downloader import check_model_exists

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "rglob") as mock_rglob:
                # Simulate finding .pt files
                def rglob_side_effect(pattern: str) -> list[Path]:
                    if ".pt" in pattern and ".pth" not in pattern:
                        return [Path("model.pt")]
                    return []

                mock_rglob.side_effect = rglob_side_effect

                result = check_model_exists(Path("/ai"), "test-model")
                assert result is True

    def test_model_exists_with_bin_weights(self) -> None:
        """Should return True when model dir has .bin files."""
        from setup_lib.model_downloader import check_model_exists

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "rglob") as mock_rglob:
                # Simulate finding .bin files
                def rglob_side_effect(pattern: str) -> list[Path]:
                    if ".bin" in pattern:
                        return [Path("pytorch_model.bin")]
                    return []

                mock_rglob.side_effect = rglob_side_effect

                result = check_model_exists(Path("/ai"), "test-model")
                assert result is True

    def test_model_exists_with_onnx(self) -> None:
        """Should return True when model dir has .onnx files."""
        from setup_lib.model_downloader import check_model_exists

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "rglob") as mock_rglob:
                # Simulate finding .onnx files
                def rglob_side_effect(pattern: str) -> list[Path]:
                    if ".onnx" in pattern:
                        return [Path("model.onnx")]
                    return []

                mock_rglob.side_effect = rglob_side_effect

                result = check_model_exists(Path("/ai"), "test-model")
                assert result is True

    def test_model_not_exists_directory_missing(self) -> None:
        """Should return False when model directory doesn't exist."""
        from setup_lib.model_downloader import check_model_exists

        with patch.object(Path, "exists", return_value=False):
            result = check_model_exists(Path("/ai"), "test-model")
            assert result is False

    def test_model_not_exists_no_model_files(self) -> None:
        """Should return False when directory exists but has no model files."""
        from setup_lib.model_downloader import check_model_exists

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "rglob") as mock_rglob:
                # No model files found
                mock_rglob.return_value = []

                result = check_model_exists(Path("/ai"), "test-model")
                assert result is False

    def test_model_exists_checks_correct_path(self) -> None:
        """Should check model-zoo subdirectory."""
        from setup_lib.model_downloader import check_model_exists

        mock_path = MagicMock(spec=Path)
        mock_model_dir = MagicMock(spec=Path)
        mock_path.__truediv__ = MagicMock(return_value=mock_model_dir)
        mock_model_dir.__truediv__ = MagicMock(return_value=mock_model_dir)
        mock_model_dir.exists.return_value = False

        check_model_exists(mock_path, "test-model")

        # Verify path construction: model_path / "model-zoo" / model_name
        mock_path.__truediv__.assert_called_with("model-zoo")


class TestDownloadHfModel:
    """Tests for download_hf_model() function."""

    def test_download_success(self) -> None:
        """Should return True when download succeeds."""
        from setup_lib.model_downloader import ModelSpec, download_hf_model

        model = ModelSpec(
            name="test-model",
            hf_repo="test/repo",
            phase=1,
            size_mb=100,
            description="Test",
            required=False,
        )

        with (
            patch("setup_lib.model_downloader.HF_HUB_AVAILABLE", True),
            patch("setup_lib.model_downloader.snapshot_download") as mock_download,
            patch.object(Path, "mkdir"),
            patch("builtins.print"),
        ):
            mock_download.return_value = "/path/to/model"

            result = download_hf_model(model, Path("/ai"))

            assert result is True
            mock_download.assert_called_once()

    def test_download_failure(self) -> None:
        """Should return False when download fails."""
        from setup_lib.model_downloader import ModelSpec, download_hf_model

        model = ModelSpec(
            name="test-model",
            hf_repo="test/repo",
            phase=1,
            size_mb=100,
            description="Test",
            required=False,
        )

        with (
            patch("setup_lib.model_downloader.HF_HUB_AVAILABLE", True),
            patch(
                "setup_lib.model_downloader.snapshot_download",
                side_effect=Exception("Network error"),
            ),
            patch.object(Path, "mkdir"),
            patch("builtins.print"),
        ):
            result = download_hf_model(model, Path("/ai"))

            assert result is False

    def test_download_no_huggingface_hub(self) -> None:
        """Should return False when huggingface_hub is not available."""
        from setup_lib.model_downloader import ModelSpec, download_hf_model

        model = ModelSpec(
            name="test-model",
            hf_repo="test/repo",
            phase=1,
            size_mb=100,
            description="Test",
            required=False,
        )

        with (
            patch("setup_lib.model_downloader.HF_HUB_AVAILABLE", False),
            patch("builtins.print"),
        ):
            result = download_hf_model(model, Path("/ai"))

            assert result is False

    def test_download_no_hf_repo(self) -> None:
        """Should return False for models without HuggingFace repo."""
        from setup_lib.model_downloader import ModelSpec, download_hf_model

        model = ModelSpec(
            name="ultralytics-model",
            hf_repo="",  # Empty repo - uses alternative loader
            phase=1,
            size_mb=100,
            description="Test",
            required=False,
        )

        with (
            patch("setup_lib.model_downloader.HF_HUB_AVAILABLE", True),
            patch("builtins.print"),
        ):
            result = download_hf_model(model, Path("/ai"))

            assert result is False

    def test_download_creates_directory(self) -> None:
        """Should create model directory if it doesn't exist."""
        from setup_lib.model_downloader import ModelSpec, download_hf_model

        model = ModelSpec(
            name="test-model",
            hf_repo="test/repo",
            phase=1,
            size_mb=100,
            description="Test",
            required=False,
        )

        with (
            patch("setup_lib.model_downloader.HF_HUB_AVAILABLE", True),
            patch("setup_lib.model_downloader.snapshot_download"),
            patch.object(Path, "mkdir") as mock_mkdir,
            patch("builtins.print"),
        ):
            download_hf_model(model, Path("/ai"))

            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_download_uses_correct_args(self) -> None:
        """Should pass correct arguments to snapshot_download."""
        from setup_lib.model_downloader import ModelSpec, download_hf_model

        model = ModelSpec(
            name="test-model",
            hf_repo="microsoft/Florence-2-large",
            phase=1,
            size_mb=1200,
            description="Test",
            required=True,
        )

        with (
            patch("setup_lib.model_downloader.HF_HUB_AVAILABLE", True),
            patch("setup_lib.model_downloader.snapshot_download") as mock_download,
            patch.object(Path, "mkdir"),
            patch("builtins.print"),
        ):
            download_hf_model(model, Path("/ai"))

            mock_download.assert_called_once()
            call_kwargs = mock_download.call_args[1]
            assert call_kwargs["repo_id"] == "microsoft/Florence-2-large"
            assert call_kwargs["local_dir_use_symlinks"] is False


class TestRunDownloadScript:
    """Tests for run_download_script() function."""

    def test_script_runs_successfully(self) -> None:
        """Should return True when script runs successfully."""
        from setup_lib.model_downloader import run_download_script

        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch.object(Path, "exists", return_value=True),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = run_download_script("download-model-zoo.py")

            assert result is True

    def test_script_not_found(self) -> None:
        """Should return False when script doesn't exist."""
        from setup_lib.model_downloader import run_download_script

        with (
            patch.object(Path, "exists", return_value=False),
            patch("builtins.print"),
        ):
            result = run_download_script("nonexistent-script.py")

            assert result is False

    def test_script_fails_with_error_code(self) -> None:
        """Should return False when script returns non-zero exit code."""
        from setup_lib.model_downloader import run_download_script

        with (
            patch.object(Path, "exists", return_value=True),
            patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "cmd"),
            ),
            patch("builtins.print"),
        ):
            result = run_download_script("download-model-zoo.py")

            assert result is False

    def test_script_python_not_found(self) -> None:
        """Should return False when Python interpreter not found."""
        from setup_lib.model_downloader import run_download_script

        with (
            patch.object(Path, "exists", return_value=True),
            patch("subprocess.run", side_effect=FileNotFoundError),
            patch("builtins.print"),
        ):
            result = run_download_script("download-model-zoo.py")

            assert result is False

    def test_script_with_args(self) -> None:
        """Should pass additional arguments to the script."""
        from setup_lib.model_downloader import run_download_script

        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch.object(Path, "exists", return_value=True),
            patch("subprocess.run", return_value=mock_result) as mock_run,
            patch("sys.executable", "/usr/bin/python3"),
        ):
            run_download_script("download-model-zoo.py", ["--all", "--force"])

            call_args = mock_run.call_args[0][0]
            assert "--all" in call_args
            assert "--force" in call_args

    def test_script_uses_sys_executable(self) -> None:
        """Should use sys.executable for Python interpreter."""
        from setup_lib.model_downloader import run_download_script

        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch.object(Path, "exists", return_value=True),
            patch("subprocess.run", return_value=mock_result) as mock_run,
            patch("sys.executable", "/custom/python3"),
        ):
            run_download_script("download-model-zoo.py")

            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "/custom/python3"


class TestCalculateDownloadSize:
    """Tests for calculate_download_size() function."""

    def test_all_models_missing(self) -> None:
        """Should return total size when all models are missing."""
        from setup_lib.model_downloader import ModelSpec, calculate_download_size

        models = [
            ModelSpec("model1", "", 1, 100, "Test 1", False),
            ModelSpec("model2", "", 1, 200, "Test 2", False),
            ModelSpec("model3", "", 1, 300, "Test 3", False),
        ]

        with patch("setup_lib.model_downloader.check_model_exists", return_value=False):
            result = calculate_download_size(models, Path("/ai"))

            assert result == 600

    def test_all_models_present(self) -> None:
        """Should return 0 when all models already exist."""
        from setup_lib.model_downloader import ModelSpec, calculate_download_size

        models = [
            ModelSpec("model1", "", 1, 100, "Test 1", False),
            ModelSpec("model2", "", 1, 200, "Test 2", False),
        ]

        with patch("setup_lib.model_downloader.check_model_exists", return_value=True):
            result = calculate_download_size(models, Path("/ai"))

            assert result == 0

    def test_some_models_missing(self) -> None:
        """Should return size of only missing models."""
        from setup_lib.model_downloader import ModelSpec, calculate_download_size

        models = [
            ModelSpec("model1", "", 1, 100, "Test 1", False),
            ModelSpec("model2", "", 1, 200, "Test 2", False),
            ModelSpec("model3", "", 1, 300, "Test 3", False),
        ]

        def check_exists_side_effect(path: Path, name: str) -> bool:
            return name == "model2"

        with patch(
            "setup_lib.model_downloader.check_model_exists",
            side_effect=check_exists_side_effect,
        ):
            result = calculate_download_size(models, Path("/ai"))

            # Only model1 (100) and model3 (300) are missing
            assert result == 400

    def test_empty_model_list(self) -> None:
        """Should return 0 for empty model list."""
        from setup_lib.model_downloader import calculate_download_size

        result = calculate_download_size([], Path("/ai"))

        assert result == 0


class TestPromptAndDownloadModels:
    """Tests for prompt_and_download_models() function."""

    def test_creates_model_zoo_directory(self) -> None:
        """Should create model-zoo directory when it doesn't exist."""
        from setup_lib.model_downloader import prompt_and_download_models

        mock_path = MagicMock(spec=Path)
        mock_model_zoo = MagicMock(spec=Path)
        mock_path.__truediv__ = MagicMock(return_value=mock_model_zoo)
        mock_model_zoo.exists.return_value = False

        with (
            patch("builtins.input", side_effect=["y", "4"]),  # Create dir, skip download
            patch("builtins.print"),
            patch.object(Path, "__new__", return_value=mock_path),
        ):
            prompt_and_download_models({"ai_models_path": "/export/ai_models"})

            mock_model_zoo.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_skips_when_all_models_downloaded(self) -> None:
        """Should skip download prompt when all models already exist."""
        from setup_lib.model_downloader import prompt_and_download_models

        with (
            patch("setup_lib.model_downloader.check_model_exists", return_value=True),
            patch("builtins.print") as mock_print,
            patch.object(Path, "exists", return_value=True),
        ):
            prompt_and_download_models({"ai_models_path": "/export/ai_models"})

            # Should print "All models already downloaded"
            print_calls = [str(c) for c in mock_print.call_args_list]
            assert any("All models already downloaded" in str(c) for c in print_calls)

    def test_option_4_skips_download(self) -> None:
        """Should skip downloads when user selects option 4."""
        from setup_lib.model_downloader import prompt_and_download_models

        with (
            patch("setup_lib.model_downloader.check_model_exists", return_value=False),
            patch("builtins.input", return_value="4"),
            patch("builtins.print") as mock_print,
            patch.object(Path, "exists", return_value=True),
            patch("shutil.disk_usage") as mock_disk,
        ):
            mock_disk.return_value = MagicMock(free=100 * 1024**3)  # 100GB free

            prompt_and_download_models({"ai_models_path": "/export/ai_models"})

            # Should print "Skipping model downloads"
            print_calls = [str(c) for c in mock_print.call_args_list]
            assert any("Skipping model downloads" in str(c) for c in print_calls)

    def test_option_1_downloads_required_models_only(self) -> None:
        """Should download only required models with HF repo when option 1 selected."""
        from setup_lib.model_downloader import prompt_and_download_models

        downloaded_models: list[str] = []

        def mock_download(model: ModelSpec, path: Path) -> bool:
            downloaded_models.append(model.name)
            return True

        with (
            patch("setup_lib.model_downloader.check_model_exists", return_value=False),
            patch("builtins.input", return_value="1"),
            patch("builtins.print"),
            patch.object(Path, "exists", return_value=True),
            patch("shutil.disk_usage") as mock_disk,
            patch("setup_lib.model_downloader.HF_HUB_AVAILABLE", True),
            patch("setup_lib.model_downloader.download_hf_model", side_effect=mock_download),
        ):
            mock_disk.return_value = MagicMock(free=100 * 1024**3)

            prompt_and_download_models({"ai_models_path": "/export/ai_models"})

            # Should have downloaded florence-2-large and clip-vit-l
            # (yolo26 is skipped because it has no hf_repo)
            assert "florence-2-large" in downloaded_models
            assert "clip-vit-l" in downloaded_models

    def test_uses_default_path_when_not_provided(self) -> None:
        """Should use default ai_models_path when not in config."""
        from setup_lib.model_downloader import prompt_and_download_models

        with (
            patch("setup_lib.model_downloader.check_model_exists", return_value=True),
            patch("builtins.print"),
            patch.object(Path, "exists", return_value=True),
        ):
            prompt_and_download_models({})

            # Function should complete without error using default path

    def test_handles_permission_error_on_mkdir(self) -> None:
        """Should handle permission error when creating directory."""
        from setup_lib.model_downloader import prompt_and_download_models

        # Create a mock path that raises PermissionError on mkdir
        mock_model_zoo = MagicMock()
        mock_model_zoo.exists.return_value = False
        mock_model_zoo.mkdir.side_effect = PermissionError("Permission denied")
        mock_model_zoo.parent = Path("/export")

        mock_ai_path = MagicMock()
        mock_ai_path.__truediv__ = MagicMock(return_value=mock_model_zoo)

        with (
            patch("builtins.input", return_value="y"),
            patch("builtins.print") as mock_print,
            patch("setup_lib.model_downloader.Path", return_value=mock_ai_path),
        ):
            prompt_and_download_models({"ai_models_path": "/export/ai_models"})

            # Should print permission denied message
            print_calls = [str(c) for c in mock_print.call_args_list]
            assert any("Permission denied" in str(c) for c in print_calls)

    def test_disk_space_warning(self) -> None:
        """Should warn when disk space is low."""
        from setup_lib.model_downloader import prompt_and_download_models

        with (
            patch("setup_lib.model_downloader.check_model_exists", return_value=False),
            patch("builtins.input", return_value="4"),  # Skip download
            patch("builtins.print") as mock_print,
            patch.object(Path, "exists", return_value=True),
            patch("shutil.disk_usage") as mock_disk,
        ):
            # Only 1GB free, need much more for models
            mock_disk.return_value = MagicMock(free=1 * 1024**3)

            prompt_and_download_models({"ai_models_path": "/export/ai_models"})

            # Should print warning about low disk space
            print_calls = [str(c) for c in mock_print.call_args_list]
            assert any("Warning" in str(c) or "free" in str(c) for c in print_calls)

    def test_installs_huggingface_hub_if_missing(self) -> None:
        """Should attempt to install huggingface_hub if not available."""
        from setup_lib.model_downloader import prompt_and_download_models

        with (
            patch("setup_lib.model_downloader.check_model_exists", return_value=False),
            patch("builtins.input", return_value="1"),
            patch("builtins.print"),
            patch.object(Path, "exists", return_value=True),
            patch("shutil.disk_usage") as mock_disk,
            patch("setup_lib.model_downloader.HF_HUB_AVAILABLE", False),
            patch("subprocess.run") as mock_run,
        ):
            mock_disk.return_value = MagicMock(free=100 * 1024**3)
            mock_run.side_effect = [
                MagicMock(returncode=0),  # pip install succeeds
            ]

            # This will attempt pip install and then fail on import
            # which falls back to download script
            prompt_and_download_models({"ai_models_path": "/export/ai_models"})

            # Should have attempted to install huggingface_hub
            pip_calls = [c for c in mock_run.call_args_list if "pip" in str(c)]
            assert len(pip_calls) > 0

    def test_tracks_download_success_and_failures(self) -> None:
        """Should track successful and failed downloads."""
        from setup_lib.model_downloader import prompt_and_download_models

        call_count = [0]

        def mock_download(model: ModelSpec, path: Path) -> bool:
            call_count[0] += 1
            # Alternate success/failure
            return call_count[0] % 2 == 0

        with (
            patch("setup_lib.model_downloader.check_model_exists", return_value=False),
            patch("builtins.input", return_value="1"),
            patch("builtins.print") as mock_print,
            patch.object(Path, "exists", return_value=True),
            patch("shutil.disk_usage") as mock_disk,
            patch("setup_lib.model_downloader.HF_HUB_AVAILABLE", True),
            patch("setup_lib.model_downloader.download_hf_model", side_effect=mock_download),
        ):
            mock_disk.return_value = MagicMock(free=100 * 1024**3)

            prompt_and_download_models({"ai_models_path": "/export/ai_models"})

            # Should print summary with succeeded/failed counts
            print_calls = [str(c) for c in mock_print.call_args_list]
            assert any("succeeded" in str(c) and "failed" in str(c) for c in print_calls)

    def test_option_2_includes_phase1_models(self) -> None:
        """Should download required + phase1 models with option 2."""
        from setup_lib.model_downloader import (
            PHASE1_MODELS,
            REQUIRED_MODELS,
            prompt_and_download_models,
        )

        downloaded_models: list[str] = []

        def mock_download(model: ModelSpec, path: Path) -> bool:
            downloaded_models.append(model.name)
            return True

        with (
            patch("setup_lib.model_downloader.check_model_exists", return_value=False),
            patch("builtins.input", return_value="2"),
            patch("builtins.print"),
            patch.object(Path, "exists", return_value=True),
            patch("shutil.disk_usage") as mock_disk,
            patch("setup_lib.model_downloader.HF_HUB_AVAILABLE", True),
            patch("setup_lib.model_downloader.download_hf_model", side_effect=mock_download),
        ):
            mock_disk.return_value = MagicMock(free=100 * 1024**3)

            prompt_and_download_models({"ai_models_path": "/export/ai_models"})

            # Should include models from REQUIRED_MODELS with hf_repo
            required_with_repo = [m.name for m in REQUIRED_MODELS if m.hf_repo]
            for name in required_with_repo:
                assert name in downloaded_models

            # Should include models from PHASE1_MODELS with hf_repo
            phase1_with_repo = [m.name for m in PHASE1_MODELS if m.hf_repo]
            for name in phase1_with_repo:
                assert name in downloaded_models

    def test_option_3_downloads_all_models(self) -> None:
        """Should download all models with option 3."""
        from setup_lib.model_downloader import (
            PHASE1_MODELS,
            PHASE2_MODELS,
            PHASE3_MODELS,
            REQUIRED_MODELS,
            prompt_and_download_models,
        )

        downloaded_models: list[str] = []

        def mock_download(model: ModelSpec, path: Path) -> bool:
            downloaded_models.append(model.name)
            return True

        with (
            patch("setup_lib.model_downloader.check_model_exists", return_value=False),
            patch("builtins.input", return_value="3"),
            patch("builtins.print"),
            patch.object(Path, "exists", return_value=True),
            patch("shutil.disk_usage") as mock_disk,
            patch("setup_lib.model_downloader.HF_HUB_AVAILABLE", True),
            patch("setup_lib.model_downloader.download_hf_model", side_effect=mock_download),
        ):
            mock_disk.return_value = MagicMock(free=100 * 1024**3)

            prompt_and_download_models({"ai_models_path": "/export/ai_models"})

            # Should include all models with hf_repo
            all_models = REQUIRED_MODELS + PHASE1_MODELS + PHASE2_MODELS + PHASE3_MODELS
            all_with_repo = [m.name for m in all_models if m.hf_repo]

            for name in all_with_repo:
                assert name in downloaded_models

    def test_skips_already_downloaded_models(self) -> None:
        """Should not re-download models that already exist."""
        from setup_lib.model_downloader import prompt_and_download_models

        downloaded_models: list[str] = []

        def mock_download(model: ModelSpec, path: Path) -> bool:
            downloaded_models.append(model.name)
            return True

        def mock_check_exists(path: Path, name: str) -> bool:
            # florence-2-large already exists
            return name == "florence-2-large"

        with (
            patch(
                "setup_lib.model_downloader.check_model_exists",
                side_effect=mock_check_exists,
            ),
            patch("builtins.input", return_value="1"),
            patch("builtins.print"),
            patch.object(Path, "exists", return_value=True),
            patch("shutil.disk_usage") as mock_disk,
            patch("setup_lib.model_downloader.HF_HUB_AVAILABLE", True),
            patch("setup_lib.model_downloader.download_hf_model", side_effect=mock_download),
        ):
            mock_disk.return_value = MagicMock(free=100 * 1024**3)

            prompt_and_download_models({"ai_models_path": "/export/ai_models"})

            # florence-2-large should not be in downloaded list
            assert "florence-2-large" not in downloaded_models

    def test_default_option_is_1(self) -> None:
        """Should default to option 1 when empty input provided."""
        from setup_lib.model_downloader import prompt_and_download_models

        downloaded_models: list[str] = []

        def mock_download(model: ModelSpec, path: Path) -> bool:
            downloaded_models.append(model.name)
            return True

        with (
            patch("setup_lib.model_downloader.check_model_exists", return_value=False),
            patch("builtins.input", return_value=""),  # Empty = default to 1
            patch("builtins.print"),
            patch.object(Path, "exists", return_value=True),
            patch("shutil.disk_usage") as mock_disk,
            patch("setup_lib.model_downloader.HF_HUB_AVAILABLE", True),
            patch("setup_lib.model_downloader.download_hf_model", side_effect=mock_download),
        ):
            mock_disk.return_value = MagicMock(free=100 * 1024**3)

            prompt_and_download_models({"ai_models_path": "/export/ai_models"})

            # Should download required models (option 1 is default)
            assert "florence-2-large" in downloaded_models
            assert "clip-vit-l" in downloaded_models


class TestHfHubAvailability:
    """Tests for HF_HUB_AVAILABLE constant."""

    def test_hf_hub_available_is_boolean(self) -> None:
        """HF_HUB_AVAILABLE should be a boolean."""
        from setup_lib.model_downloader import HF_HUB_AVAILABLE

        assert isinstance(HF_HUB_AVAILABLE, bool)
