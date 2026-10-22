"""Arming core service and scheduler (B4.7 / docs/uplevel/4n-arming.md).

Provides:
- `mode_at(session, t)` and `is_armed(session, camera_id, at=t)` over the `arming_changes` log
- `resolve_arming_at(session, camera_id, at=t)` returning `(mode, armed)` with fail-armed fallback
- `set_mode(session, mode, *, source_kind, source_name, now)` serialised by a row lock on `arming_state`
- `get_mode_exclusions` / `set_mode_exclusions` recording every mode's exclusions in `arming_changes`
- `get_schedule` / `set_schedule` / `apply_schedule` / `next_scheduled` with DST skip/fold handling
- `ensure_external_alerts_rule` seeding the editable "External alerts" rule with its fixed UUID
- `ArmingScheduler`: in-process background job that sleeps until the next scheduled occurrence or a
  schedule-save wake event
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_session
from backend.core.logging import get_logger
from backend.models.alert import AlertRule, AlertSeverityEnum
from backend.models.arming import (
    EXTERNAL_ALERTS_RULE_ID,
    EXTERNAL_ALERTS_RULE_NAME,
    VALID_ARMING_MODES,
    ArmingChange,
    ArmingModeExclusion,
    ArmingScheduleEntry,
    ArmingState,
)
from backend.models.camera import Camera
from backend.models.property import Property

logger = get_logger(__name__)

DAY_NAMES: tuple[str, ...] = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
CONFIGURABLE_EXCLUSION_MODES: tuple[str, ...] = ("home", "away", "night")
CHANGE_HISTORY_RETENTION_DAYS = 365


def _ensure_utc(ts: datetime | None, fallback: datetime | None = None) -> datetime:
    if ts is None:
        base = fallback if fallback is not None else datetime.now(UTC)
        return base.replace(tzinfo=UTC) if base.tzinfo is None else base.astimezone(UTC)
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def key_fingerprint(secret: str) -> str:
    """Return a short non-reversible SHA-256 fingerprint of an API key or command token."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


async def _ensure_state_locked(session: AsyncSession) -> ArmingState:
    """Ensure `arming_state` row `id=1` exists and lock it (`FOR UPDATE` on Postgres)."""
    await session.execute(
        pg_insert(ArmingState)
        .values(
            id=1,
            mode="home",
            set_at=datetime(1970, 1, 1, tzinfo=UTC),
            source_kind="system",
            source_name="system",
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    stmt = select(ArmingState).where(ArmingState.id == 1).with_for_update()
    row = (await session.execute(stmt)).scalars().first()
    assert row is not None
    return row


async def _load_all_exclusions(session: AsyncSession) -> dict[str, list[str]]:
    """Return `{mode: sorted(excluded_camera_ids)}` for home, away, and night."""
    rows = (await session.execute(select(ArmingModeExclusion))).scalars().all()
    by_mode: dict[str, list[str]] = {m: [] for m in CONFIGURABLE_EXCLUSION_MODES}
    for r in rows:
        if r.mode in by_mode:
            by_mode[r.mode].append(r.camera_id)
    return {m: sorted(set(vals)) for m, vals in by_mode.items()}


async def _prune_old_changes(session: AsyncSession, *, now: datetime) -> None:
    """Prune `arming_changes` older than 365 days, keeping the newest row before the cutoff."""
    cutoff = _ensure_utc(now) - timedelta(days=CHANGE_HISTORY_RETENTION_DAYS)
    older_ids = list(
        (
            await session.execute(
                select(ArmingChange.id)
                .where(ArmingChange.changed_at < cutoff)
                .order_by(ArmingChange.changed_at.desc(), ArmingChange.id.desc())
            )
        )
        .scalars()
        .all()
    )
    if len(older_ids) > 1:
        to_delete = older_ids[1:]
        await session.execute(delete(ArmingChange).where(ArmingChange.id.in_(to_delete)))


async def resolve_arming_at(
    session: AsyncSession,
    camera_id: str,
    at: datetime,
) -> tuple[str, bool]:
    """Return `(mode, is_armed)` at timestamp `at`, failing armed `('home', True)` on error."""
    target = _ensure_utc(at)
    try:
        latest_before = (
            (
                await session.execute(
                    select(ArmingChange)
                    .where(ArmingChange.changed_at <= target)
                    .order_by(ArmingChange.changed_at.desc(), ArmingChange.id.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        if latest_before is not None:
            mode = latest_before.mode_after
            excluded = (latest_before.exclusions_after or {}).get(mode, [])
            return mode, (mode != "disarmed" and camera_id not in excluded)

        # No change at or before `target`: check if any later change exists
        earliest_change = (
            (
                await session.execute(
                    select(ArmingChange)
                    .order_by(ArmingChange.changed_at.asc(), ArmingChange.id.asc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        if earliest_change is not None:
            # Before the first recorded change, the installation was in its initial state
            prior_mode = (
                str(earliest_change.from_value)
                if earliest_change.kind == "mode"
                else earliest_change.mode_after
            )
            if (
                earliest_change.kind == "cameras"
                and isinstance(earliest_change.from_value, dict)
                and earliest_change.from_value.get("mode") == prior_mode
            ):
                prior_excl = earliest_change.from_value.get("excluded_camera_ids") or []
            else:
                prior_excl = (earliest_change.exclusions_after or {}).get(prior_mode, [])
            return prior_mode, (prior_mode != "disarmed" and camera_id not in prior_excl)

        # No change rows at all: read arming_state and arming_mode_exclusions
        state = (
            (await session.execute(select(ArmingState).where(ArmingState.id == 1)))
            .scalars()
            .first()
        )
        mode = state.mode if state is not None else "home"
        if mode == "disarmed":
            return mode, False
        excl_row = (
            (
                await session.execute(
                    select(ArmingModeExclusion).where(
                        ArmingModeExclusion.mode == mode,
                        ArmingModeExclusion.camera_id == camera_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        return mode, (excl_row is None)
    except Exception as exc:
        logger.warning(f"Failed to read arming state, failing armed: {exc}")
        return "home", True


async def mode_at(session: AsyncSession, t: datetime) -> str:
    """Return the active household arming mode at timestamp `t`."""
    mode, _ = await resolve_arming_at(session, "", t)
    return mode


async def is_armed(session: AsyncSession, camera_id: str, at: datetime) -> bool:
    """Return whether `camera_id` is armed at timestamp `at` (fails armed on read error)."""
    _, armed = await resolve_arming_at(session, camera_id, at)
    return armed


async def set_mode(
    session: AsyncSession,
    mode: str,
    *,
    source_kind: str = "user",
    source_name: str = "user",
    now: datetime | None = None,
) -> ArmingChange:
    """Switch the household arming mode under the `arming_state` row lock and log the change."""
    normalized = str(mode).strip().lower()
    if normalized not in VALID_ARMING_MODES:
        raise ValueError(
            f"Invalid arming mode {mode!r}; must be one of {', '.join(VALID_ARMING_MODES)}"
        )

    ts = _ensure_utc(now)
    state = await _ensure_state_locked(session)
    from_mode = state.mode
    state.mode = normalized
    state.set_at = ts
    state.source_kind = source_kind
    state.source_name = source_name

    exclusions_map = await _load_all_exclusions(session)
    change = ArmingChange(
        kind="mode",
        from_value=from_mode,
        to_value=normalized,
        mode_after=normalized,
        exclusions_after=exclusions_map,
        source_kind=source_kind,
        source_name=source_name,
        changed_at=ts,
    )
    session.add(change)
    await session.flush()
    await _prune_old_changes(session, now=ts)
    return change


async def get_mode_exclusions(session: AsyncSession, mode: str) -> list[str]:
    """Return the sorted list of excluded `camera_id`s for `mode`."""
    normalized = str(mode).strip().lower()
    if normalized not in VALID_ARMING_MODES:
        raise ValueError(
            f"Invalid arming mode {mode!r}; must be one of {', '.join(VALID_ARMING_MODES)}"
        )
    if normalized == "disarmed":
        all_cams = (
            (await session.execute(select(Camera.id).order_by(Camera.id.asc()))).scalars().all()
        )
        return list(all_cams)
    rows = (
        (
            await session.execute(
                select(ArmingModeExclusion.camera_id)
                .where(ArmingModeExclusion.mode == normalized)
                .order_by(ArmingModeExclusion.camera_id.asc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def set_mode_exclusions(
    session: AsyncSession,
    mode: str,
    excluded_camera_ids: Sequence[str],
    *,
    source_kind: str = "user",
    source_name: str = "user",
    now: datetime | None = None,
) -> ArmingChange:
    """Replace the excluded cameras for `mode` (`home`, `away`, or `night`) and log the change."""
    normalized = str(mode).strip().lower()
    if normalized not in CONFIGURABLE_EXCLUSION_MODES:
        raise ValueError(
            f"Camera exclusions can only be configured for {', '.join(CONFIGURABLE_EXCLUSION_MODES)}"
        )

    cleaned = sorted({str(cid).strip() for cid in excluded_camera_ids if str(cid).strip()})
    if cleaned:
        existing_cams = set(
            (await session.execute(select(Camera.id).where(Camera.id.in_(cleaned)))).scalars().all()
        )
        missing = sorted(set(cleaned) - existing_cams)
        if missing:
            raise ValueError(f"Unknown camera_id(s): {', '.join(missing)}")

    ts = _ensure_utc(now)
    state = await _ensure_state_locked(session)
    before_map = await _load_all_exclusions(session)
    prev_list = list(before_map.get(normalized, []))

    await session.execute(delete(ArmingModeExclusion).where(ArmingModeExclusion.mode == normalized))
    for cid in cleaned:
        session.add(ArmingModeExclusion(mode=normalized, camera_id=cid))
    await session.flush()

    after_map = dict(before_map)
    after_map[normalized] = cleaned
    change = ArmingChange(
        kind="cameras",
        from_value={"mode": normalized, "excluded_camera_ids": prev_list},
        to_value={"mode": normalized, "excluded_camera_ids": cleaned},
        mode_after=state.mode,
        exclusions_after=after_map,
        source_kind=source_kind,
        source_name=source_name,
        changed_at=ts,
    )
    session.add(change)
    await session.flush()
    await _prune_old_changes(session, now=ts)
    return change


def _parse_hhmm(time_str: str) -> tuple[int, int]:
    parts = str(time_str).strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid schedule time {time_str!r}; expected HH:MM")
    hour = int(parts[0])
    minute = int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Out-of-range schedule time {time_str!r}; expected 00:00..23:59")
    return hour, minute


def _occurrence_on_local_date(
    local_date: date,
    hour: int,
    minute: int,
    tz: ZoneInfo,
) -> datetime:
    """Compute the single UTC instant for `(local_date, hour, minute)` in `tz` (4n-arming.md A3).

    - Normal time: exact wall-clock instant.
    - Repeated time (DST fall-back): first occurrence (`fold=0`).
    - Skipped time (DST spring-forward gap): moves forward to the first valid instant after the gap.
    """
    naive_target = datetime(local_date.year, local_date.month, local_date.day, hour, minute, 0)
    dt0 = naive_target.replace(tzinfo=tz, fold=0)
    utc0 = dt0.astimezone(UTC)
    roundtrip = utc0.astimezone(tz).replace(tzinfo=None)
    if roundtrip == naive_target:
        return utc0

    # Skipped wall-clock time (spring-forward gap): binary-search for the earliest UTC second `u`
    # whose local wall time in `tz` is `>= naive_target`.
    dt1 = naive_target.replace(tzinfo=tz, fold=1)
    lo = min(utc0, dt1.astimezone(UTC)) - timedelta(hours=3)
    hi = max(utc0, dt1.astimezone(UTC)) + timedelta(hours=3)
    lo_ts = int(lo.timestamp())
    hi_ts = int(hi.timestamp())
    while lo_ts < hi_ts:
        mid_ts = (lo_ts + hi_ts) // 2
        mid_utc = datetime.fromtimestamp(mid_ts, tz=UTC)
        if mid_utc.astimezone(tz).replace(tzinfo=None) >= naive_target:
            hi_ts = mid_ts
        else:
            lo_ts = mid_ts + 1
    return datetime.fromtimestamp(lo_ts, tz=UTC)


async def _resolve_household_tz(session: AsyncSession, override_tz: str | None = None) -> ZoneInfo:
    if override_tz:
        try:
            return ZoneInfo(override_tz)
        except Exception:
            return ZoneInfo("UTC")
    try:
        prop = (
            (await session.execute(select(Property).order_by(Property.id.asc()).limit(1)))
            .scalars()
            .first()
        )
        if prop and prop.timezone:
            return ZoneInfo(str(prop.timezone))
    except Exception:
        return ZoneInfo("UTC")
    return ZoneInfo("UTC")


async def get_schedule(session: AsyncSession) -> list[ArmingScheduleEntry]:
    """Return all configured weekly arming schedule entries ordered by id."""
    rows = (
        (await session.execute(select(ArmingScheduleEntry).order_by(ArmingScheduleEntry.id.asc())))
        .scalars()
        .all()
    )
    return list(rows)


async def set_schedule(
    session: AsyncSession,
    entries: Sequence[Mapping[str, Any]],
    *,
    now: datetime | None = None,
) -> list[ArmingScheduleEntry]:
    """Replace the weekly arming schedule, stamp `schedule_updated_at`, and wake the scheduler."""
    validated: list[tuple[list[str], str, str]] = []
    for item in entries:
        raw_days = item.get("days") or []
        days = [str(d).strip().lower() for d in raw_days if str(d).strip()]
        if not days or any(d not in DAY_NAMES for d in days):
            raise ValueError(f"Invalid schedule days {raw_days!r}; expected weekday names")
        hour, minute = _parse_hhmm(str(item.get("time", "")))
        formatted_time = f"{hour:02d}:{minute:02d}"
        mode = str(item.get("mode", "")).strip().lower()
        if mode not in VALID_ARMING_MODES:
            raise ValueError(
                f"Invalid schedule mode {mode!r}; must be one of {', '.join(VALID_ARMING_MODES)}"
            )
        validated.append((days, formatted_time, mode))

    ts = _ensure_utc(now)
    state = await _ensure_state_locked(session)
    state.schedule_updated_at = ts

    await session.execute(delete(ArmingScheduleEntry))
    created: list[ArmingScheduleEntry] = []
    for days, formatted_time, mode in validated:
        row = ArmingScheduleEntry(days=days, time=formatted_time, mode=mode, created_at=ts)
        session.add(row)
        created.append(row)
    await session.flush()

    get_arming_scheduler().wake()
    return created


async def apply_schedule(
    session: AsyncSession,
    now: datetime | None = None,
    *,
    household_tz: str | None = None,
) -> ArmingChange | None:
    """Apply the latest due schedule occurrence at or before `now` under the `arming_state` lock.

    Changes the mode only when the latest occurrence at or before `now` is strictly later than
    both `arming_state.set_at` and `arming_state.schedule_updated_at` (4n-arming.md A3).
    """
    ts = _ensure_utc(now)
    state = await _ensure_state_locked(session)
    entries = await get_schedule(session)
    if not entries:
        return None

    tz = await _resolve_household_tz(session, household_tz)
    local_now = ts.astimezone(tz)
    today = local_now.date()

    latest_occ: tuple[datetime, int, str] | None = None
    for day_offset in range(-8, 2):
        cand_date = today + timedelta(days=day_offset)
        weekday_name = DAY_NAMES[cand_date.weekday()]
        for idx, entry in enumerate(entries):
            entry_days = {str(d).lower() for d in (entry.days or [])}
            if weekday_name not in entry_days:
                continue
            hour, minute = _parse_hhmm(entry.time)
            occ_utc = _occurrence_on_local_date(cand_date, hour, minute, tz)
            if occ_utc <= ts:
                cand_key = (occ_utc, idx, entry.mode)
                if latest_occ is None or (cand_key[0], cand_key[1]) > (
                    latest_occ[0],
                    latest_occ[1],
                ):
                    latest_occ = cand_key

    if latest_occ is None:
        return None

    occ_utc, _, target_mode = latest_occ
    set_at_utc = _ensure_utc(state.set_at, datetime(1970, 1, 1, tzinfo=UTC))
    sched_upd_utc = (
        _ensure_utc(state.schedule_updated_at) if state.schedule_updated_at is not None else None
    )

    if occ_utc <= set_at_utc:
        return None
    if sched_upd_utc is not None and occ_utc <= sched_upd_utc:
        return None

    return await set_mode(
        session,
        target_mode,
        source_kind="schedule",
        source_name="schedule",
        now=ts,
    )


async def next_scheduled(
    session: AsyncSession,
    now: datetime | None = None,
    *,
    household_tz: str | None = None,
) -> tuple[datetime, str] | None:
    """Return `(occurrence_utc, mode)` for the earliest schedule occurrence strictly after `now`."""
    ts = _ensure_utc(now)
    entries = await get_schedule(session)
    if not entries:
        return None

    tz = await _resolve_household_tz(session, household_tz)
    local_now = ts.astimezone(tz)
    today = local_now.date()

    earliest: tuple[datetime, int, str] | None = None
    for day_offset in range(-1, 9):
        cand_date = today + timedelta(days=day_offset)
        weekday_name = DAY_NAMES[cand_date.weekday()]
        for idx, entry in enumerate(entries):
            entry_days = {str(d).lower() for d in (entry.days or [])}
            if weekday_name not in entry_days:
                continue
            hour, minute = _parse_hhmm(entry.time)
            occ_utc = _occurrence_on_local_date(cand_date, hour, minute, tz)
            if occ_utc > ts:
                cand_key = (occ_utc, idx, entry.mode)
                if earliest is None or (cand_key[0], cand_key[1]) < (earliest[0], earliest[1]):
                    earliest = cand_key

    if earliest is None:
        return None
    return (earliest[0], earliest[2])


async def get_arming_status(
    session: AsyncSession,
    now: datetime | None = None,
    *,
    household_tz: str | None = None,
) -> dict[str, Any]:
    """Return the household's current arming status and next scheduled transition."""
    ts = _ensure_utc(now)
    state = await _ensure_state_locked(session)
    nxt = await next_scheduled(session, now=ts, household_tz=household_tz)
    return {
        "mode": state.mode,
        "since": _ensure_utc(state.set_at, ts),
        "source_kind": state.source_kind,
        "source_name": state.source_name,
        "by_whom": f"{state.source_kind}:{state.source_name}"
        if state.source_kind != "user"
        else state.source_name,
        "next_scheduled": ({"at": nxt[0], "mode": nxt[1]} if nxt is not None else None),
    }


async def list_changes(
    session: AsyncSession,
    *,
    limit: int = 100,
) -> list[ArmingChange]:
    """Return recent arming changes ordered by `changed_at DESC, id DESC`."""
    rows = (
        (
            await session.execute(
                select(ArmingChange)
                .order_by(ArmingChange.changed_at.desc(), ArmingChange.id.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def ensure_external_alerts_rule(session: AsyncSession) -> AlertRule:
    """Ensure the seeded 'External alerts' rule with fixed UUID exists in `alert_rules`."""
    existing = (
        (await session.execute(select(AlertRule).where(AlertRule.id == EXTERNAL_ALERTS_RULE_ID)))
        .scalars()
        .first()
    )
    if existing is not None:
        return existing

    rule = AlertRule(
        id=EXTERNAL_ALERTS_RULE_ID,
        name=EXTERNAL_ALERTS_RULE_NAME,
        description="Seeded rule for external webhook alerts (B4.7)",
        enabled=True,
        severity=AlertSeverityEnum.LOW,
        dedup_key_template="{camera_id}:{object_type}:{rule_id}",
        cooldown_seconds=300,
        channels=[],
        alert_on_rejected=False,
        sources=["external"],
    )
    session.add(rule)
    await session.flush()
    return rule


class ArmingScheduler:
    """In-process background job that sleeps until the next scheduled occurrence or a save wake."""

    def __init__(self, session_factory: Callable[[], Any] | None = None) -> None:
        self._session_factory = session_factory or get_session
        self._wake_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def wake(self) -> None:
        """Wake the sleeping scheduler loop when the schedule is saved or updated."""
        self._wake_event.set()

    async def run_once(self, now: datetime | None = None) -> ArmingChange | None:
        """Run `apply_schedule` once inside a session and commit."""
        async with self._session_factory() as session:
            change = await apply_schedule(session, now=now)
            await session.commit()
            return change

    async def start(self) -> None:
        """Apply any due schedule entry on boot and start the background loop."""
        if self._running:
            return
        self._running = True
        with contextlib.suppress(Exception):
            await self.run_once()
        self._task = asyncio.create_task(self._loop(), name="arming-scheduler")

    async def stop(self) -> None:
        """Stop the background scheduler loop."""
        self._running = False
        self._wake_event.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            try:
                self._wake_event.clear()
                sleep_seconds = 60.0
                async with self._session_factory() as session:
                    await apply_schedule(session)
                    await session.commit()
                    nxt = await next_scheduled(session)
                    if nxt is not None:
                        delta = (nxt[0] - datetime.now(UTC)).total_seconds()
                        sleep_seconds = max(0.5, min(delta, 3600.0))

                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._wake_event.wait(), timeout=sleep_seconds)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f"ArmingScheduler loop error: {exc}")
                await asyncio.sleep(5.0)


_SCHEDULER = ArmingScheduler()


def get_arming_scheduler() -> ArmingScheduler:
    """Return the process-wide ArmingScheduler singleton."""
    return _SCHEDULER
