"""Typer CLI for the redeploy tool."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from scripts.redeploy.core import output
from scripts.redeploy.core.process import ProcessRunner
from scripts.redeploy.core.runtime import ContainerRuntime
from scripts.redeploy.models import DeployConfig, DeployMode, DeployResult
from scripts.redeploy.orchestrator import DeployOrchestrator
from scripts.redeploy.services.builder import ImageBuilder
from scripts.redeploy.services.containers import ContainerManager
from scripts.redeploy.services.database import DatabaseManager
from scripts.redeploy.services.git import GitManager
from scripts.redeploy.services.health import HealthChecker
from scripts.redeploy.services.storage import StorageManager
from scripts.redeploy.services.tensorrt import TensorRTBuilder

app = typer.Typer(
    name="redeploy",
    help="Deploy Home Security Intelligence services.",
    add_completion=False,
    invoke_without_command=True,
)


def _find_project_root() -> Path | None:
    """Find project root by looking for docker-compose.prod.yml."""
    current = Path.cwd()
    while current != current.parent:
        if (current / "docker-compose.prod.yml").exists():
            return current
        current = current.parent
    return None


def mode_callback(value: str) -> DeployMode:
    """Convert string to DeployMode enum."""
    try:
        return DeployMode(value.lower())
    except ValueError as err:
        raise typer.BadParameter(
            f"Invalid mode '{value}'. Choose from: local, hybrid, ghcr"
        ) from err


@app.callback(invoke_without_command=True)
def deploy(
    ctx: typer.Context,
    # Mode selection
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            "-m",
            help="Deployment mode: local (build all), hybrid (GHCR core + local AI), ghcr (all from GHCR)",
        ),
    ] = "local",
    # Volume handling
    keep_volumes: Annotated[
        bool,
        typer.Option(
            "--keep-volumes",
            "-k",
            help="Keep PostgreSQL and Redis volumes (preserve data)",
        ),
    ] = False,
    # Storage reset
    reset_storage: Annotated[
        bool,
        typer.Option(
            "--reset-storage",
            help="Nuclear option: reset container storage to fix corrupted layers",
        ),
    ] = False,
    # Git handling
    no_git_pull: Annotated[
        bool,
        typer.Option(
            "--no-git-pull",
            help="Skip git pull (use current local code)",
        ),
    ] = False,
    # Dry run
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Show what would be done without making changes",
        ),
    ] = False,
    # Seeding
    seed: Annotated[
        int,
        typer.Option(
            "--seed",
            "-s",
            help="Touch N random files to trigger AI pipeline after deploy",
        ),
    ] = 0,
    # Image tag
    tag: Annotated[
        str,
        typer.Option(
            "--tag",
            "-t",
            help="Image tag to use for GHCR images",
        ),
    ] = "latest",
    # Project root override
    project_root: Annotated[
        Path | None,
        typer.Option(
            "--project-root",
            help="Override project root directory",
        ),
    ] = None,
) -> None:
    """Deploy Home Security Intelligence services.

    Examples:

        # Full local build (default)
        uv run scripts/redeploy.py

        # Keep data between deploys
        uv run scripts/redeploy.py --keep-volumes

        # Use GHCR images for core, build AI locally
        uv run scripts/redeploy.py --mode hybrid

        # Dry run to see what would happen
        uv run scripts/redeploy.py --dry-run

        # Fix corrupted container storage
        uv run scripts/redeploy.py --reset-storage

    Subcommands:

        stop    - Stop all containers
        status  - Show container status
        prune   - Clean up build artifacts
    """
    # If a subcommand is being invoked, skip the deploy
    if ctx.invoked_subcommand is not None:
        return

    # Parse mode
    deploy_mode = mode_callback(mode)

    # Determine project root
    if project_root is None:
        project_root = _find_project_root()
        if project_root is None:
            output.fail("Could not find project root (no docker-compose.prod.yml)")
            raise typer.Exit(1)

    # Create configuration
    config = DeployConfig(
        mode=deploy_mode,
        keep_volumes=keep_volumes,
        reset_storage=reset_storage,
        skip_git_pull=no_git_pull,
        dry_run=dry_run,
        seed_files_count=seed,
        image_tag=tag,
        project_root=project_root,
    )

    # Run deployment
    result = asyncio.run(_deploy(config))

    # Exit with appropriate code
    if not result.success:
        raise typer.Exit(1)


async def _deploy(config: DeployConfig) -> DeployResult:
    """Run the deployment workflow.

    Args:
        config: Deployment configuration

    Returns:
        DeployResult with success status
    """

    # Create process runner
    process = ProcessRunner(dry_run=config.dry_run)

    # Create container runtime
    runtime = ContainerRuntime(process=process, prefer_podman=True)

    # Create all services
    containers = ContainerManager(
        runtime=runtime,
        config=config,
    )
    builder = ImageBuilder(
        runtime=runtime,
        config=config,
    )
    health = HealthChecker(config=config)
    tensorrt = TensorRTBuilder(
        runtime=runtime,
        config=config,
    )
    git = GitManager(
        process=process,
        config=config,
    )
    database = DatabaseManager(
        process=process,
        config=config,
    )
    storage = StorageManager(
        runtime=runtime,
        config=config,
    )

    # Create orchestrator
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

    # Run deployment
    return await orchestrator.deploy()


@app.command()
def stop(
    project_root: Annotated[
        Path | None,
        typer.Option(
            "--project-root",
            help="Override project root directory",
        ),
    ] = None,
) -> None:
    """Stop all project containers without redeploying."""
    if project_root is None:
        project_root = _find_project_root()
        if project_root is None:
            output.fail("Could not find project root")
            raise typer.Exit(1)

    config = DeployConfig(project_root=project_root, dry_run=False)
    process = ProcessRunner(dry_run=False)
    runtime = ContainerRuntime(process=process, prefer_podman=True)
    containers = ContainerManager(runtime=runtime, config=config)

    asyncio.run(containers.stop_all())
    output.success("All containers stopped")


@app.command()
def status(
    project_root: Annotated[
        Path | None,
        typer.Option(
            "--project-root",
            help="Override project root directory",
        ),
    ] = None,
) -> None:
    """Show status of all project containers."""
    if project_root is None:
        project_root = _find_project_root()
        if project_root is None:
            output.fail("Could not find project root")
            raise typer.Exit(1)

    config = DeployConfig(project_root=project_root, dry_run=False)

    async def _check_status() -> dict:
        health = HealthChecker(config=config)
        try:
            return await health.check_all()
        finally:
            await health.close()

    # Run health checks
    statuses = asyncio.run(_check_status())

    # Display status table
    status_data = {svc: (s.status.value, s.message or "") for svc, s in statuses.items()}
    output.status_table(status_data)


@app.command()
def prune(
    all_images: Annotated[
        bool,
        typer.Option(
            "--all",
            "-a",
            help="Prune all unused images, not just dangling ones",
        ),
    ] = False,
    project_root: Annotated[
        Path | None,
        typer.Option(
            "--project-root",
            help="Override project root directory",
        ),
    ] = None,
) -> None:
    """Prune build artifacts and unused images."""
    if project_root is None:
        project_root = _find_project_root()
        if project_root is None:
            output.fail("Could not find project root")
            raise typer.Exit(1)

    config = DeployConfig(project_root=project_root, dry_run=False)
    process = ProcessRunner(dry_run=False)
    runtime = ContainerRuntime(process=process, prefer_podman=True)
    storage = StorageManager(runtime=runtime, config=config)

    storage.prune_build_artifacts()
    output.success("Build artifacts pruned")


if __name__ == "__main__":
    app()
