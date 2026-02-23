"""Deployment phase implementations. See deploy.py for orchestration."""

from __future__ import annotations

import json
import os
import resource
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from setup_lib.core import check_port_available, generate_password


def _run_with_timeout(
    cmd: list[str],
    timeout: int = 30,
    capture_output: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess:
    """Run subprocess with timeout; on TimeoutExpired, return failed result and continue."""
    try:
        return subprocess.run(
            cmd,  # noqa: S603
            capture_output=capture_output,
            text=text,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=-1,
            stdout="",
            stderr=f"timed out after {timeout}s",
        )
from setup_lib.deploy import DeployConfig, DeployPhase, DeployResult, compose_run
from setup_lib.healthcheck import check_service_health, poll_endpoint
from setup_lib.rootful_services import (
    CADVISOR_SERVICE_NAME,
    DCGM_SERVICE_NAME,
    _is_service_installed,
    _run_sudo,
)


def _get_compose_image(config: DeployConfig, service: str) -> str | None:
    """Resolve the image name for a compose service (matches compose project-service naming).

    Uses COMPOSE_PROJECT_NAME from env if set, otherwise the project directory name.
    Falls back to podman images lookup if the derived name is not found.
    """
    project_name = config.env.get("COMPOSE_PROJECT_NAME") or config.project_root.name
    derived = f"{project_name}-{service}:latest"
    # Verify image exists
    result = subprocess.run(
        ["podman", "images", "-q", derived],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return derived
    # Fallback: find by service name pattern (handles docker.io/library/ prefix)
    result = subprocess.run(
        ["podman", "images", "--format", "{{.Repository}}:{{.Tag}}", "--filter", f"reference=*{service}*"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().splitlines()[0]
    return None


# ---------------------------------------------------------------------------
# Phase 1: Stop everything
# ---------------------------------------------------------------------------


def phase_stop(config: DeployConfig) -> DeployResult:
    """Stop all containers, legacy services, and clean up stale state."""
    # Ensure podman uses correct storage before any podman commands
    _ensure_rootless_storage(config)

    project_name = config.project_root.name

    # Compose down + rm (short timeout — can hang if storage locked)
    compose_run(config, "down", capture=True, timeout=60)
    compose_run(config, "rm", "-f", capture=True, timeout=60)

    # Stop legacy systemd user services (container-postgres, container-redis)
    subprocess.run(
        ["systemctl", "--user", "stop", "container-postgres.service", "container-redis.service"],  # noqa: S607
        capture_output=True,
        check=False,
    )
    subprocess.run(
        ["systemctl", "--user", "disable", "container-postgres.service", "container-redis.service"],  # noqa: S607
        capture_output=True,
        check=False,
    )

    # Kill orphaned rootlessport processes that hold port bindings
    subprocess.run(
        ["pkill", "-u", str(os.getuid()), "rootlessport"],  # noqa: S607
        capture_output=True,
        check=False,
    )
    time.sleep(1)

    # Stop rootful dcgm-exporter
    _run_sudo(["systemctl", "stop", "dcgm-exporter"], check=False)

    # Destroy volumes if requested
    if config.destroy_volumes:
        print("  Destroying volumes...")
        _run_with_timeout(["podman", "volume", "prune", "-f"], timeout=60)

    # Remove stale network (avoids "incorrect label" errors on recreate)
    # Use timeout — network rm can hang when network is in use
    net_result = _run_with_timeout(
        ["podman", "network", "rm", f"{project_name}_security-net"],
        timeout=15,
    )
    if net_result.returncode != 0:
        if "timed out" in (net_result.stderr or ""):
            print("  WARNING: podman network rm timed out (15s) — continuing")
        # Non-fatal; compose may recreate network

    # Detect corrupted container storage (Podman 5.x+ only)
    # Use timeout to avoid hanging (podman system check can block on storage locks)
    try:
        check_result = subprocess.run(
            ["podman", "system", "check"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        print("  WARNING: podman system check timed out (30s) — skipping storage verification")
        check_result = subprocess.CompletedProcess(
            args=["podman", "system", "check"], returncode=0, stdout="", stderr=""
        )

    # Only treat as corruption if the command exists (rc=0 or known error).
    # "unrecognized command" (Podman 4.x) is not corruption — skip it.
    is_unrecognized = "unrecognized command" in (check_result.stderr or "")
    # Skip repair/reset when failure is due to permissions (e.g. /var/lib/containers
    # owned by root). Running reset in that case can leave storage in a bad state.
    stderr_lower = (check_result.stderr or "").lower()
    is_permission_error = "permission denied" in stderr_lower or "permission" in stderr_lower
    if check_result.returncode != 0 and not is_unrecognized and not is_permission_error:
        print("  WARNING: Corrupted container storage detected!")
        if check_result.stderr:
            for line in check_result.stderr.strip().splitlines()[:5]:
                print(f"    {line}")
        # Try non-destructive repair first (preserves images and build cache).
        # Only fall back to full reset if repair fails.
        print("  Attempting non-destructive repair...")
        try:
            repair_result = subprocess.run(
                ["podman", "system", "check", "--repair", "--force"],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            print("  Repair timed out (120s) — skipping")
            repair_result = subprocess.CompletedProcess(
                args=["podman", "system", "check", "--repair", "--force"],
                returncode=1,
                stdout="",
                stderr="timeout",
            )
        if repair_result.returncode == 0:
            print("  Storage repaired (images preserved).")
        else:
            # Repair flag may not exist on older Podman — fall back to reset
            print("  Repair failed, falling back to full reset...")
            reset_result = _run_with_timeout(
                ["podman", "system", "reset", "--force"],
                timeout=60,
            )
            if reset_result.returncode != 0 and "timed out" in (reset_result.stderr or ""):
                print("  WARNING: podman system reset timed out — continuing")
            # Restart the podman socket after reset
            subprocess.run(
                ["systemctl", "--user", "restart", "podman.socket"],  # noqa: S607
                capture_output=True,
                check=False,
                timeout=10,
            )
            time.sleep(2)
            print("  Storage reset complete. All images will be rebuilt.")

    # Verify critical ports are freed
    postgres_port = int(config.env.get("POSTGRES_PORT", "5432"))
    redis_port = int(config.env.get("REDIS_PORT", "6379"))
    ports_free = True
    for port in (postgres_port, redis_port):
        if not check_port_available(port):
            print(f"  WARNING: Port {port} still in use")
            ports_free = False

    if not ports_free:
        return DeployResult(False, "Some ports still in use after cleanup")

    return DeployResult(True, "All containers stopped and ports freed")


# ---------------------------------------------------------------------------
# Phase 2: Prune unused images
# ---------------------------------------------------------------------------


def _get_free_disk_gb() -> float | None:
    """Return free disk space in GB for the root filesystem, or None on error."""
    try:
        import shutil as _shutil
        usage = _shutil.disk_usage("/")
        return usage.free / (1024 ** 3)
    except OSError:
        return None


def phase_prune_images(config: DeployConfig) -> DeployResult:
    """Remove dangling and unused container images to free disk space.

    Runs ``podman image prune -f`` (dangling only) plus removes images not
    referenced by any container.  This is safe to run after phase_stop because
    all project containers have already been stopped and removed.

    Skipped when ``config.skip_prune`` is True or the ``--skip-prune`` flag
    is passed to ``setup.py deploy``.
    """
    if config.skip_prune:
        return DeployResult(True, "Skipping image prune (--skip-prune)")

    free_before = _get_free_disk_gb()

    # Step 1: Remove dangling images (untagged build intermediates)
    dangling_result = _run_with_timeout(
        ["podman", "image", "prune", "-f"],
        timeout=120,
    )
    if "timed out" in (dangling_result.stderr or ""):
        print("  WARNING: dangling image prune timed out (120s) — skipping")

    # Step 2: Remove unused images (not used by any container)
    unused_result = _run_with_timeout(
        ["podman", "image", "prune", "-a", "-f",
         "--filter", "until=1h"],
        timeout=180,
    )
    if "timed out" in (unused_result.stderr or ""):
        print("  WARNING: unused image prune timed out (180s) — partial cleanup only")

    free_after = _get_free_disk_gb()

    if free_before is not None and free_after is not None:
        freed = free_after - free_before
        freed_str = f"{freed:.1f} GB freed" if freed > 0.05 else "no significant space freed"
        print(f"  Disk: {free_after:.1f} GB free ({freed_str})")
        if free_after < 2.0:
            print(f"  WARNING: only {free_after:.1f} GB free — build may fail. Consider removing unused models.")
        return DeployResult(True, f"Image prune complete ({freed_str}, {free_after:.1f} GB free)")

    return DeployResult(True, "Image prune complete")


# ---------------------------------------------------------------------------
# Phase 3: Build images  (was Phase 2)
# ---------------------------------------------------------------------------


def _detect_podman_socket() -> str:
    """Detect the rootless podman socket path for the current user.

    Returns the path like /run/user/<uid>/podman/podman.sock.
    """
    uid = os.getuid()
    return f"/run/user/{uid}/podman/podman.sock"


def _ensure_rootless_storage(config: DeployConfig) -> None:
    """Ensure rootless Podman uses project owner's storage, not /var/lib/containers.

    Uses the project directory owner's uid so podman runs correctly when deploy
    is invoked by root (e.g. CI) but the project belongs to a regular user.
    Sets CONTAINERS_STORAGE_CONF so all podman subprocesses use this config.
    """
    try:
        stat_info = config.project_root.stat()
        owner_uid = stat_info.st_uid
    except OSError:
        owner_uid = os.getuid()

    # Root's /run/user/0 often doesn't exist; use rootful paths when running as root
    if owner_uid == 0:
        return

    try:
        import pwd

        owner_home = Path(pwd.getpwuid(owner_uid).pw_dir)
    except (KeyError, ImportError):
        owner_home = Path.home()

    config_dir = owner_home / ".config" / "containers"
    storage_conf = config_dir / "storage.conf"
    storage_root = owner_home / ".local" / "share" / "containers" / "storage"
    run_root = Path(f"/run/user/{owner_uid}/containers")

    content = f"""# Rootless Podman storage — created by setup.py deploy
# Ensures /var/lib/containers is not used (permission denied)

[storage]
driver = "overlay"
runroot = "{run_root}"
graphroot = "{storage_root}"
"""
    config_dir.mkdir(parents=True, exist_ok=True)
    storage_conf.write_text(content)

    # Force all podman invocations to use this config
    conf_path = str(storage_conf.resolve())
    os.environ["CONTAINERS_STORAGE_CONF"] = conf_path
    config.env["CONTAINERS_STORAGE_CONF"] = conf_path


def _ensure_podman_socket(config: DeployConfig) -> None:
    """Ensure the rootless podman socket is active and PODMAN_SOCKET is set.

    The docker-compose plugin requires the podman socket at
    /run/user/<uid>/podman/podman.sock to communicate with podman.
    Detects the correct path from the current UID and exports it
    so docker-compose.prod.yml can reference ${PODMAN_SOCKET}.
    """
    # Auto-detect socket path if not already set
    socket_path = config.env.get("PODMAN_SOCKET") or _detect_podman_socket()
    config.env["PODMAN_SOCKET"] = socket_path
    os.environ["PODMAN_SOCKET"] = socket_path

    # Persist to .env so manual `podman compose` commands work outside setup.py
    env_file = config.project_root / ".env"
    if env_file.exists():
        content = env_file.read_text()
        if "PODMAN_SOCKET=" not in content:
            with env_file.open("a") as f:
                f.write(f"\nPODMAN_SOCKET={socket_path}\n")

    result = subprocess.run(
        ["systemctl", "--user", "is-active", "podman.socket"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout.strip() == "active":
        return

    print("  Podman socket not running — starting it...")
    subprocess.run(
        ["systemctl", "--user", "enable", "--now", "podman.socket"],  # noqa: S607
        capture_output=True,
        check=False,
    )
    time.sleep(1)


def phase_build(config: DeployConfig) -> DeployResult:
    """Build container images."""
    # docker-compose plugin needs the podman socket (even with --skip-build,
    # later phases like infrastructure/application also use compose)
    _ensure_podman_socket(config)

    if config.skip_build:
        return DeployResult(True, "Skipping image builds (--skip-build)")

    # Detect CUDA architecture
    cuda_args: list[str] = []
    cuda_arch = config.env.get("CUDA_ARCHITECTURES", "")

    if cuda_arch:
        cuda_args = ["--build-arg", f"CUDA_ARCHITECTURES={cuda_arch}"]
        print(f"  GPU architecture: {cuda_arch[0]}.{cuda_arch[1:]} (from .env)")
    else:
        # Fallback: detect via nvidia-smi
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                cap = result.stdout.strip().splitlines()[0].replace(".", "")
                cuda_args = ["--build-arg", f"CUDA_ARCHITECTURES={cap}"]
                print(f"  GPU architecture: {cap[0]}.{cap[1:]} (detected)")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    if not cuda_args:
        print("  GPU not detected - building for common architectures (slower)")

    # Build base image first (backend depends on it)
    print("  Building base image...")
    base_cmd = [
        "podman",
        "build",
        "--no-cache",
        "--ulimit",
        "nofile=65536:65536",
        "-f",
        str(config.project_root / "docker" / "base.Dockerfile"),
        "-t",
        "ghcr.io/mikesvoboda/nemotron-base:latest",
        str(config.project_root),
    ]
    build_env = {**os.environ, **config.env}
    if config.verbose:
        result = subprocess.run(base_cmd, check=False, text=True, env=build_env)
    else:
        result = subprocess.run(
            base_cmd,
            capture_output=True,
            text=True,
            check=False,
            env=build_env,
        )
        if result.stdout:
            last_line = result.stdout.strip().splitlines()[-1:]
            if last_line:
                print(f"  {last_line[0]}")

    if result.returncode != 0:
        return DeployResult(False, "Base image build failed")

    # Build application services with --no-cache
    # Use CONTAINERS_CONF_OVERRIDE so compose build inherits nofile=65536:65536
    # (avoids "setrlimit RLIMIT_NOFILE: Operation not permitted" in rootless)
    ulimit_conf = config.project_root / "docker" / "containers-build-ulimit.conf"
    if ulimit_conf.exists():
        config.env["CONTAINERS_CONF_OVERRIDE"] = str(ulimit_conf.resolve())

    print("  Building application services (--no-cache)...")
    ok = compose_run(
        config,
        "build",
        "--no-cache",
        "backend",
        "frontend",
        "ai-gateway",
        stream=config.verbose,
        timeout=900,
    )
    if not ok:
        return DeployResult(False, "Application service build failed")

    # Build ai-llm WITH cache (just llama.cpp, no app code)
    print("  Building ai-llm (cached)...")
    ok = compose_run(
        config,
        "build",
        *cuda_args,
        "ai-llm",
        stream=config.verbose,
        timeout=900,
    )
    if not ok:
        return DeployResult(False, "ai-llm build failed")

    return DeployResult(True, "All images built")


# ---------------------------------------------------------------------------
# Phase 3: Export models for Triton
# ---------------------------------------------------------------------------

CORE_MODELS = [
    "yolo26",
    "clip",
    "clip_text",
    "pose",
    "threat",
    "reid",
    "depth",
    "pet",
    "vehicle",
    "demographics_age",
    "demographics_gender",
    "fashion_clip",
    "stgcn_action",
]


def phase_export(config: DeployConfig) -> DeployResult:
    """Export ONNX/TensorRT models for Triton Inference Server."""
    triton_cache = config.env.get("AI_MODELS_PATH", "/export/ai_models") + "/triton"

    # Count missing models
    missing = 0
    for model in CORE_MODELS:
        model_dir = Path(triton_cache) / model / "1"
        if not (model_dir / "model.onnx").exists() and not (model_dir / "model.plan").exists():
            missing += 1

    # Handle skip/force logic
    if config.skip_export and missing == 0:
        return DeployResult(True, f"All {len(CORE_MODELS)} models cached")

    if config.force_export:
        missing = len(CORE_MODELS)

    if missing == 0:
        return DeployResult(
            True,
            f"All {len(CORE_MODELS)} core models cached (use --force-export to rebuild)",
        )

    if config.skip_export and missing > 0:
        print(f"  {missing} models missing - automatic export required")
        # Override skip since models are missing

    # Ensure cache directory exists
    Path(triton_cache).mkdir(parents=True, exist_ok=True)

    # Resolve ai-gateway image name (matches compose project-service naming)
    ai_gateway_image = _get_compose_image(config, "ai-gateway")
    if not ai_gateway_image:
        return DeployResult(False, "Could not resolve ai-gateway image (run build phase first)")

    # Run export in background
    gpu_device = config.env.get("GPU_AI_SERVICES", "1")
    export_cmd = [
        "podman",
        "run",
        "--rm",
        "--name",
        "ai-gateway-export",
        "--entrypoint",
        "bash",
        "--device",
        f"nvidia.com/gpu={gpu_device}",
        "--security-opt",
        "label=disable",
        "-e",
        "CUDA_VISIBLE_DEVICES=0",
        "-e",
        "MODELS_ZOO=/models/zoo",
        "-e",
        "CACHE_DIR=/models/cache",
        "-e",
        "REPO_DIR=/models/repository",
        "-v",
        "/export/ai_models/model-zoo:/models/zoo:ro",
        "-v",
        f"{triton_cache}:/models/cache",
        ai_gateway_image,
        "-c",
        "cd /app/gateway/export && bash export_all.sh",
    ]

    try:
        proc = subprocess.Popen(
            export_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        config._export_process = proc
    except FileNotFoundError:
        return DeployResult(False, "podman not found for model export")

    return DeployResult(
        True,
        f"Model export started in background ({missing} models, PID {proc.pid})",
    )


# ---------------------------------------------------------------------------
    # Phase 5: Start infrastructure + observability
# ---------------------------------------------------------------------------

_MONITORING_SERVICES = [
    "prometheus",
    "grafana",
    "loki",
    "tempo",
    "alertmanager",
    # alloy started separately — memlock failure must not block other services
    "node-exporter",
    "pyroscope",
    "blackbox-exporter",
    "json-exporter",
    "redis-exporter",
]

# Alloy requires high memlock for eBPF profiling (8GB).  Rootless Podman
# cannot exceed the calling user's memlock ulimit, so if the session hasn't
# picked up /etc/security/limits.d/50-memlock.conf yet (needs re-login),
# alloy will fail with RLIMIT_MEMLOCK.  We start it in isolation so the
# failure doesn't cascade to grafana, frontend, or other services.
_ALLOY_MEMLOCK_BYTES = 8_589_934_592  # 8 GB — must match docker-compose.prod.yml

# Application services started in Phase 5 (dependency order matters for retry).
# ai-llm must start first — backend depends on it via service_healthy.
_APP_SERVICES = ("ai-llm", "ai-gateway", "backend", "frontend")


def phase_infrastructure(config: DeployConfig) -> DeployResult:
    """Start infrastructure (postgres, redis, go2rtc) and monitoring stack."""
    # Ensure backend data directories exist (thumbnails for video processor)
    backend_data = config.project_root / "backend" / "data"
    (backend_data / "thumbnails").mkdir(parents=True, exist_ok=True)

    # Ensure FOSCAM_BASE_PATH exists and is writable by container user (persistent)
    foscam_path = Path(config.env.get("FOSCAM_BASE_PATH", "/export/foscam"))
    host_uid = config.env.get("HOST_UID", "1000")
    host_gid = config.env.get("HOST_GID", "1000")
    if not foscam_path.exists():
        mkdir_result = _run_sudo(["mkdir", "-p", str(foscam_path)], check=False)
        if mkdir_result.returncode != 0:
            print(f"  foscam: failed to create {foscam_path} (run: sudo mkdir -p {foscam_path})")
    if foscam_path.exists():
        chown_result = _run_sudo(["chown", "-R", f"{host_uid}:{host_gid}", str(foscam_path)], check=False)
        if chown_result.returncode == 0:
            print(f"  foscam: {foscam_path} owned by {host_uid}:{host_gid}")
        else:
            print(f"  foscam: {foscam_path} (chown skipped - run: sudo chown -R {host_uid}:{host_gid} {foscam_path})")

    # Core infrastructure (pre-built images only)
    ok = compose_run(
        config,
        "up",
        "-d",
        "--no-build",
        "postgres",
        "redis",
        "go2rtc",
    )
    if not ok:
        return DeployResult(False, "Failed to start core infrastructure")

    print("  Waiting for postgres/redis...")
    time.sleep(10)

    # Monitoring stack — no --no-build (pyroscope has a Dockerfile)
    ok = compose_run(config, "up", "-d", *_MONITORING_SERVICES)
    if not ok:
        print("  WARNING: Some monitoring services failed to start")

    # Start alloy separately — its 8GB memlock can fail without re-login
    soft, _ = resource.getrlimit(resource.RLIMIT_MEMLOCK)
    if soft != resource.RLIM_INFINITY and soft < _ALLOY_MEMLOCK_BYTES:
        print(f"  alloy: skipped (memlock {soft // 1024}KB < 8GB — re-login to apply limits)")
    else:
        alloy_ok = compose_run(config, "up", "-d", "alloy")
        if not alloy_ok:
            print("  alloy: failed to start (check memlock limits)")

    # Restart rootful systemd services
    for service_name, label in [
        (DCGM_SERVICE_NAME, "dcgm-exporter"),
        (CADVISOR_SERVICE_NAME, "cadvisor"),
    ]:
        if _is_service_installed(service_name):
            result = _run_sudo(["systemctl", "restart", service_name], check=False)
            if result.returncode == 0:
                print(f"  {label}: restarted (rootful systemd service)")
            else:
                print(f"  {label}: failed to restart (check: sudo journalctl -u {service_name})")
        else:
            print(f"  {label}: skipped (not installed)")

    # Wait for background model export if running
    if config._export_process is not None:
        print("  Waiting for model export to complete...")
        config._export_process.wait()
        if config._export_process.returncode != 0:
            print("  WARNING: Model export had failures (check logs)")

    print("  Infrastructure + observability up.")
    return DeployResult(True, "Infrastructure and monitoring started")


# ---------------------------------------------------------------------------
# Phase 5: Start application services
# ---------------------------------------------------------------------------


def _check_gpu_available() -> bool:
    """Check if NVIDIA GPU device nodes exist (driver loaded)."""
    return Path("/dev/nvidia0").exists()


def _warn_gpu_missing() -> None:
    """Print a diagnostic when GPU devices are missing."""
    # Check if a driver package is installed but kernel module isn't loaded
    result = subprocess.run(
        ["dpkg", "-l", "nvidia-driver-*"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    driver_installed = result.returncode == 0 and "nvidia-driver" in result.stdout

    if driver_installed:
        # Check kernel module mismatch
        kernel = subprocess.run(
            ["uname", "-r"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        print(f"  WARNING: NVIDIA driver installed but /dev/nvidia0 missing!")
        print(f"    Running kernel: {kernel}")
        print("    Likely cause: kernel/module mismatch — run 'sudo update-grub' and reboot")
        print("    GPU services (ai-llm, ai-gateway) will not start without GPU devices.")
    else:
        print("  WARNING: No NVIDIA GPU detected — GPU services will not start.")


def _wait_container_running(service: str, timeout: int = 30) -> bool:
    """Poll until a compose service container reaches 'running' state.

    Returns True if the container is running within *timeout* seconds.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            ["podman", "ps", "-a", "--filter", f"name={service}", "--format", "{{.State}}"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        state = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
        if state == "running":
            return True
        time.sleep(3)
    return False


def phase_application(config: DeployConfig) -> DeployResult:
    """Start all remaining services (backend, frontend, AI).

    Uses --wait with a 5-minute timeout to allow ai-llm to finish loading
    the 30B model before backend starts (backend depends on ai-llm: service_healthy).
    Only targets _APP_SERVICES to avoid re-triggering alloy (handled in phase 4).
    """
    # Pre-flight: warn if GPU devices are missing (containers will fail)
    if not _check_gpu_available():
        _warn_gpu_missing()

    print("  Starting app services (waiting up to 5min for model loading)...")
    ok = compose_run(
        config, "up", "-d", "--no-build", "--wait", "--wait-timeout", "300", *_APP_SERVICES
    )
    if ok:
        print("  All services started and healthy.")
        return DeployResult(True, "Application services started")

    # compose --wait returned non-zero.  Retry services one-by-one in
    # dependency order and verify each actually reaches "running" state.
    print("  Retrying services in dependency order...")
    stuck: list[str] = []
    for svc in _APP_SERVICES:
        compose_run(config, "up", "-d", "--no-build", svc)
        if _wait_container_running(svc, timeout=60):
            print(f"    {svc}: running")
        else:
            print(f"    {svc}: still not running")
            stuck.append(svc)

    if stuck:
        print(f"  WARNING: {', '.join(stuck)} did not reach running state")
        return DeployResult(True, f"Application services started ({', '.join(stuck)} may still be initializing)")

    print("  All services running after retry.")
    return DeployResult(True, "Application services started")


# ---------------------------------------------------------------------------
# Phase 6: Health check
# ---------------------------------------------------------------------------


def _auto_register_admin(config: DeployConfig) -> None:
    """Register default admin user if this is first deploy."""
    api_port = config.env.get("API_PORT", "8000")
    setup_url = f"http://localhost:{api_port}/api/auth/setup-status"

    try:
        resp = urllib.request.urlopen(setup_url, timeout=5)  # noqa: S310  # nosemgrep: ssrf-requests
        data = json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return

    if not data.get("setup_required"):
        return

    print("  Registering default admin user...")
    password = generate_password()
    payload = json.dumps(
        {
            "username": "admin",
            "email": "admin@local.host",
            "password": password,
        }
    ).encode()

    register_url = f"http://localhost:{api_port}/api/auth/register"
    req = urllib.request.Request(  # noqa: S310
        register_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        urllib.request.urlopen(req, timeout=10)  # noqa: S310  # nosemgrep: ssrf-requests
    except (urllib.error.URLError, OSError):
        print("    Admin registration failed (may already exist)")
        return

    # Save password securely
    secrets_dir = config.project_root / "secrets"
    secrets_dir.mkdir(exist_ok=True)
    pw_file = secrets_dir / "admin-password.txt"
    pw_file.write_text(password)
    pw_file.chmod(0o600)

    print("    Admin registered. Password saved to secrets/admin-password.txt")


def _recover_created_containers(config: DeployConfig) -> None:
    """Detect containers stuck in 'created' state and attempt to start them."""
    result = subprocess.run(
        ["podman", "ps", "-a", "--filter", "status=created", "--format", "{{.Names}}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if not result.stdout.strip():
        return

    stuck = result.stdout.strip().splitlines()
    print(f"  Recovering {len(stuck)} container(s) stuck in 'created' state...")
    for name in stuck:
        # Extract compose service name from container name
        # (e.g. "nemotron-v3-home-security-intelligence-backend-1" -> "backend")
        parts = name.rsplit("-", 1)  # strip trailing "-1"
        svc = parts[0].split(config.project_root.name + "-", 1)[-1] if config.project_root.name in name else name
        compose_run(config, "up", "-d", "--no-build", svc)
        time.sleep(2)
        if _wait_container_running(svc, timeout=30):
            print(f"    {svc}: recovered -> running")
        else:
            print(f"    {svc}: still not running")


def phase_health_check(config: DeployConfig) -> DeployResult:
    """Verify service health and print deployment summary."""
    print("  Health check (waiting for services to initialize)...")

    api_port = config.env.get("API_PORT", "8000")
    gateway_port = config.env.get("AI_GATEWAY_PORT", "8090")
    llm_port = config.env.get("LLM_PORT", "8091")

    # Recover any containers stuck in "created" state before polling endpoints
    _recover_created_containers(config)

    # Auto-register admin (resolves SetupGuard 503s)
    _auto_register_admin(config)

    # Health checks
    services = [
        ("Backend", f"http://localhost:{api_port}/api/system/health", 60),
        ("AI Gateway", f"http://localhost:{gateway_port}/health", 120),
        ("LLM", f"http://localhost:{llm_port}/health", 180),
    ]

    all_healthy = True
    for name, url, timeout in services:
        ready = poll_endpoint(url, timeout=timeout)
        if ready:
            result = check_service_health(name, url, timeout=10)
            print(f"  {name}: healthy ({result['response_time_ms']}ms)")
        else:
            print(f"  {name}: not ready yet")
            all_healthy = False

    # Deployment summary
    try:
        ps_result = subprocess.run(
            ["podman", "ps", "-q"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        container_count = (
            len(ps_result.stdout.strip().splitlines()) if ps_result.stdout.strip() else 0
        )
    except FileNotFoundError:
        container_count = 0

    print()
    print("=== Deploy Complete ===")
    frontend_port = config.env.get("FRONTEND_HTTPS_PORT", "8444")
    print(f"  Frontend: https://localhost:{frontend_port}")
    print(f"  Backend:  http://localhost:{api_port}")
    print(f"  Gateway:  http://localhost:{gateway_port}")
    print()
    print(f"  Containers: {container_count} running")
    print("  GPU usage:")

    try:
        gpu_result = subprocess.run(
            [  # noqa: S607
                "nvidia-smi",
                "--query-gpu=index,name,memory.used,memory.total",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if gpu_result.returncode == 0 and gpu_result.stdout.strip():
            for line in gpu_result.stdout.strip().splitlines():
                print(f"    {line.strip()}")
        else:
            print("    nvidia-smi not available")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("    nvidia-smi not available")

    status = "healthy" if all_healthy else "degraded (some services not ready)"
    return DeployResult(success=all_healthy, message=status)


# ---------------------------------------------------------------------------
# Phase registry
# ---------------------------------------------------------------------------

DEPLOY_PHASES: list[DeployPhase] = [
    DeployPhase(
        name="stop",
        description="Stopping all containers and services",
        func=phase_stop,
    ),
    DeployPhase(
        name="prune_images",
        description="Pruning unused container images to free disk space",
        func=phase_prune_images,
        required=False,
    ),
    DeployPhase(
        name="build",
        description="Building container images",
        func=phase_build,
    ),
    DeployPhase(
        name="export",
        description="Exporting models for Triton",
        func=phase_export,
    ),
    DeployPhase(
        name="infrastructure",
        description="Starting infrastructure + observability",
        func=phase_infrastructure,
    ),
    DeployPhase(
        name="application",
        description="Starting AI + application services",
        func=phase_application,
    ),
    DeployPhase(
        name="health_check",
        description="Health check and deployment verification",
        func=phase_health_check,
        required=False,
    ),
]
