"""Container image pull integration for setup.py.

Provides functionality to pull container images from GHCR before first startup,
reducing initial startup time.

Usage:
    from setup_lib.image_pull import prompt_and_pull_images
    prompt_and_pull_images(config)
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


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


def get_compose_files() -> list[tuple[str, str, str]]:
    """Get available compose files with descriptions.

    Returns:
        List of tuples: (filename, description, pull_mode)
        pull_mode is "ghcr" for pre-built images, "build" for local builds
    """
    compose_files = []

    # Check for GHCR compose file (full installation)
    if Path("docker-compose.ghcr.yml").exists():
        compose_files.append(
            (
                "docker-compose.ghcr.yml",
                "Full GHCR installation (all services from registry)",
                "ghcr",
            )
        )

    # Check for GHCR core compose file (hybrid)
    if Path("docker-compose.ghcr-core.yml").exists():
        compose_files.append(
            (
                "docker-compose.ghcr-core.yml",
                "GHCR core only (backend/frontend from registry, AI on host)",
                "ghcr",
            )
        )

    # Check for production compose file (local builds)
    if Path("docker-compose.prod.yml").exists():
        compose_files.append(
            (
                "docker-compose.prod.yml",
                "Local builds (build from source)",
                "build",
            )
        )

    return compose_files


def pull_images(compose_file: str, runtime: tuple[str, str]) -> bool:
    """Pull container images for a compose file.

    Args:
        compose_file: Path to the docker-compose file.
        runtime: Tuple of (runtime_name, compose_command).

    Returns:
        True if pull succeeded, False otherwise.
    """
    runtime_name, compose_cmd = runtime

    # Build the command
    if compose_cmd == "docker compose":
        cmd = ["docker", "compose", "-f", compose_file, "pull"]
    else:
        cmd = [compose_cmd, "-f", compose_file, "pull"]

    print(f"Running: {' '.join(cmd)}")
    print()

    try:
        # Run with live output
        result = subprocess.run(  # noqa: S603 - known compose command
            cmd,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        print(f"! {compose_cmd} not found")
        return False
    except KeyboardInterrupt:
        print("\n! Pull cancelled")
        return False


def _validate_compose_path(compose_file: str) -> Path | None:
    """Validate and resolve compose file path.

    Ensures the file is within the current working directory to prevent
    path traversal attacks.

    Args:
        compose_file: Path to the docker-compose file.

    Returns:
        Resolved Path if valid, None otherwise.
    """
    try:
        resolved = Path(compose_file).resolve()
        cwd = Path.cwd().resolve()
        # Ensure path is within current working directory
        if not str(resolved).startswith(str(cwd)):
            return None
        if not resolved.is_file():
            return None
        return resolved
    except (OSError, ValueError):
        return None


def get_image_list(compose_file: str) -> list[str]:
    """Get list of images defined in a compose file.

    Args:
        compose_file: Path to the docker-compose file.

    Returns:
        List of image names/tags.
    """
    images: list[str] = []

    # Validate path to prevent path traversal
    validated_path = _validate_compose_path(compose_file)
    if validated_path is None:
        return images

    try:
        import yaml

        content = validated_path.read_text()
        compose_data = yaml.safe_load(content)

        services = compose_data.get("services", {})
        for service_name, service_config in services.items():
            if "image" in service_config:
                images.append(service_config["image"])
            elif "build" in service_config:
                images.append(f"(build) {service_name}")

    except ImportError:
        # PyYAML not available, try basic parsing
        try:
            content = validated_path.read_text()
            for raw_line in content.splitlines():
                stripped_line = raw_line.strip()
                if stripped_line.startswith("image:"):
                    image = stripped_line.split(":", 1)[1].strip()
                    # Remove quotes if present
                    image = image.strip("'\"")
                    images.append(image)
        except OSError:
            # File read error - return empty list
            pass
    except (OSError, KeyError, TypeError):
        # YAML parsing or file error - return empty list
        pass

    return images


def estimate_pull_size(images: list[str]) -> str:
    """Estimate total download size for images.

    Args:
        images: List of image names.

    Returns:
        Human-readable size estimate.
    """
    # Rough size estimates for known images (in MB)
    size_estimates = {
        "postgres": 250,
        "redis": 50,
        "elasticsearch": 800,
        "grafana": 400,
        "prometheus": 200,
        "jaeger": 100,
        "alertmanager": 50,
        "loki": 100,
        "node-exporter": 30,
        "cadvisor": 100,
        "alloy": 200,
        "go2rtc": 50,
        # AI services (larger due to CUDA/TensorRT)
        "backend": 2000,
        "frontend": 200,
        "ai-yolo26": 8000,
        "ai-llm": 5000,
        "ai-florence": 6000,
        "ai-clip": 6000,
        "ai-enrichment": 6000,
    }

    total_mb = 0
    for image in images:
        image_lower = image.lower()
        for key, size in size_estimates.items():
            if key in image_lower:
                total_mb += size
                break
        else:
            # Unknown image, assume 200MB
            total_mb += 200

    if total_mb >= 1024:
        return f"~{total_mb / 1024:.1f} GB"
    return f"~{total_mb} MB"


def prompt_and_pull_images(_config: dict) -> None:  # noqa: PLR0911 - interactive function with early returns
    """Prompt user and pull container images.

    Args:
        _config: Configuration dictionary (reserved for future use).
    """
    print()
    print("=" * 60)
    print("Container Image Pull")
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

    # Get available compose files
    compose_files = get_compose_files()
    if not compose_files:
        print("! No compose files found")
        print("  Expected one of:")
        print("    - docker-compose.ghcr.yml (full GHCR installation)")
        print("    - docker-compose.prod.yml (local builds)")
        return

    # Show options
    print("Available deployment modes:")
    print()
    for i, (filename, description, pull_mode) in enumerate(compose_files, 1):
        mode_tag = "[GHCR]" if pull_mode == "ghcr" else "[BUILD]"
        print(f"  {i}. {filename}")
        print(f"     {description} {mode_tag}")

        # Show image count and estimated size for GHCR files
        if pull_mode == "ghcr":
            images = get_image_list(filename)
            ghcr_images = [
                img for img in images if "ghcr.io" in img or not img.startswith("(build)")
            ]
            if ghcr_images:
                size_est = estimate_pull_size(images)
                print(f"     {len(ghcr_images)} images to pull, {size_est} estimated")
        print()

    print(f"  {len(compose_files) + 1}. Skip (pull images later)")
    print()

    # Prompt for selection
    choice = input("Select deployment mode [1]: ").strip() or "1"

    try:
        choice_num = int(choice)
        if choice_num == len(compose_files) + 1:
            print()
            print("Skipping image pull.")
            print("To pull later, run:")
            for filename, _, pull_mode in compose_files:
                if pull_mode == "ghcr":
                    if compose_cmd == "docker compose":
                        print(f"  docker compose -f {filename} pull")
                    else:
                        print(f"  {compose_cmd} -f {filename} pull")
            return

        if choice_num < 1 or choice_num > len(compose_files):
            print("! Invalid selection")
            return

        selected_file, selected_desc, selected_mode = compose_files[choice_num - 1]

    except ValueError:
        print("! Invalid selection")
        return

    print()
    print(f"Selected: {selected_file}")
    print(f"  {selected_desc}")
    print()

    if selected_mode == "build":
        print("This compose file builds images locally instead of pulling from GHCR.")
        print("No images to pull - images will be built on first 'up' command.")
        print()
        print("To build now, run:")
        if compose_cmd == "docker compose":
            print(f"  docker compose -f {selected_file} build")
        else:
            print(f"  {compose_cmd} -f {selected_file} build")
        return

    # Confirm pull
    images = get_image_list(selected_file)
    print(f"This will pull {len(images)} container images.")
    print()

    confirm = input("Proceed with image pull? [y]: ").strip().lower()
    if confirm and confirm not in ("y", "yes"):
        print("Skipping image pull.")
        return

    print()
    print("Pulling images (this may take a while)...")
    print()

    success = pull_images(selected_file, runtime)

    print()
    if success:
        print("+ All images pulled successfully!")
        print()
        print("To start the services, run:")
        if compose_cmd == "docker compose":
            print(f"  docker compose -f {selected_file} up -d")
        else:
            print(f"  {compose_cmd} -f {selected_file} up -d")
    else:
        print("! Some images failed to pull")
        print("  Check your network connection and GHCR access")
        print()
        print("  For private registries, authenticate with:")
        if runtime_name == "podman":
            print("    podman login ghcr.io")
        else:
            print("    docker login ghcr.io")
