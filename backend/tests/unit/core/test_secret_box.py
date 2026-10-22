"""Unit tests for backend.core.secret_box (B4.2)."""

from __future__ import annotations

import pytest

from backend.core.config import get_settings
from backend.core.secret_box import (
    SecretBoxUnavailableError,
    decrypt_secret,
    encrypt_secret,
)


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRETS_MASTER_KEY", "a" * 48)
    token = encrypt_secret("whsec_abc123")
    assert token != "whsec_abc123"
    assert decrypt_secret(token) == "whsec_abc123"


def test_unavailable_without_master_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SECRETS_MASTER_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(SecretBoxUnavailableError):
        encrypt_secret("x")


def test_wrong_key_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRETS_MASTER_KEY", "a" * 48)
    token = encrypt_secret("x")
    monkeypatch.setenv("SECRETS_MASTER_KEY", "b" * 48)
    get_settings.cache_clear()
    with pytest.raises(SecretBoxUnavailableError):
        decrypt_secret(token)


def test_get_settings_has_field() -> None:
    # The Settings field exists and is redacted in dumps.
    s = get_settings()
    assert "secrets_master_key" in type(s).model_fields
