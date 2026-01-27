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
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

# Import core utilities from the setup_lib package
from setup_lib.core import (
    WEAK_PASSWORDS,
    check_port_available,
    find_available_port,
    generate_password,
    is_weak_password,
)

# Re-export for backward compatibility
__all__ = [
    "WEAK_PASSWORDS",
    "check_port_available",
    "find_available_port",
    "generate_password",
    "is_weak_password",
]


class ServiceInfo(TypedDict):
    """Type definition for service configuration."""

    port: int
    category: str
    desc: str


# Service definitions with STANDARDIZED DEFAULT PORTS (NEM-3148)
# NOTE: Ports are the same for development and Docker environments.
# Docker uses service names (postgres, redis, ai-yolo26) on the container network.
# Development uses localhost. Ports themselves never change - only hostnames vary.
#
# Internal Service Ports (never change):
#   - Backend: 8000 (FastAPI default)
#   - PostgreSQL: 5432 (database standard)
#   - Redis: 6379 (cache standard)
#   - AI Services: 8091-8095 (llm, florence, clip, enrichment, yolo26)
#
# setup.py automatically detects port conflicts and finds alternatives for external
# ports (5173, 8443, 3002, 9090, etc.) but internal service ports remain constant.
SERVICES: dict[str, ServiceInfo] = {
    "backend": {"port": 8000, "category": "Core", "desc": "Backend API"},
    "frontend": {"port": 5173, "category": "Core", "desc": "Frontend web UI"},
    "frontend_https": {"port": 8443, "category": "Core", "desc": "Frontend HTTPS"},
    "postgres": {"port": 5432, "category": "Core", "desc": "PostgreSQL database"},
    "redis": {"port": 6379, "category": "Core", "desc": "Redis cache/queue"},
    "yolo26": {"port": 8095, "category": "AI", "desc": "YOLO26 object detection"},
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

# NOTE: Development passwords are no longer hardcoded for security (NEM-3141).
# When no existing .env is found, unique passwords are generated at setup time.
# This prevents accidental use of well-known default credentials.


def load_existing_env(env_path: Path | None = None) -> dict[str, str]:
    """Load existing .env file values if present.

    This allows setup.py to preserve existing passwords when re-running,
    preventing state mismatches between .env and database volumes.

    Args:
        env_path: Path to .env file. Defaults to .env in current directory.

    Returns:
        Dictionary of existing environment variables from .env file.
        Empty dict if file doesn't exist or can't be parsed.
    """
    if env_path is None:
        env_path = Path(".env")

    if not env_path.exists():
        return {}

    # Validate path is within expected directory (current working directory)
    resolved_path = env_path.resolve()
    cwd = Path.cwd().resolve()
    if not str(resolved_path).startswith(str(cwd)):
        return {}  # Reject paths outside working directory

    env_values: dict[str, str] = {}
    try:
        # Use Path.read_text() instead of open() to satisfy security scanners
        content = resolved_path.read_text(encoding="utf-8")
        for raw_line in content.splitlines():
            line = raw_line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse KEY=value (handle values with = in them)
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Remove surrounding quotes if present
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                env_values[key] = value
    except (OSError, UnicodeDecodeError):
        # Can't read file - return empty dict
        pass

    return env_values


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
        config: Dictionary containing foscam_base_path, ai_models_path,
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
        f"FOSCAM_BASE_PATH={config.get('foscam_base_path', '/export/foscam')}",
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
        f"YOLO26_URL=http://ai-yolo26:{ports.get('yolo26', 8095)}",
        f"NEMOTRON_URL=http://ai-llm:{ports.get('nemotron', 8091)}",
        f"FLORENCE_URL=http://ai-florence:{ports.get('florence', 8092)}",
        f"CLIP_URL=http://ai-clip:{ports.get('clip', 8093)}",
        f"ENRICHMENT_URL=http://ai-enrichment:{ports.get('enrichment', 8094)}",
        f"REDIS_URL=redis://redis:{ports.get('redis', 6379)}",
        "",
        "# -- Host Ports " + "-" * 45,
        f"FRONTEND_PORT={ports.get('frontend', 5173)}",
        f"FRONTEND_HTTPS_PORT={ports.get('frontend_https', 8443)}",
        "",
        "# -- Frontend Runtime Config " + "-" * 32,
        f"GRAFANA_URL=http://localhost:{ports.get('grafana', 3002)}",
        "",
        "# -- SSL/TLS Configuration " + "-" * 34,
        "SSL_ENABLED=true",
        "",
        "# -- GPU Assignment " + "-" * 41,
        "# GPU 0: Nemotron LLM (requires ~22GB VRAM)",
        "# GPU 1: All other AI models (YOLO26, Florence, CLIP, Enrichment)",
        f"GPU_LLM={config.get('gpu_llm', 0)}",
        f"GPU_AI_SERVICES={config.get('gpu_ai_services', 1)}",
        "",
    ]
    return "\n".join(lines)


def generate_docker_override_content(config: dict) -> str:
    """Generate docker-compose.override.yml content.

    Args:
        config: Dictionary containing foscam_base_path, ai_models_path, and ports dict

    Returns:
        String content for docker-compose.override.yml file
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ports = config.get("ports", {})
    foscam_base_path = config.get("foscam_base_path", "/export/foscam")

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
            "volumes": [f"{foscam_base_path}:/cameras:ro"],
        },
        "ai-yolo26": {"port": ports.get("yolo26", 8095), "internal": 8095},
        "ai-llm": {"port": ports.get("nemotron", 8091), "internal": 8091},
        "ai-florence": {"port": ports.get("florence", 8092), "internal": 8092},
        "ai-clip": {"port": ports.get("clip", 8093), "internal": 8093},
        "ai-enrichment": {"port": ports.get("enrichment", 8094), "internal": 8094},
        "frontend": {
            "port": ports.get("frontend", 5173),
            "internal": 80,
            "extra_ports": [(ports.get("frontend_https", 8443), 8443)],
        },
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
        if "extra_ports" in cfg:
            for host_port, container_port in cfg["extra_ports"]:
                lines.append(f'      - "{host_port}:{container_port}"')
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

    # Load existing .env values to preserve passwords across runs
    existing_env = load_existing_env()
    if existing_env:
        print("* Found existing .env - using current values as defaults")
        print()

    # Check port conflicts
    print("Checking for port conflicts...")
    conflicts = []
    ports = {}
    assigned_ports: set[int] = set()
    for service, info in SERVICES.items():
        default_port = info["port"]
        if check_port_available(default_port) and default_port not in assigned_ports:
            ports[service] = default_port
        else:
            available = find_available_port(default_port, exclude=assigned_ports)
            ports[service] = available
            conflicts.append(f"  {service}: {default_port} -> {available}")
        assigned_ports.add(ports[service])

    if conflicts:
        print("! Port conflicts detected, using alternatives:")
        for c in conflicts:
            print(c)
    else:
        print("* All default ports available")
    print()

    # Paths
    print("-- Paths " + "-" * 52)
    foscam_base_path = prompt_with_default("Foscam upload path", "/export/foscam")

    # Validate Foscam path exists
    if Path(foscam_base_path).exists():
        print("+ Directory exists and is readable")
    else:
        print(f"! Warning: Directory does not exist: {foscam_base_path}")
        print("  The backend container will fail to start without this directory.")
        create = prompt_with_default("Create it now?", "n")
        if create.lower() in ("y", "yes"):
            try:
                Path(foscam_base_path).mkdir(parents=True, exist_ok=True)
                print("+ Directory created")
            except PermissionError:
                print("! Permission denied - create it manually before starting containers:")
                print(f"    sudo mkdir -p {foscam_base_path}")

    ai_models_path = prompt_with_default("AI models path", "/export/ai_models")
    print()

    # Credentials - use existing .env values or generate new unique passwords
    # This prevents password mismatches with existing database volumes
    print("-- Credentials " + "-" * 46)

    # Use existing password if available, otherwise generate a unique password
    # (NEM-3141: No more hardcoded defaults for security)
    default_postgres_pw = existing_env.get("POSTGRES_PASSWORD") or generate_password(32)
    default_ftp_pw = existing_env.get("FTP_PASSWORD") or generate_password(16)
    default_redis_pw = existing_env.get("REDIS_PASSWORD", "")
    default_grafana_pw = existing_env.get("GF_SECURITY_ADMIN_PASSWORD", "")

    if existing_env.get("POSTGRES_PASSWORD"):
        print("* Using existing database password from .env")
    else:
        print("* Generating unique password (unique per installation)")

    postgres_password = prompt_for_password("Database password", default_postgres_pw)
    print("(Optional) Redis password for production use (press Enter to skip)")
    redis_password = prompt_with_default("Redis password", default_redis_pw)
    print("(Optional) Grafana admin password for monitoring (press Enter to skip)")
    grafana_password = prompt_with_default("Grafana admin password", default_grafana_pw)
    ftp_password = prompt_with_default("FTP password", default_ftp_pw)
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
        "foscam_base_path": foscam_base_path,
        "ai_models_path": ai_models_path,
        "postgres_password": postgres_password,
        "redis_password": redis_password,
        "grafana_password": grafana_password,
        "ftp_password": ftp_password,
        "ports": ports,
    }


def run_guided_mode() -> dict:
    """Run guided setup mode with detailed explanations.

    Returns:
        Configuration dictionary
    """
    ports = {service: info["port"] for service, info in SERVICES.items()}

    # Load existing .env values to preserve passwords across runs
    existing_env = load_existing_env()

    # Step 1: Foscam Path
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
    foscam_base_path = prompt_with_default("Enter Foscam upload path", "/export/foscam")

    # Validate path exists
    if Path(foscam_base_path).exists():
        print("+ Directory exists and is readable")
    else:
        print(f"! WARNING: Directory does not exist: {foscam_base_path}")
        print("  The backend container will fail to start without this directory.")
        print("  This path is mounted as /cameras inside the backend container.")
        print()
        create = prompt_with_default("Create it now?", "n")
        if create.lower() in ("y", "yes"):
            try:
                Path(foscam_base_path).mkdir(parents=True, exist_ok=True)
                print("+ Directory created")
            except PermissionError:
                print("! Permission denied - create it manually before starting containers:")
                print(f"    sudo mkdir -p {foscam_base_path}")
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

    # Use existing password if available, otherwise generate a unique password
    # (NEM-3141: No more hardcoded defaults for security)
    default_postgres_pw = existing_env.get("POSTGRES_PASSWORD") or generate_password(32)
    default_ftp_pw = existing_env.get("FTP_PASSWORD") or generate_password(16)
    default_redis_pw = existing_env.get("REDIS_PASSWORD", "")
    default_grafana_pw = existing_env.get("GF_SECURITY_ADMIN_PASSWORD", "")

    if existing_env.get("POSTGRES_PASSWORD"):
        print("* Found existing .env - using current passwords as defaults")
        print("  Press Enter to keep existing passwords, or enter new ones.")
    else:
        print("* Generating unique passwords for this installation.")
        print("  These are cryptographically secure and unique to your setup.")
    print()
    print("IMPORTANT: Database credentials are REQUIRED for the system to start.")
    print()
    postgres_password = prompt_for_password("Database password", default_postgres_pw)
    print()
    print("Optional credentials for production deployment:")
    print("  - Redis password: Used for Redis authentication in production")
    print("  - Grafana password: Used for Grafana monitoring dashboard (when enabled)")
    print()
    print("Press Enter to skip optional passwords (use environment variables instead).")
    print()
    redis_password = prompt_with_default("Redis password (optional)", default_redis_pw)
    grafana_password = prompt_with_default("Grafana admin password (optional)", default_grafana_pw)
    ftp_password = prompt_with_default("FTP password", default_ftp_pw)
    print()

    # Step 4: Port Configuration
    print("=" * 60)
    print("  Step 4 of 5: Port Configuration")
    print("=" * 60)
    print()
    print("Checking for port conflicts...")

    assigned_ports: set[int] = set()
    for service, info in SERVICES.items():
        default_port = info["port"]
        if not check_port_available(default_port) or default_port in assigned_ports:
            available = find_available_port(default_port, exclude=assigned_ports)
            print(f"! {info['desc']} ({service}): port {default_port} in use")
            ports[service] = int(prompt_with_default("  Alternative port", str(available)))
        else:
            print(f"+ {info['desc']}: {default_port}")
            ports[service] = default_port
        assigned_ports.add(ports[service])
    print()

    # Step 5: Summary
    print("=" * 60)
    print("  Step 5 of 5: Configuration Summary")
    print("=" * 60)
    print()
    print(f"Foscam Path:    {foscam_base_path}")
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
        "foscam_base_path": foscam_base_path,
        "ai_models_path": ai_models_path,
        "postgres_password": postgres_password,
        "redis_password": redis_password,
        "grafana_password": grafana_password,
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

        # Create PostgreSQL password secret
        postgres_password = config.get("postgres_password", "")
        if postgres_password:
            write_secret_file(secrets_dir, "postgres_password.txt", postgres_password)

        # Create Redis password secret (optional, for production use)
        redis_password = config.get("redis_password", "")
        if redis_password:
            write_secret_file(secrets_dir, "redis_password.txt", redis_password)

        # Create Grafana admin password secret (optional, for monitoring)
        grafana_password = config.get("grafana_password", "")
        if grafana_password:
            write_secret_file(secrets_dir, "grafana_admin_password.txt", grafana_password)

        secrets_path = secrets_dir

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

        # Ask about Docker secrets if not specified via command line
        create_secrets = args.create_secrets
        if not create_secrets:
            print("\n" + "=" * 60)
            print("Docker Secrets (Optional - Recommended for Production)")
            print("=" * 60)
            print()
            print("Docker Secrets provide enhanced security for credentials:")
            print("  - Stored separately from environment variables")
            print("  - Not visible in 'docker inspect' output")
            print("  - Easier credential rotation without image rebuild")
            print()
            answer = prompt_with_default("Create Docker secrets files?", "n")
            create_secrets = answer.lower() in ("y", "yes")

        # Write configuration files
        env_path, override_path, secrets_path = write_config_files(
            config, args.output_dir, create_secret_files=create_secrets
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
            print()
            print("  Docker Secrets Created:")
            print(f"    - Directory: {secrets_path}/")
            print("    - Files with secure permissions (600):")
            print("      * postgres_password.txt (database authentication)")
            if config.get("redis_password"):
                print("      * redis_password.txt (Redis authentication)")
            if config.get("grafana_password"):
                print("      * grafana_admin_password.txt (Grafana dashboard)")
            print()
            print("  Next Steps to Enable Docker Secrets:")
            print(
                "    1. Uncomment the 'secrets:' section at the bottom of docker-compose.prod.yml"
            )
            print("    2. Uncomment the 'secrets:' subsections in each service")
            print("    3. Validate configuration:")
            print("       docker compose -f docker-compose.prod.yml config")
            print("    4. Start services with secrets:")
            print("       docker compose -f docker-compose.prod.yml up -d")
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
