"""Unit tests for GpuConfigService.

Tests cover:
- GpuAssignment dataclass creation
- YAML generation produces valid output
- Environment override included when vram_budget set
- File writing creates both files
- Config directory created if missing
- Multiple assignments handled correctly
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from backend.services.gpu_config_service import GpuAssignment, GpuConfigService

# =============================================================================
# Test Configuration and Fixtures
# =============================================================================


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory."""
    return tmp_path / "config"


@pytest.fixture
def gpu_config_service(temp_config_dir: Path) -> GpuConfigService:
    """Create a GpuConfigService with a temporary config directory."""
    return GpuConfigService(config_dir=temp_config_dir)


@pytest.fixture
def single_assignment() -> list[GpuAssignment]:
    """Create a single GPU assignment fixture."""
    return [GpuAssignment(service_name="ai-llm", gpu_index=0)]


@pytest.fixture
def multiple_assignments() -> list[GpuAssignment]:
    """Create multiple GPU assignments fixture."""
    return [
        GpuAssignment(service_name="ai-llm", gpu_index=0),
        GpuAssignment(service_name="ai-yolo26", gpu_index=0),
        GpuAssignment(service_name="ai-enrichment", gpu_index=1, vram_budget_override=3.5),
    ]


# =============================================================================
# GpuAssignment Tests
# =============================================================================


class TestGpuAssignment:
    """Tests for GpuAssignment dataclass."""

    def test_basic_assignment_creation(self) -> None:
        """Test creating a basic GPU assignment."""
        assignment = GpuAssignment(service_name="ai-llm", gpu_index=0)

        assert assignment.service_name == "ai-llm"
        assert assignment.gpu_index == 0
        assert assignment.vram_budget_override is None

    def test_assignment_with_vram_budget(self) -> None:
        """Test creating a GPU assignment with VRAM budget override."""
        assignment = GpuAssignment(
            service_name="ai-enrichment",
            gpu_index=1,
            vram_budget_override=3.5,
        )

        assert assignment.service_name == "ai-enrichment"
        assert assignment.gpu_index == 1
        assert assignment.vram_budget_override == 3.5

    def test_assignment_with_zero_gpu_index(self) -> None:
        """Test GPU assignment with GPU index 0."""
        assignment = GpuAssignment(service_name="test-service", gpu_index=0)

        assert assignment.gpu_index == 0

    def test_assignment_with_higher_gpu_index(self) -> None:
        """Test GPU assignment with higher GPU index."""
        assignment = GpuAssignment(service_name="test-service", gpu_index=3)

        assert assignment.gpu_index == 3

    def test_assignment_with_zero_vram_budget(self) -> None:
        """Test GPU assignment with zero VRAM budget (edge case)."""
        assignment = GpuAssignment(
            service_name="test-service",
            gpu_index=0,
            vram_budget_override=0.0,
        )

        assert assignment.vram_budget_override == 0.0


# =============================================================================
# GpuConfigService Initialization Tests
# =============================================================================


class TestGpuConfigServiceInit:
    """Tests for GpuConfigService initialization."""

    def test_init_with_custom_config_dir(self, temp_config_dir: Path) -> None:
        """Test initialization with custom config directory."""
        service = GpuConfigService(config_dir=temp_config_dir)

        assert service.config_dir == temp_config_dir
        assert service.override_file == temp_config_dir / "docker-compose.gpu-override.yml"
        assert service.assignments_file == temp_config_dir / "gpu-assignments.yml"

    def test_init_with_default_config_dir(self) -> None:
        """Test initialization with default config directory."""
        service = GpuConfigService()

        assert service.config_dir == Path("config")
        assert service.override_file == Path("config/docker-compose.gpu-override.yml")
        assert service.assignments_file == Path("config/gpu-assignments.yml")


# =============================================================================
# generate_override_content Tests
# =============================================================================


class TestGenerateOverrideContent:
    """Tests for GpuConfigService.generate_override_content method."""

    def test_generates_valid_yaml(
        self,
        gpu_config_service: GpuConfigService,
        single_assignment: list[GpuAssignment],
    ) -> None:
        """Test that generated content is valid YAML."""
        content = gpu_config_service.generate_override_content(single_assignment)

        # Should be parseable as YAML (skip header line)
        yaml_content = "\n".join(content.split("\n")[1:])
        parsed = yaml.safe_load(yaml_content)

        assert parsed is not None
        assert "services" in parsed

    def test_includes_header_comment(
        self,
        gpu_config_service: GpuConfigService,
        single_assignment: list[GpuAssignment],
    ) -> None:
        """Test that generated content includes header comment."""
        content = gpu_config_service.generate_override_content(single_assignment)

        assert content.startswith("# Auto-generated by GPU Config Service")
        assert "DO NOT EDIT MANUALLY" in content

    def test_single_service_structure(
        self,
        gpu_config_service: GpuConfigService,
        single_assignment: list[GpuAssignment],
    ) -> None:
        """Test correct structure for a single service."""
        content = gpu_config_service.generate_override_content(single_assignment)

        # Skip header and parse
        yaml_content = "\n".join(content.split("\n")[1:])
        parsed = yaml.safe_load(yaml_content)

        assert "ai-llm" in parsed["services"]
        service_config = parsed["services"]["ai-llm"]

        # Verify deploy/resources/reservations/devices structure
        assert "deploy" in service_config
        assert "resources" in service_config["deploy"]
        assert "reservations" in service_config["deploy"]["resources"]
        devices = service_config["deploy"]["resources"]["reservations"]["devices"]

        assert len(devices) == 1
        assert devices[0]["driver"] == "nvidia"
        assert devices[0]["device_ids"] == ["0"]
        assert devices[0]["capabilities"] == ["gpu"]

    def test_multiple_services(
        self,
        gpu_config_service: GpuConfigService,
        multiple_assignments: list[GpuAssignment],
    ) -> None:
        """Test correct structure for multiple services."""
        content = gpu_config_service.generate_override_content(multiple_assignments)

        yaml_content = "\n".join(content.split("\n")[1:])
        parsed = yaml.safe_load(yaml_content)

        services = parsed["services"]
        assert len(services) == 3
        assert "ai-llm" in services
        assert "ai-yolo26" in services
        assert "ai-enrichment" in services

    def test_vram_budget_environment_variable(
        self,
        gpu_config_service: GpuConfigService,
    ) -> None:
        """Test that VRAM budget override adds environment variable."""
        assignments = [
            GpuAssignment(
                service_name="ai-enrichment",
                gpu_index=1,
                vram_budget_override=3.5,
            )
        ]
        content = gpu_config_service.generate_override_content(assignments)

        yaml_content = "\n".join(content.split("\n")[1:])
        parsed = yaml.safe_load(yaml_content)

        service_config = parsed["services"]["ai-enrichment"]
        assert "environment" in service_config
        assert "VRAM_BUDGET_GB=3.5" in service_config["environment"]

    def test_no_environment_without_vram_budget(
        self,
        gpu_config_service: GpuConfigService,
        single_assignment: list[GpuAssignment],
    ) -> None:
        """Test that no environment section when no VRAM budget set."""
        content = gpu_config_service.generate_override_content(single_assignment)

        yaml_content = "\n".join(content.split("\n")[1:])
        parsed = yaml.safe_load(yaml_content)

        service_config = parsed["services"]["ai-llm"]
        assert "environment" not in service_config

    def test_empty_assignments_list(
        self,
        gpu_config_service: GpuConfigService,
    ) -> None:
        """Test generating content with empty assignments list."""
        content = gpu_config_service.generate_override_content([])

        yaml_content = "\n".join(content.split("\n")[1:])
        parsed = yaml.safe_load(yaml_content)

        assert parsed["services"] == {}

    def test_gpu_index_as_string(
        self,
        gpu_config_service: GpuConfigService,
    ) -> None:
        """Test that GPU index is converted to string in device_ids."""
        assignments = [GpuAssignment(service_name="test", gpu_index=2)]
        content = gpu_config_service.generate_override_content(assignments)

        yaml_content = "\n".join(content.split("\n")[1:])
        parsed = yaml.safe_load(yaml_content)

        device_ids = parsed["services"]["test"]["deploy"]["resources"]["reservations"]["devices"][
            0
        ]["device_ids"]
        # Should contain string "2", not integer 2
        assert device_ids == ["2"]

    def test_zero_vram_budget_includes_environment(
        self,
        gpu_config_service: GpuConfigService,
    ) -> None:
        """Test that zero VRAM budget still includes environment variable."""
        assignments = [
            GpuAssignment(
                service_name="test",
                gpu_index=0,
                vram_budget_override=0.0,
            )
        ]
        content = gpu_config_service.generate_override_content(assignments)

        yaml_content = "\n".join(content.split("\n")[1:])
        parsed = yaml.safe_load(yaml_content)

        # 0.0 is falsy but not None, so it should NOT be included
        # Wait - the implementation checks `is not None`, so 0.0 SHOULD be included
        service_config = parsed["services"]["test"]
        assert "environment" in service_config
        assert "VRAM_BUDGET_GB=0.0" in service_config["environment"]


# =============================================================================
# generate_assignments_content Tests
# =============================================================================


class TestGenerateAssignmentsContent:
    """Tests for GpuConfigService.generate_assignments_content method."""

    def test_generates_valid_yaml(
        self,
        gpu_config_service: GpuConfigService,
        single_assignment: list[GpuAssignment],
    ) -> None:
        """Test that generated content is valid YAML."""
        content = gpu_config_service.generate_assignments_content(single_assignment, "manual")

        yaml_content = "\n".join(content.split("\n")[1:])
        parsed = yaml.safe_load(yaml_content)

        assert parsed is not None

    def test_includes_header_comment(
        self,
        gpu_config_service: GpuConfigService,
        single_assignment: list[GpuAssignment],
    ) -> None:
        """Test that generated content includes header comment."""
        content = gpu_config_service.generate_assignments_content(single_assignment, "manual")

        assert content.startswith("# Auto-generated")
        assert "for reference only" in content

    def test_includes_generated_at_timestamp(
        self,
        gpu_config_service: GpuConfigService,
        single_assignment: list[GpuAssignment],
    ) -> None:
        """Test that content includes generated_at timestamp."""
        content = gpu_config_service.generate_assignments_content(single_assignment, "vram_based")

        yaml_content = "\n".join(content.split("\n")[1:])
        parsed = yaml.safe_load(yaml_content)

        assert "generated_at" in parsed
        # Should be ISO format with timezone
        assert "T" in parsed["generated_at"]

    def test_includes_strategy(
        self,
        gpu_config_service: GpuConfigService,
        single_assignment: list[GpuAssignment],
    ) -> None:
        """Test that content includes strategy field."""
        content = gpu_config_service.generate_assignments_content(single_assignment, "vram_based")

        yaml_content = "\n".join(content.split("\n")[1:])
        parsed = yaml.safe_load(yaml_content)

        assert parsed["strategy"] == "vram_based"

    def test_includes_assignments(
        self,
        gpu_config_service: GpuConfigService,
        multiple_assignments: list[GpuAssignment],
    ) -> None:
        """Test that content includes all assignments."""
        content = gpu_config_service.generate_assignments_content(multiple_assignments, "manual")

        yaml_content = "\n".join(content.split("\n")[1:])
        parsed = yaml.safe_load(yaml_content)

        assignments = parsed["assignments"]
        assert len(assignments) == 3
        assert "ai-llm" in assignments
        assert "ai-yolo26" in assignments
        assert "ai-enrichment" in assignments

    def test_assignment_structure(
        self,
        gpu_config_service: GpuConfigService,
        single_assignment: list[GpuAssignment],
    ) -> None:
        """Test assignment entry structure."""
        content = gpu_config_service.generate_assignments_content(single_assignment, "manual")

        yaml_content = "\n".join(content.split("\n")[1:])
        parsed = yaml.safe_load(yaml_content)

        assignment = parsed["assignments"]["ai-llm"]
        assert assignment["gpu"] == 0
        assert assignment["vram_budget"] is None

    def test_assignment_with_vram_budget(
        self,
        gpu_config_service: GpuConfigService,
    ) -> None:
        """Test assignment entry with VRAM budget."""
        assignments = [
            GpuAssignment(
                service_name="ai-enrichment",
                gpu_index=1,
                vram_budget_override=3.5,
            )
        ]
        content = gpu_config_service.generate_assignments_content(assignments, "manual")

        yaml_content = "\n".join(content.split("\n")[1:])
        parsed = yaml.safe_load(yaml_content)

        assignment = parsed["assignments"]["ai-enrichment"]
        assert assignment["gpu"] == 1
        assert assignment["vram_budget"] == 3.5

    def test_different_strategies(
        self,
        gpu_config_service: GpuConfigService,
        single_assignment: list[GpuAssignment],
    ) -> None:
        """Test different strategy values."""
        strategies = ["manual", "vram_based", "latency_optimized", "isolation_first", "balanced"]

        for strategy in strategies:
            content = gpu_config_service.generate_assignments_content(single_assignment, strategy)

            yaml_content = "\n".join(content.split("\n")[1:])
            parsed = yaml.safe_load(yaml_content)

            assert parsed["strategy"] == strategy

    def test_empty_assignments(
        self,
        gpu_config_service: GpuConfigService,
    ) -> None:
        """Test generating content with empty assignments."""
        content = gpu_config_service.generate_assignments_content([], "manual")

        yaml_content = "\n".join(content.split("\n")[1:])
        parsed = yaml.safe_load(yaml_content)

        assert parsed["assignments"] == {}


# =============================================================================
# write_config_files Tests
# =============================================================================


class TestWriteConfigFiles:
    """Tests for GpuConfigService.write_config_files method."""

    @pytest.mark.asyncio
    async def test_creates_config_directory(
        self,
        gpu_config_service: GpuConfigService,
        temp_config_dir: Path,
        single_assignment: list[GpuAssignment],
    ) -> None:
        """Test that config directory is created if missing."""
        assert not temp_config_dir.exists()

        await gpu_config_service.write_config_files(single_assignment, "manual")

        assert temp_config_dir.exists()
        assert temp_config_dir.is_dir()

    @pytest.mark.asyncio
    async def test_creates_override_file(
        self,
        gpu_config_service: GpuConfigService,
        temp_config_dir: Path,
        single_assignment: list[GpuAssignment],
    ) -> None:
        """Test that override file is created."""
        await gpu_config_service.write_config_files(single_assignment, "manual")

        override_path = temp_config_dir / "docker-compose.gpu-override.yml"
        assert override_path.exists()
        assert override_path.is_file()

    @pytest.mark.asyncio
    async def test_creates_assignments_file(
        self,
        gpu_config_service: GpuConfigService,
        temp_config_dir: Path,
        single_assignment: list[GpuAssignment],
    ) -> None:
        """Test that assignments file is created."""
        await gpu_config_service.write_config_files(single_assignment, "manual")

        assignments_path = temp_config_dir / "gpu-assignments.yml"
        assert assignments_path.exists()
        assert assignments_path.is_file()

    @pytest.mark.asyncio
    async def test_returns_correct_paths(
        self,
        gpu_config_service: GpuConfigService,
        temp_config_dir: Path,
        single_assignment: list[GpuAssignment],
    ) -> None:
        """Test that correct file paths are returned."""
        override_path, assignments_path = await gpu_config_service.write_config_files(
            single_assignment, "manual"
        )

        assert override_path == temp_config_dir / "docker-compose.gpu-override.yml"
        assert assignments_path == temp_config_dir / "gpu-assignments.yml"

    @pytest.mark.asyncio
    async def test_override_file_content(
        self,
        gpu_config_service: GpuConfigService,
        temp_config_dir: Path,
        single_assignment: list[GpuAssignment],
    ) -> None:
        """Test that override file has correct content."""
        await gpu_config_service.write_config_files(single_assignment, "manual")

        override_path = temp_config_dir / "docker-compose.gpu-override.yml"
        content = override_path.read_text()

        assert "# Auto-generated by GPU Config Service" in content
        assert "services:" in content
        assert "ai-llm:" in content

    @pytest.mark.asyncio
    async def test_assignments_file_content(
        self,
        gpu_config_service: GpuConfigService,
        temp_config_dir: Path,
        single_assignment: list[GpuAssignment],
    ) -> None:
        """Test that assignments file has correct content."""
        await gpu_config_service.write_config_files(single_assignment, "vram_based")

        assignments_path = temp_config_dir / "gpu-assignments.yml"
        content = assignments_path.read_text()

        assert "# Auto-generated" in content
        assert "strategy: vram_based" in content
        assert "assignments:" in content

    @pytest.mark.asyncio
    async def test_overwrites_existing_files(
        self,
        gpu_config_service: GpuConfigService,
        temp_config_dir: Path,
    ) -> None:
        """Test that existing files are overwritten."""
        # Create initial files
        initial_assignments = [GpuAssignment(service_name="old-service", gpu_index=0)]
        await gpu_config_service.write_config_files(initial_assignments, "manual")

        # Overwrite with new assignments
        new_assignments = [GpuAssignment(service_name="new-service", gpu_index=1)]
        await gpu_config_service.write_config_files(new_assignments, "vram_based")

        # Read and verify content
        override_path = temp_config_dir / "docker-compose.gpu-override.yml"
        content = override_path.read_text()

        assert "new-service:" in content
        assert "old-service:" not in content

    @pytest.mark.asyncio
    async def test_creates_nested_directory(
        self,
        tmp_path: Path,
    ) -> None:
        """Test creating deeply nested config directory."""
        nested_dir = tmp_path / "deep" / "nested" / "config"
        service = GpuConfigService(config_dir=nested_dir)
        assignments = [GpuAssignment(service_name="test", gpu_index=0)]

        await service.write_config_files(assignments, "manual")

        assert nested_dir.exists()
        assert (nested_dir / "docker-compose.gpu-override.yml").exists()
        assert (nested_dir / "gpu-assignments.yml").exists()

    @pytest.mark.asyncio
    async def test_multiple_assignments_in_files(
        self,
        gpu_config_service: GpuConfigService,
        temp_config_dir: Path,
        multiple_assignments: list[GpuAssignment],
    ) -> None:
        """Test that multiple assignments are correctly written."""
        await gpu_config_service.write_config_files(multiple_assignments, "balanced")

        # Verify override file
        override_path = temp_config_dir / "docker-compose.gpu-override.yml"
        override_content = override_path.read_text()
        yaml_content = "\n".join(override_content.split("\n")[1:])
        override_parsed = yaml.safe_load(yaml_content)

        assert len(override_parsed["services"]) == 3
        assert "ai-llm" in override_parsed["services"]
        assert "ai-enrichment" in override_parsed["services"]

        # Verify VRAM budget is in enrichment service
        enrichment = override_parsed["services"]["ai-enrichment"]
        assert "environment" in enrichment
        assert "VRAM_BUDGET_GB=3.5" in enrichment["environment"]

        # Verify assignments file
        assignments_path = temp_config_dir / "gpu-assignments.yml"
        assignments_content = assignments_path.read_text()
        yaml_assignments = "\n".join(assignments_content.split("\n")[1:])
        assignments_parsed = yaml.safe_load(yaml_assignments)

        assert len(assignments_parsed["assignments"]) == 3
        assert assignments_parsed["strategy"] == "balanced"

    @pytest.mark.asyncio
    async def test_empty_assignments(
        self,
        gpu_config_service: GpuConfigService,
        temp_config_dir: Path,
    ) -> None:
        """Test writing files with empty assignments."""
        await gpu_config_service.write_config_files([], "manual")

        override_path = temp_config_dir / "docker-compose.gpu-override.yml"
        assert override_path.exists()

        assignments_path = temp_config_dir / "gpu-assignments.yml"
        assert assignments_path.exists()


# =============================================================================
# Integration Tests
# =============================================================================


class TestGpuConfigServiceIntegration:
    """Integration tests for complete GpuConfigService workflow."""

    @pytest.mark.asyncio
    async def test_full_workflow_multi_gpu(
        self,
        tmp_path: Path,
    ) -> None:
        """Test complete workflow with multi-GPU configuration."""
        # Setup
        config_dir = tmp_path / "config"
        service = GpuConfigService(config_dir=config_dir)

        # Create realistic multi-GPU assignments
        assignments = [
            GpuAssignment(service_name="ai-llm", gpu_index=0),
            GpuAssignment(service_name="ai-yolo26", gpu_index=0),
            GpuAssignment(service_name="ai-florence", gpu_index=0),
            GpuAssignment(service_name="ai-clip", gpu_index=0),
            GpuAssignment(
                service_name="ai-enrichment",
                gpu_index=1,
                vram_budget_override=3.5,
            ),
        ]

        # Execute
        override_path, assignments_path = await service.write_config_files(
            assignments, "isolation_first"
        )

        # Verify override file is valid docker-compose format
        override_content = override_path.read_text()
        assert override_content.startswith("# Auto-generated")

        yaml_content = "\n".join(override_content.split("\n")[1:])
        parsed = yaml.safe_load(yaml_content)

        # Check all services are present
        services = parsed["services"]
        assert len(services) == 5

        # Check GPU assignments
        assert services["ai-llm"]["deploy"]["resources"]["reservations"]["devices"][0][
            "device_ids"
        ] == ["0"]
        assert services["ai-enrichment"]["deploy"]["resources"]["reservations"]["devices"][0][
            "device_ids"
        ] == ["1"]

        # Check VRAM budget
        assert "VRAM_BUDGET_GB=3.5" in services["ai-enrichment"]["environment"]

        # Verify assignments file
        assignments_content = assignments_path.read_text()
        assert "isolation_first" in assignments_content
        assert "ai-enrichment" in assignments_content

    @pytest.mark.asyncio
    async def test_file_content_is_idempotent(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that same assignments produce consistent file structure."""
        config_dir = tmp_path / "config"
        service = GpuConfigService(config_dir=config_dir)
        assignments = [
            GpuAssignment(service_name="ai-llm", gpu_index=0),
            GpuAssignment(service_name="ai-yolo26", gpu_index=1),
        ]

        # Write first time
        await service.write_config_files(assignments, "manual")
        override_content_1 = (config_dir / "docker-compose.gpu-override.yml").read_text()

        # Write second time
        await service.write_config_files(assignments, "manual")
        override_content_2 = (config_dir / "docker-compose.gpu-override.yml").read_text()

        # Content should be identical (except for timestamp in assignments file)
        assert override_content_1 == override_content_2
