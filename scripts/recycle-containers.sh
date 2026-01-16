#!/usr/bin/env bash
# recycle-containers.sh - Full container reset with volume cleanup and no-cache rebuild
#
# Usage:
#   ./scripts/recycle-containers.sh              # Full recycle (all containers)
#   ./scripts/recycle-containers.sh backend      # Recycle specific service(s)
#   ./scripts/recycle-containers.sh --help       # Show help
#
# This script:
#   1. Force stops all containers (with timeout)
#   2. Removes all containers
#   3. Destroys all volumes (WARNING: data loss!)
#   4. Rebuilds all images with --no-cache
#   5. Regenerates .env and docker-compose.override.yml
#   6. Starts all containers fresh
#   7. Waits for health checks to pass

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.prod.yml"

# Timeouts (in seconds)
STOP_TIMEOUT=10
KILL_TIMEOUT=5
BUILD_TIMEOUT=600  # 10 minutes
STARTUP_TIMEOUT=120
HEALTH_TIMEOUT=180  # 3 minutes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${CYAN}[STEP]${NC} $1"; }

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] [SERVICE...]

Full container reset with volume cleanup and no-cache rebuild.
Includes timeouts to prevent hanging on unresponsive containers.

Options:
    -h, --help          Show this help message
    -y, --yes           Skip confirmation prompt
    --keep-volumes      Don't destroy volumes (faster, keeps data)
    --no-rebuild        Skip the rebuild step (use existing images)
    --no-setup          Skip regenerating .env and docker-compose.override.yml
    --build-timeout N   Build timeout in seconds (default: 600)
    --health-timeout N  Health check timeout in seconds (default: 180)

Arguments:
    SERVICE...          Specific service(s) to recycle (default: all)

Examples:
    $(basename "$0")                    # Full recycle of all services
    $(basename "$0") backend            # Recycle only backend
    $(basename "$0") backend frontend   # Recycle backend and frontend
    $(basename "$0") --keep-volumes     # Recycle without destroying volumes
    $(basename "$0") -y                 # Skip confirmation
    $(basename "$0") -y --no-rebuild    # Quick restart without rebuild

Timeouts:
    Container stop:  ${STOP_TIMEOUT}s (then force kill)
    Build:           ${BUILD_TIMEOUT}s
    Health check:    ${HEALTH_TIMEOUT}s

WARNING: This destroys all data in volumes unless --keep-volumes is used!
EOF
}

# Run command with timeout, return success/failure
run_with_timeout() {
    local timeout_secs=$1
    shift
    timeout --signal=KILL "$timeout_secs" "$@" 2>&1
    return $?
}

# Force stop all containers with escalating force
force_stop_all_containers() {
    log_step "Stopping all containers (timeout: ${STOP_TIMEOUT}s)..."

    # Get list of running containers
    local containers
    containers=$(podman ps -q 2>/dev/null || true)

    if [[ -z "$containers" ]]; then
        log_info "No running containers found"
        return 0
    fi

    local count
    count=$(echo "$containers" | wc -l)
    log_info "Found $count running container(s)"

    # Try graceful stop first
    log_info "Attempting graceful stop..."
    podman stop -t "$STOP_TIMEOUT" -a 2>&1 || true

    # Check if any containers still running
    containers=$(podman ps -q 2>/dev/null || true)
    if [[ -n "$containers" ]]; then
        log_warn "Some containers didn't stop gracefully, force killing..."
        podman kill -a 2>&1 || true
        sleep 2
    fi

    # Final check
    containers=$(podman ps -q 2>/dev/null || true)
    if [[ -n "$containers" ]]; then
        log_error "Failed to stop all containers!"
        podman ps
        return 1
    fi

    log_info "All containers stopped"
    return 0
}

# Remove all containers
remove_all_containers() {
    log_step "Removing all containers..."

    local containers
    containers=$(podman ps -aq 2>/dev/null || true)

    if [[ -z "$containers" ]]; then
        log_info "No containers to remove"
        return 0
    fi

    podman rm -f -a 2>&1 || true

    # Verify removal
    containers=$(podman ps -aq 2>/dev/null || true)
    if [[ -n "$containers" ]]; then
        log_error "Failed to remove all containers!"
        return 1
    fi

    log_info "All containers removed"
    return 0
}

# Destroy all volumes
destroy_all_volumes() {
    log_step "Destroying all volumes..."

    # First, use compose to remove project volumes
    podman-compose -f "$COMPOSE_FILE" down -v --timeout 5 2>&1 || true

    # Prune any remaining volumes
    podman volume prune -f 2>&1 || true

    # List remaining volumes (for verification)
    local volumes
    volumes=$(podman volume ls -q 2>/dev/null | grep -E "$(basename "$PROJECT_DIR")" || true)

    if [[ -n "$volumes" ]]; then
        log_warn "Some project volumes remain, force removing..."
        echo "$volumes" | xargs -r podman volume rm -f 2>&1 || true
    fi

    log_info "Volumes destroyed"
    return 0
}

# Build images with timeout
build_images() {
    local services=("$@")

    log_step "Building images with --no-cache (timeout: ${BUILD_TIMEOUT}s)..."

    local build_cmd="podman-compose -f $COMPOSE_FILE build --no-cache"
    if [[ ${#services[@]} -gt 0 ]]; then
        build_cmd="$build_cmd ${services[*]}"
    fi

    if ! run_with_timeout "$BUILD_TIMEOUT" bash -c "$build_cmd"; then
        log_error "Build timed out or failed after ${BUILD_TIMEOUT}s"
        return 1
    fi

    log_info "Build completed successfully"
    return 0
}

# Start containers
start_containers() {
    local services=("$@")

    log_step "Starting containers..."

    if [[ ${#services[@]} -eq 0 ]]; then
        podman-compose -f "$COMPOSE_FILE" up -d 2>&1
    else
        podman-compose -f "$COMPOSE_FILE" up -d "${services[@]}" 2>&1
    fi

    log_info "Containers started"
    return 0
}

# Wait for containers to become healthy
wait_for_health() {
    log_step "Waiting for containers to become healthy (timeout: ${HEALTH_TIMEOUT}s)..."

    local start_time
    start_time=$(date +%s)
    local healthy_count=0
    local total_count=0
    local last_status=""

    while true; do
        local current_time
        current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        if [[ $elapsed -ge $HEALTH_TIMEOUT ]]; then
            log_error "Health check timeout after ${HEALTH_TIMEOUT}s"
            log_info "Current container status:"
            podman ps --format "table {{.Names}}\t{{.Status}}"
            return 1
        fi

        # Count containers by health status
        total_count=$(podman ps --format "{{.Names}}" 2>/dev/null | wc -l)
        healthy_count=$(podman ps --format "{{.Status}}" 2>/dev/null | grep -c "(healthy)" || true)
        local starting_count
        starting_count=$(podman ps --format "{{.Status}}" 2>/dev/null | grep -c "(starting)" || true)
        local unhealthy_count
        unhealthy_count=$(podman ps --format "{{.Status}}" 2>/dev/null | grep -c "(unhealthy)" || true)

        local status="Healthy: $healthy_count, Starting: $starting_count, Unhealthy: $unhealthy_count, Total: $total_count"

        # Only print if status changed
        if [[ "$status" != "$last_status" ]]; then
            log_info "$status (${elapsed}s elapsed)"
            last_status="$status"
        fi

        # Check for unhealthy containers
        if [[ $unhealthy_count -gt 0 ]]; then
            log_warn "Found $unhealthy_count unhealthy container(s)"
            # Continue waiting - might recover
        fi

        # All healthy (accounting for containers without health checks)
        if [[ $starting_count -eq 0 && $unhealthy_count -eq 0 ]]; then
            log_info "All containers healthy or stable"
            break
        fi

        sleep 5
    done

    return 0
}

# Parse arguments
SKIP_CONFIRM=false
KEEP_VOLUMES=false
NO_REBUILD=false
NO_SETUP=false
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
        --no-setup)
            NO_SETUP=true
            shift
            ;;
        --build-timeout)
            BUILD_TIMEOUT="$2"
            shift 2
            ;;
        --health-timeout)
            HEALTH_TIMEOUT="$2"
            shift 2
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
    echo ""
    echo "============================================"
    echo "  Container Recycle Script"
    echo "============================================"
    echo ""
    echo "This will:"
    echo "  1. Stop all running containers"
    echo "  2. Remove all containers"
    if [[ "$KEEP_VOLUMES" == "false" ]]; then
        echo -e "  3. ${RED}DESTROY ALL VOLUMES (data loss!)${NC}"
    else
        echo "  3. Keep volumes (data preserved)"
    fi
    if [[ "$NO_REBUILD" == "false" ]]; then
        echo "  4. Rebuild all images (no cache)"
    else
        echo "  4. Skip rebuild (use existing images)"
    fi
    echo "  5. Start all containers"
    echo "  6. Wait for health checks"
    echo ""
    read -p "Are you sure you want to continue? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Aborted."
        exit 0
    fi
fi

echo ""
log_info "Starting container recycle..."
echo ""

# Step 1: Stop containers
if ! force_stop_all_containers; then
    log_error "Failed to stop containers"
    exit 1
fi

# Step 2: Remove containers
if ! remove_all_containers; then
    log_error "Failed to remove containers"
    exit 1
fi

# Step 3: Remove volumes (if not keeping)
if [[ "$KEEP_VOLUMES" == "false" ]]; then
    if ! destroy_all_volumes; then
        log_warn "Some volumes may not have been removed"
    fi
fi

# Step 4: Rebuild images (if not skipping)
if [[ "$NO_REBUILD" == "false" ]]; then
    if ! build_images "${SERVICES[@]}"; then
        log_error "Build failed"
        exit 1
    fi
fi

# Step 5: Regenerate config (only for full recycle, if not skipping)
if [[ ${#SERVICES[@]} -eq 0 && "$NO_SETUP" == "false" ]]; then
    log_step "Regenerating configuration..."
    # Run setup in non-interactive mode by piping empty input
    if ! "$PROJECT_DIR/setup.sh" <<< ""; then
        log_warn "Setup script failed, continuing with existing config"
    fi
fi

# Step 6: Start containers
if ! start_containers "${SERVICES[@]}"; then
    log_error "Failed to start containers"
    exit 1
fi

# Step 7: Wait for health
if ! wait_for_health; then
    log_warn "Not all containers are healthy, but continuing..."
fi

echo ""
log_info "============================================"
log_info "  Container Recycle Complete!"
log_info "============================================"
echo ""

# Final status
log_info "Final container status:"
podman ps --format "table {{.Names}}\t{{.Status}}" | head -20

echo ""
log_info "Done!"
