# Setup UX Redesign

**Date:** 2026-02-02
**Status:** Approved

## Overview

Redesign the setup experience to provide zero-dependency onboarding for production users. The setup utility will be delivered as pre-built executables that automatically detect, install, and configure all required system components.

## Goals

1. **Zero host dependencies** - Users download one executable, run it, done
2. **Production-first** - Default to containerized deployment, not development mode
3. **Auto-configure everything** - Detect and fix issues rather than just warn
4. **Cross-platform** - Support Linux and Windows (macOS removed - no NVIDIA CUDA support)

## Supported Platforms

| Platform                                   | GPU Support | Notes                                   |
| ------------------------------------------ | ----------- | --------------------------------------- |
| Linux (Fedora, Ubuntu, Debian, RHEL, Arch) | Full        | Primary target                          |
| Windows 10/11                              | Full (WSL2) | Via Podman Desktop                      |
| ~~macOS~~                                  | None        | Removed - Apple GPUs don't support CUDA |

## Delivery

- **PyInstaller executables** built in CI
- Attached to GitHub releases as:
  - `setup-linux` (x86_64)
  - `setup.exe` (Windows x86_64)
- Users download the appropriate binary and run it
- No Python, Node.js, or other dependencies required on host

## Setup Flow

### Step 1/5: Container Runtime

Detect and install Podman if missing.

```
Step 1/5: Container Runtime
  Detecting container runtime...
  ✗ Podman not found

  Install Podman? [Y/n]: y

  Detected: Fedora 43
  Running: sudo dnf install -y podman podman-compose
  [sudo] password: ********
  ✓ Podman 5.3.1 installed

  Initializing Podman...
  ✓ Podman ready
```

**Platform-specific installation:**

| Platform      | Command                                            |
| ------------- | -------------------------------------------------- |
| Fedora/RHEL   | `sudo dnf install -y podman podman-compose`        |
| Ubuntu/Debian | `sudo apt install -y podman podman-compose`        |
| Arch          | `sudo pacman -S --noconfirm podman podman-compose` |
| Windows       | `winget install -e --id RedHat.Podman`             |

### Step 2/5: NVIDIA GPU

Detect GPU, verify/upgrade drivers, install container toolkit.

```
Step 2/5: NVIDIA GPU
  Detecting GPU hardware...
  ✓ Found: NVIDIA RTX A5500 (24GB), RTX A400 (4GB)

  Checking driver...
  ✗ Driver version 470.223 is outdated (minimum: 535)

  Upgrade NVIDIA driver? [Y/n]: y
  Detected: Fedora 43
  Running: sudo dnf install -y akmod-nvidia
  ✓ Driver 560.35 installed

  Checking container GPU support...
  ✗ nvidia-container-toolkit not found

  Install nvidia-container-toolkit? [Y/n]: y
  Running: sudo dnf install -y nvidia-container-toolkit
  Running: sudo nvidia-ctk runtime configure --runtime=podman
  Running: systemctl --user restart podman
  ✓ Container GPU passthrough configured
```

**Driver installation by platform:**

| Platform    | Command                                                                  |
| ----------- | ------------------------------------------------------------------------ |
| Fedora/RHEL | `sudo dnf install -y akmod-nvidia`                                       |
| Ubuntu      | `sudo apt install -y nvidia-driver-560` or `sudo ubuntu-drivers install` |
| Debian      | `sudo apt install -y nvidia-driver`                                      |
| Windows     | Prompt to download from nvidia.com or use GeForce Experience             |

**nvidia-container-toolkit installation:**

| Platform      | Command                                                              |
| ------------- | -------------------------------------------------------------------- |
| Fedora/RHEL   | `sudo dnf install -y nvidia-container-toolkit`                       |
| Ubuntu/Debian | Add NVIDIA repo, then `sudo apt install -y nvidia-container-toolkit` |
| Windows       | Included with Podman Desktop                                         |

**Reboot handling:**

- If driver was upgraded, setup exits with message: "Reboot required. Run setup again after reboot."

### Step 3/5: Storage

Configure paths and verify disk space.

```
Step 3/5: Storage
  Camera recordings path [/export/foscam]:
    ✓ Directory exists

  AI models path [/export/ai_models]:
    ✓ Directory created
    ✓ 142 GB available (50 GB required)
```

**Validations:**

- Create directories if they don't exist (with user consent)
- Check minimum 50 GB free space
- Warn if on slow storage (HDD vs SSD detection where possible)

### Step 4/5: Network

Detect available ports and configure firewall.

```
Step 4/5: Network
  Checking ports...
    ✓ 8443 (HTTPS dashboard) - available
    ✓ 8555 (WebRTC streaming) - available
    ✓ 5432 (PostgreSQL) - available
    ✓ 6379 (Redis) - available

  Checking firewall...
  ! Firewall active (firewalld)
    Ports 8443, 8555 need to be opened for external access.

  Open firewall ports? [Y/n]: y
  Running: sudo firewall-cmd --permanent --add-port={8443,8555}/tcp
  Running: sudo firewall-cmd --reload
  ✓ Firewall configured
```

**Port conflict handling:**

- If default port unavailable, find next available and report to user
- Store actual ports in generated `.env` file

**Firewall commands by platform:**

| Platform          | Detection                                  | Open Ports                                                                                       |
| ----------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| Linux (firewalld) | `firewall-cmd --state`                     | `firewall-cmd --permanent --add-port=PORT/tcp && firewall-cmd --reload`                          |
| Linux (ufw)       | `ufw status`                               | `ufw allow PORT/tcp`                                                                             |
| Windows           | `netsh advfirewall show allprofiles state` | `netsh advfirewall firewall add rule name="HSI" dir=in action=allow protocol=tcp localport=PORT` |

### Step 5/5: Credentials & Security

Generate all credentials and SSL certificate.

```
Step 5/5: Credentials & Security
  Generating secure credentials...
    ✓ Database password generated
    ✓ Redis password generated
    ✓ Grafana admin password generated

  Creating Docker secrets...
    ✓ secrets/postgres_password.txt
    ✓ secrets/redis_password.txt
    ✓ secrets/grafana_admin_password.txt

  Generating SSL certificate...
    Detected local IP: 192.168.1.100
    ✓ Certificate created for: localhost, 192.168.1.100
    ✓ Saved to: certs/cert.pem, certs/key.pem
```

**Defaults:**

- Docker secrets: Created by default (not prompted)
- SSL certificate: Auto-generated with localhost + detected local IP in SANs
- All passwords: Cryptographically secure, unique per installation

### Automatic Downloads

After configuration, download models and images automatically.

```
Downloading AI models...
  This may take 20-30 minutes depending on your connection.

  [1/14] florence-2-large (1.2 GB)
  [████████████████████] 100%

  [2/14] clip-vit-l (800 MB)
  [████████████████████] 100%

  ... (all 14 models)

  ✓ All models downloaded (18.5 GB)

Pulling container images...
  [████████████████████] 100% - 25/25 images pulled
  ✓ All images ready (12.3 GB)
```

**Models downloaded:**
All models used by the project (currently 14):

- florence-2-large
- clip-vit-l
- yolo26
- depth-anything-v2-small
- osnet-x0-25
- yolov8n-pose
- fashion-clip
- xclip-base
- vit-age-classifier
- vit-gender-classifier
- vehicle-segment-classification
- pet-classifier
- threat-detection-yolov8n
- (Nemotron LLM)

### Linux Kernel Optimizations

Prompt for system optimizations after downloads complete.

```
Linux Kernel Optimizations
==========================

Apply performance optimizations for AI workloads?
  - Network buffer tuning (256MB DGX-style)
  - Memory optimizations (NUMA, swappiness)
  - NVIDIA driver optimizations (PCIe relaxed ordering)
  - User limits (memlock, nofile)

Apply optimizations? [Y/n]: y
  ✓ Network buffers optimized
  ✓ Memory settings optimized
  ✓ NVIDIA optimizations applied
  ✓ User limits configured
  ! Reboot recommended for full effect
```

### Mitigations Consent (Separate Prompt)

Security tradeoff requires explicit consent.

```
CPU Security Mitigations
========================

! This setting reduces security in exchange for ~5-30% CPU performance.

Disabling Spectre/Meltdown mitigations:
  - Improves CPU-bound workload performance
  - Primarily benefits CPU operations (minimal GPU impact)
  - REDUCES SECURITY against side-channel attacks

Your system shows these mitigations:
  - spectre_v1: Mitigation active
  - spectre_v2: Mitigation active
  - meltdown: Not affected (AMD CPU)

Disable CPU security mitigations? [y/N]: n
  Keeping security mitigations enabled (recommended)
```

**Default: No** - This is the only setting that defaults to No due to security implications.

### Completion

```
════════════════════════════════════════════════════════════

Setup complete!

Start the system:
  podman-compose -f docker-compose.ghcr.yml up -d

Dashboard:
  https://localhost:8443
  https://192.168.1.100:8443

Default credentials:
  Stored in ./secrets/ directory

Next steps:
  1. Start the system with the command above
  2. Open the dashboard in your browser
  3. Accept the self-signed certificate warning
  4. Add your first camera in Settings > Cameras

Documentation: https://github.com/your-repo/docs

════════════════════════════════════════════════════════════
```

## Command Line Interface

```
usage: setup [-h] [--advanced] [--defaults] [--dev]

Home Security Intelligence Setup

options:
  -h, --help   Show this help message and exit
  --advanced   Show advanced options (port customization, etc.)
  --defaults   Non-interactive mode with all defaults
  --dev        Developer mode (install pre-commit hooks, skip container setup)
```

**Modes:**

- **Default (no flags):** Production setup as described above
- **--advanced:** Adds prompts for port customization, custom SSL SANs, individual model selection
- **--defaults:** Non-interactive, uses all defaults (for automation/CI)
- **--dev:** Developer setup - installs pre-commit hooks, Python deps, skips container/GPU setup

## Files Generated

| File                                 | Purpose                         |
| ------------------------------------ | ------------------------------- |
| `.env`                               | Environment configuration       |
| `docker-compose.override.yml`        | Port mappings and volume mounts |
| `secrets/postgres_password.txt`      | Database credential             |
| `secrets/redis_password.txt`         | Redis credential                |
| `secrets/grafana_admin_password.txt` | Grafana credential              |
| `certs/cert.pem`                     | SSL certificate                 |
| `certs/key.pem`                      | SSL private key                 |

## Implementation Notes

### PyInstaller Build

```yaml
# .github/workflows/build-setup.yml
- Build setup-linux on ubuntu-latest
- Build setup.exe on windows-latest
- Attach to release artifacts
```

**Considerations:**

- Bundle size: ~20-30 MB per executable
- Include CA certificates for HTTPS downloads
- Test on clean VMs to verify no missing dependencies

### Privilege Escalation

- Linux: Use `sudo` for package installation, firewall, driver install
- Windows: Use `runas` or prompt for UAC elevation
- Always explain what elevated command will do before prompting

### Error Recovery

- Each step is idempotent - can re-run setup if it fails midway
- Existing `.env` values preserved on re-run
- Downloaded models/images not re-downloaded if present

### Removed from Setup

The following are no longer part of the default setup flow:

| Removed                      | Reason                                    |
| ---------------------------- | ----------------------------------------- |
| macOS support                | No NVIDIA CUDA support                    |
| Python/Node.js installation  | Not needed for production (in containers) |
| Pre-commit hooks             | Developer-only (`--dev` flag)             |
| Manual firewall instructions | Auto-configure with consent               |
| Model selection prompts      | Download all models automatically         |
| Docker secrets prompt        | Create by default                         |
| SSL certificate prompts      | Auto-generate by default                  |

## Success Metrics

1. **Time to first dashboard:** < 30 minutes on good internet
2. **User prompts:** ≤ 10 yes/no decisions
3. **Support requests:** Reduce "setup failed" issues by 80%
4. **Platform coverage:** Linux + Windows covers 95%+ of deployment targets

## Future Enhancements

- Web-based setup wizard (optional alternative to CLI)
- Remote/SSH setup for headless servers
- Kubernetes/Helm chart for cloud deployment
- Automatic camera discovery (ONVIF/UPnP)
