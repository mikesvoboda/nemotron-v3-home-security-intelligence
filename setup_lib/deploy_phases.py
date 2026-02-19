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
from setup_lib.deploy import DeployConfig, DeployPhase, DeployResult, compose_run
from setup_lib.healthcheck import check_service_health, poll_endpoint
from setup_lib.rootful_services import (
    CADVISOR_SERVICE_NAME,
    DCGM_SERVICE_NAME,
    _is_service_installed,
    _run_sudo,
)

# ---------------------------------------------------------------------------
# Phase 1: Stop everything
# ---------------------------------------------------------------------------


def phase_stop(config: DeployConfig) -> DeployResult:
    """Stop all containers, legacy services, and clean up stale state."""
    project_name = config.project_root.name

    # Compose down + rm
    compose_run(config, "down", capture=True)
    compose_run(config, "rm", "-f", capture=True)

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
        subprocess.run(
            ["podman", "volume", "prune", "-f"],  # noqa: S607
            capture_output=True,
            check=False,
        )

    # Remove stale network (avoids "incorrect label" errors on recreate)
    subprocess.run(
        ["podman", "network", "rm", f"{project_name}_security-net"],  # noqa: S607
        capture_output=True,
        check=False,
    )

    # Detect corrupted container storage (Podman 5.x+ only)
    check_result = subprocess.run(
        ["podman", "system", "check"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    # Only treat as corruption if the command exists (rc=0 or known error).
    # "unrecognized command" (Podman 4.x) is not corruption — skip it.
    is_unrecognized = "unrecognized command" in (check_result.stderr or "")
    if check_result.returncode != 0 and not is_unrecognized:
        print("  WARNING: Corrupted container storage detected!")
        if check_result.stderr:
            for line in check_result.stderr.strip().splitlines()[:5]:
                print(f"    {line}")
        # Try non-destructive repair first (preserves images and build cache).
        # Only fall back to full reset if repair fails.
        print("  Attempting non-destructive repair...")
        repair_result = subprocess.run(
            ["podman", "system", "check", "--repair", "--force"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        if repair_result.returncode == 0:
            print("  Storage repaired (images preserved).")
        else:
            # Repair flag may not exist on older Podman — fall back to reset
            print("  Repair failed, falling back to full reset...")
            subprocess.run(
                ["podman", "system", "reset", "--force"],  # noqa: S607
                capture_output=True,
                check=False,
            )
            # Restart the podman socket after reset
            subprocess.run(
                ["systemctl", "--user", "restart", "podman.socket"],  # noqa: S607
                capture_output=True,
                check=False,
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
# Phase 2: Build images
# ---------------------------------------------------------------------------


def _detect_podman_socket() -> str:
    """Detect the rootless podman socket path for the current user.

    Returns the path like /run/user/<uid>/podman/podman.sock.
    """
    uid = os.getuid()
    return f"/run/user/{uid}/podman/podman.sock"


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
        "-f",
        str(config.project_root / "docker" / "base.Dockerfile"),
        "-t",
        "ghcr.io/mikesvoboda/nemotron-base:latest",
        str(config.project_root),
    ]
    if config.verbose:
        result = subprocess.run(base_cmd, check=False, text=True)
    else:
        result = subprocess.run(
            base_cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            last_line = result.stdout.strip().splitlines()[-1:]
            if last_line:
                print(f"  {last_line[0]}")

    if result.returncode != 0:
        return DeployResult(False, "Base image build failed")

    # Build application services with --no-cache
    print("  Building application services (--no-cache)...")
    ok = compose_run(
        config,
        "build",
        "--no-cache",
        "backend",
        "frontend",
        "ai-gateway",
        stream=config.verbose,
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
        "localhost/nemotron-v3-home-security-intelligence_ai-gateway:latest",
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
# Phase 4: Start infrastructure + observability
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


def phase_infrastructure(config: DeployConfig) -> DeployResult:
    """Start infrastructure (postgres, redis, go2rtc) and monitoring stack."""
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


def phase_application(config: DeployConfig) -> DeployResult:
    """Start all remaining services (backend, frontend, AI).

    Uses --wait with a 5-minute timeout to allow ai-llm to finish loading
    the 30B model before backend starts (backend depends on ai-llm: service_healthy).
    """
    print("  Starting all services (waiting up to 5min for model loading)...")
    ok = compose_run(config, "up", "-d", "--no-build", "--wait", "--wait-timeout", "300")
    if not ok:
        # compose --wait returns non-zero if any container fails or times out.
        # A prior alloy RLIMIT error can leave other containers in "created"
        # state. Retry critical services individually to ensure they start.
        print("  Retrying critical services that may not have started...")
        for svc in ("backend", "frontend", "ai-gateway", "ai-llm"):
            compose_run(config, "up", "-d", "--no-build", svc)

        result = compose_run(config, "ps", "--format", "json", capture=True)
        if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
            print("  Services started (some may still be initializing).")
            return DeployResult(True, "Application services started (some initializing)")
        return DeployResult(False, "Failed to start application services")

    print("  All services started and healthy.")
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


def phase_health_check(config: DeployConfig) -> DeployResult:
    """Verify service health and print deployment summary."""
    print("  Health check (waiting for services to initialize)...")

    api_port = config.env.get("API_PORT", "8000")
    gateway_port = config.env.get("AI_GATEWAY_PORT", "8090")
    llm_port = config.env.get("LLM_PORT", "8091")

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
