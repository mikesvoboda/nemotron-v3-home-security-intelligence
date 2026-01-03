#!/usr/bin/env python3
"""Interactive setup script for Home Security Intelligence.

Generates .env and docker-compose.override.yml files for user environment.
Supports two modes:
- Quick mode (default): Accept defaults with Enter
- Guided mode (--guided): Step-by-step with explanations

Security features:
- Generates cryptographically secure random passwords
- Creates secrets directory with proper permissions
- Warns about weak/default passwords
"""

import argparse
import platform
import secrets
import shutil
import socket
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict


class ServiceInfo(TypedDict):
    """Type definition for service configuration."""

    port: int
    category: str
    desc: str


# Service definitions with default ports
SERVICES: dict[str, ServiceInfo] = {
    "backend": {"port": 8000, "category": "Core", "desc": "Backend API"},
    "frontend": {"port": 5173, "category": "Core", "desc": "Frontend web UI"},
    "postgres": {"port": 5432, "category": "Core", "desc": "PostgreSQL database"},
    "redis": {"port": 6379, "category": "Core", "desc": "Redis cache/queue"},
    "rtdetr": {"port": 8090, "category": "AI", "desc": "RT-DETRv2 object detection"},
    "nemotron": {"port": 8091, "category": "AI", "desc": "Nemotron LLM reasoning"},
    "florence": {"port": 8092, "category": "AI", "desc": "Florence-2 vision-language"},
    "clip": {"port": 8093, "category": "AI", "desc": "CLIP embeddings"},
    "enrichment": {"port": 8094, "category": "AI", "desc": "Entity enrichment"},
    "grafana": {"port": 3002, "category": "Monitoring", "desc": "Grafana dashboards"},
    "prometheus": {"port": 9090, "category": "Monitoring", "desc": "Prometheus metrics"},
    "alertmanager": {"port": 3000, "category": "Monitoring", "desc": "Alert manager"},
    "redis_exporter": {"port": 9121, "category": "Monitoring", "desc": "Redis exporter"},
    "json_exporter": {"port": 7979, "category": "Monitoring", "desc": "JSON exporter"},
}


def check_port_available(port: int) -> bool:
    """Check if a port is available for binding.

    Args:
        port: Port number to check

    Returns:
        True if port is available, False if in use
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0


def find_available_port(start: int) -> int:
    """Find the next available port starting from a given port.

    Args:
        start: Starting port number

    Returns:
        First available port >= start
    """
    port = start
    while not check_port_available(port):
        port += 1
        if port > 65535:
            raise RuntimeError(f"No available ports found starting from {start}")
    return port


def prompt_with_default(prompt: str, default: str) -> str:
    """Prompt user for input with a default value.

    Args:
        prompt: Prompt text to display
        default: Default value if user presses Enter

    Returns:
        User input or default value
    """
    try:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def generate_password(length: int = 32) -> str:
    """Generate a secure random password.

    Args:
        length: Desired password length (default: 32 for security)

    Returns:
        URL-safe random string of specified length
    """
    return secrets.token_urlsafe(length)[:length]


# Known weak/default passwords to warn about
WEAK_PASSWORDS = {
    "security_dev_password",
    "password",
    "postgres",
    "admin",
    "root",
    "123456",
    "changeme",
    "secret",
}


def is_weak_password(password: str) -> bool:
    """Check if a password is considered weak.

    Args:
        password: Password to check

    Returns:
        True if password is weak, False otherwise
    """
    if len(password) < 16:
        return True
    return password.lower() in WEAK_PASSWORDS


def prompt_for_password(prompt_text: str, default: str | None = None) -> str:
    """Prompt for a password with weak password warning.

    Args:
        prompt_text: Text to display when prompting
        default: Default password (auto-generated if None)

    Returns:
        The password entered by the user
    """
    if default is None:
        default = generate_password(32)

    password = prompt_with_default(prompt_text, default)

    # Warn and re-prompt if weak
    if is_weak_password(password):
        print()
        print("! WARNING: This password appears weak!")
        print("  - Minimum recommended length: 16 characters")
        print("  - Avoid common words like 'password', 'admin', 'secret'")
        print()
        confirm = prompt_with_default("Use this weak password anyway?", "n")
        if confirm.lower() not in ("y", "yes"):
            print()
            password = prompt_with_default(prompt_text, generate_password(32))

    return password


def create_secrets_directory(output_dir: str = ".") -> Path:
    """Create the secrets directory with proper permissions.

    Args:
        output_dir: Base directory for secrets folder

    Returns:
        Path to the secrets directory
    """
    secrets_dir = Path(output_dir) / "secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)

    # Set directory permissions to 700 (owner only)
    if platform.system() != "Windows":
        secrets_dir.chmod(stat.S_IRWXU)

    return secrets_dir


def write_secret_file(secrets_dir: Path, filename: str, content: str) -> Path:
    """Write a secret to a file with secure permissions.

    Args:
        secrets_dir: Directory to write the secret file
        filename: Name of the secret file
        content: Secret content to write

    Returns:
        Path to the created secret file
    """
    secret_path = secrets_dir / filename
    secret_path.write_text(content)

    # Set file permissions to 600 (owner read/write only)
    if platform.system() != "Windows":
        secret_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    return secret_path


def generate_env_content(config: dict) -> str:
    """Generate .env file content from configuration.

    Args:
        config: Dictionary containing camera_path, ai_models_path,
                postgres_password, ftp_password, and ports dict

    Returns:
        String content for .env file
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ports = config.get("ports", {})

    lines = [
        f"# Generated by setup.py on {timestamp}",
        "# " + "=" * 59,
        "",
        "# -- Paths " + "-" * 50,
        f"CAMERA_PATH={config.get('camera_path', '/export/foscam')}",
        f"AI_MODELS_PATH={config.get('ai_models_path', '/export/ai_models')}",
        "",
        "# -- Credentials " + "-" * 44,
        f"POSTGRES_PASSWORD={config.get('postgres_password', '')}",
        f"FTP_PASSWORD={config.get('ftp_password', '')}",
        "",
        "# -- Database " + "-" * 47,
        "POSTGRES_USER=security",
        "POSTGRES_DB=security",
        f"DATABASE_URL=postgresql+asyncpg://security:{config.get('postgres_password', '')}@postgres:{ports.get('postgres', 5432)}/security",
        "",
        "# -- Service URLs " + "-" * 43,
        f"RTDETR_URL=http://ai-detector:{ports.get('rtdetr', 8090)}",
        f"NEMOTRON_URL=http://ai-llm:{ports.get('nemotron', 8091)}",
        f"FLORENCE_URL=http://ai-florence:{ports.get('florence', 8092)}",
        f"CLIP_URL=http://ai-clip:{ports.get('clip', 8093)}",
        f"ENRICHMENT_URL=http://ai-enrichment:{ports.get('enrichment', 8094)}",
        f"REDIS_URL=redis://redis:{ports.get('redis', 6379)}",
        "",
        "# -- Frontend Runtime Config " + "-" * 32,
        f"GRAFANA_URL=http://localhost:{ports.get('grafana', 3002)}",
        "",
    ]
    return "\n".join(lines)


def generate_docker_override_content(config: dict) -> str:
    """Generate docker-compose.override.yml content.

    Args:
        config: Dictionary containing camera_path, ai_models_path, and ports dict

    Returns:
        String content for docker-compose.override.yml file
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ports = config.get("ports", {})
    camera_path = config.get("camera_path", "/export/foscam")

    lines = [
        f"# Generated by setup.py on {timestamp}",
        "# This file is auto-merged with docker-compose.prod.yml",
        "",
        "services:",
    ]

    service_configs = {
        "postgres": {"port": ports.get("postgres", 5432), "internal": 5432},
        "redis": {"port": ports.get("redis", 6379), "internal": 6379},
        "backend": {
            "port": ports.get("backend", 8000),
            "internal": 8000,
            "volumes": [f"{camera_path}:/cameras:ro"],
        },
        "ai-detector": {"port": ports.get("rtdetr", 8090), "internal": 8090},
        "ai-llm": {"port": ports.get("nemotron", 8091), "internal": 8091},
        "ai-florence": {"port": ports.get("florence", 8092), "internal": 8092},
        "ai-clip": {"port": ports.get("clip", 8093), "internal": 8093},
        "ai-enrichment": {"port": ports.get("enrichment", 8094), "internal": 8094},
        "frontend": {"port": ports.get("frontend", 5173), "internal": 80},
        "grafana": {"port": ports.get("grafana", 3002), "internal": 3000},
        "prometheus": {"port": ports.get("prometheus", 9090), "internal": 9090},
        "alertmanager": {"port": ports.get("alertmanager", 3000), "internal": 9093},
        "redis-exporter": {"port": ports.get("redis_exporter", 9121), "internal": 9121},
        "json-exporter": {"port": ports.get("json_exporter", 7979), "internal": 7979},
    }

    for service, cfg in service_configs.items():
        lines.append(f"  {service}:")
        lines.append("    ports:")
        lines.append(f'      - "{cfg["port"]}:{cfg["internal"]}"')
        if "volumes" in cfg:
            lines.append("    volumes:")
            for vol in cfg["volumes"]:
                lines.append(f"      - {vol}")
        lines.append("")

    return "\n".join(lines)


def run_quick_mode() -> dict:
    """Run quick setup mode with minimal prompts.

    Returns:
        Configuration dictionary
    """
    print("=" * 60)
    print("  Home Security Intelligence - Quick Setup")
    print("=" * 60)
    print()

    # Check port conflicts
    print("Checking for port conflicts...")
    conflicts = []
    ports = {}
    for service, info in SERVICES.items():
        default_port = info["port"]
        if check_port_available(default_port):
            ports[service] = default_port
        else:
            available = find_available_port(default_port)
            ports[service] = available
            conflicts.append(f"  {service}: {default_port} -> {available}")

    if conflicts:
        print("! Port conflicts detected, using alternatives:")
        for c in conflicts:
            print(c)
    else:
        print("* All default ports available")
    print()

    # Paths
    print("-- Paths " + "-" * 52)
    camera_path = prompt_with_default("Camera upload path", "/export/foscam")
    ai_models_path = prompt_with_default("AI models path", "/export/ai_models")
    print()

    # Credentials
    print("-- Credentials " + "-" * 46)
    print("! SECURITY: Strong passwords are required for database access")
    postgres_password = prompt_for_password("Database password")
    ftp_password = prompt_with_default("FTP password", generate_password(32))
    print()

    # Ports (optional customization)
    print("-- Ports (press Enter to keep defaults) " + "-" * 21)
    for service, info in SERVICES.items():
        suggested = ports[service]
        custom = prompt_with_default(f"{info['desc']}", str(suggested))
        try:
            ports[service] = int(custom)
        except ValueError:
            ports[service] = suggested
    print()

    return {
        "camera_path": camera_path,
        "ai_models_path": ai_models_path,
        "postgres_password": postgres_password,
        "ftp_password": ftp_password,
        "ports": ports,
    }


def run_guided_mode() -> dict:
    """Run guided setup mode with detailed explanations.

    Returns:
        Configuration dictionary
    """
    ports = {service: info["port"] for service, info in SERVICES.items()}

    # Step 1: Camera Path
    print("=" * 60)
    print("  Step 1 of 5: Camera Upload Path")
    print("=" * 60)
    print()
    print("This is where your Foscam cameras upload images via FTP.")
    print("The backend watches this directory for new files.")
    print()
    print("Requirements:")
    print("  * Must exist and be readable by Docker")
    print("  * Recommended: SSD or fast storage for real-time processing")
    print("  * Typical size: 10-50GB depending on camera count/retention")
    print()
    camera_path = prompt_with_default("Enter camera upload path", "/export/foscam")

    # Validate path exists
    if Path(camera_path).exists():
        print("+ Directory exists and is readable")
    else:
        print(f"! Directory does not exist: {camera_path}")
        create = prompt_with_default("Create it now?", "n")
        if create.lower() in ("y", "yes"):
            try:
                Path(camera_path).mkdir(parents=True, exist_ok=True)
                print("+ Directory created")
            except PermissionError:
                print("! Permission denied - you may need to create it manually")
    print()

    # Step 2: AI Models Path
    print("=" * 60)
    print("  Step 2 of 5: AI Models Path")
    print("=" * 60)
    print()
    print("This is where AI model weights are stored.")
    print("The AI services load models from this directory.")
    print()
    print("Requirements:")
    print("  * Requires ~15GB of disk space for all models")
    print("  * Must be readable by Docker containers")
    print()
    ai_models_path = prompt_with_default("Enter AI models path", "/export/ai_models")

    # Check disk space
    try:
        _total, _used, free = shutil.disk_usage(Path(ai_models_path).parent)
        free_gb = free / (1024**3)
        if free_gb < 15:
            print(f"! Warning: Only {free_gb:.1f}GB free space (15GB recommended)")
        else:
            print(f"+ {free_gb:.1f}GB free space available")
    except OSError:
        # Path doesn't exist yet or isn't accessible - that's OK
        pass
    print()

    # Step 3: Credentials
    print("=" * 60)
    print("  Step 3 of 5: Security Credentials")
    print("=" * 60)
    print()
    print("IMPORTANT: Database credentials are REQUIRED for the system to start.")
    print("Strong 32-character passwords will be auto-generated if you press Enter.")
    print()
    print("! The old default password 'security_dev_password' has been removed")
    print("  for security reasons. You MUST set a password.")
    print()
    postgres_password = prompt_for_password("Database password")
    ftp_password = prompt_with_default("FTP password", generate_password(32))
    print()

    # Step 4: Port Configuration
    print("=" * 60)
    print("  Step 4 of 5: Port Configuration")
    print("=" * 60)
    print()
    print("Checking for port conflicts...")

    for service, info in SERVICES.items():
        default_port = info["port"]
        if not check_port_available(default_port):
            available = find_available_port(default_port)
            print(f"! {info['desc']} ({service}): port {default_port} in use")
            ports[service] = int(prompt_with_default("  Alternative port", str(available)))
        else:
            print(f"+ {info['desc']}: {default_port}")
            ports[service] = default_port
    print()

    # Step 5: Summary
    print("=" * 60)
    print("  Step 5 of 5: Configuration Summary")
    print("=" * 60)
    print()
    print(f"Camera Path:    {camera_path}")
    print(f"AI Models Path: {ai_models_path}")
    print(f"Database Port:  {ports['postgres']}")
    print(f"Frontend Port:  {ports['frontend']}")
    print(f"Grafana Port:   {ports['grafana']}")
    print()
    confirm = prompt_with_default("Proceed with this configuration?", "y")
    if confirm.lower() not in ("y", "yes"):
        print("Setup cancelled.")
        sys.exit(0)

    return {
        "camera_path": camera_path,
        "ai_models_path": ai_models_path,
        "postgres_password": postgres_password,
        "ftp_password": ftp_password,
        "ports": ports,
    }


def write_config_files(
    config: dict[str, Any], output_dir: str = ".", create_secret_files: bool = False
) -> tuple[Path, Path, Path | None]:
    """Write configuration files to disk.

    Args:
        config: Configuration dictionary
        output_dir: Directory to write files to
        create_secret_files: If True, also create Docker secrets files

    Returns:
        Tuple of (env_path, override_path, secrets_path or None)
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    env_path = output / ".env"
    override_path = output / "docker-compose.override.yml"

    env_content = generate_env_content(config)
    override_content = generate_docker_override_content(config)

    env_path.write_text(env_content)
    override_path.write_text(override_content)

    # Set .env file permissions to 600 (owner read/write only)
    if platform.system() != "Windows":
        env_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    # Optionally create Docker secrets files
    secrets_path = None
    if create_secret_files:
        secrets_dir = create_secrets_directory(output_dir)
        postgres_password = config.get("postgres_password", "")
        if postgres_password:
            secrets_path = write_secret_file(
                secrets_dir, "postgres_password.txt", postgres_password
            )

    return env_path, override_path, secrets_path


def configure_firewall(ports: list[int]) -> bool:
    """Configure Linux firewall to allow specified ports.

    Args:
        ports: List of port numbers to open

    Returns:
        True if successful, False otherwise
    """
    if platform.system() != "Linux":
        return False

    # Try firewall-cmd (Fedora/RHEL/CentOS)
    if shutil.which("firewall-cmd"):
        try:
            for port in ports:
                subprocess.run(  # noqa: S603 - firewall config requires subprocess
                    ["firewall-cmd", "--permanent", f"--add-port={port}/tcp"],  # noqa: S607
                    check=True,
                    capture_output=True,
                )
            subprocess.run(
                ["firewall-cmd", "--reload"],  # noqa: S607
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    # Try ufw (Ubuntu/Debian)
    if shutil.which("ufw"):
        try:
            for port in ports:
                subprocess.run(  # noqa: S603 - firewall config requires subprocess
                    ["ufw", "allow", f"{port}/tcp"],  # noqa: S607
                    check=True,
                    capture_output=True,
                )
            return True
        except subprocess.CalledProcessError:
            return False

    return False


def main() -> None:
    """Main entry point for setup script."""
    parser = argparse.ArgumentParser(description="Interactive setup for Home Security Intelligence")
    parser.add_argument(
        "--guided",
        action="store_true",
        help="Run in guided mode with detailed explanations",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Output directory for generated files (default: current directory)",
    )
    parser.add_argument(
        "--create-secrets",
        action="store_true",
        help="Also create Docker secrets files in secrets/ directory",
    )
    args = parser.parse_args()

    try:
        config = run_guided_mode() if args.guided else run_quick_mode()

        # Write configuration files
        env_path, override_path, secrets_path = write_config_files(
            config, args.output_dir, create_secret_files=args.create_secrets
        )

        # Install pre-commit hooks after config files written
        print("\n" + "=" * 60)
        print("Installing pre-commit hooks...")
        print("=" * 60)

        try:
            # Install pre-commit hook (linting/formatting)
            subprocess.run(
                ["pre-commit", "install"],  # noqa: S607
                check=True,
                capture_output=True,
            )
            print("+ Pre-commit hook installed")

            # Install pre-push hook (unit tests)
            subprocess.run(
                ["pre-commit", "install", "--hook-type", "pre-push"],  # noqa: S607
                check=True,
                capture_output=True,
            )
            print("+ Pre-push hook installed (unit tests run before push)")
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("! Could not install pre-commit hooks")
            print("  Install manually with:")
            print("    pre-commit install")
            print("    pre-commit install --hook-type pre-push")

        print("=" * 60)
        print("Generated:")
        print(f"  - {env_path}")
        print(f"  - {override_path}")
        if secrets_path:
            print(f"  - {secrets_path}")
        print()

        # Security reminder
        print("! SECURITY NOTES:")
        print("  - .env file permissions set to 600 (owner only)")
        print("  - POSTGRES_PASSWORD is required - containers will fail without it")
        print("  - Never commit .env or secrets/ to version control")
        if secrets_path:
            print("  - Docker secrets file created with secure permissions (600)")
            print("  - To use secrets, uncomment the secrets sections in docker-compose.prod.yml")
        print()

        # Offer firewall configuration on Linux
        if platform.system() == "Linux":
            frontend_port = config["ports"].get("frontend", 5173)
            grafana_port = config["ports"].get("grafana", 3002)

            answer = prompt_with_default(
                f"Open firewall ports for frontend ({frontend_port}) and Grafana ({grafana_port})?",
                "n",
            )
            if answer.lower() in ("y", "yes"):
                if configure_firewall([frontend_port, grafana_port]):
                    print("Firewall configured")
                else:
                    print("Could not configure firewall (may need sudo)")

        print()
        print("Ready! Run: docker compose -f docker-compose.prod.yml up -d")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(1)


if __name__ == "__main__":
    main()
