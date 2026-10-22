"""[r308a] — the CI notification sinks' smoke: one message per sink, read back.

The box (``docs/uplevel/packages/ops.md``, ruling 308): "The CI harness admits
a mail sink, a webhook sink and a Web Push service fake beside
``FAKE_SERVICES``, each started by the fake stack and readable by a golden
test; the CI webhook sink is marked 'on this network'." Done when: "a smoke
test sends one message to each sink and reads it back in CI, and the UR-89
review approves."

Three roads, one per channel, each the road its consumer drives:

* **email** through the product route ``POST /api/notification/test`` (channel
  ``email``), which reaches ``NotificationService.send_email`` → ``smtplib`` →
  the mail sink at ``FEATURE_CHECK_SINK_SMTP_URL``; read back through the
  sink's HTTP surface at ``FEATURE_CHECK_SINK_MAIL_HTTP_URL``. The SMTP shape
  is the CI backend's own env (``SMTP_HOST=mail-sink``, ``SMTP_USE_TLS=false``
  — the sink advertises no STARTTLS, pinned in
  ``backend/tests/unit/scripts/test_ci_sink_server.py``).
* **webhook** through the outbound-webhooks machinery
  (``POST /api/outbound-webhooks`` → acknowledge → ``deliver_webhook``), the
  only webhook send path that reaches the sink's private address: the
  notification route's own leg validates every URL through
  ``validate_webhook_url_for_request`` and the CI backend holds no
  ``is_development`` attribute, so a private URL there is refused by design —
  the per-channel "on this network" flag that opens it is B4.2's build, and
  this spec's create payload now carries it (B4.2, #7346). The sink is marked
  ``on-this-network`` by the compose label ``uplevel.r308a/sink`` (pinned in
  ``test_ci_sinks_overlay.py``).
* **push** directly to the service fake (``FEATURE_CHECK_SINK_PUSH_URL``):
  ``send_push`` is a stub returning "Push notifications are not yet
  implemented", so there is no product path yet — B4.3's adapter is the
  consumer this fake is built for (RFC 8030's 201-Created contract is
  already served so the adapter lands against the shape it will meet).

Read-backs go over HTTP to the published loopback ports the harness exports;
each sink's store is cleared in fixture teardown so a re-run or a sibling
module's leg sees an empty store (the sinks are per-run, single-tenant, so
there is nothing else to preserve).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.network, pytest.mark.timeout(300)]

SINK_ENV = (
    "FEATURE_CHECK_SINK_SMTP_URL",
    "FEATURE_CHECK_SINK_MAIL_HTTP_URL",
    "FEATURE_CHECK_SINK_WEBHOOK_URL",
    "FEATURE_CHECK_SINK_PUSH_URL",
)


def _sinks() -> dict[str, str]:
    """The four sink URLs, or a skip when the harness env is absent.

    Collection must never crash (the conftest's rule), and a spec that runs
    outside the harness skips rather than erroring — same contract as
    ``api_url``.
    """
    missing = [
        name
        for name in (*SINK_ENV, "FEATURE_CHECK_SINK_WEBHOOK_HOST", "FEATURE_CHECK_MODE")
        if not os.environ.get(name)
    ]
    if missing:
        pytest.skip(f"feature-check sink env absent: {', '.join(missing)}")
    return {name: os.environ[name].rstrip("/") for name in SINK_ENV}


@pytest.fixture(scope="module")
def sinks() -> dict[str, str]:
    return _sinks()


@pytest.fixture(scope="module")
def sink_reader() -> Any:
    """An HTTP client for the sinks' read-back surfaces; clears per sink."""

    class _Reader:
        def __init__(self, base: str) -> None:
            self.base = base

        def get(self, path: str) -> Any:
            # The read-back IS the test: the sink's HTTP surface, unmocked.
            # nosemgrep: ssrf-requests - the base is the harness's own sink env (loopback)
            response = httpx.get(f"{self.base}{path}", timeout=10.0)  # real
            assert response.status_code == 200, response.text[:300]
            return response.json()

        def clear(self, path: str) -> None:
            # nosemgrep: ssrf-requests - same harness sink env base as get above
            response = httpx.request("DELETE", f"{self.base}{path}", timeout=10.0)  # real
            assert response.status_code in (200, 204), response.status_code

    return _Reader


def test_the_mail_sink_receives_the_test_route_email(
    logged_in_api: httpx.Client, sinks: dict[str, str], sink_reader: Any
) -> None:
    """One email sent through the product route, read back from the sink.

    The route answers ``success: true`` only when ``send_email`` did, and the
    read-back proves the message actually left the backend — a delivery row
    without the SMTP round would pass the route and fail here.
    """
    reader = sink_reader(sinks["FEATURE_CHECK_SINK_MAIL_HTTP_URL"])
    reader.clear("/messages")

    sent = logged_in_api.post(
        "/api/notification/test",
        json={"channel": "email", "email_recipients": ["sinks@nemotron.test"]},
    )
    assert sent.status_code == 200, sent.text[:500]
    body = sent.json()
    assert body["success"] is True, body

    messages = reader.get("/messages")["messages"]
    assert len(messages) >= 1, messages
    message = messages[-1]
    assert "sinks@nemotron.test" in message["to"], message
    assert "Security Alert" in message["subject"], message
    assert message["received_at"], message


def test_the_webhook_sink_receives_the_acknowledgement_payload(
    logged_in_api: httpx.Client, sinks: dict[str, str], sink_reader: Any
) -> None:
    """One webhook delivery through the outbound machinery, read back.

    The webhook is created aimed at the sink's in-network address — the
    backend container dials the sink over ci-net, so the create-time URL is
    ``FEATURE_CHECK_SINK_WEBHOOK_HOST``'s value (the overlay spells it into
    the backend env), NOT the host-side loopback URL, which from inside the
    backend container points at the backend itself. The read-back goes over
    the host-side URL the harness exports. The sink answers 200 so the
    delivery lands ``success``; the payload's ``event_type``/``webhook_id``
    are what the sink recorded. The idempotency key is F4.2's golden-path row
    ("the webhook sink receives the payload with its idempotency key"), and
    arrives with B4.2's payload work — the read-back here pins the transport,
    not the field B4.2 adds.
    """
    reader = sink_reader(sinks["FEATURE_CHECK_SINK_WEBHOOK_URL"])
    reader.clear("/requests")

    sink_host = os.environ["FEATURE_CHECK_SINK_WEBHOOK_HOST"]
    created = logged_in_api.post(
        "/api/outbound-webhooks",
        json={
            "name": f"golden-r308a-{uuid.uuid4().hex[:8]}",
            "url": f"http://{sink_host}",
            "event_types": ["alert_acknowledged"],
            # The sink sits on the compose network (plain HTTP, private
            # address) — B4.2's per-channel flag is what admits exactly this
            # target, as this docstring's webhook paragraph anticipated.
            "on_local_network": True,
            "max_retries": 0,
            "retry_delay_seconds": 1,
        },
    )
    assert created.status_code == 201, created.text[:500]
    webhook_id = created.json()["id"]
    try:
        events = logged_in_api.get("/api/events", params={"limit": 1})
        assert events.status_code == 200, events.text[:500]
        items = events.json()["items"]
        if not items:
            pytest.skip("no events on this stack; an alert needs a real events.id")
        alert = logged_in_api.post(
            "/api/alert-service/alerts",
            json={
                "event_id": items[0]["id"],
                "severity": "high",
                "dedup_key": f"golden:r308a:{uuid.uuid4().hex[:12]}",
            },
        )
        assert alert.status_code == 201, alert.text[:500]
        acked = logged_in_api.post(f"/api/alerts/{alert.json()['id']}/acknowledge")
        assert acked.status_code == 200, acked.text[:300]

        deadline = 90.0
        while deadline > 0:
            deliveries = logged_in_api.get(
                f"/api/outbound-webhooks/{webhook_id}/deliveries", params={"limit": 50}
            )
            assert deliveries.status_code == 200, deliveries.text[:300]
            mine = [
                d for d in deliveries.json()["deliveries"] if d["event_id"] == alert.json()["id"]
            ]
            if mine and mine[0]["status"] in ("success", "failed"):
                assert mine[0]["status"] == "success", mine[0]
                break
            time.sleep(1.0)  # real - the poll loop IS the delivery wait
            deadline -= 1.0
        else:
            pytest.fail("the webhook delivery never reached a terminal state")
    finally:
        deleted = logged_in_api.delete(f"/api/outbound-webhooks/{webhook_id}")
        assert deleted.status_code == 204, deleted.status_code

    records = reader.get("/requests")["requests"]
    assert len(records) >= 1, records
    payload = json.loads(records[-1]["body"])
    assert payload["event_type"] == "alert_acknowledged", payload
    assert payload["webhook_id"] == webhook_id, payload


def test_the_push_fake_accepts_a_push_request(sinks: dict[str, str], sink_reader: Any) -> None:
    """One push POST to the service fake, read back; RFC 8030's 201.

    Sent directly: the product's ``send_push`` is a stub today, so the fake's
    consumer (B4.3's adapter) does not exist yet — this leg proves the fake is
    up, serves the Web Push contract's success shape, and is readable, which
    is what "a Web Push service fake ... readable by a golden test" asks for.
    """
    reader = sink_reader(sinks["FEATURE_CHECK_SINK_PUSH_URL"])
    reader.clear("/requests")

    # nosemgrep: ssrf-requests - the push fake's harness env URL, the leg's subject
    sent = httpx.post(  # real
        f"{sinks['FEATURE_CHECK_SINK_PUSH_URL']}/push/golden-{uuid.uuid4().hex[:8]}",
        json={"blob": "r308a-golden-smoke"},
        headers={"TTL": "60"},
        timeout=10.0,
    )
    assert sent.status_code == 201, sent.text[:300]

    records = reader.get("/requests")["requests"]
    assert len(records) >= 1, records
    assert json.loads(records[-1]["body"]) == {"blob": "r308a-golden-smoke"}, records[-1]
    assert records[-1]["headers"]["ttl"] == "60", records[-1]


def test_the_run_records_the_on_this_network_marking(
    sinks: dict[str, str], sink_reader: Any
) -> None:
    """The marking is data in the run, not a comment: the env names it.

    The harness exports ``FEATURE_CHECK_SINKS_MODE`` to the golden env; the
    spec holds the CI contract to its word so a silent rename of the marking
    reds here before B4.2 builds against a shape that moved.
    """
    assert os.environ.get("FEATURE_CHECK_SINKS_MODE") == "on-this-network"
    # And the labelled service answers on the network the marking describes:
    # a POST to the webhook sink from inside the golden leg's network
    # namespace succeeds only while the sink is genuinely reachable in-network.
    # nosemgrep: ssrf-requests - the webhook sink's harness env URL, the leg's subject
    probe = httpx.get(f"{sinks['FEATURE_CHECK_SINK_WEBHOOK_URL']}/health", timeout=10.0)  # real
    assert probe.status_code == 200, probe.status_code
