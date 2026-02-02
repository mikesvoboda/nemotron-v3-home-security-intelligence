"""Tests to validate Docker Compose security hardening for AI container services.

NEM-4976: Apply security hardening to AI container services

This module verifies that all AI services in docker-compose.prod.yml have
proper security hardening applied, including:
- no-new-privileges:true (prevents privilege escalation)
- cap_drop: ALL (drops all Linux capabilities by default)

These security controls follow the principle of least privilege and prevent
container escape attacks.
"""

from pathlib import Path
from typing import ClassVar

import pytest
import yaml


class TestDockerComposeSecurityHardening:
    """Tests for Docker Compose production security configuration."""

    # AI services that require security hardening
    AI_SERVICES: ClassVar[list[str]] = [
        "ai-yolo26",
        "ai-llm",
        "ai-florence",
        "ai-clip",
        "ai-enrichment",
        "ai-enrichment-light",
    ]

    @pytest.fixture
    def docker_compose_path(self) -> Path:
        """Get the path to docker-compose.prod.yml."""
        # Navigate from tests/security/ to project root
        return Path(__file__).parent.parent.parent.parent / "docker-compose.prod.yml"

    @pytest.fixture
    def compose_config(self, docker_compose_path: Path) -> dict:
        """Load and parse docker-compose.prod.yml."""
        if not docker_compose_path.exists():
            pytest.skip(f"docker-compose.prod.yml not found at {docker_compose_path}")
        return yaml.safe_load(docker_compose_path.read_text())

    def test_docker_compose_prod_exists(self, docker_compose_path: Path) -> None:
        """Test that docker-compose.prod.yml exists."""
        assert docker_compose_path.exists(), (
            f"docker-compose.prod.yml not found at {docker_compose_path}"
        )

    def test_all_ai_services_defined(self, compose_config: dict) -> None:
        """Test that all expected AI services are defined in the compose file."""
        services = compose_config.get("services", {})
        for service_name in self.AI_SERVICES:
            assert service_name in services, (
                f"AI service '{service_name}' not found in docker-compose.prod.yml"
            )

    @pytest.mark.parametrize("service_name", AI_SERVICES)
    def test_ai_service_has_no_new_privileges(
        self, compose_config: dict, service_name: str
    ) -> None:
        """Test that AI service has no-new-privileges:true security option.

        no-new-privileges prevents processes inside the container from gaining
        additional privileges via setuid/setgid executables. This is a critical
        security control that prevents privilege escalation attacks.
        """
        services = compose_config.get("services", {})
        service = services.get(service_name, {})

        security_opts = service.get("security_opt", [])
        assert "no-new-privileges:true" in security_opts, (
            f"AI service '{service_name}' missing 'no-new-privileges:true' in security_opt. "
            "Add security_opt: ['no-new-privileges:true'] to prevent privilege escalation."
        )

    @pytest.mark.parametrize("service_name", AI_SERVICES)
    def test_ai_service_drops_all_capabilities(
        self, compose_config: dict, service_name: str
    ) -> None:
        """Test that AI service drops all Linux capabilities.

        Dropping all capabilities follows the principle of least privilege.
        Containers should only have the minimum capabilities required to function.
        If specific capabilities are needed, they should be explicitly added back.
        """
        services = compose_config.get("services", {})
        service = services.get(service_name, {})

        cap_drop = service.get("cap_drop", [])
        assert "ALL" in cap_drop, (
            f"AI service '{service_name}' missing 'ALL' in cap_drop. "
            "Add cap_drop: ['ALL'] to drop all Linux capabilities by default."
        )

    @pytest.mark.parametrize("service_name", AI_SERVICES)
    def test_ai_service_no_privileged_mode(self, compose_config: dict, service_name: str) -> None:
        """Test that AI service does not run in privileged mode.

        Privileged mode gives the container full access to host devices and
        kernel capabilities. AI services should never run privileged.
        """
        services = compose_config.get("services", {})
        service = services.get(service_name, {})

        privileged = service.get("privileged", False)
        assert not privileged, (
            f"AI service '{service_name}' has privileged: true. "
            "AI services must not run in privileged mode for security."
        )

    @pytest.mark.parametrize("service_name", AI_SERVICES)
    def test_ai_service_no_sys_admin_capability(
        self, compose_config: dict, service_name: str
    ) -> None:
        """Test that AI service does not add SYS_ADMIN capability.

        SYS_ADMIN is a dangerous capability that effectively grants root-like
        privileges. AI services should never require this capability.
        """
        services = compose_config.get("services", {})
        service = services.get(service_name, {})

        cap_add = service.get("cap_add", [])
        assert "SYS_ADMIN" not in cap_add, (
            f"AI service '{service_name}' has SYS_ADMIN in cap_add. "
            "AI services should not require SYS_ADMIN capability."
        )

    def test_security_hardening_consistency(self, compose_config: dict) -> None:
        """Test that security hardening is consistent across all AI services.

        All AI services should have identical security configurations to ensure
        a consistent security posture.
        """
        services = compose_config.get("services", {})

        security_configs = []
        for service_name in self.AI_SERVICES:
            service = services.get(service_name, {})
            config = {
                "security_opt": set(service.get("security_opt", [])),
                "cap_drop": set(service.get("cap_drop", [])),
                "privileged": service.get("privileged", False),
            }
            security_configs.append((service_name, config))

        # Compare all configs to the first one
        first_name, first_config = security_configs[0]
        for service_name, config in security_configs[1:]:
            assert config == first_config, (
                f"Security configuration mismatch between '{first_name}' and '{service_name}'. "
                "All AI services should have consistent security hardening."
            )


class TestExistingSecurityHardening:
    """Tests to verify existing infrastructure services maintain their security hardening."""

    # Infrastructure services that should already have security hardening
    INFRASTRUCTURE_SERVICES: ClassVar[list[str]] = [
        "postgres",
        "redis",
        "go2rtc",
        "prometheus",
        "grafana",
        "alertmanager",
        "blackbox-exporter",
        "redis-exporter",
        "json-exporter",
        "loki",
        "pyroscope",
        "jaeger",
        "elasticsearch",
        "node-exporter",
        "cadvisor",
    ]

    @pytest.fixture
    def docker_compose_path(self) -> Path:
        """Get the path to docker-compose.prod.yml."""
        return Path(__file__).parent.parent.parent.parent / "docker-compose.prod.yml"

    @pytest.fixture
    def compose_config(self, docker_compose_path: Path) -> dict:
        """Load and parse docker-compose.prod.yml."""
        if not docker_compose_path.exists():
            pytest.skip(f"docker-compose.prod.yml not found at {docker_compose_path}")
        return yaml.safe_load(docker_compose_path.read_text())

    @pytest.mark.parametrize("service_name", INFRASTRUCTURE_SERVICES)
    def test_infrastructure_service_has_security_opt(
        self, compose_config: dict, service_name: str
    ) -> None:
        """Test that infrastructure services have security_opt defined.

        This ensures existing security hardening is not accidentally removed.
        """
        services = compose_config.get("services", {})
        if service_name not in services:
            pytest.skip(f"Service '{service_name}' not in compose file")

        service = services.get(service_name, {})

        # Services with security_opt should have no-new-privileges
        security_opts = service.get("security_opt", [])
        if security_opts:
            assert "no-new-privileges:true" in security_opts, (
                f"Infrastructure service '{service_name}' has security_opt but missing "
                "'no-new-privileges:true'. This may indicate accidental security regression."
            )


class TestComposeConfigValidation:
    """Tests to validate docker-compose.prod.yml can be parsed and validated."""

    @pytest.fixture
    def docker_compose_path(self) -> Path:
        """Get the path to docker-compose.prod.yml."""
        return Path(__file__).parent.parent.parent.parent / "docker-compose.prod.yml"

    def test_compose_file_is_valid_yaml(self, docker_compose_path: Path) -> None:
        """Test that docker-compose.prod.yml is valid YAML."""
        if not docker_compose_path.exists():
            pytest.skip(f"docker-compose.prod.yml not found at {docker_compose_path}")

        try:
            content = docker_compose_path.read_text()
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            pytest.fail(f"docker-compose.prod.yml contains invalid YAML: {e}")

    def test_compose_file_has_services_section(self, docker_compose_path: Path) -> None:
        """Test that docker-compose.prod.yml has a services section."""
        if not docker_compose_path.exists():
            pytest.skip(f"docker-compose.prod.yml not found at {docker_compose_path}")

        content = yaml.safe_load(docker_compose_path.read_text())
        assert "services" in content, "docker-compose.prod.yml missing 'services' section"
        assert isinstance(content["services"], dict), "'services' section should be a dictionary"
