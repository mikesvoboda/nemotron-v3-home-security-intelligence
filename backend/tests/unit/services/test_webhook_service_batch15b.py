"""Batch-15b mutation-kill battery: CURRENT-generation webhook survivors.

Target: the 23 survivors the whserv re-check measured against the shipped +
batch-15 suites (``/tmp/redcheck-whserv.log``, rc=0, 19 KILLED / 23 SURVIVED
of the 42 CURRENT-cache keys — badge-relevant because the mutmut 3.x cache is
diff-scoped and this generation IS the denominator). Module
``backend/services/webhook_service.py``.

Survivor clusters and disposition (per-mutant, triaged against MEASURED
shipped behavior — /tmp/b15b-harness.py → /tmp/b15b-probes.json):
- SQL-shape family (keys 12-21, 11 total): shipped suites never compiled the
  trigger query. Killed here by full-shape compiled SQL-text pins (batch-14
  vehicle) plus plain-str-input shapes; ``and_(None, ...)`` / ``select(None)``
  raise TypeError at build (measured), the rest change the emitted text.
- ternary family 2/4/10: diverge and are killed. Key 2 (``= None``) makes
  the query bind NULL; key 4 (``hasattr(event_type, None)``) raises
  TypeError on EVERY input; key 10 (``else str(None)``) emits "None" for
  plain-str inputs (MEASURED shipped: ``'motion' = ANY``). Killed by the
  full-shape SQL text pins on enum AND plain-str inputs.
- ternary family 3/8/9: EQUIVALENT for every input — WebhookEventType is a
  str-subclass enum so ``str(e) == e.value`` (MEASURED); key 3
  (``hasattr(None, …)`` → False) and keys 8/9 (absent attribute spellings
  "XXvalueXX"/"VALUE") all fall to ``str(event_type)``, and for plain-str
  input shipped already takes that branch. Documented; no test admissible.
- debug-log family (25/26/28/29/30): message text + EXTRA KEY pinned EXACT.
- ``__init___1``: stored-client identity pin.

Every expected value MEASURED against shipped production this session;
production NOT bent to any mutant. No kill tallies claimed here — those come
only from the 15b lane red-check.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.schemas.outbound_webhook import WebhookEventType
from backend.services import webhook_service as W
from backend.services.webhook_service import WebhookService

pytestmark = pytest.mark.unit


def make_svc(rows=()):
    """Carrier: capture the COMPILED trigger SQL, return `rows` from scalars."""
    svc = WebhookService.__new__(WebhookService)
    cap: dict[str, str] = {}

    async def execute(stmt):
        cap["sql"] = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        res = MagicMock(name="result")
        res.scalars.return_value.all.return_value = list(rows)
        return res

    db = MagicMock(name="db")
    db.execute = AsyncMock(side_effect=execute)
    return svc, db, cap


def patched_logger():
    lg = MagicMock(name="logger")
    orig = W.logger
    W.logger = lg
    return lg, orig


class TestInitStoresClient:
    def test_http_client_stored_identity(self):
        sentinel = object()
        svc = WebhookService.__new__(WebhookService)
        WebhookService.__init__(svc, sentinel)
        assert svc._http_client is sentinel  # kills `= None` (key 1)


class TestTriggerQueryShape:
    async def test_enum_sql_full_shape(self):
        svc, db, cap = make_svc()
        lg, orig = patched_logger()
        try:
            out = await svc.trigger_webhooks_for_event(
                db, WebhookEventType.ALERT_FIRED, {"a": 1}, "evt-1"
            )
        finally:
            W.logger = orig
        where = cap["sql"].split("WHERE")[1]
        assert "outbound_webhooks.enabled IS true" in where
        assert "'alert_fired' = ANY (outbound_webhooks.event_types)" in where
        # MEASURED empty-db return
        assert out == []

    async def test_plain_string_event_type_shape(self):
        # schema-adjacent input the shipped code explicitly supports via the
        # hasattr fallback; MEASURED: emits 'motion' = ANY (not str(None)).
        svc, db, cap = make_svc()
        lg, orig = patched_logger()
        try:
            await svc.trigger_webhooks_for_event(db, "motion", {}, None)  # type: ignore[arg-type]
        finally:
            W.logger = orig
        assert "'motion' = ANY (outbound_webhooks.event_types)" in cap["sql"]


class TestTriggerLoggingShape:
    async def test_empty_path_debug_message_and_extra_exact(self):
        svc, db, _ = make_svc()
        lg, orig = patched_logger()
        try:
            await svc.trigger_webhooks_for_event(db, WebhookEventType.ALERT_FIRED, {}, None)
        finally:
            W.logger = orig
        dbg = lg.debug.call_args
        assert dbg.args[0] == "No webhooks subscribed to event type: alert_fired"
        assert dict(dbg.kwargs["extra"]) == {"event_type": "alert_fired"}

    async def test_nonempty_info_message_extra_and_delivery(self):
        row = MagicMock(name="webhook")
        svc, db, _ = make_svc(rows=[row])
        delivered = MagicMock(name="delivery")
        svc.deliver_webhook = AsyncMock(return_value=delivered)
        lg, orig = patched_logger()
        try:
            out = await svc.trigger_webhooks_for_event(
                db, WebhookEventType.ALERT_FIRED, {"d": 2}, "evt-9"
            )
        finally:
            W.logger = orig
        inf = lg.info.call_args
        assert inf.args[0] == "Triggering 1 webhooks for event type: alert_fired"
        assert dict(inf.kwargs["extra"]) == {"event_type": "alert_fired", "webhook_count": 1}
        args = svc.deliver_webhook.call_args.args
        assert args[1] is row
        assert (
            args[2] is WebhookEventType.ALERT_FIRED
        )  # identity — str-enum == str passes either way
        assert args[3] == {"d": 2}
        assert args[4] == "evt-9"
        assert out == [delivered]
