"""Unit tests for GpuDetectionService.

This module contains comprehensive unit tests for the GpuDetectionService, which
detects available GPUs and their specifications using pynvml or nvidia-smi fallback.

Related Issues:
    - NEM-3317: Implement GPU detection service with pynvml

Test Organization:
    - Initialization tests: Service creation and configuration
    - GPU detection tests: pynvml, nvidia-smi fallback, no GPUs
    - GPU utilization tests: Real-time utilization queries
    - VRAM requirements tests: Hardcoded service estimates
    - Error handling tests: Graceful fallback on errors

Acceptance Criteria:
    - Service detects GPUs via pynvml when available
    - Falls back to nvidia-smi subprocess when pynvml unavailable
    - Returns empty list gracefully when no GPUs present
    - VRAM estimates defined for all AI services (YOLO26, Nemotron, Age/Gender, ReID)
    - Works in containerized environment
"""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from backend.services.gpu_detection_service import (
    AI_SERVICE_VRAM_REQUIREMENTS_MB,
    GpuDetectionService,
    GpuDevice,
    GpuUtilization,
    get_gpu_detection_service,
    reset_gpu_detection_service,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_pynvml() -> MagicMock:
    """Create a comprehensive mock for pynvml module."""
    mock_nvml = MagicMock()

    # Configure nvmlInit to succeed
    mock_nvml.nvmlInit.return_value = None
    mock_nvml.nvmlShutdown.return_value = None

    # Configure device count
    mock_nvml.nvmlDeviceGetCount.return_value = 2

    # Create mock handles for two GPUs
    mock_handle_0 = MagicMock()
    mock_handle_1 = MagicMock()

    def get_handle_by_index(index: int) -> MagicMock:
        if index == 0:
            return mock_handle_0
        elif index == 1:
            return mock_handle_1
        raise mock_nvml.NVMLError("Invalid GPU index")

    mock_nvml.nvmlDeviceGetHandleByIndex.side_effect = get_handle_by_index

    # GPU 0: RTX A5500 (24GB)
    mock_nvml.nvmlDeviceGetName.side_effect = lambda h: (
        "NVIDIA RTX A5500" if h == mock_handle_0 else "NVIDIA RTX A400"
    )
    mock_nvml.nvmlDeviceGetUUID.side_effect = lambda h: (
        "GPU-uuid-0-1234-5678" if h == mock_handle_0 else "GPU-uuid-1-abcd-efgh"
    )

    # Memory info
    mock_memory_0 = MagicMock()
    mock_memory_0.used = 8192 * 1024 * 1024  # 8 GB in bytes
    mock_memory_0.total = 24576 * 1024 * 1024  # 24 GB in bytes

    mock_memory_1 = MagicMock()
    mock_memory_1.used = 512 * 1024 * 1024  # 512 MB in bytes
    mock_memory_1.total = 4096 * 1024 * 1024  # 4 GB in bytes

    mock_nvml.nvmlDeviceGetMemoryInfo.side_effect = lambda h: (
        mock_memory_0 if h == mock_handle_0 else mock_memory_1
    )

    # Utilization rates
    mock_util_0 = MagicMock()
    mock_util_0.gpu = 75
    mock_util_0.memory = 45

    mock_util_1 = MagicMock()
    mock_util_1.gpu = 25
    mock_util_1.memory = 15

    mock_nvml.nvmlDeviceGetUtilizationRates.side_effect = lambda h: (
        mock_util_0 if h == mock_handle_0 else mock_util_1
    )

    # Temperature
    mock_nvml.nvmlDeviceGetTemperature.side_effect = lambda h, _: (65 if h == mock_handle_0 else 45)
    mock_nvml.NVML_TEMPERATURE_GPU = 0

    # Power usage (milliwatts)
    mock_nvml.nvmlDeviceGetPowerUsage.side_effect = lambda h: (
        150000 if h == mock_handle_0 else 35000
    )

    # Compute capability - both GPUs have same capability for consistency
    mock_nvml.nvmlDeviceGetCudaComputeCapability.return_value = (8, 6)

    # NVMLError exception class
    mock_nvml.NVMLError = Exception

    return mock_nvml


@pytest.fixture
def mock_pynvml_single_gpu() -> MagicMock:
    """Create a mock for pynvml with single GPU."""
    mock_nvml = MagicMock()
    mock_nvml.nvmlInit.return_value = None
    mock_nvml.nvmlShutdown.return_value = None
    mock_nvml.nvmlDeviceGetCount.return_value = 1

    mock_handle = MagicMock()
    mock_nvml.nvmlDeviceGetHandleByIndex.side_effect = lambda i: (
        mock_handle if i == 0 else Exception("Invalid index")
    )
    mock_nvml.nvmlDeviceGetName.return_value = "NVIDIA GeForce RTX 4090"
    mock_nvml.nvmlDeviceGetUUID.return_value = "GPU-4090-uuid"

    mock_memory = MagicMock()
    mock_memory.used = 4096 * 1024 * 1024
    mock_memory.total = 24576 * 1024 * 1024
    mock_nvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

    mock_nvml.nvmlDeviceGetCudaComputeCapability.return_value = (8, 9)
    mock_nvml.NVMLError = Exception

    return mock_nvml


@pytest.fixture
def mock_pynvml_no_gpus() -> MagicMock:
    """Create a mock for pynvml with no GPUs detected."""
    mock_nvml = MagicMock()
    mock_nvml.nvmlInit.return_value = None
    mock_nvml.nvmlShutdown.return_value = None
    mock_nvml.nvmlDeviceGetCount.return_value = 0
    mock_nvml.NVMLError = Exception

    return mock_nvml


@pytest.fixture
def mock_pynvml_init_fails() -> MagicMock:
    """Create a mock for pynvml where nvmlInit fails."""
    mock_nvml = MagicMock()
    mock_nvml.NVMLError = Exception
    mock_nvml.nvmlInit.side_effect = Exception("NVML initialization failed")

    return mock_nvml


@pytest.fixture
def nvidia_smi_output_two_gpus() -> str:
    """Sample nvidia-smi CSV output for two GPUs."""
    return """0, NVIDIA RTX A5500, 24576, 8192, GPU-uuid-0
1, NVIDIA RTX A400, 4096, 512, GPU-uuid-1
"""


@pytest.fixture
def nvidia_smi_output_single_gpu() -> str:
    """Sample nvidia-smi CSV output for single GPU."""
    return """0, NVIDIA GeForce RTX 4090, 24576, 4096, GPU-uuid-4090
"""


@pytest.fixture
def nvidia_smi_utilization_output() -> str:
    """Sample nvidia-smi utilization output."""
    return """75, 8192, 65, 150.5
"""


@pytest.fixture
def service_reset():
    """Reset service singleton before and after test."""
    reset_gpu_detection_service()
    yield
    reset_gpu_detection_service()


# =============================================================================
# GpuDevice Dataclass Tests
# =============================================================================


class TestGpuDevice:
    """Tests for GpuDevice dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a basic GpuDevice."""
        device = GpuDevice(
            index=0,
            name="NVIDIA RTX A5500",
            vram_total_mb=24576,
            vram_used_mb=8192,
            uuid="GPU-uuid-1234",
        )

        assert device.index == 0
        assert device.name == "NVIDIA RTX A5500"
        assert device.vram_total_mb == 24576
        assert device.vram_used_mb == 8192
        assert device.uuid == "GPU-uuid-1234"
        assert device.compute_capability is None

    def test_with_compute_capability(self) -> None:
        """Test GpuDevice with compute capability."""
        device = GpuDevice(
            index=0,
            name="NVIDIA RTX A5500",
            vram_total_mb=24576,
            vram_used_mb=8192,
            uuid="GPU-uuid-1234",
            compute_capability="8.6",
        )

        assert device.compute_capability == "8.6"

    def test_vram_available_property(self) -> None:
        """Test VRAM available calculation."""
        device = GpuDevice(
            index=0,
            name="Test GPU",
            vram_total_mb=24576,
            vram_used_mb=8192,
            uuid="GPU-uuid",
        )

        assert device.vram_available_mb == 16384

    def test_vram_usage_percent_property(self) -> None:
        """Test VRAM usage percentage calculation."""
        device = GpuDevice(
            index=0,
            name="Test GPU",
            vram_total_mb=24576,
            vram_used_mb=12288,  # 50%
            uuid="GPU-uuid",
        )

        assert device.vram_usage_percent == pytest.approx(50.0, rel=0.01)

    def test_vram_usage_percent_with_zero_total(self) -> None:
        """Test VRAM usage percentage when total is zero."""
        device = GpuDevice(
            index=0,
            name="Test GPU",
            vram_total_mb=0,
            vram_used_mb=0,
            uuid="GPU-uuid",
        )

        assert device.vram_usage_percent == 0.0


# =============================================================================
# GpuUtilization Dataclass Tests
# =============================================================================


class TestGpuUtilization:
    """Tests for GpuUtilization dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a basic GpuUtilization."""
        util = GpuUtilization(
            gpu_index=0,
            gpu_utilization_percent=75.0,
            memory_utilization_percent=45.0,
            vram_used_mb=8192,
            vram_total_mb=24576,
        )

        assert util.gpu_index == 0
        assert util.gpu_utilization_percent == 75.0
        assert util.memory_utilization_percent == 45.0
        assert util.vram_used_mb == 8192
        assert util.vram_total_mb == 24576
        assert util.temperature_celsius is None
        assert util.power_watts is None

    def test_with_optional_fields(self) -> None:
        """Test GpuUtilization with temperature and power."""
        util = GpuUtilization(
            gpu_index=0,
            gpu_utilization_percent=75.0,
            memory_utilization_percent=45.0,
            vram_used_mb=8192,
            vram_total_mb=24576,
            temperature_celsius=65.0,
            power_watts=150.5,
        )

        assert util.temperature_celsius == 65.0
        assert util.power_watts == 150.5


# =============================================================================
# GpuDetectionService Initialization Tests
# =============================================================================


class TestGpuDetectionServiceInit:
    """Tests for GpuDetectionService initialization."""

    def test_init_default(self, service_reset: None) -> None:
        """Test default initialization."""
        with patch.dict(sys.modules, {"pynvml": MagicMock()}):
            service = GpuDetectionService()

        assert service is not None
        assert service._nvml_available is not None  # Either True or False

    def test_singleton_pattern(self, service_reset: None) -> None:
        """Test that get_gpu_detection_service returns singleton."""
        with patch.dict(sys.modules, {"pynvml": MagicMock()}):
            service1 = get_gpu_detection_service()
            service2 = get_gpu_detection_service()

        assert service1 is service2

    def test_reset_clears_singleton(self, service_reset: None) -> None:
        """Test that reset_gpu_detection_service clears the singleton."""
        with patch.dict(sys.modules, {"pynvml": MagicMock()}):
            service1 = get_gpu_detection_service()
            reset_gpu_detection_service()
            service2 = get_gpu_detection_service()

        # After reset, should be a different instance
        assert service1 is not service2


# =============================================================================
# GPU Detection Tests - pynvml
# =============================================================================


class TestGpuDetectionPynvml:
    """Tests for GPU detection using pynvml."""

    @pytest.mark.asyncio
    async def test_detect_gpus_two_gpus(self, mock_pynvml: MagicMock, service_reset: None) -> None:
        """Test detecting two GPUs via pynvml."""
        with patch.dict(sys.modules, {"pynvml": mock_pynvml}):
            service = GpuDetectionService()
            gpus = await service.detect_gpus()

        assert len(gpus) == 2

        # GPU 0
        assert gpus[0].index == 0
        assert gpus[0].name == "NVIDIA RTX A5500"
        assert gpus[0].vram_total_mb == 24576
        assert gpus[0].vram_used_mb == 8192
        assert gpus[0].uuid == "GPU-uuid-0-1234-5678"
        assert gpus[0].compute_capability == "8.6"

        # GPU 1
        assert gpus[1].index == 1
        assert gpus[1].name == "NVIDIA RTX A400"
        assert gpus[1].vram_total_mb == 4096
        assert gpus[1].vram_used_mb == 512
        assert gpus[1].uuid == "GPU-uuid-1-abcd-efgh"

    @pytest.mark.asyncio
    async def test_detect_gpus_single_gpu(
        self, mock_pynvml_single_gpu: MagicMock, service_reset: None
    ) -> None:
        """Test detecting single GPU via pynvml."""
        with patch.dict(sys.modules, {"pynvml": mock_pynvml_single_gpu}):
            service = GpuDetectionService()
            gpus = await service.detect_gpus()

        assert len(gpus) == 1
        assert gpus[0].name == "NVIDIA GeForce RTX 4090"
        assert gpus[0].compute_capability == "8.9"

    @pytest.mark.asyncio
    async def test_detect_gpus_no_gpus_via_pynvml(
        self, mock_pynvml_no_gpus: MagicMock, service_reset: None
    ) -> None:
        """Test detecting no GPUs via pynvml returns empty list."""
        with patch.dict(sys.modules, {"pynvml": mock_pynvml_no_gpus}):
            service = GpuDetectionService()
            gpus = await service.detect_gpus()

        assert gpus == []

    @pytest.mark.asyncio
    async def test_detect_gpus_pynvml_init_fails_uses_fallback(
        self,
        mock_pynvml_init_fails: MagicMock,
        nvidia_smi_output_two_gpus: str,
        service_reset: None,
    ) -> None:
        """Test that service falls back to nvidia-smi when pynvml init fails."""
        with (
            patch.dict(sys.modules, {"pynvml": mock_pynvml_init_fails}),
            patch("shutil.which", return_value="/usr/bin/nvidia-smi"),
            patch("backend.services.gpu_detection_service.async_subprocess_run") as mock_run,
        ):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = nvidia_smi_output_two_gpus
            mock_run.return_value = mock_result

            service = GpuDetectionService()
            gpus = await service.detect_gpus()

        assert len(gpus) == 2
        assert gpus[0].name == "NVIDIA RTX A5500"


# =============================================================================
# GPU Detection Tests - nvidia-smi Fallback
# =============================================================================


class TestGpuDetectionNvidiaSmi:
    """Tests for GPU detection using nvidia-smi fallback."""

    @pytest.mark.asyncio
    async def test_detect_gpus_nvidia_smi_fallback(
        self, nvidia_smi_output_two_gpus: str, service_reset: None
    ) -> None:
        """Test detecting GPUs via nvidia-smi when pynvml unavailable."""
        with (
            patch("shutil.which", return_value="/usr/bin/nvidia-smi"),
            patch("backend.services.gpu_detection_service.async_subprocess_run") as mock_run,
        ):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = nvidia_smi_output_two_gpus
            mock_run.return_value = mock_result

            # Simulate pynvml being unavailable
            service = GpuDetectionService()
            service._nvml_available = False
            service._nvidia_smi_path = "/usr/bin/nvidia-smi"
            gpus = await service.detect_gpus()

        assert len(gpus) == 2
        assert gpus[0].index == 0
        assert gpus[0].name == "NVIDIA RTX A5500"
        assert gpus[0].vram_total_mb == 24576
        assert gpus[0].vram_used_mb == 8192

    @pytest.mark.asyncio
    async def test_detect_gpus_nvidia_smi_single_gpu(
        self, nvidia_smi_output_single_gpu: str, service_reset: None
    ) -> None:
        """Test detecting single GPU via nvidia-smi."""
        with (
            patch("shutil.which", return_value="/usr/bin/nvidia-smi"),
            patch("backend.services.gpu_detection_service.async_subprocess_run") as mock_run,
        ):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = nvidia_smi_output_single_gpu
            mock_run.return_value = mock_result

            service = GpuDetectionService()
            service._nvml_available = False
            service._nvidia_smi_path = "/usr/bin/nvidia-smi"
            gpus = await service.detect_gpus()

        assert len(gpus) == 1
        assert gpus[0].name == "NVIDIA GeForce RTX 4090"

    @pytest.mark.asyncio
    async def test_detect_gpus_nvidia_smi_not_found(self, service_reset: None) -> None:
        """Test that empty list returned when nvidia-smi not found."""
        with (
            patch("shutil.which", return_value=None),
            patch.dict(sys.modules, {}),
        ):
            service = GpuDetectionService()
            service._nvml_available = False
            service._nvidia_smi_path = None
            gpus = await service.detect_gpus()

        assert gpus == []

    @pytest.mark.asyncio
    async def test_detect_gpus_nvidia_smi_returns_error(self, service_reset: None) -> None:
        """Test graceful handling when nvidia-smi returns error."""
        with (
            patch("shutil.which", return_value="/usr/bin/nvidia-smi"),
            patch("backend.services.gpu_detection_service.async_subprocess_run") as mock_run,
        ):
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "NVIDIA driver not loaded"
            mock_run.return_value = mock_result

            service = GpuDetectionService()
            service._nvml_available = False
            service._nvidia_smi_path = "/usr/bin/nvidia-smi"
            gpus = await service.detect_gpus()

        assert gpus == []

    @pytest.mark.asyncio
    async def test_detect_gpus_nvidia_smi_timeout(self, service_reset: None) -> None:
        """Test graceful handling when nvidia-smi times out."""
        with (
            patch("shutil.which", return_value="/usr/bin/nvidia-smi"),
            patch("backend.services.gpu_detection_service.async_subprocess_run") as mock_run,
        ):
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=5)

            service = GpuDetectionService()
            service._nvml_available = False
            service._nvidia_smi_path = "/usr/bin/nvidia-smi"
            gpus = await service.detect_gpus()

        assert gpus == []


# =============================================================================
# GPU Utilization Tests
# =============================================================================


class TestGpuUtilizationQueries:
    """Tests for GPU utilization queries."""

    @pytest.mark.asyncio
    async def test_get_gpu_utilization_pynvml(
        self, mock_pynvml: MagicMock, service_reset: None
    ) -> None:
        """Test getting GPU utilization via pynvml."""
        with patch.dict(sys.modules, {"pynvml": mock_pynvml}):
            service = GpuDetectionService()
            util = await service.get_gpu_utilization(0)

        assert util is not None
        assert util.gpu_index == 0
        assert util.gpu_utilization_percent == 75
        assert util.memory_utilization_percent == 45
        assert util.vram_used_mb == 8192
        assert util.vram_total_mb == 24576
        assert util.temperature_celsius == 65
        assert util.power_watts == pytest.approx(150.0, rel=0.01)

    @pytest.mark.asyncio
    async def test_get_gpu_utilization_second_gpu(
        self, mock_pynvml: MagicMock, service_reset: None
    ) -> None:
        """Test getting utilization for second GPU."""
        with patch.dict(sys.modules, {"pynvml": mock_pynvml}):
            service = GpuDetectionService()
            util = await service.get_gpu_utilization(1)

        assert util is not None
        assert util.gpu_index == 1
        assert util.gpu_utilization_percent == 25
        assert util.memory_utilization_percent == 15
        assert util.vram_used_mb == 512
        assert util.vram_total_mb == 4096
        assert util.temperature_celsius == 45
        assert util.power_watts == pytest.approx(35.0, rel=0.01)

    @pytest.mark.asyncio
    async def test_get_gpu_utilization_invalid_index(
        self, mock_pynvml: MagicMock, service_reset: None
    ) -> None:
        """Test getting utilization for invalid GPU index returns None."""
        with patch.dict(sys.modules, {"pynvml": mock_pynvml}):
            service = GpuDetectionService()
            util = await service.get_gpu_utilization(99)

        assert util is None

    @pytest.mark.asyncio
    async def test_get_gpu_utilization_nvidia_smi_fallback(
        self, nvidia_smi_utilization_output: str, service_reset: None
    ) -> None:
        """Test getting GPU utilization via nvidia-smi fallback."""
        with (
            patch("shutil.which", return_value="/usr/bin/nvidia-smi"),
            patch("backend.services.gpu_detection_service.async_subprocess_run") as mock_run,
        ):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = nvidia_smi_utilization_output
            mock_run.return_value = mock_result

            service = GpuDetectionService()
            service._nvml_available = False
            service._nvidia_smi_path = "/usr/bin/nvidia-smi"
            util = await service.get_gpu_utilization(0)

        assert util is not None
        assert util.gpu_utilization_percent == 75
        assert util.vram_used_mb == 8192
        assert util.temperature_celsius == 65
        assert util.power_watts == pytest.approx(150.5, rel=0.01)


# =============================================================================
# VRAM Requirements Tests
# =============================================================================


class TestVramRequirements:
    """Tests for VRAM requirements estimates."""

    def test_get_service_vram_requirements_returns_dict(self, service_reset: None) -> None:
        """Test that get_service_vram_requirements returns a dict."""
        service = GpuDetectionService()
        requirements = service.get_service_vram_requirements()

        assert isinstance(requirements, dict)
        assert len(requirements) > 0

    def test_yolo26_vram_requirement(self, service_reset: None) -> None:
        """Test YOLO26 detector VRAM requirement (~100MB TensorRT)."""
        service = GpuDetectionService()
        requirements = service.get_service_vram_requirements()

        assert "ai-yolo26" in requirements
        assert requirements["ai-yolo26"] == 100  # ~100 MB TensorRT engine

    def test_nemotron_vram_requirement(self, service_reset: None) -> None:
        """Test Nemotron enrichment VRAM requirement (~8GB)."""
        service = GpuDetectionService()
        requirements = service.get_service_vram_requirements()

        assert "ai-llm" in requirements
        assert requirements["ai-llm"] == 8192  # 8 GB in MB

    def test_age_gender_vram_requirement(self, service_reset: None) -> None:
        """Test Age/Gender models VRAM requirement (~1GB each)."""
        service = GpuDetectionService()
        requirements = service.get_service_vram_requirements()

        # Age and Gender models are part of the enrichment service
        assert "ai-enrichment" in requirements
        # Enrichment includes multiple models
        assert requirements["ai-enrichment"] >= 1024  # At least 1 GB

    def test_reid_vram_requirement(self, service_reset: None) -> None:
        """Test ReID model VRAM requirement (~1GB)."""
        service = GpuDetectionService()
        requirements = service.get_service_vram_requirements()

        # ReID is part of enrichment service
        assert "ai-enrichment" in requirements

    def test_all_ai_services_have_requirements(self, service_reset: None) -> None:
        """Test that all AI services have VRAM requirements defined."""
        service = GpuDetectionService()
        requirements = service.get_service_vram_requirements()

        expected_services = [
            "ai-llm",
            "ai-yolo26",
            "ai-enrichment",
            "ai-florence",
            "ai-clip",
        ]

        for svc in expected_services:
            assert svc in requirements, f"Missing VRAM requirement for {svc}"
            assert requirements[svc] > 0, f"VRAM requirement for {svc} should be positive"

    def test_module_constant_defined(self) -> None:
        """Test that AI_SERVICE_VRAM_REQUIREMENTS_MB constant is defined."""
        assert AI_SERVICE_VRAM_REQUIREMENTS_MB is not None
        assert isinstance(AI_SERVICE_VRAM_REQUIREMENTS_MB, dict)
        assert "ai-llm" in AI_SERVICE_VRAM_REQUIREMENTS_MB


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling and graceful degradation."""

    @pytest.mark.asyncio
    async def test_detect_gpus_handles_pynvml_exception(self, service_reset: None) -> None:
        """Test that detect_gpus handles pynvml exceptions gracefully."""
        mock_nvml = MagicMock()
        mock_nvml.nvmlInit.return_value = None
        mock_nvml.nvmlDeviceGetCount.side_effect = Exception("NVML error")
        mock_nvml.NVMLError = Exception

        with (
            patch.dict(sys.modules, {"pynvml": mock_nvml}),
            patch("shutil.which", return_value=None),  # No nvidia-smi fallback
        ):
            service = GpuDetectionService()
            service._nvidia_smi_path = None  # Ensure no fallback
            gpus = await service.detect_gpus()

        # Should return empty list, not raise
        assert gpus == []

    @pytest.mark.asyncio
    async def test_detect_gpus_handles_partial_failure(self, service_reset: None) -> None:
        """Test that detect_gpus handles partial GPU query failures."""
        mock_nvml = MagicMock()
        mock_nvml.nvmlInit.return_value = None
        mock_nvml.nvmlDeviceGetCount.return_value = 2
        mock_nvml.NVMLError = Exception

        mock_handle_0 = MagicMock()
        mock_handle_1 = MagicMock()

        mock_nvml.nvmlDeviceGetHandleByIndex.side_effect = lambda i: (
            mock_handle_0 if i == 0 else mock_handle_1
        )

        # GPU 0 works fine
        mock_nvml.nvmlDeviceGetName.side_effect = lambda h: (
            "GPU 0" if h == mock_handle_0 else Exception("Failed")
        )
        mock_nvml.nvmlDeviceGetUUID.side_effect = lambda h: (
            "uuid-0" if h == mock_handle_0 else Exception("Failed")
        )

        mock_memory = MagicMock()
        mock_memory.used = 1024 * 1024 * 1024
        mock_memory.total = 8192 * 1024 * 1024
        mock_nvml.nvmlDeviceGetMemoryInfo.side_effect = lambda h: (
            mock_memory if h == mock_handle_0 else Exception("Failed")
        )
        mock_nvml.nvmlDeviceGetCudaComputeCapability.return_value = (8, 0)

        with patch.dict(sys.modules, {"pynvml": mock_nvml}):
            service = GpuDetectionService()
            gpus = await service.detect_gpus()

        # Should return at least GPU 0
        assert len(gpus) >= 1
        assert gpus[0].name == "GPU 0"

    @pytest.mark.asyncio
    async def test_get_utilization_handles_no_gpu_access(self, service_reset: None) -> None:
        """Test that get_gpu_utilization returns None when no GPU access."""
        with (
            patch("shutil.which", return_value=None),
        ):
            service = GpuDetectionService()
            service._nvml_available = False
            service._nvidia_smi_path = None
            util = await service.get_gpu_utilization(0)

        assert util is None


# =============================================================================
# Container Environment Tests
# =============================================================================


class TestContainerEnvironment:
    """Tests for containerized environment support."""

    @pytest.mark.asyncio
    async def test_detect_gpus_uses_nvidia_smi_in_container(
        self, nvidia_smi_output_single_gpu: str, service_reset: None
    ) -> None:
        """Test GPU detection works via nvidia-smi in container (no pynvml)."""
        # Simulate container environment: no pynvml but nvidia-smi available
        with (
            patch("shutil.which", return_value="/usr/bin/nvidia-smi"),
            patch("backend.services.gpu_detection_service.async_subprocess_run") as mock_run,
        ):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = nvidia_smi_output_single_gpu
            mock_run.return_value = mock_result

            service = GpuDetectionService()
            service._nvml_available = False
            service._nvidia_smi_path = "/usr/bin/nvidia-smi"
            gpus = await service.detect_gpus()

        assert len(gpus) == 1
        assert "NVIDIA" in gpus[0].name

    @pytest.mark.asyncio
    async def test_detect_gpus_no_gpu_in_container(self, service_reset: None) -> None:
        """Test graceful handling when no GPU in container."""
        # Simulate container with no GPU access at all
        with (
            patch("shutil.which", return_value=None),
        ):
            service = GpuDetectionService()
            service._nvml_available = False
            service._nvidia_smi_path = None
            gpus = await service.detect_gpus()

        assert gpus == []


# =============================================================================
# Integration-style Tests
# =============================================================================


class TestGpuDetectionIntegration:
    """Integration-style tests for GpuDetectionService."""

    @pytest.mark.asyncio
    async def test_full_workflow_two_gpus(
        self, mock_pynvml: MagicMock, service_reset: None
    ) -> None:
        """Test full workflow: detect GPUs and get utilization."""
        with patch.dict(sys.modules, {"pynvml": mock_pynvml}):
            service = GpuDetectionService()

            # Detect GPUs
            gpus = await service.detect_gpus()
            assert len(gpus) == 2

            # Get utilization for each
            for gpu in gpus:
                util = await service.get_gpu_utilization(gpu.index)
                assert util is not None
                assert util.gpu_index == gpu.index

            # Get VRAM requirements
            requirements = service.get_service_vram_requirements()
            assert len(requirements) > 0

    @pytest.mark.asyncio
    async def test_detect_after_gpu_failure_and_recovery(
        self, mock_pynvml: MagicMock, service_reset: None
    ) -> None:
        """Test that detection works after GPU failure and recovery."""
        with patch.dict(sys.modules, {"pynvml": mock_pynvml}):
            service = GpuDetectionService()

            # First detection succeeds
            gpus1 = await service.detect_gpus()
            assert len(gpus1) == 2

            # Simulate failure by making device count return 0 temporarily
            original_count = mock_pynvml.nvmlDeviceGetCount.return_value
            mock_pynvml.nvmlDeviceGetCount.return_value = 0

            gpus2 = await service.detect_gpus()
            assert len(gpus2) == 0

            # Restore and verify recovery
            mock_pynvml.nvmlDeviceGetCount.return_value = original_count
            gpus3 = await service.detect_gpus()
            assert len(gpus3) == 2
