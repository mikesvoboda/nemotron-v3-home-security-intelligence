"""Batch-15 battery: webhook_service TEST-GAP clusters from the WP4.4 dossier
(``archive/wp25-feed/wp44-triage/webhook_service.md``).

Clusters killed here (mutmut-adjacent behaviour pinned per cluster):
C1 bted-values (87), C5 fmt-discord (30), C6 fmt-teams (29), C7 fmt-slack (18),
C12 int-routing (6), C13 boundary300 (6), C15 or-default (6), C19 singleton (2),
C20 bted-fallback (2), C21 timing-formula (2), C22 tw-body (3), C23 hdrs-names (3).

Deliberately NOT touched (owned by other batches): C2/C3 query-build SQL,
C4 delivery-record construction, C8 stats counters, C9 signature recomputation,
C10 resp-fields, C11 create-fields, C14 health-boundary, C16 jinja-context,
C17 db-args, C18 post-args.

EVERY asserted literal below was MEASURED against the pristine shipped source on
2026-09-23 by throwaway probes (``/tmp/b15-probe-*.py`` run with
``uv run python`` under the repo venv, consolidated dump in
``/tmp/b15-probes.json``). No value was guessed and production was NOT bent to
any mutant: where shipped behaviour differs from the dossier draft, the shipped
behaviour is what is pinned. Measured corrections / additions to the dossier:

* Dossier D1 claims ``_build_test_event_data`` returns a ``data``-less shape and
  that ``timestamp`` ordering is meaningful; the shipped shape is
  ``{**base, **specific}`` where ``base == {"test": True, "timestamp": <iso>}``
  (probe1/probe6): the full dict is pinned with a patched clock.
* ``WebhookDeliveryStatus`` is ``auto()`` so its values are the *lowercase*
  member names (``"success"``, ``"retrying"``, ``"failed"``) — probe4.
* C13 boundary: 299 -> SUCCESS in all three classifiers; 300 is FAILURE with a
  *different* failure shape per entry point — ``deliver_webhook`` -> status
  ``retrying`` + ``next_retry_at`` set + ``delivered_at`` None, ``test_webhook``
  -> ``success=False, error_message="HTTP 300", response_body="b300"`` (body is
  still returned on failure), ``retry_delivery`` -> status ``failed`` +
  ``delivered_at`` None + ``next_retry_at`` None (probe4).
* C19: the shipped reset pattern is the module-level holder global
  ``webhook_service._WebhookServiceHolder.instance`` (there is NO
  ``reset_webhook_service()`` helper); it is saved/restored in ``finally`` so no
  module state leaks to other tests (probe6).
* C21: both ``/1000`` and ``*1001`` are killed by pinning the exact int returned
  from ``_send_request`` with the service module's ``datetime`` patched to a
  2-tick clock (37 ms -> 37; ``/1000`` would yield 0, ``*1001`` 37037);
  ``int()`` also truncates sub-millisecond elapsed to 0 (probe7).
* C23: the shipped base headers are exactly ``{"Content-Type":
  "application/json", "User-Agent": "NemotronWebhook/1.0"}`` and the
  ``post()`` kwargs are exactly ``("json", "headers")`` with the url positional;
  header VALUES (not just the key set) are pinned because the shipped
  ``_send_request`` merges custom headers over the base — a value tweak
  survives a keys-only assert (probe3/probe7).
* Unmeasured-by-us but recorded because it is shipped contract: the three
  formatters raise ``AttributeError`` when ``data`` is present-but-``None``
  (``payload.get("data", {})`` only defaults a *missing* key) — probe2.

Provable-EQUIVALENT members found inside the targeted clusters (kill-work in
this file cannot reach them; ledger candidates): dropping ``| bool`` from the
formatters' ``isinstance(value, str | int | float | bool)`` (bool is a subclass
of int, so the union is unchanged — verified on the mutated module) and the
Discord-only ``payload.get("event_type", "event")`` default case flip (that
default reaches ``.title()`` only, so ``"EVENT"`` renders identically).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

import backend.services.webhook_service as W
from backend.api.schemas.outbound_webhook import WebhookEventType
from backend.models.outbound_webhook import (
    IntegrationType,
    OutboundWebhook,
    WebhookDelivery,
    WebhookDeliveryStatus,
)
from backend.services.webhook_service import DEFAULT_TIMEOUT, WebhookService

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Measured constants (probes 6/7). FIXED/FIXED_ISO come from patching the
# service module's utc_now, so every iso timestamp in this file is the same
# measured value.
# ---------------------------------------------------------------------------
WID = "wid-fixed-1"
URL = "https://x.test/hook"
FIXED = datetime(2026, 3, 4, 5, 6, 7, 891011, tzinfo=UTC)
FIXED_ISO = "2026-03-04T05:06:07.891011+00:00"
SECRET = "ab" * 32
SECRET_A = "a" * 64
# probe7: HMAC over json.dumps(payload, sort_keys=True, separators=(",",":"))
SIG_P1 = "4012d12033f6bfe41db94b44a97ac0b5434779648ccd370c53ff31d117a6aa4f"
SIG_P3 = "31f13e5e1b6da4560d8cca7ec6a477f41b1eb3724711410670f3685c699aec72"
BASE_HEADERS = {"Content-Type": "application/json", "User-Agent": "NemotronWebhook/1.0"}

# Payloads whose signatures above were measured with SECRET (probe6/probe7).
P1 = {"zz": 1, "aa": {"y": 2, "b": 3}}
P3 = {"b": [1, 2], "a": "x"}

# A wide data mapping mixing scalar and non-scalar values; the non-scalars must
# be dropped by all three formatters (measured, probe2).
WIDE_DATA = {
    "zone_id": "driveway",
    "score": 0.5,
    "count": 3,
    "flag": False,
    "nested": {"x": 1},
    "items": [1, 2],
    "none": None,
}


# ---------------------------------------------------------------------------
# Local fixtures (self-contained; mock_db_session comes from backend/tests)
# ---------------------------------------------------------------------------
@pytest.fixture
def service() -> WebhookService:
    return WebhookService()


@pytest.fixture
def clock():
    """Patch the service module's utc_now to the measured FIXED instant."""
    with patch.object(W, "utc_now", return_value=FIXED, autospec=True):
        yield FIXED


def webhook(integration: IntegrationType = IntegrationType.GENERIC, **overrides) -> OutboundWebhook:
    """Build an unpersisted OutboundWebhook with the probe's baseline config."""
    kwargs = {
        "id": WID,
        "name": "Batch15",
        "url": URL,
        "event_types": ["alert_fired"],
        "integration_type": integration,
        "enabled": True,
        "auth_config": None,
        "custom_headers": {},
        "payload_template": None,
        "max_retries": 4,
        "retry_delay_seconds": 10,
        "signing_secret": None,
        "total_deliveries": 0,
        "successful_deliveries": 0,
    }
    kwargs.update(overrides)
    return OutboundWebhook(**kwargs)


class ClientSpy:
    """Stand-in for ``httpx.AsyncClient`` that records the ``post()`` call.

    Instances are callable and return themselves from ``__call__`` so the
    ``async with httpx.AsyncClient(timeout=...) as client`` form works, and no
    real socket is ever opened.
    """

    def __init__(self, status_code: int = 202, text: str = "queued") -> None:
        self.status_code = status_code
        self.text = text
        self.calls: list[tuple[tuple, dict]] = []
        self.constructor_kwargs: list[dict] = []

    def __call__(self, **kwargs) -> ClientSpy:
        self.constructor_kwargs.append(kwargs)
        return self

    async def __aenter__(self) -> ClientSpy:
        return self

    async def __aexit__(self, *exc_info) -> None:
        return None

    async def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        response = MagicMock()
        response.status_code = self.status_code
        response.text = self.text
        return response


def _session_with(execute: AsyncMock) -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = execute
    return session


def _result(scalar=None, rows=None, one_or_none=None) -> MagicMock:
    result = MagicMock()
    result.scalar.return_value = scalar
    scalars = MagicMock()
    scalars.all.return_value = rows if rows is not None else []
    result.scalars.return_value = scalars
    result.scalar_one_or_none.return_value = one_or_none
    return result


def _patched_clock(steps: list[datetime]) -> type:
    """A ``datetime`` look-alike whose ``now()`` walks ``steps`` once."""

    class TickClock:
        _steps = steps
        _tick = 0

        @classmethod
        def now(cls, _tz=None):
            value = cls._steps[min(cls._tick, len(cls._steps) - 1)]
            cls._tick += 1
            return value

    return TickClock


# ===========================================================================
# C1 bted-values (87) — full-shape equality of the sample-event table
# ===========================================================================
def test_build_test_event_data_full_shape_per_event_type(service, clock):
    """Kills every key/value text mutation (XX…XX, UPPER/lower flips, 1.95/1.87)
    in the event-specific test-data table: the whole merged dict is pinned."""
    measured = {
        WebhookEventType.ALERT_FIRED: {
            "test": True,
            "timestamp": FIXED_ISO,
            "alert_id": "test-alert-001",
            "severity": "high",
            "camera_id": "front_door",
            "description": "Test alert triggered",
        },
        WebhookEventType.ALERT_DISMISSED: {
            "test": True,
            "timestamp": FIXED_ISO,
            "alert_id": "test-alert-001",
        },
        WebhookEventType.ALERT_ACKNOWLEDGED: {
            "test": True,
            "timestamp": FIXED_ISO,
            "alert_id": "test-alert-001",
        },
        WebhookEventType.EVENT_CREATED: {
            "test": True,
            "timestamp": FIXED_ISO,
            "event_id": "test-event-001",
            "camera_id": "front_door",
            "event_type": "motion_detected",
        },
        WebhookEventType.EVENT_ENRICHED: {
            "test": True,
            "timestamp": FIXED_ISO,
            "event_id": "test-event-001",
            "enrichment_type": "person_detection",
            "confidence": 0.95,
        },
        WebhookEventType.ENTITY_DISCOVERED: {
            "test": True,
            "timestamp": FIXED_ISO,
            "entity_id": "test-entity-001",
            "entity_type": "person",
            "label": "Unknown Person",
        },
        WebhookEventType.ANOMALY_DETECTED: {
            "test": True,
            "timestamp": FIXED_ISO,
            "anomaly_id": "test-anomaly-001",
            "zone_id": "driveway",
            "anomaly_type": "unusual_activity",
            "score": 0.87,
        },
        WebhookEventType.SYSTEM_HEALTH_CHANGED: {
            "test": True,
            "timestamp": FIXED_ISO,
            "component": "ai-yolo26",
            "status": "degraded",
            "message": "High latency detected",
        },
    }
    for event_type, expected in measured.items():
        assert service._build_test_event_data(event_type) == expected
        # insertion order is part of the shipped shape: base first, then specific
        assert list(service._build_test_event_data(event_type)) == list(expected)

    # float literals are floats, not strings / rounded ints (kills 0.95->"0.95")
    assert service._build_test_event_data(WebhookEventType.EVENT_ENRICHED)["confidence"] == 0.95
    assert (
        type(service._build_test_event_data(WebhookEventType.EVENT_ENRICHED)["confidence"]) is float
    )
    assert service._build_test_event_data(WebhookEventType.ANOMALY_DETECTED)["score"] == 0.87
    assert type(service._build_test_event_data(WebhookEventType.ANOMALY_DETECTED)["score"]) is float


def test_build_test_event_data_timestamp_is_utc_iso_and_advances(service):
    """Timestamp shape without the clock patch: 32-char ``+00:00`` isoformat."""
    data = service._build_test_event_data(WebhookEventType.ALERT_FIRED)
    stamp = data["timestamp"]
    assert isinstance(stamp, str)
    assert stamp.endswith("+00:00")
    assert len(stamp) == 32
    assert datetime.fromisoformat(stamp).tzinfo == UTC
    later = service._build_test_event_data(WebhookEventType.ALERT_FIRED)["timestamp"]
    assert later >= stamp


# ===========================================================================
# C20 bted-fallback (2) — unmapped event types merge {} (no None, no raise)
# ===========================================================================
def test_build_test_event_data_unmapped_event_type_merges_empty_dict(service, clock):
    """Kills ``.get(value, {})`` -> ``.get(value)`` / dropped default: an enum
    member absent from the table must merge an empty dict, never None."""
    unmapped = [
        WebhookEventType.BATCH_ANALYSIS_STARTED,
        WebhookEventType.BATCH_ANALYSIS_COMPLETED,
        WebhookEventType.BATCH_ANALYSIS_FAILED,
    ]
    for event_type in unmapped:
        data = service._build_test_event_data(event_type)
        assert data == {"test": True, "timestamp": FIXED_ISO}
        assert data["test"] is True

    # shipped: the lookup keys are the lowercase StrEnum values
    assert service._build_test_event_data(WebhookEventType.ALERT_FIRED) != {
        "test": True,
        "timestamp": FIXED_ISO,
    }


# ===========================================================================
# C7 fmt-slack (18) — full shape, key case, inline flags, text assembly
# ===========================================================================
def test_format_slack_payload_full_shape(service):
    payload = {"event_type": "camera_motion_detected", "data": WIDE_DATA}
    text = (
        "*camera_motion_detected*\n- zone_id: driveway\n- score: 0.5\n- count: 3\n- flag: False\n"
    )
    assert service._format_slack_payload(payload) == {
        "text": text,
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
    }


def test_format_slack_payload_defaults_and_non_scalar_filter(service):
    assert service._format_slack_payload({}) == {
        "text": "*event*\n",
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "*event*\n"}}],
    }
    assert service._format_slack_payload({"event_type": "e"}) == {
        "text": "*e*\n",
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "*e*\n"}}],
    }
    # keys are used verbatim (no title-casing) and non-scalars are skipped
    odd = {
        "event_type": "a_B_c",
        "data": {"HTTP_code_x2": "v", "UPPER_CASE": 1, "mix ed": 2, "": 3},
    }
    text = "*a_B_c*\n- HTTP_code_x2: v\n- UPPER_CASE: 1\n- mix ed: 2\n- : 3\n"
    assert service._format_slack_payload(odd) == {
        "text": text,
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
    }


# ===========================================================================
# C5 fmt-discord (30) — embed shape, inline flag, title-casing, [:25] cap
# ===========================================================================
def test_format_discord_payload_full_shape(service):
    payload = {"event_type": "camera_motion_detected", "timestamp": "TS-STAMP", "data": WIDE_DATA}
    assert service._format_discord_payload(payload) == {
        "embeds": [
            {
                "title": "Camera Motion Detected",
                "timestamp": "TS-STAMP",
                "fields": [
                    {"name": "Zone Id", "value": "driveway", "inline": True},
                    {"name": "Score", "value": "0.5", "inline": True},
                    {"name": "Count", "value": "3", "inline": True},
                    {"name": "Flag", "value": "False", "inline": True},
                ],
            }
        ]
    }


def test_format_discord_payload_timestamp_lookup_and_defaults(service):
    # missing timestamp falls back to the module clock (utc_now is module-global)
    with patch.object(W, "utc_now", return_value=FIXED, autospec=True):
        assert service._format_discord_payload({"event_type": "e", "data": {}}) == {
            "embeds": [{"title": "E", "timestamp": FIXED_ISO, "fields": []}]
        }
        assert service._format_discord_payload({}) == {
            "embeds": [{"title": "Event", "timestamp": FIXED_ISO, "fields": []}]
        }
    # explicit timestamp wins
    assert service._format_discord_payload({"timestamp": "T2", "data": {"alert_id": "a-1"}}) == {
        "embeds": [
            {
                "title": "Event",
                "timestamp": "T2",
                "fields": [{"name": "Alert Id", "value": "a-1", "inline": True}],
            }
        ]
    }


def test_format_discord_fields_cap_at_25(service):
    """Boundary pin: 26 inputs -> 25 fields (kills ``fields[:25]`` -> ``[:26]``)."""
    data = {f"k{i}": i for i in range(26)}
    fields = service._format_discord_payload({"data": data})["embeds"][0]["fields"]
    assert len(fields) == 25
    assert fields[0] == {"name": "K0", "value": "0", "inline": True}
    assert fields[-1] == {"name": "K24", "value": "24", "inline": True}
    assert [f["name"] for f in fields][-3:] == ["K22", "K23", "K24"]
    # 25 inputs is the largest uncapped case; 24 stays 24
    assert (
        len(
            service._format_discord_payload({"data": {f"k{i}": i for i in range(25)}})["embeds"][0][
                "fields"
            ]
        )
        == 25
    )
    assert (
        len(
            service._format_discord_payload({"data": {f"k{i}": i for i in range(24)}})["embeds"][0][
                "fields"
            ]
        )
        == 24
    )
    empty = service._format_discord_payload({"data": {}})["embeds"][0]
    assert empty["title"] == "Event" and empty["fields"] == []


# ===========================================================================
# C6 fmt-teams (29) — MessageCard shape, themeColor, summary, [:10] cap
# ===========================================================================
def test_format_teams_payload_full_shape(service):
    payload = {"event_type": "camera_motion_detected", "timestamp": "TS-STAMP", "data": WIDE_DATA}
    assert service._format_teams_payload(payload) == {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": "camera_motion_detected",
        "themeColor": "0076D7",
        "title": "Camera Motion Detected",
        "sections": [
            {
                "facts": [
                    {"title": "Zone Id", "value": "driveway"},
                    {"title": "Score", "value": "0.5"},
                    {"title": "Count", "value": "3"},
                    {"title": "Flag", "value": "False"},
                ]
            }
        ],
    }
    # fact dicts carry exactly two keys — no inline flag (unlike Discord)
    assert list(service._format_teams_payload(payload)["sections"][0]["facts"][0]) == [
        "title",
        "value",
    ]
    # top-level key order is part of the shipped shape
    assert list(service._format_teams_payload(payload)) == [
        "@type",
        "@context",
        "summary",
        "themeColor",
        "title",
        "sections",
    ]


def test_format_teams_summary_is_raw_event_type_and_defaults(service):
    """``summary`` keeps the raw value while ``title`` is title-cased."""
    assert service._format_teams_payload({}) == {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": "event",
        "themeColor": "0076D7",
        "title": "Event",
        "sections": [{"facts": []}],
    }
    slim = service._format_teams_payload(
        {"event_type": "a_B_c", "data": {"HTTP_code_x2": "v", "": 3}}
    )
    assert slim["summary"] == "a_B_c"
    assert slim["title"] == "A B C"
    assert slim["sections"][0]["facts"] == [
        {"title": "Http Code X2", "value": "v"},
        {"title": "", "value": "3"},
    ]


def test_format_teams_facts_cap_at_10(service):
    """Boundary pin: 11 inputs -> 10 facts (kills ``facts[:10]`` -> ``[:11]``)."""
    facts = service._format_teams_payload({"data": {f"k{i}": i for i in range(11)}})["sections"][0][
        "facts"
    ]
    assert len(facts) == 10
    assert facts[0] == {"title": "K0", "value": "0"}
    assert facts[-1] == {"title": "K9", "value": "9"}
    assert (
        len(
            service._format_teams_payload({"data": {f"k{i}": i for i in range(10)}})["sections"][0][
                "facts"
            ]
        )
        == 10
    )
    assert (
        len(
            service._format_teams_payload({"data": {f"k{i}": i for i in range(9)}})["sections"][0][
                "facts"
            ]
        )
        == 9
    )
    assert service._format_teams_payload({"data": {}})["sections"] == [{"facts": []}]


# ===========================================================================
# C12 int-routing (6) — _format_for_integration comparison targets
# ===========================================================================
def test_format_for_integration_routes_each_type_with_full_shape(service, clock):
    """Kills ``"slack"/"discord"/"teams"`` comparison-target renames: each route
    must produce its formatted shape; anything else is verbatim passthrough."""
    standard = {
        "event_type": "camera_motion",
        "timestamp": "TS",
        "data": {"zone_id": "driveway", "score": 0.5},
    }

    slack = service._format_for_integration(webhook(IntegrationType.SLACK), {**standard})
    text = "*camera_motion*\n- zone_id: driveway\n- score: 0.5\n"
    assert slack == {
        "text": text,
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
    }

    discord = service._format_for_integration(webhook(IntegrationType.DISCORD), {**standard})
    assert discord == {
        "embeds": [
            {
                "title": "Camera Motion",
                "timestamp": "TS",
                "fields": [
                    {"name": "Zone Id", "value": "driveway", "inline": True},
                    {"name": "Score", "value": "0.5", "inline": True},
                ],
            }
        ]
    }

    teams = service._format_for_integration(webhook(IntegrationType.TEAMS), {**standard})
    assert teams == {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": "camera_motion",
        "themeColor": "0076D7",
        "title": "Camera Motion",
        "sections": [
            {
                "facts": [
                    {"title": "Zone Id", "value": "driveway"},
                    {"title": "Score", "value": "0.5"},
                ]
            }
        ],
    }

    generic = webhook(IntegrationType.GENERIC)
    assert service._format_for_integration(generic, standard) == standard
    assert service._format_for_integration(generic, standard) is standard
    # TELEGRAM is not a formatting branch -> passthrough
    assert service._format_for_integration(webhook(IntegrationType.TELEGRAM), standard) == standard
    # a bare (non-enum) integration_type string still routes when it matches
    plain = webhook(IntegrationType.GENERIC)
    plain.integration_type = "discord"
    assert service._format_for_integration(plain, {**standard}) == discord
    # ...and does NOT route when case differs (shipped behaviour, not lenient)
    plain.integration_type = "SLACK"
    assert service._format_for_integration(plain, standard) == standard


def test_build_payload_routes_through_integration(service, clock):
    """_build_payload (no template) ends in the integration formatter."""
    event_data = {"alert_id": "a1"}
    assert service._build_payload(webhook(), WebhookEventType.ALERT_FIRED, event_data) == {
        "event_type": "alert_fired",
        "timestamp": FIXED_ISO,
        "webhook_id": WID,
        "data": event_data,
    }
    text = "*alert_fired*\n- a: 1\n"
    assert service._build_payload(
        webhook(IntegrationType.SLACK), WebhookEventType.ALERT_FIRED, {"a": 1}
    ) == {
        "text": text,
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
    }
    assert service._build_payload(
        webhook(IntegrationType.TEAMS), WebhookEventType.ALERT_FIRED, {"a": 1}
    ) == {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": "alert_fired",
        "themeColor": "0076D7",
        "title": "Alert Fired",
        "sections": [{"facts": [{"title": "A", "value": "1"}]}],
    }


# ===========================================================================
# C13 boundary300 (6) — 200 <= status < 300 in deliver / test / retry
# ===========================================================================
@pytest.mark.parametrize(
    ("status_code", "expected_status"),
    [
        (199, WebhookDeliveryStatus.RETRYING),
        (200, WebhookDeliveryStatus.SUCCESS),
        (204, WebhookDeliveryStatus.SUCCESS),
        (299, WebhookDeliveryStatus.SUCCESS),
        (300, WebhookDeliveryStatus.RETRYING),
        (301, WebhookDeliveryStatus.RETRYING),
        (500, WebhookDeliveryStatus.RETRYING),
    ],
)
async def test_deliver_webhook_status_classification_at_300_boundary(
    service, mock_db_session, status_code, expected_status
):
    """Kills ``< 300`` -> ``<= 300`` / ``< 301``: 299 succeeds, 300 does not."""
    mock_db_session.execute = AsyncMock(return_value=_result())
    hook = webhook(max_retries=4, retry_delay_seconds=10)

    with patch.object(service, "_send_request", new_callable=AsyncMock) as send:
        send.return_value = (status_code, f"body-{status_code}", 42)
        delivery = await service.deliver_webhook(
            mock_db_session,
            hook,
            WebhookEventType.ALERT_FIRED,
            {"alert_id": "a1"},
            event_id="evt-9",
        )

    assert delivery.status is expected_status
    assert delivery.status_code == status_code
    assert delivery.response_body == f"body-{status_code}"
    assert delivery.response_time_ms == 42
    if expected_status is WebhookDeliveryStatus.SUCCESS:
        assert delivery.error_message is None
        assert delivery.delivered_at is not None
        assert hook.last_delivery_status == "success"
    else:
        assert delivery.error_message == f"HTTP {status_code}"
        assert delivery.delivered_at is None
        assert delivery.next_retry_at is not None
        assert hook.last_delivery_status == "retrying"


@pytest.mark.parametrize("status_code", [300, 301, 404])
async def test_deliver_webhook_300_is_failure_with_measured_field_proof(
    service, mock_db_session, status_code
):
    """The delivery-record fields that *prove* 300 is not a success."""
    mock_db_session.execute = AsyncMock(return_value=_result())
    hook = webhook()
    with patch.object(service, "_send_request", new_callable=AsyncMock) as send:
        send.return_value = (status_code, "b", 5)
        delivery = await service.deliver_webhook(
            mock_db_session, hook, WebhookEventType.ALERT_FIRED, {}
        )

    assert delivery.status is WebhookDeliveryStatus.RETRYING
    assert delivery.status == "retrying"  # auto()-based StrEnum value is lowercase
    assert delivery.error_message == f"HTTP {status_code}"
    assert delivery.delivered_at is None
    assert hook.total_deliveries == 1
    assert hook.successful_deliveries == 0


@pytest.mark.parametrize(
    ("status_code", "body", "expected"),
    [
        (
            299,
            "b299",
            {
                "success": True,
                "status_code": 299,
                "response_time_ms": 7,
                "response_body": "b299",
                "error_message": None,
            },
        ),
        (
            300,
            "b300",
            {
                "success": False,
                "status_code": 300,
                "response_time_ms": 7,
                "response_body": "b300",
                "error_message": "HTTP 300",
            },
        ),
        (
            301,
            "b301",
            {
                "success": False,
                "status_code": 301,
                "response_time_ms": 7,
                "response_body": "b301",
                "error_message": "HTTP 301",
            },
        ),
    ],
)
async def test_test_webhook_success_boundary_at_300(
    service, mock_db_session, status_code, body, expected
):
    """test_webhook classification: 299 success / 300 failure, full response."""
    hook = webhook()
    mock_db_session.execute = AsyncMock(return_value=_result(one_or_none=hook))
    with patch.object(service, "_send_request", new_callable=AsyncMock) as send:
        send.return_value = (status_code, body, 7)
        result = await service.test_webhook(mock_db_session, hook.id, WebhookEventType.ALERT_FIRED)
    assert result.model_dump() == expected


async def test_retry_delivery_300_is_failed_299_is_success(service, mock_db_session):
    """retry_delivery uses the same window but the FAILED branch (not RETRYING)."""
    hook = webhook()
    delivery = WebhookDelivery(
        webhook_id=hook.id,
        event_type="alert_fired",
        status=WebhookDeliveryStatus.FAILED,
        attempt_count=1,
        request_payload={"a": 1},
    )
    mock_db_session.execute = AsyncMock(
        side_effect=[_result(one_or_none=delivery), _result(one_or_none=hook)]
    )
    with patch.object(service, "_send_request", new_callable=AsyncMock) as send:
        send.return_value = (299, "r299", 11)
        retried = await service.retry_delivery(mock_db_session, "delivery-1")

    assert retried.status is WebhookDeliveryStatus.SUCCESS
    assert retried.status_code == 299
    assert retried.response_body == "r299"
    assert retried.response_time_ms == 11
    assert retried.error_message is None
    assert retried.attempt_count == 2
    assert hook.last_delivery_status == "success"

    hook2 = webhook()
    delivery2 = WebhookDelivery(
        webhook_id=hook2.id,
        event_type="alert_fired",
        status=WebhookDeliveryStatus.FAILED,
        attempt_count=1,
        request_payload={"a": 1},
    )
    mock_db_session.execute = AsyncMock(
        side_effect=[_result(one_or_none=delivery2), _result(one_or_none=hook2)]
    )
    with patch.object(service, "_send_request", new_callable=AsyncMock) as send:
        send.return_value = (300, "r300", 11)
        failed = await service.retry_delivery(mock_db_session, "delivery-1")

    assert failed.status is WebhookDeliveryStatus.FAILED
    assert failed.status_code == 300
    assert failed.error_message == "HTTP 300"
    assert failed.response_body == "r300"
    assert failed.attempt_count == 2
    assert hook2.total_deliveries == 1
    assert hook2.successful_deliveries == 0
    assert hook2.last_delivery_status == "failed"


# ===========================================================================
# C22 tw-body (3) — test_webhook response_body passthrough / None / cap
# ===========================================================================
@pytest.mark.parametrize(
    ("status_code", "body", "expected_body"),
    [
        (200, "pong", "pong"),
        (200, "", None),
        (404, "", None),
        (404, "nope", "nope"),
    ],
)
async def test_test_webhook_response_body_passthrough(
    service, mock_db_session, status_code, body, expected_body
):
    hook = webhook()
    mock_db_session.execute = AsyncMock(return_value=_result(one_or_none=hook))
    with patch.object(service, "_send_request", new_callable=AsyncMock) as send:
        send.return_value = (status_code, body, 7)
        result = await service.test_webhook(mock_db_session, hook.id, WebhookEventType.ALERT_FIRED)
    assert result.response_body == expected_body
    assert result.model_dump()["response_body"] == expected_body


async def test_test_webhook_response_body_capped_at_2000(service, mock_db_session):
    hook = webhook()
    mock_db_session.execute = AsyncMock(return_value=_result(one_or_none=hook))
    with patch.object(service, "_send_request", new_callable=AsyncMock) as send:
        send.return_value = (200, "x" * 2001, 7)
        result = await service.test_webhook(mock_db_session, hook.id, WebhookEventType.ALERT_FIRED)
    assert len(result.response_body) == 2000
    assert result.response_body == "x" * 2000
    assert result.success is True and result.error_message is None


async def test_test_webhook_full_success_shape(service, mock_db_session):
    hook = webhook()
    mock_db_session.execute = AsyncMock(return_value=_result(one_or_none=hook))
    with patch.object(service, "_send_request", new_callable=AsyncMock) as send:
        send.return_value = (200, "pong", 7)
        result = await service.test_webhook(mock_db_session, hook.id, WebhookEventType.ALERT_FIRED)
    assert result.model_dump() == {
        "success": True,
        "status_code": 200,
        "response_time_ms": 7,
        "response_body": "pong",
        "error_message": None,
    }


# ===========================================================================
# C23 hdrs-names (3) + C21 timing-formula (2) — _send_request wire contract
# ===========================================================================
async def test_send_request_posts_exact_url_json_and_base_headers(service):
    """Header dict is pinned by keys AND values: the shipped base headers are
    exactly Content-Type/User-Agent and post() gets (url, json=, headers=)."""
    spy = ClientSpy(status_code=202, text="queued")
    with patch.object(httpx, "AsyncClient", spy):
        result = await service._send_request(webhook(), P1)

    assert spy.constructor_kwargs == [{"timeout": DEFAULT_TIMEOUT}]
    assert spy.calls == [((URL,), {"json": P1, "headers": BASE_HEADERS})]
    assert result == (202, "queued", 0)


async def test_send_request_signed_headers_exact_dict(service):
    """Kills header key renames for the signature pair (values are the measured
    HMAC over the canonical json.dumps form)."""
    spy = ClientSpy(status_code=200, text="OK")
    with patch.object(httpx, "AsyncClient", spy):
        await service._send_request(webhook(signing_secret=SECRET), P1)

    _, kwargs = spy.calls[0]
    assert kwargs["headers"] == {
        "Content-Type": "application/json",
        "User-Agent": "NemotronWebhook/1.0",
        "X-Webhook-Signature": f"sha256={SIG_P1}",
        "X-Webhook-Signature-256": SIG_P1,
    }
    assert list(kwargs["headers"]) == [
        "Content-Type",
        "User-Agent",
        "X-Webhook-Signature",
        "X-Webhook-Signature-256",
    ]
    # the measured literal equals an in-test recomputation of the shipped
    # canonicalization (sort_keys + tight separators)
    canonical = json.dumps(P1, sort_keys=True, separators=(",", ":")).encode()
    assert hmac.new(bytes.fromhex(SECRET), canonical, hashlib.sha256).hexdigest() == SIG_P1


async def test_send_request_auth_and_custom_header_dicts_are_exact(service):
    bearer = webhook(
        custom_headers={"X-Trace": "t1"},
        auth_config={"type": "bearer", "token": "TK1"},
        signing_secret=SECRET,
    )
    spy = ClientSpy()
    with patch.object(httpx, "AsyncClient", spy):
        await service._send_request(bearer, P3)
    _, kwargs = spy.calls[0]
    assert kwargs["headers"] == {
        "Content-Type": "application/json",
        "User-Agent": "NemotronWebhook/1.0",
        "X-Trace": "t1",
        "Authorization": "Bearer TK1",
        "X-Webhook-Signature": f"sha256={SIG_P3}",
        "X-Webhook-Signature-256": SIG_P3,
    }
    assert list(kwargs["headers"]) == [
        "Content-Type",
        "User-Agent",
        "X-Trace",
        "Authorization",
        "X-Webhook-Signature",
        "X-Webhook-Signature-256",
    ]

    basic = webhook(auth_config={"type": "basic", "username": "cam", "password": "pw"})
    spy = ClientSpy()
    with patch.object(httpx, "AsyncClient", spy):
        await service._send_request(basic, P1)
    assert spy.calls[0][1]["headers"] == {
        "Authorization": "Basic Y2FtOnB3",
        **BASE_HEADERS,
    }

    header_auth = webhook(
        auth_config={"type": "header", "header_name": "X-Api-Key", "header_value": "VV"}
    )
    spy = ClientSpy()
    with patch.object(httpx, "AsyncClient", spy):
        await service._send_request(header_auth, P1)
    assert spy.calls[0][1]["headers"] == {"X-Api-Key": "VV", **BASE_HEADERS}

    # unknown auth type and empty auth_config add nothing
    for auth_config in ({"type": "weird"}, {}):
        spy = ClientSpy()
        with patch.object(httpx, "AsyncClient", spy):
            await service._send_request(webhook(auth_config=auth_config), P1)
        assert spy.calls[0][1]["headers"] == BASE_HEADERS

    # custom headers are merged OVER the base (later update wins)
    override = webhook(
        custom_headers={"Content-Type": "text/plain", "User-Agent": "mine", "X-Extra": "e"}
    )
    spy = ClientSpy()
    with patch.object(httpx, "AsyncClient", spy):
        await service._send_request(override, P3)
    assert spy.calls[0][1]["headers"] == {
        "Content-Type": "text/plain",
        "User-Agent": "mine",
        "X-Extra": "e",
    }


@pytest.mark.parametrize(
    ("elapsed_ms", "expected_ms"),
    [(0, 0), (1, 1), (37, 37), (2500, 2500), (100000, 100000)],
)
async def test_send_request_response_time_ms_formula_is_times_1000(
    service, elapsed_ms, expected_ms
):
    """Kills ``* 1000`` -> ``/ 1000`` (37 -> 0) and ``* 1001`` (37 -> 37037) with
    a two-tick clock injected into the service module's ``datetime``."""
    steps = [
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(milliseconds=elapsed_ms),
    ]
    spy = ClientSpy(status_code=200, text="pong")
    with (
        patch.object(httpx, "AsyncClient", spy),
        patch.object(W, "datetime", _patched_clock(steps)),
    ):
        status, text, response_time_ms = await service._send_request(webhook(), P1)
    assert (status, text) == (200, "pong")
    assert response_time_ms == expected_ms
    assert type(response_time_ms) is int


async def test_send_request_sub_millisecond_elapsed_truncates_to_zero(service):
    """``int()`` truncation is measurable: 999us -> 0, 1999us -> 1."""
    steps = [datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, 0, 0, 0, 999, tzinfo=UTC)]
    spy = ClientSpy()
    with (
        patch.object(httpx, "AsyncClient", spy),
        patch.object(W, "datetime", _patched_clock(steps)),
    ):
        assert (await service._send_request(webhook(), P1))[2] == 0
    steps = [datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, 0, 0, 0, 1999, tzinfo=UTC)]
    spy = ClientSpy()
    with (
        patch.object(httpx, "AsyncClient", spy),
        patch.object(W, "datetime", _patched_clock(steps)),
    ):
        assert (await service._send_request(webhook(), P1))[2] == 1


# ===========================================================================
# C15 or-default (6) — ``scalar() or 0`` fallbacks
# ===========================================================================
async def test_health_summary_zero_and_none_scalars_fall_back_to_zero(service, mock_db_session):
    """Kills ``or 0`` -> ``or 1`` on all five count scalars: None and 0 both
    produce 0, and average_response_time_ms is None for None *and* 0.0."""
    for values in ([None] * 6, [0, 0, 0, 0, 0, 0]):
        mock_db_session.execute = AsyncMock(side_effect=[_result(scalar=v) for v in values])
        with patch.object(service, "list_webhooks", new_callable=AsyncMock) as lister:
            lister.return_value = []
            summary = await service.get_health_summary(mock_db_session)
        assert summary.model_dump() == {
            "total_webhooks": 0,
            "enabled_webhooks": 0,
            "healthy_webhooks": 0,
            "unhealthy_webhooks": 0,
            "total_deliveries_24h": 0,
            "successful_deliveries_24h": 0,
            "failed_deliveries_24h": 0,
            "average_response_time_ms": None,
        }
        assert mock_db_session.execute.call_count == 6
        assert lister.call_args.args[0] is mock_db_session

    mock_db_session.execute = AsyncMock(
        side_effect=[_result(scalar=v) for v in [0, 0, 0, 0, 0, 0.0]]
    )
    with patch.object(service, "list_webhooks", new_callable=AsyncMock) as lister:
        lister.return_value = []
        summary = await service.get_health_summary(mock_db_session)
    assert summary.average_response_time_ms is None


async def test_health_summary_nonzero_scalars_pass_through(service, mock_db_session):
    """Same helper proves the fallback is not ``or 1`` in the other direction:
    real scalars flow through untouched (avg None -> None)."""
    mock_db_session.execute = AsyncMock(
        side_effect=[_result(scalar=v) for v in [7, 5, 20, 15, 3, None]]
    )
    with patch.object(service, "list_webhooks", new_callable=AsyncMock) as lister:
        lister.return_value = []
        summary = await service.get_health_summary(mock_db_session)
    assert summary.model_dump() == {
        "total_webhooks": 7,
        "enabled_webhooks": 5,
        "healthy_webhooks": 0,
        "unhealthy_webhooks": 0,
        "total_deliveries_24h": 20,
        "successful_deliveries_24h": 15,
        "failed_deliveries_24h": 3,
        "average_response_time_ms": None,
    }

    mock_db_session.execute = AsyncMock(
        side_effect=[_result(scalar=v) for v in [7, 5, 20, 15, 3, 12.5]]
    )
    with patch.object(service, "list_webhooks", new_callable=AsyncMock) as lister:
        lister.return_value = []
        summary = await service.get_health_summary(mock_db_session)
    assert summary.average_response_time_ms == 12.5


@pytest.mark.parametrize(("scalar", "expected"), [(None, 0), (0, 0), (5, 5)])
async def test_get_deliveries_total_falls_back_to_zero(service, mock_db_session, scalar, expected):
    """Kills ``count_result.scalar() or 0`` -> ``or 1`` in get_deliveries."""
    mock_db_session.execute = AsyncMock(side_effect=[_result(scalar=scalar), _result(rows=[])])
    deliveries, total = await service.get_deliveries(mock_db_session, "wid-1", limit=50, offset=0)
    assert total == expected
    assert type(total) is int
    assert deliveries == []
    assert mock_db_session.execute.call_count == 2


# ===========================================================================
# C19 singleton (2) — get_webhook_service holder contract
# ===========================================================================
def test_get_webhook_service_singleton_roundtrip():
    """Kills ``is None`` -> ``is not None`` and ``instance = None``: the holder
    global must be populated with a real, stable WebhookService.

    Shipped reset pattern is the module-level holder attribute (there is no
    reset helper); the original value is restored in ``finally`` so no other
    test can observe a mutated singleton.
    """
    original = W._WebhookServiceHolder.instance
    try:
        W._WebhookServiceHolder.instance = None
        first = W.get_webhook_service()
        assert isinstance(first, WebhookService)
        assert first is not None
        assert W.get_webhook_service() is first
        assert W._WebhookServiceHolder.instance is first

        W._WebhookServiceHolder.instance = None
        assert W._WebhookServiceHolder.instance is None
        second = W.get_webhook_service()
        assert isinstance(second, WebhookService)
        assert second is not first
        assert W._WebhookServiceHolder.instance is second
    finally:
        W._WebhookServiceHolder.instance = original
    assert W._WebhookServiceHolder.instance is original


def test_get_webhook_service_reuses_preexisting_holder_instance():
    """The ``is None`` guard must NOT rebuild when an instance already exists."""
    original = W._WebhookServiceHolder.instance
    sentinel = WebhookService()
    try:
        W._WebhookServiceHolder.instance = sentinel
        assert W.get_webhook_service() is sentinel
        assert W.get_webhook_service() is sentinel
    finally:
        W._WebhookServiceHolder.instance = original


# ===========================================================================
# Shipped-contract extras measured while probing these clusters (not dossier
# drafts): formatter None-data crash and the webhook baseline used above.
# ===========================================================================
def test_formatters_crash_on_present_but_none_data(service):
    """.get("data", {}) only defaults a MISSING key — shipped behaviour raises."""
    for formatter in (
        service._format_slack_payload,
        service._format_discord_payload,
        service._format_teams_payload,
    ):
        with pytest.raises(AttributeError):
            formatter({"event_type": "e", "data": None})


def test_webhook_baseline_helper_matches_probe_construction():
    hook = webhook(IntegrationType.DISCORD, signing_secret=SECRET_A, total_deliveries=7)
    assert (hook.id, hook.url, hook.name) == (WID, URL, "Batch15")
    assert hook.integration_type is IntegrationType.DISCORD
    assert hook.total_deliveries == 7
    assert hook.max_retries == 4 and hook.retry_delay_seconds == 10
    assert str(uuid4()) != hook.id
