"""Tests to validate AI service resource limits in docker-compose.prod.yml.

This module tests that all AI services have proper CPU and memory resource
limits configured for production deployments.

NEM-4975: Add CPU/memory resource limits to AI services in production compose
"""

import re
from pathlib import Path
from typing import ClassVar

import pytest
import yaml


class TestAIServiceResourceLimits:
    """Tests for AI service resource limits in docker-compose.prod.yml."""

    # AI services that require resource limits
    AI_SERVICES: ClassVar[list[str]] = [
        "ai-yolo26",
        "ai-llm",
        "ai-florence",
        "ai-clip",
        "ai-enrichment",
        "ai-enrichment-light",
    ]

    @pytest.fixture
    def compose_file_path(self) -> Path:
        """Get the path to docker-compose.prod.yml."""
        # Navigate from tests/unit/core/ to project root (one level up from backend/)
        return Path(__file__).parent.parent.parent.parent.parent / "docker-compose.prod.yml"

    @pytest.fixture
    def compose_content(self, compose_file_path: Path) -> dict:
        """Parse the docker-compose.prod.yml file."""
        if not compose_file_path.exists():
            pytest.skip(f"docker-compose.prod.yml not found at {compose_file_path}")
        return yaml.safe_load(compose_file_path.read_text())

    def test_compose_file_exists(self, compose_file_path: Path) -> None:
        """Test that docker-compose.prod.yml exists."""
        assert compose_file_path.exists(), (
            f"docker-compose.prod.yml not found at {compose_file_path}"
        )

    def test_compose_parses_valid_yaml(self, compose_content: dict) -> None:
        """Test that docker-compose.prod.yml is valid YAML."""
        assert isinstance(compose_content, dict), "docker-compose.prod.yml should be valid YAML"
        assert "services" in compose_content, "docker-compose.prod.yml should have services section"

    def test_all_ai_services_exist(self, compose_content: dict) -> None:
        """Test that all required AI services are defined."""
        services = compose_content.get("services", {})
        for service_name in self.AI_SERVICES:
            assert service_name in services, (
                f"Service '{service_name}' not found in docker-compose.prod.yml"
            )

    def test_ai_yolo26_has_resource_limits(self, compose_content: dict) -> None:
        """Test that ai-yolo26 has CPU and memory limits configured."""
        service = compose_content["services"]["ai-yolo26"]
        assert "deploy" in service, "ai-yolo26 should have deploy section"
        assert "resources" in service["deploy"], "ai-yolo26 deploy should have resources section"
        assert "limits" in service["deploy"]["resources"], "ai-yolo26 resources should have limits"
        limits = service["deploy"]["resources"]["limits"]
        assert "cpus" in limits, "ai-yolo26 limits should have cpus"
        assert "memory" in limits, "ai-yolo26 limits should have memory"

    def test_ai_llm_has_resource_limits(self, compose_content: dict) -> None:
        """Test that ai-llm has CPU and memory limits configured."""
        service = compose_content["services"]["ai-llm"]
        assert "deploy" in service, "ai-llm should have deploy section"
        assert "resources" in service["deploy"], "ai-llm deploy should have resources section"
        assert "limits" in service["deploy"]["resources"], "ai-llm resources should have limits"
        limits = service["deploy"]["resources"]["limits"]
        assert "cpus" in limits, "ai-llm limits should have cpus"
        assert "memory" in limits, "ai-llm limits should have memory"

    def test_ai_florence_has_resource_limits(self, compose_content: dict) -> None:
        """Test that ai-florence has CPU and memory limits configured."""
        service = compose_content["services"]["ai-florence"]
        assert "deploy" in service, "ai-florence should have deploy section"
        assert "resources" in service["deploy"], "ai-florence deploy should have resources section"
        assert "limits" in service["deploy"]["resources"], (
            "ai-florence resources should have limits"
        )
        limits = service["deploy"]["resources"]["limits"]
        assert "cpus" in limits, "ai-florence limits should have cpus"
        assert "memory" in limits, "ai-florence limits should have memory"

    def test_ai_clip_has_resource_limits(self, compose_content: dict) -> None:
        """Test that ai-clip has CPU and memory limits configured."""
        service = compose_content["services"]["ai-clip"]
        assert "deploy" in service, "ai-clip should have deploy section"
        assert "resources" in service["deploy"], "ai-clip deploy should have resources section"
        assert "limits" in service["deploy"]["resources"], "ai-clip resources should have limits"
        limits = service["deploy"]["resources"]["limits"]
        assert "cpus" in limits, "ai-clip limits should have cpus"
        assert "memory" in limits, "ai-clip limits should have memory"

    def test_ai_enrichment_has_resource_limits(self, compose_content: dict) -> None:
        """Test that ai-enrichment has CPU and memory limits configured."""
        service = compose_content["services"]["ai-enrichment"]
        assert "deploy" in service, "ai-enrichment should have deploy section"
        assert "resources" in service["deploy"], (
            "ai-enrichment deploy should have resources section"
        )
        assert "limits" in service["deploy"]["resources"], (
            "ai-enrichment resources should have limits"
        )
        limits = service["deploy"]["resources"]["limits"]
        assert "cpus" in limits, "ai-enrichment limits should have cpus"
        assert "memory" in limits, "ai-enrichment limits should have memory"

    def test_ai_enrichment_light_has_resource_limits(self, compose_content: dict) -> None:
        """Test that ai-enrichment-light has CPU and memory limits configured."""
        service = compose_content["services"]["ai-enrichment-light"]
        assert "deploy" in service, "ai-enrichment-light should have deploy section"
        assert "resources" in service["deploy"], (
            "ai-enrichment-light deploy should have resources section"
        )
        assert "limits" in service["deploy"]["resources"], (
            "ai-enrichment-light resources should have limits"
        )
        limits = service["deploy"]["resources"]["limits"]
        assert "cpus" in limits, "ai-enrichment-light limits should have cpus"
        assert "memory" in limits, "ai-enrichment-light limits should have memory"

    def test_all_ai_services_have_complete_resource_limits(self, compose_content: dict) -> None:
        """Test that all AI services have both CPU and memory limits."""
        services = compose_content.get("services", {})
        for service_name in self.AI_SERVICES:
            service = services[service_name]
            assert "deploy" in service, f"{service_name} should have deploy section"
            assert "resources" in service["deploy"], f"{service_name} deploy should have resources"
            assert "limits" in service["deploy"]["resources"], (
                f"{service_name} resources should have limits"
            )

            limits = service["deploy"]["resources"]["limits"]
            assert "cpus" in limits, f"{service_name} limits should have cpus"
            assert "memory" in limits, f"{service_name} limits should have memory"

            # Validate the values are strings (YAML format)
            assert isinstance(limits["cpus"], (int | float | str)), (
                f"{service_name} cpus should be a number or string"
            )
            assert isinstance(limits["memory"], str), (
                f"{service_name} memory should be a string (e.g., '8G')"
            )

    def test_resource_limits_are_reasonable(self, compose_content: dict) -> None:
        """Test that resource limits are reasonable values for AI services."""
        services = compose_content.get("services", {})
        for service_name in self.AI_SERVICES:
            service = services[service_name]
            limits = service["deploy"]["resources"]["limits"]

            # Parse CPU limit
            cpus = limits["cpus"]
            if isinstance(cpus, str):
                cpus_float = float(cpus)
            else:
                cpus_float = float(cpus)

            # AI services should have at least 1 CPU
            assert cpus_float >= 1, (
                f"{service_name} should have at least 1 CPU (found {cpus_float})"
            )

            # Parse memory limit
            memory_str = limits["memory"]
            memory_match = re.match(r"(\d+(?:\.\d+)?)\s*([GMK]?)", str(memory_str))
            assert memory_match, f"{service_name} memory format is invalid: {memory_str}"

            memory_value = float(memory_match.group(1))
            memory_unit = memory_match.group(2) or "M"

            # Convert to MB for comparison
            unit_multipliers = {"K": 0.001, "M": 1, "G": 1024}
            memory_mb = memory_value * unit_multipliers.get(memory_unit, 1)

            # AI services should have at least 1GB (1024 MB) of memory
            assert memory_mb >= 1024, (
                f"{service_name} should have at least 1G memory (found {memory_str})"
            )

    def test_memory_reservations_exist_for_ai_services(self, compose_content: dict) -> None:
        """Test that memory reservations are defined for AI services.

        Memory reservations are important for container orchestration to ensure
        sufficient resources are available before scheduling.
        """
        services = compose_content.get("services", {})
        for service_name in self.AI_SERVICES:
            service = services[service_name]
            assert "deploy" in service, f"{service_name} should have deploy section"
            assert "resources" in service["deploy"], f"{service_name} deploy should have resources"
            assert "reservations" in service["deploy"]["resources"], (
                f"{service_name} resources should have reservations for proper scheduling"
            )

    def test_docker_compose_yaml_syntax_valid(self, compose_content: dict) -> None:
        """Test that docker-compose.prod.yml has valid YAML structure.

        This ensures the compose file can be parsed by docker-compose tools.
        """
        # PyYAML successfully parsed the file, which means it's valid YAML
        assert isinstance(compose_content, dict), "docker-compose.prod.yml should parse to a dict"
        assert "version" in compose_content, "docker-compose.prod.yml should have version field"
        assert "services" in compose_content, "docker-compose.prod.yml should have services section"
