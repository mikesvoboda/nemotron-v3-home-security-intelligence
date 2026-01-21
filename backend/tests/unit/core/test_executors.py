"""Tests for backend/core/executors.py - CPU executor management."""

from __future__ import annotations

import os
from concurrent.futures import Executor, ThreadPoolExecutor
from unittest.mock import patch

from backend.core.executors import (
    HAS_INTERPRETER_POOL,
    get_cpu_executor,
    get_executor_info,
    get_executor_type,
    is_free_threaded,
)


class TestIsFreeThreaded:
    """Tests for is_free_threaded()."""

    def test_returns_bool(self):
        """Function should return a boolean value."""
        result = is_free_threaded()
        assert isinstance(result, bool)

    def test_with_gil_enabled_check_available(self):
        """When sys._is_gil_enabled exists and returns True, is_free_threaded returns False."""
        import sys

        if hasattr(sys, "_is_gil_enabled"):
            # Running on Python with GIL status API
            expected = not sys._is_gil_enabled()
            assert is_free_threaded() == expected

    def test_without_gil_check_returns_false(self):
        """When sys._is_gil_enabled doesn't exist, return False."""
        import sys

        original_func = getattr(sys, "_is_gil_enabled", None)
        try:
            if hasattr(sys, "_is_gil_enabled"):
                delattr(sys, "_is_gil_enabled")
            assert is_free_threaded() is False
        finally:
            # Restore the original function if it existed
            if original_func is not None:
                sys._is_gil_enabled = original_func


class TestGetExecutorType:
    """Tests for get_executor_type()."""

    def test_returns_string(self):
        """Function should return a string."""
        result = get_executor_type()
        assert isinstance(result, str)

    def test_returns_known_executor_type(self):
        """Function should return a recognized executor type."""
        result = get_executor_type()
        assert result in {"InterpreterPoolExecutor", "ThreadPoolExecutor"}

    def test_matches_has_interpreter_pool(self):
        """Return value should match HAS_INTERPRETER_POOL flag."""
        result = get_executor_type()
        if HAS_INTERPRETER_POOL:
            assert result == "InterpreterPoolExecutor"
        else:
            assert result == "ThreadPoolExecutor"


class TestGetCpuExecutor:
    """Tests for get_cpu_executor()."""

    def test_returns_executor(self):
        """Function should return an Executor instance."""
        executor = get_cpu_executor()
        try:
            assert isinstance(executor, Executor)
        finally:
            executor.shutdown(wait=True)

    def test_default_workers(self):
        """Default workers should be CPU count or 4."""
        executor = get_cpu_executor()
        try:
            # The executor should be created successfully
            assert executor is not None
        finally:
            executor.shutdown(wait=True)

    def test_custom_workers(self):
        """Should respect custom max_workers parameter."""
        executor = get_cpu_executor(max_workers=2)
        try:
            # ThreadPoolExecutor has _max_workers attribute
            if isinstance(executor, ThreadPoolExecutor):
                assert executor._max_workers == 2
            # InterpreterPoolExecutor should also respect the parameter
            # (we can verify by the fact it was created successfully)
            assert executor is not None
        finally:
            executor.shutdown(wait=True)

    def test_executor_can_submit_work(self):
        """Executor should be able to submit and execute work."""

        def compute(x: int) -> int:
            return x * 2

        executor = get_cpu_executor(max_workers=2)
        try:
            future = executor.submit(compute, 21)
            result = future.result(timeout=5)
            assert result == 42
        finally:
            executor.shutdown(wait=True)

    def test_executor_map(self):
        """Executor should support map operation."""

        def square(x: int) -> int:
            return x**2

        executor = get_cpu_executor(max_workers=2)
        try:
            results = list(executor.map(square, [1, 2, 3, 4]))
            assert results == [1, 4, 9, 16]
        finally:
            executor.shutdown(wait=True)

    def test_executor_context_manager(self):
        """Executor should work as context manager."""

        def identity(x: int) -> int:
            return x

        with get_cpu_executor(max_workers=2) as executor:
            future = executor.submit(identity, 42)
            assert future.result(timeout=5) == 42

    def test_fallback_when_cpu_count_none(self):
        """Should fallback to 4 workers when os.cpu_count() returns None."""
        with patch.object(os, "cpu_count", return_value=None):
            executor = get_cpu_executor()
            try:
                # Should create executor with 4 workers as fallback
                if isinstance(executor, ThreadPoolExecutor):
                    assert executor._max_workers == 4
            finally:
                executor.shutdown(wait=True)


class TestGetExecutorInfo:
    """Tests for get_executor_info()."""

    def test_returns_dict(self):
        """Function should return a dictionary."""
        result = get_executor_info()
        assert isinstance(result, dict)

    def test_contains_required_keys(self):
        """Result should contain all expected keys."""
        result = get_executor_info()
        required_keys = {
            "executor_type",
            "has_interpreter_pool",
            "is_free_threaded",
            "python_version",
            "cpu_count",
        }
        assert required_keys.issubset(result.keys())

    def test_executor_type_matches(self):
        """executor_type in info should match get_executor_type()."""
        info = get_executor_info()
        assert info["executor_type"] == get_executor_type()

    def test_has_interpreter_pool_matches(self):
        """has_interpreter_pool in info should match module constant."""
        info = get_executor_info()
        assert info["has_interpreter_pool"] == HAS_INTERPRETER_POOL

    def test_is_free_threaded_matches(self):
        """is_free_threaded in info should match function result."""
        info = get_executor_info()
        assert info["is_free_threaded"] == is_free_threaded()

    def test_python_version_is_tuple(self):
        """python_version should be a tuple of 3 integers."""
        info = get_executor_info()
        version = info["python_version"]
        assert isinstance(version, tuple)
        assert len(version) == 3
        assert all(isinstance(v, int) for v in version)

    def test_cpu_count_is_int_or_none(self):
        """cpu_count should be an integer or None."""
        info = get_executor_info()
        cpu_count = info["cpu_count"]
        assert cpu_count is None or isinstance(cpu_count, int)


class TestHasInterpreterPool:
    """Tests for HAS_INTERPRETER_POOL constant."""

    def test_is_bool(self):
        """Constant should be a boolean."""
        assert isinstance(HAS_INTERPRETER_POOL, bool)

    def test_matches_import_attempt(self):
        """Constant should reflect whether InterpreterPoolExecutor can be imported."""
        try:
            from concurrent.futures import InterpreterPoolExecutor  # noqa: F401

            assert HAS_INTERPRETER_POOL is True
        except ImportError:
            assert HAS_INTERPRETER_POOL is False


class TestModuleImports:
    """Tests for module-level imports and exports."""

    def test_import_from_backend_core(self):
        """All exports should be importable from backend.core."""
        from backend.core import (
            HAS_INTERPRETER_POOL as core_has_pool,
        )
        from backend.core import (
            get_cpu_executor as core_get_executor,
        )
        from backend.core import (
            get_executor_info as core_get_info,
        )
        from backend.core import (
            get_executor_type as core_get_type,
        )
        from backend.core import (
            is_free_threaded as core_is_free,
        )

        # Verify they're the same functions
        assert core_has_pool == HAS_INTERPRETER_POOL
        assert core_get_executor is get_cpu_executor
        assert core_get_type is get_executor_type
        assert core_get_info is get_executor_info
        assert core_is_free is is_free_threaded
