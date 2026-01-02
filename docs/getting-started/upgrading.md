---
title: Upgrading
description: Guide for upgrading Home Security Intelligence to new versions
source_refs:
  - scripts/setup-hooks.sh:1
  - ai/download_models.sh:1
  - docker-compose.prod.yml:1
  - backend/requirements.txt:1
  - frontend/package.json:1
---

# Upgrading

This guide covers upgrading Home Security Intelligence to new versions.

<!-- Nano Banana Pro Prompt:
"Technical illustration of software upgrade process,
version arrows pointing upward with progress indicators,
dark background #121212, NVIDIA green #76B900 accent lighting,
clean minimalist style, vertical 2:3 aspect ratio,
no text overlays"
-->

---

## Before You Upgrade

### Backup Your Data

```bash
# Stop the application
podman-compose -f docker-compose.prod.yml down

# Backup PostgreSQL
podman run --rm -v postgres_data:/data -v $(pwd)/backups:/backup \
  alpine tar czf /backup/postgres-$(date +%Y%m%d).tar.gz /data

# Backup configuration
cp .env backups/.env.$(date +%Y%m%d)
```

### Check Release Notes

Review the release notes for breaking changes:

```bash
# View CHANGELOG
cat CHANGELOG.md

# Or check GitHub releases
# https://github.com/your-org/home-security-intelligence/releases
```

---

## Standard Upgrade Process

### Step 1: Stop Services

```bash
# Stop AI servers (Ctrl+C in their terminals)

# Stop containers
podman-compose -f docker-compose.prod.yml down
```

### Step 2: Pull Latest Code

```bash
# Fetch updates
git fetch origin

# Check current version
git describe --tags

# Pull latest
git pull origin main

# Or checkout specific version
git checkout v1.2.0
```

### Step 3: Update Dependencies

```bash
# Update Python dependencies using uv (10-100x faster than pip)
uv sync --extra dev

# Update Node dependencies
cd frontend && npm install && cd ..
```

### Step 4: Run Database Migrations

If the release includes database changes:

```bash
# Start PostgreSQL only
podman-compose -f docker-compose.prod.yml up -d postgres

# Run migrations (from backend container or locally)
source .venv/bin/activate
cd backend
alembic upgrade head
```

### Step 5: Rebuild Containers

```bash
# Rebuild with new code
podman-compose -f docker-compose.prod.yml build --no-cache

# Or pull pre-built images (if using registry)
podman-compose -f docker-compose.prod.yml pull
```

### Step 6: Start Services

```bash
# Start AI servers (in separate terminals)
./ai/start_detector.sh
./ai/start_llm.sh

# Start application
podman-compose -f docker-compose.prod.yml up -d
```

### Step 7: Verify

```bash
# Check health
curl http://localhost:8000/api/system/health

# Check version
curl http://localhost:8000/api/system/version
```

---

## Quick Upgrade (No Breaking Changes)

For minor updates without breaking changes:

```bash
# Pull and restart
git pull origin main
podman-compose -f docker-compose.prod.yml up -d --build
```

---

## Upgrading AI Models

When new model versions are released:

### Check for Model Updates

```bash
# View current models
ls -la ai/nemotron/*.gguf
# RT-DETRv2 weights are cached by HuggingFace; verify detector health instead:
# curl http://localhost:8090/health
```

### Download New Models

```bash
# Stop AI servers first
# Ctrl+C in their terminals

# Remove old models (optional - keeps backup)
mv ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf \
   ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf.bak

# Download new models
./ai/download_models.sh

# Restart AI servers
./ai/start_detector.sh
./ai/start_llm.sh
```

---

## Version-Specific Guides

### Upgrading from 0.x to 1.0

Major changes in v1.0:

1. **Database schema changes** - Full migration required
2. **New configuration format** - Check `.env.example` for new variables
3. **Model runtime change** - RT-DETRv2 runs via PyTorch + HuggingFace Transformers (no separate ONNX artifact required)

```bash
# Full upgrade process for 0.x -> 1.0
podman-compose -f docker-compose.prod.yml down
git checkout v1.0.0
cp .env .env.bak
cp .env.example .env
# Merge your settings from .env.bak to .env

# Fresh model download
./ai/download_models.sh

# If you previously had local ONNX/PT artifacts checked in or copied, you can remove them:
rm -f ai/rtdetr/*.onnx ai/rtdetr/*.pt

# Database migration
podman-compose -f docker-compose.prod.yml up -d postgres
source .venv/bin/activate && cd backend && alembic upgrade head

# Full rebuild
podman-compose -f docker-compose.prod.yml build --no-cache
podman-compose -f docker-compose.prod.yml up -d
```

---

## Rollback Procedure

If an upgrade causes issues:

### Quick Rollback

```bash
# Stop services
podman-compose -f docker-compose.prod.yml down

# Checkout previous version
git checkout v1.1.0  # Previous stable version

# Restore configuration
cp backups/.env.YYYYMMDD .env

# Rebuild and start
podman-compose -f docker-compose.prod.yml build
podman-compose -f docker-compose.prod.yml up -d
```

### Database Rollback

If migrations were applied:

```bash
# Downgrade to previous migration
source .venv/bin/activate
cd backend
alembic downgrade -1  # One step back

# Or downgrade to specific revision
alembic downgrade abc123
```

### Full Data Restore

For complete rollback including data:

```bash
# Stop everything
podman-compose -f docker-compose.prod.yml down -v

# Restore PostgreSQL backup
podman run --rm -v postgres_data:/data -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/postgres-YYYYMMDD.tar.gz -C /

# Checkout old version and restart
git checkout v1.1.0
podman-compose -f docker-compose.prod.yml up -d
```

---

## Automated Upgrade Script

For future upgrades, consider using:

```bash
#!/bin/bash
# upgrade.sh - Automated upgrade script

set -e

VERSION=${1:-main}
BACKUP_DIR="backups/$(date +%Y%m%d-%H%M%S)"

echo "Upgrading to $VERSION..."

# Backup
mkdir -p "$BACKUP_DIR"
cp .env "$BACKUP_DIR/"
podman-compose -f docker-compose.prod.yml down

# Update
git fetch origin
git checkout "$VERSION"

# Dependencies
uv sync --extra dev
cd frontend && npm install && cd ..

# Rebuild and start
podman-compose -f docker-compose.prod.yml build
podman-compose -f docker-compose.prod.yml up -d

echo "Upgrade complete. Backup saved to $BACKUP_DIR"
```

---

## Troubleshooting Upgrades

### Dependencies won't install

```bash
# Clear pip cache
pip cache purge

# Clear npm cache
cd frontend && rm -rf node_modules && npm cache clean --force && npm install
```

### Migration fails

```bash
# Check current migration state
source .venv/bin/activate
cd backend
alembic current

# View migration history
alembic history
```

### Container won't start after upgrade

```bash
# View logs
podman-compose -f docker-compose.prod.yml logs backend

# Check for configuration issues
podman-compose -f docker-compose.prod.yml config
```

---

## Next Steps

- **[Configuration](../admin-guide/configuration.md)** - Review new configuration options
- **[Troubleshooting](../admin-guide/troubleshooting.md)** - Resolve common issues
- **[CHANGELOG](../../CHANGELOG.md)** - Full version history
