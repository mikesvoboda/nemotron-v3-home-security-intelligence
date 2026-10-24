"""Alert delivery worker (B4.2).

Claims pending/retrying deliveries past their next_attempt_at under a lease
(``FOR UPDATE SKIP LOCKED`` — multiple workers never claim the same row), sends
OUTSIDE any transaction under a per-channel-kind timeout, and records the
outcome: sent, or retrying with the next backoff (30 s / 2 min / 10 min / 30 min),
or failed after the ladder is exhausted. The claim itself increments
``attempts`` and moves ``next_attempt_at`` the lease out — a send whose process
dies is re-claimed when the lease ends, and each re-claim is charged to the
ladder, so even a dying sender cannot retry forever.

Browser rows: the pipeline publishes on commit and marks the rows ``broadcast``
once the publish reaches a client; the worker's browser ladder is the
republish — a browser delivery still ``pending`` 15 s after it was created is
re-broadcast (client-side notification tag dedups), one still ``pending`` after
5 minutes expires, and a republish that finds nobody listening stays ``pending``
due again after 15 s. Browser rows never consume the backoff ladder.

Wake: the pipeline calls ``worker.wake()`` after committing new deliveries;
the poll interval is the fallback.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.models.alert_delivery import DeliveryChannelKind, DeliveryStatus
from backend.services.alerting.channels.base import Channel, DeliveryTask, SendResult

if TYPE_CHECKING:
    from backend.services.worker_supervisor import WorkerSupervisor

logger = logging.getLogger(__name__)

LEASE_SECONDS = 120  # the claim lease: next_attempt_at jumps forward this much
POLL_INTERVAL_SECONDS = 15.0
# Backoff ladder by ATTEMPTS ALREADY MADE when scheduling the next try:
# after attempt 1 -> 30 s, 2 -> 2 min, 3 -> 10 min, 4 -> 30 min, 5 -> fail.
BACKOFF_SECONDS: tuple[int, ...] = (30, 120, 600, 1800)
MAX_ATTEMPTS = 5  # attempts 1..5; a 5th failure marks the delivery failed
BROWSER_REPUBLISH_AFTER = timedelta(seconds=15)
BROWSER_EXPIRE_AFTER = timedelta(minutes=5)
CHANNEL_TIMEOUT_SECONDS: Mapping[str, float] = {
    DeliveryChannelKind.EMAIL.value: 40.0,
    DeliveryChannelKind.WEBHOOK.value: 12.0,
    DeliveryChannelKind.BROWSER.value: 5.0,
    DeliveryChannelKind.WEBPUSH.value: 12.0,
}

_CLAIM_SQL = text(
    """
    UPDATE notification_deliveries
    SET next_attempt_at = :lease_until, attempts = attempts + 1,
        updated_at = timezone('utc', now())
    WHERE id IN (
        SELECT id FROM notification_deliveries
        WHERE status IN ('pending', 'retrying')
          AND (next_attempt_at IS NULL OR next_attempt_at <= :now)
          -- A browser row's first window belongs to the pipeline's publish on
          -- commit (F3): the worker only claims it once it is 15 s old (the
          -- republish ladder), and never claims one older than the expiry.
          AND (kind <> 'browser' OR created_at <= :browser_horizon)
        ORDER BY next_attempt_at
        LIMIT :batch
        FOR UPDATE SKIP LOCKED
    )
    RETURNING id, alert_id, recipient_id, channel_id, kind, status, attempts,
              idempotency_key, created_at
    """
)


def next_backoff(attempts: int) -> timedelta | None:
    """Backoff for the NEXT attempt given attempts already made.

    Returns None when the ladder is exhausted (the delivery is failed).
    attempts is 1-based count of sends already tried — the claim writes it,
    so a send that dies with its worker still consumed one.
    """
    if attempts >= MAX_ATTEMPTS:
        return None
    return timedelta(seconds=BACKOFF_SECONDS[min(attempts, len(BACKOFF_SECONDS)) - 1])


class NotificationDeliveryWorker:
    """Claims and sends pending alert deliveries."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        channels: Mapping[str, Channel],
        *,
        build_payload: Callable[..., Awaitable[DeliveryTask]] | None = None,
        known_names_loader: Callable[[], set[str] | Awaitable[set[str]]] | None = None,
        poll_interval: float = POLL_INTERVAL_SECONDS,
        batch_size: int = 20,
    ) -> None:
        self._session_factory = session_factory
        self._channels = dict(channels)
        self._build_payload = build_payload or self._default_task_builder
        self._known_names_loader = known_names_loader or set
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._wake_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._stopping = False
        # NEM-4148: the supervisor reads a heartbeat from the loop below.
        # Set by main.py at registration; None in tests (the check is skipped).
        self._supervisor: WorkerSupervisor | None = None

    # -- lifecycle ---------------------------------------------------------

    def wake(self) -> None:
        """Signal the loop to claim immediately (pipeline calls after commit)."""
        self._wake_event.set()

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopping = False
            self._task = asyncio.create_task(self._run(), name="notification-delivery-worker")

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
        # NEM-4148: heartbeat the supervisor every 20 s (the pipeline workers'
        # cadence). A cycle here is bounded by the channel timeout (<=40 s),
        # so the loop is never silent past its heartbeat_timeout (120 s).
        last_heartbeat = time.monotonic()
        HEARTBEAT_INTERVAL_S = 20.0
        while not self._stopping:
            try:
                if self._supervisor is not None:
                    if time.monotonic() - last_heartbeat >= HEARTBEAT_INTERVAL_S:
                        self._supervisor.record_heartbeat("notification-delivery-worker")
                        last_heartbeat = time.monotonic()
                await self.process_ready()
            except Exception:
                logger.exception("delivery worker cycle failed")
            try:
                await asyncio.wait_for(self._wake_event.wait(), timeout=self._poll_interval)
            except TimeoutError:
                pass
            finally:
                self._wake_event.clear()

    # -- claim + send ------------------------------------------------------

    async def process_ready(self, now: datetime | None = None) -> int:
        """One claim-send-record cycle. Returns the number of deliveries claimed."""
        now = now or datetime.now(UTC)
        claimed = await self._claim(now)
        if not claimed:
            return 0
        loaded = self._known_names_loader()
        # The loader may be sync (tests pass a set factory) or async (the
        # production loader queries per cycle) — await only when awaitable.
        known_names = await loaded if inspect.isawaitable(loaded) else loaded
        results = await asyncio.gather(
            *(self._send_one(row, known_names, now) for row in claimed),
            return_exceptions=True,
        )
        for row, outcome in zip(claimed, results, strict=True):
            if isinstance(outcome, BaseException):
                await self._record_failure(row, now, f"worker_error: {outcome!r}")
        return len(claimed)

    async def _claim(self, now: datetime) -> list[dict[str, Any]]:
        lease_until = now + timedelta(seconds=LEASE_SECONDS)
        browser_horizon = now - BROWSER_REPUBLISH_AFTER
        async with self._session_factory() as session:
            result = await session.execute(
                _CLAIM_SQL,
                {
                    "now": now,
                    "lease_until": lease_until,
                    "batch": self._batch_size,
                    "browser_horizon": browser_horizon,
                },
            )
            rows = [dict(r._mapping) for r in result]
            await session.commit()
        return rows

    async def _send_one(self, row: dict[str, Any], known_names: set[str], now: datetime) -> None:
        """Send one claimed delivery and record the outcome (no transaction held)."""
        kind = str(row["kind"])
        created_at = row.get("created_at")
        if kind == DeliveryChannelKind.BROWSER.value and created_at is not None:
            created = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
            if now - created >= BROWSER_EXPIRE_AFTER:
                # The republish ladder's end: still pending after 5 minutes.
                await self._record(row, DeliveryStatus.EXPIRED)
                return
        channel = self._channels.get(kind)
        timeout = CHANNEL_TIMEOUT_SECONDS.get(kind, 15.0)
        task = await self._build_payload(
            row["alert_id"],
            row["channel_id"],
            row["recipient_id"],
            {"idempotency_key": row["idempotency_key"], "kind": kind},
            known_names=known_names,
        )
        if channel is None:
            await self._record_failure(row, now, f"no_adapter:{kind}")
            return
        try:
            outcome = await asyncio.wait_for(channel.send(task), timeout=timeout)
        except TimeoutError:
            outcome = SendResult(success=False, error=f"channel_timeout after {timeout}s")
        except Exception as exc:
            outcome = SendResult(success=False, error=f"adapter_error: {exc!r}")
        if outcome.success:
            await self._record_success(row, kind)
        elif kind == DeliveryChannelKind.BROWSER.value:
            # A republish that found nobody listening stays ``pending`` due
            # again after 15 s — browser rows never consume the backoff
            # ladder; the 5-minute expiry above ends them.
            await self._record(
                row,
                DeliveryStatus.PENDING,
                next_attempt_in=BROWSER_REPUBLISH_AFTER,
                now=now,
            )
        else:
            await self._record_failure(row, now, outcome.error or "send_failed")

    # -- record ------------------------------------------------------------

    async def _record_success(self, row: dict[str, Any], kind: str) -> None:
        status = (
            DeliveryStatus.BROADCAST
            if kind == DeliveryChannelKind.BROWSER.value
            else DeliveryStatus.SENT
        )
        await self._record(row, status)

    async def _record_failure(
        self,
        row: dict[str, Any],
        now: datetime | None,
        error: str,
    ) -> None:
        # The claim already counted this send in ``attempts``; the failure only
        # schedules the next leg of the ladder (or fails the row).
        attempts = int(row["attempts"])
        backoff = next_backoff(attempts)
        if backoff is None:
            await self._record(
                row,
                DeliveryStatus.FAILED,
                attempts=attempts,
                error=error,
            )
        else:
            await self._record(
                row,
                DeliveryStatus.RETRYING,
                attempts=attempts,
                error=error,
                next_attempt_in=backoff,
                now=now,
            )

    async def _record(
        self,
        row: dict[str, Any],
        status: DeliveryStatus,
        *,
        attempts: int | None = None,
        error: str | None = None,
        next_attempt_in: timedelta | None = None,
        now: datetime | None = None,
    ) -> None:
        sets = ["status = :status"]
        params: dict[str, Any] = {"id": row["id"], "status": status.value}
        if attempts is not None:
            sets.append("attempts = :attempts")
            params["attempts"] = attempts
        if error is not None:
            sets.append("last_error = :last_error")
            params["last_error"] = error[:2000]
        if next_attempt_in is not None:
            # Backoff is measured from the cycle's claim clock (``now``), not DB
            # wall clock, so a fixed-clock test and a real cycle agree.
            when = now or datetime.now(UTC)
            sets.append("next_attempt_at = :next_attempt_at")
            params["next_attempt_at"] = when + next_attempt_in
        if status in (DeliveryStatus.SENT, DeliveryStatus.BROADCAST):
            sets.append("sent_at = timezone('utc', now())")
        async with self._session_factory() as session:
            await session.execute(
                # The SET-list is internal; every value is a bound param (:id, :status, ...).
                text(  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
                    "UPDATE notification_deliveries SET "  # noqa: S608
                    + ", ".join(sets)
                    + ", updated_at = timezone('utc', now()) WHERE id = :id"
                ),
                params,
            )
            await session.commit()

    async def _default_task_builder(
        self,
        alert_id: str,
        channel_id: str,
        recipient_id: str,
        extras: dict[str, Any],
        *,
        known_names: set[str] | None = None,
    ) -> DeliveryTask:
        """Task builder the production wiring replaces; tests inject theirs.

        ``known_names`` is accepted so the production builder (payload.py)
        can redact; the default builds no payload, so it only carries the
        names through to the task's redaction metadata.
        """
        return DeliveryTask(
            delivery_id=alert_id,
            channel_id=channel_id,
            channel_kind=DeliveryChannelKind(extras.get("kind", "email")),
            recipient_id=recipient_id,
            idempotency_key=extras.get("idempotency_key", ""),
            payload={},
            include_names=False,
            known_names=known_names or set(),
        )


__all__ = [
    "BACKOFF_SECONDS",
    "MAX_ATTEMPTS",
    "NotificationDeliveryWorker",
    "next_backoff",
]
