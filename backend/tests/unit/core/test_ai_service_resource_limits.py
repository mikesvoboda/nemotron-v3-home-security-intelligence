"""Tests to validate AI service resource limits in docker-compose.prod.yml.

This module tests that all AI services have proper CPU and memory resource
limits configured for production deployments.

NEM-4975: Add CPU/memory resource limits to AI services in production compose

Note: R8 S2b (commit 602379e2) deleted the ai-llm (Nemotron) service; the prod
AI tier is now ai-gateway, ai-vlm (the shipped serving engine) and the optional
profile-`vllm` ai-llm-vllm. The earlier removal of ai-yolo26, ai-florence,
ai-clip, ai-enrichment and ai-enrichment-light stands; all of them stay gone.
"""

import re
from pathlib import Path
from typing import ClassVar

import pytest
import yaml


class TestAIServiceResourceLimits:
    """Tests for AI service resource limits in docker-compose.prod.yml."""

    # The prod AI tier, DERIVED from the compose file by the ai_services fixture
    # below and pinned as exactly this trio: a hand-curated list here is how
    # ai-llm kept being asserted after R8 S2b (602379e2) deleted the service.
    EXPECTED_AI_SERVICES: ClassVar[list[str]] = [
        "ai-gateway",
        "ai-llm-vllm",
        "ai-vlm",
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

    @pytest.fixture
    def ai_services(self, compose_content: dict) -> list[str]:
        """The AI tier AS THE COMPOSE FILE DEFINES IT: every ``ai-`` service.

        Deriving it here is what keeps the sweeps below from quietly shrinking.
        The file used to carry a hand-curated list, and that is exactly how it
        came to assert resource limits for ai-llm after R8 S2b (602379e2)
        deleted the service — and how a service someone adds to compose could
        sail past a limits review nobody remembered to update. The derived set
        is pinned against EXPECTED_AI_SERVICES in test_all_ai_services_exist,
        so a surprise in either direction is a failure with a name on it.
        """
        services = compose_content.get("services", {})
        return sorted(name for name in services if name.startswith("ai-"))

    def test_compose_file_exists(self, compose_file_path: Path) -> None:
        """Test that docker-compose.prod.yml exists."""
        assert compose_file_path.exists(), (
            f"docker-compose.prod.yml not found at {compose_file_path}"
        )

    def test_compose_parses_valid_yaml(self, compose_content: dict) -> None:
        """Test that docker-compose.prod.yml is valid YAML."""
        assert isinstance(compose_content, dict), "docker-compose.prod.yml should be valid YAML"
        assert "services" in compose_content, "docker-compose.prod.yml should have services section"

    def test_all_ai_services_exist(self, ai_services: list[str]) -> None:
        """The prod AI tier is exactly the three services R8 S2b left standing.

        ai-gateway (Triton + FastAPI routing), ai-vlm (the shipped serving
        engine, profile `vlm`) and ai-llm-vllm (the optional vLLM benchmark
        engine, profile `vllm`). ai-llm / Nemotron was deleted in 602379e2, so
        the set is asserted EQUAL rather than as a containment check — a
        containment check is what let the deleted service stay on the list for
        a whole slice, and it would equally let a fourth engine appear
        un-hardened and un-mentioned.
        """
        assert ai_services == sorted(self.EXPECTED_AI_SERVICES), (
            f"docker-compose.prod.yml defines {ai_services}, expected "
            f"{sorted(self.EXPECTED_AI_SERVICES)} — if the AI tier really changed, "
            "update EXPECTED_AI_SERVICES in the same change that moves the limits "
            "sweep onto the new service"
        )

    def test_ai_gateway_has_resource_limits(self, compose_content: dict) -> None:
        """Test that ai-gateway has CPU and memory limits configured."""
        service = compose_content["services"]["ai-gateway"]
        assert "deploy" in service, "ai-gateway should have deploy section"
        assert "resources" in service["deploy"], "ai-gateway deploy should have resources section"
        assert "limits" in service["deploy"]["resources"], "ai-gateway resources should have limits"
        limits = service["deploy"]["resources"]["limits"]
        assert "cpus" in limits, "ai-gateway limits should have cpus"
        assert "memory" in limits, "ai-gateway limits should have memory"

    # test_ai_llm_has_resource_limits retired with its subject: R8 S2b (602379e2)
    # deleted the ai-llm service from docker-compose.prod.yml, so there is no
    # deploy: block left to read. Nothing shrinks — the sweep below now walks the
    # derived tier, and ai-llm-vllm (profile `vllm`, the vLLM benchmark engine, a
    # different service from the deleted ai-llm) joins it: the curated list never
    # named it, which is precisely the gap the derivation closes.

    def test_all_ai_services_have_complete_resource_limits(
        self, compose_content: dict, ai_services: list[str]
    ) -> None:
        """Test that all AI services have both CPU and memory limits."""
        services = compose_content.get("services", {})
        for service_name in ai_services:
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

    def test_resource_limits_are_reasonable(
        self, compose_content: dict, ai_services: list[str]
    ) -> None:
        """Test that resource limits are reasonable values for AI services."""
        services = compose_content.get("services", {})
        for service_name in ai_services:
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

    def test_memory_reservations_exist_for_ai_services(
        self, compose_content: dict, ai_services: list[str]
    ) -> None:
        """Test that memory reservations are defined for AI services.

        Memory reservations are important for container orchestration to ensure
        sufficient resources are available before scheduling.
        """
        services = compose_content.get("services", {})
        for service_name in ai_services:
            service = services[service_name]
            assert "deploy" in service, f"{service_name} should have deploy section"
            assert "resources" in service["deploy"], f"{service_name} deploy should have resources"
            assert "reservations" in service["deploy"]["resources"], (
                f"{service_name} resources should have reservations for proper scheduling"
            )

    def test_docker_compose_yaml_syntax_valid(self, compose_content: dict) -> None:
        """Test that docker-compose.prod.yml has valid YAML structure.

        This ensures the compose file can be parsed by docker-compose tools.
        Note: Docker Compose v2+ no longer requires the 'version' field.
        """
        # PyYAML successfully parsed the file, which means it's valid YAML
        assert isinstance(compose_content, dict), "docker-compose.prod.yml should parse to a dict"
        assert "services" in compose_content, "docker-compose.prod.yml should have services section"
