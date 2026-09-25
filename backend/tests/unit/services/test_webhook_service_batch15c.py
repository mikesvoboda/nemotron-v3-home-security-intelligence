"""Batch-15c mutation-kill battery: whserv2's four true-gap survivors + the
wh15c discord-default gap.

Measured red-check inputs (this session, no assumptions):
- ``whserv2`` (42 CURRENT-cache keys vs shipped + batch-15 + batch-15b)
  landed 37 KILLED / 5 SURVIVED (``/tmp/redcheck-whserv2.log``, rc=0, source
  clean). Survivors {2,4,8,9,14} triaged against the FEED SHAPES
  (``/tmp/extracts/webhook_service.tsv`` full minus/plus, dumped this
  session) — and two of my batch-15b claims were WRONG, corrected here:
  * key 2 is ``and False`` (not ``= None`` as the 15b note said) and key 4 is
    ``hasattr(None, "value")`` (not TypeError): BOTH make the ternary always
    take ``str(event_type)``. For str-subclass enums and plain strings that
    is invisible (measured equivalence), but a NON-str input carrying a
    ``.value`` attribute diverges — shipped binds ``custom_duck`` (the
    ``.value``), the mutants bind ``DUCK`` (``str(obj)``). MEASURED shipped
    duck-input WHERE clause via /tmp/b15c-duck.py; killed by the duck pin.
  * keys 8/9 (attribute spellings "XXvalueXX"/"VALUE") are the SAME
    str-vs-value divergence on the same duck input — same pin kills them;
    they stay documented EQUIVALENT for enum/plain-str inputs only.
  * key 3 (``or True``, always ``.value`` branch) is NOT equivalent after
    all: on plain-str input the forced ``.value`` raises AttributeError
    (measured). It was already KILLED by the batch-15b plain-str shape test
    in whserv2 — the 15b docstring's "keys 3/8/9 equivalent" claim is
    superseded by this row.
  * key 14 ``select(OutboundWebhook)`` -> ``select(None)`` changes the
    SELECT head to ``SELECT NULL AS anon_1`` while the WHERE clause stays
    intact — the 15b test asserted into ``sql.split("WHERE")[1]`` only, so
    it could never see it. Killed by a SELECT-head prefix pin (full
    MEASURED 18-column head from /tmp/b15c-probes.json).
- ``wh15c2`` (77-key batch-15-era feed vs batch-15 battery) landed 76 KILLED
  / 1 SURVIVED: ``_format_discord_payload__mutmut_9`` swaps the default
  ``payload.get("event_type", "event")`` -> ``"EVENT"``, which only shows in
  the embed TITLE (``"event".title() == "Event"``). Killed by pinning the
  MEASURED shipped titles (absent event_type -> title "Event";
  "alert_fired" -> "Alert Fired"; fields verified verbatim).

Every expected value MEASURED against shipped production this session;
production NOT bent to any mutant. No kill tallies claimed here — those
come only from the whserv3/wh15d lane red-checks.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services import webhook_service as W
from backend.services.webhook_service import WebhookService

pytestmark = pytest.mark.unit


class DuckEventType:
    """Non-str input carrying .value where str(obj) != obj.value — the only
    input class that separates the ternary mutants from shipped (measured)."""

    value = "custom_duck"

    def __str__(self) -> str:
        return "DUCK"


def make_svc(rows=()):
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


class TestValueAttributeBinding:
    async def test_duck_input_binds_value_not_str(self):
        # MEASURED shipped: "'custom_duck' = ANY (…)" — the .value branch.
        # Mutants 2 (and False), 4 (hasattr(None,"value")), 8/9 (spelling
        # "XXvalueXX"/"VALUE") all fall to str(obj) -> binds "DUCK".
        svc, db, cap = make_svc()
        lg, orig = patched_logger()
        try:
            await svc.trigger_webhooks_for_event(db, DuckEventType(), {}, None)  # type: ignore[arg-type]
        finally:
            W.logger = orig
        where = cap["sql"].split("WHERE")[1]
        assert "'custom_duck' = ANY (outbound_webhooks.event_types)" in where
        assert "'DUCK'" not in cap["sql"]


class TestSelectHeadShape:
    async def test_select_head_full_columns(self):
        # key 14 select(None) emits "SELECT NULL AS anon_1" — WHERE-only
        # asserts are blind to it; pin the MEASURED shipped head prefix.
        svc, db, cap = make_svc()
        lg, orig = patched_logger()
        try:
            from backend.api.schemas.outbound_webhook import WebhookEventType

            await svc.trigger_webhooks_for_event(db, WebhookEventType.ALERT_FIRED, {}, None)
        finally:
            W.logger = orig
        assert cap["sql"].startswith(
            "SELECT outbound_webhooks.id, outbound_webhooks.name, "
            "outbound_webhooks.url, outbound_webhooks.event_types, "
            "outbound_webhooks.integration_type, outbound_webhooks.enabled, "
            "outbound_webhooks.auth_config, outbound_webhooks.custom_headers, "
            "outbound_webhooks.payload_template, outbound_webhooks.max_retries, "
            "outbound_webhooks.retry_delay_seconds, outbound_webhooks.signing_secret, "
            "outbound_webhooks.created_at, outbound_webhooks.updated_at, "
            "outbound_webhooks.total_deliveries, outbound_webhooks.successful_deliveries, "
            "outbound_webhooks.last_delivery_at, outbound_webhooks.last_delivery_status"
        )


class TestDiscordTitleDefault:
    def test_missing_event_type_title_exact(self):
        # wh15c2 survivor: default "event" -> "EVENT" changes title
        # "Event" -> "EVENT". MEASURED shipped title + fields verbatim.
        svc = WebhookService.__new__(WebhookService)
        out = svc._format_discord_payload({"data": {"x": 1}})
        embed = out["embeds"][0]
        assert embed["title"] == "Event"
        assert embed["fields"] == [{"name": "X", "value": "1", "inline": True}]

    def test_provided_event_type_title_exact(self):
        svc = WebhookService.__new__(WebhookService)
        out = svc._format_discord_payload({"data": {"x": 1}, "event_type": "alert_fired"})
        assert out["embeds"][0]["title"] == "Alert Fired"
