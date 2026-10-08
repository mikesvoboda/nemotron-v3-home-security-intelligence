"""Container image preparation for setup.py.

O1.2 (UR-17) retired the GHCR pre-built compose surface: it advertised itself
as an install path while shipping no ``ai-vlm`` service. One install path
remains — ``docker-compose.prod.yml``, which builds backend, frontend and the
AI services from source and pulls only public infrastructure images
(postgres, redis, go2rtc, monitoring) on first ``up``. There is no
private-registry pull flow left to choose, so this module reports the single
path instead of offering a menu.

Usage:
    from setup_lib.image_pull import prompt_and_pull_images
    prompt_and_pull_images(config)
"""

from __future__ import annotations

import shutil
import subprocess


def detect_container_runtime() -> tuple[str, str] | None:
    """Detect available container runtime.

    Returns:
        Tuple of (runtime_name, compose_command) or None if none found.
        Examples: ("podman", "podman-compose"), ("docker", "docker compose")
    """
    # Check for podman first (preferred for rootless containers)
    if shutil.which("podman-compose"):
        return ("podman", "podman-compose")

    # Check for docker compose (v2 plugin style)
    if shutil.which("docker"):
        try:
            result = subprocess.run(
                ["docker", "compose", "version"],  # noqa: S607
                capture_output=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                return ("docker", "docker compose")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Check for docker-compose (v1 standalone)
    if shutil.which("docker-compose"):
        return ("docker", "docker-compose")

    return None


def prompt_and_pull_images(config: dict) -> None:
    """Report how images are obtained for the one supported install path.

    The prod compose stack builds the application images locally; the only
    registry pulls are public infrastructure images, which ``up`` performs.
    Nothing here logs into a private registry any more — that flow retired
    with the GHCR compose surface (O1.2, UR-17).

    Args:
        config: Configuration dictionary (may contain skip_pull flag).
    """
    skip_pull = config.get("skip_pull", False)

    print()
    print("=" * 60)
    print("Container Images")
    print("=" * 60)
    print()

    # Detect container runtime
    runtime = detect_container_runtime()
    if not runtime:
        print("! No container runtime detected")
        print("  Install Docker or Podman to continue")
        print()
        print("  Docker: https://docs.docker.com/get-docker/")
        print("  Podman: https://podman.io/getting-started/installation")
        return

    runtime_name, compose_cmd = runtime
    print(f"Container runtime: {runtime_name} ({compose_cmd})")
    print()

    print("docker-compose.prod.yml is the only application compose file:")
    print("  - backend, frontend and the AI services build from source")
    print("  - postgres, redis and monitoring images pull from public registries")
    print()

    if skip_pull:
        print("Image preparation deferred to the first 'up'.")
        print("To build the application images now:")
        print(f"  {compose_cmd} -f docker-compose.prod.yml build")
        print()
        return

    print("To build the application images now:")
    print(f"  {compose_cmd} -f docker-compose.prod.yml build")
    print("Or just start — 'up' builds what is missing:")
    print(f"  {compose_cmd} -f docker-compose.prod.yml up -d")
    print()
