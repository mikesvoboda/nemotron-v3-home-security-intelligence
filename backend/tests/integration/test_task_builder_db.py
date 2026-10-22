"""DB-backed tests for the production delivery task builder (B4.2).

The worker's ``build_payload`` seam has a default builder that ships an EMPTY
payload and no target (its own docstring says the production wiring replaces
it). These tests pin the production builder against real rows: the payload
comes from ``build_payload`` (F13 redaction applied), the target is the
channel's, and a stored signing secret is decrypted for the send, not stored
plaintext (design 4n-alerting.md:186 — secrets never plaintext in the DB).

Needs real Postgres: the builder runs real SELECTs against seeded rows.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch
from uuid import uuid7

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# asyncio_mode=auto (pyproject) makes async tests run under pytest-asyncio.


@pytest_asyncio.fixture
async def db_engine(worker_db_url: str):
    engine = create_async_engine(worker_db_url, isolation_level="AUTOCOMMIT")
    from backend.models.camera import Base
    from backend.models.outbound_webhook import OutboundWebhook  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=None)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def clean_tables(db_engine):
    """Truncate the delivery tables between tests (worker DBs are per-worker)."""
    async with db_engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE notification_deliveries, recipient_channels, recipients CASCADE")
        )
    yield
    async with db_engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE notification_deliveries, recipient_channels, recipients CASCADE")
        )


def _json_lit(d: dict[str, Any]) -> str:
    import json

    return json.dumps(d)


async def _seed_chain(
    session_factory: Any,
    *,
    metadata: dict[str, Any] | None = None,
    kind: str = "webhook",
    secret_encrypted: str | None = None,
) -> dict[str, str]:
    """One camera -> event -> alert chain plus one recipient and one channel."""
    recipient_id = str(uuid7())
    channel_id = str(uuid7())
    alert_id = str(uuid7())
    event_id = 740000 + int(uuid7().hex[-5:], 16) % 100000
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO cameras (id, name, folder_path, status, created_at,"
                " ingestion_mode, motion_sensitivity)"
                " VALUES ('front_door', 'Front door', '/media/front_door', 'online',"
                " timezone('utc', now()), 'rtsp', 0.5)"
                " ON CONFLICT (id) DO NOTHING"
            ),
        )
        await session.execute(
            text(
                "INSERT INTO events (id, batch_id, camera_id, started_at, version, reviewed,"
                " flagged, is_fast_path)"
                " VALUES (:eid, :batch, 'front_door', timezone('utc', now()), 1, FALSE,"
                " FALSE, FALSE)"
                " ON CONFLICT (id) DO NOTHING"
            ),
            {"eid": event_id, "batch": f"b-{event_id}"},
        )
        meta_json = _json_lit(metadata) if metadata is not None else None
        await session.execute(
            text(
                "INSERT INTO alerts (id, event_id, severity, status, created_at, updated_at,"
                " dedup_key, version_id, is_high_priority, match_count, metadata)"
                " VALUES (:aid, :eid, 'high', 'open', timezone('utc', now()),"
                " timezone('utc', now()), :dk, 1, FALSE, 1,"
                " CAST(:meta AS jsonb))"
            ),
            {"aid": alert_id, "eid": event_id, "dk": f"dk-{alert_id[:12]}", "meta": meta_json},
        )
        await session.execute(
            text(
                "INSERT INTO recipients (id, name, enabled, critical_breaks_quiet, created_at,"
                " updated_at)"
                " VALUES (:rid, :name, TRUE, TRUE, timezone('utc', now()), timezone('utc', now()))"
            ),
            {"rid": recipient_id, "name": f"r-{recipient_id}"},
        )
        await session.execute(
            text(
                "INSERT INTO recipient_channels (id, recipient_id, kind, target, enabled,"
                " include_names, on_local_network, signing_secret_encrypted, signing_secret_hint,"
                " created_at, updated_at)"
                " VALUES (:cid, :rid, :kind, 'https://hooks.example.test/hook', TRUE, FALSE,"
                " FALSE, :secret, 'abcd****', timezone('utc', now()), timezone('utc', now()))"
            ),
            {"cid": channel_id, "rid": recipient_id, "kind": kind, "secret": secret_encrypted},
        )
        await session.commit()
    return {
        "alert_id": alert_id,
        "recipient_id": recipient_id,
        "channel_id": channel_id,
    }


async def test_builder_builds_full_task(session_factory, clean_tables) -> None:
    """The production builder loads the alert and channel and fills every task
    field the adapters read: payload (F13-applied), target, include_names."""
    from backend.services.alerting.payload import build_delivery_task

    seeded = await _seed_chain(
        session_factory,
        metadata={"rule_name": "Person at door", "summary": "Known person Jane at the door"},
    )
    builder = build_delivery_task(session_factory)

    task = await builder(
        seeded["alert_id"],
        seeded["channel_id"],
        seeded["recipient_id"],
        {"idempotency_key": f"{seeded['alert_id']}:{seeded['channel_id']}", "kind": "webhook"},
        known_names={"Jane"},
    )

    assert task.delivery_id == seeded["alert_id"]
    assert task.channel_id == seeded["channel_id"]
    assert task.recipient_id == seeded["recipient_id"]
    assert task.channel_kind.value == "webhook"
    assert task.idempotency_key == f"{seeded['alert_id']}:{seeded['channel_id']}"
    assert task.target == "https://hooks.example.test/hook"
    assert task.include_names is False
    # F13: the gallery name is redacted in the payload text.
    assert "Jane" not in (task.payload.get("summary") or "")
    assert "a known person" in (task.payload.get("summary") or "")
    assert task.payload["alert_id"] == seeded["alert_id"]
    assert task.payload["title"] == "Person at door"
    assert task.payload["idempotency_key"] == task.idempotency_key


async def test_builder_decrypts_signing_secret(session_factory, clean_tables, monkeypatch) -> None:
    """A webhook channel's stored secret arrives on the task decrypted (the
    plaintext is resolved at send time only, from the encrypted column)."""
    from backend.core.config import get_settings
    from backend.core.secret_box import encrypt_secret
    from backend.services.alerting.payload import build_delivery_task

    monkeypatch.setenv("SECRETS_MASTER_KEY", "a" * 48)
    get_settings.cache_clear()

    seeded = await _seed_chain(session_factory, secret_encrypted=encrypt_secret("whsec-abc123"))
    builder = build_delivery_task(session_factory)

    task = await builder(
        seeded["alert_id"],
        seeded["channel_id"],
        seeded["recipient_id"],
        {"idempotency_key": "k", "kind": "webhook"},
    )

    assert task.signing_secret == "whsec-abc123"  # pragma: allowlist secret


async def test_builder_graceful_when_secret_unavailable(
    session_factory, clean_tables, monkeypatch
) -> None:
    """No SECRETS_MASTER_KEY configured: the send must fail closed with a
    clear error, not deliver unsigned (a forged secret could impersonate the
    household's receiver). The builder raises the SecretBox error; the worker
    records it as a failure for that delivery, as with any adapter error."""
    from backend.core.config import get_settings
    from backend.core.secret_box import SecretBoxUnavailableError, encrypt_secret
    from backend.services.alerting.payload import build_delivery_task

    monkeypatch.setenv("SECRETS_MASTER_KEY", "a" * 48)
    get_settings.cache_clear()

    seeded = await _seed_chain(session_factory, secret_encrypted=encrypt_secret("whsec-abc123"))
    builder = build_delivery_task(session_factory)

    # Simulate a lost key: the box cannot decrypt, so the builder refuses to
    # hand the adapter an unsigned task (fail closed). The worker's generic
    # adapter-error path records this as the delivery's failure.
    import pytest

    with patch(
        "backend.services.alerting.payload.decrypt_secret",
        side_effect=SecretBoxUnavailableError(
            "Stored secret does not decrypt under the current SECRETS_MASTER_KEY"
        ),
        autospec=True,
    ):
        with pytest.raises(SecretBoxUnavailableError):
            await builder(
                seeded["alert_id"],
                seeded["channel_id"],
                seeded["recipient_id"],
                {"idempotency_key": "k", "kind": "webhook"},
            )


async def test_builder_missing_alert_is_failure(session_factory, clean_tables) -> None:
    """A delivery row whose alert vanished (e.g. Trash purge) builds a task
    with an empty payload so the send is skipped rather than crashing the
    cycle — the worker's own default builder also carries an empty payload."""
    from backend.services.alerting.payload import build_delivery_task

    seeded = await _seed_chain(session_factory)
    builder = build_delivery_task(session_factory)

    task = await builder(
        "00000000-0000-0000-0000-000000000000",  # no such alert
        seeded["channel_id"],
        seeded["recipient_id"],
        {"idempotency_key": "k", "kind": "webhook"},
    )

    assert task.payload == {}
    assert task.target == "https://hooks.example.test/hook"
