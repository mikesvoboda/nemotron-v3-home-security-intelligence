"""Integration tests for GPU configuration workflow.

This module tests the complete end-to-end GPU configuration workflow:
1. GPU detection and database persistence
2. Configuration updates with validation
3. Auto-assignment strategy calculations
4. Override file generation
5. Configuration application and status monitoring
6. Error recovery and rollback

These tests verify multi-component integration including:
- GpuDetectionService with database updates
- GpuConfigService for file generation
- API routes for workflow orchestration
- Database transactions and persistence
- Strategy calculation algorithms

Test Setup:
- Uses real PostgreSQL database via integration_db fixture
- Mocks pynvml and nvidia-smi for GPU detection
- Uses temporary directory for override file generation
- Mocks container operations (restart commands)

Related Issues:
    - NEM-3324: Add integration tests for GPU configuration workflow
    - NEM-3292: Multi-GPU Support Epic
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from httpx import AsyncClient

from backend.api.schemas.gpu_config import GpuAssignmentStrategy
from backend.models.gpu_config import (
    GpuConfiguration,
    SystemSetting,
)
from backend.models.gpu_config import (
    GpuDevice as GpuDeviceModel,
)
from backend.services.gpu_config_service import (
    GpuAssignment,
    GpuConfigService,
)
from backend.services.gpu_detection_service import (
    GpuDetectionService,
    GpuDevice,
    reset_gpu_detection_service,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


pytestmark = pytest.mark.integration


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_config_dir() -> Path:
    """Create a temporary directory for GPU config files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_pynvml():
    """Mock pynvml library for GPU detection."""
    mock_pynvml = MagicMock()

    # Mock GPU count
    mock_pynvml.nvmlDeviceGetCount.return_value = 2

    # Mock GPU 0 (NVIDIA RTX A5500 - 24GB)
    mock_handle_0 = MagicMock()
    mock_pynvml.nvmlDeviceGetHandleByIndex.side_effect = lambda idx: (
        mock_handle_0 if idx == 0 else mock_handle_1
    )

    mock_pynvml.nvmlDeviceGetName.side_effect = lambda h: (
        b"NVIDIA RTX A5500" if h == mock_handle_0 else b"NVIDIA RTX 4090"
    )
    mock_pynvml.nvmlDeviceGetUUID.side_effect = lambda h: (
        b"GPU-00000000-0000-0000-0000-000000000000"
        if h == mock_handle_0
        else b"GPU-11111111-1111-1111-1111-111111111111"
    )

    # Mock GPU 1 (NVIDIA RTX 4090 - 48GB)
    mock_handle_1 = MagicMock()

    # Mock memory info
    def mock_memory_info(handle):
        memory = MagicMock()
        if handle == mock_handle_0:
            memory.total = 24 * 1024 * 1024 * 1024  # 24GB in bytes
            memory.used = 1024 * 1024 * 1024  # 1GB used
        else:
            memory.total = 48 * 1024 * 1024 * 1024  # 48GB in bytes
            memory.used = 2 * 1024 * 1024 * 1024  # 2GB used
        return memory

    mock_pynvml.nvmlDeviceGetMemoryInfo.side_effect = mock_memory_info

    # Mock compute capability
    def mock_compute_capability(handle):
        if handle == mock_handle_0:
            return (8, 6)  # Ampere
        else:
            return (8, 9)  # Ada Lovelace
        return None

    mock_pynvml.nvmlDeviceGetCudaComputeCapability.side_effect = mock_compute_capability

    # Mock nvmlInit
    mock_pynvml.nvmlInit.return_value = None

    # Mock utilization rates
    def mock_utilization_rates(handle):
        util = MagicMock()
        if handle == mock_handle_0:
            util.gpu = 25
            util.memory = 10
        else:
            util.gpu = 50
            util.memory = 20
        return util

    mock_pynvml.nvmlDeviceGetUtilizationRates.side_effect = mock_utilization_rates

    # Mock temperature
    mock_pynvml.nvmlDeviceGetTemperature.return_value = 65.0
    mock_pynvml.NVML_TEMPERATURE_GPU = 0

    # Mock power
    mock_pynvml.nvmlDeviceGetPowerUsage.return_value = 150000  # 150W in milliwatts

    # Patch sys.modules to intercept the dynamic import of pynvml
    # (pynvml is not imported at module level in gpu_detection_service.py)
    with patch.dict("sys.modules", {"pynvml": mock_pynvml}):
        yield mock_pynvml


@pytest.fixture
async def gpu_detection_service(mock_pynvml):
    """Create a GPU detection service with mocked pynvml."""
    reset_gpu_detection_service()
    service = GpuDetectionService()
    # Force pynvml to be available
    service._pynvml = mock_pynvml
    service._nvml_available = True
    service._nvml_initialized = True
    yield service
    reset_gpu_detection_service()


@pytest.fixture
def gpu_config_service(temp_config_dir: Path) -> GpuConfigService:
    """Create a GPU config service with temp directory."""
    return GpuConfigService(config_dir=temp_config_dir)


@pytest.fixture
def sample_gpus() -> list[GpuDevice]:
    """Sample GPU devices for testing."""
    return [
        GpuDevice(
            index=0,
            name="NVIDIA RTX A5500",
            vram_total_mb=24576,  # 24GB
            vram_used_mb=1024,  # 1GB
            uuid="GPU-00000000-0000-0000-0000-000000000000",
            compute_capability="8.6",
        ),
        GpuDevice(
            index=1,
            name="NVIDIA RTX 4090",
            vram_total_mb=49152,  # 48GB
            vram_used_mb=2048,  # 2GB
            uuid="GPU-11111111-1111-1111-1111-111111111111",
            compute_capability="8.9",
        ),
    ]


# =============================================================================
# Test 1: Full Configuration Workflow
# =============================================================================


class TestFullConfigurationWorkflow:
    """Test the complete GPU configuration workflow end-to-end."""

    @pytest.mark.asyncio
    async def test_detect_update_preview_apply_verify(
        self,
        db_session: AsyncSession,
        gpu_detection_service: GpuDetectionService,
        gpu_config_service: GpuConfigService,
        temp_config_dir: Path,
    ) -> None:
        """Test full workflow: detect → update config → preview strategy → apply → verify.

        This is the primary integration test that verifies the complete workflow
        a user would follow when configuring GPU assignments.
        """
        # Step 1: Detect GPUs
        gpus = await gpu_detection_service.detect_gpus()
        assert len(gpus) == 2
        assert gpus[0].name == "NVIDIA RTX A5500"
        assert gpus[1].name == "NVIDIA RTX 4090"

        # Verify VRAM calculations
        assert gpus[0].vram_available_mb == 23552  # 24GB - 1GB used
        assert gpus[1].vram_available_mb == 47104  # 48GB - 2GB used

        # Step 2: Update database with detected GPUs
        await self._save_gpus_to_db(db_session, gpus)
        await db_session.commit()

        # Verify database persistence
        db_gpus = await self._get_gpus_from_db(db_session)
        assert len(db_gpus) == 2
        assert db_gpus[0].gpu_index == 0
        assert db_gpus[1].gpu_index == 1

        # Step 3: Create and save configuration assignments
        assignments = [
            GpuAssignment(service_name="ai-llm", gpu_index=1, vram_budget_override=None),
            GpuAssignment(service_name="ai-yolo26", gpu_index=0, vram_budget_override=None),
            GpuAssignment(service_name="ai-enrichment", gpu_index=0, vram_budget_override=None),
        ]

        await self._save_assignments_to_db(db_session, assignments, GpuAssignmentStrategy.MANUAL)
        await db_session.commit()

        # Verify assignments persisted
        db_configs = await self._get_assignments_from_db(db_session)
        assert len(db_configs) == 3
        assert db_configs[0].service_name == "ai-llm"
        assert db_configs[0].gpu_index == 1

        # Step 4: Preview auto-assignment strategy
        from backend.api.routes.gpu_config import _calculate_auto_assignments

        vram_assignments, _warnings = _calculate_auto_assignments(
            GpuAssignmentStrategy.VRAM_BASED, gpus
        )
        assert len(vram_assignments) == 5  # All known services
        # LLM should be on larger GPU (index 1)
        llm_assignment = next(a for a in vram_assignments if a.service == "ai-llm")
        assert llm_assignment.gpu_index == 1

        # Step 5: Generate override files
        override_path, assignments_path = await gpu_config_service.write_config_files(
            assignments=assignments,
            strategy=GpuAssignmentStrategy.MANUAL.value,
        )

        # Verify files were created
        assert override_path.exists()
        assert assignments_path.exists()

        # Verify override file content
        override_content = yaml.safe_load(override_path.read_text())
        assert "services" in override_content
        assert "ai-llm" in override_content["services"]
        assert override_content["services"]["ai-llm"]["deploy"]["resources"]["reservations"][
            "devices"
        ][0]["device_ids"] == ["1"]

        # Verify assignments file content
        assignments_content = yaml.safe_load(assignments_path.read_text())
        assert assignments_content["strategy"] == "manual"
        assert "ai-llm" in assignments_content["assignments"]
        assert assignments_content["assignments"]["ai-llm"]["gpu"] == 1

        # Step 6: Verify configuration status
        # In a full implementation, this would check service restart status
        # For now, verify file integrity
        assert override_path.stat().st_size > 0
        assert "# Auto-generated" in override_path.read_text()

    async def _save_gpus_to_db(self, db: AsyncSession, devices: list[GpuDevice]) -> None:
        """Helper to save GPU devices to database."""
        now = datetime.now(UTC)
        for device in devices:
            db_device = GpuDeviceModel(
                gpu_index=device.index,
                name=device.name,
                vram_total_mb=device.vram_total_mb,
                vram_available_mb=device.vram_available_mb,
                compute_capability=device.compute_capability,
                last_seen_at=now,
            )
            db.add(db_device)

    async def _get_gpus_from_db(self, db: AsyncSession) -> list[GpuDeviceModel]:
        """Helper to retrieve GPU devices from database."""
        from sqlalchemy import select

        result = await db.execute(select(GpuDeviceModel).order_by(GpuDeviceModel.gpu_index))
        return list(result.scalars().all())

    async def _save_assignments_to_db(
        self,
        db: AsyncSession,
        assignments: list[GpuAssignment],
        strategy: GpuAssignmentStrategy,
    ) -> None:
        """Helper to save GPU assignments to database."""
        for assignment in assignments:
            config = GpuConfiguration(
                service_name=assignment.service_name,
                gpu_index=assignment.gpu_index,
                strategy=strategy.value,
                vram_budget_override=assignment.vram_budget_override,
                enabled=True,
            )
            db.add(config)

    async def _get_assignments_from_db(self, db: AsyncSession) -> list[GpuConfiguration]:
        """Helper to retrieve GPU assignments from database."""
        from sqlalchemy import select

        result = await db.execute(select(GpuConfiguration).order_by(GpuConfiguration.service_name))
        return list(result.scalars().all())


# =============================================================================
# Test 2: Database Integration
# =============================================================================


class TestDatabaseIntegration:
    """Test database operations for GPU configuration."""

    @pytest.mark.asyncio
    async def test_gpu_devices_persisted_correctly(
        self, db_session: AsyncSession, sample_gpus: list[GpuDevice]
    ) -> None:
        """Test that GPU devices are saved and retrieved from database correctly."""
        # Save GPUs
        now = datetime.now(UTC)
        for gpu in sample_gpus:
            db_device = GpuDeviceModel(
                gpu_index=gpu.index,
                name=gpu.name,
                vram_total_mb=gpu.vram_total_mb,
                vram_available_mb=gpu.vram_available_mb,
                compute_capability=gpu.compute_capability,
                last_seen_at=now,
            )
            db_session.add(db_device)

        await db_session.commit()

        # Retrieve and verify
        from sqlalchemy import select

        result = await db_session.execute(select(GpuDeviceModel).order_by(GpuDeviceModel.gpu_index))
        db_gpus = result.scalars().all()

        assert len(db_gpus) == 2
        assert db_gpus[0].gpu_index == 0
        assert db_gpus[0].name == "NVIDIA RTX A5500"
        assert db_gpus[0].vram_total_mb == 24576
        assert db_gpus[1].gpu_index == 1
        assert db_gpus[1].name == "NVIDIA RTX 4090"
        assert db_gpus[1].vram_total_mb == 49152

    @pytest.mark.asyncio
    async def test_configuration_assignments_saved_with_strategy(
        self, db_session: AsyncSession
    ) -> None:
        """Test that GPU configuration assignments are persisted with strategy."""
        # Create configurations
        configs = [
            GpuConfiguration(
                service_name="ai-llm",
                gpu_index=0,
                strategy=GpuAssignmentStrategy.VRAM_BASED.value,
                vram_budget_override=None,
                enabled=True,
            ),
            GpuConfiguration(
                service_name="ai-yolo26",
                gpu_index=1,
                strategy=GpuAssignmentStrategy.VRAM_BASED.value,
                vram_budget_override=2.5,  # 2.5GB override
                enabled=True,
            ),
        ]

        for config in configs:
            db_session.add(config)

        await db_session.commit()

        # Retrieve and verify
        from sqlalchemy import select

        result = await db_session.execute(
            select(GpuConfiguration).order_by(GpuConfiguration.service_name)
        )
        db_configs = result.scalars().all()

        assert len(db_configs) == 2
        assert db_configs[0].service_name == "ai-yolo26"
        assert db_configs[0].gpu_index == 1
        assert db_configs[0].vram_budget_override == 2.5
        assert db_configs[1].service_name == "ai-llm"
        assert db_configs[1].strategy == GpuAssignmentStrategy.VRAM_BASED.value

    @pytest.mark.asyncio
    async def test_system_settings_stored_correctly(self, db_session: AsyncSession) -> None:
        """Test that system settings (strategy) are stored in database."""
        # Save strategy setting
        setting = SystemSetting(
            key="gpu_assignment_strategy",
            value={"strategy": GpuAssignmentStrategy.ISOLATION_FIRST.value},
        )
        db_session.add(setting)
        await db_session.commit()

        # Retrieve and verify
        from sqlalchemy import select

        result = await db_session.execute(
            select(SystemSetting).where(SystemSetting.key == "gpu_assignment_strategy")
        )
        db_setting = result.scalar_one()

        assert db_setting.key == "gpu_assignment_strategy"
        assert db_setting.value["strategy"] == GpuAssignmentStrategy.ISOLATION_FIRST.value

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(
        self, db_session: AsyncSession, sample_gpus: list[GpuDevice]
    ) -> None:
        """Test that database transactions rollback correctly on error."""
        from sqlalchemy.exc import IntegrityError

        # Save first GPU successfully
        db_device_1 = GpuDeviceModel(
            gpu_index=0,
            name=sample_gpus[0].name,
            vram_total_mb=sample_gpus[0].vram_total_mb,
            vram_available_mb=sample_gpus[0].vram_available_mb,
            compute_capability=sample_gpus[0].compute_capability,
            last_seen_at=datetime.now(UTC),
        )
        db_session.add(db_device_1)
        await db_session.commit()

        # Try to add duplicate gpu_index (should fail due to unique constraint)
        try:
            db_device_2 = GpuDeviceModel(
                gpu_index=0,  # Duplicate!
                name="Duplicate GPU",
                vram_total_mb=8192,
                vram_available_mb=8192,
                compute_capability="8.0",
                last_seen_at=datetime.now(UTC),
            )
            db_session.add(db_device_2)
            await db_session.commit()
            pytest.fail("Should have raised IntegrityError")
        except IntegrityError:
            await db_session.rollback()

        # Verify original GPU still exists and no duplicate was added
        from sqlalchemy import select

        result = await db_session.execute(select(GpuDeviceModel))
        db_gpus = result.scalars().all()
        assert len(db_gpus) == 1
        assert db_gpus[0].name == sample_gpus[0].name


# =============================================================================
# Test 3: Override File Generation
# =============================================================================


class TestOverrideFileGeneration:
    """Test docker-compose override file generation."""

    @pytest.mark.asyncio
    async def test_file_created_at_correct_path(
        self, gpu_config_service: GpuConfigService, temp_config_dir: Path
    ) -> None:
        """Test that override files are created at the expected paths."""
        assignments = [GpuAssignment(service_name="ai-llm", gpu_index=0, vram_budget_override=None)]

        override_path, assignments_path = await gpu_config_service.write_config_files(
            assignments=assignments,
            strategy=GpuAssignmentStrategy.MANUAL.value,
        )

        assert override_path == temp_config_dir / "docker-compose.gpu-override.yml"
        assert assignments_path == temp_config_dir / "gpu-assignments.yml"
        assert override_path.exists()
        assert assignments_path.exists()

    @pytest.mark.asyncio
    async def test_yaml_structure_valid(self, gpu_config_service: GpuConfigService) -> None:
        """Test that generated YAML files have valid structure."""
        assignments = [
            GpuAssignment(service_name="ai-llm", gpu_index=1, vram_budget_override=None),
            GpuAssignment(service_name="ai-yolo26", gpu_index=0, vram_budget_override=2.0),
        ]

        override_path, assignments_path = await gpu_config_service.write_config_files(
            assignments=assignments,
            strategy=GpuAssignmentStrategy.VRAM_BASED.value,
        )

        # Parse and validate override file
        override_content = yaml.safe_load(override_path.read_text())
        assert "services" in override_content
        assert "ai-llm" in override_content["services"]
        assert "ai-yolo26" in override_content["services"]

        # Verify LLM configuration
        llm_config = override_content["services"]["ai-llm"]
        assert "deploy" in llm_config
        assert "resources" in llm_config["deploy"]
        devices = llm_config["deploy"]["resources"]["reservations"]["devices"]
        assert len(devices) == 1
        assert devices[0]["driver"] == "nvidia"
        assert devices[0]["device_ids"] == ["1"]
        assert devices[0]["capabilities"] == ["gpu"]

        # Verify detector configuration has VRAM override
        detector_config = override_content["services"]["ai-yolo26"]
        assert "environment" in detector_config
        assert "VRAM_BUDGET_GB=2.0" in detector_config["environment"]

        # Parse and validate assignments file
        assignments_content = yaml.safe_load(assignments_path.read_text())
        assert "strategy" in assignments_content
        assert assignments_content["strategy"] == "vram_based"
        assert "assignments" in assignments_content
        assert assignments_content["assignments"]["ai-llm"]["gpu"] == 1
        assert assignments_content["assignments"]["ai-yolo26"]["vram_budget"] == 2.0

    @pytest.mark.asyncio
    async def test_environment_variables_included_when_override_set(
        self, gpu_config_service: GpuConfigService
    ) -> None:
        """Test that VRAM_BUDGET_GB env var is included when override is set."""
        assignments = [
            GpuAssignment(service_name="ai-enrichment", gpu_index=0, vram_budget_override=3.5),
        ]

        override_path, _ = await gpu_config_service.write_config_files(
            assignments=assignments,
            strategy=GpuAssignmentStrategy.MANUAL.value,
        )

        override_content = yaml.safe_load(override_path.read_text())
        enrichment_config = override_content["services"]["ai-enrichment"]

        assert "environment" in enrichment_config
        assert "VRAM_BUDGET_GB=3.5" in enrichment_config["environment"]

    @pytest.mark.asyncio
    async def test_environment_variables_not_included_when_no_override(
        self, gpu_config_service: GpuConfigService
    ) -> None:
        """Test that VRAM_BUDGET_GB env var is excluded when no override."""
        assignments = [
            GpuAssignment(service_name="ai-llm", gpu_index=0, vram_budget_override=None),
        ]

        override_path, _ = await gpu_config_service.write_config_files(
            assignments=assignments,
            strategy=GpuAssignmentStrategy.MANUAL.value,
        )

        override_content = yaml.safe_load(override_path.read_text())
        llm_config = override_content["services"]["ai-llm"]

        assert "environment" not in llm_config


# =============================================================================
# Test 4: Error Recovery
# =============================================================================


class TestErrorRecovery:
    """Test error handling and recovery mechanisms."""

    @pytest.mark.asyncio
    async def test_database_error_rolls_back_transaction(self, db_session: AsyncSession) -> None:
        """Test that database errors trigger proper rollback."""
        from sqlalchemy import select
        from sqlalchemy.exc import IntegrityError

        # Create initial valid config
        config1 = GpuConfiguration(
            service_name="ai-llm",
            gpu_index=0,
            strategy=GpuAssignmentStrategy.MANUAL.value,
            enabled=True,
        )
        db_session.add(config1)
        await db_session.commit()

        # Try to add duplicate (unique constraint on service_name)
        try:
            config2 = GpuConfiguration(
                service_name="ai-llm",  # Duplicate!
                gpu_index=1,
                strategy=GpuAssignmentStrategy.MANUAL.value,
                enabled=True,
            )
            db_session.add(config2)
            await db_session.commit()
            pytest.fail("Should have raised IntegrityError")
        except IntegrityError:
            await db_session.rollback()

        # Verify only original config exists
        result = await db_session.execute(select(GpuConfiguration))
        configs = result.scalars().all()
        assert len(configs) == 1
        assert configs[0].gpu_index == 0

    @pytest.mark.asyncio
    async def test_file_write_error_does_not_corrupt_state(self, temp_config_dir: Path) -> None:
        """Test that file write errors don't leave corrupted files."""
        # Create service with invalid path (read-only parent)
        invalid_dir = temp_config_dir / "readonly"
        invalid_dir.mkdir()
        invalid_dir.chmod(0o444)  # Read-only

        service = GpuConfigService(config_dir=invalid_dir / "config")

        assignments = [GpuAssignment(service_name="ai-llm", gpu_index=0, vram_budget_override=None)]

        # Should raise OSError due to permission denied
        with pytest.raises(OSError):
            await service.write_config_files(
                assignments=assignments,
                strategy=GpuAssignmentStrategy.MANUAL.value,
            )

        # Verify no partial files were created
        assert not (invalid_dir / "config" / "docker-compose.gpu-override.yml").exists()
        assert not (invalid_dir / "config" / "gpu-assignments.yml").exists()

        # Cleanup
        invalid_dir.chmod(0o755)


# =============================================================================
# Test 5: Strategy Calculations
# =============================================================================


class TestStrategyCalculations:
    """Test auto-assignment strategy calculation algorithms."""

    @pytest.mark.asyncio
    async def test_vram_based_strategy_assigns_largest_to_biggest_gpu(
        self, sample_gpus: list[GpuDevice]
    ) -> None:
        """Test VRAM-based strategy assigns largest models to GPU with most VRAM."""
        from backend.api.routes.gpu_config import _calculate_auto_assignments

        assignments, _warnings = _calculate_auto_assignments(
            GpuAssignmentStrategy.VRAM_BASED, sample_gpus
        )

        # LLM (8GB) should be on GPU 1 (48GB)
        llm_assignment = next(a for a in assignments if a.service == "ai-llm")
        assert llm_assignment.gpu_index == 1

        # Smaller models should pack on GPU 1 first, then GPU 0
        # GPU 1: ai-llm (8GB) + ai-florence (4GB) = 12GB < 48GB ✓
        # GPU 0: smaller models
        florence_assignment = next(a for a in assignments if a.service == "ai-florence")
        assert florence_assignment.gpu_index == 1

    @pytest.mark.asyncio
    async def test_latency_optimized_assigns_detector_to_fastest_gpu(
        self, sample_gpus: list[GpuDevice]
    ) -> None:
        """Test latency-optimized strategy assigns critical models to fastest GPU."""
        from backend.api.routes.gpu_config import _calculate_auto_assignments

        assignments, _warnings = _calculate_auto_assignments(
            GpuAssignmentStrategy.LATENCY_OPTIMIZED, sample_gpus
        )

        # Detector (critical path) should be on fastest GPU (highest compute capability)
        # GPU 1 has compute capability 8.9 (fastest)
        detector_assignment = next(a for a in assignments if a.service == "ai-yolo26")
        assert detector_assignment.gpu_index == 1

        # Enrichment (also critical) should be on fastest GPU
        enrichment_assignment = next(a for a in assignments if a.service == "ai-enrichment")
        assert enrichment_assignment.gpu_index == 1

    @pytest.mark.asyncio
    async def test_isolation_first_dedicates_gpu_to_llm(self, sample_gpus: list[GpuDevice]) -> None:
        """Test isolation-first strategy dedicates largest GPU to LLM."""
        from backend.api.routes.gpu_config import _calculate_auto_assignments

        assignments, _warnings = _calculate_auto_assignments(
            GpuAssignmentStrategy.ISOLATION_FIRST, sample_gpus
        )

        # LLM should get dedicated GPU (largest = GPU 1)
        llm_assignment = next(a for a in assignments if a.service == "ai-llm")
        assert llm_assignment.gpu_index == 1

        # All other services should share GPU 0
        other_services = [a for a in assignments if a.service != "ai-llm"]
        for assignment in other_services:
            assert assignment.gpu_index == 0

    @pytest.mark.asyncio
    async def test_balanced_strategy_distributes_evenly(self, sample_gpus: list[GpuDevice]) -> None:
        """Test balanced strategy distributes VRAM usage evenly across GPUs."""
        from backend.api.routes.gpu_config import _calculate_auto_assignments

        assignments, _warnings = _calculate_auto_assignments(
            GpuAssignmentStrategy.BALANCED, sample_gpus
        )

        # Calculate VRAM usage per GPU
        from backend.services.gpu_detection_service import AI_SERVICE_VRAM_REQUIREMENTS_MB

        gpu_usage = {0: 0, 1: 0}
        for assignment in assignments:
            vram_mb = AI_SERVICE_VRAM_REQUIREMENTS_MB.get(assignment.service, 0)
            if assignment.gpu_index is not None:
                gpu_usage[assignment.gpu_index] += vram_mb

        # Both GPUs should have some assignments
        assert gpu_usage[0] > 0
        assert gpu_usage[1] > 0

        # Usage should be relatively balanced (within 50% of each other)
        ratio = min(gpu_usage[0], gpu_usage[1]) / max(gpu_usage[0], gpu_usage[1])
        assert ratio > 0.5, f"Imbalanced distribution: {gpu_usage}"

    @pytest.mark.asyncio
    async def test_strategy_with_single_gpu_handles_gracefully(self) -> None:
        """Test that strategies handle single GPU scenario gracefully."""
        from backend.api.routes.gpu_config import _calculate_auto_assignments

        single_gpu = [
            GpuDevice(
                index=0,
                name="NVIDIA RTX A5500",
                vram_total_mb=24576,
                vram_used_mb=1024,
                uuid="GPU-00000000-0000-0000-0000-000000000000",
                compute_capability="8.6",
            )
        ]

        # ISOLATION_FIRST should warn but still assign all services
        assignments, warnings = _calculate_auto_assignments(
            GpuAssignmentStrategy.ISOLATION_FIRST, single_gpu
        )

        assert len(assignments) == 5  # All services assigned
        assert all(a.gpu_index == 0 for a in assignments)  # All on GPU 0
        assert len(warnings) == 1  # Should warn about single GPU
        assert "isolation strategy not possible" in warnings[0].lower()

    @pytest.mark.asyncio
    async def test_strategy_with_no_gpus_returns_error(self) -> None:
        """Test that strategies return appropriate error when no GPUs detected."""
        from backend.api.routes.gpu_config import _calculate_auto_assignments

        empty_gpus: list[GpuDevice] = []

        assignments, warnings = _calculate_auto_assignments(
            GpuAssignmentStrategy.VRAM_BASED, empty_gpus
        )

        assert len(assignments) == 0
        assert len(warnings) == 1
        assert "no gpus detected" in warnings[0].lower()


# =============================================================================
# Test 6: API Workflow Integration
# =============================================================================


class TestAPIWorkflowIntegration:
    """Test GPU configuration API endpoint workflow."""

    @pytest.mark.asyncio
    async def test_api_detect_update_apply_status_workflow(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        gpu_detection_service: GpuDetectionService,
        temp_config_dir: Path,
    ) -> None:
        """Test complete API workflow: detect → update → apply → status.

        This test verifies the workflow through actual API calls as the
        frontend would use them.
        """
        # Mock the config service to use temp directory
        with patch("backend.api.routes.gpu_config.GpuConfigService") as mock_config_service_class:
            mock_service = MagicMock()
            mock_service.write_config_files = AsyncMock(
                return_value=(
                    temp_config_dir / "docker-compose.gpu-override.yml",
                    temp_config_dir / "gpu-assignments.yml",
                )
            )
            mock_config_service_class.return_value = mock_service

            # Create sample files that write_config_files would create
            (temp_config_dir / "docker-compose.gpu-override.yml").write_text("services: {}")
            (temp_config_dir / "gpu-assignments.yml").write_text("assignments: {}")

            # Step 1: Detect GPUs
            response = await client.get("/api/system/gpus")
            assert response.status_code == 200
            data = response.json()
            assert len(data["gpus"]) == 2

            # Step 2: Get current config
            response = await client.get("/api/system/gpu-config")
            assert response.status_code == 200
            data = response.json()
            assert data["strategy"] == "manual"  # Default strategy

            # Step 3: Update config
            update_payload = {
                "strategy": "vram_based",
                "assignments": [
                    {"service": "ai-llm", "gpu_index": 1, "vram_budget_override": None},
                    {
                        "service": "ai-yolo26",
                        "gpu_index": 0,
                        "vram_budget_override": None,
                    },
                ],
            }
            response = await client.put("/api/system/gpu-config", json=update_payload)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

            # Step 4: Preview strategy
            response = await client.get(
                "/api/system/gpu-config/preview", params={"strategy": "isolation_first"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["strategy"] == "isolation_first"
            assert len(data["proposed_assignments"]) > 0

            # Step 5: Apply configuration
            response = await client.post("/api/system/gpu-config/apply")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["restarted_services"]) == 2

            # Step 6: Check apply status
            response = await client.get("/api/system/gpu-config/status")
            assert response.status_code == 200
            data = response.json()
            assert data["in_progress"] is False
            assert len(data["services_completed"]) == 2
