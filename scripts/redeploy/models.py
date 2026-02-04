"""Data models, enums, and exceptions for the redeploy tool."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_env_example_ports() -> dict[str, int]:
    """Load port defaults from .env.example (single source of truth).

    Returns:
        Dictionary mapping env var names to port values.
    """
    env_example = Path(".env.example")
    if not env_example.exists():
        return {}

    ports: dict[str, int] = {}
    try:
        for raw_line in env_example.read_text().splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" in stripped and "_PORT" in stripped:
                key, _, value = stripped.partition("=")
                try:
                    ports[key.strip()] = int(value.strip())
                except ValueError:
                    pass
    except (OSError, UnicodeDecodeError):
        pass
    return ports


# Load defaults from .env.example at module load time
_ENV_PORTS = _load_env_example_ports()


def _port_default(env_var: str, fallback: int) -> int:
    """Get port default from .env.example, with hardcoded fallback."""
    return _ENV_PORTS.get(env_var, fallback)


class DeployMode(str, Enum):
    """Deployment mode selection."""

    LOCAL = "local"  # Build all images locally
    HYBRID = "hybrid"  # GHCR core + local AI
    GHCR = "ghcr"  # All from GHCR (no AI services)


class ContainerStatus(str, Enum):
    """Container status states."""

    RUNNING = "running"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    STOPPED = "stopped"
    NOT_FOUND = "not_found"


class BuildStatus(str, Enum):
    """Image build status."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CACHED = "cached"


# =============================================================================
# Exceptions
# =============================================================================


class DeployError(Exception):
    """Base exception for deployment errors."""

    pass


class PortConflictError(DeployError):
    """Required ports are in use by other processes."""

    def __init__(self, ports: dict[int, str]):
        self.ports = ports
        port_list = ", ".join(f"{p} ({s})" for p, s in ports.items())
        super().__init__(f"Ports in use: {port_list}")


class BuildError(DeployError):
    """Image build failed."""

    def __init__(self, service: str, message: str):
        self.service = service
        super().__init__(f"Build failed for {service}: {message}")


class HealthCheckError(DeployError):
    """Service health check failed."""

    def __init__(self, service: str, message: str):
        self.service = service
        super().__init__(f"Health check failed for {service}: {message}")


class StorageError(DeployError):
    """Container storage operation failed."""

    pass


class ContainerError(DeployError):
    """Container operation failed."""

    def __init__(self, container: str, operation: str, message: str):
        self.container = container
        self.operation = operation
        super().__init__(f"{operation} failed for {container}: {message}")


class GitError(DeployError):
    """Git operation failed."""

    pass


class MigrationError(DeployError):
    """Database migration failed."""

    pass


# =============================================================================
# Result dataclasses
# =============================================================================


@dataclass
class CommandResult:
    """Result of a subprocess command."""

    returncode: int
    stdout: str
    stderr: str
    duration: float
    command: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.returncode == 0


@dataclass
class BuildResult:
    """Result of an image build."""

    service: str
    status: BuildStatus
    duration: float
    image_id: str | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.status in (BuildStatus.SUCCESS, BuildStatus.CACHED)


@dataclass
class HealthStatus:
    """Health status of a service."""

    service: str
    status: ContainerStatus
    message: str | None = None
    details: dict | None = None

    @property
    def healthy(self) -> bool:
        return self.status in (ContainerStatus.RUNNING, ContainerStatus.HEALTHY)


@dataclass
class PortStatus:
    """Status of required ports."""

    ports_in_use: dict[int, str]  # port -> process/container using it
    blocking_containers: list[str]

    @property
    def all_free(self) -> bool:
        return len(self.ports_in_use) == 0


@dataclass
class DeployResult:
    """Final result of deployment."""

    success: bool
    duration: float = 0.0
    error: str | None = None
    phase_failed: str | None = None
    services_started: list[str] = field(default_factory=list)
    build_results: dict[str, BuildResult] = field(default_factory=dict)


# =============================================================================
# Configuration
# =============================================================================


class DeployConfig(BaseSettings):
    """Deployment configuration loaded from .env and CLI."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # CLI options (set via constructor, not from .env)
    mode: DeployMode = DeployMode.LOCAL
    keep_volumes: bool = False
    reset_storage: bool = False
    skip_git_pull: bool = False
    dry_run: bool = False
    seed_files_count: int = 0
    image_tag: str = "latest"

    # Project paths (computed)
    project_root: Path = Field(default_factory=Path.cwd)

    # Database settings
    postgres_user: str = Field(default="security", alias="POSTGRES_USER")
    postgres_password: str = Field(default="", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="security", alias="POSTGRES_DB")
    database_url: str = Field(default="", alias="DATABASE_URL")

    # Redis settings
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")

    # Paths
    ai_models_path: Path = Field(default=Path("/export/ai_models"), alias="AI_MODELS_PATH")
    foscam_base_path: Path = Field(default=Path("/export/foscam"), alias="FOSCAM_BASE_PATH")

    # Core service ports (defaults from .env.example)
    postgres_port: int = Field(
        default_factory=lambda: _port_default("POSTGRES_PORT", 5432), alias="POSTGRES_PORT"
    )
    redis_port: int = Field(
        default_factory=lambda: _port_default("REDIS_PORT", 6379), alias="REDIS_PORT"
    )
    api_port: int = Field(default_factory=lambda: _port_default("API_PORT", 8000), alias="API_PORT")
    frontend_port: int = Field(
        default_factory=lambda: _port_default("FRONTEND_HTTPS_PORT", 8444),
        alias="FRONTEND_HTTPS_PORT",
    )
    go2rtc_api_port: int = Field(
        default_factory=lambda: _port_default("GO2RTC_API_PORT", 1984), alias="GO2RTC_API_PORT"
    )
    go2rtc_webrtc_port: int = Field(
        default_factory=lambda: _port_default("GO2RTC_WEBRTC_PORT", 8555),
        alias="GO2RTC_WEBRTC_PORT",
    )

    # AI service ports (defaults from .env.example)
    yolo26_port: int = Field(
        default_factory=lambda: _port_default("YOLO26_PORT", 8095), alias="YOLO26_PORT"
    )
    llm_port: int = Field(default_factory=lambda: _port_default("LLM_PORT", 8091), alias="LLM_PORT")
    florence_port: int = Field(
        default_factory=lambda: _port_default("FLORENCE_PORT", 8092), alias="FLORENCE_PORT"
    )
    clip_port: int = Field(
        default_factory=lambda: _port_default("CLIP_PORT", 8093), alias="CLIP_PORT"
    )
    enrichment_port: int = Field(
        default_factory=lambda: _port_default("ENRICHMENT_PORT", 8094), alias="ENRICHMENT_PORT"
    )
    enrichment_light_port: int = Field(
        default_factory=lambda: _port_default("ENRICHMENT_LIGHT_PORT", 8096),
        alias="ENRICHMENT_LIGHT_PORT",
    )

    # Monitoring service ports (defaults from .env.example)
    prometheus_port: int = Field(
        default_factory=lambda: _port_default("PROMETHEUS_PORT", 9090), alias="PROMETHEUS_PORT"
    )
    grafana_port: int = Field(
        default_factory=lambda: _port_default("GRAFANA_PORT", 3002), alias="GRAFANA_PORT"
    )
    alertmanager_port: int = Field(
        default_factory=lambda: _port_default("ALERTMANAGER_PORT", 9093), alias="ALERTMANAGER_PORT"
    )
    loki_port: int = Field(
        default_factory=lambda: _port_default("LOKI_PORT", 3100), alias="LOKI_PORT"
    )
    jaeger_ui_port: int = Field(
        default_factory=lambda: _port_default("JAEGER_UI_PORT", 16686), alias="JAEGER_UI_PORT"
    )
    jaeger_otlp_grpc_port: int = Field(
        default_factory=lambda: _port_default("JAEGER_OTLP_GRPC_PORT", 4317),
        alias="JAEGER_OTLP_GRPC_PORT",
    )
    jaeger_otlp_http_port: int = Field(
        default_factory=lambda: _port_default("JAEGER_OTLP_HTTP_PORT", 4318),
        alias="JAEGER_OTLP_HTTP_PORT",
    )
    pyroscope_port: int = Field(
        default_factory=lambda: _port_default("PYROSCOPE_PORT", 4040), alias="PYROSCOPE_PORT"
    )
    alloy_ui_port: int = Field(
        default_factory=lambda: _port_default("ALLOY_UI_PORT", 12345), alias="ALLOY_UI_PORT"
    )
    node_exporter_port: int = Field(
        default_factory=lambda: _port_default("NODE_EXPORTER_PORT", 9100),
        alias="NODE_EXPORTER_PORT",
    )
    redis_exporter_port: int = Field(
        default_factory=lambda: _port_default("REDIS_EXPORTER_PORT", 9121),
        alias="REDIS_EXPORTER_PORT",
    )
    json_exporter_port: int = Field(
        default_factory=lambda: _port_default("JSON_EXPORTER_PORT", 7979),
        alias="JSON_EXPORTER_PORT",
    )
    blackbox_exporter_port: int = Field(
        default_factory=lambda: _port_default("BLACKBOX_EXPORTER_PORT", 9115),
        alias="BLACKBOX_EXPORTER_PORT",
    )
    elasticsearch_port: int = Field(
        default_factory=lambda: _port_default("ELASTICSEARCH_PORT", 9200),
        alias="ELASTICSEARCH_PORT",
    )

    # Privileged monitoring ports (defaults from .env.example, require sudo podman)
    cadvisor_port: int = Field(
        default_factory=lambda: _port_default("CADVISOR_PORT", 8082), alias="CADVISOR_PORT"
    )
    dcgm_exporter_port: int = Field(
        default_factory=lambda: _port_default("DCGM_EXPORTER_PORT", 9400),
        alias="DCGM_EXPORTER_PORT",
    )

    # GPU assignments
    gpu_ai_services: int = Field(default=1, alias="GPU_AI_SERVICES")
    gpu_llm: int = Field(default=0, alias="GPU_LLM")
    gpu_florence: int = Field(default=0, alias="GPU_FLORENCE")
    gpu_clip: int = Field(default=1, alias="GPU_CLIP")
    gpu_enrichment: int = Field(default=1, alias="GPU_ENRICHMENT")

    # TensorRT settings
    yolo26_confidence: float = Field(default=0.5, alias="YOLO26_CONFIDENCE")

    # Debug
    debug: bool = Field(default=False, alias="DEBUG")

    # Computed properties
    @property
    def compose_file_prod(self) -> Path:
        return self.project_root / "docker-compose.prod.yml"

    @property
    def compose_file_ghcr(self) -> Path:
        return self.project_root / "docker-compose.ghcr.yml"

    @property
    def project_name(self) -> str:
        """Generate project name from directory (used for container naming)."""
        return self.project_root.name.replace("-", "_").replace(".", "_")

    @property
    def required_ports(self) -> dict[int, str]:
        """Map of required ports to service names."""
        return {
            # Core services
            self.postgres_port: "PostgreSQL",
            self.redis_port: "Redis",
            self.api_port: "Backend API",
            # AI services
            self.llm_port: "LLM",
            self.florence_port: "Florence",
            self.clip_port: "CLIP",
            self.enrichment_port: "Enrichment",
            self.yolo26_port: "YOLO26",
            # Monitoring (subset - only critical ones)
            self.prometheus_port: "Prometheus",
            self.grafana_port: "Grafana",
            self.loki_port: "Loki",
        }

    @property
    def monitoring_ports(self) -> dict[int, str]:
        """Map of monitoring ports to service names."""
        return {
            self.prometheus_port: "Prometheus",
            self.grafana_port: "Grafana",
            self.alertmanager_port: "Alertmanager",
            self.loki_port: "Loki",
            self.jaeger_ui_port: "Jaeger UI",
            self.jaeger_otlp_grpc_port: "Jaeger OTLP gRPC",
            self.jaeger_otlp_http_port: "Jaeger OTLP HTTP",
            self.pyroscope_port: "Pyroscope",
            self.alloy_ui_port: "Alloy",
            self.node_exporter_port: "Node Exporter",
            self.redis_exporter_port: "Redis Exporter",
            self.json_exporter_port: "JSON Exporter",
            self.blackbox_exporter_port: "Blackbox Exporter",
            self.elasticsearch_port: "Elasticsearch",
            self.cadvisor_port: "cAdvisor",
            self.dcgm_exporter_port: "DCGM Exporter",
        }

    # Class-level constants
    AI_SERVICES: ClassVar[list[str]] = [
        "ai-yolo26",
        "ai-llm",
        "ai-florence",
        "ai-clip",
        "ai-enrichment",
        "ai-enrichment-light",
    ]

    STANDALONE_CONTAINERS: ClassVar[list[str]] = [
        "ai-yolo26",
        "ai-llm",
        "ai-florence",
        "ai-clip",
        "ai-enrichment",
        "ai-enrichment-light",
        "backend",
        "frontend",
    ]

    PROJECT_PATTERNS: ClassVar[list[str]] = [
        "nemotron",
        "security",
        "ai-yolo",
        "ai-llm",
        "ai-florence",
        "ai-clip",
        "ai-enrichment",
        "backend",
        "frontend",
        "postgres",
        "redis",
        "go2rtc",
        "elasticsearch",
    ]
