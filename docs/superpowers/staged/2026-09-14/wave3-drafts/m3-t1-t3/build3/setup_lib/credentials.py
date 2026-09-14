"""Credentials and secrets generation for setup.py.

Provides secure credential generation, validation, and management for the
Home Security Intelligence application. Supports both .env file and Docker
secrets modes for flexible deployment scenarios.

Security Notes:
    - Uses secrets module for cryptographically secure random generation
    - Minimum 32 character passwords enforced
    - Passwords include uppercase, lowercase, numbers, and special characters
    - Secrets are never logged or printed (only redacted versions)
    - .env files are written with 600 permissions (owner read/write only)
    - Docker secrets are passed via stdin, never CLI arguments

Usage:
    from setup_lib.credentials import CredentialsManager, generate_password

    # Generate a single password
    password = generate_password(length=32)

    # Manage all credentials
    manager = CredentialsManager()
    manager.generate_all()
    manager.write_env_file(Path(".env"))
"""

from __future__ import annotations

import os
import re
import secrets
import stat
import string
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

if TYPE_CHECKING:
    from collections.abc import Callable


class PasswordStrength(Enum):
    """Password strength levels for validation."""

    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"


# Minimum password length for security
MIN_PASSWORD_LENGTH = 32

# Character sets for password generation
LOWERCASE = string.ascii_lowercase
UPPERCASE = string.ascii_uppercase
DIGITS = string.digits
# Special characters safe for use in environment variables and database URLs
SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"


def generate_password(
    length: int = 32,
    include_uppercase: bool = True,
    include_lowercase: bool = True,
    include_digits: bool = True,
    include_special: bool = True,
) -> str:
    """Generate a cryptographically secure random password.

    Uses the secrets module for cryptographic randomness. Enforces a minimum
    length of 32 characters for security, even if a shorter length is requested.

    Args:
        length: Desired password length. Enforced minimum of 32.
        include_uppercase: Include uppercase letters (A-Z).
        include_lowercase: Include lowercase letters (a-z).
        include_digits: Include digits (0-9).
        include_special: Include special characters (!@#$%^&*()_+-=[]{}|;:,.<>?).

    Returns:
        Cryptographically secure random password string.

    Raises:
        ValueError: If all character types are excluded.

    Examples:
        >>> len(generate_password()) >= 32
        True
        >>> len(generate_password(length=64)) == 64
        True
        >>> len(generate_password(length=16)) == 32  # Enforced minimum
        True
    """
    # Enforce minimum length
    effective_length = max(length, MIN_PASSWORD_LENGTH)

    # Build character set
    charset = ""
    required_chars: list[str] = []

    if include_lowercase:
        charset += LOWERCASE
        required_chars.append(secrets.choice(LOWERCASE))
    if include_uppercase:
        charset += UPPERCASE
        required_chars.append(secrets.choice(UPPERCASE))
    if include_digits:
        charset += DIGITS
        required_chars.append(secrets.choice(DIGITS))
    if include_special:
        charset += SPECIAL_CHARS
        required_chars.append(secrets.choice(SPECIAL_CHARS))

    if not charset:
        raise ValueError("At least one character type must be included")

    # Generate remaining characters
    remaining_length = effective_length - len(required_chars)
    password_chars = required_chars + [secrets.choice(charset) for _ in range(remaining_length)]

    # Shuffle to avoid predictable positions
    # Use Fisher-Yates shuffle with secrets for cryptographic randomness
    for i in range(len(password_chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        password_chars[i], password_chars[j] = password_chars[j], password_chars[i]

    return "".join(password_chars)


def generate_api_key(prefix: str = "hsi_") -> str:
    """Generate a URL-safe API key with optional prefix.

    Uses secrets.token_urlsafe for cryptographically secure random generation.
    The resulting key is URL-safe and suitable for use in HTTP headers.

    Args:
        prefix: Prefix to add to the API key (default: "hsi_" for Home Security Intelligence).

    Returns:
        URL-safe API key string with prefix.

    Examples:
        >>> key = generate_api_key()
        >>> key.startswith("hsi_")
        True
        >>> len(key) >= 48  # prefix + 32 bytes base64
        True
    """
    # Generate 32 bytes of random data, URL-safe base64 encoded
    token = secrets.token_urlsafe(32)
    return f"{prefix}{token}"


def validate_password_strength(password: str) -> PasswordStrength:
    """Validate password strength based on complexity criteria.

    Evaluates password against multiple criteria:
    - Length (minimum 32 for strong)
    - Character variety (uppercase, lowercase, digits, special)
    - Common patterns (sequential, repeated)

    Args:
        password: Password string to validate.

    Returns:
        PasswordStrength enum value (WEAK, MEDIUM, or STRONG).

    Examples:
        >>> validate_password_strength("password") == PasswordStrength.WEAK
        True
        >>> validate_password_strength("P@ssw0rd123!") == PasswordStrength.MEDIUM
        True
    """
    if not password:
        return PasswordStrength.WEAK

    score = 0

    # Length scoring
    if len(password) >= 32:
        score += 3
    elif len(password) >= 16:
        score += 2
    elif len(password) >= 8:
        score += 1

    # Character type presence
    has_lower = bool(re.search(r"[a-z]", password))
    has_upper = bool(re.search(r"[A-Z]", password))
    has_digit = bool(re.search(r"\d", password))
    has_special = bool(re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]", password))

    char_types = sum([has_lower, has_upper, has_digit, has_special])
    score += char_types

    # Penalty for common patterns
    # Sequential characters (abc, 123)
    if re.search(
        r"(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|"
        r"opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz|012|123|234|345|"
        r"456|567|678|789)",
        password.lower(),
    ):
        score -= 1

    # Repeated characters (aaa, 111)
    if re.search(r"(.)\1{2,}", password):
        score -= 1

    # Common weak passwords
    weak_passwords = {
        "password",
        "123456",
        "admin",
        "root",
        "changeme",
        "secret",
        "postgres",
        "redis",
        "mqtt",
        "security_dev_password",
    }
    if password.lower() in weak_passwords:
        return PasswordStrength.WEAK

    # Determine strength
    if score >= 6:
        return PasswordStrength.STRONG
    elif score >= 3:
        return PasswordStrength.MEDIUM
    return PasswordStrength.WEAK


def redact_secret(secret: str, visible_chars: int = 2) -> str:
    """Safely redact a secret for logging, showing only first and last characters.

    Useful for debugging and logging without exposing actual secrets.

    Args:
        secret: Secret string to redact.
        visible_chars: Number of characters to show at start and end (default: 2).

    Returns:
        Redacted string with middle replaced by asterisks.

    Examples:
        >>> redact_secret("mysupersecretpassword")
        'my***************rd'
        >>> redact_secret("short")
        '**********'
        >>> redact_secret("")
        '**********'
    """
    if not secret or len(secret) <= visible_chars * 2:
        return "*" * 10

    start = secret[:visible_chars]
    end = secret[-visible_chars:]
    middle_len = len(secret) - (visible_chars * 2)
    return f"{start}{'*' * middle_len}{end}"


@dataclass
class CredentialConfig:
    """Configuration for credential generation.

    Attributes:
        postgres_password_length: Length for PostgreSQL password.
        redis_password_length: Length for Redis password.
        mqtt_password_length: Length for MQTT password.
        api_key_prefix: Prefix for generated API keys.
        include_special_chars: Whether to include special characters in passwords.
        docker_secrets_mode: Whether to use Docker secrets instead of .env.
    """

    postgres_password_length: int = 32
    redis_password_length: int = 32
    mqtt_password_length: int = 32
    api_key_prefix: str = "hsi_"
    include_special_chars: bool = True
    docker_secrets_mode: bool = False


@dataclass
class CredentialsManager:
    """Manager for generating, storing, and rotating application credentials.

    Handles all credential operations for the Home Security Intelligence
    application, including PostgreSQL, Redis, MQTT, and API keys.

    Attributes:
        config: CredentialConfig for customizing generation.
        credentials: Dictionary of generated credentials (name -> value).
        on_credential_generated: Callback when a credential is generated.

    Examples:
        >>> manager = CredentialsManager()
        >>> manager.generate_all()
        >>> "postgres_password" in manager.credentials  # pragma: allowlist secret
        True
    """

    config: CredentialConfig = field(default_factory=CredentialConfig)
    credentials: dict[str, str] = field(default_factory=dict)
    on_credential_generated: Callable[[str, str], None] | None = None

    # Credential names and their descriptions (not actual secrets)
    CREDENTIAL_NAMES: dict[str, str] = field(  # pragma: allowlist secret
        default_factory=lambda: {
            "postgres_password": "PostgreSQL database password",  # pragma: allowlist secret
            "redis_password": "Redis cache password",  # pragma: allowlist secret
            "mqtt_password": "MQTT broker password",  # pragma: allowlist secret
            "api_key": "API key for external integrations",  # pragma: allowlist secret
        }
    )

    def generate_all(self) -> dict[str, str]:
        """Generate all required credentials.

        Generates fresh credentials for all required services:
        - PostgreSQL password
        - Redis password
        - MQTT password
        - API key

        Returns:
            Dictionary of credential name to value.
        """
        self.credentials["postgres_password"] = generate_password(
            length=self.config.postgres_password_length,
            include_special=self.config.include_special_chars,
        )
        self._notify_generated("postgres_password")

        self.credentials["redis_password"] = generate_password(
            length=self.config.redis_password_length,
            include_special=self.config.include_special_chars,
        )
        self._notify_generated("redis_password")

        self.credentials["mqtt_password"] = generate_password(
            length=self.config.mqtt_password_length,
            include_special=self.config.include_special_chars,
        )
        self._notify_generated("mqtt_password")

        self.credentials["api_key"] = generate_api_key(prefix=self.config.api_key_prefix)
        self._notify_generated("api_key")

        return self.credentials

    def _notify_generated(self, name: str) -> None:
        """Notify callback that a credential was generated (with redacted value)."""
        if self.on_credential_generated and name in self.credentials:
            redacted = redact_secret(self.credentials[name])
            self.on_credential_generated(name, redacted)

    def write_env_file(self, path: Path, mode: int = 0o600) -> bool:
        """Write credentials to a .env file with secure permissions.

        Creates or overwrites a .env file with all generated credentials.
        The file is written with 600 permissions (owner read/write only)
        to protect sensitive data.

        Args:
            path: Path to the .env file to write.
            mode: File permissions (default: 0o600 for owner-only access).

        Returns:
            True if file was written successfully, False otherwise.

        Raises:
            RuntimeError: If no credentials have been generated.
        """
        if not self.credentials:
            raise RuntimeError("No credentials generated. Call generate_all() first.")

        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Build .env content
            lines = [
                "# Auto-generated credentials - DO NOT COMMIT TO VERSION CONTROL",
                "# Generated by setup.py",
                "",
            ]

            # Add credentials with comments
            for name, value in self.credentials.items():
                description = self.CREDENTIAL_NAMES.get(name, name)
                lines.append(f"# {description}")

                # Map credential names to environment variable names
                env_name = self._credential_to_env_name(name)
                lines.append(f"{env_name}={value}")
                lines.append("")

            # Add database URL
            lines.append("# Database connection URL (auto-generated)")
            lines.append(f"DATABASE_URL={self.get_database_url()}")
            lines.append("")

            # Write file
            content = "\n".join(lines)
            path.write_text(content)

            # Set secure permissions
            path.chmod(mode)

            return True

        except (OSError, PermissionError) as e:
            print(f"! Failed to write .env file: {e}")
            return False

    def _credential_to_env_name(self, name: str) -> str:
        """Convert credential name to environment variable name."""
        mapping = {  # pragma: allowlist secret
            "postgres_password": "POSTGRES_PASSWORD",  # pragma: allowlist secret
            "redis_password": "REDIS_PASSWORD",  # pragma: allowlist secret
            "mqtt_password": "MQTT_PASSWORD",  # pragma: allowlist secret
            "api_key": "API_KEY",  # pragma: allowlist secret
        }
        return mapping.get(name, name.upper())

    def create_docker_secrets(self, secrets_dir: Path | None = None) -> bool:
        """Create Docker secrets by writing to files or using docker secret create.

        For Docker Swarm mode, uses 'docker secret create' with stdin.
        For Compose, writes to a secrets directory.

        Important: Secrets are passed via stdin, never as CLI arguments,
        to prevent exposure in process listings.

        Args:
            secrets_dir: Directory for secret files (Compose mode). If None,
                uses Docker Swarm secrets.

        Returns:
            True if all secrets were created successfully, False otherwise.

        Raises:
            RuntimeError: If no credentials have been generated.
        """
        if not self.credentials:
            raise RuntimeError("No credentials generated. Call generate_all() first.")

        if secrets_dir:
            return self._create_file_secrets(secrets_dir)
        return self._create_swarm_secrets()

    def _create_file_secrets(self, secrets_dir: Path) -> bool:
        """Create secrets as files in a directory (for Docker Compose)."""
        try:
            secrets_dir.mkdir(parents=True, exist_ok=True)

            for name, value in self.credentials.items():
                secret_file = secrets_dir / name
                secret_file.write_text(value)
                # Secure permissions
                secret_file.chmod(stat.S_IRUSR | stat.S_IWUSR)

            return True

        except (OSError, PermissionError) as e:
            print(f"! Failed to create secret files: {e}")
            return False

    def _create_swarm_secrets(self) -> bool:
        """Create Docker Swarm secrets using docker secret create."""
        for name, value in self.credentials.items():
            secret_name = f"hsi_{name}"

            try:
                # Check if secret already exists
                check_result = subprocess.run(
                    ["docker", "secret", "inspect", secret_name],  # noqa: S607
                    capture_output=True,
                    check=False,
                    timeout=10,
                )

                if check_result.returncode == 0:
                    # Secret exists, skip or update based on config
                    print(f"  Secret '{secret_name}' already exists, skipping")
                    continue

                # Create secret via stdin (never CLI argument)
                result = subprocess.run(
                    ["docker", "secret", "create", secret_name, "-"],  # noqa: S607
                    input=value.encode(),
                    capture_output=True,
                    check=True,
                    timeout=30,
                )

                if result.returncode != 0:
                    print(f"! Failed to create secret '{secret_name}'")
                    if result.stderr:
                        print(f"  Error: {result.stderr.decode().strip()}")
                    return False

            except subprocess.TimeoutExpired:
                print(f"! Timeout creating secret '{secret_name}'")
                return False
            except subprocess.SubprocessError as e:
                print(f"! Failed to create secret '{secret_name}': {e}")
                return False

        return True

    def rotate_credential(self, name: str) -> str | None:
        """Rotate a single credential by generating a new value.

        Generates a new value for the specified credential. The old value
        is discarded and cannot be recovered.

        Args:
            name: Name of the credential to rotate (e.g., 'postgres_password').

        Returns:
            New credential value, or None if rotation failed.

        Raises:
            ValueError: If the credential name is unknown.
        """
        if name not in self.CREDENTIAL_NAMES:
            raise ValueError(f"Unknown credential: {name}")

        if name == "api_key":
            new_value = generate_api_key(prefix=self.config.api_key_prefix)
        elif name == "postgres_password":
            new_value = generate_password(
                length=self.config.postgres_password_length,
                include_special=self.config.include_special_chars,
            )
        elif name == "redis_password":
            new_value = generate_password(
                length=self.config.redis_password_length,
                include_special=self.config.include_special_chars,
            )
        elif name == "mqtt_password":
            new_value = generate_password(
                length=self.config.mqtt_password_length,
                include_special=self.config.include_special_chars,
            )
        else:
            return None

        self.credentials[name] = new_value
        self._notify_generated(name)
        return new_value

    def get_database_url(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "home_security",
        user: str = "postgres",
    ) -> str:
        """Generate a properly encoded PostgreSQL database URL.

        Creates a database URL with the current PostgreSQL password,
        properly URL-encoding special characters.

        Args:
            host: Database host (default: localhost).
            port: Database port (default: 5432).
            database: Database name (default: home_security).
            user: Database user (default: postgres).

        Returns:
            PostgreSQL connection URL string.

        Raises:
            RuntimeError: If PostgreSQL password has not been generated.
        """
        password = self.credentials.get("postgres_password")
        if not password:
            raise RuntimeError("PostgreSQL password not generated. Call generate_all() first.")

        # URL-encode the password to handle special characters
        encoded_password = quote_plus(password)

        return f"postgresql://{user}:{encoded_password}@{host}:{port}/{database}"

    def get_credential(self, name: str) -> str | None:
        """Get a credential value by name.

        Args:
            name: Name of the credential.

        Returns:
            Credential value, or None if not found.
        """
        return self.credentials.get(name)

    def has_credential(self, name: str) -> bool:
        """Check if a credential exists.

        Args:
            name: Name of the credential.

        Returns:
            True if credential exists, False otherwise.
        """
        return name in self.credentials

    def clear_credentials(self) -> None:
        """Clear all stored credentials from memory.

        Should be called when credentials are no longer needed to
        minimize exposure in memory.
        """
        # Overwrite with empty strings before clearing
        for name in self.credentials:
            self.credentials[name] = ""
        self.credentials.clear()

    def load_from_env(self) -> bool:
        """Load existing credentials from environment variables.

        Useful for checking if credentials already exist or for
        loading credentials in a running application.

        Returns:
            True if at least one credential was loaded, False otherwise.
        """
        loaded = False
        env_mapping = {  # pragma: allowlist secret
            "POSTGRES_PASSWORD": "postgres_password",  # pragma: allowlist secret
            "REDIS_PASSWORD": "redis_password",  # pragma: allowlist secret
            "MQTT_PASSWORD": "mqtt_password",  # pragma: allowlist secret
            "API_KEY": "api_key",  # pragma: allowlist secret
        }

        for env_name, cred_name in env_mapping.items():
            value = os.environ.get(env_name)
            if value:
                self.credentials[cred_name] = value
                loaded = True

        return loaded


def prompt_and_generate_credentials(config: dict) -> dict[str, str]:
    """Prompt user and generate credentials interactively.

    Provides an interactive setup experience for credential generation,
    showing progress and allowing user confirmation.

    Args:
        config: Configuration dictionary. May contain:
            - 'credentials_mode': 'env' or 'docker' for output mode
            - 'env_file_path': Custom path for .env file

    Returns:
        Dictionary of generated credentials.
    """
    print()
    print("=" * 60)
    print("Credentials Generation")
    print("=" * 60)
    print()
    print("Generating secure credentials for all services...")
    print()

    # Check for existing .env file
    env_path = Path(config.get("env_file_path", ".env"))
    if env_path.exists():
        print(f"! Existing .env file found at {env_path}")
        answer = input("  Overwrite with new credentials? [n]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("  Keeping existing credentials")
            return {}

    # Create manager with callback for progress
    def on_generated(name: str, redacted: str) -> None:
        print(f"  + Generated {name}: {redacted}")

    manager = CredentialsManager()
    manager.on_credential_generated = on_generated

    # Generate all credentials
    credentials = manager.generate_all()

    print()
    print(f"+ Generated {len(credentials)} credentials")

    # Write to .env file
    print()
    print(f"Writing credentials to {env_path}...")

    if manager.write_env_file(env_path):
        print(f"+ Credentials written to {env_path}")
        print("  File permissions set to 600 (owner read/write only)")
    else:
        print("! Failed to write credentials file")

    # Offer Docker secrets mode
    if config.get("credentials_mode") == "docker":
        print()
        print("Creating Docker secrets...")
        secrets_dir = Path(config.get("secrets_dir", "./secrets"))
        if manager.create_docker_secrets(secrets_dir):
            print(f"+ Docker secrets created in {secrets_dir}")
        else:
            print("! Failed to create Docker secrets")

    print()
    print("Important: Keep these credentials secure!")
    print("  - Do not commit .env to version control")
    print("  - Back up credentials securely")
    print("  - Rotate credentials periodically")

    return credentials


if __name__ == "__main__":
    # Allow testing the module directly
    prompt_and_generate_credentials({})
