#!/bin/bash
# =============================================================================
# Redeploy Script for Home Security Intelligence
# =============================================================================
# Stops all containers, destroys volumes, and redeploys fresh.
# By default uses docker-compose.prod.yml (all 9 services, builds locally).
#
# Usage:
#   ./scripts/redeploy.sh [OPTIONS]
#
# Options:
#   --help, -h       Show this help message
#   --dry-run        Show what would be done without executing
#   --keep-volumes   Preserve volumes (by default, volumes are DESTROYED)
#   --ghcr           Use pre-built GHCR images instead of building locally
#   --tag TAG        Image tag for GHCR mode (default: latest)
#   --skip-pull      Skip pulling images in GHCR mode
#   --skip-ci-check  Skip CI build status verification (not recommended)
#   --no-seed        Skip database seeding after clean deploy
#
# Services (9 total):
#   Core:     postgres, redis, backend, frontend
#   AI:       ai-detector, ai-llm, ai-florence, ai-clip, ai-enrichment
#
# Prerequisites:
#   - Podman or Docker installed
#   - .env file configured (run ./setup.sh if missing)
#   - NVIDIA GPU + nvidia-container-toolkit for AI services
#
# Exit Codes:
#   0 - Redeploy successful
#   1 - Error during redeploy
#   2 - Prerequisite check failed
# =============================================================================

set -e

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default settings
DRY_RUN="${DRY_RUN:-false}"
KEEP_VOLUMES="${KEEP_VOLUMES:-false}"
USE_GHCR="${USE_GHCR:-false}"
SKIP_PULL="${SKIP_PULL:-false}"
SKIP_CI_CHECK="${SKIP_CI_CHECK:-false}"
SKIP_SEED="${SKIP_SEED:-false}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# Compose files
COMPOSE_FILE_PROD="docker-compose.prod.yml"
COMPOSE_FILE_GHCR="docker-compose.ghcr.yml"

# GHCR settings
GHCR_OWNER="${GHCR_OWNER:-mikesvoboda}"
GHCR_REPO="${GHCR_REPO:-nemotron-v3-home-security-intelligence}"

# Load .env file if present
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Ensure POSTGRES_PASSWORD is set
if [ -z "$POSTGRES_PASSWORD" ]; then
    if [ -n "$DATABASE_URL" ]; then
        POSTGRES_PASSWORD=$(echo "$DATABASE_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
    fi
    if [ -z "$POSTGRES_PASSWORD" ]; then
        POSTGRES_PASSWORD="security_dev_password"
    fi
    export POSTGRES_PASSWORD
fi

# Detect container runtime
if command -v podman-compose &> /dev/null; then
    COMPOSE_CMD="podman-compose"
    CONTAINER_CMD="podman"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    CONTAINER_CMD="docker"
else
    echo "Error: Neither podman-compose nor docker compose found"
    exit 2
fi

# =============================================================================
# Colors
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

# =============================================================================
# Utility Functions
# =============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}${BOLD}=== $1 ===${NC}"
}

print_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

run_cmd() {
    if [ "$DRY_RUN" = "true" ]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} $*"
    else
        "$@"
    fi
}

show_help() {
    cat << 'EOF'
Home Security Intelligence - Redeploy Script

USAGE:
    ./scripts/redeploy.sh [OPTIONS]

OPTIONS:
    --help, -h       Show this help message
    --dry-run        Show what would be done without executing
    --keep-volumes   Preserve volumes (by default, volumes are DESTROYED)
    --ghcr           Use pre-built GHCR images (4 services) instead of building (9 services)
    --tag TAG        Image tag for GHCR mode (default: latest)
    --skip-pull      Skip pulling images in GHCR mode
    --skip-ci-check  Skip CI build status verification (not recommended)
    --no-seed        Skip database seeding after clean deploy

DESCRIPTION:
    This script performs a CLEAN redeploy of all services:

    1. Stop all running containers
    2. Destroy volumes (postgres, redis data) - unless --keep-volumes
    3. Build/pull fresh images
    4. Start all containers
    5. Verify deployment health

    DEFAULT MODE (docker-compose.prod.yml):
      Builds all 9 services locally:
      - Core: postgres, redis, backend, frontend
      - AI: ai-detector, ai-llm, ai-florence, ai-clip, ai-enrichment

    GHCR MODE (--ghcr flag):
      Pulls 4 pre-built services from GitHub Container Registry:
      - postgres, redis, backend, frontend
      (AI services must be started separately)

EXAMPLES:
    # Full clean redeploy (builds all 9 services, wipes data)
    ./scripts/redeploy.sh

    # Redeploy but keep database/redis data
    ./scripts/redeploy.sh --keep-volumes

    # Use pre-built GHCR images (4 services only)
    ./scripts/redeploy.sh --ghcr

    # Dry run to see what would happen
    ./scripts/redeploy.sh --dry-run

    # Deploy specific GHCR version
    ./scripts/redeploy.sh --ghcr --tag abc1234

WARNING:
    By default, this script DESTROYS all volumes including:
    - PostgreSQL database (all events, detections, settings)
    - Redis cache

    Use --keep-volumes to preserve existing data.

EOF
}

# =============================================================================
# Main Functions
# =============================================================================

check_prerequisites() {
    print_header "Checking Prerequisites"

    local compose_file
    if [ "$USE_GHCR" = "true" ]; then
        compose_file="$COMPOSE_FILE_GHCR"
    else
        compose_file="$COMPOSE_FILE_PROD"
    fi

    # Check compose file exists
    print_step "Checking compose file..."
    if [ ! -f "$PROJECT_ROOT/$compose_file" ]; then
        print_fail "Compose file not found: $compose_file"
        return 2
    fi
    print_success "Found $compose_file"

    # Check .env file exists
    print_step "Checking environment file..."
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        print_warn ".env file not found - some services may not start correctly"
        echo "  Run ./setup.sh to generate .env"
    else
        print_success "Found .env file"
    fi

    # Check container runtime
    print_step "Checking container runtime..."
    print_success "Using $COMPOSE_CMD ($CONTAINER_CMD)"

    # Check GPU for prod mode
    if [ "$USE_GHCR" != "true" ]; then
        print_step "Checking GPU availability..."
        if command -v nvidia-smi &> /dev/null; then
            local gpu_name
            gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
            print_success "GPU detected: $gpu_name"
        else
            print_warn "nvidia-smi not found - AI services may fail to start"
        fi
    fi

    # Check CI build status for GHCR mode
    if [ "$USE_GHCR" = "true" ] && [ "$SKIP_CI_CHECK" != "true" ]; then
        if ! check_ci_build_status; then
            return 1
        fi
    elif [ "$USE_GHCR" = "true" ] && [ "$SKIP_CI_CHECK" = "true" ]; then
        print_warn "Skipping CI build status check (--skip-ci-check)"
    fi

    return 0
}

check_ci_build_status() {
    print_step "Checking CI build status for main branch..."

    # Check if gh CLI is available
    if ! command -v gh &> /dev/null; then
        print_warn "GitHub CLI (gh) not found - skipping CI status check"
        print_warn "Install with: sudo dnf install gh  OR  brew install gh"
        return 0
    fi

    # Check if authenticated
    if ! gh auth status &> /dev/null 2>&1; then
        print_warn "GitHub CLI not authenticated - skipping CI status check"
        print_warn "Authenticate with: gh auth login"
        return 0
    fi

    local repo="${GHCR_OWNER}/${GHCR_REPO}"

    # Get the latest commit on main
    local latest_sha
    latest_sha=$(gh api "repos/${repo}/commits/main" --jq '.sha' 2>/dev/null)
    if [ -z "$latest_sha" ]; then
        print_fail "Could not fetch latest commit from main branch"
        return 1
    fi
    local short_sha="${latest_sha:0:7}"
    print_info "Latest main commit: $short_sha"

    # Check workflow runs for the CI workflow on main
    # Look for the most recent workflow run that includes container builds
    local workflow_status
    workflow_status=$(gh run list \
        --repo "$repo" \
        --branch main \
        --limit 1 \
        --json conclusion,headSha,name,status \
        --jq '.[0] | "\(.status)|\(.conclusion)|\(.headSha)"' 2>/dev/null)

    if [ -z "$workflow_status" ]; then
        print_warn "Could not fetch workflow status - proceeding anyway"
        return 0
    fi

    local status conclusion run_sha
    status=$(echo "$workflow_status" | cut -d'|' -f1)
    conclusion=$(echo "$workflow_status" | cut -d'|' -f2)
    run_sha=$(echo "$workflow_status" | cut -d'|' -f3)
    local run_short_sha="${run_sha:0:7}"

    # Check if workflow is still running
    if [ "$status" = "in_progress" ] || [ "$status" = "queued" ]; then
        print_fail "CI workflow is still running for commit $run_short_sha"
        echo ""
        echo -e "  ${YELLOW}Wait for CI to complete or use --skip-ci-check to bypass${NC}"
        echo "  View status: gh run list --repo $repo --branch main"
        return 1
    fi

    # Check if workflow succeeded
    if [ "$conclusion" != "success" ]; then
        print_fail "CI workflow failed for commit $run_short_sha (conclusion: $conclusion)"
        echo ""
        echo -e "  ${RED}Container images may not be available or may be broken${NC}"
        echo "  View details: gh run list --repo $repo --branch main"
        echo ""
        echo "  Options:"
        echo "    1. Fix the CI failure and re-run"
        echo "    2. Use --skip-ci-check to bypass this check (not recommended)"
        echo "    3. Use local build mode (remove --ghcr flag)"
        return 1
    fi

    # Verify the successful run is for the latest commit
    if [ "$run_sha" != "$latest_sha" ]; then
        print_warn "Latest CI run ($run_short_sha) doesn't match latest commit ($short_sha)"
        print_warn "A newer commit may not have container images yet"
    fi

    print_success "CI build passed for commit $run_short_sha"
    return 0
}

stop_and_clean() {
    print_header "Stopping Containers"

    cd "$PROJECT_ROOT"

    local compose_file
    if [ "$USE_GHCR" = "true" ]; then
        compose_file="$COMPOSE_FILE_GHCR"
    else
        compose_file="$COMPOSE_FILE_PROD"
    fi

    if [ "$KEEP_VOLUMES" = "true" ]; then
        print_step "Stopping containers (preserving volumes)..."
        if run_cmd $COMPOSE_CMD -f "$compose_file" down; then
            print_success "Containers stopped"
        else
            print_warn "Some containers may not have been running"
        fi
    else
        echo ""
        echo -e "${RED}${BOLD}  ⚠️  WARNING: DESTRUCTIVE OPERATION  ⚠️${NC}"
        echo ""
        echo -e "  This will ${RED}PERMANENTLY DELETE${NC}:"
        echo "    - PostgreSQL database (all events, detections, settings)"
        echo "    - Redis cache"
        echo ""

        if [ "$DRY_RUN" != "true" ]; then
            echo -e "${YELLOW}  Press Ctrl+C within 5 seconds to cancel...${NC}"
            sleep 5
        fi

        print_step "Stopping containers and DESTROYING volumes..."
        if run_cmd $COMPOSE_CMD -f "$compose_file" down -v; then
            print_success "Containers stopped and volumes destroyed"
        else
            print_warn "Some containers may not have been running"
        fi
    fi
}

pull_images() {
    print_header "Pulling Images from GHCR"

    local backend_image="ghcr.io/${GHCR_OWNER}/${GHCR_REPO}/backend:${IMAGE_TAG}"
    local frontend_image="ghcr.io/${GHCR_OWNER}/${GHCR_REPO}/frontend:${IMAGE_TAG}"

    print_step "Pulling backend image..."
    print_info "$backend_image"
    if run_cmd $CONTAINER_CMD pull "$backend_image"; then
        print_success "Backend image pulled"
    else
        print_fail "Failed to pull backend image"
        return 1
    fi

    print_step "Pulling frontend image..."
    print_info "$frontend_image"
    if run_cmd $CONTAINER_CMD pull "$frontend_image"; then
        print_success "Frontend image pulled"
    else
        print_fail "Failed to pull frontend image"
        return 1
    fi

    return 0
}

build_images() {
    print_header "Building Images"

    cd "$PROJECT_ROOT"

    print_step "Building all service images (this may take a few minutes)..."
    if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_PROD" build; then
        print_success "All images built"
    else
        print_fail "Failed to build images"
        return 1
    fi

    return 0
}

start_containers() {
    print_header "Starting Containers"

    cd "$PROJECT_ROOT"

    local compose_file
    if [ "$USE_GHCR" = "true" ]; then
        compose_file="$COMPOSE_FILE_GHCR"
    else
        compose_file="$COMPOSE_FILE_PROD"
    fi

    print_step "Starting all containers..."
    if run_cmd $COMPOSE_CMD -f "$compose_file" up -d; then
        print_success "Containers started"
    else
        print_fail "Failed to start containers"
        return 1
    fi

    return 0
}

verify_deployment() {
    print_header "Verifying Deployment"

    if [ "$DRY_RUN" = "true" ]; then
        print_info "Skipping verification in dry-run mode"
        return 0
    fi

    print_step "Waiting for services to initialize..."
    sleep 10

    local compose_file
    if [ "$USE_GHCR" = "true" ]; then
        compose_file="$COMPOSE_FILE_GHCR"
    else
        compose_file="$COMPOSE_FILE_PROD"
    fi

    # Health check endpoints
    local -a services
    services=(
        "Backend:http://localhost:8000/api/system/health/ready"
    )

    # Add AI services only for prod mode
    if [ "$USE_GHCR" != "true" ]; then
        services+=(
            "RT-DETRv2:http://localhost:8090/health"
            "Nemotron:http://localhost:8091/health"
            "Florence:http://localhost:8092/health"
            "CLIP:http://localhost:8093/health"
            "Enrichment:http://localhost:8094/health"
        )
    fi

    echo ""
    print_step "Service health checks:"
    for svc in "${services[@]}"; do
        local name="${svc%%:*}"
        local url="${svc#*:}"

        # Try multiple times for backend (depends on postgres/redis)
        local attempts=0
        local max_attempts=30
        local healthy=false

        while [ $attempts -lt $max_attempts ]; do
            if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
                healthy=true
                break
            fi
            ((attempts++))
            sleep 2
        done

        if [ "$healthy" = "true" ]; then
            echo -e "  ${GREEN}✓${NC} $name"
        else
            echo -e "  ${RED}✗${NC} $name (not responding after ${max_attempts} attempts)"
        fi
    done

    # Check frontend
    echo ""
    print_step "Checking frontend..."
    if curl -sf --max-time 5 "http://localhost:${FRONTEND_PORT}" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Frontend (port ${FRONTEND_PORT})"
    else
        echo -e "  ${RED}✗${NC} Frontend (port ${FRONTEND_PORT})"
    fi

    # Show running containers
    echo ""
    print_step "Running containers:"
    $COMPOSE_CMD -f "$compose_file" ps

    return 0
}

seed_database() {
    print_header "Seeding Database"

    if [ "$DRY_RUN" = "true" ]; then
        print_info "Skipping database seeding in dry-run mode"
        return 0
    fi

    cd "$PROJECT_ROOT"

    # Check if uv is available
    if ! command -v uv &> /dev/null; then
        print_warn "uv not found - skipping database seeding"
        print_warn "Install uv and run manually:"
        echo "  uv run python scripts/seed-cameras.py --discover"
        echo "  uv run python scripts/seed-mock-events.py --count 25"
        return 0
    fi

    # Seed cameras from filesystem
    print_step "Seeding cameras from /export/foscam..."
    if uv run python scripts/seed-cameras.py --clear --discover 2>&1 | grep -E "(Added|Found|Error|Warning)"; then
        print_success "Cameras seeded"
    else
        print_warn "Camera seeding may have failed"
    fi

    # Seed mock events
    print_step "Seeding mock events and detections..."
    if uv run python scripts/seed-mock-events.py --clear --count 25 2>&1 | grep -E "(Created|Error|Warning)"; then
        print_success "Mock events seeded"
    else
        print_warn "Event seeding may have failed"
    fi

    return 0
}

# =============================================================================
# Main
# =============================================================================

main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                show_help
                exit 0
                ;;
            --dry-run)
                DRY_RUN="true"
                shift
                ;;
            --keep-volumes)
                KEEP_VOLUMES="true"
                shift
                ;;
            --ghcr)
                USE_GHCR="true"
                shift
                ;;
            --skip-pull)
                SKIP_PULL="true"
                shift
                ;;
            --skip-ci-check)
                SKIP_CI_CHECK="true"
                shift
                ;;
            --no-seed)
                SKIP_SEED="true"
                shift
                ;;
            --tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done

    # Determine compose file and mode
    local compose_file mode_desc service_count
    if [ "$USE_GHCR" = "true" ]; then
        compose_file="$COMPOSE_FILE_GHCR"
        mode_desc="GHCR (pre-built images)"
        service_count="4"
    else
        compose_file="$COMPOSE_FILE_PROD"
        mode_desc="Production (local build)"
        service_count="9"
    fi

    echo ""
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo -e "${BLUE}${BOLD}  Home Security Intelligence Redeploy      ${NC}"
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo ""
    echo -e "Mode:         ${CYAN}$mode_desc${NC}"
    echo -e "Services:     ${CYAN}$service_count${NC}"
    echo -e "Compose:      ${CYAN}$compose_file${NC}"
    echo -e "Runtime:      ${CYAN}$COMPOSE_CMD${NC}"
    echo -e "Dry Run:      ${CYAN}$DRY_RUN${NC}"
    echo -e "Keep Volumes: ${CYAN}$KEEP_VOLUMES${NC}"
    if [ "$USE_GHCR" = "true" ]; then
        echo -e "Image Tag:    ${CYAN}$IMAGE_TAG${NC}"
    fi
    echo -e "Started:      ${CYAN}$(date '+%Y-%m-%d %H:%M:%S')${NC}"

    # Run prerequisite checks
    if ! check_prerequisites; then
        exit 2
    fi

    # Stop containers and optionally destroy volumes
    stop_and_clean

    # Pull or build images
    if [ "$USE_GHCR" = "true" ]; then
        if [ "$SKIP_PULL" = "false" ]; then
            if ! pull_images; then
                print_fail "Failed to pull images"
                exit 1
            fi
        else
            print_info "Skipping image pull (--skip-pull specified)"
        fi
    else
        if ! build_images; then
            print_fail "Failed to build images"
            exit 1
        fi
    fi

    # Start containers
    if ! start_containers; then
        print_fail "Failed to start containers"
        exit 1
    fi

    # Verify deployment
    verify_deployment

    # Seed database if volumes were destroyed and seeding not skipped
    if [ "$KEEP_VOLUMES" != "true" ] && [ "$SKIP_SEED" != "true" ]; then
        seed_database
    elif [ "$SKIP_SEED" = "true" ]; then
        print_info "Skipping database seeding (--no-seed specified)"
    fi

    # Summary
    print_header "Redeploy Complete"
    echo ""
    echo -e "${GREEN}${BOLD}  ✅ REDEPLOY SUCCESSFUL  ${NC}"
    echo ""
    echo "Services ($service_count):"
    echo "  - Backend:  http://localhost:8000"
    echo "  - Frontend: http://localhost:${FRONTEND_PORT}"
    if [ "$USE_GHCR" != "true" ]; then
        echo "  - RT-DETRv2: http://localhost:8090"
        echo "  - Nemotron:  http://localhost:8091"
        echo "  - Florence:  http://localhost:8092"
        echo "  - CLIP:      http://localhost:8093"
        echo "  - Enrichment: http://localhost:8094"
    fi
    echo ""
    echo "Useful commands:"
    echo "  View logs:    $COMPOSE_CMD -f $compose_file logs -f"
    echo "  Stop:         $COMPOSE_CMD -f $compose_file down"
    echo "  Restart:      $COMPOSE_CMD -f $compose_file restart"
    echo ""

    exit 0
}

# Run main
main "$@"
