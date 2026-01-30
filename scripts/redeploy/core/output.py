"""Console output helpers using Rich."""

from collections.abc import Generator
from contextlib import contextmanager

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

# Singleton console instance
console = Console()


def header(text: str) -> None:
    """Print a section header."""
    console.print()
    console.print(f"[bold blue]=== {text} ===[/]")


def step(text: str) -> None:
    """Print a step message."""
    console.print(f"[cyan][STEP][/] {text}")


def success(text: str) -> None:
    """Print a success message."""
    console.print(f"[green][OK][/] {text}")


def fail(text: str) -> None:
    """Print a failure message."""
    console.print(f"[red][FAIL][/] {text}")


def warn(text: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow][WARN][/] {text}")


def info(text: str) -> None:
    """Print an info message."""
    console.print(f"[cyan][INFO][/] {text}")


def dry_run(text: str) -> None:
    """Print a dry-run message."""
    console.print(f"[yellow][DRY-RUN][/] {text}")


def error(text: str) -> None:
    """Print an error message."""
    console.print(f"[bold red][ERROR][/] {text}")


def banner(
    title: str,
    mode: str,
    services: int,
    runtime: str,
    dry_run_mode: bool,
    keep_volumes: bool,
) -> None:
    """Print the startup banner."""
    console.print()
    console.print("[bold blue]" + "=" * 44 + "[/]")
    console.print(f"[bold blue]  {title}[/]")
    console.print("[bold blue]" + "=" * 44 + "[/]")
    console.print()
    console.print(f"Mode:         [cyan]{mode}[/]")
    console.print(f"Services:     [cyan]{services}[/]")
    console.print(f"Runtime:      [cyan]{runtime}[/]")
    console.print(f"Dry Run:      [cyan]{dry_run_mode}[/]")
    console.print(f"Keep Volumes: [cyan]{keep_volumes}[/]")


def destructive_warning(items: list[str], timeout: int = 5) -> None:
    """Print a destructive operation warning with countdown."""
    import time

    console.print()
    console.print("[bold red]  ⚠️  WARNING: DESTRUCTIVE OPERATION  ⚠️[/]")
    console.print()
    console.print("  This will [red]PERMANENTLY DELETE[/]:")
    for item in items:
        console.print(f"    - {item}")
    console.print()
    console.print(f"[yellow]  Press Ctrl+C within {timeout} seconds to cancel...[/]")
    time.sleep(timeout)


def nuclear_warning(items: list[str], timeout: int = 5) -> None:
    """Print a nuclear option warning (even more severe)."""
    import time

    console.print()
    console.print("[bold red]  ⚠️  WARNING: NUCLEAR OPTION  ⚠️[/]")
    console.print()
    console.print("  This will [red]PERMANENTLY DELETE[/]:")
    for item in items:
        console.print(f"    - {item}")
    console.print()
    console.print(f"[yellow]  Press Ctrl+C within {timeout} seconds to cancel...[/]")
    time.sleep(timeout)


def status_table(statuses: dict[str, tuple[str, str]]) -> None:
    """Print a status table.

    Args:
        statuses: Dict of service name -> (status, details)
    """
    table = Table(title="Service Status")
    table.add_column("Service", style="cyan")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    for service, (status, details) in statuses.items():
        if status in ("running", "healthy"):
            status_style = "[green]●[/] " + status
        elif status in ("starting", "unhealthy"):
            status_style = "[yellow]●[/] " + status
        else:
            status_style = "[red]●[/] " + status
        table.add_row(service, status_style, details)

    console.print(table)


def build_summary(results: dict[str, tuple[str, float]]) -> None:
    """Print a build summary table.

    Args:
        results: Dict of service name -> (status, duration_seconds)
    """
    table = Table(title="Build Summary")
    table.add_column("Service", style="cyan")
    table.add_column("Status")
    table.add_column("Duration", justify="right")

    for service, (status, duration) in results.items():
        if status == "success":
            status_style = "[green]✓[/] success"
        elif status == "cached":
            status_style = "[blue]○[/] cached"
        elif status == "skipped":
            status_style = "[yellow]○[/] skipped"
        else:
            status_style = "[red]✗[/] failed"
        table.add_row(service, status_style, f"{duration:.1f}s")

    console.print(table)


@contextmanager
def progress_spinner(description: str) -> Generator[None]:
    """Context manager for a simple spinner."""
    with console.status(f"[cyan]{description}[/]"):
        yield


def create_progress() -> Progress:
    """Create a progress bar for multiple tasks."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def create_build_progress() -> Progress:
    """Create a progress bar optimized for build output."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )
