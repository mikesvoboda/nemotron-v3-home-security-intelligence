# Nemotron HuggingFace BuildKit Secrets - Implementation Guide

This guide provides step-by-step instructions for implementing BuildKit secrets in the Nemotron HuggingFace deployment pipeline.

## Overview

The Nemotron HuggingFace Transformers server (NEM-3806) uses BuildKit secrets to securely handle the HuggingFace API token during container builds. This ensures:

- Token is never exposed in image layers
- Token is never visible in `docker history`
- Token is never logged or persisted in the container
- Secure handling across local development and CI/CD pipelines

## File Changes

### 1. Updated: `ai/nemotron/Dockerfile.hf`

The Dockerfile has been updated to:

- Add `syntax=docker/dockerfile:1.4` directive for BuildKit secrets support
- Use `RUN --mount=type=secret,id=hf_token` to mount the secret
- Extract token from `/run/secrets/hf_token` at build time
- Never persist the token in environment variables

Key section:

```dockerfile
RUN --mount=type=secret,id=hf_token \
    HF_TOKEN=$(cat /run/secrets/hf_token 2>/dev/null || echo "") && \
    export HF_TOKEN && \
    pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu121 && \
    pip3 install --no-cache-dir -r requirements_hf.txt && \
    unset HF_TOKEN
```

### 2. Created: `ai/nemotron/README.md`

Comprehensive guide for building the Nemotron HuggingFace server with secure BuildKit secrets.

### 3. Created: `docs/development/buildkit-secrets.md`

Detailed documentation on BuildKit secrets usage patterns for CI/CD and local development.

### 4. Optional: `.github/workflows/deploy.yml`

To fully integrate nemotron-hf builds into the deploy workflow, add the following:

**A. Update matrix to include nemotron-hf:**

```yaml
strategy:
  fail-fast: false
  matrix:
    image:
      - name: backend
        context: .
        dockerfile: ./backend/Dockerfile
        target: prod
      - name: frontend
        context: ./frontend
        dockerfile: ./frontend/Dockerfile
        target: prod
      - name: ai-yolo26
        context: .
        dockerfile: ./ai/yolo26/Dockerfile
      - name: nemotron-hf
        context: .
        dockerfile: ./ai/nemotron/Dockerfile.hf
        use_hf_secret: true
```

**B. Add secret preparation before build step:**

```yaml
- name: Prepare BuildKit secret for nemotron-hf
  if: matrix.image.use_hf_secret == true && secrets.HF_TOKEN != ''
  run: |
    mkdir -p /tmp/build_secrets
    echo "${{ secrets.HF_TOKEN }}" > /tmp/build_secrets/hf_token
    chmod 600 /tmp/build_secrets/hf_token
    echo "secret_file=/tmp/build_secrets/hf_token" >> $GITHUB_ENV
  env:
    HF_TOKEN: ${{ secrets.HF_TOKEN }}
```

**C. Update build step to use secret:**

```yaml
- name: Build and push by digest
  id: build
  uses: docker/build-push-action@ca052bb54ab0790a636c9b5f226502c73d547a25 # v5
  with:
    context: ${{ matrix.image.context }}
    file: ${{ matrix.image.dockerfile }}
    target: ${{ matrix.image.target || '' }}
    platforms: ${{ matrix.platform.arch }}
    labels: ${{ steps.meta.outputs.labels }}
    outputs: type=image,name=${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/${{ matrix.image.name }},push-by-digest=true,name-canonical=true,push=true
    cache-from: type=gha,scope=${{ matrix.image.name }}-${{ matrix.platform.suffix }}
    cache-to: type=gha,mode=max,scope=${{ matrix.image.name }}-${{ matrix.platform.suffix }}
    secrets: ${{ matrix.image.use_hf_secret == true && format('hf_token={0}', env.secret_file) || '' }}
```

**D. Clean up after build:**

```yaml
- name: Clean up BuildKit secret file
  if: always() && matrix.image.use_hf_secret == true && env.secret_file != ''
  run: |
    rm -rf /tmp/build_secrets
    echo "secret_file=" >> $GITHUB_ENV
```

**E. Update merge job matrix:**

```yaml
strategy:
  matrix:
    image: [backend, frontend, nemotron-hf]
```

**F. Update SBOM and sign job matrix:**

```yaml
strategy:
  matrix:
    image: [backend, frontend, nemotron-hf]
```

**G. Update SLSA provenance job matrix:**

```yaml
strategy:
  matrix:
    image: [backend, frontend, nemotron-hf]
```

## GitHub Setup

### 1. Create HF_TOKEN Secret

Store your HuggingFace token in GitHub repository secrets:

1. Go to repository Settings
2. Navigate to **Secrets and variables** > **Actions**
3. Click **New repository secret**
4. Name: `HF_TOKEN`
5. Value: Your HuggingFace API token (from https://huggingface.co/settings/tokens)
6. Click **Add secret**

### 2. Verify Token Permissions

1. Ensure token has **read** or **write** permissions
2. Accept model license at https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B
3. Verify token works locally:

```bash
huggingface-cli whoami --token $HF_TOKEN
```

## Local Development

### Docker Build

```bash
# Create token file
mkdir -p ~/.huggingface
echo "hf_your_token_here" > ~/.huggingface/token
chmod 600 ~/.huggingface/token

# Build with secret
docker build \
  --secret id=hf_token,src=$HOME/.huggingface/token \
  -f ai/nemotron/Dockerfile.hf \
  -t nemotron-hf:latest .
```

### Podman Build

```bash
podman build \
  --secret id=hf_token,src=$HOME/.huggingface/token \
  -f ai/nemotron/Dockerfile.hf \
  -t nemotron-hf:latest .
```

### Compose Build

```bash
docker compose build \
  --build-arg HF_TOKEN=$(cat ~/.huggingface/token) \
  nemotron-hf
```

Or with secrets mounted:

```yaml
# docker-compose.yml
services:
  nemotron-hf:
    build:
      context: .
      dockerfile: ai/nemotron/Dockerfile.hf
      secrets:
        - hf_token

secrets:
  hf_token:
    file: ~/.huggingface/token
```

## Security Verification

### Verify Token is NOT in Image

```bash
# Check image layers (token should not appear)
docker history nemotron-hf:latest

# Check image environment variables (token should not appear)
docker inspect nemotron-hf:latest | jq '.ContainerConfig.Env'

# Run container and check for secret mount (should be empty)
docker run --rm nemotron-hf:latest ls /run/secrets/ 2>/dev/null || echo "No secrets (expected)"
```

### Verify Model Downloaded

```bash
# Start container
docker run --gpus all -p 8091:8091 nemotron-hf:latest &

# Check health endpoint
sleep 5
curl http://localhost:8091/health | jq .
```

Expected output includes:

- `"model_loaded": true`
- `"quantization": "4bit"`
- `"vram_used_gb": <value>`

## Implementation Checklist

### Phase 1: Local Development

- [ ] Update Dockerfile.hf with syntax directive and secret mount
- [ ] Create README.md with secure build instructions
- [ ] Test Docker build with secret locally
- [ ] Test Podman build with secret locally
- [ ] Verify token not in image layers

### Phase 2: Documentation

- [ ] Create buildkit-secrets.md guide
- [ ] Create nemotron-buildkit-secrets.md implementation guide
- [ ] Document GitHub secret setup
- [ ] Document CI/CD integration pattern

### Phase 3: CI/CD Integration (Optional)

- [ ] Add HF_TOKEN secret to GitHub repository
- [ ] Add nemotron-hf to deploy.yml build matrix
- [ ] Add secret preparation step
- [ ] Add clean up step
- [ ] Update merge, SBOM, SLSA jobs
- [ ] Test in CI/CD pipeline
- [ ] Verify images pushed to GHCR

### Phase 4: Production

- [ ] Enable nemotron-hf builds in main branch
- [ ] Monitor GHCR for successful builds
- [ ] Update deployment documentation
- [ ] Test production deployment

## Related Issues

- **NEM-3806**: Docker BuildKit Secrets for HuggingFace Token (this issue)
- **NEM-3810**: BitsAndBytes 4-bit quantization support
- **NEM-3811**: FlashAttention-2 integration
- **NEM-3736**: Epic - Platform Technology Improvements

## References

- [Docker BuildKit Secrets](https://docs.docker.com/build/buildkit/)
- [Dockerfile Syntax Version 1.4](https://docs.docker.com/build/dockerfile/frontend/)
- [HuggingFace Token Management](https://huggingface.co/docs/hub/security-tokens)
- [Podman Build Secrets](https://docs.podman.io/en/latest/markdown/podman-build.1.html#secret)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)

## Troubleshooting

### BuildKit Not Available

```bash
# Check Docker BuildKit
docker buildx version

# Enable for next build
export DOCKER_BUILDKIT=1
docker build ...
```

### Secret File Not Found

```bash
# Verify file exists
ls -l ~/.huggingface/token

# Create if missing
mkdir -p ~/.huggingface
echo "hf_your_token_here" > ~/.huggingface/token
chmod 600 ~/.huggingface/token
```

### HuggingFace Authentication Errors

- Verify token at: https://huggingface.co/settings/tokens
- Accept model license: https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B
- Test token: `huggingface-cli whoami --token $HF_TOKEN`
- Check file permissions: `chmod 600 ~/.huggingface/token`

### GitHub Actions Secret Issues

- Verify secret name matches exactly: `HF_TOKEN`
- Secrets are not visible in logs (this is expected)
- Check repository (not organization) secrets
- Verify job permissions include contents and packages access

## Support

For questions or issues, refer to:

- `docs/development/buildkit-secrets.md` - General BuildKit secrets guide
- `ai/nemotron/README.md` - Nemotron-specific build instructions
- `CLAUDE.md` - Project guidelines
