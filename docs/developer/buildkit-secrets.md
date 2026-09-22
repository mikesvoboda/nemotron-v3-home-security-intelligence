# Docker BuildKit Secrets for CI/CD

This guide explains how to securely use BuildKit secrets in the CI/CD pipeline, with a focus on the HuggingFace token for the Nemotron LLM service.

## Overview

BuildKit secrets ensure sensitive credentials are never exposed in:

- Container image layers
- Docker history
- Build cache
- Container logs
- Build output

They are mounted at `/run/secrets/<id>` during the build process and are automatically cleaned up after the build completes.

## Setting Up HuggingFace Token Secret

### 1. Create GitHub Repository Secret

Store your HuggingFace token as a repository secret:

1. Navigate to your repository Settings
2. Go to **Secrets and variables** > **Actions**
3. Click **New repository secret**
4. Name: `HF_TOKEN`
5. Value: Your HuggingFace API token (from https://huggingface.co/settings/tokens)
6. Click **Add secret**

The token will be available in GitHub Actions workflows as `${{ secrets.HF_TOKEN }}`.

### 2. Create HuggingFace Account & Token

If you don't have a HuggingFace account yet:

1. Sign up at https://huggingface.co
2. Go to https://huggingface.co/settings/tokens
3. Create a new token (select "read" or "write" as needed)
4. Copy the token value

### 3. Accept Model Licenses

For proprietary models like Nemotron, you must accept the model license:

1. Navigate to the model page: https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B
2. Check "I have read the Nemotron-3-Nano-30B-A3B model card..."
3. Accept the license
4. Your token now has access to download this model

## GitHub Actions Workflow Implementation

### Basic Example

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      # Create temporary secret file (secure approach)
      - name: Prepare BuildKit secret
        if: secrets.HF_TOKEN != ''
        run: |
          mkdir -p /tmp/build_secrets
          echo "${{ secrets.HF_TOKEN }}" > /tmp/build_secrets/hf_token
          chmod 600 /tmp/build_secrets/hf_token

      # Build with secret mount
      - name: Build with BuildKit secret
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile
          secrets: hf_token=/tmp/build_secrets/hf_token
          push: true

      # Clean up
      - name: Clean up secret file
        if: always()
        run: rm -rf /tmp/build_secrets
```

### Dockerfile Usage

In your `Dockerfile`, mount the secret at build time:

```dockerfile
# syntax=docker/dockerfile:1.4

# Use the secret during pip install
RUN --mount=type=secret,id=hf_token \
    HF_TOKEN=$(cat /run/secrets/hf_token) \
    pip install transformers
```

Or for model downloads:

```dockerfile
# syntax=docker/dockerfile:1.4

RUN --mount=type=secret,id=hf_token \
    HF_TOKEN=$(cat /run/secrets/hf_token) \
    huggingface-cli download nvidia/Nemotron-3-Nano-30B-A3B
```

## Security Best Practices

### DO

- Use BuildKit secret mounts for credentials
- Create temporary files with `chmod 600` permissions
- Clean up secret files in `if: always()` steps
- Use conditional secret setup (`if: secrets.HF_TOKEN != ''`)
- Document secret usage in comments

### DON'T

- Never use environment variables for secrets: `ENV HF_TOKEN=value` # pragma: allowlist secret
- Never use build arguments for secrets: `ARG HF_TOKEN` # pragma: allowlist secret
- Never echo or log secrets to build output
- Never commit secrets to version control
- Never hardcode credentials in Dockerfiles

### Wrong Approaches

```dockerfile
# WRONG - Token visible in layers and history
ENV HF_API_TOKEN=your_token_here
RUN pip install transformers

# WRONG - Token visible in build args
ARG HF_API_TOKEN=your_token_here
RUN HF_API_TOKEN=${HF_API_TOKEN} pip install transformers

# WRONG - Leaked in echo output
RUN echo $HF_API_TOKEN > /tmp/token
```

### Correct Approach

```dockerfile
# CORRECT - Token never in image
RUN --mount=type=secret,id=hf_token \
    HF_TOKEN=$(cat /run/secrets/hf_token) \
    pip install transformers
```

## Implementation in Nemotron Build

The Nemotron HF Dockerfile (`ai/nemotron/Dockerfile.hf`) implements BuildKit secrets:

```yaml
# In .github/workflows/deploy.yml
- name: Prepare BuildKit secret for nemotron-hf
  if: matrix.image.use_hf_secret == true && secrets.HF_TOKEN != ''
  run: |
    mkdir -p /tmp/build_secrets
    echo "${{ secrets.HF_TOKEN }}" > /tmp/build_secrets/hf_token
    chmod 600 /tmp/build_secrets/hf_token

- name: Build with secret
  uses: docker/build-push-action@v5
  with:
    secrets: hf_token=/tmp/build_secrets/hf_token

- name: Clean up
  if: always()
  run: rm -rf /tmp/build_secrets
```

## Local Development

### Using BuildKit Locally with Docker

```bash
# Ensure Docker Buildx is available
docker buildx version

# Build with secret
docker build \
  --secret id=hf_token,src=$HOME/.huggingface/token \
  -f Dockerfile.hf \
  -t nemotron-hf:latest .
```

### Using BuildKit with Podman

```bash
# Create token file
mkdir -p ~/.huggingface
echo "hf_your_token_here" > ~/.huggingface/token
chmod 600 ~/.huggingface/token

# Build with secret
podman build \
  --secret id=hf_token,src=$HOME/.huggingface/token \
  -f Dockerfile.hf \
  -t nemotron-hf:latest .
```

## Verifying Security

### Check That Token is NOT Exposed

```bash
# View image layers - token should never appear
docker history nemotron-hf:latest

# Inspect image config - token should not appear
docker inspect nemotron-hf:latest | jq '.ContainerConfig.Env'

# Check for secret mounts - they're ephemeral and won't exist
docker run --rm nemotron-hf:latest ls -la /run/secrets/ 2>/dev/null || echo "No secrets (expected)"
```

### Verify Model Loaded Successfully

```bash
# Run the image and check health
docker run --gpus all -p 8091:8091 nemotron-hf:latest &
sleep 10
curl http://localhost:8091/health | jq .
```

## Troubleshooting

### BuildKit Not Available

```bash
# Check BuildKit version
docker buildx version

# Enable BuildKit explicitly
export DOCKER_BUILDKIT=1
docker build ...
```

### Secret File Not Found

```bash
# Verify token file exists and is readable
ls -l ~/.huggingface/token

# Create file if missing
mkdir -p ~/.huggingface
echo "your_token_here" > ~/.huggingface/token
chmod 600 ~/.huggingface/token
```

### HuggingFace Token Errors During Build

Error message examples:

- `401 Client Error: Unauthorized`
- `You need to authenticate to this hub`
- `Access Denied`

Solutions:

1. Verify token is valid: https://huggingface.co/settings/tokens
2. Accept model license: https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B
3. Verify token has correct permissions (read/write)
4. Verify file permissions on token file (`chmod 600`)
5. Verify the secret mount path in Dockerfile matches usage

### GitHub Actions Secret Not Available

If the `HF_TOKEN` secret is not available in GitHub Actions:

1. Verify you added the secret to the correct repository (not organization-wide unless intended)
2. Check that the secret name matches exactly: `HF_TOKEN`
3. Verify the job has `permissions: contents: read` or similar
4. Secrets are not visible in workflow logs, so you won't see them in output (this is expected)

## References

- [Docker BuildKit Documentation](https://docs.docker.com/build/buildkit/)
- [Dockerfile `RUN --mount=type=secret`](https://docs.docker.com/build/dockerfile/recipes/#secrets)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)
- [Podman Build Secrets](https://docs.podman.io/en/latest/markdown/podman-build.1.html#secret)
- [HuggingFace Token Management](https://huggingface.co/docs/hub/security-tokens)

## Related Issues

- **NEM-3806**: Docker BuildKit Secrets for HuggingFace Token
- **NEM-3810**: BitsAndBytes 4-bit quantization
- **NEM-3811**: FlashAttention-2 integration
