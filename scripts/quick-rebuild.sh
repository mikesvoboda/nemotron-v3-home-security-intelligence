#!/bin/bash
# quick-rebuild.sh - Quick rebuild for a single service from worktree
#
# Unlike the full redeploy.sh (which does full stack + volumes), this script:
# - Copies changes from worktree to main repo
# - Rebuilds only the specified service (no cache)
# - Restarts only that service
#
# Usage:
#   ./scripts/quick-rebuild.sh frontend     # Rebuild frontend only
#   ./scripts/quick-rebuild.sh backend      # Rebuild backend only
#   ./scripts/quick-rebuild.sh --no-copy frontend  # Skip copy step

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

MAIN_REPO="/home/msvoboda/github/nemotron-v3-home-security-intelligence"
WORKTREE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="docker-compose.prod.yml"

SKIP_COPY=false
TARGET=""

# Parse arguments
for arg in "$@"; do
    case $arg in
        --no-copy) SKIP_COPY=true ;;
        frontend|backend) TARGET="$arg" ;;
    esac
done

if [ -z "$TARGET" ]; then
    echo "Usage: $0 [--no-copy] <frontend|backend>"
    exit 1
fi

log() { echo -e "${BLUE}>>>${NC} $1"; }
ok() { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}!${NC} $1"; }

# Copy files from worktree to main repo
copy_changes() {
    if [ "$SKIP_COPY" = true ]; then
        log "Skipping copy (--no-copy)"
        return
    fi

    if [[ ! "$WORKTREE_DIR" == *"worktrees"* ]]; then
        log "Not in worktree, skipping copy"
        return
    fi

    log "Copying $TARGET changes to main repo..."

    if [ "$TARGET" = "frontend" ]; then
        rsync -av --delete "$WORKTREE_DIR/frontend/src/" "$MAIN_REPO/frontend/src/"
    else
        rsync -av --delete \
            --exclude '__pycache__' --exclude '*.pyc' --exclude '.pytest_cache' \
            "$WORKTREE_DIR/backend/" "$MAIN_REPO/backend/"
    fi
    ok "Changes copied"
}

# Build and restart
rebuild() {
    cd "$MAIN_REPO"
    source .env

    log "Building $TARGET (no cache)..."
    podman-compose -f "$COMPOSE_FILE" build --no-cache "$TARGET"
    ok "Built"

    log "Restarting $TARGET..."
    podman-compose -f "$COMPOSE_FILE" stop "$TARGET" 2>/dev/null || true
    podman rm -f "nemotron-v3-home-security-intelligence_${TARGET}_1" 2>/dev/null || true
    podman-compose -f "$COMPOSE_FILE" up -d "$TARGET"
    ok "Restarted"

    log "Waiting for healthy..."
    for i in {1..30}; do
        status=$(podman ps --filter "name=nemotron-v3-home-security-intelligence_${TARGET}_1" --format "{{.Status}}" 2>/dev/null)
        [[ "$status" == *"healthy"* ]] && { ok "$TARGET is healthy"; return; }
        sleep 2
    done
    warn "$TARGET may still be starting"
}

echo ""
log "Quick rebuild: $TARGET"
copy_changes
rebuild
echo ""
echo "Done! Access at https://localhost:8443"
