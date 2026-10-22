"""Unit tests for upgrade 0012-alert-pipeline-core and the B4.1 alert schema additions."""

from __future__ import annotations

from sqlalchemy import inspect

from backend.migrations.checks import CHECKS
from backend.migrations.registry import UPGRADES
from backend.models.alert import (
    ActivitySnooze,
    Alert,
    AlertEvent,
    AlertRule,
    AlertStatusEnum,
)


def test_upgrade_0012_is_registered_and_checked() -> None:
    upgrade_ids = [u.id for u in UPGRADES]
    assert "0012-alert-pipeline-core" in upgrade_ids
    assert "0012-alert-pipeline-core" in CHECKS

    upgrade = next(u for u in UPGRADES if u.id == "0012-alert-pipeline-core")
    assert upgrade.path.is_file()
    sql = upgrade.read_sql()
    assert "verdict_source" in sql
    assert "match_count" in sql
    assert "last_seen_at" in sql
    assert "last_event_id" in sql
    assert "alert_events" in sql
    assert "activity_snoozes" in sql
    assert "alert_on_rejected" in sql
    assert "excluded_camera_ids" in sql


def test_alert_model_has_new_columns_and_open_status() -> None:
    assert AlertStatusEnum.OPEN == "open"
    cols = set(inspect(Alert).columns.keys())
    assert {"verdict_source", "match_count", "last_seen_at", "last_event_id"} <= cols

    rule_cols = set(inspect(AlertRule).columns.keys())
    assert {"alert_on_rejected", "excluded_camera_ids"} <= rule_cols

    ae_cols = set(inspect(AlertEvent).columns.keys())
    assert {"alert_id", "event_id"} <= ae_cols

    snooze_cols = set(inspect(ActivitySnooze).columns.keys())
    assert {"camera_id", "object_type", "until"} <= snooze_cols
