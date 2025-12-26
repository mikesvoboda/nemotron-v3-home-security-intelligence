# Self-Hosted GPU Runner Setup

This document describes how to set up a self-hosted GitHub Actions runner on the RTX A5500 machine for GPU-accelerated CI/CD tests.

## Prerequisites

- Ubuntu 22.04+ or compatible Linux
- NVIDIA RTX A5500 (24GB VRAM)
- NVIDIA Driver 535+ installed
- Docker with NVIDIA Container Toolkit
- GitHub repository admin access

## Installation

### 1. Install NVIDIA Container Toolkit

```bash
# Add NVIDIA repo
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 2. Create Runner User

```bash
sudo useradd -m -s /bin/bash github-runner
sudo usermod -aG docker github-runner
sudo usermod -aG video github-runner
```

### 3. Install GitHub Actions Runner

```bash
# As github-runner user
sudo su - github-runner

# Create directory
mkdir actions-runner && cd actions-runner

# Download latest runner
curl -o actions-runner-linux-x64.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz

tar xzf actions-runner-linux-x64.tar.gz
```

### 4. Configure Runner

Get a registration token from:
`https://github.com/YOUR_USER/nemotron-v3-home-security-intelligence/settings/actions/runners/new`

```bash
./config.sh \
  --url https://github.com/YOUR_USER/nemotron-v3-home-security-intelligence \
  --token YOUR_TOKEN \
  --name "rtx-a5500-runner" \
  --labels "self-hosted,linux,gpu,rtx-a5500" \
  --work "_work"
```

### 5. Install as Service

```bash
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status
```

## Security Considerations

### Fork Protection

When the repository goes public, malicious PRs from forks could execute arbitrary code on your machine.

**Mitigation in workflows:**

```yaml
jobs:
  gpu-test:
    runs-on: [self-hosted, gpu]
    # Only run for non-fork PRs or direct pushes
    if: >
      github.event.pull_request.head.repo.full_name == github.repository ||
      github.event_name == 'push'
```

### Resource Limits

Configure in `/etc/docker/daemon.json`:

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

### Secrets Management

- Never echo secrets in logs
- Use GitHub Environments with protection rules
- Consider ephemeral runners for sensitive workflows

## Troubleshooting

### Runner Not Picking Up Jobs

```bash
sudo ./svc.sh status
journalctl -u actions.runner.*
```

### GPU Not Available in Container

```bash
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### Permission Denied

```bash
sudo usermod -aG docker github-runner
newgrp docker
```

## Maintenance

### Update Runner

```bash
sudo ./svc.sh stop
# Download new version
sudo ./svc.sh start
```

### Monitor GPU Usage

```bash
watch -n 1 nvidia-smi
```
