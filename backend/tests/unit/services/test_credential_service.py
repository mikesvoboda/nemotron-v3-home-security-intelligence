"""Unit tests for credential encryption service.

NEM-4382: Test-Driven Development for RTSP credential encryption.
These tests define the expected behavior for the CredentialService class.

Tests cover:
- Encryption and decryption roundtrip
- Invalid/empty input handling
- Key validation
- Error handling
"""

import pytest
from cryptography.fernet import Fernet, InvalidToken

from backend.services.credential_service import CredentialService


class TestCredentialService:
    """Test suite for CredentialService."""

    @pytest.fixture
    def valid_key(self) -> str:
        """Generate a valid Fernet key for testing."""
        return Fernet.generate_key().decode()

    @pytest.fixture
    def service(self, valid_key: str) -> CredentialService:
        """Create a CredentialService instance with a valid key."""
        return CredentialService(encryption_key=valid_key)

    def test_encrypt_decrypt_roundtrip(self, service: CredentialService) -> None:
        """Test that encryption and decryption work correctly together.

        Property: decrypt(encrypt(plaintext)) == plaintext
        """
        plaintext = "my_secure_password"  # pragma: allowlist secret

        # Encrypt the plaintext
        ciphertext = service.encrypt(plaintext)

        # Verify ciphertext is different from plaintext
        assert ciphertext != plaintext
        assert len(ciphertext) > len(plaintext)

        # Decrypt and verify it matches original
        decrypted = service.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_returns_different_values(self, service: CredentialService) -> None:
        """Test that encrypting the same plaintext multiple times produces different ciphertexts.

        This verifies that Fernet is using proper nonces/IVs.
        """
        plaintext = "password123"  # pragma: allowlist secret

        ciphertext1 = service.encrypt(plaintext)
        ciphertext2 = service.encrypt(plaintext)

        # Different ciphertexts
        assert ciphertext1 != ciphertext2

        # But both decrypt to same plaintext
        assert service.decrypt(ciphertext1) == plaintext
        assert service.decrypt(ciphertext2) == plaintext

    def test_encrypt_empty_string(self, service: CredentialService) -> None:
        """Test that encrypting an empty string succeeds."""
        ciphertext = service.encrypt("")
        assert ciphertext != ""
        assert service.decrypt(ciphertext) == ""

    def test_decrypt_empty_string(self, service: CredentialService) -> None:
        """Test that decrypting an empty string raises an error."""
        with pytest.raises(InvalidToken):
            service.decrypt("")

    def test_encrypt_unicode_characters(self, service: CredentialService) -> None:
        """Test encryption of passwords with Unicode characters."""
        plaintext = "pássw0rd_日本語_🔒"  # pragma: allowlist secret

        ciphertext = service.encrypt(plaintext)
        decrypted = service.decrypt(ciphertext)

        assert decrypted == plaintext

    def test_encrypt_long_password(self, service: CredentialService) -> None:
        """Test encryption of very long passwords."""
        plaintext = "a" * 1000  # pragma: allowlist secret

        ciphertext = service.encrypt(plaintext)
        decrypted = service.decrypt(ciphertext)

        assert decrypted == plaintext

    def test_invalid_encryption_key(self) -> None:
        """Test that invalid encryption keys raise an error during initialization."""
        with pytest.raises(ValueError, match="Fernet key must be"):
            CredentialService(encryption_key="not_a_valid_key")

    def test_decrypt_with_wrong_key(self, valid_key: str) -> None:
        """Test that decrypting with a different key fails."""
        service1 = CredentialService(encryption_key=valid_key)
        service2 = CredentialService(encryption_key=Fernet.generate_key().decode())

        plaintext = "secret_password"  # pragma: allowlist secret
        ciphertext = service1.encrypt(plaintext)

        # Decrypting with wrong key should raise InvalidToken
        with pytest.raises(InvalidToken):
            service2.decrypt(ciphertext)

    def test_decrypt_invalid_ciphertext(self, service: CredentialService) -> None:
        """Test that decrypting invalid ciphertext raises an error."""
        with pytest.raises(InvalidToken):
            service.decrypt("not_valid_ciphertext")

    def test_decrypt_corrupted_ciphertext(self, service: CredentialService) -> None:
        """Test that decrypting corrupted ciphertext raises an error."""
        plaintext = "password"  # pragma: allowlist secret
        ciphertext = service.encrypt(plaintext)

        # Corrupt the ciphertext
        corrupted = ciphertext[:-5] + "XXXXX"

        with pytest.raises(InvalidToken):
            service.decrypt(corrupted)

    def test_key_persistence(self, valid_key: str) -> None:
        """Test that multiple service instances with the same key can decrypt each other's data."""
        service1 = CredentialService(encryption_key=valid_key)
        service2 = CredentialService(encryption_key=valid_key)

        plaintext = "shared_password"  # pragma: allowlist secret

        ciphertext = service1.encrypt(plaintext)
        decrypted = service2.decrypt(ciphertext)

        assert decrypted == plaintext

    def test_encrypt_special_characters(self, service: CredentialService) -> None:
        """Test encryption of passwords with special characters."""
        plaintext = "p@$$w0rd!#&*()[]{}|\\:;\"'<>,.?/~`"  # pragma: allowlist secret

        ciphertext = service.encrypt(plaintext)
        decrypted = service.decrypt(ciphertext)

        assert decrypted == plaintext

    def test_encrypt_whitespace(self, service: CredentialService) -> None:
        """Test encryption of passwords with whitespace."""
        plaintext = "  password with spaces  "  # pragma: allowlist secret

        ciphertext = service.encrypt(plaintext)
        decrypted = service.decrypt(ciphertext)

        # Whitespace should be preserved
        assert decrypted == plaintext

    def test_none_input_raises_error(self, service: CredentialService) -> None:
        """Test that None input raises an appropriate error."""
        with pytest.raises((TypeError, AttributeError)):
            service.encrypt(None)  # type: ignore[arg-type]

        with pytest.raises((TypeError, AttributeError)):
            service.decrypt(None)  # type: ignore[arg-type]
