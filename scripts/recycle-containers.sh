#!/usr/bin/env bash
# recycle-containers.sh - Full container reset with volume cleanup and no-cache rebuild
#
# Usage:
#   ./scripts/recycle-containers.sh              # Full recycle (all containers)
#   ./scripts/recycle-containers.sh backend      # Recycle specific service(s)
#   ./scripts/recycle-containers.sh --help       # Show help
#
# This script:
#   1. Stops all containers
#   2. Removes all containers
#   3. Destroys all volumes (WARNING: data loss!)
#   4. Rebuilds all images with --no-cache
#   5. Regenerates .env and docker-compose.override.yml
#   6. Starts all containers fresh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.prod.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] [SERVICE...]

Full container reset with volume cleanup and no-cache rebuild.

Options:
    -h, --help          Show this help message
    -y, --yes           Skip confirmation prompt
    --keep-volumes      Don't destroy volumes (faster, keeps data)
    --no-rebuild        Skip the rebuild step (use existing images)

Arguments:
    SERVICE...          Specific service(s) to recycle (default: all)

Examples:
    $(basename "$0")                    # Full recycle of all services
    $(basename "$0") backend            # Recycle only backend
    $(basename "$0") backend frontend   # Recycle backend and frontend
    $(basename "$0") --keep-volumes     # Recycle without destroying volumes
    $(basename "$0") -y                 # Skip confirmation

WARNING: This destroys all data in volumes unless --keep-volumes is used!
EOF
}

# Parse arguments
SKIP_CONFIRM=false
KEEP_VOLUMES=false
NO_REBUILD=false
SERVICES=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -y|--yes)
            SKIP_CONFIRM=true
            shift
            ;;
        --keep-volumes)
            KEEP_VOLUMES=true
            shift
            ;;
        --no-rebuild)
            NO_REBUILD=true
            shift
            ;;
        -*)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
        *)
            SERVICES+=("$1")
            shift
            ;;
    esac
done

cd "$PROJECT_DIR"

# Confirmation
if [[ "$SKIP_CONFIRM" == "false" ]]; then
    if [[ "$KEEP_VOLUMES" == "false" ]]; then
        log_warn "This will DESTROY ALL DATA in volumes!"
    fi
    echo ""
    read -p "Are you sure you want to continue? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Aborted."
        exit 0
    fi
fi

# Step 1: Stop containers
log_info "Stopping containers..."
if [[ ${#SERVICES[@]} -eq 0 ]]; then
    podman-compose -f "$COMPOSE_FILE" down --timeout 5 || true
else
    for svc in "${SERVICES[@]}"; do
        podman-compose -f "$COMPOSE_FILE" stop --timeout 5 "$svc" || true
        podman-compose -f "$COMPOSE_FILE" rm -f "$svc" || true
    done
fi

# Step 2: Remove volumes (if not keeping)
if [[ "$KEEP_VOLUMES" == "false" ]]; then
    log_info "Destroying volumes..."
    if [[ ${#SERVICES[@]} -eq 0 ]]; then
        podman-compose -f "$COMPOSE_FILE" down -v --timeout 5 || true
        # Also prune any orphaned volumes
        podman volume prune -f || true
    else
        log_warn "Selective volume removal not supported, skipping volume cleanup for specific services"
    fi
fi

# Step 3: Rebuild images (if not skipping)
if [[ "$NO_REBUILD" == "false" ]]; then
    log_info "Rebuilding images with --no-cache..."
    if [[ ${#SERVICES[@]} -eq 0 ]]; then
        podman-compose -f "$COMPOSE_FILE" build --no-cache
    else
        podman-compose -f "$COMPOSE_FILE" build --no-cache "${SERVICES[@]}"
    fi
fi

# Step 4: Regenerate config (only for full recycle)
if [[ ${#SERVICES[@]} -eq 0 ]]; then
    log_info "Regenerating configuration..."
    # Run setup in non-interactive mode by piping empty input
    "$PROJECT_DIR/setup.sh" <<< "" || {
        log_warn "Setup script failed, continuing with existing config"
    }
fi

# Step 5: Start containers
log_info "Starting containers..."
if [[ ${#SERVICES[@]} -eq 0 ]]; then
    podman-compose -f "$COMPOSE_FILE" up -d
else
    podman-compose -f "$COMPOSE_FILE" up -d "${SERVICES[@]}"
fi

# Step 6: Wait for health
log_info "Waiting for containers to become healthy..."
sleep 10

# Show status
log_info "Container status:"
podman ps --format "table {{.Names}}\t{{.Status}}" | head -20

log_info "Recycle complete!"
