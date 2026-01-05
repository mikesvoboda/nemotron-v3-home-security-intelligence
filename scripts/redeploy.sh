#!/usr/bin/env bash
# =============================================================================
# Redeploy Script for Home Security Intelligence
# =============================================================================
# Stops all containers, destroys volumes, and redeploys fresh.
# By default uses HYBRID mode: pulls backend/frontend from GHCR, builds AI locally.
#
# Usage:
#   ./scripts/redeploy.sh [OPTIONS]
#
# Options:
#   --help, -h       Show this help message
#   --dry-run        Show what would be done without executing
#   --keep-volumes   Preserve volumes (by default, volumes are DESTROYED)
#   --local          Build all 9 services locally (disable hybrid mode)
#   --ghcr           Use GHCR images only (4 services, no AI)
#   --tag TAG        Image tag for GHCR images (default: latest)
#   --skip-pull      Skip pulling GHCR images
#   --skip-ci-check  Skip CI build status verification (not recommended)
#   --no-seed        Skip database seeding after clean deploy
#   --seed-files N   Touch N random images from /export/foscam to trigger AI pipeline (default: 0)
#   --qa             QA mode: equivalent to --keep-volumes --seed-files 100
#
# Modes:
#   DEFAULT (hybrid): Pull backend/frontend from GHCR, build AI locally (9 services)
#   --local:          Build all 9 services locally
#   --ghcr:           Pull 4 services from GHCR only (no AI)
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
# Mode: "hybrid" (default), "local", or "ghcr"
DEPLOY_MODE="${DEPLOY_MODE:-hybrid}"
SKIP_PULL="${SKIP_PULL:-false}"
SKIP_CI_CHECK="${SKIP_CI_CHECK:-false}"
SKIP_SEED="${SKIP_SEED:-false}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
SEED_FILES_COUNT="${SEED_FILES_COUNT:-0}"
FOSCAM_PATH="${FOSCAM_PATH:-/export/foscam}"

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
        POSTGRES_PASSWORD="security_dev_password"  # pragma: allowlist secret
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
    --local          Build all 9 services locally (disable hybrid mode)
    --ghcr           Use GHCR images only (4 services, no AI)
    --tag TAG        Image tag for GHCR images (default: latest)
    --skip-pull      Skip pulling GHCR images
    --skip-ci-check  Skip CI build status verification (not recommended)
    --no-seed        Skip database seeding after clean deploy
    --seed-files N   Touch N random images from /export/foscam to trigger AI pipeline
    --qa             QA mode: --keep-volumes + --seed-files 100 (quick QA testing)

DESCRIPTION:
    This script performs a CLEAN redeploy of all services:

    1. Force stop ALL running containers (from all compose files)
    2. Clean up pods and orphaned containers
    3. Destroy volumes (postgres, redis data) - unless --keep-volumes
    4. Pull/build images based on mode
    5. Start all containers
    6. Verify deployment health

    HYBRID MODE (default):
      Pulls backend/frontend from GHCR, builds AI services locally.
      All 9 services deployed:
      - Core (GHCR): postgres, redis, backend, frontend
      - AI (local build): ai-detector, ai-llm, ai-florence, ai-clip, ai-enrichment

    LOCAL MODE (--local flag):
      Builds all 9 services locally:
      - Core: postgres, redis, backend, frontend
      - AI: ai-detector, ai-llm, ai-florence, ai-clip, ai-enrichment

    GHCR MODE (--ghcr flag):
      Pulls 4 pre-built services from GitHub Container Registry:
      - postgres, redis, backend, frontend
      (No AI services - use for lightweight deployments)

EXAMPLES:
    # Hybrid mode (default): GHCR for backend/frontend, build AI locally
    ./scripts/redeploy.sh

    # Redeploy but keep database/redis data
    ./scripts/redeploy.sh --keep-volumes

    # QA mode: keep volumes + seed 100 images for AI pipeline testing
    ./scripts/redeploy.sh --qa

    # Seed a specific number of files for testing
    ./scripts/redeploy.sh --keep-volumes --seed-files 50

    # Build everything locally
    ./scripts/redeploy.sh --local

    # Use GHCR images only (4 services, no AI)
    ./scripts/redeploy.sh --ghcr

    # Dry run to see what would happen
    ./scripts/redeploy.sh --dry-run

    # Deploy specific GHCR version
    ./scripts/redeploy.sh --tag abc1234

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

    # Check compose files exist
    print_step "Checking compose files..."
    if [ ! -f "$PROJECT_ROOT/$COMPOSE_FILE_PROD" ]; then
        print_fail "Compose file not found: $COMPOSE_FILE_PROD"
        return 2
    fi
    if [ ! -f "$PROJECT_ROOT/$COMPOSE_FILE_GHCR" ]; then
        print_fail "Compose file not found: $COMPOSE_FILE_GHCR"
        return 2
    fi
    print_success "Found compose files"

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

    # Check GPU for modes that include AI services
    if [ "$DEPLOY_MODE" != "ghcr" ]; then
        print_step "Checking GPU availability..."
        if command -v nvidia-smi &> /dev/null; then
            local gpu_name
            gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
            print_success "GPU detected: $gpu_name"
        else
            print_warn "nvidia-smi not found - AI services may fail to start"
        fi
    fi

    # Check CI build status for modes that use GHCR (hybrid and ghcr)
    if [ "$DEPLOY_MODE" != "local" ] && [ "$SKIP_CI_CHECK" != "true" ]; then
        if ! check_ci_build_status; then
            return 1
        fi
    elif [ "$DEPLOY_MODE" != "local" ] && [ "$SKIP_CI_CHECK" = "true" ]; then
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
    print_header "Stopping All Containers"

    cd "$PROJECT_ROOT"

    # Volume destruction warning
    if [ "$KEEP_VOLUMES" != "true" ]; then
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
    fi

    # Stop containers from BOTH compose files to ensure clean state
    print_step "Stopping containers from all compose files..."

    local down_flags=""
    if [ "$KEEP_VOLUMES" != "true" ]; then
        down_flags="-v"
    fi

    # Stop prod compose containers
    if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_PROD" down $down_flags --remove-orphans 2>/dev/null; then
        print_success "Stopped prod compose containers"
    else
        print_info "No prod containers were running"
    fi

    # Stop GHCR compose containers
    if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_GHCR" down $down_flags --remove-orphans 2>/dev/null; then
        print_success "Stopped GHCR compose containers"
    else
        print_info "No GHCR containers were running"
    fi

    # Force cleanup of any remaining pods and containers (Podman-specific)
    if [ "$CONTAINER_CMD" = "podman" ]; then
        print_step "Cleaning up pods and orphaned containers..."
        if run_cmd $CONTAINER_CMD pod rm -f -a 2>/dev/null; then
            print_success "Pods cleaned up"
        else
            print_info "No pods to clean up"
        fi
        if run_cmd $CONTAINER_CMD stop -a 2>/dev/null; then
            print_success "All containers stopped"
        else
            print_info "No running containers"
        fi
    fi

    if [ "$KEEP_VOLUMES" = "true" ]; then
        print_success "Containers stopped (volumes preserved)"
    else
        print_success "Containers stopped and volumes destroyed"
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

    if [ "$DEPLOY_MODE" = "local" ]; then
        # Build all 9 services locally
        print_step "Building all service images (this may take a few minutes)..."
        if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_PROD" build; then
            print_success "All images built"
        else
            print_fail "Failed to build images"
            return 1
        fi
    elif [ "$DEPLOY_MODE" = "hybrid" ]; then
        # Build only AI services locally
        print_step "Building AI service images (this may take a few minutes)..."
        if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_PROD" build ai-detector ai-llm ai-florence ai-clip ai-enrichment; then
            print_success "AI images built"
        else
            print_fail "Failed to build AI images"
            return 1
        fi
    fi
    # GHCR mode doesn't build anything

    return 0
}

start_containers() {
    print_header "Starting Containers"

    cd "$PROJECT_ROOT"

    if [ "$DEPLOY_MODE" = "local" ]; then
        # Start all 9 services from prod compose
        print_step "Starting all containers from prod compose..."
        if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_PROD" up -d; then
            print_success "All containers started"
        else
            print_fail "Failed to start containers"
            return 1
        fi
    elif [ "$DEPLOY_MODE" = "ghcr" ]; then
        # Start only 4 services from GHCR compose
        print_step "Starting GHCR containers..."
        if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_GHCR" up -d; then
            print_success "GHCR containers started"
        else
            print_fail "Failed to start GHCR containers"
            return 1
        fi
    elif [ "$DEPLOY_MODE" = "hybrid" ]; then
        # Hybrid: Start core services from GHCR, then AI services from prod
        print_step "Starting core containers from GHCR..."
        if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_GHCR" up -d; then
            print_success "Core containers started (postgres, redis, backend, frontend)"
        else
            print_fail "Failed to start core containers"
            return 1
        fi

        print_step "Starting AI containers from prod compose..."
        if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_PROD" up -d ai-detector ai-llm ai-florence ai-clip ai-enrichment; then
            print_success "AI containers started"
        else
            print_fail "Failed to start AI containers"
            return 1
        fi
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

    # Health check endpoints
    local -a services
    services=(
        "Backend:http://localhost:8000/api/system/health/ready"
    )

    # Add AI services for hybrid and local modes
    if [ "$DEPLOY_MODE" != "ghcr" ]; then
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
    $CONTAINER_CMD ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || $COMPOSE_CMD -f "$COMPOSE_FILE_PROD" ps

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

seed_files() {
    local count="$1"

    if [ "$count" -le 0 ]; then
        return 0
    fi

    print_header "Seeding AI Pipeline with Real Images"

    if [ "$DRY_RUN" = "true" ]; then
        print_info "Would touch $count random images from $FOSCAM_PATH"
        return 0
    fi

    # Check if foscam directory exists
    if [ ! -d "$FOSCAM_PATH" ]; then
        print_warn "Foscam directory not found: $FOSCAM_PATH"
        print_warn "Skipping file seeding"
        return 0
    fi

    # Count available images
    local total_images
    total_images=$(find "$FOSCAM_PATH" -name "*.jpg" 2>/dev/null | wc -l)

    if [ "$total_images" -eq 0 ]; then
        print_warn "No JPG images found in $FOSCAM_PATH"
        return 0
    fi

    print_info "Found $total_images images in $FOSCAM_PATH"

    # Adjust count if more than available
    if [ "$count" -gt "$total_images" ]; then
        print_warn "Requested $count but only $total_images available, using all"
        count="$total_images"
    fi

    print_step "Touching $count random images to trigger file watcher..."

    # Select random images and touch them
    # Using shuf for random selection, touch to update timestamp
    local touched=0
    while IFS= read -r file; do
        if touch "$file" 2>/dev/null; then
            ((touched++))
        fi
    done < <(find "$FOSCAM_PATH" -name "*.jpg" 2>/dev/null | shuf -n "$count")

    if [ "$touched" -gt 0 ]; then
        print_success "Touched $touched images - AI pipeline will process them"
        print_info "Monitor progress at http://localhost:5173/ai"
        print_info "View events at http://localhost:5173/timeline"
    else
        print_warn "Failed to touch any images"
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
            --local)
                DEPLOY_MODE="local"
                shift
                ;;
            --ghcr)
                DEPLOY_MODE="ghcr"
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
            --seed-files)
                SEED_FILES_COUNT="$2"
                shift 2
                ;;
            --qa)
                KEEP_VOLUMES="true"
                SEED_FILES_COUNT=100
                shift
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done

    # Determine mode description and service count
    local mode_desc service_count
    case "$DEPLOY_MODE" in
        hybrid)
            mode_desc="Hybrid (GHCR core + local AI)"
            service_count="9"
            ;;
        local)
            mode_desc="Local (build all)"
            service_count="9"
            ;;
        ghcr)
            mode_desc="GHCR only (no AI)"
            service_count="4"
            ;;
    esac

    echo ""
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo -e "${BLUE}${BOLD}  Home Security Intelligence Redeploy      ${NC}"
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo ""
    echo -e "Mode:         ${CYAN}$mode_desc${NC}"
    echo -e "Services:     ${CYAN}$service_count${NC}"
    echo -e "Runtime:      ${CYAN}$COMPOSE_CMD${NC}"
    echo -e "Dry Run:      ${CYAN}$DRY_RUN${NC}"
    echo -e "Keep Volumes: ${CYAN}$KEEP_VOLUMES${NC}"
    if [ "$SEED_FILES_COUNT" -gt 0 ]; then
        echo -e "Seed Files:   ${CYAN}$SEED_FILES_COUNT${NC}"
    fi
    if [ "$DEPLOY_MODE" != "local" ]; then
        echo -e "Image Tag:    ${CYAN}$IMAGE_TAG${NC}"
    fi
    echo -e "Started:      ${CYAN}$(date '+%Y-%m-%d %H:%M:%S')${NC}"

    # Run prerequisite checks
    if ! check_prerequisites; then
        exit 2
    fi

    # Stop containers and optionally destroy volumes
    stop_and_clean

    # Pull GHCR images for hybrid and ghcr modes
    if [ "$DEPLOY_MODE" != "local" ]; then
        if [ "$SKIP_PULL" = "false" ]; then
            if ! pull_images; then
                print_fail "Failed to pull images"
                exit 1
            fi
        else
            print_info "Skipping image pull (--skip-pull specified)"
        fi
    fi

    # Build images for local and hybrid modes
    if [ "$DEPLOY_MODE" != "ghcr" ]; then
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

    # Seed files to trigger AI pipeline if requested
    seed_files "$SEED_FILES_COUNT"

    # Summary
    print_header "Redeploy Complete"
    echo ""
    echo -e "${GREEN}${BOLD}  ✅ REDEPLOY SUCCESSFUL  ${NC}"
    echo ""
    echo "Services ($service_count):"
    echo "  - Backend:  http://localhost:8000"
    echo "  - Frontend: http://localhost:${FRONTEND_PORT}"
    if [ "$DEPLOY_MODE" != "ghcr" ]; then
        echo "  - RT-DETRv2: http://localhost:8090"
        echo "  - Nemotron:  http://localhost:8091"
        echo "  - Florence:  http://localhost:8092"
        echo "  - CLIP:      http://localhost:8093"
        echo "  - Enrichment: http://localhost:8094"
    fi
    echo ""
    echo "Useful commands:"
    echo "  View logs:    $COMPOSE_CMD -f $COMPOSE_FILE_PROD logs -f"
    echo "  Stop:         $COMPOSE_CMD -f $COMPOSE_FILE_PROD down && $COMPOSE_CMD -f $COMPOSE_FILE_GHCR down"
    echo "  Status:       $CONTAINER_CMD ps"
    echo ""

    exit 0
}

# Run main
main "$@"
