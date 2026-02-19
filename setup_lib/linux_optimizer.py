"""Linux AI workstation optimizer.

Applies kernel tunables and system optimizations for AI/ML workloads.
Based on NVIDIA DGX OS best practices.

WARNING: Some optimizations disable CPU security mitigations (Spectre/Meltdown/MDS).
Only use on trusted, isolated AI workstations.
"""

import os
import platform
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# ANSI color codes
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
NC = "\033[0m"  # No Color


def log_info(msg: str) -> None:
    """Print info message in green."""
    print(f"{GREEN}[INFO]{NC} {msg}")


def log_warn(msg: str) -> None:
    """Print warning message in yellow."""
    print(f"{YELLOW}[WARN]{NC} {msg}")


def log_error(msg: str) -> None:
    """Print error message in red."""
    print(f"{RED}[ERROR]{NC} {msg}")


@dataclass
class OptimizationResult:
    """Result of an optimization phase."""

    success: bool
    message: str
    requires_reboot: bool = False


# =============================================================================
# Configuration Content
# =============================================================================

SYSCTL_NETWORK_CONFIG = """\
# DGX OS-style network tuning for AI workloads
# Optimizes for large model transfers and distributed training

# Socket buffer maximums (256MB - matches DGX OS)
net.core.rmem_max = 268435456
net.core.wmem_max = 268435456
net.core.rmem_default = 16777216
net.core.wmem_default = 16777216

# Increase network backlog for burst traffic
net.core.netdev_max_backlog = 250000
net.core.somaxconn = 65535

# TCP buffer auto-tuning ranges (min, default, max)
# Max 128MB for large transfers
net.ipv4.tcp_rmem = 4096 87380 134217728
net.ipv4.tcp_wmem = 4096 65536 134217728

# Use BBR congestion control (better than cubic for variable latency)
net.ipv4.tcp_congestion_control = bbr

# Enable MTU probing for jumbo frames
net.ipv4.tcp_mtu_probing = 1

# Increase max orphaned sockets
net.ipv4.tcp_max_orphans = 262144

# Faster TCP keepalive for distributed training fault detection
net.ipv4.tcp_keepalive_time = 60
net.ipv4.tcp_keepalive_intvl = 10
net.ipv4.tcp_keepalive_probes = 6

# Allow more simultaneous connections
net.ipv4.ip_local_port_range = 1024 65535
"""

SYSCTL_MEMORY_CONFIG = """\
# DGX OS-style memory tuning for AI workloads

# Disable NUMA balancing (reduces latency for GPU-pinned workloads)
kernel.numa_balancing = 0

# Reduce swappiness (prefer keeping GPU-related data in RAM)
vm.swappiness = 10

# Increase dirty page thresholds for large dataset writes
vm.dirty_ratio = 40
vm.dirty_background_ratio = 10

# Increase max memory map areas (needed for large model mmaps)
vm.max_map_count = 2097152

# Reduce zone reclaim aggressiveness
vm.zone_reclaim_mode = 0

# Allow overcommit for CUDA memory allocations
vm.overcommit_memory = 1

# Increase inotify limits for large projects
fs.inotify.max_user_watches = 1048576
fs.inotify.max_user_instances = 8192

# Increase file descriptor limits
fs.file-max = 2097152
fs.nr_open = 2097152

# Kernel performance settings
kernel.sched_autogroup_enabled = 0
kernel.perf_event_paranoid = -1
"""

NVIDIA_MODPROBE_CONFIG = """\
# DGX OS-style NVIDIA driver options

# Enable PCIe relaxed ordering for improved GPU-to-GPU transfers
options nvidia NVreg_EnablePCIERelaxedOrderingMode=1

# Preserve video memory allocations across suspend/resume
options nvidia NVreg_PreserveVideoMemoryAllocations=1

# Enable dynamic power management for better thermals
options nvidia NVreg_DynamicPowerManagement=0x02

# Increase GPU timeout for long-running kernels (in seconds)
# Default is 8 seconds, increase for training workloads
options nvidia NVreg_RegistryDwords="RMGpuHangTimeout=0x3C"
"""

LIMITS_CONFIG = """\
# Increased limits for AI workloads

# Memory locking (for CUDA pinned memory)
*    soft    memlock    unlimited
*    hard    memlock    unlimited

# File descriptors
*    soft    nofile     1048576
*    hard    nofile     1048576

# Process limits
*    soft    nproc      unlimited
*    hard    nproc      unlimited

# Core dumps (disable for production, enable for debugging)
*    soft    core       0
*    hard    core       unlimited

# Stack size
*    soft    stack      unlimited
*    hard    stack      unlimited
"""

AI_ENV_SCRIPT = """\
# AI Workstation Environment Variables
# Optimizes CUDA, PyTorch, and threading libraries

# CUDA device ordering (matches nvidia-smi output)
export CUDA_DEVICE_ORDER=PCI_BUS_ID

# PyTorch memory allocator optimization (reduces fragmentation)
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# OpenMP threading (auto-detect physical cores)
PHYSICAL_CORES=$(lscpu -p | grep -v '^#' | sort -t, -k 2 -u | wc -l)
export OMP_NUM_THREADS=${PHYSICAL_CORES:-32}
export OMP_PROC_BIND=spread
export OMP_PLACES=cores

# Intel MKL threading (used by NumPy, SciPy)
export MKL_NUM_THREADS=${PHYSICAL_CORES:-32}

# OpenBLAS threading
export OPENBLAS_NUM_THREADS=${PHYSICAL_CORES:-32}

# NCCL optimizations for multi-GPU (if using distributed training)
export NCCL_P2P_DISABLE=0
export NCCL_SHM_DISABLE=0
"""

VERIFY_SCRIPT = """\
#!/bin/bash
# Verify AI workstation optimizations

echo "=== AI Workstation Optimization Verification ==="
echo ""

echo "1. Kernel Parameters:"
echo "   iommu:        $(grep -o 'iommu=[^ ]*' /proc/cmdline 2>/dev/null || echo 'NOT SET')"
echo "   mitigations:  $(grep -o 'mitigations=[^ ]*' /proc/cmdline 2>/dev/null || echo 'NOT SET (default enabled)')"
echo "   init_on_alloc: $(grep -o 'init_on_alloc=[^ ]*' /proc/cmdline 2>/dev/null || echo 'NOT SET')"
echo ""

echo "2. Network Buffers:"
echo "   rmem_max: $(sysctl -n net.core.rmem_max) (target: 268435456)"
echo "   wmem_max: $(sysctl -n net.core.wmem_max) (target: 268435456)"
echo "   tcp_congestion: $(sysctl -n net.ipv4.tcp_congestion_control) (target: bbr)"
echo ""

echo "3. Memory Settings:"
echo "   numa_balancing: $(sysctl -n kernel.numa_balancing) (target: 0)"
echo "   swappiness: $(sysctl -n vm.swappiness) (target: 10)"
echo "   max_map_count: $(sysctl -n vm.max_map_count) (target: 2097152)"
echo ""

echo "4. NVIDIA Settings:"
if command -v nvidia-smi &> /dev/null; then
    echo "   Persistence Mode: $(nvidia-smi --query-gpu=persistence_mode --format=csv,noheader | head -1)"
    echo "   PCIe Relaxed Ordering: $(cat /sys/module/nvidia/parameters/NVreg_EnablePCIERelaxedOrderingMode 2>/dev/null || echo 'N/A')"
else
    echo "   nvidia-smi not found"
fi
echo ""

echo "5. CPU Governor:"
echo "   $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo 'N/A')"
echo ""

echo "6. Transparent Hugepages:"
echo "   $(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || echo 'N/A')"
echo ""

echo "7. Vulnerability Mitigations Status:"
if [[ -d /sys/devices/system/cpu/vulnerabilities ]]; then
    for vuln in /sys/devices/system/cpu/vulnerabilities/*; do
        echo "   $(basename $vuln): $(cat $vuln)"
    done
fi
echo ""

echo "8. AI Framework Environment Variables:"
echo "   Profile script: $(test -f /etc/profile.d/ai-workstation.sh && echo 'INSTALLED' || echo 'NOT FOUND')"
echo "   CUDA_DEVICE_ORDER: ${CUDA_DEVICE_ORDER:-NOT SET}"
echo "   OMP_NUM_THREADS: ${OMP_NUM_THREADS:-NOT SET}"
echo "   MKL_NUM_THREADS: ${MKL_NUM_THREADS:-NOT SET}"
echo "   PYTORCH_CUDA_ALLOC_CONF: ${PYTORCH_CUDA_ALLOC_CONF:-NOT SET}"
echo ""
echo "   Note: Environment variables require a new login session to take effect."
echo "   Run 'source /etc/profile.d/ai-workstation.sh' to apply in current shell."
"""


# =============================================================================
# Utility Functions
# =============================================================================


def is_linux() -> bool:
    """Check if running on Linux."""
    return platform.system() == "Linux"


def is_root() -> bool:
    """Check if running as root."""
    return os.geteuid() == 0


def _run_sudo(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a command with sudo."""
    return subprocess.run(
        ["sudo", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=check,
    )


def write_config_file(
    path: Path, content: str, backup_dir: Path | None = None
) -> tuple[bool, bool]:
    """Write a configuration file via sudo, optionally backing up existing.

    Args:
        path: Path to write the config file
        content: Content to write
        backup_dir: If provided, backup existing file here first

    Returns:
        Tuple of (success, was_modified). was_modified is False if file
        already existed with identical content (idempotent).
    """
    try:
        # Check if file already exists with same content
        if path.exists():
            existing_content = path.read_text()
            if existing_content.strip() == content.strip():
                log_info(f"Already configured: {path}")
                return True, False  # Success, but not modified

            # Backup existing file if different and backup requested
            if backup_dir:
                backup_path = backup_dir / path.name
                print(f"  $ sudo cp {path} {backup_path}")
                _run_sudo(["cp", str(path), str(backup_path)])

        # Write new content via sudo (write to temp file, then sudo cp)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=path.suffix or ".conf", delete=False
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Ensure parent directory exists
            _run_sudo(["mkdir", "-p", str(path.parent)])
            print(f"  $ sudo write {path} ({len(content)} bytes)")
            result = _run_sudo(["cp", tmp_path, str(path)])
            if result.returncode != 0:
                log_error(f"Failed to write {path}: {result.stderr.strip()}")
                return False, False
            _run_sudo(["chmod", "644", str(path)])
            return True, True  # Success and modified
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    except (OSError, PermissionError) as e:
        log_error(f"Failed to write {path}: {e}")
        return False, False


def run_command(cmd: list[str], check: bool = True, verbose: bool = True) -> tuple[bool, str]:
    """Run a command with sudo and return success status and output.

    All optimizer commands require root privileges. Instead of requiring
    the entire setup.py to run as root, we use sudo per-command.

    Args:
        cmd: Command and arguments as list (sudo is prepended automatically)
        check: If True, don't raise on non-zero exit
        verbose: If True, log the command being executed

    Returns:
        Tuple of (success, output/error message)
    """
    # Prepend sudo if not already root
    if os.geteuid() != 0:
        full_cmd = ["sudo", *cmd]
    else:
        full_cmd = cmd

    cmd_str = " ".join(full_cmd)

    if verbose:
        print(f"  $ {cmd_str}")

    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            check=check,
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        if verbose:
            log_warn(f"Command failed: {cmd_str}")
        return False, e.stderr or str(e)
    except FileNotFoundError:
        if verbose:
            log_error(f"Command not found: {full_cmd[0]}")
        return False, f"Command not found: {full_cmd[0]}"


# =============================================================================
# Optimization Phases
# =============================================================================


def apply_network_optimizations(backup_dir: Path) -> OptimizationResult:
    """Apply network buffer optimizations.

    Creates /etc/sysctl.d/90-ai-network.conf
    """
    log_info("Checking network buffer optimizations...")

    config_path = Path("/etc/sysctl.d/90-ai-network.conf")
    success, modified = write_config_file(config_path, SYSCTL_NETWORK_CONFIG, backup_dir)

    if not success:
        return OptimizationResult(False, "Failed to write network sysctl config")

    if modified:
        return OptimizationResult(True, "Network optimizations configured")
    return OptimizationResult(True, "Network optimizations already applied")


def apply_memory_optimizations(backup_dir: Path) -> OptimizationResult:
    """Apply memory and CPU optimizations.

    Creates /etc/sysctl.d/90-ai-memory.conf
    """
    log_info("Checking memory and CPU optimizations...")

    config_path = Path("/etc/sysctl.d/90-ai-memory.conf")
    success, modified = write_config_file(config_path, SYSCTL_MEMORY_CONFIG, backup_dir)

    if not success:
        return OptimizationResult(False, "Failed to write memory sysctl config")

    if modified:
        return OptimizationResult(True, "Memory optimizations configured")
    return OptimizationResult(True, "Memory optimizations already applied")


def apply_sysctl_changes() -> OptimizationResult:
    """Apply sysctl changes immediately."""
    log_info("Applying sysctl changes...")

    success, output = run_command(["sysctl", "--system"], check=False)
    if not success:
        return OptimizationResult(False, f"Failed to apply sysctl: {output}")

    return OptimizationResult(True, "Sysctl changes applied")


def apply_nvidia_optimizations(backup_dir: Path) -> OptimizationResult:
    """Apply NVIDIA driver optimizations.

    Creates /etc/modprobe.d/nvidia-ai.conf and enables persistence daemon.
    """
    log_info("Checking NVIDIA kernel module options...")

    config_path = Path("/etc/modprobe.d/nvidia-ai.conf")
    success, modified = write_config_file(config_path, NVIDIA_MODPROBE_CONFIG, backup_dir)

    if not success:
        return OptimizationResult(
            False, "Failed to write NVIDIA modprobe config", requires_reboot=True
        )

    # Check and enable NVIDIA persistence daemon
    check_result, output = run_command(
        ["systemctl", "is-enabled", "nvidia-persistenced"], check=False
    )
    if check_result and "enabled" in output:
        log_info("nvidia-persistenced already enabled")
    else:
        log_info("Enabling NVIDIA persistence daemon...")
        enable_result, _ = run_command(["systemctl", "enable", "nvidia-persistenced"], check=False)
        if enable_result:
            run_command(["systemctl", "start", "nvidia-persistenced"], check=False)
            log_info("nvidia-persistenced enabled and started")
        else:
            log_warn("nvidia-persistenced service not found - install nvidia-persistenced package")

    # Set persistence mode via nvidia-smi as fallback
    if shutil.which("nvidia-smi"):
        run_command(["nvidia-smi", "-pm", "1"], check=False)

    if modified:
        return OptimizationResult(True, "NVIDIA optimizations configured", requires_reboot=True)
    return OptimizationResult(
        True,
        "NVIDIA optimizations already applied",
        requires_reboot=False,  # No reboot needed if config unchanged
    )


def _update_grub_parameters(backup_dir: Path, kernel_params: dict[str, str]) -> OptimizationResult:
    """Update GRUB kernel parameters.

    Args:
        backup_dir: Directory to backup existing config
        kernel_params: Dict of parameter name -> value to add

    Returns:
        OptimizationResult with success status
    """
    grub_path = Path("/etc/default/grub")
    if not grub_path.exists():
        return OptimizationResult(
            False, "GRUB config not found at /etc/default/grub", requires_reboot=True
        )

    # Backup current GRUB config (only if not already backed up)
    backup_file = backup_dir / "grub.bak"
    if backup_dir and not backup_file.exists():
        shutil.copy2(grub_path, backup_file)  # /etc/default/grub is world-readable

    # Read current config (world-readable, no sudo needed)
    grub_content = grub_path.read_text()

    # Extract current GRUB_CMDLINE_LINUX
    match = re.search(r'^GRUB_CMDLINE_LINUX="([^"]*)"', grub_content, re.MULTILINE)
    if not match:
        return OptimizationResult(False, "Could not parse GRUB_CMDLINE_LINUX", requires_reboot=True)

    current_cmdline = match.group(1)

    # Check which params are missing
    new_params = []
    for param_name, param_value in kernel_params.items():
        if not re.search(rf"(^| ){param_name}(=|$| )", current_cmdline):
            new_params.append(f"{param_name}={param_value}")
        else:
            log_info(f"Parameter '{param_name}' already present in kernel cmdline")

    if not new_params:
        return OptimizationResult(
            True, "All kernel parameters already present", requires_reboot=False
        )

    # Add new params
    new_cmdline = current_cmdline + " " + " ".join(new_params)
    new_grub_content = re.sub(
        r'^GRUB_CMDLINE_LINUX="[^"]*"',
        f'GRUB_CMDLINE_LINUX="{new_cmdline}"',
        grub_content,
        flags=re.MULTILINE,
    )

    # Write updated config via sudo
    log_info(f"Adding kernel parameters: {' '.join(new_params)}")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".grub", delete=False) as tmp:
        tmp.write(new_grub_content)
        tmp_path = tmp.name
    try:
        result = _run_sudo(["cp", tmp_path, str(grub_path)])
        if result.returncode != 0:
            return OptimizationResult(
                False, f"Failed to write GRUB config: {result.stderr.strip()}", requires_reboot=True
            )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # Regenerate GRUB config — use the correct tool for the distro
    log_info("Regenerating GRUB configuration...")

    if shutil.which("update-grub"):
        # Debian/Ubuntu
        success, output = run_command(["update-grub"], check=False)
    else:
        # Fedora/RHEL fallback
        efi_grub = Path("/boot/efi/EFI/fedora/grub.cfg")
        legacy_grub = Path("/boot/grub2/grub.cfg")

        try:
            efi_parent_exists = efi_grub.parent.exists()
        except PermissionError:
            efi_parent_exists = False

        if Path("/sys/firmware/efi").is_dir() and efi_parent_exists:
            success, output = run_command(["grub2-mkconfig", "-o", str(efi_grub)], check=False)
        else:
            success, output = run_command(["grub2-mkconfig", "-o", str(legacy_grub)], check=False)

    if not success:
        return OptimizationResult(
            False, f"Failed to regenerate GRUB config: {output}", requires_reboot=True
        )

    return OptimizationResult(
        True, f"Kernel parameters configured: {' '.join(new_params)}", requires_reboot=True
    )


def apply_kernel_parameters(backup_dir: Path) -> OptimizationResult:
    """Apply safe kernel boot parameters.

    Modifies /etc/default/grub and regenerates GRUB config.
    Adds: iommu=pt pci=realloc=on init_on_alloc=0 transparent_hugepage=madvise

    Note: mitigations=off is NOT included here - use apply_disable_mitigations()
    for that, which requires separate explicit consent.
    """
    log_info("Configuring kernel boot parameters...")

    # Safe parameters only - no security tradeoffs
    kernel_params = {
        "iommu": "pt",
        "pci": "realloc=on",
        "init_on_alloc": "0",
        "transparent_hugepage": "madvise",
    }

    return _update_grub_parameters(backup_dir, kernel_params)


def apply_disable_mitigations(backup_dir: Path) -> OptimizationResult:
    """Disable CPU security mitigations (Spectre/Meltdown/MDS).

    WARNING: This reduces security for a modest performance gain (~3-15%).
    Only use on trusted, isolated systems.

    This is separate from apply_kernel_parameters() to require explicit consent.
    """
    log_info("Disabling CPU security mitigations...")

    kernel_params = {
        "mitigations": "off",
    }

    return _update_grub_parameters(backup_dir, kernel_params)


def disable_unnecessary_services() -> OptimizationResult:
    """Disable unnecessary services for AI workstation."""
    log_info("Checking unnecessary services...")

    services_to_disable = [
        "bluetooth.service",
        "cups.service",
        "cups-browsed.service",
        "avahi-daemon.service",
        "ModemManager.service",
    ]

    disabled = []
    already_disabled = []
    not_found = []

    for service in services_to_disable:
        # Check if service exists and its current state
        check_result, output = run_command(["systemctl", "is-enabled", service], check=False)

        if "No such file" in output or "not-found" in output:
            not_found.append(service)
            continue

        if "disabled" in output or "masked" in output:
            already_disabled.append(service)
            log_info(f"Already disabled: {service}")
            continue

        # Service exists and is enabled - disable it
        run_command(["systemctl", "disable", service], check=False)
        run_command(["systemctl", "stop", service], check=False)
        disabled.append(service)
        log_info(f"Disabled: {service}")

    if disabled:
        return OptimizationResult(True, f"Disabled {len(disabled)} services")
    if already_disabled:
        return OptimizationResult(True, f"All {len(already_disabled)} services already disabled")
    return OptimizationResult(True, "No services to disable")


def apply_user_limits(backup_dir: Path) -> OptimizationResult:
    """Apply user limits configuration.

    Creates /etc/security/limits.d/90-ai-workstation.conf
    """
    log_info("Checking user limits...")

    config_path = Path("/etc/security/limits.d/90-ai-workstation.conf")
    success, modified = write_config_file(config_path, LIMITS_CONFIG, backup_dir)

    if not success:
        return OptimizationResult(False, "Failed to write limits config")

    if modified:
        return OptimizationResult(True, "User limits configured")
    return OptimizationResult(True, "User limits already configured")


def apply_ai_environment(backup_dir: Path) -> OptimizationResult:
    """Apply AI framework environment variables.

    Creates /etc/profile.d/ai-workstation.sh
    """
    log_info("Checking AI framework environment variables...")

    config_path = Path("/etc/profile.d/ai-workstation.sh")
    success, modified = write_config_file(config_path, AI_ENV_SCRIPT, backup_dir)

    if not success:
        return OptimizationResult(False, "Failed to write AI environment script")

    # Make executable
    if config_path.exists():
        _run_sudo(["chmod", "755", str(config_path)])

    if modified:
        return OptimizationResult(
            True, "AI environment variables configured (active after new login)"
        )
    return OptimizationResult(True, "AI environment variables already configured")


def install_verification_script() -> OptimizationResult:
    """Install the verification script via sudo."""
    script_path = Path("/usr/local/bin/verify-ai-optimizations")

    # Check if already installed with same content
    if script_path.exists():
        try:
            existing = script_path.read_text()
            if existing.strip() == VERIFY_SCRIPT.strip():
                log_info(f"Verification script already installed: {script_path}")
                return OptimizationResult(True, "Verification script already installed")
        except (OSError, PermissionError):
            pass  # Will try to write anyway

    log_info("Installing verification script...")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as tmp:
        tmp.write(VERIFY_SCRIPT)
        tmp_path = tmp.name

    try:
        result = _run_sudo(["cp", tmp_path, str(script_path)])
        if result.returncode != 0:
            return OptimizationResult(
                False, f"Failed to install verification script: {result.stderr.strip()}"
            )
        _run_sudo(["chmod", "755", str(script_path)])
        return OptimizationResult(True, f"Verification script installed: {script_path}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# =============================================================================
# Main Optimization Runner
# =============================================================================


@dataclass
class OptimizationPhase:
    """Definition of an optimization phase."""

    name: str
    description: str
    func: Callable[[Path], OptimizationResult]
    requires_backup: bool = True


# Define all optimization phases (safe by default)
OPTIMIZATION_PHASES: list[OptimizationPhase] = [
    OptimizationPhase(
        "network",
        "Network buffer optimizations (256MB DGX-style)",
        apply_network_optimizations,
    ),
    OptimizationPhase(
        "memory",
        "Memory and CPU optimizations (NUMA, swappiness, mmap limits)",
        apply_memory_optimizations,
    ),
    OptimizationPhase(
        "nvidia",
        "NVIDIA driver optimizations (PCIe relaxed ordering, persistence)",
        apply_nvidia_optimizations,
    ),
    OptimizationPhase(
        "kernel",
        "Kernel boot parameters (iommu=pt, hugepages) - safe, no security tradeoffs",
        apply_kernel_parameters,
    ),
    OptimizationPhase(
        "services",
        "Disable unnecessary services (bluetooth, cups, avahi)",
        lambda _: disable_unnecessary_services(),
        requires_backup=False,
    ),
    OptimizationPhase(
        "limits",
        "User limits (memlock, nofile, nproc)",
        apply_user_limits,
    ),
    OptimizationPhase(
        "environment",
        "AI framework environment variables (CUDA, PyTorch, OMP)",
        apply_ai_environment,
    ),
]

# Separate dangerous phase - requires explicit opt-in
MITIGATIONS_PHASE = OptimizationPhase(
    "mitigations",
    "Disable CPU security mitigations (Spectre/Meltdown) - REDUCES SECURITY",
    apply_disable_mitigations,
)


def get_phase_descriptions() -> list[tuple[str, str]]:
    """Get list of (name, description) for all phases."""
    return [(p.name, p.description) for p in OPTIMIZATION_PHASES]


def run_optimizations(
    phases: list[str] | None = None,
    dry_run: bool = False,
    include_mitigations: bool = False,
) -> tuple[bool, bool]:
    """Run the specified optimization phases.

    Args:
        phases: List of phase names to run, or None for all safe phases
        dry_run: If True, only show what would be done
        include_mitigations: If True, also disable CPU security mitigations

    Returns:
        Tuple of (overall_success, requires_reboot)
    """
    if not is_linux():
        log_error("This optimizer only works on Linux systems")
        return False, False

    # Create backup directory (use /tmp since we may not be root)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = Path(f"/tmp/ai-optimizer-backup-{timestamp}")  # noqa: S108

    if not dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)
        log_info(f"Backup directory: {backup_dir}")

        # Backup current sysctl
        success, sysctl_output = run_command(["sysctl", "-a"], check=False, verbose=False)
        if success:
            (backup_dir / "sysctl-before.conf").write_text(sysctl_output)

    # Filter phases if specified
    phases_to_run = list(OPTIMIZATION_PHASES)
    if phases:
        phases_to_run = [p for p in OPTIMIZATION_PHASES if p.name in phases]

    # Add mitigations phase if explicitly requested
    if include_mitigations:
        phases_to_run.append(MITIGATIONS_PHASE)

    # Run phases
    overall_success = True
    requires_reboot = False
    results: list[tuple[str, OptimizationResult]] = []
    mitigations_disabled = False

    for phase in phases_to_run:
        if dry_run:
            log_info(f"[DRY RUN] Would apply: {phase.description}")
            continue

        log_info(f"=== Phase: {phase.name} ===")
        phase_backup = backup_dir if phase.requires_backup else Path(tempfile.gettempdir())
        result = phase.func(phase_backup)
        results.append((phase.name, result))

        if result.success:
            log_info(result.message)
            if phase.name == "mitigations":
                mitigations_disabled = True
        else:
            log_error(result.message)
            overall_success = False

        if result.requires_reboot:
            requires_reboot = True

    # Apply sysctl changes if we modified sysctl configs
    if not dry_run and any(p.name in ("network", "memory") for p in phases_to_run):
        result = apply_sysctl_changes()
        if not result.success:
            log_error(result.message)
            overall_success = False

    # Install verification script
    if not dry_run:
        result = install_verification_script()
        if result.success:
            log_info(result.message)

    # Print summary
    if not dry_run:
        print()
        log_info("=" * 46)
        log_info("  AI WORKSTATION OPTIMIZATION COMPLETE")
        log_info("=" * 46)
        print()

        if requires_reboot:
            log_warn("REBOOT REQUIRED for kernel parameter changes:")
            print("  - iommu=pt")
            print("  - init_on_alloc=0")
            print("  - transparent_hugepage=madvise")
            if mitigations_disabled:
                print("  - mitigations=off")
            print("  - NVIDIA module options")
            print()

        if mitigations_disabled:
            log_warn("SECURITY NOTICE:")
            log_warn("  CPU security mitigations have been DISABLED")
            log_warn("  (Spectre, Meltdown, MDS, L1TF, etc.)")
            log_warn("  Only use this system for trusted AI workloads")
            print()

        log_info(f"Backup saved to: {backup_dir}")
        log_info("After reboot, run: verify-ai-optimizations")

    return overall_success, requires_reboot


def prompt_and_run_optimizations(skip: bool = False) -> tuple[bool, bool]:
    """Interactive prompt to run optimizations.

    Args:
        skip: If True, skip optimizations without prompting.

    Returns:
        Tuple of (success, requires_reboot).
        success is True if optimizations were applied successfully or skipped.
        requires_reboot is True if kernel/driver changes need a reboot to take effect.
    """
    if not is_linux():
        return True, False  # Skip silently on non-Linux

    print()
    print("=" * 60)
    print("  Linux AI Workstation Optimizations (Optional)")
    print("=" * 60)
    print()

    if skip:
        print("Skipping kernel optimizations (can be applied later)")
        print("  To apply later: sudo python3 scripts/optimize-linux.py")
        print()
        return True, False

    print("This applies kernel tunables optimized for AI workloads:")
    print()
    for name, desc in get_phase_descriptions():
        print(f"  [{name}] {desc}")
    print()

    try:
        answer = input("Apply AI workstation optimizations? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return True, False

    if answer in ("n", "no"):
        print("Skipping AI optimizations.")
        return True, False

    print()
    log_info("Optimizations require sudo — you may be prompted for your password.")
    print()

    # Separate prompt for mitigations (security tradeoff)
    print()
    print("-" * 60)
    print(f"{YELLOW}OPTIONAL: Disable CPU Security Mitigations{NC}")
    print("-" * 60)
    print()
    print("Disabling Spectre/Meltdown mitigations can improve performance")
    print("by ~3-15% on CPU-bound workloads (data loading, preprocessing).")
    print()
    print(f"{RED}SECURITY RISK:{NC} This makes your system vulnerable to side-channel")
    print("attacks. Only do this on isolated, single-user AI workstations.")
    print()

    try:
        mitigations_answer = input("Disable CPU security mitigations? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        mitigations_answer = "n"

    include_mitigations = mitigations_answer in ("y", "yes")

    if include_mitigations:
        log_warn("CPU mitigations will be DISABLED")
    else:
        log_info("CPU mitigations will remain ENABLED (safer)")

    print()

    # Run optimizations
    success, requires_reboot = run_optimizations(include_mitigations=include_mitigations)

    if requires_reboot:
        print()
        try:
            reboot = input("Reboot now? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return success, requires_reboot

        if reboot in ("y", "yes"):
            log_info("Rebooting...")
            run_command(["reboot"])

    return success, requires_reboot
