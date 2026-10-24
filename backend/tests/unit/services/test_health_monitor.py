"""Unit tests for ServiceHealthMonitor (NEM-5057).

Tests cover:
- Health monitor task naming for asyncio debugging
- Start/stop lifecycle management
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.schemas.websocket import WebSocketServiceStatus, WebSocketServiceStatusData
from backend.services.event_broadcaster import EventBroadcaster
from backend.services.health_monitor import ServiceHealthMonitor
from backend.services.service_managers import ServiceConfig


@pytest.fixture
def mock_manager() -> MagicMock:
    """Create a mock ServiceManager."""
    manager = MagicMock()
    manager.check_health = AsyncMock(return_value=True)
    manager.restart = AsyncMock(return_value=True)
    return manager


@pytest.fixture
def mock_broadcaster() -> MagicMock:
    """Create a mock EventBroadcaster."""
    broadcaster = MagicMock()
    broadcaster.broadcast_service_status = AsyncMock()
    return broadcaster


@pytest.fixture
def service_config() -> ServiceConfig:
    """Create a test service configuration."""
    return ServiceConfig(
        name="test_service",
        health_url="http://localhost:8000/health",
        restart_cmd="echo restart",
        max_retries=3,
        backoff_base=0.01,  # Very short for testing
    )


class TestHealthMonitorTaskNaming:
    """Tests for NEM-5057: asyncio.create_task() should have name parameter."""

    @pytest.mark.asyncio
    async def test_start_creates_named_task(
        self,
        mock_manager: MagicMock,
        mock_broadcaster: MagicMock,
        service_config: ServiceConfig,
    ) -> None:
        """Test that start() creates a task with a descriptive name for debugging."""
        monitor = ServiceHealthMonitor(
            manager=mock_manager,
            services=[service_config],
            broadcaster=mock_broadcaster,
            check_interval=0.05,
        )

        await monitor.start()
        try:
            # Verify task exists and has a name
            assert monitor._task is not None
            task_name = monitor._task.get_name()
            # Task should have a descriptive name containing "health"
            assert "health" in task_name.lower(), (
                f"Task name should contain 'health' for debugging, got: {task_name}"
            )
        finally:
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_task_name_includes_monitor_identifier(
        self,
        mock_manager: MagicMock,
        mock_broadcaster: MagicMock,
        service_config: ServiceConfig,
    ) -> None:
        """Test that the task name is specific enough for debugging multiple monitors."""
        monitor = ServiceHealthMonitor(
            manager=mock_manager,
            services=[service_config],
            broadcaster=mock_broadcaster,
            check_interval=0.05,
        )

        await monitor.start()
        try:
            task_name = monitor._task.get_name()
            # Name should be descriptive - check it's not just "Task-N"
            assert not task_name.startswith("Task-"), (
                f"Task should have a custom name, not default Task-N: {task_name}"
            )
        finally:
            await monitor.stop()


# Mark as unit tests
pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[4]


_MUTANT_DEF = re.compile(r"__mutmut_\d+$")


def _emitted_statuses() -> set[str]:
    """Collect every status literal passed to _broadcast_status in the monitor.

    Parsed from the module's AST so the probe tracks new emission sites in
    health_monitor.py automatically (it cannot drift from a hand-maintained
    list — that drift is what caused the original bug).

    Mutation-runner safe: under mutmut this file runs from the mutant home,
    where the source file additionally holds per-mutant variant copies of
    every function (def names suffixed ``__mutmut_<N>``) carrying mutated
    literals like "FAILED"/"XXunhealthyXX". The contract is about the SHIPPED
    module, so calls inside numbered variant defs are pruned. A plain repo
    checkout has no such defs (no-op there); ``__mutmut_orig`` copies are the
    shipped bodies and stay. Verified: pruned mutant-copy probe returns
    exactly the shipped status set.
    """
    source = REPO_ROOT / "backend/services/health_monitor.py"
    tree = ast.parse(source.read_text())
    mutant_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if _MUTANT_DEF.search(node.name):
                mutant_lines.update(range(node.lineno, node.end_lineno + 1))
    statuses: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if node.lineno in mutant_lines:
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "_broadcast_status":
                if len(node.args) >= 2:
                    arg = node.args[1]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        statuses.add(arg.value)
    return statuses


class TestMonitorBroadcasterStatusContract:
    """Every monitor-emittable status must satisfy the broadcast schema."""

    def test_probe_finds_monitor_status_literals(self) -> None:
        # Guard against the AST probe silently finding nothing (e.g. after a
        # refactor changed the call shape) — a vacuous pass is worse than a
        # missing test.
        statuses = _emitted_statuses()
        assert "unhealthy" in statuses
        assert "restart_disabled" in statuses
        assert "healthy" in statuses

    def test_all_emitted_statuses_validate_against_ws_schema(self) -> None:
        for status in sorted(_emitted_statuses()):
            data = WebSocketServiceStatusData.model_validate(
                {"service": "test_service", "status": status, "message": "contract probe"}
            )
            assert data.status == WebSocketServiceStatus(status), (
                f"health_monitor emits status '{status}' but the WebSocket "
                f"schema enum cannot represent it"
            )

    def test_restart_disabled_is_broadcastable(self) -> None:
        # The specific session-learned defect: an unhealthy service with
        # restart disabled (restart_cmd=None) enters this branch every monitor
        # cycle. The status must survive broadcast validation end-to-end.
        payload = {
            "type": "service_status",
            "data": {
                "service": "test_service",
                "status": "restart_disabled",
                "message": "Service unhealthy but automatic restart is disabled",
            },
            "timestamp": "2026-09-22T00:00:00+00:00",
        }
        validated = WebSocketServiceStatusData.model_validate(payload["data"])
        assert validated.status is WebSocketServiceStatus.RESTART_DISABLED

    @pytest.mark.asyncio
    async def test_broadcast_service_status_accepts_restart_disabled(
        self, mock_redis_for_broadcaster
    ) -> None:
        # End-to-end through the real EventBroadcaster validation path
        # (broadcast_service_status raises ValueError on schema rejection —
        # the exact call that failed every cycle in the live sandbox).
        broadcaster = EventBroadcaster(redis_client=mock_redis_for_broadcaster)
        count = await broadcaster.broadcast_service_status(
            {
                "type": "service_status",
                "data": {
                    "service": "test_service",
                    "status": "restart_disabled",
                    "message": "Service unhealthy but automatic restart is disabled",
                },
                "timestamp": "2026-09-22T00:00:00+00:00",
            }
        )
        assert count == 1
        published = mock_redis_for_broadcaster.publish.call_args[0][1]
        assert published["data"]["status"] == "restart_disabled"


@pytest.fixture
def mock_redis_for_broadcaster():
    from unittest.mock import AsyncMock, MagicMock

    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=1)
    redis.pubsub = MagicMock()
    return redis
