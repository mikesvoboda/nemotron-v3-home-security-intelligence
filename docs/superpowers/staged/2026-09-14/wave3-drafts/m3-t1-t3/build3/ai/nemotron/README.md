# Nemotron LLM Service - Secure Build Guide

This document describes how to securely build the Nemotron container images using Docker BuildKit secrets.

## Overview

The Nemotron service uses two alternative approaches:

1. **llama.cpp-based server** (`Dockerfile`) - Compiled from source with CUDA support
2. **HuggingFace Transformers server** (`Dockerfile.hf`) - Uses native HuggingFace models with quantization

## Security Best Practices

### HuggingFace Token Management

When building with the HuggingFace Transformers server (`Dockerfile.hf`), you may need to download private models from HuggingFace. BuildKit secrets ensure your token is never exposed in:

- Image layers
- Docker history
- Container logs
- Build cache

**Never use environment variables or build args for secrets:**

```dockerfile
# WRONG - token exposed in layers
ENV HF_TOKEN=hf_abcdef123456
RUN pip install transformers

# WRONG - token visible in history
ARG HF_TOKEN=hf_abcdef123456
RUN HF_TOKEN=${HF_TOKEN} pip install transformers

# CORRECT - token never in image
RUN --mount=type=secret,id=hf_token \
    HF_TOKEN=$(cat /run/secrets/hf_token) \
    pip install transformers
```

## Building the HuggingFace Transformers Server

### Prerequisites

1. Create a HuggingFace account at https://huggingface.co
2. Generate a token at https://huggingface.co/settings/tokens
3. Accept model license at https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B
4. Save your token to `$HOME/.huggingface/token`

```bash
# Create the token file with proper permissions
mkdir -p ~/.huggingface
echo "hf_your_token_here" > ~/.huggingface/token
chmod 600 ~/.huggingface/token
```

### Docker Build

Build with Docker (BuildKit enabled by default in Docker 20.10+):

```bash
# Build with BuildKit secret
docker build \
  --secret id=hf_token,src=$HOME/.huggingface/token \
  -f Dockerfile.hf \
  -t nemotron-hf:latest \
  ai/nemotron/
```

If using an older Docker version without BuildKit, enable it explicitly:

```bash
DOCKER_BUILDKIT=1 docker build \
  --secret id=hf_token,src=$HOME/.huggingface/token \
  -f Dockerfile.hf \
  -t nemotron-hf:latest \
  ai/nemotron/
```

### Podman Build

Build with Podman (BuildKit support available in Podman 3.0+):

```bash
podman build \
  --secret id=hf_token,src=$HOME/.huggingface/token \
  -f Dockerfile.hf \
  -t nemotron-hf:latest \
  ai/nemotron/
```

### Compose Build

When using `docker-compose` or `podman-compose`, you can pass the secret via build args in the compose file, or use environment override:

```yaml
# docker-compose.yml
services:
  nemotron:
    build:
      context: .
      dockerfile: ai/nemotron/Dockerfile.hf
      secrets:
        - hf_token

secrets:
  hf_token:
    file: ~/.huggingface/token
```

Or pass during build:

```bash
docker compose build --secret hf_token=$HOME/.huggingface/token
```

## Verifying Security

### Check that token is NOT in image

```bash
# View image layers - token should not appear
docker history nemotron-hf:latest

# Inspect image config - token should not appear
docker inspect nemotron-hf:latest | jq '.ContainerConfig.Env'

# Check filesystem - token directory should not exist
docker run --rm nemotron-hf:latest ls -la /run/secrets/ 2>/dev/null || echo "Secret mount not present (expected)"
```

### Verify model loaded successfully

```bash
# Run container and check health
docker run --gpus all -p 8091:8091 nemotron-hf:latest &
sleep 5
curl http://localhost:8091/health | jq .
```

## CI/CD Integration

For GitHub Actions, store the HuggingFace token as a repository secret:

1. Navigate to Settings > Secrets and variables > Actions
2. Create a new repository secret named `HF_TOKEN`
3. Paste your HuggingFace token as the value

In your workflow file:

```yaml
- name: Build Nemotron HF
  run: |
    # Create temporary secret file with proper permissions
    mkdir -p /tmp/hf_secrets
    echo "${{ secrets.HF_TOKEN }}" > /tmp/hf_secrets/hf_token
    chmod 600 /tmp/hf_secrets/hf_token

    # Build with secret mount
    docker build \
      --secret id=hf_token,src=/tmp/hf_secrets/hf_token \
      -f Dockerfile.hf \
      -t nemotron-hf:${{ github.sha }} \
      ai/nemotron/

    # Clean up
    rm -rf /tmp/hf_secrets
```

## Troubleshooting

### "Secret not found" error

Ensure the secret file exists and is readable:

```bash
ls -l ~/.huggingface/token
```

If the file doesn't exist, create it:

```bash
mkdir -p ~/.huggingface
echo "hf_your_token_here" > ~/.huggingface/token
chmod 600 ~/.huggingface/token
```

### BuildKit not enabled

Check if BuildKit is available:

```bash
# Docker
docker buildx version

# Podman
podman version | grep -i buildah
```

Enable BuildKit:

```bash
# For Docker
export DOCKER_BUILDKIT=1

# For Podman - BuildKit enabled by default in 3.0+
podman --version
```

### Model download still fails

Verify your token has the correct permissions:

1. Check token is valid: https://huggingface.co/settings/tokens
2. Accept model license: https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B
3. Check file permissions: `ls -l ~/.huggingface/token` should show `600`

## References

- [Docker BuildKit Documentation](https://docs.docker.com/build/buildkit/)
- [Podman Build Secrets](https://docs.podman.io/en/latest/markdown/podman-build.1.html#secret)
- [HuggingFace Model Access](https://huggingface.co/docs/hub/models-gating)
- [HuggingFace Token Management](https://huggingface.co/docs/hub/security-tokens)
- Related: NEM-3806 (Docker BuildKit Secrets), NEM-3810 (BitsAndBytes Quantization), NEM-3811 (FlashAttention-2)
