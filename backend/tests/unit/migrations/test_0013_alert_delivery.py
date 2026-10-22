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
    assert ids[-1] == "0013-alert-delivery"
    assert ids.index("0013-alert-delivery") == ids.index("0012-alert-pipeline-core") + 1


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
    """The CHECK is column-presence, not data-existence.

    A data-shaped predicate ("Household exists") would make a fresh create_all database
    EXECUTE the file, and the upgrade-path suite pins fresh boots as verified-without-
    running. The seed's real audience is databases that predate the column, where the
    columns are absent and the CHECK already said "run it".
    """
    from backend.migrations.checks import _B42_ALERT_DELIVERY_COLUMNS

    assert set(_B42_ALERT_DELIVERY_COLUMNS) == {
        ("quiet_hours_periods", "recipient_id"),
        ("outbound_webhooks", "on_local_network"),
    }
