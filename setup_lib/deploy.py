"""Production deployment orchestrator for Home Security Intelligence.

Manages phased container deployment using Podman Compose.
Replaces the bash deploy-gateway.sh with proper error handling,
health check polling, and code reuse from setup_lib.

Usage:
    python setup.py deploy [--destroy-volumes] [--skip-build] [--no-verbose]
    python setup.py deploy --log-file /path/to/deploy.log
    python setup.py deploy --no-log-file
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DeployConfig:
    """Configuration for a deployment run."""

    project_root: Path
    compose_file: str = "docker-compose.prod.yml"
    compose_cmd: list[str] = field(default_factory=list)
    destroy_volumes: bool = False
    skip_build: bool = False
    skip_export: bool = False
    force_export: bool = False
    verbose: bool = True
    env: dict[str, str] = field(default_factory=dict)
    _export_process: subprocess.Popen | None = field(default=None, repr=False)


@dataclass
class DeployResult:
    """Result of a deployment phase."""

    success: bool
    message: str


@dataclass
class DeployPhase:
    """Definition of a deployment phase."""

    name: str
    description: str
    func: Callable[[DeployConfig], DeployResult]
    required: bool = True


def detect_compose_command() -> list[str]:
    """Detect the available compose command.

    Tries podman compose (native, Podman 5.x+) first, then falls back
    to podman-compose (external Python tool, Podman 4.x).

    Returns:
        List of command parts, e.g. ["podman", "compose"] or ["podman-compose"].

    Raises:
        RuntimeError: If no compose command is found.
    """
    # Try native podman compose (Podman 5.x+)
    if shutil.which("podman"):
        try:
            result = subprocess.run(
                ["podman", "compose", "version"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                return ["podman", "compose"]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Try external podman-compose (Podman 4.x), including ~/.local/bin fallback
    local_bin_compose = str(Path.home() / ".local" / "bin" / "podman-compose")
    for compose_candidate in ["podman-compose", local_bin_compose]:
        candidate_path = shutil.which(compose_candidate) or (
            compose_candidate if Path(compose_candidate).is_file() else None
        )
        if candidate_path:
            try:
                result = subprocess.run(
                    [candidate_path, "--version"],  # noqa: S607
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if result.returncode == 0:
                    return [candidate_path]
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

    raise RuntimeError(
        "No compose command found. Install podman-compose or upgrade to Podman 5.x+."
    )


def compose_run(
    config: DeployConfig,
    *args: str,
    capture: bool = False,
    stream: bool = False,
) -> subprocess.CompletedProcess | bool:
    """Run a compose command with the given arguments.

    Args:
        config: Deployment configuration.
        *args: Additional arguments to pass to the compose command.
        capture: If True, capture stdout/stderr and return CompletedProcess.
        stream: If True, stream stdout line-by-line to the terminal.

    Returns:
        CompletedProcess if capture=True, else bool indicating success.
    """
    compose_file_path = str(config.project_root / config.compose_file)
    cmd = [*config.compose_cmd, "-f", compose_file_path, *args]

    env = {**os.environ, **config.env} if config.env else None

    if config.verbose:
        print(f"  $ {' '.join(cmd)}")

    try:
        if stream:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
            for line in proc.stdout:  # type: ignore[union-attr]
                print(f"  {line}", end="")
            proc.wait()
            return proc.returncode == 0

        if capture:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

        result = subprocess.run(
            cmd,
            check=False,
            env=env,
        )
        return result.returncode == 0

    except FileNotFoundError:
        if capture:
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="Command not found"
            )
        return False
    except KeyboardInterrupt:
        print("\n  Cancelled by user")
        return False


def load_env(project_root: Path) -> dict[str, str]:
    """Parse a .env file into a dictionary.

    Handles KEY=VALUE and KEY="VALUE" formats. Skips comments and empty lines.

    Args:
        project_root: Path to the project root containing .env.

    Returns:
        Dictionary of environment variables.
    """
    env_file = project_root / ".env"
    env: dict[str, str] = {}

    if not env_file.exists():
        return env

    for raw_line in env_file.read_text().splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue

        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip()

        # Strip surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]

        env[key] = value

    return env


def run_deploy(config: DeployConfig) -> bool:
    """Run all deployment phases in sequence.

    Args:
        config: Deployment configuration.

    Returns:
        True if all required phases succeeded, False otherwise.
    """
    # Lazy import to avoid circular imports
    from setup_lib.deploy_phases import DEPLOY_PHASES

    total = len(DEPLOY_PHASES)
    passed = 0
    failed = 0

    for i, phase in enumerate(DEPLOY_PHASES, 1):
        print(f"\n[{i}/{total}] {phase.description}...")
        result = phase.func(config)

        if result.success:
            print(f"  OK: {result.message}")
            passed += 1
        elif phase.required:
            print(f"  FAILED: {result.message}")
            print(f"\nDeployment aborted at phase '{phase.name}'.")
            return False
        else:
            print(f"  SKIPPED: {result.message}")
            failed += 1

    print(f"\nDeployment complete: {passed} passed, {failed} skipped.")
    return True
