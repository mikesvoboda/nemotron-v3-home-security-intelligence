"""Scheduled resend worker for outbound webhook deliveries (B4.2, ruling 310).

On failure ``WebhookService._handle_delivery_failure`` sets
``WebhookDelivery.next_retry_at`` with exponential backoff — and until this
worker nothing read that column, so a delivery that failed once stayed failed
while the UI showed a retry time that never arrived (#7336). This worker
closes that loop: it claims RETRYING deliveries whose ``next_retry_at`` has
passed while attempts remain below the webhook's ``max_retries``, resends the
stored payload, and records the outcome — the same claim-lease-send shape the
alerting delivery worker uses for recipient channels
(``backend/services/alerting/worker.py``).

The lease IS ``next_retry_at``: claiming stamps it into the future, so a
second worker's claim query skips the row; on failure the service's backoff
overwrites it with the next scheduled slot, and on success the status moves
to SUCCESS. ``attempt_count`` is incremented at claim time, so a claim holds
its attempt even if the process dies mid-send — the next claim sees the
incremented count and stops at ``max_retries``.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.core.logging import get_logger
from backend.services.webhook_service import WebhookService

logger = get_logger(__name__)

#: How long a claim holds the row before another worker may take it. Also the
#: floor for the next ``next_retry_at`` after a failed resend within the lease.
_LEASE_SECONDS = 60

#: Rows claimed per cycle.
_BATCH_SIZE = 20

#: The claim: RETRYING rows past their retry time, with attempts still below
#: the webhook's max_retries, leased via ``next_retry_at`` under SKIP LOCKED
#: (the same shape as the alerting worker's claim). The attempt increment and
#: the lease stamp happen in the same UPDATE so a crashed claim still holds
#: its attempt (the next claim sees it and stops at max_retries).
_CLAIM_SQL = text(
    """
    UPDATE webhook_deliveries d
    SET next_retry_at = :lease_until,
        attempt_count = d.attempt_count + 1,
        status = 'pending'
    WHERE d.id IN (
        SELECT d2.id
        FROM webhook_deliveries d2
        JOIN outbound_webhooks w ON w.id = d2.webhook_id
        WHERE d2.status = 'retrying'
          AND d2.next_retry_at IS NOT NULL
          AND d2.next_retry_at <= :now
          AND d2.attempt_count < w.max_retries
          AND w.enabled
        ORDER BY d2.next_retry_at
        LIMIT :batch
        FOR UPDATE OF d2 SKIP LOCKED
    )
    RETURNING d.id, d.webhook_id, d.request_payload, d.attempt_count
    """
)


class WebhookRetryWorker:
    """Resends outbound webhook deliveries whose retry time has passed."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        service: WebhookService | None = None,
        poll_interval: float = 30.0,
        batch_size: int = _BATCH_SIZE,
    ) -> None:
        self._session_factory = session_factory
        self._service = service or WebhookService()
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._wake_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._stopping = False

    def wake(self) -> None:
        """Signal the loop to claim immediately (the service calls on failure)."""
        self._wake_event.set()

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopping = False
            self._task = asyncio.create_task(self._run(), name="webhook-retry-worker")

    async def stop(self) -> None:
        self._stopping = True
        self.wake()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        while not self._stopping:
            try:
                await self.process_due()
            except Exception:
                logger.exception("webhook retry worker cycle failed")
            try:
                await asyncio.wait_for(self._wake_event.wait(), timeout=self._poll_interval)
            except TimeoutError:
                pass
            finally:
                self._wake_event.clear()

    async def process_due(self, now: datetime | None = None) -> int:
        """One claim-resend-record cycle. Returns the number of rows claimed."""
        now = now or datetime.now(UTC)
        claimed = await self._claim(now)
        for row in claimed:
            await self._resend_one(row, now)
        return len(claimed)

    async def _claim(self, now: datetime) -> list[dict[str, Any]]:
        lease_until = now + timedelta(seconds=_LEASE_SECONDS)
        async with self._session_factory() as session:
            result = await session.execute(
                _CLAIM_SQL,
                {"now": now, "lease_until": lease_until, "batch": self._batch_size},
            )
            rows = [dict(r._mapping) for r in result]
            await session.commit()
        return rows

    async def _resend_one(self, row: dict[str, Any], now: datetime) -> None:  # noqa: ARG002
        """Resend one claimed delivery and record the outcome (no transaction held).

        ``now`` is kept in the signature for clock symmetry with ``_claim``
        (injection point when the send-time backoff moves to the worker clock).
        """
        payload = row["request_payload"] or {}
        # The service's send path applies the F12 URL policy (validate, resolve,
        # pin) and records SUCCESS/FAILED on the delivery row itself; pass the
        # already-incremented attempt count back via the delivery row the
        # service re-loads inside _send_and_record.
        await self._service.resend_delivery_payload(
            self._session_factory, str(row["webhook_id"]), str(row["id"]), payload
        )
