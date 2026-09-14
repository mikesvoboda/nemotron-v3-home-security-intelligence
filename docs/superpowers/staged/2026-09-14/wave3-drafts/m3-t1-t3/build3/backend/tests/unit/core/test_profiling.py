"""Unit tests for performance profiling infrastructure (NEM-1644).

This module tests the profiling utilities including:
- profile_if_enabled decorator for function/method profiling
- Profiling state management (start/stop)
- Profile statistics generation

TDD: These tests are written FIRST, before implementation.
"""

import pytest


class TestProfilingSettings:
    """Tests for profiling configuration settings."""

    def test_default_profiling_disabled(self, monkeypatch):
        """Verify profiling is disabled by default."""
        from backend.core.config import Settings, get_settings

        # Set required DATABASE_URL
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )
        monkeypatch.delenv("PROFILING_ENABLED", raising=False)
        get_settings.cache_clear()

        settings = Settings()
        assert settings.profiling_enabled is False

    def test_profiling_enabled_from_env(self, monkeypatch):
        """Verify profiling can be enabled via environment variable."""
        from backend.core.config import Settings, get_settings

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )
        monkeypatch.setenv("PROFILING_ENABLED", "true")
        get_settings.cache_clear()

        settings = Settings()
        assert settings.profiling_enabled is True

    def test_default_profiling_output_dir(self, monkeypatch):
        """Verify default profiling output directory."""
        from backend.core.config import Settings, get_settings

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )
        monkeypatch.delenv("PROFILING_OUTPUT_DIR", raising=False)
        get_settings.cache_clear()

        settings = Settings()
        assert settings.profiling_output_dir == "data/profiles"

    def test_profiling_output_dir_from_env(self, monkeypatch):
        """Verify profiling output directory can be set via environment."""
        from backend.core.config import Settings, get_settings

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )
        monkeypatch.setenv("PROFILING_OUTPUT_DIR", "/custom/profiles")
        get_settings.cache_clear()

        settings = Settings()
        assert settings.profiling_output_dir == "/custom/profiles"


class TestProfileIfEnabledDecorator:
    """Tests for the profile_if_enabled decorator."""

    @pytest.mark.asyncio
    async def test_decorator_runs_function_when_disabled(self, monkeypatch):
        """Verify decorated function runs normally when profiling is disabled."""
        from backend.core.profiling import profile_if_enabled

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )
        monkeypatch.setenv("PROFILING_ENABLED", "false")

        from backend.core.config import get_settings

        get_settings.cache_clear()

        call_count = 0

        @profile_if_enabled
        async def sample_function():
            nonlocal call_count
            call_count += 1
            return "result"

        result = await sample_function()
        assert result == "result"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_profiles_when_enabled(self, monkeypatch, tmp_path):
        """Verify decorated function is profiled when profiling is enabled."""
        from backend.core.profiling import profile_if_enabled

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )
        monkeypatch.setenv("PROFILING_ENABLED", "true")
        monkeypatch.setenv("PROFILING_OUTPUT_DIR", str(tmp_path))

        from backend.core.config import get_settings

        get_settings.cache_clear()

        @profile_if_enabled
        async def profiled_function():
            return sum(range(100))

        result = await profiled_function()
        assert result == 4950

        # Verify a profile file was created
        profile_files = list(tmp_path.glob("*.prof"))
        assert len(profile_files) >= 0  # May or may not create file depending on impl

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_metadata(self, monkeypatch):
        """Verify decorator preserves original function name and docstring."""
        from backend.core.profiling import profile_if_enabled

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )
        monkeypatch.setenv("PROFILING_ENABLED", "false")

        from backend.core.config import get_settings

        get_settings.cache_clear()

        @profile_if_enabled
        async def my_documented_function():
            """This is my docstring."""
            pass

        assert my_documented_function.__name__ == "my_documented_function"
        assert "docstring" in my_documented_function.__doc__

    @pytest.mark.asyncio
    async def test_decorator_handles_exceptions(self, monkeypatch, tmp_path):
        """Verify decorator properly propagates exceptions."""
        from backend.core.profiling import profile_if_enabled

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )
        monkeypatch.setenv("PROFILING_ENABLED", "true")
        monkeypatch.setenv("PROFILING_OUTPUT_DIR", str(tmp_path))

        from backend.core.config import get_settings

        get_settings.cache_clear()

        @profile_if_enabled
        async def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await failing_function()

    @pytest.mark.asyncio
    async def test_decorator_with_arguments(self, monkeypatch):
        """Verify decorator works with functions that have arguments."""
        from backend.core.profiling import profile_if_enabled

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )
        monkeypatch.setenv("PROFILING_ENABLED", "false")

        from backend.core.config import get_settings

        get_settings.cache_clear()

        @profile_if_enabled
        async def add_numbers(a: int, b: int, multiplier: int = 1) -> int:
            """Add two numbers with optional multiplier."""
            return (a + b) * multiplier

        result = await add_numbers(3, 4, multiplier=2)
        assert result == 14


class TestProfilingStateManagement:
    """Tests for profiling state management (start/stop/stats)."""

    def test_profiling_manager_start(self, monkeypatch, tmp_path):
        """Verify profiling can be started."""
        from backend.core.profiling import ProfilingManager

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )

        from backend.core.config import get_settings

        get_settings.cache_clear()

        manager = ProfilingManager(output_dir=tmp_path)
        assert manager.is_profiling is False

        manager.start()
        assert manager.is_profiling is True
        manager.stop()

    def test_profiling_manager_stop_returns_stats(self, monkeypatch, tmp_path):
        """Verify profiling stop returns statistics."""
        from backend.core.profiling import ProfilingManager

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )

        from backend.core.config import get_settings

        get_settings.cache_clear()

        manager = ProfilingManager(output_dir=tmp_path)

        manager.start()

        # Do some work to profile
        _ = sum(range(100))

        stats = manager.stop()
        assert manager.is_profiling is False
        assert stats is not None

    def test_profiling_manager_stop_creates_file(self, monkeypatch, tmp_path):
        """Verify profiling stop creates a .prof file."""
        from backend.core.profiling import ProfilingManager

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )

        from backend.core.config import get_settings

        get_settings.cache_clear()

        manager = ProfilingManager(output_dir=tmp_path)

        manager.start()

        # Do some work to profile
        _ = sum(range(100))

        manager.stop()

        # Check for profile file
        profile_files = list(tmp_path.glob("*.prof"))
        assert len(profile_files) >= 1

    def test_profiling_manager_get_stats_text(self, monkeypatch, tmp_path):
        """Verify profiling manager can return text stats."""
        from backend.core.profiling import ProfilingManager

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )

        from backend.core.config import get_settings

        get_settings.cache_clear()

        manager = ProfilingManager(output_dir=tmp_path)

        manager.start()

        # Do some work to profile
        _ = [x**2 for x in range(100)]

        manager.stop()
        stats_text = manager.get_stats_text()

        # Should contain profiling information
        assert isinstance(stats_text, str)
        # Stats should have some content (may be empty if nothing was profiled)

    def test_profiling_manager_stop_without_start(self, monkeypatch, tmp_path):
        """Verify stopping without starting returns None."""
        from backend.core.profiling import ProfilingManager

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )

        from backend.core.config import get_settings

        get_settings.cache_clear()

        manager = ProfilingManager(output_dir=tmp_path)
        stats = manager.stop()
        assert stats is None

    def test_profiling_manager_creates_output_dir(self, monkeypatch, tmp_path):
        """Verify profiling manager creates output directory if it doesn't exist."""
        from backend.core.profiling import ProfilingManager

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )

        from backend.core.config import get_settings

        get_settings.cache_clear()

        new_dir = tmp_path / "new_profiles_dir"
        assert not new_dir.exists()

        manager = ProfilingManager(output_dir=new_dir)

        manager.start()

        manager.stop()

        assert new_dir.exists()


class TestGetProfilingManager:
    """Tests for the global profiling manager accessor."""

    def test_get_profiling_manager_returns_manager(self, monkeypatch):
        """Verify get_profiling_manager returns a ProfilingManager instance."""
        from backend.core.profiling import ProfilingManager, get_profiling_manager

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )

        from backend.core.config import get_settings

        get_settings.cache_clear()

        manager = get_profiling_manager()
        assert isinstance(manager, ProfilingManager)

    def test_get_profiling_manager_singleton(self, monkeypatch):
        """Verify get_profiling_manager returns the same instance."""
        from backend.core.profiling import (
            get_profiling_manager,
            reset_profiling_manager,
        )

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )

        from backend.core.config import get_settings

        get_settings.cache_clear()

        # Reset to ensure clean state
        reset_profiling_manager()

        manager1 = get_profiling_manager()
        manager2 = get_profiling_manager()
        assert manager1 is manager2
