"""F-250 / F-251 — the webhooks page's delivery history and its Retry button.

Inventory rows: ``docs/reference/feature-inventory.md`` §3, grep anchors
``Delivery history`` (count 1) and ``Retry failed delivery`` (count 1) — literal
substrings rather than the rows' full feature names, because the section heading
separator in this repo's docstrings trips ``RUF002``.

Both rows describe a read-back of the same table, so both are driven from one
seed: a webhook aimed at an address that refuses connections, triggered through
the route a user actually clicks (``POST /api/alerts/{id}/acknowledge`` →
``trigger_webhook_background``, ``backend/api/routes/alerts.py:646``), then read
through ``GET /api/outbound-webhooks/{webhook_id}/deliveries``.

Why the seed is deterministic instead of polled-forever: the webhook is created
with ``max_retries: 0`` (``backend/api/schemas/outbound_webhook.py:158`` allows
``ge=0``), so ``_handle_delivery_failure`` takes its else-branch
(``backend/services/webhook_service.py:470``) and the row lands ``failed`` on the
first attempt with no ``next_retry_at`` to wait out. The refused loopback
address is accepted by ``create_webhook`` — there is no SSRF or private-host
guard on that path — and ``httpx`` fails it in milliseconds, so the only wait
left is for the background task to commit.

One delivery row per *acknowledgment*, not per alert: ``deliver_webhook``
unconditionally ``db.add``\\ s a new ``WebhookDelivery``
(``backend/services/webhook_service.py:359``), and ``retry_delivery`` then
updates that same row rather than inserting one (``attempt_count += 1`` at
``backend/services/webhook_service.py:644``) even though the route's own
description says it "Creates a new delivery attempt"
(``backend/api/routes/outbound_webhooks.py:281``). Each test therefore
acknowledges its own alert and gets its own delivery row: this module runs under
``-p randomly``, so a single shared row would let the retry test move
``attempt_count`` out from under the history test depending on seed order.

What is deliberately *not* asserted: the ``409`` that ``responses=``
(``backend/api/routes/outbound_webhooks.py:286``) and the handler's ``Raises:``
(``:310``) both advertise for "delivery not in a retriable state". No such guard
exists — measured through the route, retrying a delivery forced to ``success``
answered 200 and re-sent it, leaving the row ``failed`` with ``attempt_count``
bumped and ``delivered_at`` still holding the earlier success timestamp (only
the 2xx branch writes it, so nothing clears it on the way back to failed). The
row therefore claims both that it failed and that it was delivered at a time it
was not. Reaching that state needs a direct row update, which no route offers,
so the spec cannot set it up over HTTP: the finding is recorded in the row's
evidence and on #6979, not asserted here. The ``404`` branch *is* implemented
and is pinned.

Teardown deletes the webhook (``DELETE /api/outbound-webhooks/{webhook_id}``,
which the route documents as also deleting "all associated delivery history" —
the FK is ``ondelete="CASCADE"``, ``backend/models/outbound_webhook.py:271``).
That teardown is load-bearing beyond tidiness: a leftover enabled webhook aimed
at a dead address fires on every later test's alert on the shared stack, so it
lives in fixture teardown, not in a final test.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.network, pytest.mark.timeout(300)]

# Nothing listens on port 1, so the connect is refused rather than timed out —
# the delivery reaches a terminal state without eating the marker's budget.
REFUSED_URL = "http://127.0.0.1:1/golden-f250-f251-refused"

POLL_INTERVAL_S = 1.0
POLL_DEADLINE_S = 90.0

TERMINAL_STATUSES = {"failed", "success"}


def _terminal_delivery(client: httpx.Client, webhook_id: str, alert_id: str) -> dict[str, Any]:
    """Poll the history endpoint until *this* alert's delivery leaves PENDING.

    Matched on ``event_id`` rather than "the newest row": the module's webhook is
    subscribed to ``alert_acknowledged``, so any other test that acknowledges an
    alert would otherwise be able to satisfy this wait with its own row.
    """
    deadline = time.monotonic() + POLL_DEADLINE_S
    seen: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        response = client.get(
            f"/api/outbound-webhooks/{webhook_id}/deliveries", params={"limit": 50}
        )
        assert response.status_code == 200, response.text[:500]
        mine = [d for d in response.json()["deliveries"] if d.get("event_id") == alert_id]
        if mine:
            seen = mine
            if mine[0]["status"] in TERMINAL_STATUSES:
                return mine[0]
        time.sleep(POLL_INTERVAL_S)
    pytest.fail(
        f"no terminal delivery for alert {alert_id} within {POLL_DEADLINE_S:.0f}s; "
        f"rows seen for it: {seen!r} (webhook {webhook_id})"
    )


@pytest.fixture(scope="module")
def dead_webhook(logged_in_api: httpx.Client) -> dict[str, Any]:
    """One webhook subscribed to ``alert_acknowledged``, deleted at module end.

    Carries the event id the alerts are hung off: ``Alert.event_id`` is a
    non-nullable FK to ``events.id`` (``backend/models/alert.py:93``), so an
    alert needs a real event. The run's smoke step has already created one
    (``feature_check`` asserts its verdict), and if none exists this skips
    rather than failing — a stack with no events cannot exercise this row at all.
    """
    created = logged_in_api.post(
        "/api/outbound-webhooks",
        json={
            "name": f"golden-f250-f251-{uuid.uuid4().hex[:8]}",
            "url": REFUSED_URL,
            "event_types": ["alert_acknowledged"],
            # 0 retries is what makes the row terminal on the first attempt.
            "max_retries": 0,
            "retry_delay_seconds": 1,
        },
    )
    assert created.status_code == 201, created.text[:500]
    webhook_id = created.json()["id"]
    assert webhook_id, created.json()

    try:
        events = logged_in_api.get("/api/events", params={"limit": 1})
        assert events.status_code == 200, events.text[:500]
        items = events.json()["items"]
        if not items:
            pytest.skip("no events on this stack; an alert needs a real events.id")

        yield {"webhook_id": webhook_id, "event_id": items[0]["id"]}
    finally:
        deleted = logged_in_api.delete(f"/api/outbound-webhooks/{webhook_id}")
        # A leak here is not cosmetic: the webhook stays enabled and fires on
        # every later alert on the shared stack, so a wrong code is a failure.
        assert deleted.status_code == 204, (
            f"cleanup DELETE /api/outbound-webhooks/{webhook_id} answered "
            f"{deleted.status_code}: {deleted.text[:300]}"
        )


@pytest.fixture
def failed_delivery(logged_in_api: httpx.Client, dead_webhook: dict[str, Any]) -> dict[str, Any]:
    """A fresh, terminally-failed delivery row, owned by one test.

    Created the way a user creates one: file an alert through the alert-service
    CRUD route, then acknowledge it. ``POST /api/alert-service/alerts`` exists
    precisely to create alerts without alert rules ("bypasses alert rules",
    ``backend/api/routes/alert_service.py:172``), and a new alert is
    ``pending``, which is the status the acknowledge route accepts.
    """
    alert = logged_in_api.post(
        "/api/alert-service/alerts",
        json={
            "event_id": dead_webhook["event_id"],
            "severity": "high",
            # dedup_key is not unique-constrained (it is indexed,
            # backend/models/alert.py:142) but a fresh key per test keeps any
            # rule-side dedupe from collapsing two of these into one alert.
            "dedup_key": f"golden:f250f251:{uuid.uuid4().hex[:12]}",
        },
    )
    assert alert.status_code == 201, alert.text[:500]
    alert_id = alert.json()["id"]

    acked = logged_in_api.post(f"/api/alerts/{alert_id}/acknowledge")
    assert acked.status_code == 200, (
        f"acknowledge of a fresh alert answered {acked.status_code}: {acked.text[:300]}"
    )

    delivery = _terminal_delivery(logged_in_api, dead_webhook["webhook_id"], alert_id)
    delivery["_alert_id"] = alert_id
    return delivery


def test_history_lists_the_attempt_with_its_error(
    logged_in_api: httpx.Client, dead_webhook: dict[str, Any], failed_delivery: dict[str, Any]
) -> None:
    """F-250: the history endpoint shows the attempt, its status and its error.

    The row's claim is "sees each attempt with status and response", so the
    assertion is on the fields the UI's delivery-history component reads, and it
    goes through the list endpoint rather than the fixture's own poll result —
    the fixture proves the row exists, this proves the reader reports it.

    ``status_code`` stays ``None`` here on purpose: the request never got an HTTP
    response at all (connection refused), so ``error_message`` is the only
    failure surface, which is the shape ``deliver_webhook``'s
    ``httpx.RequestError`` branch writes (``webhook_service.py:409``).
    """
    listing = logged_in_api.get(
        f"/api/outbound-webhooks/{dead_webhook['webhook_id']}/deliveries",
        params={"limit": 50},
    )
    assert listing.status_code == 200, listing.text[:500]
    body = listing.json()

    mine = [d for d in body["deliveries"] if d["id"] == failed_delivery["id"]]
    assert mine, f"delivery {failed_delivery['id']} missing from its own webhook's history"
    row = mine[0]

    assert row["status"] == "failed", row
    assert row["webhook_id"] == dead_webhook["webhook_id"], row
    assert row["event_type"] == "alert_acknowledged", row
    assert row["event_id"] == failed_delivery["_alert_id"], row
    assert row["attempt_count"] == 1, f"first attempt should be counted once: {row!r}"
    assert row["error_message"], f"a failed delivery must say why: {row!r}"
    assert row["delivered_at"] is None, row
    # max_retries=0 means this is terminal, not scheduled: no future attempt is
    # queued, which is what makes Retry the only way forward for the user.
    assert row["next_retry_at"] is None, row

    assert body["total"] >= 1, body
    assert body["limit"] == 50, body
    assert body["offset"] == 0, body
    assert body["has_more"] is (body["offset"] + len(body["deliveries"]) < body["total"]), body


def test_history_of_an_unknown_webhook_is_404(logged_in_api: httpx.Client) -> None:
    """F-250's error path: an unknown webhook 404s instead of listing nothing.

    ``list_deliveries`` calls ``_get_webhook_or_404`` before querying
    (``outbound_webhooks.py:763``), so a typo'd id is a loud failure. That
    distinction matters on a security dashboard: an empty list reads as "no
    delivery problems", a 404 reads as "wrong webhook".
    """
    missing = logged_in_api.get(f"/api/outbound-webhooks/{uuid.uuid4()}/deliveries")
    assert missing.status_code == 404, f"{missing.status_code}: {missing.text[:300]}"


def test_retry_resends_the_same_row_and_counts_the_attempt(
    logged_in_api: httpx.Client, dead_webhook: dict[str, Any], failed_delivery: dict[str, Any]
) -> None:
    """F-251: Retry re-sends inline, bumps ``attempt_count``, and stays one row.

    The retry response and the history read-back are both asserted because the
    row's own evidence is that the retry "updates the ``webhook_deliveries`` row
    that the history (F-250) reads" — a 200 from the endpoint that never reached
    the table would be exactly the "reports success it did not achieve" shape the
    inventory's half-built definition targets.

    Pinning the failure too: the endpoint still aims at the refused address, so a
    correct implementation lands ``failed`` again with the error repopulated
    (``retry_delivery`` clears ``error_message`` before sending,
    ``webhook_service.py:646``, and the ``httpx.RequestError`` branch refills it).
    """
    retried = logged_in_api.post(f"/api/outbound-webhooks/deliveries/{failed_delivery['id']}/retry")
    assert retried.status_code == 200, f"{retried.status_code}: {retried.text[:400]}"
    body = retried.json()

    assert body["id"] == failed_delivery["id"], (
        "retry must update the existing delivery, not mint a new one: "
        f"{body['id']} != {failed_delivery['id']}"
    )
    assert body["attempt_count"] == 2, body
    assert body["status"] == "failed", body
    assert body["error_message"], body

    listing = logged_in_api.get(
        f"/api/outbound-webhooks/{dead_webhook['webhook_id']}/deliveries",
        params={"limit": 50},
    )
    assert listing.status_code == 200, listing.text[:500]
    rows = [
        d for d in listing.json()["deliveries"] if d["event_id"] == failed_delivery["_alert_id"]
    ]
    assert len(rows) == 1, (
        f"retry is documented as creating a new attempt but must update in place; "
        f"history now holds {len(rows)} rows for alert {failed_delivery['_alert_id']}"
    )
    assert rows[0]["id"] == failed_delivery["id"], rows[0]
    assert rows[0]["attempt_count"] == 2, rows[0]
    assert rows[0]["status"] == "failed", rows[0]


def test_retry_of_an_unknown_delivery_is_404(logged_in_api: httpx.Client) -> None:
    """F-251's one implemented error path.

    The route has exactly two outcomes in code: ``retry_delivery`` returns
    ``None`` for an unknown id and the handler 404s
    (``outbound_webhooks.py:314-318``). Its advertised ``409`` is unreachable —
    see this module's docstring — so this test pins what exists and leaves the
    gap to the inventory row rather than papering over it with an assertion that
    would pass for the wrong reason.
    """
    missing = logged_in_api.post(f"/api/outbound-webhooks/deliveries/{uuid.uuid4()}/retry")
    assert missing.status_code == 404, f"{missing.status_code}: {missing.text[:300]}"
