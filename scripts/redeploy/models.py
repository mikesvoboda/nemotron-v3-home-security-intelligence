"""Data models, enums, and exceptions for the redeploy tool."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Service ports
    api_port: int = Field(default=8000, alias="API_PORT")
    frontend_port: int = Field(default=8444, alias="FRONTEND_HTTPS_PORT")
    yolo26_port: int = Field(default=8095, alias="YOLO26_PORT")
    llm_port: int = Field(default=8091, alias="LLM_PORT")
    florence_port: int = Field(default=8092, alias="FLORENCE_PORT")
    clip_port: int = Field(default=8093, alias="CLIP_PORT")
    enrichment_port: int = Field(default=8094, alias="ENRICHMENT_PORT")

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
            5432: "PostgreSQL",
            6379: "Redis",
            self.api_port: "Backend API",
            self.llm_port: "LLM",
            self.florence_port: "Florence",
            self.clip_port: "CLIP",
            self.enrichment_port: "Enrichment",
            self.yolo26_port: "YOLO26",
        }

    # Class-level constants
    AI_SERVICES: ClassVar[list[str]] = [
        "ai-yolo26",
        "ai-llm",
        "ai-florence",
        "ai-clip",
        "ai-enrichment",
    ]

    STANDALONE_CONTAINERS: ClassVar[list[str]] = [
        "ai-yolo26",
        "ai-llm",
        "ai-florence",
        "ai-clip",
        "ai-enrichment",
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
    ]
