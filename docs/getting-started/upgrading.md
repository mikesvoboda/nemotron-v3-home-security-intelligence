---
title: Upgrading
description: Guide for upgrading Home Security Intelligence to new versions
source_refs:
  - scripts/setup-hooks.sh:1
  - ai/download_models.sh:1
  - docker-compose.prod.yml:1
  - pyproject.toml:1
  - uv.lock:1
  - frontend/package.json:1
  - backend/core/database.py:407
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

## How Versions and the Database Work Here

- **Versioning:** the app is pre-1.0 (`version = "0.1.0"` in `pyproject.toml`; the only git tag is `v0.1.0`). Track upstream by branch and commit, not release tags.
- **Database schema:** there is **no Alembic and no migration tooling**. On startup the backend runs `ModelsBase.metadata.create_all`, which creates missing tables but never alters existing ones. Upgrades that add new tables need no action; upgrades that change an existing table's columns require manual `ALTER TABLE` (check the changelog) — which is exactly why you back up first.

## Before You Upgrade

### Backup Your Data

```bash
mkdir -p backups

# Stop the application (keep postgres out — the dump below restarts it)
podman compose -f docker-compose.prod.yml down

# Backup PostgreSQL via a throwaway dump
podman compose -f docker-compose.prod.yml up -d postgres
podman compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U security security | gzip > backups/postgres-$(date +%Y%m%d).sql.gz
podman compose -f docker-compose.prod.yml stop postgres

# Backup configuration
cp .env backups/.env.$(date +%Y%m%d)
```

### Check Release Notes

Review the changelog for breaking changes:

```bash
# View CHANGELOG
cat CHANGELOG.md

# Or check GitHub releases
# https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/releases
```

---

## Standard Upgrade Process

### Step 1: Stop Services

```bash
# Stop AI servers if you run them on the host (Ctrl+C in their terminals)

# Stop containers
podman compose -f docker-compose.prod.yml down
```

### Step 2: Pull Latest Code

```bash
# Fetch updates
git fetch origin

# Record where you are, so you can roll back
git rev-parse HEAD

# Pull latest
git pull origin main

# Or check out a specific commit you know works
git checkout <commit-sha>
```

### Step 3: Update Dependencies

Only needed if you run the backend or frontend on the host. Containers rebuild from the checked-in lockfiles.

```bash
# Update Python dependencies using uv (10-100x faster than pip)
uv sync --extra dev

# Update Node dependencies
cd frontend && npm ci && cd ..
```

### Step 4: Rebuild Containers

This project uses Podman; plain `docker compose` works too. Always rebuild without cache — cached layers may contain stale code.

```bash
# Rebuild with new code
podman compose -f docker-compose.prod.yml build --no-cache

# Or pull pre-built images (if using a registry)
podman compose -f docker-compose.prod.yml pull
```

### Step 5: Start Services

```bash
# Full containerized stack — AI included, no host scripts needed
podman compose -f docker-compose.prod.yml up -d

# (Development mode only: start host AI servers in separate terminals
#  BEFORE the stack, and point YOLO26_URL/NEMOTRON_URL at them — see First Run)
```

### Step 6: Verify

```bash
# Wait for health, then check
podman compose -f docker-compose.prod.yml ps          # all Up (healthy)
curl http://localhost:8000/api/system/health

# Version is whatever git says — there is no /api/system/version endpoint
git rev-parse --short HEAD
```

---

## Quick Upgrade (No Breaking Changes)

For minor updates without breaking changes:

```bash
# Pull and restart
git pull origin main
podman compose -f docker-compose.prod.yml up -d --build
```

---

## Upgrading AI Models

When new model versions are released:

### Check for Model Updates

```bash
# Production LLM (download_models.sh target)
ls -la /export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km/

# Host-dev LLM used by ./ai/start_llm.sh
ls -la ai/nemotron/*.gguf

# YOLO26 weights are cached by HuggingFace; verify the gateway instead:
curl http://localhost:8090/yolo26/health
```

### Download New Models

```bash
# Stop the AI stack first
podman compose -f docker-compose.prod.yml stop ai-gateway ai-llm

# Move the old production model aside if you want a fallback
mv /export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km \
   /export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km.bak

# Download new models (writes to $AI_MODELS_PATH, default /export/ai_models)
./ai/download_models.sh

# Restart
podman compose -f docker-compose.prod.yml up -d ai-gateway ai-llm
```

---

## Rollback Procedure

If an upgrade causes issues:

### Quick Rollback

```bash
# Stop services
podman compose -f docker-compose.prod.yml down

# Checkout the previous commit (the SHA you recorded in Step 2)
git checkout <previous-commit-sha>

# Restore configuration
cp backups/.env.YYYYMMDD .env

# Rebuild and start
podman compose -f docker-compose.prod.yml build --no-cache
podman compose -f docker-compose.prod.yml up -d
```

### Database Rollback

There is no `alembic downgrade` — no migration tool exists. Two honest options:

1. **Restore the dump you took before upgrading** (works even if the new schema added tables, since the dump predates them):

   ```bash
   podman compose -f docker-compose.prod.yml up -d postgres
   gunzip -c backups/postgres-YYYYMMDD.sql.gz | \
     podman compose -f docker-compose.prod.yml exec -T postgres \
     psql -U security security
   ```

2. **Start without restoring** if you only changed config — the old code usually runs fine against a schema that merely has extra tables.

### Full Data Restore

For complete rollback including data:

```bash
# Stop everything and remove volumes (deletes the current database!)
podman compose -f docker-compose.prod.yml down -v

# Recreate the database volume and start postgres
podman compose -f docker-compose.prod.yml up -d postgres

# Load the backup dump
gunzip -c backups/postgres-YYYYMMDD.sql.gz | \
  podman compose -f docker-compose.prod.yml exec -T postgres \
  psql -U security security

# Checkout the old version and restart everything
git checkout <previous-commit-sha>
podman compose -f docker-compose.prod.yml up -d --build
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
podman compose -f docker-compose.prod.yml up -d postgres
podman compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U security security | gzip > "$BACKUP_DIR/postgres.sql.gz"
podman compose -f docker-compose.prod.yml down

# Update
git fetch origin
git checkout "$VERSION"

# Rebuild and start (host deps only if you run services outside containers)
podman compose -f docker-compose.prod.yml build --no-cache
podman compose -f docker-compose.prod.yml up -d

echo "Upgrade complete. Backup saved to $BACKUP_DIR"
```

---

## Troubleshooting Upgrades

### Dependencies won't install

```bash
# Clear uv cache
uv cache clean

# Clear npm cache
cd frontend && rm -rf node_modules && npm cache clean --force && npm ci
```

### Schema looks out of date after a rollback

`create_all` only adds missing **tables** — it never adds or changes **columns** on an existing table. If the app errors about a missing column, add it by hand or restore a database dump from before the change (see Database Rollback).

### Container won't start after upgrade

```bash
# View logs
podman compose -f docker-compose.prod.yml logs backend

# Check for configuration issues
podman compose -f docker-compose.prod.yml config
```

---

## Next Steps

- **[Configuration Reference](../reference/config/env-reference.md)** - Review new configuration options
- **[Troubleshooting](../reference/troubleshooting/index.md)** - Resolve common issues
- **[CHANGELOG](../../CHANGELOG.md)** - Full version history
