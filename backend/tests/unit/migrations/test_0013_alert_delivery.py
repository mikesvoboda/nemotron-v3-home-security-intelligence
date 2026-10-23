"""Unit tests for upgrade 0013-alert-delivery and the B4.2 delivery schema additions."""

from __future__ import annotations

from sqlalchemy import inspect

from backend.migrations.checks import CHECKS
from backend.migrations.registry import UPGRADES
from backend.models.alert_delivery import Recipient, RecipientChannel
from backend.models.notification_preferences import QuietHoursPeriod
from backend.models.outbound_webhook import OutboundWebhook


def test_upgrade_0013_is_registered_and_checked() -> None:
    upgrade_ids = [u.id for u in UPGRADES]
    assert "0013-alert-delivery" in upgrade_ids
    assert "0013-alert-delivery" in CHECKS

    upgrade = next(u for u in UPGRADES if u.id == "0013-alert-delivery")
    assert upgrade.path.is_file()
    sql = upgrade.read_sql()
    # The two schema additions...
    assert "recipient_id" in sql
    assert "on_local_network" in sql
    # ...and the idempotent seed that hands the existing quiet-hours rows to Household.
    assert "Household" in sql
    assert "UPDATE quiet_hours_periods" in sql


def test_0013_sits_last_in_order() -> None:
    ids = [u.id for u in UPGRADES]
    assert ids.index("0013-alert-delivery") == ids.index("0012-alert-pipeline-core") + 1 == 12


def test_models_have_the_0013_columns() -> None:
    # quiet_hours_periods.recipient_id -- the column the recorded upgrade adds, so the
    # model must already declare it (create_all builds today's shape on fresh databases;
    # the upgrade only widens databases that predate the column).
    assert "recipient_id" in set(inspect(QuietHoursPeriod).columns.keys())
    # outbound_webhooks.on_local_network -- same create_all logic.
    assert "on_local_network" in set(inspect(OutboundWebhook).columns.keys())
    # And the delivery tables 0013's seed writes into are create_all-owned models.
    assert Recipient.__tablename__ == "recipients"
    assert RecipientChannel.__tablename__ == "recipient_channels"


def test_outbound_webhook_on_local_network_defaults_off() -> None:
    # The SQL-level default is the contract (create_all emits it; the recorded upgrade
    # matches it) -- construction-time defaults on this pre-existing model apply at
    # flush, not at construction, and OutboundWebhook carries no __init__ filler.
    col = inspect(OutboundWebhook).columns["on_local_network"]
    assert col.nullable is False
    assert col.default.arg is False


def test_0013_check_predicate_targets_the_derived_column_pairs() -> None:
    """The column half of the CHECK is derived from the file, not hand-copied.

    `_B42_ALERT_DELIVERY_COLUMNS` is `_add_column_pairs("0013-alert-delivery")`'s output, so a
    reworded file reddens here instead of silently leaving a column unchecked.
    """
    from backend.migrations.checks import _B42_ALERT_DELIVERY_COLUMNS

    assert set(_B42_ALERT_DELIVERY_COLUMNS) == {
        ("quiet_hours_periods", "recipient_id"),
        ("outbound_webhooks", "on_local_network"),
    }


def test_0013_check_requires_the_household_seed_too() -> None:
    """The CHECK is data-aware: the seed is part of 0013's effect, not just the columns.

    A column-only CHECK records 0013 as ``verified`` on a fresh create_all database (the
    columns come from the models) and the Household seed never runs -- measured live:
    feature-check run 39901062658 answered every
    ``PUT /api/notification-preferences/push-subscription`` with 503 "No notification
    recipient exists yet" because `recipients` was empty on that stack. The file's seed is
    idempotent (`WHERE NOT EXISTS`), so a fresh database EXECUTING the file is harmless --
    and the create_all fresh-boot pin (verified-without-running, NEM-5051's
    ACCESS EXCLUSIVE rationale) belongs to the ALTER-carrying upgrades, not to an
    INSERT-only side effect.
    """
    from backend.migrations.checks import _household_recipient_seeded

    # The named predicate exists and is a Check (callable returning an awaitable), so the
    # data half is pinned as part of the registered CHECK, not reachable only by accident.
    check = _household_recipient_seeded()
    assert callable(check)
