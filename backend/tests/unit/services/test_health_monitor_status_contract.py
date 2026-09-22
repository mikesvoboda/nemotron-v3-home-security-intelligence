"""Contract tests: ServiceHealthMonitor statuses vs the WebSocket status schema.

Session-learned defect (2026-09-22 sandbox bring-up): on any deployment with
restart disabled for a service (restart_cmd=None — the AI-tolerance config
shape, e.g. AI_RESTART_ENABLED=false), the monitor broadcasts the status
string "restart_disabled". EventBroadcaster.broadcast_service_status validates
every status payload against WebSocketServiceStatusData, whose
WebSocketServiceStatus enum never contained that value. Every monitor cycle
for an unhealthy restart-disabled service logged
"Service status message validation failed: ... Invalid status
'restart_disabled'" — the alert never reached any WebSocket client and the
error log drowned.

Neither side's tests caught it: the monitor unit tests
(tests/unit/core/test_health_monitor.py) mock the broadcaster and only assert
the payload carries "restart_disabled", while the broadcaster-side schema
validation is exercised only with its own enum values. The two halves agreed
independently and disagreed at the seam. These tests close the seam: every
status literal the monitor can emit must validate through the real
broadcaster validation path.

Fix: WebSocketServiceStatus gained RESTART_DISABLED; the frontend union is
its generated mirror (scripts/generate-ws-types.py imports the enum and CI
--checks the generated file). The negative-branch tests here make the
schema-side omission loud instead of silent.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.api.schemas.websocket import WebSocketServiceStatus, WebSocketServiceStatusData
from backend.services.event_broadcaster import EventBroadcaster

# Mark as unit tests
pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[4]


def _emitted_statuses() -> set[str]:
    """Collect every status literal passed to _broadcast_status in the monitor.

    Parsed from the module's AST so the probe tracks new emission sites in
    health_monitor.py automatically (it cannot drift from a hand-maintained
    list — that drift is what caused the original bug).
    """
    source = REPO_ROOT / "backend/services/health_monitor.py"
    tree = ast.parse(source.read_text())
    statuses: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
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
