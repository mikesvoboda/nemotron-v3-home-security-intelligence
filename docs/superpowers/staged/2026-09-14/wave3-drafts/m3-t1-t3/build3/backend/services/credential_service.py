"""Credential encryption service for RTSP authentication.

NEM-4382: Service for encrypting and decrypting RTSP credentials.
Uses Fernet symmetric encryption to protect stored credentials.
"""

from __future__ import annotations

from cryptography.fernet import Fernet


class CredentialService:
    """Service for encrypting and decrypting credentials.

    Uses Fernet symmetric encryption which provides:
    - 128-bit AES in CBC mode
    - HMAC using SHA256 for authentication
    - Timestamps to reject old tokens
    """

    def __init__(self, encryption_key: str) -> None:
        """Initialize the credential service with an encryption key.

        Args:
            encryption_key: A valid Fernet key (base64-encoded 32-byte key)

        Raises:
            ValueError: If the encryption key is invalid or not provided
        """
        if not encryption_key:
            raise ValueError("Encryption key is required")

        try:
            self._fernet = Fernet(encryption_key.encode())
        except (TypeError, ValueError) as e:
            raise ValueError(f"Fernet key must be 32 url-safe base64-encoded bytes: {e}") from e

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string.

        Args:
            plaintext: The string to encrypt

        Returns:
            The encrypted string (base64-encoded)

        Raises:
            TypeError: If plaintext is None
            AttributeError: If plaintext is None
        """
        # Let Fernet handle None (raises TypeError/AttributeError)
        encrypted: bytes = self._fernet.encrypt(plaintext.encode())
        return encrypted.decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a ciphertext string.

        Args:
            ciphertext: The encrypted string (base64-encoded)

        Returns:
            The decrypted plaintext string

        Raises:
            TypeError: If ciphertext is None
            InvalidToken: If the ciphertext is invalid, empty, or tampered with
        """
        # Let Fernet handle invalid input (raises InvalidToken for empty,
        # TypeError/AttributeError for None)
        decrypted: bytes = self._fernet.decrypt(ciphertext.encode())
        return decrypted.decode("utf-8")
