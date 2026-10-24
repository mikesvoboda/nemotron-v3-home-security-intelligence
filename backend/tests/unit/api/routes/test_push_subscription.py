"""Tests for the Web Push subscription API (B4.3).

Covers the This-browser subscription endpoints on the notification-preferences
router (4n-alerting.md "Screens": Settings > Notifications > This browser):

- ``PUT /api/notification-preferences/push-subscription`` registers or rotates
  this browser's ``webpush`` channel on the Household recipient;
- ``GET /api/notification-preferences/push-subscription`` answers the
  subscription's state with the keys NEVER returned in full (privacy row);
- ``DELETE /api/notification-preferences/push-subscription`` removes the
  channel row.

All tests use mocked database operations following the module's TDD shape.
"""

from __future__ import annotations

import base64
import os
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core import get_db
from backend.main import app
from backend.models.alert_delivery import Recipient, RecipientChannel
from backend.tests.unit.conftest import authenticated_async_client


def _subscription_body() -> dict[str, Any]:
    """A realistic PushSubscriptionJSON from a browser's pushManager.subscribe."""
    return {
        "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
        "keys": {
            "p256dh": base64.urlsafe_b64encode(os.urandom(65)).rstrip(b"=").decode(),
            "auth": base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode(),
        },
    }


def _recipient_row() -> MagicMock:
    r = MagicMock(spec=Recipient)
    r.id = str(uuid.uuid4())
    r.name = "Household"
    r.enabled = True
    return r


def _channel_row(enabled: bool = True, sub: dict[str, Any] | None = None) -> MagicMock:
    c = MagicMock(spec=RecipientChannel)
    c.id = str(uuid.uuid4())
    c.recipient_id = "r-1"
    from backend.models.alert_delivery import DeliveryChannelKind

    c.kind = DeliveryChannelKind.WEBPUSH
    c.target = "browser-device-1"
    c.push_subscription = sub
    c.enabled = enabled
    c.last_error = None
    return c


@pytest.fixture
def mock_db() -> AsyncMock:
    mock = AsyncMock()
    mock.execute = AsyncMock()
    mock.commit = AsyncMock()
    mock.refresh = AsyncMock()
    mock.add = MagicMock()
    mock.delete = AsyncMock()
    mock.rollback = AsyncMock()
    return mock


def create_mock_db_dependency(mock_db: AsyncMock):
    async def _mock_db_dependency():
        yield mock_db

    return _mock_db_dependency


class TestPutPushSubscription:
    """PUT /api/notification-preferences/push-subscription."""

    async def test_register_creates_webpush_channel(self, mock_db: AsyncMock) -> None:
        """A browser without a channel gets one on the Household recipient."""
        household = _recipient_row()

        def _scalar(recipients: list[Any]) -> Any:
            r = MagicMock()
            r.scalars.return_value.all.return_value = recipients
            return r

        mock_db.execute.side_effect = [
            _scalar([household]),  # recipients lookup
        ]

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with authenticated_async_client() as client:
                response = await client.put(
                    "/api/notification-preferences/push-subscription",
                    json={
                        "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
                        "keys": {"p256dh": "p" * 87, "auth": "a" * 22},
                    },
                )
            assert response.status_code == 200, response.text[:400]
            data = response.json()
            assert data["status"] == "registered"
            # The stored row never echoes the auth secret (masked fingerprint).
            assert data["push_subscription"]["keys"]["auth"] != "a" * 22
        finally:
            app.dependency_overrides.clear()

        added = [c for c in [mock_db.add.call_args] if c]
        assert added, "a channel row should be added"

    async def test_register_masks_keys_in_the_response(self, mock_db: AsyncMock) -> None:
        """Privacy (4n-alerting.md privacy section): the API never returns
        secrets or push keys in full."""
        household = _recipient_row()

        def _scalar(recipients: list[Any]) -> Any:
            r = MagicMock()
            r.scalars.return_value.all.return_value = recipients
            return r

        mock_db.execute.side_effect = [_scalar([household])]

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with authenticated_async_client() as client:
                response = await client.put(
                    "/api/notification-preferences/push-subscription",
                    json={
                        "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
                        "keys": {"p256dh": "p" * 87, "auth": "a" * 22},
                    },
                )
            assert response.status_code == 200
            body = response.text
            assert "a" * 22 not in body, "the auth secret leaked in the response"
        finally:
            app.dependency_overrides.clear()

    async def test_register_replaces_an_existing_subscription(self, mock_db: AsyncMock) -> None:
        """Rotation: an existing webpush channel for the browser is updated,
        not duplicated."""
        household = _recipient_row()
        existing = _channel_row(sub={"endpoint": "https://old.example/push", "keys": {}})
        existing.target = "browser-device-1"
        household.channels = [existing]

        def _scalar(recipients: list[Any]) -> Any:
            r = MagicMock()
            r.scalars.return_value.all.return_value = recipients
            return r

        mock_db.execute.side_effect = [_scalar([household])]

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with authenticated_async_client() as client:
                response = await client.put(
                    "/api/notification-preferences/push-subscription",
                    json={
                        "device_id": "browser-device-1",
                        "endpoint": "https://fcm.googleapis.com/fcm/send/new",
                        "keys": {"p256dh": "p" * 87, "auth": "a" * 22},
                    },
                )
            assert response.status_code == 200, response.text[:400]
            # The existing row is re-used (mutated), not duplicated.
            assert (
                existing.push_subscription["endpoint"] == "https://fcm.googleapis.com/fcm/send/new"
            )
            assert existing.enabled is True
            added = mock_db.add.call_count
            assert added == 0, "rotation must not insert a second channel"
        finally:
            app.dependency_overrides.clear()

    async def test_register_re_enables_a_disabled_channel(self, mock_db: AsyncMock) -> None:
        """A re-subscription after a 410 disable flips the row back on — the
        settings page then shows the channel active again."""
        household = _recipient_row()
        existing = _channel_row(enabled=False, sub={"endpoint": "https://old/x", "keys": {}})
        existing.target = "browser-device-1"
        household.channels = [existing]

        def _scalar(recipients: list[Any]) -> Any:
            r = MagicMock()
            r.scalars.return_value.all.return_value = recipients
            return r

        mock_db.execute.side_effect = [_scalar([household])]

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with authenticated_async_client() as client:
                response = await client.put(
                    "/api/notification-preferences/push-subscription",
                    json={
                        "device_id": "browser-device-1",
                        "endpoint": "https://fcm.googleapis.com/fcm/send/new",
                        "keys": {"p256dh": "p" * 87, "auth": "a" * 22},
                    },
                )
            assert response.status_code == 200, response.text[:400]
            assert existing.enabled is True
        finally:
            app.dependency_overrides.clear()

    async def test_register_rejects_a_body_without_keys(self, mock_db: AsyncMock) -> None:
        """Schema guard: a subscription without p256dh/auth keys is a 422."""
        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with authenticated_async_client() as client:
                response = await client.put(
                    "/api/notification-preferences/push-subscription",
                    json={"endpoint": "https://fcm.googleapis.com/fcm/send/abc123"},
                )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()


class TestGetPushSubscription:
    """GET /api/notification-preferences/push-subscription."""

    async def test_get_returns_masked_state(self, mock_db: AsyncMock) -> None:
        """State read for the settings page: registered, with masked keys."""
        household = _recipient_row()
        sub = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
            "keys": {"p256dh": "P" * 87, "auth": "A" * 22},
        }
        existing = _channel_row(enabled=True, sub=sub)
        existing.target = "browser-device-1"
        household.channels = [existing]

        def _scalar(recipients: list[Any]) -> Any:
            r = MagicMock()
            r.scalars.return_value.all.return_value = recipients
            return r

        mock_db.execute.side_effect = [_scalar([household])]

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with authenticated_async_client() as client:
                response = await client.get(
                    "/api/notification-preferences/push-subscription",
                    params={"device_id": "browser-device-1"},
                )
            assert response.status_code == 200, response.text[:400]
            data = response.json()
            assert data["registered"] is True
            assert data["enabled"] is True
            # Keys never come back in full.
            assert "A" * 22 not in response.text
            assert "P" * 87 not in response.text
            # The endpoint is host-only: the push token in the path is not echoed.
            assert data["push_subscription"]["endpoint"].startswith("fcm.googleapis.com/")
            assert "abc123" not in response.text
        finally:
            app.dependency_overrides.clear()

    async def test_get_unregistered_answers_not_registered(self, mock_db: AsyncMock) -> None:
        household = _recipient_row()
        household.channels = []

        def _scalar(recipients: list[Any]) -> Any:
            r = MagicMock()
            r.scalars.return_value.all.return_value = recipients
            return r

        mock_db.execute.side_effect = [_scalar([household])]

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with authenticated_async_client() as client:
                response = await client.get(
                    "/api/notification-preferences/push-subscription",
                    params={"device_id": "browser-device-1"},
                )
            assert response.status_code == 200
            assert response.json()["registered"] is False
        finally:
            app.dependency_overrides.clear()

    async def test_get_shows_a_disabled_channel_as_disabled(self, mock_db: AsyncMock) -> None:
        """The 410 disable must be visible in the recipient's settings
        (4n-alerting.md:236)."""
        household = _recipient_row()
        existing = _channel_row(enabled=False, sub={"endpoint": "https://x/y", "keys": {}})
        existing.target = "browser-device-1"
        existing.last_error = "subscription_expired"
        household.channels = [existing]

        def _scalar(recipients: list[Any]) -> Any:
            r = MagicMock()
            r.scalars.return_value.all.return_value = recipients
            return r

        mock_db.execute.side_effect = [_scalar([household])]

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with authenticated_async_client() as client:
                response = await client.get(
                    "/api/notification-preferences/push-subscription",
                    params={"device_id": "browser-device-1"},
                )
            assert response.status_code == 200
            data = response.json()
            assert data["registered"] is True
            assert data["enabled"] is False
        finally:
            app.dependency_overrides.clear()


class TestDeletePushSubscription:
    """DELETE /api/notification-preferences/push-subscription."""

    async def test_delete_removes_the_channel_row(self, mock_db: AsyncMock) -> None:
        household = _recipient_row()
        existing = _channel_row(sub={"endpoint": "https://x/y", "keys": {}})
        existing.target = "browser-device-1"
        household.channels = [existing]

        def _scalar(recipients: list[Any]) -> Any:
            r = MagicMock()
            r.scalars.return_value.all.return_value = recipients
            return r

        mock_db.execute.side_effect = [_scalar([household])]

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with authenticated_async_client() as client:
                response = await client.delete(
                    "/api/notification-preferences/push-subscription",
                    params={"device_id": "browser-device-1"},
                )
            assert response.status_code == 200, response.text[:400]
            assert mock_db.delete.await_count >= 1
        finally:
            app.dependency_overrides.clear()

    async def test_delete_of_an_unknown_device_is_a_noop_204(self, mock_db: AsyncMock) -> None:
        household = _recipient_row()
        household.channels = []

        def _scalar(recipients: list[Any]) -> Any:
            r = MagicMock()
            r.scalars.return_value.all.return_value = recipients
            return r

        mock_db.execute.side_effect = [_scalar([household])]

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            async with authenticated_async_client() as client:
                response = await client.delete(
                    "/api/notification-preferences/push-subscription",
                    params={"device_id": "browser-device-9"},
                )
            assert response.status_code == 200
            assert mock_db.delete.await_count == 0
        finally:
            app.dependency_overrides.clear()
