"""Comprehensive tests for credentials generation module.

Tests cover:
- Password generation with various options
- API key generation
- Password strength validation
- Secret redaction
- CredentialConfig dataclass
- CredentialsManager class methods
- Docker secrets creation
- .env file writing
- Database URL generation
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from setup_lib.credentials import (
    DIGITS,
    LOWERCASE,
    MIN_PASSWORD_LENGTH,
    SPECIAL_CHARS,
    UPPERCASE,
    CredentialConfig,
    CredentialsManager,
    PasswordStrength,
    generate_api_key,
    generate_password,
    prompt_and_generate_credentials,
    redact_secret,
    validate_password_strength,
)

# =============================================================================
# generate_password Tests
# =============================================================================


class TestGeneratePassword:
    """Tests for generate_password function."""

    def test_default_length_is_32(self) -> None:
        """Default password length is 32 characters."""
        password = generate_password()
        assert len(password) == 32

    def test_custom_length_respected_if_above_minimum(self) -> None:
        """Custom length is respected when above minimum."""
        password = generate_password(length=64)
        assert len(password) == 64

    def test_minimum_length_enforced(self) -> None:
        """Minimum length of 32 is enforced even if shorter requested."""
        password = generate_password(length=8)
        assert len(password) == MIN_PASSWORD_LENGTH

    def test_minimum_length_enforced_for_zero(self) -> None:
        """Minimum length enforced for zero length request."""
        password = generate_password(length=0)
        assert len(password) == MIN_PASSWORD_LENGTH

    def test_minimum_length_enforced_for_negative(self) -> None:
        """Minimum length enforced for negative length request."""
        password = generate_password(length=-10)
        assert len(password) == MIN_PASSWORD_LENGTH

    def test_includes_lowercase_by_default(self) -> None:
        """Password includes lowercase letters by default."""
        # Generate multiple passwords to handle randomness
        for _ in range(10):
            password = generate_password()
            if any(c in LOWERCASE for c in password):
                return
        pytest.fail("No lowercase characters found in 10 generated passwords")

    def test_includes_uppercase_by_default(self) -> None:
        """Password includes uppercase letters by default."""
        for _ in range(10):
            password = generate_password()
            if any(c in UPPERCASE for c in password):
                return
        pytest.fail("No uppercase characters found in 10 generated passwords")

    def test_includes_digits_by_default(self) -> None:
        """Password includes digits by default."""
        for _ in range(10):
            password = generate_password()
            if any(c in DIGITS for c in password):
                return
        pytest.fail("No digits found in 10 generated passwords")

    def test_includes_special_chars_by_default(self) -> None:
        """Password includes special characters by default."""
        for _ in range(10):
            password = generate_password()
            if any(c in SPECIAL_CHARS for c in password):
                return
        pytest.fail("No special characters found in 10 generated passwords")

    def test_exclude_uppercase(self) -> None:
        """Can exclude uppercase letters."""
        for _ in range(10):
            password = generate_password(include_uppercase=False)
            assert not any(c in UPPERCASE for c in password)

    def test_exclude_lowercase(self) -> None:
        """Can exclude lowercase letters."""
        for _ in range(10):
            password = generate_password(include_lowercase=False)
            assert not any(c in LOWERCASE for c in password)

    def test_exclude_digits(self) -> None:
        """Can exclude digits."""
        for _ in range(10):
            password = generate_password(include_digits=False)
            assert not any(c in DIGITS for c in password)

    def test_exclude_special_chars(self) -> None:
        """Can exclude special characters."""
        for _ in range(10):
            password = generate_password(include_special=False)
            assert not any(c in SPECIAL_CHARS for c in password)

    def test_only_lowercase(self) -> None:
        """Can generate password with only lowercase."""
        password = generate_password(
            include_uppercase=False,
            include_digits=False,
            include_special=False,
        )
        assert all(c in LOWERCASE for c in password)

    def test_only_uppercase(self) -> None:
        """Can generate password with only uppercase."""
        password = generate_password(
            include_lowercase=False,
            include_digits=False,
            include_special=False,
        )
        assert all(c in UPPERCASE for c in password)

    def test_raises_if_all_excluded(self) -> None:
        """Raises ValueError if all character types excluded."""
        with pytest.raises(ValueError, match="At least one character type"):
            generate_password(
                include_lowercase=False,
                include_uppercase=False,
                include_digits=False,
                include_special=False,
            )

    def test_passwords_are_unique(self) -> None:
        """Generated passwords should be unique (cryptographically random)."""
        passwords = {generate_password() for _ in range(100)}
        assert len(passwords) == 100  # All unique

    def test_uses_secrets_module(self) -> None:
        """Verify secrets module is used for cryptographic randomness."""
        with patch("setup_lib.credentials.secrets.choice") as mock_choice:
            mock_choice.side_effect = lambda x: x[0]  # Always return first char
            with patch("setup_lib.credentials.secrets.randbelow") as mock_randbelow:
                mock_randbelow.return_value = 0
                generate_password(length=32)
                assert mock_choice.called


# =============================================================================
# generate_api_key Tests
# =============================================================================


class TestGenerateApiKey:
    """Tests for generate_api_key function."""

    def test_default_prefix(self) -> None:
        """Default prefix is 'hsi_'."""
        key = generate_api_key()
        assert key.startswith("hsi_")

    def test_custom_prefix(self) -> None:
        """Custom prefix is applied."""
        key = generate_api_key(prefix="test_")
        assert key.startswith("test_")

    def test_empty_prefix(self) -> None:
        """Empty prefix produces key without prefix."""
        key = generate_api_key(prefix="")
        assert not key.startswith("hsi_")

    def test_key_is_url_safe(self) -> None:
        """Generated key is URL-safe."""
        key = generate_api_key()
        # URL-safe base64 only contains [A-Za-z0-9_-]
        key_without_prefix = key.removeprefix("hsi_")
        assert re.match(r"^[A-Za-z0-9_-]+$", key_without_prefix)

    def test_key_length(self) -> None:
        """Key has appropriate length (prefix + 43 chars for 32 bytes base64)."""
        key = generate_api_key()
        # 32 bytes -> 43 characters in URL-safe base64
        assert len(key) >= 43 + 4  # 4 for "hsi_"

    def test_keys_are_unique(self) -> None:
        """Generated keys should be unique."""
        keys = {generate_api_key() for _ in range(100)}
        assert len(keys) == 100


# =============================================================================
# validate_password_strength Tests
# =============================================================================


class TestValidatePasswordStrength:
    """Tests for validate_password_strength function."""

    def test_empty_password_is_weak(self) -> None:
        """Empty password is weak."""
        assert validate_password_strength("") == PasswordStrength.WEAK

    def test_common_weak_passwords(self) -> None:
        """Common weak passwords are detected."""
        weak_passwords = ["password", "123456", "admin", "root", "changeme"]
        for pwd in weak_passwords:
            assert validate_password_strength(pwd) == PasswordStrength.WEAK

    def test_short_password_is_weak(self) -> None:
        """Short passwords (< 8 chars) with limited character types are weak."""
        # Very short password with only lowercase
        assert validate_password_strength("abc") == PasswordStrength.WEAK

    def test_medium_length_mixed_case(self) -> None:
        """16+ chars with mixed case is at least medium."""
        password = "AbcDefGhiJkl1234!"  # pragma: allowlist secret  # nosemgrep: hardcoded-password
        strength = validate_password_strength(password)
        assert strength in (PasswordStrength.MEDIUM, PasswordStrength.STRONG)

    def test_long_password_all_types_is_strong(self) -> None:
        """32+ chars with all character types is strong."""
        password = generate_password()  # Uses all types
        assert validate_password_strength(password) == PasswordStrength.STRONG

    def test_sequential_chars_reduce_strength(self) -> None:
        """Sequential characters (abc, 123) reduce strength."""
        # Password with sequential pattern
        password = (
            "abc123DEF!@#abcdefghij"  # pragma: allowlist secret  # nosemgrep: hardcoded-password
        )
        strength = validate_password_strength(password)
        # Should be penalized but still could be medium due to length/variety
        assert strength in (PasswordStrength.WEAK, PasswordStrength.MEDIUM)

    def test_repeated_chars_reduce_strength(self) -> None:
        """Repeated characters (aaa, 111) reduce strength."""
        password = (
            "AAAAAAbbbbbb123456!!!!!!!"  # pragma: allowlist secret  # nosemgrep: hardcoded-password
        )
        strength = validate_password_strength(password)
        assert strength in (PasswordStrength.WEAK, PasswordStrength.MEDIUM)

    def test_only_lowercase_is_not_strong(self) -> None:
        """Password with only lowercase is not strong."""
        password = "abcdefghijklmnopqrstuvwxyzabcd"  # pragma: allowlist secret  # nosemgrep: hardcoded-password
        strength = validate_password_strength(password)
        assert strength != PasswordStrength.STRONG


# =============================================================================
# redact_secret Tests
# =============================================================================


class TestRedactSecret:
    """Tests for redact_secret function."""

    def test_long_secret_shows_first_and_last(self) -> None:
        """Long secret shows first and last 2 characters."""
        result = redact_secret("mysupersecretpassword")
        assert result == "my*****************rd"

    def test_short_secret_fully_redacted(self) -> None:
        """Short secret (<=4 chars) is fully redacted."""
        result = redact_secret("abcd")
        assert result == "**********"

    def test_empty_secret_fully_redacted(self) -> None:
        """Empty secret returns redaction placeholder."""
        result = redact_secret("")
        assert result == "**********"

    def test_custom_visible_chars(self) -> None:
        """Custom visible_chars parameter works."""
        result = redact_secret("mysupersecretpassword", visible_chars=4)
        assert result == "mysu*************word"

    def test_secret_at_boundary(self) -> None:
        """Secret at boundary (exactly 5 chars with 2 visible) is fully redacted."""
        result = redact_secret("abcde")
        assert result == "ab*de"


# =============================================================================
# CredentialConfig Tests
# =============================================================================


class TestCredentialConfig:
    """Tests for CredentialConfig dataclass."""

    def test_default_values(self) -> None:
        """Default values are correct."""
        config = CredentialConfig()
        assert config.postgres_password_length == 32  # pragma: allowlist secret
        assert config.redis_password_length == 32  # pragma: allowlist secret
        assert config.mqtt_password_length == 32  # pragma: allowlist secret
        assert config.api_key_prefix == "hsi_"  # pragma: allowlist secret
        assert config.include_special_chars is True
        assert config.docker_secrets_mode is False

    def test_custom_values(self) -> None:
        """Custom values can be set."""
        config = CredentialConfig(
            postgres_password_length=64,  # pragma: allowlist secret
            redis_password_length=48,  # pragma: allowlist secret
            mqtt_password_length=40,  # pragma: allowlist secret
            api_key_prefix="custom_",  # pragma: allowlist secret
            include_special_chars=False,
            docker_secrets_mode=True,
        )
        assert config.postgres_password_length == 64  # pragma: allowlist secret
        assert config.redis_password_length == 48  # pragma: allowlist secret
        assert config.mqtt_password_length == 40  # pragma: allowlist secret
        assert config.api_key_prefix == "custom_"  # pragma: allowlist secret
        assert config.include_special_chars is False
        assert config.docker_secrets_mode is True


# =============================================================================
# CredentialsManager Tests
# =============================================================================


class TestCredentialsManager:
    """Tests for CredentialsManager class."""

    def test_generate_all_creates_all_credentials(self) -> None:
        """generate_all creates all required credentials."""
        manager = CredentialsManager()
        credentials = manager.generate_all()

        assert "postgres_password" in credentials
        assert "redis_password" in credentials
        assert "mqtt_password" in credentials
        assert "api_key" in credentials

    def test_generate_all_respects_config_lengths(self) -> None:
        """generate_all respects custom password lengths."""
        config = CredentialConfig(
            postgres_password_length=64,
            redis_password_length=48,
        )
        manager = CredentialsManager(config=config)
        credentials = manager.generate_all()

        assert len(credentials["postgres_password"]) == 64
        assert len(credentials["redis_password"]) == 48

    def test_generate_all_respects_special_chars_setting(self) -> None:
        """generate_all respects include_special_chars setting."""
        config = CredentialConfig(include_special_chars=False)
        manager = CredentialsManager(config=config)
        credentials = manager.generate_all()

        for name, value in credentials.items():
            if name != "api_key":  # API key uses URL-safe encoding
                assert not any(c in SPECIAL_CHARS for c in value)

    def test_callback_called_on_generation(self) -> None:
        """on_credential_generated callback is called for each credential."""
        generated: list[tuple[str, str]] = []

        def callback(name: str, redacted: str) -> None:
            generated.append((name, redacted))

        manager = CredentialsManager()
        manager.on_credential_generated = callback
        manager.generate_all()

        assert len(generated) == 4
        names = [g[0] for g in generated]
        assert "postgres_password" in names
        assert "redis_password" in names
        assert "mqtt_password" in names
        assert "api_key" in names

    def test_get_credential_returns_value(self) -> None:
        """get_credential returns stored credential value."""
        manager = CredentialsManager()
        manager.generate_all()

        value = manager.get_credential("postgres_password")
        assert value is not None
        assert len(value) >= 32

    def test_get_credential_returns_none_for_missing(self) -> None:
        """get_credential returns None for missing credential."""
        manager = CredentialsManager()
        assert manager.get_credential("nonexistent") is None

    def test_has_credential_returns_true_for_existing(self) -> None:
        """has_credential returns True for existing credential."""
        manager = CredentialsManager()
        manager.generate_all()
        assert manager.has_credential("postgres_password") is True

    def test_has_credential_returns_false_for_missing(self) -> None:
        """has_credential returns False for missing credential."""
        manager = CredentialsManager()
        assert manager.has_credential("postgres_password") is False

    def test_clear_credentials_removes_all(self) -> None:
        """clear_credentials removes all stored credentials."""
        manager = CredentialsManager()
        manager.generate_all()
        manager.clear_credentials()

        assert len(manager.credentials) == 0
        assert manager.get_credential("postgres_password") is None


class TestCredentialsManagerRotation:
    """Tests for credential rotation functionality."""

    def test_rotate_credential_generates_new_value(self) -> None:
        """rotate_credential generates a new value."""
        manager = CredentialsManager()
        manager.generate_all()

        old_value = manager.get_credential("postgres_password")
        new_value = manager.rotate_credential("postgres_password")

        assert new_value is not None
        assert new_value != old_value
        assert manager.get_credential("postgres_password") == new_value

    def test_rotate_api_key(self) -> None:
        """rotate_credential works for API key."""
        manager = CredentialsManager()
        manager.generate_all()

        old_key = manager.get_credential("api_key")
        new_key = manager.rotate_credential("api_key")

        assert new_key is not None
        assert new_key != old_key
        assert new_key.startswith("hsi_")

    def test_rotate_unknown_credential_raises(self) -> None:
        """rotate_credential raises ValueError for unknown credential."""
        manager = CredentialsManager()
        with pytest.raises(ValueError, match="Unknown credential"):
            manager.rotate_credential("unknown_credential")


class TestCredentialsManagerEnvFile:
    """Tests for .env file operations."""

    def test_write_env_file_creates_file(self, env_file_path: Path) -> None:
        """write_env_file creates the .env file."""
        manager = CredentialsManager()
        manager.generate_all()

        result = manager.write_env_file(env_file_path)

        assert result is True
        assert env_file_path.exists()

    def test_write_env_file_contains_credentials(self, env_file_path: Path) -> None:
        """write_env_file includes all credentials."""
        manager = CredentialsManager()
        manager.generate_all()
        manager.write_env_file(env_file_path)

        content = env_file_path.read_text()

        assert "POSTGRES_PASSWORD=" in content
        assert "REDIS_PASSWORD=" in content
        assert "MQTT_PASSWORD=" in content
        assert "API_KEY=" in content
        assert "DATABASE_URL=" in content

    def test_write_env_file_sets_permissions(self, env_file_path: Path) -> None:
        """write_env_file sets secure permissions (600)."""
        manager = CredentialsManager()
        manager.generate_all()
        manager.write_env_file(env_file_path)

        mode = env_file_path.stat().st_mode
        # Check that permissions are 600 (owner read/write only)
        assert mode & 0o777 == 0o600

    def test_write_env_file_custom_permissions(self, env_file_path: Path) -> None:
        """write_env_file respects custom permissions."""
        manager = CredentialsManager()
        manager.generate_all()
        manager.write_env_file(env_file_path, mode=0o640)

        mode = env_file_path.stat().st_mode
        assert mode & 0o777 == 0o640

    def test_write_env_file_creates_parent_dirs(self, tmp_path: Path) -> None:
        """write_env_file creates parent directories."""
        nested_path = tmp_path / "nested" / "dir" / ".env"
        manager = CredentialsManager()
        manager.generate_all()

        result = manager.write_env_file(nested_path)

        assert result is True
        assert nested_path.exists()

    def test_write_env_file_raises_if_no_credentials(self, env_file_path: Path) -> None:
        """write_env_file raises RuntimeError if no credentials generated."""
        manager = CredentialsManager()
        with pytest.raises(RuntimeError, match="No credentials generated"):
            manager.write_env_file(env_file_path)


class TestCredentialsManagerDatabaseUrl:
    """Tests for database URL generation."""

    def test_get_database_url_default_values(self) -> None:
        """get_database_url uses default values."""
        manager = CredentialsManager()
        manager.generate_all()

        url = manager.get_database_url()

        assert url.startswith("postgresql://postgres:")
        assert "@localhost:5432/home_security" in url

    def test_get_database_url_custom_values(self) -> None:
        """get_database_url accepts custom values."""
        manager = CredentialsManager()
        manager.generate_all()

        url = manager.get_database_url(
            host="dbserver",
            port=5433,
            database="mydb",
            user="myuser",
        )

        assert "myuser:" in url
        assert "@dbserver:5433/mydb" in url

    def test_get_database_url_encodes_special_chars(self) -> None:
        """get_database_url properly encodes special characters."""
        manager = CredentialsManager()
        # Set a password with special characters
        manager.credentials["postgres_password"] = "p@ss:word/test"  # pragma: allowlist secret

        url = manager.get_database_url()

        # Special characters should be URL-encoded
        assert "p%40ss%3Aword%2Ftest" in url

    def test_get_database_url_raises_if_no_password(self) -> None:
        """get_database_url raises RuntimeError if password not generated."""
        manager = CredentialsManager()
        with pytest.raises(RuntimeError, match="PostgreSQL password not generated"):
            manager.get_database_url()


class TestCredentialsManagerDockerSecrets:
    """Tests for Docker secrets creation."""

    def test_create_docker_secrets_file_mode(
        self, secrets_dir: Path, mock_subprocess: MagicMock
    ) -> None:
        """create_docker_secrets creates files in directory mode."""
        manager = CredentialsManager()
        manager.generate_all()

        result = manager.create_docker_secrets(secrets_dir)

        assert result is True
        assert (secrets_dir / "postgres_password").exists()
        assert (secrets_dir / "redis_password").exists()
        assert (secrets_dir / "mqtt_password").exists()
        assert (secrets_dir / "api_key").exists()

    def test_create_docker_secrets_file_permissions(
        self, secrets_dir: Path, mock_subprocess: MagicMock
    ) -> None:
        """create_docker_secrets sets secure file permissions."""
        manager = CredentialsManager()
        manager.generate_all()
        manager.create_docker_secrets(secrets_dir)

        for name in ["postgres_password", "redis_password", "mqtt_password", "api_key"]:
            secret_file = secrets_dir / name
            mode = secret_file.stat().st_mode
            assert mode & 0o777 == stat.S_IRUSR | stat.S_IWUSR  # 600

    def test_create_docker_secrets_swarm_mode(self, mock_subprocess: MagicMock) -> None:
        """create_docker_secrets uses docker secret create in swarm mode."""
        # First call to inspect returns error (secret doesn't exist)
        # Second call to create returns success
        mock_subprocess.side_effect = [
            MagicMock(returncode=1),  # inspect fails
            MagicMock(returncode=0),  # create succeeds
            MagicMock(returncode=1),  # inspect fails
            MagicMock(returncode=0),  # create succeeds
            MagicMock(returncode=1),  # inspect fails
            MagicMock(returncode=0),  # create succeeds
            MagicMock(returncode=1),  # inspect fails
            MagicMock(returncode=0),  # create succeeds
        ]

        manager = CredentialsManager()
        manager.generate_all()

        result = manager.create_docker_secrets()  # No secrets_dir = swarm mode

        assert result is True
        # Check that create was called with stdin input
        create_calls = [c for c in mock_subprocess.call_args_list if "create" in str(c)]
        assert len(create_calls) == 4

    def test_create_docker_secrets_raises_if_no_credentials(self, secrets_dir: Path) -> None:
        """create_docker_secrets raises RuntimeError if no credentials."""
        manager = CredentialsManager()
        with pytest.raises(RuntimeError, match="No credentials generated"):
            manager.create_docker_secrets(secrets_dir)


class TestCredentialsManagerLoadFromEnv:
    """Tests for loading credentials from environment."""

    def test_load_from_env_loads_existing(self, clean_env: None) -> None:
        """load_from_env loads credentials from environment variables."""
        os.environ["POSTGRES_PASSWORD"] = "test_postgres_pw"  # pragma: allowlist secret
        os.environ["REDIS_PASSWORD"] = "test_redis_pw"  # pragma: allowlist secret

        manager = CredentialsManager()
        result = manager.load_from_env()

        assert result is True
        assert (
            manager.get_credential("postgres_password") == "test_postgres_pw"
        )  # pragma: allowlist secret
        assert (
            manager.get_credential("redis_password") == "test_redis_pw"
        )  # pragma: allowlist secret

    def test_load_from_env_returns_false_if_empty(self, clean_env: None) -> None:
        """load_from_env returns False if no environment variables set."""
        manager = CredentialsManager()
        result = manager.load_from_env()

        assert result is False
        assert len(manager.credentials) == 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestPromptAndGenerateCredentials:
    """Tests for interactive credential generation."""

    def test_prompt_generates_credentials(
        self, env_file_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """prompt_and_generate_credentials creates credentials."""
        # Mock input to decline overwrite and confirm generation
        inputs = iter(["y"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs, ""))

        config = {"env_file_path": str(env_file_path)}
        credentials = prompt_and_generate_credentials(config)

        assert len(credentials) == 4
        assert env_file_path.exists()

    def test_prompt_skips_if_existing_and_declined(
        self, env_file_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """prompt_and_generate_credentials skips if user declines overwrite."""
        # Create existing file
        env_file_path.write_text("existing content")

        # Mock input to decline overwrite
        inputs = iter(["n"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs, "n"))

        config = {"env_file_path": str(env_file_path)}
        credentials = prompt_and_generate_credentials(config)

        assert len(credentials) == 0
        assert env_file_path.read_text() == "existing content"
