# Redeploy Script Python Refactor Plan

## Overview

Refactor `scripts/redeploy.sh` (2226 lines bash) into a Python CLI tool with proper structure, testing, and maintainability.

## Target Structure

```
scripts/
├── redeploy.py              # Entry point (thin wrapper)
├── redeploy/
│   ├── __init__.py
│   ├── cli.py               # Typer CLI definition
│   ├── config.py            # Settings, .env loading
│   ├── containers.py        # ContainerManager class
│   ├── builder.py           # ImageBuilder class
│   ├── health.py            # HealthChecker class
│   ├── tensorrt.py          # TensorRT engine builder
│   ├── git.py               # Git operations
│   ├── output.py            # Colored console output
│   └── models.py            # Pydantic models for config
```

## Core Classes

### 1. Config (config.py)

```python
@dataclass
class DeployConfig:
    mode: Literal["local", "hybrid", "ghcr"]
    keep_volumes: bool
    reset_storage: bool
    skip_git_pull: bool
    dry_run: bool
    seed_files_count: int
    image_tag: str

    # From .env
    postgres_password: str
    redis_password: str
    ai_models_path: Path
    foscam_base_path: Path
    # ... etc
```

### 2. ContainerManager (containers.py)

```python
class ContainerManager:
    def __init__(self, runtime: str = "podman"):
        self.runtime = runtime  # podman or docker
        self.compose_cmd = f"{runtime}-compose"

    async def stop_all(self) -> None: ...
    async def stop_standalone(self) -> None: ...
    async def stop_compose(self, file: Path) -> None: ...
    def verify_ports_available(self) -> bool: ...
    def kill_port_holders(self, ports: list[int]) -> None: ...

    async def start_infrastructure(self) -> None: ...
    async def start_ai_services(self) -> None: ...
    async def start_backend(self) -> None: ...
    async def start_frontend(self) -> None: ...

    def get_container_status(self) -> dict[str, str]: ...
```

### 3. ImageBuilder (builder.py)

```python
class ImageBuilder:
    def __init__(self, manager: ContainerManager, config: DeployConfig):
        self.manager = manager
        self.config = config

    async def build_base(self) -> bool: ...
    async def build_core(self) -> bool: ...
    async def build_ai_parallel(self) -> dict[str, bool]: ...
    async def prune_artifacts(self) -> None: ...
    async def reset_storage(self) -> None: ...
```

### 4. HealthChecker (health.py)

```python
class HealthChecker:
    async def wait_healthy(
        self,
        services: list[str],
        timeout: int = 120
    ) -> bool: ...

    async def check_backend(self) -> ServiceHealth: ...
    async def check_ai_services(self) -> dict[str, ServiceHealth]: ...
    async def verify_deployment(self) -> DeploymentStatus: ...
```

### 5. TensorRTBuilder (tensorrt.py)

```python
class TensorRTBuilder:
    async def rebuild_engine(
        self,
        model_path: Path,
        output_path: Path
    ) -> bool: ...
```

## CLI Interface (cli.py)

```python
import typer
from enum import Enum

class Mode(str, Enum):
    LOCAL = "local"
    HYBRID = "hybrid"
    GHCR = "ghcr"

app = typer.Typer(help="Deploy Home Security Intelligence services")

@app.command()
def deploy(
    mode: Mode = typer.Option(Mode.LOCAL, help="Deployment mode"),
    keep_volumes: bool = typer.Option(False, "--keep-volumes", help="Preserve database volumes"),
    reset_storage: bool = typer.Option(False, "--reset-storage", help="Reset container storage (nuclear)"),
    no_git_pull: bool = typer.Option(False, "--no-git-pull", help="Skip git pull"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be done"),
    qa: bool = typer.Option(False, "--qa", help="QA mode: keep-volumes + seed 100 files"),
    seed_files: int = typer.Option(0, "--seed-files", help="Number of files to seed"),
    tag: str = typer.Option("latest", "--tag", help="Image tag for GHCR"),
):
    """Full redeploy of all services."""
    asyncio.run(_deploy(mode, keep_volumes, ...))
```

## Output Formatting (output.py)

```python
from rich.console import Console
from rich.progress import Progress

console = Console()

def header(text: str) -> None:
    console.print(f"\n[bold blue]=== {text} ===[/]")

def step(text: str) -> None:
    console.print(f"[cyan][STEP][/] {text}")

def success(text: str) -> None:
    console.print(f"[green][OK][/] {text}")

def fail(text: str) -> None:
    console.print(f"[red][FAIL][/] {text}")

def warn(text: str) -> None:
    console.print(f"[yellow][WARN][/] {text}")
```

## Migration Strategy

### Phase 1: Scaffold (this session)

1. Create directory structure
2. Implement Config and output modules
3. Implement ContainerManager with stop/verify functionality
4. Create CLI entry point that calls existing bash for builds

### Phase 2: Container Management

1. Migrate start_containers logic
2. Migrate health checks
3. Test container lifecycle

### Phase 3: Build System

1. Migrate image building (base, core)
2. Migrate parallel AI builds
3. Migrate TensorRT builder

### Phase 4: Full Migration

1. Migrate git operations
2. Migrate seeding
3. Remove bash script dependency
4. Add comprehensive tests

## Dependencies

Add to pyproject.toml:

```toml
[project.optional-dependencies]
deploy = [
    "typer>=0.9.0",
    "rich>=13.0.0",
    "httpx>=0.25.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
]

[project.scripts]
redeploy = "scripts.redeploy.cli:app"
```

## Testing Strategy

```python
# tests/unit/scripts/test_containers.py
@pytest.fixture
def mock_subprocess():
    with patch("subprocess.run") as mock:
        yield mock

def test_verify_ports_available_all_free(mock_subprocess):
    mock_subprocess.return_value.stdout = ""
    manager = ContainerManager()
    assert manager.verify_ports_available() is True

def test_verify_ports_available_port_in_use(mock_subprocess):
    mock_subprocess.return_value.stdout = "LISTEN 0 128 *:5432"
    manager = ContainerManager()
    assert manager.verify_ports_available() is False
```

## Backwards Compatibility

- Keep `scripts/redeploy.sh` as legacy (deprecated)
- New entry point: `./scripts/redeploy.py` or `uv run redeploy`
- Same CLI flags for muscle memory
