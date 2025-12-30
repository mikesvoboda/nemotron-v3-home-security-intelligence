"""Tests for Docker Compose production deployment configuration.

This module validates the docker-compose.prod.yml file to ensure:
1. Valid compose file syntax
2. All required services are defined
3. Environment variable references are correct
4. Volume mounts and network configuration are valid

Bead: mb9s.11
"""

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml


class TestDockerComposeProdConfig:
    """Tests for production Docker Compose configuration."""

    @pytest.fixture
    def compose_file_path(self) -> Path:
        """Get the path to docker-compose.prod.yml."""
        # Navigate from tests/unit/ to project root
        return Path(__file__).parent.parent.parent.parent / "docker-compose.prod.yml"

    @pytest.fixture
    def compose_content(self, compose_file_path: Path) -> dict[str, Any]:
        """Parse the Docker Compose file content as YAML."""
        if not compose_file_path.exists():
            pytest.skip(f"docker-compose.prod.yml not found at {compose_file_path}")
        return yaml.safe_load(compose_file_path.read_text())

    @pytest.fixture
    def compose_raw_content(self, compose_file_path: Path) -> str:
        """Read the raw Docker Compose file content."""
        if not compose_file_path.exists():
            pytest.skip(f"docker-compose.prod.yml not found at {compose_file_path}")
        return compose_file_path.read_text()

    # ==========================================================================
    # Syntax Validation Tests
    # ==========================================================================

    def test_compose_file_exists(self, compose_file_path: Path) -> None:
        """Test that docker-compose.prod.yml exists."""
        assert compose_file_path.exists(), (
            f"docker-compose.prod.yml not found at {compose_file_path}"
        )

    def test_compose_file_valid_yaml(self, compose_file_path: Path) -> None:
        """Test that docker-compose.prod.yml is valid YAML."""
        try:
            content = yaml.safe_load(compose_file_path.read_text())
            assert isinstance(content, dict), "Compose file should be a YAML dict"
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML syntax: {e}")

    def test_compose_file_syntax_with_docker_compose(self, compose_file_path: Path) -> None:
        """Test compose file syntax using docker-compose config --quiet.

        This validates the compose file against the docker-compose schema
        and ensures all environment variable interpolations are valid.
        """
        # Check if docker-compose or docker compose is available
        docker_compose_cmd: list[str] | None = None

        # Try docker-compose first (using shutil.which for full path)
        docker_compose_path = shutil.which("docker-compose")
        if docker_compose_path:
            try:
                result = subprocess.run(  # noqa: S603 # intentional subprocess for compose validation
                    [docker_compose_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0:
                    docker_compose_cmd = [docker_compose_path]
            except subprocess.TimeoutExpired:
                pass

        # Try docker compose (plugin style) if docker-compose not found
        docker_path = shutil.which("docker")
        if docker_compose_cmd is None and docker_path:
            try:
                result = subprocess.run(  # noqa: S603 # intentional subprocess for compose validation
                    [docker_path, "compose", "version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0:
                    docker_compose_cmd = [docker_path, "compose"]
            except subprocess.TimeoutExpired:
                pass

        # Try podman-compose as fallback
        podman_compose_path = shutil.which("podman-compose")
        if docker_compose_cmd is None and podman_compose_path:
            try:
                result = subprocess.run(  # noqa: S603 # intentional subprocess for compose validation
                    [podman_compose_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0:
                    docker_compose_cmd = [podman_compose_path]
            except subprocess.TimeoutExpired:
                pass

        if docker_compose_cmd is None:
            pytest.skip("Neither docker-compose, docker compose, nor podman-compose is available")

        # Run validation command
        cmd = [*docker_compose_cmd, "-f", str(compose_file_path), "config", "--quiet"]
        result = subprocess.run(  # noqa: S603 # intentional subprocess for config validation
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=compose_file_path.parent,  # Run from project root for relative paths
            check=False,
        )

        assert result.returncode == 0, (
            f"docker-compose config validation failed:\n"
            f"Command: {' '.join(cmd)}\n"
            f"stderr: {result.stderr}\n"
            f"stdout: {result.stdout}"
        )

    # ==========================================================================
    # Required Services Tests
    # ==========================================================================

    def test_services_section_exists(self, compose_content: dict[str, Any]) -> None:
        """Test that services section exists."""
        assert "services" in compose_content, "Compose file must have 'services' section"

    def test_required_services_defined(self, compose_content: dict[str, Any]) -> None:
        """Test that all required services are defined.

        The production stack requires:
        - postgres: Database for events, detections, cameras
        - redis: Pub/sub and caching
        - backend: FastAPI application
        - frontend: React web interface
        - ai-detector: RT-DETRv2 object detection
        - ai-llm: Nemotron LLM for risk analysis
        """
        required_services = [
            "postgres",
            "redis",
            "backend",
            "frontend",
            "ai-detector",
            "ai-llm",
        ]

        services = compose_content.get("services", {})
        missing = [svc for svc in required_services if svc not in services]

        assert not missing, f"Missing required services: {missing}"

    def test_service_count(self, compose_content: dict[str, Any]) -> None:
        """Test that we have expected number of services."""
        services = compose_content.get("services", {})
        assert len(services) >= 6, f"Expected at least 6 services, found {len(services)}"

    # ==========================================================================
    # Service Configuration Tests
    # ==========================================================================

    def test_postgres_service_config(self, compose_content: dict[str, Any]) -> None:
        """Test PostgreSQL service configuration."""
        postgres = compose_content["services"].get("postgres", {})

        # Check image
        assert "postgres" in postgres.get("image", ""), "PostgreSQL must use postgres image"

        # Check port exposure
        ports = postgres.get("ports", [])
        assert any("5432" in str(p) for p in ports), "PostgreSQL must expose port 5432"

        # Check volume mount for data persistence
        volumes = postgres.get("volumes", [])
        assert any("postgres_data" in str(v) for v in volumes), (
            "PostgreSQL must have persistent data volume"
        )

        # Check healthcheck
        assert "healthcheck" in postgres, "PostgreSQL must have healthcheck configured"

    def test_redis_service_config(self, compose_content: dict[str, Any]) -> None:
        """Test Redis service configuration."""
        redis = compose_content["services"].get("redis", {})

        # Check image
        assert "redis" in redis.get("image", ""), "Redis must use redis image"

        # Check port exposure
        ports = redis.get("ports", [])
        assert any("6379" in str(p) for p in ports), "Redis must expose port 6379"

        # Check healthcheck
        assert "healthcheck" in redis, "Redis must have healthcheck configured"

    def test_backend_service_config(self, compose_content: dict[str, Any]) -> None:
        """Test Backend service configuration."""
        backend = compose_content["services"].get("backend", {})

        # Check build context
        build = backend.get("build", {})
        assert build.get("context") == "./backend", "Backend build context must be ./backend"
        assert build.get("dockerfile") == "Dockerfile.prod", "Backend must use Dockerfile.prod"

        # Check port exposure
        ports = backend.get("ports", [])
        assert any("8000" in str(p) for p in ports), "Backend must expose port 8000"

        # Check dependencies
        depends_on = backend.get("depends_on", {})
        required_deps = ["postgres", "redis", "ai-detector", "ai-llm"]
        for dep in required_deps:
            assert dep in depends_on, f"Backend must depend on {dep}"

        # Check healthcheck
        assert "healthcheck" in backend, "Backend must have healthcheck configured"

    def test_frontend_service_config(self, compose_content: dict[str, Any]) -> None:
        """Test Frontend service configuration."""
        frontend = compose_content["services"].get("frontend", {})

        # Check build context
        build = frontend.get("build", {})
        assert build.get("context") == "./frontend", "Frontend build context must be ./frontend"

        # Check port exposure
        ports = frontend.get("ports", [])
        assert len(ports) >= 1, "Frontend must expose at least one port"

        # Check dependency on backend
        depends_on = frontend.get("depends_on", {})
        assert "backend" in depends_on, "Frontend must depend on backend"

        # Check healthcheck
        assert "healthcheck" in frontend, "Frontend must have healthcheck configured"

    def test_ai_detector_service_config(self, compose_content: dict[str, Any]) -> None:
        """Test AI Detector (RT-DETRv2) service configuration."""
        detector = compose_content["services"].get("ai-detector", {})

        # Check build context
        build = detector.get("build", {})
        assert build.get("context") == "./ai/rtdetr", (
            "AI Detector build context must be ./ai/rtdetr"
        )

        # Check port exposure
        ports = detector.get("ports", [])
        assert any("8090" in str(p) for p in ports), "AI Detector must expose port 8090"

        # Check GPU resource reservation
        deploy = detector.get("deploy", {})
        resources = deploy.get("resources", {})
        reservations = resources.get("reservations", {})
        devices = reservations.get("devices", [])
        assert any(d.get("capabilities") == ["gpu"] for d in devices), (
            "AI Detector must have GPU capability reserved"
        )

        # Check healthcheck
        assert "healthcheck" in detector, "AI Detector must have healthcheck configured"

    def test_ai_llm_service_config(self, compose_content: dict[str, Any]) -> None:
        """Test AI LLM (Nemotron) service configuration."""
        llm = compose_content["services"].get("ai-llm", {})

        # Check build context
        build = llm.get("build", {})
        assert build.get("context") == "./ai/nemotron", "AI LLM build context must be ./ai/nemotron"

        # Check port exposure
        ports = llm.get("ports", [])
        assert any("8091" in str(p) for p in ports), "AI LLM must expose port 8091"

        # Check GPU resource reservation
        deploy = llm.get("deploy", {})
        resources = deploy.get("resources", {})
        reservations = resources.get("reservations", {})
        devices = reservations.get("devices", [])
        assert any(d.get("capabilities") == ["gpu"] for d in devices), (
            "AI LLM must have GPU capability reserved"
        )

        # Check healthcheck
        assert "healthcheck" in llm, "AI LLM must have healthcheck configured"

    # ==========================================================================
    # Environment Variable Tests
    # ==========================================================================

    def test_environment_variable_syntax(self, compose_raw_content: str) -> None:
        """Test that environment variable references use valid syntax.

        Docker Compose supports:
        - ${VAR} - required variable
        - ${VAR:-default} - variable with default
        - ${VAR:?error} - required variable with error message
        """
        # Find all ${...} patterns
        env_pattern = r"\$\{([^}]+)\}"
        matches = re.findall(env_pattern, compose_raw_content)

        for match in matches:
            # Valid patterns: VAR, VAR:-default, VAR:?error, VAR-default, VAR?error
            valid_pattern = r"^[A-Z_][A-Z0-9_]*(:?[-?].*)?$"
            assert re.match(valid_pattern, match), (
                f"Invalid environment variable syntax: ${{{match}}}"
            )

    def test_postgres_environment_variables(self, compose_content: dict[str, Any]) -> None:
        """Test PostgreSQL environment variables are properly configured."""
        postgres = compose_content["services"].get("postgres", {})
        env = postgres.get("environment", [])

        # Convert list format to dict for easier checking
        env_dict = {}
        for item in env:
            if "=" in item:
                key, value = item.split("=", 1)
                env_dict[key] = value

        required_vars = ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"]
        for var in required_vars:
            assert any(var in str(e) for e in env), (
                f"PostgreSQL must have {var} environment variable"
            )

    def test_backend_environment_variables(self, compose_content: dict[str, Any]) -> None:
        """Test Backend environment variables are properly configured."""
        backend = compose_content["services"].get("backend", {})
        env = backend.get("environment", [])

        required_vars = [
            "DATABASE_URL",
            "REDIS_URL",
            "RTDETR_URL",
            "NEMOTRON_URL",
        ]
        for var in required_vars:
            assert any(var in str(e) for e in env), f"Backend must have {var} environment variable"

    def test_backend_database_url_references_postgres(self, compose_raw_content: str) -> None:
        """Test that DATABASE_URL references the postgres service."""
        # Find DATABASE_URL in the compose file
        db_url_pattern = r"DATABASE_URL.*postgres.*5432"
        assert re.search(db_url_pattern, compose_raw_content), (
            "DATABASE_URL must reference postgres service on port 5432"
        )

    def test_backend_redis_url_references_redis(self, compose_raw_content: str) -> None:
        """Test that REDIS_URL references the redis service."""
        # Find REDIS_URL in the compose file
        redis_url_pattern = r"REDIS_URL.*redis.*6379"
        assert re.search(redis_url_pattern, compose_raw_content), (
            "REDIS_URL must reference redis service on port 6379"
        )

    # ==========================================================================
    # Volume Configuration Tests
    # ==========================================================================

    def test_volumes_section_exists(self, compose_content: dict[str, Any]) -> None:
        """Test that volumes section exists."""
        assert "volumes" in compose_content, "Compose file must have 'volumes' section"

    def test_required_volumes_defined(self, compose_content: dict[str, Any]) -> None:
        """Test that required named volumes are defined."""
        volumes = compose_content.get("volumes", {})

        required_volumes = ["postgres_data", "redis_data"]
        missing = [vol for vol in required_volumes if vol not in volumes]

        assert not missing, f"Missing required volumes: {missing}"

    def test_postgres_data_volume_local_driver(self, compose_content: dict[str, Any]) -> None:
        """Test PostgreSQL data volume uses local driver."""
        volumes = compose_content.get("volumes", {})
        postgres_vol = volumes.get("postgres_data", {})

        # If explicit driver specified, must be local
        if postgres_vol and isinstance(postgres_vol, dict):
            driver = postgres_vol.get("driver", "local")
            assert driver == "local", "postgres_data volume must use local driver"

    def test_backend_camera_volume_mount(self, compose_content: dict[str, Any]) -> None:
        """Test backend has camera volume mount for reading images."""
        backend = compose_content["services"].get("backend", {})
        volumes = backend.get("volumes", [])

        # Should have a volume mount for cameras
        has_camera_mount = any("/cameras" in str(v) or "foscam" in str(v).lower() for v in volumes)
        assert has_camera_mount, "Backend must have camera volume mount"

    # ==========================================================================
    # Network Configuration Tests
    # ==========================================================================

    def test_networks_section_exists(self, compose_content: dict[str, Any]) -> None:
        """Test that networks section exists."""
        assert "networks" in compose_content, "Compose file must have 'networks' section"

    def test_security_network_defined(self, compose_content: dict[str, Any]) -> None:
        """Test that security-net network is defined."""
        networks = compose_content.get("networks", {})
        assert "security-net" in networks, "security-net network must be defined"

    def test_all_services_on_security_network(self, compose_content: dict[str, Any]) -> None:
        """Test that all services are connected to security-net."""
        services = compose_content.get("services", {})

        for name, config in services.items():
            networks = config.get("networks", [])
            assert "security-net" in networks, f"Service '{name}' must be on security-net"

    def test_network_uses_bridge_driver(self, compose_content: dict[str, Any]) -> None:
        """Test that security-net uses bridge driver."""
        networks = compose_content.get("networks", {})
        security_net = networks.get("security-net", {})

        # Default is bridge, so accept if not specified or explicitly bridge
        if security_net and isinstance(security_net, dict):
            driver = security_net.get("driver", "bridge")
            assert driver == "bridge", "security-net must use bridge driver"

    # ==========================================================================
    # Health Check Configuration Tests
    # ==========================================================================

    def test_all_services_have_healthchecks(self, compose_content: dict[str, Any]) -> None:
        """Test that all services have health checks defined."""
        services = compose_content.get("services", {})

        for name, config in services.items():
            assert "healthcheck" in config, f"Service '{name}' must have healthcheck"

    def test_healthchecks_have_required_fields(self, compose_content: dict[str, Any]) -> None:
        """Test that health checks have required fields."""
        services = compose_content.get("services", {})
        required_fields = ["test", "interval", "timeout", "retries"]

        for name, config in services.items():
            healthcheck = config.get("healthcheck", {})
            for field in required_fields:
                assert field in healthcheck, (
                    f"Service '{name}' healthcheck must have '{field}' field"
                )

    def test_service_dependencies_use_health_condition(
        self, compose_content: dict[str, Any]
    ) -> None:
        """Test that service dependencies wait for healthy condition."""
        services = compose_content.get("services", {})

        for name, config in services.items():
            depends_on = config.get("depends_on", {})
            if isinstance(depends_on, dict):
                for dep_name, dep_config in depends_on.items():
                    if isinstance(dep_config, dict):
                        condition = dep_config.get("condition")
                        assert condition == "service_healthy", (
                            f"Service '{name}' dependency on '{dep_name}' "
                            f"must use condition: service_healthy"
                        )

    # ==========================================================================
    # Restart Policy Tests
    # ==========================================================================

    def test_all_services_have_restart_policy(self, compose_content: dict[str, Any]) -> None:
        """Test that all services have restart policy defined."""
        services = compose_content.get("services", {})

        for name, config in services.items():
            assert "restart" in config, f"Service '{name}' must have restart policy"

    def test_restart_policy_is_unless_stopped(self, compose_content: dict[str, Any]) -> None:
        """Test that services use unless-stopped restart policy."""
        services = compose_content.get("services", {})
        valid_policies = ["unless-stopped", "always", "on-failure"]

        for name, config in services.items():
            restart = config.get("restart", "")
            assert restart in valid_policies, (
                f"Service '{name}' has invalid restart policy: {restart}. "
                f"Expected one of: {valid_policies}"
            )

    # ==========================================================================
    # Resource Limit Tests
    # ==========================================================================

    def test_cpu_services_have_resource_limits(self, compose_content: dict[str, Any]) -> None:
        """Test that CPU-bound services have resource limits."""
        services = compose_content.get("services", {})
        cpu_services = ["postgres", "redis", "backend", "frontend"]

        for name in cpu_services:
            config = services.get(name, {})
            deploy = config.get("deploy", {})
            resources = deploy.get("resources", {})
            limits = resources.get("limits", {})

            # At least one resource limit should be defined
            has_limits = "cpus" in limits or "memory" in limits
            assert has_limits, f"Service '{name}' should have resource limits defined"

    def test_gpu_services_have_device_reservations(self, compose_content: dict[str, Any]) -> None:
        """Test that GPU services have device reservations."""
        services = compose_content.get("services", {})
        gpu_services = ["ai-detector", "ai-llm"]

        for name in gpu_services:
            config = services.get(name, {})
            deploy = config.get("deploy", {})
            resources = deploy.get("resources", {})
            reservations = resources.get("reservations", {})
            devices = reservations.get("devices", [])

            has_gpu = any(d.get("capabilities") == ["gpu"] for d in devices)
            assert has_gpu, f"Service '{name}' must have GPU device reservation"
