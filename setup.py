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
from setup_lib.firewall_config import prompt_and_configure_firewall
from setup_lib.image_pull import prompt_and_pull_images
from setup_lib.linux_optimizer import prompt_and_run_optimizations
from setup_lib.model_downloader import prompt_and_download_models
from setup_lib.nvidia_detect import fix_broken_apt_if_needed, prompt_and_check_nvidia
from setup_lib.platform_detect import get_platform_info, print_platform_info
from setup_lib.podman_install import prompt_and_install_podman
from setup_lib.rootful_services import (
    prompt_and_install_dcgm_service,
    prompt_and_install_rootful_services,
)
from setup_lib.ssl_certs import prompt_and_generate_certificates
from setup_lib.storage_config import prompt_and_configure_storage

# Re-export for backward compatibility
__all__ = [
    "WEAK_PASSWORDS",
    "check_port_available",
    "find_available_port",
    "generate_jwt_secret",
    "generate_password",
    "is_weak_password",
]


def generate_jwt_secret() -> str:
    """Generate a cryptographically secure JWT secret.

    Generates a 64-byte (128-character hex) random secret suitable for
    JWT signing. This provides strong security for token authentication.

    Returns:
        128-character hexadecimal string (64 bytes of entropy)
    """
    return secrets.token_hex(64)


class ServiceInfo(TypedDict):
    """Type definition for service configuration."""

    port: int
    category: str
    desc: str


def load_ports_from_env_example(env_example_path: Path | None = None) -> dict[str, int]:
    """Load port defaults from .env.example file.

    .env.example is the single source of truth for all port configurations.
    This function parses it to extract port values for use in setup and deployment.

    Args:
        env_example_path: Path to .env.example file. Defaults to .env.example in cwd.

    Returns:
        Dictionary mapping port variable names to their integer values.
        Example: {"POSTGRES_PORT": 5432, "REDIS_PORT": 6379, ...}
    """
    if env_example_path is None:
        env_example_path = Path(".env.example")

    if not env_example_path.exists():
        # Return empty dict if file doesn't exist - will use hardcoded fallbacks
        return {}

    ports: dict[str, int] = {}
    try:
        content = env_example_path.read_text(encoding="utf-8")
        for raw_line in content.splitlines():
            stripped = raw_line.strip()
            # Skip comments and empty lines
            if not stripped or stripped.startswith("#"):
                continue
            # Parse KEY=value for port variables
            if "=" in stripped and "_PORT" in stripped:
                key, _, value = stripped.partition("=")
                key = key.strip()
                value = value.strip()
                # Try to parse as integer
                try:
                    ports[key] = int(value)
                except ValueError:
                    pass  # Skip non-integer values
    except (OSError, UnicodeDecodeError):
        pass

    return ports


def get_default_ports() -> dict[str, int]:
    """Get default port values from .env.example.

    Returns a mapping from internal service names to port numbers.
    This is the bridge between .env.example variable names and internal service names.
    """
    env_ports = load_ports_from_env_example()

    # Map from internal service name to .env.example variable name
    # .env.example is the source of truth - these mappings define the relationship
    port_mappings = {
        "backend": "API_PORT",
        "frontend": "FRONTEND_PORT",
        "frontend_https": "FRONTEND_HTTPS_PORT",
        "frontend_http": "FRONTEND_HTTP_PORT",
        "postgres": "POSTGRES_PORT",
        "redis": "REDIS_PORT",
        "go2rtc_api": "GO2RTC_API_PORT",
        "go2rtc_webrtc": "GO2RTC_WEBRTC_PORT",
        "yolo26": "YOLO26_PORT",
        "nemotron": "LLM_PORT",
        "florence": "FLORENCE_PORT",
        "clip": "CLIP_PORT",
        "enrichment": "ENRICHMENT_PORT",
        "enrichment_light": "ENRICHMENT_LIGHT_PORT",
        "grafana": "GRAFANA_PORT",
        "prometheus": "PROMETHEUS_PORT",
        "alertmanager": "ALERTMANAGER_PORT",
        "loki": "LOKI_PORT",
        "jaeger_ui": "JAEGER_UI_PORT",
        "jaeger_otlp_grpc": "JAEGER_OTLP_GRPC_PORT",
        "jaeger_otlp_http": "JAEGER_OTLP_HTTP_PORT",
        "pyroscope": "PYROSCOPE_PORT",
        "alloy_ui": "ALLOY_UI_PORT",
        "node_exporter": "NODE_EXPORTER_PORT",
        "redis_exporter": "REDIS_EXPORTER_PORT",
        "json_exporter": "JSON_EXPORTER_PORT",
        "blackbox_exporter": "BLACKBOX_EXPORTER_PORT",
        "elasticsearch": "ELASTICSEARCH_PORT",
        "cadvisor": "CADVISOR_PORT",
        "dcgm_exporter": "DCGM_EXPORTER_PORT",
    }

    # Hardcoded fallbacks only used if .env.example is missing or malformed
    fallbacks = {
        "backend": 8000,
        "frontend": 5173,
        "frontend_https": 8444,
        "frontend_http": 8080,
        "postgres": 5432,
        "redis": 6379,
        "go2rtc_api": 1984,
        "go2rtc_webrtc": 8555,
        "yolo26": 8095,
        "nemotron": 8091,
        "florence": 8092,
        "clip": 8093,
        "enrichment": 8094,
        "enrichment_light": 8096,
        "grafana": 3002,
        "prometheus": 9090,
        "alertmanager": 9093,
        "loki": 3100,
        "jaeger_ui": 16686,
        "jaeger_otlp_grpc": 4317,
        "jaeger_otlp_http": 4318,
        "pyroscope": 4040,
        "alloy_ui": 12345,
        "node_exporter": 9100,
        "redis_exporter": 9121,
        "json_exporter": 7979,
        "blackbox_exporter": 9115,
        "elasticsearch": 9200,
        "cadvisor": 8082,
        "dcgm_exporter": 9400,
    }

    # Build result using .env.example values, falling back to hardcoded if missing
    result = {}
    for service, env_var in port_mappings.items():
        result[service] = env_ports.get(env_var, fallbacks.get(service, 0))

    return result


def build_services_dict() -> dict[str, ServiceInfo]:
    """Build SERVICES dict dynamically from .env.example ports.

    This ensures .env.example is the single source of truth for port values.
    Service metadata (category, description) is defined here, but ports come from .env.example.
    """
    ports = get_default_ports()

    # Service metadata - ports are loaded from .env.example
    service_metadata = {
        # Core Services
        "backend": {"category": "Core", "desc": "Backend API"},
        "frontend": {"category": "Core", "desc": "Frontend web UI"},
        "frontend_https": {"category": "Core", "desc": "Frontend HTTPS"},
        "frontend_http": {"category": "Core", "desc": "Frontend HTTP (Cloudflare tunnel)"},
        "postgres": {"category": "Core", "desc": "PostgreSQL database"},
        "redis": {"category": "Core", "desc": "Redis cache/queue"},
        "go2rtc_api": {"category": "Core", "desc": "go2rtc streaming API"},
        "go2rtc_webrtc": {"category": "Core", "desc": "go2rtc WebRTC"},
        # AI Services
        "yolo26": {"category": "AI", "desc": "YOLO26 object detection"},
        "nemotron": {"category": "AI", "desc": "Nemotron LLM reasoning"},
        "florence": {"category": "AI", "desc": "Florence-2 vision-language"},
        "clip": {"category": "AI", "desc": "CLIP embeddings"},
        "enrichment": {"category": "AI", "desc": "Entity enrichment"},
        "enrichment_light": {"category": "AI", "desc": "Light enrichment"},
        # Monitoring Services
        "grafana": {"category": "Monitoring", "desc": "Grafana dashboards"},
        "prometheus": {"category": "Monitoring", "desc": "Prometheus metrics"},
        "alertmanager": {"category": "Monitoring", "desc": "Alert manager"},
        "loki": {"category": "Monitoring", "desc": "Log aggregation"},
        "jaeger_ui": {"category": "Monitoring", "desc": "Jaeger tracing UI"},
        "jaeger_otlp_grpc": {"category": "Monitoring", "desc": "Jaeger OTLP gRPC"},
        "jaeger_otlp_http": {"category": "Monitoring", "desc": "Jaeger OTLP HTTP"},
        "pyroscope": {"category": "Monitoring", "desc": "Continuous profiling"},
        "alloy_ui": {"category": "Monitoring", "desc": "Alloy collector UI"},
        "node_exporter": {"category": "Monitoring", "desc": "Node metrics"},
        "redis_exporter": {"category": "Monitoring", "desc": "Redis exporter"},
        "json_exporter": {"category": "Monitoring", "desc": "JSON exporter"},
        "blackbox_exporter": {"category": "Monitoring", "desc": "Blackbox exporter"},
        "elasticsearch": {"category": "Monitoring", "desc": "Elasticsearch"},
        # Privileged Monitoring (require sudo podman)
        "cadvisor": {"category": "Privileged", "desc": "Container metrics"},
        "dcgm_exporter": {"category": "Privileged", "desc": "GPU metrics"},
    }

    services: dict[str, ServiceInfo] = {}
    for name, meta in service_metadata.items():
        services[name] = {
            "port": ports.get(name, 0),
            "category": meta["category"],
            "desc": meta["desc"],
        }

    return services


# SERVICES dict is built dynamically from .env.example
# .env.example is the SINGLE SOURCE OF TRUTH for all port values
SERVICES: dict[str, ServiceInfo] = build_services_dict()

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
        f"REDIS_PASSWORD={config.get('redis_password', '')}",
        f"FTP_PASSWORD={config.get('ftp_password', '')}",
        "",
        "# -- Authentication (NEM-3471) " + "-" * 30,
        f"JWT_SECRET={config.get('jwt_secret', '')}",
        f"JWT_EXPIRY_HOURS={config.get('jwt_expiry_hours', 24)}",
        f"REFRESH_TOKEN_DAYS={config.get('refresh_token_days', 30)}",
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
        f"FRONTEND_HTTPS_PORT={ports.get('frontend_https', 8444)}",
        f"FRONTEND_HTTP_PORT={ports.get('frontend_http', 8080)}",
        "",
        "# -- Foscam Init (chown on FOSCAM_BASE_PATH) " + "-" * 22,
        f"HOST_UID={config.get('host_uid', 1000)}",
        f"HOST_GID={config.get('host_gid', 1000)}",
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
        "# -- CUDA Build Optimization " + "-" * 31,
        "# Detected GPU compute capability for optimized CUDA builds",
        "# Reduces ai-llm build time by ~6x by only compiling for detected GPU",
        "# Format: XY (e.g., 89 = compute capability 8.9)",
        "# Leave empty to build for all common architectures (slower)",
        f"CUDA_ARCHITECTURES={config.get('cuda_architectures', '')}",
        "",
        "# -- Core Service Ports " + "-" * 37,
        f"POSTGRES_PORT={ports.get('postgres', 5432)}",
        f"REDIS_PORT={ports.get('redis', 6379)}",
        f"API_PORT={ports.get('backend', 8000)}",
        f"GO2RTC_API_PORT={ports.get('go2rtc_api', 1984)}",
        f"GO2RTC_WEBRTC_PORT={ports.get('go2rtc_webrtc', 8555)}",
        "",
        "# -- AI Service Ports " + "-" * 39,
        f"YOLO26_PORT={ports.get('yolo26', 8095)}",
        f"LLM_PORT={ports.get('nemotron', 8091)}",
        f"FLORENCE_PORT={ports.get('florence', 8092)}",
        f"CLIP_PORT={ports.get('clip', 8093)}",
        f"ENRICHMENT_PORT={ports.get('enrichment', 8094)}",
        f"ENRICHMENT_LIGHT_PORT={ports.get('enrichment_light', 8096)}",
        "",
        "# -- Monitoring Service Ports " + "-" * 31,
        f"PROMETHEUS_PORT={ports.get('prometheus', 9090)}",
        f"GRAFANA_PORT={ports.get('grafana', 3002)}",
        f"ALERTMANAGER_PORT={ports.get('alertmanager', 9093)}",
        f"LOKI_PORT={ports.get('loki', 3100)}",
        f"JAEGER_UI_PORT={ports.get('jaeger_ui', 16686)}",
        f"JAEGER_OTLP_GRPC_PORT={ports.get('jaeger_otlp_grpc', 4317)}",
        f"JAEGER_OTLP_HTTP_PORT={ports.get('jaeger_otlp_http', 4318)}",
        f"PYROSCOPE_PORT={ports.get('pyroscope', 4040)}",
        f"ALLOY_UI_PORT={ports.get('alloy_ui', 12345)}",
        f"NODE_EXPORTER_PORT={ports.get('node_exporter', 9100)}",
        f"REDIS_EXPORTER_PORT={ports.get('redis_exporter', 9121)}",
        f"JSON_EXPORTER_PORT={ports.get('json_exporter', 7979)}",
        f"BLACKBOX_EXPORTER_PORT={ports.get('blackbox_exporter', 9115)}",
        f"ELASTICSEARCH_PORT={ports.get('elasticsearch', 9200)}",
        "",
        "# -- Privileged Monitoring Ports (sudo podman) " + "-" * 14,
        f"CADVISOR_PORT={ports.get('cadvisor', 8082)}",
        f"DCGM_EXPORTER_PORT={ports.get('dcgm_exporter', 9400)}",
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
    # JWT secret for authentication (NEM-3471)
    jwt_secret = existing_env.get("JWT_SECRET") or generate_jwt_secret()
    jwt_expiry_hours = int(existing_env.get("JWT_EXPIRY_HOURS", "24"))
    refresh_token_days = int(existing_env.get("REFRESH_TOKEN_DAYS", "30"))

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

    # Ports - auto-detected free ports (optional manual override)
    print("-- Ports " + "-" * 52)
    print("  Auto-detected free ports for all services.")
    print()

    # Group ports by category for display
    categories: dict[str, list[tuple[str, int]]] = {}
    for service, info in SERVICES.items():
        cat = info["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((info["desc"], ports[service]))

    for cat, items in categories.items():
        print(f"  {cat}:")
        for desc, port in items:
            print(f"    {desc:<30s} {port}")
    print()

    manual = prompt_with_default("Configure ports manually?", "n")
    if manual.lower() in ("y", "yes"):
        print()
        for service, info in SERVICES.items():
            suggested = ports[service]
            custom = prompt_with_default(f"{info['desc']}", str(suggested))
            try:
                ports[service] = int(custom)
            except ValueError:
                ports[service] = suggested
    print()

    # Detect GPU compute capability for optimized CUDA builds
    from setup_lib.nvidia_detect import get_gpu_info

    cuda_arch = ""
    gpus = get_gpu_info()
    if gpus and len(gpus) > 0:
        # Use first GPU's compute capability (e.g., "8.9" -> "89")
        compute_cap = gpus[0].get("compute_cap", "")
        if compute_cap and compute_cap != "unknown":
            cuda_arch = compute_cap.replace(".", "")

    return {
        "foscam_base_path": foscam_base_path,
        "ai_models_path": ai_models_path,
        "postgres_password": postgres_password,
        "redis_password": redis_password,
        "grafana_password": grafana_password,
        "ftp_password": ftp_password,
        "jwt_secret": jwt_secret,
        "jwt_expiry_hours": jwt_expiry_hours,
        "refresh_token_days": refresh_token_days,
        "ports": ports,
        "gpu_llm": 0,
        "gpu_ai_services": 1,
        "cuda_architectures": cuda_arch,
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
    # JWT secret for authentication (NEM-3471)
    jwt_secret = existing_env.get("JWT_SECRET") or generate_jwt_secret()
    jwt_expiry_hours = int(existing_env.get("JWT_EXPIRY_HOURS", "24"))
    refresh_token_days = int(existing_env.get("REFRESH_TOKEN_DAYS", "30"))

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
    print("Auto-detecting free ports for all services...")
    print()

    assigned_ports: set[int] = set()
    conflicts = []
    for service, info in SERVICES.items():
        default_port = info["port"]
        if check_port_available(default_port) and default_port not in assigned_ports:
            ports[service] = default_port
        else:
            available = find_available_port(default_port, exclude=assigned_ports)
            ports[service] = available
            conflicts.append(f"  {info['desc']}: {default_port} -> {available}")
        assigned_ports.add(ports[service])

    if conflicts:
        print("! Port conflicts detected, using alternatives:")
        for c in conflicts:
            print(c)
        print()
    else:
        print("+ All default ports available")
        print()

    # Group ports by category for display
    categories: dict[str, list[tuple[str, int]]] = {}
    for service, info in SERVICES.items():
        cat = info["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((info["desc"], ports[service]))

    for cat, items in categories.items():
        print(f"  {cat}:")
        for desc, port in items:
            print(f"    {desc:<30s} {port}")
    print()

    manual = prompt_with_default("Configure ports manually?", "n")
    if manual.lower() in ("y", "yes"):
        print()
        for service, info in SERVICES.items():
            suggested = ports[service]
            custom = prompt_with_default(f"  {info['desc']}", str(suggested))
            try:
                ports[service] = int(custom)
            except ValueError:
                ports[service] = suggested
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

    # Detect GPU compute capability for optimized CUDA builds
    from setup_lib.nvidia_detect import get_gpu_info

    cuda_arch = ""
    gpus = get_gpu_info()
    if gpus and len(gpus) > 0:
        # Use first GPU's compute capability (e.g., "8.9" -> "89")
        compute_cap = gpus[0].get("compute_cap", "")
        if compute_cap and compute_cap != "unknown":
            cuda_arch = compute_cap.replace(".", "")

    return {
        "foscam_base_path": foscam_base_path,
        "ai_models_path": ai_models_path,
        "postgres_password": postgres_password,
        "redis_password": redis_password,
        "grafana_password": grafana_password,
        "ftp_password": ftp_password,
        "jwt_secret": jwt_secret,
        "jwt_expiry_hours": jwt_expiry_hours,
        "refresh_token_days": refresh_token_days,
        "ports": ports,
        "host_uid": os.getuid(),
        "host_gid": os.getgid(),
        "gpu_llm": 0,
        "gpu_ai_services": 1,
        "cuda_architectures": cuda_arch,
    }


def write_config_files(
    config: dict[str, Any], output_dir: str = ".", create_secret_files: bool = False
) -> tuple[Path, Path | None, Path | None]:
    """Write configuration files to disk.

    .env is the source of truth. docker-compose.prod.yml reads all config from .env.
    No docker-compose.override.yml is generated.

    Args:
        config: Configuration dictionary
        output_dir: Directory to write files to
        create_secret_files: If True, also create Docker secrets files

    Returns:
        Tuple of (env_path, None, secrets_path or None)
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    env_path = output / ".env"
    env_content = generate_env_content(config)
    env_path.write_text(env_content)

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

    return env_path, None, secrets_path


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


def run_defaults_mode() -> dict:
    """Run non-interactive setup with all defaults.

    Used by redeploy.py to bootstrap .env without user interaction.

    Returns:
        Configuration dictionary with all defaults applied
    """
    # Check port conflicts silently
    ports = {}
    assigned_ports: set[int] = set()
    for service, info in SERVICES.items():
        default_port = info["port"]
        if check_port_available(default_port) and default_port not in assigned_ports:
            ports[service] = default_port
        else:
            ports[service] = find_available_port(default_port, exclude=assigned_ports)
        assigned_ports.add(ports[service])

    # Generate unique passwords (including redis for production security)
    postgres_password = generate_password(32)
    redis_password = generate_password(32)
    ftp_password = generate_password(16)
    # JWT secret for authentication (NEM-3471)
    jwt_secret = generate_jwt_secret()

    # Detect GPU compute capability for optimized CUDA builds
    from setup_lib.nvidia_detect import get_gpu_info

    cuda_arch = ""
    gpus = get_gpu_info()
    if gpus and len(gpus) > 0:
        # Use first GPU's compute capability (e.g., "8.9" -> "89")
        compute_cap = gpus[0].get("compute_cap", "")
        if compute_cap and compute_cap != "unknown":
            cuda_arch = compute_cap.replace(".", "")

    return {
        "foscam_base_path": "/export/foscam",
        "ai_models_path": "/export/ai_models",
        "postgres_password": postgres_password,
        "redis_password": redis_password,
        "grafana_password": "",
        "ftp_password": ftp_password,
        "jwt_secret": jwt_secret,
        "jwt_expiry_hours": 24,
        "refresh_token_days": 30,
        "ports": ports,
        "host_uid": os.getuid(),
        "host_gid": os.getgid(),
        "gpu_llm": 0,
        "gpu_ai_services": 1,
        "cuda_architectures": cuda_arch,
    }


def main() -> None:
    """Main entry point for setup script."""
    parser = argparse.ArgumentParser(description="Interactive setup for Home Security Intelligence")
    parser.add_argument(
        "command",
        nargs="?",
        default=None,
        help="Command to run (e.g., 'deploy')",
    )
    parser.add_argument(
        "--guided",
        action="store_true",
        help="Run in guided mode with detailed explanations",
    )
    parser.add_argument(
        "--defaults",
        action="store_true",
        help="Non-interactive mode: use all defaults without prompting",
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
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Developer mode: install pre-commit hooks for code contributions",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Auto-accept all prompts (non-interactive quick mode with model downloads)",
    )
    parser.add_argument(
        "--destroy-volumes",
        action="store_true",
        help="(deploy) Destroy all volumes before deploy",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="(deploy) Skip container image builds",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="(deploy) Skip model export before deploy",
    )
    parser.add_argument(
        "--force-export",
        action="store_true",
        help="(deploy) Force re-export all models",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=True,
        help="(deploy) Show full build output (default)",
    )
    parser.add_argument(
        "--no-verbose",
        action="store_false",
        dest="verbose",
        help="(deploy) Suppress build output",
    )
    parser.add_argument(
        "--log-file",
        metavar="PATH",
        default="/tmp/deploy.log",
        help="(deploy) Write output to this log file (default: /tmp/deploy.log)",
    )
    parser.add_argument(
        "--no-log-file",
        action="store_true",
        help="(deploy) Do not write output to a log file",
    )
    args = parser.parse_args()

    # Deploy mode: delegate to setup_lib.deploy
    if args.command == "deploy":
        from setup_lib.deploy import DeployConfig, detect_compose_command, load_env, run_deploy

        project_root = Path(__file__).resolve().parent
        env = load_env(project_root)
        compose_cmd = detect_compose_command()

        config = DeployConfig(
            project_root=project_root,
            compose_cmd=compose_cmd,
            destroy_volumes=args.destroy_volumes,
            skip_build=args.skip_build,
            skip_export=args.skip_export,
            force_export=args.force_export,
            verbose=args.verbose,
            env=env,
        )

        def run_deploy_with_logging():
            """Run deploy, optionally teeing output to a log file."""
            # Print banner
            branch = subprocess.run(  # noqa: S603
                ["git", "-C", str(project_root), "branch", "--show-current"],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            commit = subprocess.run(  # noqa: S603
                ["git", "-C", str(project_root), "rev-parse", "--short", "HEAD"],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            print("=== Production Deploy ===")
            print(f"Branch: {branch}")
            print(f"Commit: {commit}")
            if not args.no_log_file:
                print(f"Log file: {Path(args.log_file).resolve()}")
            print()

            return run_deploy(config)

        if args.no_log_file:
            success = run_deploy_with_logging()
        else:
            log_path = Path(args.log_file).resolve()
            log_path.parent.mkdir(parents=True, exist_ok=True)

            class TeeOutput:
                """Write to both stdout and a log file."""

                def __init__(self, stream, log_file):  # noqa: D107
                    self.stream = stream
                    self.log_file = log_file

                def write(self, data):
                    self.stream.write(data)
                    self.stream.flush()
                    self.log_file.write(data)
                    self.log_file.flush()

                def flush(self):
                    self.stream.flush()
                    self.log_file.flush()

                def __getattr__(self, name):
                    return getattr(self.stream, name)

            with open(log_path, "w", encoding="utf-8") as log_file:
                tee = TeeOutput(sys.stdout, log_file)
                original_stdout = sys.stdout
                sys.stdout = tee  # type: ignore[assignment]

                try:
                    success = run_deploy_with_logging()
                finally:
                    sys.stdout = original_stdout

        sys.exit(0 if success else 1)

    try:
        driver_was_upgraded = False

        # Step 0: Platform detection and validation
        if not args.defaults:
            print("=" * 60)
            print("  Home Security Intelligence - Setup")
            print("=" * 60)
            print()
            print("Detecting platform...")
            print_platform_info()
            print()

            platform_info = get_platform_info()
            if platform_info is None:
                print("! Unsupported platform. Only Linux and Windows are supported.")
                print("  macOS is not supported due to lack of NVIDIA CUDA support.")
                sys.exit(1)

            # Step 0: Fix broken apt (e.g. from failed nvidia installs) so podman can install
            fix_broken_apt_if_needed()

            # Step 1/5: Container Runtime (Podman)
            # Auto-install without prompting for streamlined setup
            prompt_and_install_podman({"auto_install": True})

            # Step 2/5: NVIDIA GPU detection
            # Auto-install without prompting for streamlined setup
            nvidia_config: dict[str, object] = {"auto_install": True}
            prompt_and_check_nvidia(nvidia_config)
            driver_was_upgraded = bool(nvidia_config.get("driver_upgraded"))

            # Step 2b: DCGM Exporter service (GPU hardware metrics)
            # Installs a rootful systemd service for DCGM, which requires
            # host-level root access that rootless Podman cannot provide.
            project_root = Path(__file__).resolve().parent
            prompt_and_install_dcgm_service(project_root, auto_install=True)

            # Step 2c: Rootful services + host configuration
            # - Memlock limits for eBPF profiling (Grafana Alloy)
            # - cAdvisor systemd service (container metrics)
            prompt_and_install_rootful_services(project_root, auto_install=True)

            # Step 3/5: Storage configuration
            storage_result = prompt_and_configure_storage({"auto_create": True})
        else:
            storage_result = None

        if args.defaults:
            config = run_defaults_mode()
            print("[setup.py] Running in defaults mode (non-interactive)")
        elif args.guided:
            config = run_guided_mode()
        elif args.yes:
            # Non-interactive quick mode with all defaults
            config = run_defaults_mode()
            print("[setup.py] Auto-accepting all defaults (--yes mode)")
        else:
            config = run_quick_mode()

        # Merge storage config from step 3 (if interactive mode)
        if storage_result is not None:
            config["foscam_base_path"] = storage_result["foscam_base_path"]
            config["ai_models_path"] = storage_result["ai_models_path"]

        # Docker secrets are created by default for production security
        create_secrets = args.create_secrets
        if not args.defaults:
            print("\n" + "=" * 60)
            print("Docker Secrets (Production Security)")
            print("=" * 60)
            print()
            print("Docker Secrets provide enhanced security for credentials:")
            print("  - Stored separately from environment variables")
            print("  - Not visible in 'docker inspect' output")
            print("  - Easier credential rotation without image rebuild")
            print()
            # Default to Yes for production-first approach
            answer = prompt_with_default("Create Docker secrets files?", "Y")
            create_secrets = answer.lower() in ("y", "yes", "")

        # Write configuration files
        env_path, _, secrets_path = write_config_files(
            config, args.output_dir, create_secret_files=create_secrets
        )

        # Install pre-commit hooks (only in developer mode)
        if args.dev:
            print("\n" + "=" * 60)
            print("Installing pre-commit hooks (developer mode)...")
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

        if args.defaults:
            # Minimal output in defaults mode
            print(f"[setup.py] Generated: {env_path}")
        else:
            print("=" * 60)
            print("Generated:")
            print(f"  - {env_path}")
            print(f"  - Configuration via .env (docker-compose.prod.yml reads from .env)")
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

        # Step 4/5: Network configuration (skip in defaults mode)
        if not args.defaults:
            # Get all external ports that need firewall access
            external_ports = [
                config["ports"].get("frontend", 5173),
                config["ports"].get("frontend_https", 8443),
                config["ports"].get("grafana", 3002),
            ]
            prompt_and_configure_firewall(
                {"firewall_ports": external_ports, "auto_configure": True}
            )

        # Step 5/5: Credentials & Security (skip in defaults mode)
        if not args.defaults:
            config["auto_generate"] = True  # Auto-generate certificates
            prompt_and_generate_certificates(config)

        # Offer AI workstation optimizations on Linux (skip in defaults mode)
        # This runs BEFORE model downloads because it may require a reboot.
        # If the user reboots, they re-run setup.py and models download after
        # the system is fully configured.
        optimizer_reboot = False
        if platform.system() == "Linux" and not args.defaults:
            _opt_success, optimizer_reboot = prompt_and_run_optimizations()

        # Combine reboot signals: driver upgrade OR kernel parameter changes
        # Both require a reboot before GPU containers can start.
        reboot_required = optimizer_reboot or (
            not args.defaults and driver_was_upgraded
        )

        # Download AI models (skip in defaults mode, but enable for --yes mode)
        if not args.defaults or args.yes:
            if reboot_required:
                print()
                print("=" * 60)
                print("! System configuration changes require a reboot")
                if driver_was_upgraded and not optimizer_reboot:
                    print("  NVIDIA driver was upgraded — new driver loads after reboot.")
                elif driver_was_upgraded and optimizer_reboot:
                    print("  NVIDIA driver was upgraded and kernel parameters were changed.")
                else:
                    print("  Kernel parameters and driver options will not take")
                    print("  effect until after a restart.")
                print("=" * 60)
                print()
                try:
                    proceed = input(
                        "Continue with model downloads anyway? [y/N]: "
                    ).strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print()
                    proceed = "n"

                if proceed not in ("y", "yes"):
                    print()
                    print("Skipping model downloads.")
                    print("  After rebooting, re-run: python3 setup.py")
                    print()
                else:
                    config["auto_download"] = True
                    prompt_and_download_models(config)
            else:
                # Auto-download required + Phase 1 models (full ai-gateway support)
                config["auto_download"] = True
                prompt_and_download_models(config)

        # Pull container images (skip in defaults mode)
        if not args.defaults:
            config["skip_pull"] = True  # Skip image pull to save time
            prompt_and_pull_images(config)

        # Auto-deploy or reboot
        # Skip deploy if reboot is required — GPU containers will fail without
        # the new driver's device nodes (/dev/nvidia*).
        if not args.defaults and reboot_required:
            print()
            print("=" * 60)
            print("  Reboot Required Before Deployment")
            print("=" * 60)
            print()
            if driver_was_upgraded:
                print("  The NVIDIA driver was upgraded and the new driver will")
                print("  not load until after a reboot. GPU containers (ai-llm,")
                print("  ai-gateway) cannot start without /dev/nvidia* devices.")
            if optimizer_reboot:
                print("  Kernel parameters were changed that require a reboot.")
            print()
            print("  After rebooting, deploy services with:")
            print("    python3 setup.py deploy")
            print()
            try:
                reboot_now = input("Reboot now? [Y/n]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                reboot_now = "n"

            if reboot_now in ("y", "yes", ""):
                print("  Rebooting...")
                subprocess.run(["sudo", "reboot"], check=False)  # noqa: S603, S607
            else:
                print()
                print("  Remember to reboot before deploying.")
                print("  Then run: python3 setup.py deploy")

        elif not args.defaults:
            print()
            print("=" * 60)
            print("  Deploying Services")
            print("=" * 60)
            print()

            from setup_lib.deploy import DeployConfig as _DeployConfig
            from setup_lib.deploy import detect_compose_command, load_env, run_deploy

            project_root = Path(__file__).resolve().parent
            env = load_env(project_root)
            compose_cmd = detect_compose_command()

            deploy_config = _DeployConfig(
                project_root=project_root,
                compose_cmd=compose_cmd,
                skip_build=False,
                skip_export=True,
                verbose=False,
                env=env,
            )

            success = run_deploy(deploy_config)
            if success:
                print()
                print("=" * 60)
                print("  Setup complete! All services are running.")
                print("=" * 60)
            else:
                print()
                print("! Deployment encountered errors.")
                print("  Check logs with: podman compose -f docker-compose.prod.yml logs")
                print("  Retry with: python setup.py deploy")

    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(1)


if __name__ == "__main__":
    main()
