"""Fernet encryption helpers for stored secrets (B4.2).

Webhook signing secrets are persisted encrypted, never plaintext: the
plaintext is shown to the operator once at channel creation and only the
Fernet ciphertext goes into the database. The key is the SECRETS_MASTER_KEY
from settings (hashed to the 32-byte Fernet key with SHA-256 so any
operator-chosen passphrase length works).
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from backend.core.config import get_settings


class SecretBoxUnavailableError(RuntimeError):
    """SECRETS_MASTER_KEY is not configured."""


def _fernet() -> Fernet:
    master = get_settings().secrets_master_key
    if master is None or not master.get_secret_value():
        raise SecretBoxUnavailableError(
            "SECRETS_MASTER_KEY is not set: webhook signing secrets cannot be "
            "encrypted or decrypted. Set it to a generated token "
            '(python -c "import secrets; print(secrets.token_urlsafe(48))").'
        )
    # SHA-256 of the operator's passphrase → 32 bytes → urlsafe base64, the
    # exact key shape Fernet demands (it validates the length strictly).
    digest = hashlib.sha256(master.get_secret_value().encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext secret into a storable Fernet token."""
    token: bytes = _fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(token: str) -> str:
    """Decrypt a stored Fernet token back to the plaintext secret.

    Raises:
        InvalidToken: The stored ciphertext does not decrypt under the
            current master key (key rotated or ciphertext corrupted).
    """
    try:
        plain: bytes = _fernet().decrypt(token.encode("utf-8"))
        return plain.decode("utf-8")
    except InvalidToken as exc:
        raise SecretBoxUnavailableError(
            "Stored secret does not decrypt under the current SECRETS_MASTER_KEY "
            "(key rotated since it was stored?)."
        ) from exc
