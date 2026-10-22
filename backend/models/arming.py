"""SQLAlchemy models for the Arming core tables (B4.7 / docs/uplevel/4n-arming.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.time_utils import utc_now

from .camera import Base

#: Fixed UUID for the seeded, editable "External alerts" rule (4n-arming.md §What changes).
EXTERNAL_ALERTS_RULE_ID = "00000000-0000-4000-8000-00000000e470"
EXTERNAL_ALERTS_RULE_NAME = "External alerts"

VALID_ARMING_MODES: tuple[str, ...] = ("home", "away", "night", "disarmed")


class ArmingState(Base):
    """Single-row table storing the household's current arming mode and schedule update time."""

    __tablename__ = "arming_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="home")
    set_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="system")
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    schedule_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ArmingModeExclusion(Base):
    """Cameras excluded from a given arming mode (`ON DELETE CASCADE` on camera)."""

    __tablename__ = "arming_mode_exclusions"

    mode: Mapped[str] = mapped_column(String(32), primary_key=True)
    camera_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        primary_key=True,
    )

    __table_args__ = (Index("idx_arming_mode_exclusions_mode", "mode"),)


class ArmingScheduleEntry(Base):
    """Weekly schedule entry switching the household arming mode in local time."""

    __tablename__ = "arming_schedule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    days: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    time: Mapped[str] = mapped_column(String(16), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ArmingChange(Base):
    """Append-only change log for arming mode transitions and per-mode camera exclusions.

    Each row carries `mode_after` and `exclusions_after` (every mode's exclusions
    after the change) so `mode_at(t)` and `is_armed(camera_id, at)` can evaluate
    an event by the arming state at its `started_at`. Pruned after 365 days while
    keeping the newest row before the cutoff.
    """

    __tablename__ = "arming_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    from_value: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    to_value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    mode_after: Mapped[str] = mapped_column(String(32), nullable=False, default="home")
    exclusions_after: Mapped[dict[str, list[str]]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (Index("idx_arming_changes_changed_at", "changed_at"),)
