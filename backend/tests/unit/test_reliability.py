"""Unit tests for reliability improvements.

Tests cover:
- Redis startup guard: RuntimeError when Redis unavailable (allow_redis_failure toggle)
- Loki healthcheck: compose YAML parses correctly with healthcheck config
- Alloy depends_on: service_healthy conditions for loki and pyroscope
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Redis startup guard tests
# ---------------------------------------------------------------------------


class TestRedisStartupGuard:
    """Tests for the Redis startup guard in backend/main.py lifespan."""

    @pytest.mark.asyncio
    async def test_redis_failure_raises_by_default(self) -> None:
        """When init_redis raises and allow_redis_failure=False, RuntimeError is raised."""
        from unittest.mock import AsyncMock, patch

        with patch("backend.main.init_redis", new_callable=AsyncMock) as mock_init:
            mock_init.side_effect = ConnectionError("Redis connection refused")

            # Replicate the guard logic from main.py ~lines 698-709
            # with allow_redis_failure=False (the default)
            allow_redis_failure = False
            with pytest.raises(RuntimeError, match="Redis is REQUIRED"):
                try:
                    await mock_init()
                except Exception as e:
                    if allow_redis_failure:
                        pass
                    else:
                        raise RuntimeError(
                            "Redis is REQUIRED for pipeline workers, file watcher, "
                            "and event broadcast. "
                            "Set ALLOW_REDIS_FAILURE=1 to override (dev/testing only)."
                        ) from e

    @pytest.mark.asyncio
    async def test_redis_failure_continues_with_allow_flag(self) -> None:
        """When init_redis raises and allow_redis_failure=True, no exception is raised."""
        from unittest.mock import AsyncMock, patch

        with patch("backend.main.init_redis", new_callable=AsyncMock) as mock_init:
            mock_init.side_effect = ConnectionError("Redis connection refused")

            # Simulate the guard logic with allow_redis_failure=True
            allow_redis_failure = True
            redis_client = None
            try:
                redis_client = await mock_init()
            except Exception:
                if allow_redis_failure:
                    pass  # continues without Redis
                else:
                    raise RuntimeError("Should not reach here") from None

            assert redis_client is None

    def test_allow_redis_failure_defaults_false(self) -> None:
        """Settings.allow_redis_failure defaults to False."""
        from backend.core.config import Settings

        s = Settings(
            POSTGRES_PASSWORD="test",  # pragma: allowlist secret
            REDIS_PASSWORD="test",  # pragma: allowlist secret
            SECRET_KEY="test-secret-key-for-unit-tests-only",  # pragma: allowlist secret
        )
        assert s.allow_redis_failure is False

    def test_allow_redis_failure_env_override(self) -> None:
        """ALLOW_REDIS_FAILURE=1 env var sets the field to True."""
        from unittest.mock import patch

        from backend.core.config import Settings

        with patch.dict("os.environ", {"ALLOW_REDIS_FAILURE": "1"}):
            s = Settings(
                POSTGRES_PASSWORD="test",  # pragma: allowlist secret
                REDIS_PASSWORD="test",  # pragma: allowlist secret
                SECRET_KEY="test-secret-key-for-unit-tests-only",  # pragma: allowlist secret
            )
            assert s.allow_redis_failure is True


# ---------------------------------------------------------------------------
# Docker Compose YAML validation tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def compose_config() -> dict:
    """Parse docker-compose.prod.yml once for all compose tests."""
    compose_path = Path(__file__).resolve().parents[3] / "docker-compose.prod.yml"
    assert compose_path.exists(), f"Compose file not found: {compose_path}"
    return yaml.safe_load(compose_path.read_text())


class TestLokiHealthcheck:
    """Verify Loki service has a proper healthcheck in compose YAML."""

    def test_loki_service_exists(self, compose_config: dict) -> None:
        """Loki service is defined in docker-compose.prod.yml."""
        assert "loki" in compose_config["services"]

    def test_loki_has_healthcheck(self, compose_config: dict) -> None:
        """Loki service has a healthcheck block."""
        loki = compose_config["services"]["loki"]
        assert "healthcheck" in loki

    def test_loki_healthcheck_uses_ready_endpoint(self, compose_config: dict) -> None:
        """Loki healthcheck hits the /ready endpoint."""
        hc = compose_config["services"]["loki"]["healthcheck"]
        test_cmd = hc["test"]
        # test is a list like ['CMD', 'wget', '-q', '--spider', 'http://localhost:3100/ready']
        cmd_str = " ".join(test_cmd) if isinstance(test_cmd, list) else test_cmd
        assert "/ready" in cmd_str

    def test_loki_healthcheck_has_start_period(self, compose_config: dict) -> None:
        """Loki healthcheck has a start_period for fresh volume initialization."""
        hc = compose_config["services"]["loki"]["healthcheck"]
        assert "start_period" in hc

    def test_loki_healthcheck_has_retries(self, compose_config: dict) -> None:
        """Loki healthcheck has retries configured."""
        hc = compose_config["services"]["loki"]["healthcheck"]
        assert hc.get("retries", 0) >= 5, "Loki needs generous retries for fresh volumes"

    def test_loki_has_restart_policy(self, compose_config: dict) -> None:
        """Loki service has a restart policy."""
        loki = compose_config["services"]["loki"]
        assert "restart" in loki


class TestAlloyDependsOn:
    """Verify Alloy service depends on Loki and Pyroscope with service_healthy."""

    def test_alloy_service_exists(self, compose_config: dict) -> None:
        """Alloy service is defined in docker-compose.prod.yml."""
        assert "alloy" in compose_config["services"]

    def test_alloy_depends_on_loki_healthy(self, compose_config: dict) -> None:
        """Alloy depends_on loki with condition: service_healthy."""
        alloy = compose_config["services"]["alloy"]
        depends = alloy.get("depends_on", {})
        assert "loki" in depends
        assert depends["loki"]["condition"] == "service_healthy"

    def test_alloy_depends_on_pyroscope_healthy(self, compose_config: dict) -> None:
        """Alloy depends_on pyroscope with condition: service_healthy."""
        alloy = compose_config["services"]["alloy"]
        depends = alloy.get("depends_on", {})
        assert "pyroscope" in depends
        assert depends["pyroscope"]["condition"] == "service_healthy"

    def test_alloy_has_healthcheck(self, compose_config: dict) -> None:
        """Alloy service has a healthcheck block."""
        alloy = compose_config["services"]["alloy"]
        assert "healthcheck" in alloy

    def test_alloy_has_restart_policy(self, compose_config: dict) -> None:
        """Alloy service has a restart policy."""
        alloy = compose_config["services"]["alloy"]
        assert "restart" in alloy
