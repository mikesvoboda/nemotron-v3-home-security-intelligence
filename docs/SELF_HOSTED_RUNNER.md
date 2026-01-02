# Self-Hosted GPU Runner Setup

This document describes how to set up a self-hosted GitHub Actions runner on the RTX A5500 machine for GPU-accelerated CI/CD tests.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Hardware Requirements](#hardware-requirements)
- [Software Requirements](#software-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Security Considerations](#security-considerations)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)

## Prerequisites

### Hardware Requirements

| Component | Requirement                | This Machine     |
| --------- | -------------------------- | ---------------- |
| GPU       | NVIDIA RTX with 8GB+ VRAM  | RTX A5500 (24GB) |
| CPU       | 4+ cores                   | Verified         |
| RAM       | 16GB+                      | Verified         |
| Storage   | 50GB+ free                 | Verified         |
| Network   | Stable internet connection | Verified         |

### Software Requirements

| Software                 | Minimum Version            | Purpose               |
| ------------------------ | -------------------------- | --------------------- |
| OS                       | Ubuntu 22.04+ / Fedora 36+ | Host operating system |
| NVIDIA Driver            | 535+                       | GPU access            |
| CUDA                     | 11.8+                      | GPU compute           |
| Docker                   | 24.0+                      | Container runtime     |
| NVIDIA Container Toolkit | Latest                     | GPU in containers     |
| Python                   | 3.10+                      | Test execution        |

### GitHub Requirements

- Repository admin access (to register runners)
- GitHub Actions enabled for the repository

## Installation

### Step 1: Verify GPU and Driver

```bash
# Verify NVIDIA driver is installed
nvidia-smi

# Expected output should show:
# - Driver Version: 535+ (or newer)
# - CUDA Version: 11.8+ (or newer)
# - GPU: NVIDIA RTX A5500
# - Memory: 24GB
```

### Step 2: Install NVIDIA Container Toolkit

**For Ubuntu/Debian:**

```bash
# Add NVIDIA repo
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

**For Fedora:**

```bash
# Install nvidia-container-toolkit
sudo dnf install -y nvidia-container-toolkit

# Configure Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### Step 3: Verify Docker GPU Access

```bash
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

This should display the same GPU information as the host `nvidia-smi`.

### Step 4: Create Runner User

```bash
# Create dedicated user for security isolation
sudo useradd -m -s /bin/bash github-runner

# Add to required groups
sudo usermod -aG docker github-runner
sudo usermod -aG video github-runner

# Create working directories
sudo mkdir -p /opt/actions-runner
sudo chown github-runner:github-runner /opt/actions-runner
```

### Step 5: Download GitHub Actions Runner

**IMPORTANT:** Always use the latest runner version. GitHub requires v2.329.0 or later.
Check https://github.com/actions/runner/releases for the current version.

```bash
# Switch to runner user
sudo su - github-runner
cd /opt/actions-runner

# Get latest version (update version number as needed)
RUNNER_VERSION="2.321.0"  # Check GitHub releases for latest

# Download runner
curl -o actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz -L \
  https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

# Extract
tar xzf actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
```

## Configuration

### Step 1: Get Registration Token

1. Go to repository: `https://github.com/YOUR_USER/home-security-intelligence`
2. Navigate to: Settings > Actions > Runners > New self-hosted runner
3. Copy the registration token (valid for 1 hour)

### Step 2: Configure Runner

```bash
# As github-runner user in /opt/actions-runner
./config.sh \
  --url https://github.com/YOUR_USER/home-security-intelligence \
  --token YOUR_REGISTRATION_TOKEN \
  --name "rtx-a5500-runner" \
  --labels "self-hosted,linux,gpu,rtx-a5500" \
  --work "_work" \
  --runasservice
```

**Required Labels:**

| Label         | Purpose                               |
| ------------- | ------------------------------------- |
| `self-hosted` | Required by GitHub                    |
| `linux`       | OS platform (auto-detected)           |
| `gpu`         | Indicates GPU capability              |
| `rtx-a5500`   | Specific GPU model (matches workflow) |

### Step 3: Install as Systemd Service

```bash
# Exit to root/sudo user
exit

# Install service
cd /opt/actions-runner
sudo ./svc.sh install github-runner

# Start service
sudo ./svc.sh start

# Verify status
sudo ./svc.sh status
```

### Step 4: Enable Auto-Start on Boot

The systemd service should auto-start. Verify with:

```bash
systemctl is-enabled actions.runner.*.service
```

## Security Considerations

### Fork Protection (CRITICAL)

When the repository is public, malicious PRs from forks could execute arbitrary code on your machine.

**This protection is already implemented in `gpu-tests.yml`:**

```yaml
jobs:
  gpu-integration:
    runs-on: [self-hosted, gpu, rtx-a5500]
    # Fork protection - only run for trusted sources
    if: >
      github.event.pull_request.head.repo.full_name == github.repository ||
      github.event_name == 'push'
```

This ensures GPU tests ONLY run for:

- Direct pushes to the repository
- PRs from branches within the same repository (not forks)

### Resource Limits

Configure Docker resource limits in `/etc/docker/daemon.json`:

```json
{
  "default-runtime": "nvidia",
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  },
  "default-ulimits": {
    "memlock": { "Name": "memlock", "Hard": -1, "Soft": -1 }
  }
}
```

After editing, restart Docker:

```bash
sudo systemctl restart docker
```

### Job Timeout

The `gpu-tests.yml` workflow has a 30-minute timeout configured:

```yaml
timeout-minutes: 30
```

This prevents runaway jobs from consuming resources indefinitely.

### Secrets Management

- Never echo secrets in workflow logs
- Use GitHub Environments with protection rules for production secrets
- The runner should NOT have access to production credentials
- Review workflow files before enabling for new contributors

### Network Isolation (Recommended)

Consider running the GPU machine on an isolated network segment with:

- Outbound access to GitHub only
- No inbound access from the internet
- VPN for administrative access

## Verification

### Step 1: Verify Runner is Online

1. Go to: Settings > Actions > Runners
2. Runner `rtx-a5500-runner` should show as "Idle" with green status

### Step 2: Test GPU Workflow

Create a test PR or push to main and verify:

```bash
# Check workflow runs
gh run list --workflow=gpu-tests.yml

# View specific run
gh run view <run-id>
```

### Step 3: Verify Workflow Labels Match

The `gpu-tests.yml` workflow expects these labels:

```yaml
runs-on: [self-hosted, gpu, rtx-a5500]
```

Ensure your runner has all three labels configured.

### Step 4: Test Manual Trigger

```bash
# Trigger nightly workflow manually
gh workflow run nightly.yml
```

## Troubleshooting

### Runner Not Picking Up Jobs

**Check service status:**

```bash
sudo systemctl status actions.runner.*.service
journalctl -u actions.runner.* -f
```

**Verify runner is online in GitHub:**

Settings > Actions > Runners should show runner as "Idle" (green)

**Check labels match workflow:**

Workflow expects: `[self-hosted, gpu, rtx-a5500]`
Runner must have ALL these labels.

### GPU Not Available in Container

**Test Docker GPU access:**

```bash
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

**If this fails, reconfigure NVIDIA Container Toolkit:**

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### Permission Denied Errors

```bash
# Add runner user to docker group
sudo usermod -aG docker github-runner

# Apply group changes (runner must restart)
sudo ./svc.sh restart
```

### Runner Shows Offline

**Check network connectivity:**

```bash
curl -I https://github.com
curl -I https://api.github.com
```

**Check systemd service:**

```bash
sudo systemctl status actions.runner.*.service
sudo journalctl -u actions.runner.* --since "1 hour ago"
```

### Jobs Fail with CUDA Errors

**Verify CUDA is accessible:**

```bash
# As github-runner user
su - github-runner
nvidia-smi
python3 -c "import torch; print(torch.cuda.is_available())"
```

**Check CUDA_VISIBLE_DEVICES:**

The workflow sets `CUDA_VISIBLE_DEVICES: "0"` - ensure device 0 is available.

### Out of Disk Space

```bash
# Check disk usage
df -h

# Clean Docker resources
docker system prune -a

# Clean old workflow artifacts
rm -rf /opt/actions-runner/_work/_temp/*
```

## Maintenance

### Update Runner

GitHub requires runners to stay updated within 30 days of new releases.

```bash
# Check current version
cd /opt/actions-runner
./config.sh --version

# Stop service
sudo ./svc.sh stop

# Backup configuration
cp .runner .runner.bak
cp .credentials .credentials.bak

# Download new version
RUNNER_VERSION="2.321.0"  # Check GitHub releases
curl -o actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz -L \
  https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

# Extract (preserves configuration)
tar xzf actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

# Restart service
sudo ./svc.sh start
```

### Monitor GPU Usage During Runs

```bash
# Real-time GPU monitoring
watch -n 1 nvidia-smi

# Monitor runner logs
journalctl -u actions.runner.* -f
```

### View Recent Workflow Runs

```bash
# List recent GPU test runs
gh run list --workflow=gpu-tests.yml --limit=10

# View logs for a specific run
gh run view <run-id> --log
```

### Clean Up Old Artifacts

```bash
# Remove old work directories (older than 7 days)
find /opt/actions-runner/_work -type d -mtime +7 -exec rm -rf {} +

# Remove old Docker images
docker image prune -a --filter "until=168h"
```

## Quick Reference

### Workflow Files Using This Runner

| Workflow  | File                              | Schedule           |
| --------- | --------------------------------- | ------------------ |
| GPU Tests | `.github/workflows/gpu-tests.yml` | On PR/push to main |
| Nightly   | `.github/workflows/nightly.yml`   | Daily at 2am EST   |

### Key Commands

```bash
# Runner service management
sudo ./svc.sh status
sudo ./svc.sh start
sudo ./svc.sh stop
sudo ./svc.sh restart

# View logs
journalctl -u actions.runner.* -f

# GPU monitoring
nvidia-smi
watch -n 1 nvidia-smi

# GitHub CLI
gh run list --workflow=gpu-tests.yml
gh run view <run-id> --log
```

### Expected Resource Usage During Tests

| Metric          | Expected | Warning Threshold |
| --------------- | -------- | ----------------- |
| GPU Memory      | 7-10 GB  | >20 GB            |
| GPU Utilization | 50-90%   | Sustained 100%    |
| Test Duration   | 5-15 min | >30 min (timeout) |

## Additional Resources

- [GitHub Self-Hosted Runner Docs](https://docs.github.com/en/actions/hosting-your-own-runners)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/overview.html)
- [GitHub Actions Runner Releases](https://github.com/actions/runner/releases)
- Project AI Setup: `/docs/AI_SETUP.md`
