"""M1: `WebSocketEventData.notify` is the analyzer's notify decision.

The key is ABSENT where no decision was made (replay, events from other
emitters); a consumer must read absence as "no decision", never as False. A
present value is a real bool, and the field validates through the shipped
schema like `verification` does.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.api.schemas.websocket import WebSocketEventData


def _payload(**extra: Any) -> dict[str, Any]:
    return {
        "id": 1,
        "event_id": 1,
        "batch_id": "b1",
        "camera_id": "front_door",
        "risk_score": 85,
        "risk_level": "critical",
        "summary": "A person stands at the door.",
        "reasoning": "Criterion evidence reviewed.",
        "started_at": "2026-10-03T12:00:00",
        **extra,
    }


class TestNotifyField:
    @pytest.mark.parametrize("decision", [True, False])
    def test_a_decision_is_carried_as_a_bool(self, decision: bool) -> None:
        dumped = WebSocketEventData.model_validate(_payload(notify=decision)).model_dump(
            mode="json"
        )
        assert dumped["notify"] is decision

    def test_no_decision_leaves_the_key_absent_not_false(self) -> None:
        dumped = WebSocketEventData.model_validate(_payload()).model_dump(mode="json")
        assert "notify" not in dumped

    def test_an_explicit_none_is_also_absent(self) -> None:
        dumped = WebSocketEventData.model_validate(_payload(notify=None)).model_dump(mode="json")
        assert "notify" not in dumped
