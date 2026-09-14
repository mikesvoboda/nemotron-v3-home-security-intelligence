# Redeploy Python Design Document

## Overview

Replace `scripts/redeploy.sh` (2226 lines bash) with a well-modularized Python CLI tool using OOP principles.

## Design Goals

1. **Single Responsibility** - Each class has one clear purpose
2. **Dependency Injection** - Classes receive dependencies, enabling testing
3. **Async-First** - Parallel operations (AI builds) use asyncio
4. **Testable** - All business logic can be unit tested
5. **Type-Safe** - Full type hints, Pydantic for config validation

## Package Structure

```
scripts/
├── redeploy.py                    # Entry point (3 lines)
└── redeploy/
    ├── __init__.py
    ├── cli.py                     # Typer CLI, argument parsing
    ├── config.py                  # Configuration loading & validation
    ├── models.py                  # Pydantic models, enums
    │
    ├── core/
    │   ├── __init__.py
    │   ├── runtime.py             # ContainerRuntime (podman/docker abstraction)
    │   ├── process.py             # ProcessRunner (subprocess wrapper)
    │   └── output.py              # Console output (rich)
    │
    ├── services/
    │   ├── __init__.py
    │   ├── containers.py          # ContainerManager
    │   ├── builder.py             # ImageBuilder
    │   ├── health.py              # HealthChecker
    │   ├── tensorrt.py            # TensorRTBuilder
    │   ├── git.py                 # GitManager
    │   ├── database.py            # DatabaseManager (migrations, seeding)
    │   └── storage.py             # StorageManager (prune, reset)
    │
    └── orchestrator.py            # DeployOrchestrator (main workflow)
```

## Class Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      DeployOrchestrator                         │
│─────────────────────────────────────────────────────────────────│
│ - config: DeployConfig                                          │
│ - containers: ContainerManager                                  │
│ - builder: ImageBuilder                                         │
│ - health: HealthChecker                                         │
│ - tensorrt: TensorRTBuilder                                     │
│ - git: GitManager                                               │
│ - database: DatabaseManager                                     │
│ - storage: StorageManager                                       │
│─────────────────────────────────────────────────────────────────│
│ + async deploy() -> DeployResult                                │
│ - async _stop_phase() -> None                                   │
│ - async _build_phase() -> None                                  │
│ - async _start_phase() -> None                                  │
│ - async _verify_phase() -> None                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ uses
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
┌───────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  ContainerManager │ │  ImageBuilder   │ │  HealthChecker  │
│───────────────────│ │─────────────────│ │─────────────────│
│ - runtime         │ │ - runtime       │ │ - http: httpx   │
│ - process         │ │ - process       │ │─────────────────│
│───────────────────│ │ - config        │ │ + check_backend │
│ + stop_all()      │ │─────────────────│ │ + check_ai()    │
│ + stop_compose()  │ │ + build_base()  │ │ + wait_healthy()│
│ + start_infra()   │ │ + build_core()  │ └─────────────────┘
│ + start_ai()      │ │ + build_ai()    │
│ + start_backend() │ │ + build_parallel│
│ + verify_ports()  │ └─────────────────┘
└───────────────────┘
         │
         │ uses
         ▼
┌───────────────────┐
│ ContainerRuntime  │
│───────────────────│
│ - cmd: str        │  "podman" or "docker"
│ - compose: str    │  "podman-compose" or "docker-compose"
│───────────────────│
│ + run()           │
│ + stop()          │
│ + rm()            │
│ + ps()            │
│ + exec()          │
│ + logs()          │
└───────────────────┘
         │
         │ uses
         ▼
┌───────────────────┐
│  ProcessRunner    │
│───────────────────│
│ - dry_run: bool   │
│ - console: Console│
│───────────────────│
│ + run() -> Result │
│ + run_async()     │
│ + stream()        │
└───────────────────┘
```

## Core Classes

### 1. ProcessRunner (core/process.py)

Wraps subprocess calls with logging, dry-run support, and async.

```python
@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    duration: float

class ProcessRunner:
    def __init__(self, dry_run: bool = False, console: Console | None = None):
        self.dry_run = dry_run
        self.console = console or Console()

    def run(
        self,
        cmd: list[str],
        check: bool = True,
        capture: bool = True,
        timeout: int | None = None,
    ) -> CommandResult:
        """Run command synchronously."""

    async def run_async(
        self,
        cmd: list[str],
        check: bool = True,
        capture: bool = True,
    ) -> CommandResult:
        """Run command asynchronously."""

    def stream(
        self,
        cmd: list[str],
        prefix: str = "",
    ) -> Generator[str, None, int]:
        """Stream command output line by line."""
```

### 2. ContainerRuntime (core/runtime.py)

Abstraction over podman/docker commands.

```python
class ContainerRuntime:
    def __init__(self, process: ProcessRunner, prefer_podman: bool = True):
        self.process = process
        self.cmd = self._detect_runtime(prefer_podman)
        self.compose_cmd = f"{self.cmd}-compose"

    def _detect_runtime(self, prefer_podman: bool) -> str:
        """Detect available container runtime."""

    # Container operations
    def ps(self, all: bool = False, format: str | None = None) -> list[Container]: ...
    def stop(self, name: str, timeout: int = 10) -> bool: ...
    def rm(self, name: str, force: bool = False) -> bool: ...
    def run(self, image: str, name: str, **kwargs) -> str: ...
    def logs(self, name: str, tail: int | None = None) -> str: ...
    def exec(self, name: str, cmd: list[str]) -> CommandResult: ...
    def port(self, name: str) -> dict[int, int]: ...
    def exists(self, name: str) -> bool: ...

    # Compose operations
    def compose_up(self, file: Path, services: list[str] | None = None, detach: bool = True) -> bool: ...
    def compose_down(self, file: Path, volumes: bool = False, remove_orphans: bool = True) -> bool: ...
    def compose_build(self, file: Path, services: list[str] | None = None, no_cache: bool = False) -> bool: ...

    # Image operations
    def build(self, context: Path, tag: str, file: Path | None = None, no_cache: bool = False) -> bool: ...
    def images(self, filter: str | None = None) -> list[Image]: ...
    def rmi(self, image: str, force: bool = False) -> bool: ...
    def prune_images(self, all: bool = False) -> None: ...
    def prune_system(self, all: bool = False, volumes: bool = False) -> None: ...

    # Pod operations (podman-specific)
    def pod_rm(self, name: str | None = None, all: bool = False, force: bool = False) -> bool: ...
```

### 3. ContainerManager (services/containers.py)

High-level container lifecycle management.

```python
class ContainerManager:
    # Required ports for the application
    REQUIRED_PORTS: ClassVar[dict[int, str]] = {
        5432: "PostgreSQL",
        6379: "Redis",
        8000: "Backend API",
        8091: "LLM",
        8092: "Florence",
        8093: "CLIP",
        8094: "Enrichment",
        8095: "YOLO26",
    }

    # Container name patterns to match
    PROJECT_PATTERNS: ClassVar[list[str]] = [
        "nemotron", "security", "ai-yolo", "ai-llm",
        "ai-florence", "ai-clip", "ai-enrichment",
        "backend", "frontend", "postgres", "redis",
    ]

    def __init__(self, runtime: ContainerRuntime, config: DeployConfig):
        self.runtime = runtime
        self.config = config

    async def stop_all(self) -> None:
        """Stop all project containers in correct order."""

    async def stop_standalone(self) -> None:
        """Stop containers started with 'run' (not compose)."""

    async def stop_compose(self, compose_file: Path) -> None:
        """Stop containers from a compose file."""

    def verify_ports_available(self) -> PortStatus:
        """Check if required ports are free."""

    def kill_port_holders(self) -> None:
        """Force-kill processes holding required ports."""

    async def start_infrastructure(self) -> None:
        """Start postgres and redis."""

    async def start_ai_services(self) -> None:
        """Start all AI services with GPU assignments."""

    async def start_backend(self) -> None:
        """Start backend service."""

    async def start_frontend(self) -> None:
        """Start frontend service."""

    def get_status(self) -> dict[str, ContainerStatus]:
        """Get status of all project containers."""
```

### 4. ImageBuilder (services/builder.py)

Image building with parallel support.

```python
class ImageBuilder:
    AI_SERVICES: ClassVar[list[str]] = [
        "ai-yolo26", "ai-llm", "ai-florence", "ai-clip", "ai-enrichment"
    ]

    def __init__(self, runtime: ContainerRuntime, config: DeployConfig):
        self.runtime = runtime
        self.config = config

    async def build_base(self) -> BuildResult:
        """Build the base image."""

    async def build_core(self) -> dict[str, BuildResult]:
        """Build backend and frontend images."""

    async def build_ai_parallel(self) -> dict[str, BuildResult]:
        """Build all AI images in parallel."""

    async def build_ai_single(self, service: str) -> BuildResult:
        """Build a single AI service image."""
```

### 5. DeployOrchestrator (orchestrator.py)

Main workflow coordinator.

```python
class DeployOrchestrator:
    """Coordinates the full deployment workflow."""

    def __init__(
        self,
        config: DeployConfig,
        containers: ContainerManager,
        builder: ImageBuilder,
        health: HealthChecker,
        tensorrt: TensorRTBuilder,
        git: GitManager,
        database: DatabaseManager,
        storage: StorageManager,
    ):
        self.config = config
        self.containers = containers
        # ... etc

    async def deploy(self) -> DeployResult:
        """Execute full deployment workflow."""
        try:
            await self._pre_flight_checks()
            await self._stop_phase()
            await self._build_phase()
            await self._start_phase()
            await self._post_deploy()
            await self._verify_phase()
            return DeployResult(success=True)
        except DeployError as e:
            return DeployResult(success=False, error=str(e))

    async def _pre_flight_checks(self) -> None:
        """Git pull, CI check, prerequisites."""

    async def _stop_phase(self) -> None:
        """Stop containers, verify ports, reset storage if needed."""

    async def _build_phase(self) -> None:
        """Build images (base, core, AI parallel)."""

    async def _start_phase(self) -> None:
        """Start all services in correct order."""

    async def _post_deploy(self) -> None:
        """Migrations, seeding, TensorRT rebuild."""

    async def _verify_phase(self) -> None:
        """Health checks and final verification."""
```

## Configuration Model

```python
# models.py
from enum import Enum
from pydantic import BaseModel, Field
from pathlib import Path

class DeployMode(str, Enum):
    LOCAL = "local"    # Build all images locally
    HYBRID = "hybrid"  # GHCR core + local AI
    GHCR = "ghcr"      # All from GHCR (no AI)

class DeployConfig(BaseModel):
    """Deployment configuration."""

    # CLI options
    mode: DeployMode = DeployMode.LOCAL
    keep_volumes: bool = False
    reset_storage: bool = False
    skip_git_pull: bool = False
    dry_run: bool = False
    seed_files_count: int = 0
    image_tag: str = "latest"

    # From .env
    project_root: Path
    compose_file_prod: Path
    compose_file_ghcr: Path

    # Database
    postgres_user: str = "security"
    postgres_password: str
    postgres_db: str = "security"
    database_url: str

    # Redis
    redis_password: str = ""

    # Paths
    ai_models_path: Path
    foscam_base_path: Path

    # Ports
    api_port: int = 8000
    frontend_port: int = 8444
    yolo26_port: int = 8095
    llm_port: int = 8091
    florence_port: int = 8092
    clip_port: int = 8093
    enrichment_port: int = 8094

    # GPU assignments
    gpu_ai_services: int = 1
    gpu_llm: int = 0
    gpu_florence: int = 0
    gpu_clip: int = 1
    gpu_enrichment: int = 1

    @classmethod
    def from_env(cls, project_root: Path, **cli_overrides) -> "DeployConfig":
        """Load config from .env file with CLI overrides."""
```

## CLI Interface

```python
# cli.py
import typer
from rich.console import Console

app = typer.Typer(
    name="redeploy",
    help="Deploy Home Security Intelligence services",
    no_args_is_help=True,
)
console = Console()

@app.command()
def deploy(
    mode: DeployMode = typer.Option(
        DeployMode.LOCAL,
        "--mode", "-m",
        help="Deployment mode",
    ),
    keep_volumes: bool = typer.Option(
        False,
        "--keep-volumes",
        help="Preserve database volumes",
    ),
    reset_storage: bool = typer.Option(
        False,
        "--reset-storage",
        help="Reset container storage (nuclear option)",
    ),
    no_git_pull: bool = typer.Option(
        False,
        "--no-git-pull",
        help="Skip pulling latest from origin/main",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run", "-n",
        help="Show what would be done without doing it",
    ),
    qa: bool = typer.Option(
        False,
        "--qa",
        help="QA mode: --keep-volumes --seed-files=100",
    ),
    seed_files: int = typer.Option(
        0,
        "--seed-files",
        help="Number of files to touch for seeding",
    ),
    tag: str = typer.Option(
        "latest",
        "--tag",
        help="Image tag for GHCR images",
    ),
):
    """Full redeploy of all services."""
    # Build config
    config = DeployConfig.from_env(
        project_root=Path.cwd(),
        mode=mode,
        keep_volumes=keep_volumes or qa,
        reset_storage=reset_storage,
        skip_git_pull=no_git_pull,
        dry_run=dry_run,
        seed_files_count=100 if qa else seed_files,
        image_tag=tag,
    )

    # Build dependency tree
    process = ProcessRunner(dry_run=config.dry_run, console=console)
    runtime = ContainerRuntime(process)
    containers = ContainerManager(runtime, config)
    builder = ImageBuilder(runtime, config)
    health = HealthChecker(config)
    tensorrt = TensorRTBuilder(runtime, config)
    git = GitManager(process, config)
    database = DatabaseManager(process, config)
    storage = StorageManager(runtime, config)

    # Create orchestrator and run
    orchestrator = DeployOrchestrator(
        config=config,
        containers=containers,
        builder=builder,
        health=health,
        tensorrt=tensorrt,
        git=git,
        database=database,
        storage=storage,
    )

    result = asyncio.run(orchestrator.deploy())
    raise typer.Exit(0 if result.success else 1)


@app.command()
def stop():
    """Stop all containers without redeploying."""

@app.command()
def status():
    """Show status of all services."""

@app.command()
def logs(service: str, follow: bool = False, tail: int = 100):
    """View logs for a service."""
```

## Error Handling

```python
# models.py
class DeployError(Exception):
    """Base exception for deployment errors."""

class PortConflictError(DeployError):
    """Required ports are in use."""

class BuildError(DeployError):
    """Image build failed."""

class HealthCheckError(DeployError):
    """Service health check failed."""

class StorageError(DeployError):
    """Container storage operation failed."""
```

## Testing Strategy

```python
# tests/unit/scripts/redeploy/test_containers.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_runtime():
    runtime = MagicMock(spec=ContainerRuntime)
    runtime.ps.return_value = []
    return runtime

@pytest.fixture
def container_manager(mock_runtime, deploy_config):
    return ContainerManager(mock_runtime, deploy_config)

class TestContainerManager:
    def test_verify_ports_all_free(self, container_manager, mock_runtime):
        # No processes on ports
        mock_runtime.process.run.return_value = CommandResult(0, "", "", 0.1)
        status = container_manager.verify_ports_available()
        assert status.all_free

    def test_verify_ports_postgres_in_use(self, container_manager):
        # Port 5432 in use
        ...

    async def test_stop_all_stops_in_order(self, container_manager, mock_runtime):
        await container_manager.stop_all()
        # Verify stop order: standalone -> compose -> pods
        ...
```

## Implementation Order

1. **Phase 1: Core Infrastructure**

   - [ ] `models.py` - Enums, config, exceptions
   - [ ] `core/output.py` - Console output helpers
   - [ ] `core/process.py` - ProcessRunner
   - [ ] `core/runtime.py` - ContainerRuntime

2. **Phase 2: Services**

   - [ ] `services/containers.py` - ContainerManager
   - [ ] `services/storage.py` - StorageManager
   - [ ] `services/health.py` - HealthChecker

3. **Phase 3: Build System**

   - [ ] `services/builder.py` - ImageBuilder
   - [ ] `services/tensorrt.py` - TensorRTBuilder

4. **Phase 4: Supporting Services**

   - [ ] `services/git.py` - GitManager
   - [ ] `services/database.py` - DatabaseManager

5. **Phase 5: Orchestration**

   - [ ] `orchestrator.py` - DeployOrchestrator
   - [ ] `cli.py` - Typer CLI

6. **Phase 6: Testing & Migration**
   - [ ] Unit tests for each service
   - [ ] Integration tests
   - [ ] Deprecate bash script

## Dependencies

```toml
# Add to pyproject.toml [project.optional-dependencies]
deploy = [
    "typer[all]>=0.9.0",
    "rich>=13.0.0",
    "httpx>=0.25.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
]
```

## Open Questions

1. **Async everywhere or selective?** - Currently planning async for operations that benefit from parallelism (builds, health checks). Sync for simple commands.

2. **Keep bash for TensorRT?** - The TensorRT rebuild runs inside a container. Could keep as bash script called via subprocess, or rewrite in Python.

3. **Config file vs CLI only?** - Currently all config from .env + CLI. Should we support a `redeploy.yaml` config file?

4. **Backwards compatibility?** - Keep `redeploy.sh` as deprecated wrapper that calls Python? Or clean break?
