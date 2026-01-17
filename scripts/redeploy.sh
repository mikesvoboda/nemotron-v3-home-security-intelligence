#!/usr/bin/env bash
# =============================================================================
# Redeploy Script for Home Security Intelligence
# =============================================================================
# Stops all containers, destroys volumes, and redeploys fresh.
# By default uses LOCAL mode: builds all 9 services from source.
#
# Usage:
#   ./scripts/redeploy.sh [OPTIONS]
#
# Options:
#   --help, -h       Show this help message
#   --dry-run        Show what would be done without executing
#   --keep-volumes   Preserve volumes (by default, volumes are DESTROYED)
#   --hybrid         Pull backend/frontend from GHCR, build AI locally
#   --ghcr           Use GHCR images only (4 services, no AI)
#   --tag TAG        Image tag for GHCR images (default: latest)
#   --skip-pull      Skip pulling GHCR images
#   --skip-ci-check  Skip CI build status verification (not recommended)
#   --no-seed        Skip database seeding after clean deploy
#   --seed-files N   Touch N random images from /export/foscam to trigger AI pipeline (default: 0)
#   --qa             QA mode: equivalent to --keep-volumes --seed-files 100
#
# Modes:
#   DEFAULT (local):  Build all 9 services locally from source
#   --hybrid:         Pull backend/frontend from GHCR, build AI locally (9 services)
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
# Mode: "local" (default), "hybrid", or "ghcr"
DEPLOY_MODE="${DEPLOY_MODE:-local}"
SKIP_PULL="${SKIP_PULL:-false}"
SKIP_CI_CHECK="${SKIP_CI_CHECK:-false}"
SKIP_SEED="${SKIP_SEED:-false}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
SEED_FILES_COUNT="${SEED_FILES_COUNT:-0}"
FOSCAM_PATH="${FOSCAM_PATH:-/export/foscam}"

# Project name for container naming (derived from directory name)
PROJECT_NAME="$(basename "$PROJECT_ROOT" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/_/g')"

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
    --hybrid         Pull backend/frontend from GHCR, build AI locally
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

    LOCAL MODE (default):
      Builds all 9 services locally from source:
      - Core: postgres, redis, backend, frontend
      - AI: ai-detector, ai-llm, ai-florence, ai-clip, ai-enrichment

    HYBRID MODE (--hybrid flag):
      Pulls backend/frontend from GHCR, builds AI services locally.
      All 9 services deployed:
      - Core (GHCR): postgres, redis, backend, frontend
      - AI (local build): ai-detector, ai-llm, ai-florence, ai-clip, ai-enrichment

    GHCR MODE (--ghcr flag):
      Pulls 4 pre-built services from GitHub Container Registry:
      - postgres, redis, backend, frontend
      (No AI services - use for lightweight deployments)

EXAMPLES:
    # Local mode (default): build all services from source
    ./scripts/redeploy.sh

    # Redeploy but keep database/redis data
    ./scripts/redeploy.sh --keep-volumes

    # QA mode: keep volumes + seed 100 images for AI pipeline testing
    ./scripts/redeploy.sh --qa

    # Seed a specific number of files for testing
    ./scripts/redeploy.sh --keep-volumes --seed-files 50

    # Hybrid mode: GHCR for backend/frontend, build AI locally
    ./scripts/redeploy.sh --hybrid

    # Use GHCR images only (4 services, no AI)
    ./scripts/redeploy.sh --ghcr

    # Dry run to see what would happen
    ./scripts/redeploy.sh --dry-run

    # Deploy specific GHCR version (hybrid or ghcr mode)
    ./scripts/redeploy.sh --hybrid --tag abc1234

WARNING:
    By default, this script DESTROYS all volumes including:
    - PostgreSQL database (all events, detections, settings)
    - Redis cache

    Use --keep-volumes to preserve existing data.

EOF
}

# =============================================================================
# Podman-specific Functions (optimized deployment for hybrid mode)
# =============================================================================
# These functions use podman build/run directly to provide:
# - Optimized hybrid deployment (GHCR images + local AI builds)
# - Proper internal network routing for AI services
# - Consistent behavior across Docker and Podman
#
# Note: While podman-compose can now parse docker-compose.prod.yml correctly
# (with version: '3.8' specification), this hybrid approach provides better
# control over service initialization order and network configuration.

stop_ai_containers_podman() {
    # Stop and remove AI containers if they exist (called during cleanup)
    local -a ai_containers=("ai-detector" "ai-llm" "ai-florence" "ai-clip" "ai-enrichment")

    for container in "${ai_containers[@]}"; do
        if $CONTAINER_CMD container exists "$container" 2>/dev/null; then
            run_cmd $CONTAINER_CMD stop "$container" 2>/dev/null || true
            run_cmd $CONTAINER_CMD rm -f "$container" 2>/dev/null || true
        fi
    done
}

build_ai_images_podman() {
    print_header "Building AI Images (podman build)"

    cd "$PROJECT_ROOT"

    local -a ai_services=(
        "ai-detector:./ai/rtdetr"
        "ai-llm:./ai/nemotron"
        "ai-florence:./ai/florence"
        "ai-clip:./ai/clip"
        "ai-enrichment:./ai/enrichment"
    )

    for svc in "${ai_services[@]}"; do
        local name="${svc%%:*}"
        local context="${svc#*:}"

        print_step "Building $name from $context..."
        if run_cmd $CONTAINER_CMD build -t "$name" "$context"; then
            print_success "$name image built"
        else
            print_fail "Failed to build $name"
            return 1
        fi
    done

    return 0
}

start_ai_containers_podman() {
    print_header "Starting AI Containers (podman run)"

    cd "$PROJECT_ROOT"

    # Get network name - podman-compose creates networks with project prefix
    local network_name="nemotron-v3-home-security-intelligence_security-net"

    # Ensure network exists (may have been created by GHCR compose)
    if ! $CONTAINER_CMD network exists "$network_name" 2>/dev/null; then
        print_step "Creating network $network_name..."
        run_cmd $CONTAINER_CMD network create "$network_name" || true
    fi

    # GPU and security flags for podman
    # --device nvidia.com/gpu=all: CDI device for GPU access
    # --security-opt=label=disable: Disable SELinux for GPU device access
    local gpu_flags="--device nvidia.com/gpu=all --security-opt=label=disable"

    # ai-detector (RT-DETRv2)
    print_step "Starting ai-detector..."
    run_cmd $CONTAINER_CMD run -d \
        --name ai-detector \
        --network "$network_name" \
        $gpu_flags \
        -p 8090:8090 \
        -v "${HF_CACHE:-$HOME/.cache/huggingface}:/cache/huggingface:z" \
        -e "RTDETR_CONFIDENCE=${RTDETR_CONFIDENCE:-0.5}" \
        -e "RTDETR_MODEL_PATH=${RTDETR_MODEL_PATH:-PekingU/rtdetr_r50vd_coco_o365}" \
        --restart unless-stopped \
        ai-detector
    print_success "ai-detector started"

    # ai-llm (Nemotron)
    print_step "Starting ai-llm..."
    run_cmd $CONTAINER_CMD run -d \
        --name ai-llm \
        --network "$network_name" \
        $gpu_flags \
        -p 8091:8091 \
        -v "${AI_MODELS_PATH:-/export/ai_models}/nemotron/nemotron-3-nano-30b-a3b-q4km:/models:ro,z" \
        -e "GPU_LAYERS=${GPU_LAYERS:-35}" \
        -e "CTX_SIZE=${CTX_SIZE:-131072}" \
        --restart unless-stopped \
        ai-llm
    print_success "ai-llm started"

    # ai-florence
    print_step "Starting ai-florence..."
    run_cmd $CONTAINER_CMD run -d \
        --name ai-florence \
        --network "$network_name" \
        $gpu_flags \
        -p 8092:8092 \
        -v "${AI_MODELS_PATH:-/export/ai_models}/model-zoo/florence-2-large:/models/florence-2-large:ro,z" \
        -e "MODEL_PATH=/models/florence-2-large" \  # pragma: allowlist secret
        --restart unless-stopped \
        ai-florence
    print_success "ai-florence started"

    # ai-clip
    print_step "Starting ai-clip..."
    run_cmd $CONTAINER_CMD run -d \
        --name ai-clip \
        --network "$network_name" \
        $gpu_flags \
        -p 8093:8093 \
        -v "${AI_MODELS_PATH:-/export/ai_models}/model-zoo/clip-vit-l:/models/clip-vit-l:ro,z" \
        -e "CLIP_MODEL_PATH=/models/clip-vit-l" \  # pragma: allowlist secret
        --restart unless-stopped \
        ai-clip
    print_success "ai-clip started"

    # ai-enrichment
    print_step "Starting ai-enrichment..."
    run_cmd $CONTAINER_CMD run -d \
        --name ai-enrichment \
        --network "$network_name" \
        $gpu_flags \
        -p 8094:8094 \
        -v "${AI_MODELS_PATH:-/export/ai_models}/model-zoo/vehicle-segment-classification:/models/vehicle-segment-classification:ro,z" \
        -v "${AI_MODELS_PATH:-/export/ai_models}/model-zoo/pet-classifier:/models/pet-classifier:ro,z" \
        -v "${AI_MODELS_PATH:-/export/ai_models}/model-zoo/fashion-clip:/models/fashion-clip:ro,z" \
        -v "${AI_MODELS_PATH:-/export/ai_models}/model-zoo/depth-anything-v2-small:/models/depth-anything-v2-small:ro,z" \
        -e "VEHICLE_MODEL_PATH=/models/vehicle-segment-classification" \  # pragma: allowlist secret
        -e "PET_MODEL_PATH=/models/pet-classifier" \  # pragma: allowlist secret
        -e "CLOTHING_MODEL_PATH=/models/fashion-clip" \  # pragma: allowlist secret
        -e "DEPTH_MODEL_PATH=/models/depth-anything-v2-small" \  # pragma: allowlist secret
        --restart unless-stopped \
        ai-enrichment
    print_success "ai-enrichment started"

    return 0
}

# Restart backend with internal network URLs for AI services
# This is needed because podman-compose starts the backend with host.docker.internal URLs,
# but in hybrid mode the AI containers are on the same network and should use container names
restart_backend_with_internal_urls() {
    print_header "Restarting Backend with Internal AI URLs"

    cd "$PROJECT_ROOT"
    source .env 2>/dev/null || true

    local network_name="nemotron-v3-home-security-intelligence_security-net"
    local backend_name="nemotron-v3-home-security-intelligence_backend_1"
    local frontend_name="nemotron-v3-home-security-intelligence_frontend_1"

    # Stop frontend first (depends on backend)
    print_step "Stopping frontend..."
    run_cmd $CONTAINER_CMD stop "$frontend_name" 2>/dev/null || true
    run_cmd $CONTAINER_CMD rm -f "$frontend_name" 2>/dev/null || true

    # Stop backend
    print_step "Stopping backend..."
    run_cmd $CONTAINER_CMD stop "$backend_name" 2>/dev/null || true
    run_cmd $CONTAINER_CMD rm -f "$backend_name" 2>/dev/null || true

    # Start backend with internal network URLs
    print_step "Starting backend with internal AI URLs..."
    run_cmd $CONTAINER_CMD run -d \
        --name "$backend_name" \
        --network "$network_name" \
        --network-alias backend \
        -p 8000:8000 \
        -v "./backend/data:/app/data:z" \
        -v "${FOSCAM_BASE_PATH:-/export/foscam}:/cameras:ro,z" \
        -v "${AI_MODELS_PATH:-/export/ai_models}/model-zoo:/models/model-zoo:ro,z" \
        -e "DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-security}:${POSTGRES_PASSWORD:-security_dev_password}@postgres:5432/${POSTGRES_DB:-security}" \
        -e "REDIS_URL=redis://redis:6379" \
        -e "REDIS_PASSWORD=${REDIS_PASSWORD:-}" \
        -e "RTDETR_URL=http://ai-detector:8090" \
        -e "NEMOTRON_URL=http://ai-llm:8091" \
        -e "FLORENCE_URL=http://ai-florence:8092" \
        -e "CLIP_URL=http://ai-clip:8093" \
        -e "ENRICHMENT_URL=http://ai-enrichment:8094" \
        -e "FRONTEND_URL=http://frontend:80" \
        -e "FOSCAM_BASE_PATH=/cameras" \
        -e "DEBUG=${DEBUG:-false}" \
        -e "FAST_PATH_CONFIDENCE_THRESHOLD=${FAST_PATH_CONFIDENCE_THRESHOLD:-0.90}" \
        --restart unless-stopped \
        "ghcr.io/${GHCR_OWNER:-mikesvoboda}/${GHCR_REPO:-nemotron-v3-home-security-intelligence}/backend:${IMAGE_TAG:-latest}"
    print_success "Backend started with internal AI URLs"

    # Restart frontend
    print_step "Starting frontend..."
    run_cmd $CONTAINER_CMD run -d \
        --name "$frontend_name" \
        --network "$network_name" \
        --network-alias frontend \
        -p "${FRONTEND_PORT:-5173}:8080" \
        --restart unless-stopped \
        "ghcr.io/${GHCR_OWNER:-mikesvoboda}/${GHCR_REPO:-nemotron-v3-home-security-intelligence}/frontend:${IMAGE_TAG:-latest}"
    print_success "Frontend started"

    return 0
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

    # Check .env file exists, run setup.sh if missing
    print_step "Checking environment file..."
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        print_warn ".env file not found - running setup.sh to generate it"
        if [ -f "$PROJECT_ROOT/setup.sh" ]; then
            print_step "Running setup.sh..."
            if (cd "$PROJECT_ROOT" && ./setup.sh); then
                print_success "Generated .env via setup.sh"
            else
                print_fail "setup.sh failed - please run manually"
                return 2
            fi
        else
            print_fail "setup.sh not found - cannot generate .env"
            return 2
        fi
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

    # Stop containers from compose files and standalone containers
    print_step "Stopping containers..."

    local down_flags=""
    if [ "$KEEP_VOLUMES" != "true" ]; then
        down_flags="-v"
    fi

    if [ "$CONTAINER_CMD" = "podman" ]; then
        # Podman: Stop AI containers first (they're not managed by compose)
        print_step "Stopping AI containers..."
        stop_ai_containers_podman

        # Stop GHCR compose containers (this works with podman-compose)
        if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_GHCR" down $down_flags --remove-orphans 2>/dev/null; then
            print_success "Stopped GHCR compose containers"
        else
            print_info "No GHCR containers were running"
        fi

        # Note: We use hybrid mode (GHCR compose + direct podman for AI) for optimal performance
        # This approach provides better network routing and service initialization control

        # Final cleanup of any remaining pods and containers
        print_step "Cleaning up pods and orphaned containers..."
        run_cmd $CONTAINER_CMD pod rm -f -a 2>/dev/null || true
        run_cmd $CONTAINER_CMD container prune -f 2>/dev/null || true
        print_success "Cleanup complete"
    else
        # Docker: Use compose normally for both files
        if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_PROD" down $down_flags --remove-orphans 2>/dev/null; then
            print_success "Stopped prod compose containers"
        else
            print_info "No prod containers were running"
        fi

        if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_GHCR" down $down_flags --remove-orphans 2>/dev/null; then
            print_success "Stopped GHCR compose containers"
        else
            print_info "No GHCR containers were running"
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

# =============================================================================
# Build/Start Functions
# =============================================================================

build_images() {
    print_header "Building Images"

    cd "$PROJECT_ROOT"

    if [ "$DEPLOY_MODE" = "local" ]; then
        # Build all 9 services locally
        if [ "$CONTAINER_CMD" = "podman" ]; then
            # Podman: Build core services with compose, AI services directly
            print_step "Building core service images..."
            if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_GHCR" build 2>/dev/null; then
                print_success "Core images built"
            else
                print_info "Core services use pre-built images"
            fi
            # Build AI services with podman build (bypasses compose parser bug)
            if ! build_ai_images_podman; then
                return 1
            fi
        else
            # Docker: Use compose normally
            print_step "Building all service images (this may take a few minutes)..."
            if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_PROD" build; then
                print_success "All images built"
            else
                print_fail "Failed to build images"
                return 1
            fi
        fi
    elif [ "$DEPLOY_MODE" = "hybrid" ]; then
        # Build only AI services locally
        if [ "$CONTAINER_CMD" = "podman" ]; then
            # Podman: Use podman build directly (bypasses compose parser bug)
            if ! build_ai_images_podman; then
                return 1
            fi
        else
            # Docker: Use compose normally
            print_step "Building AI service images (this may take a few minutes)..."
            if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_PROD" build ai-detector ai-llm ai-florence ai-clip ai-enrichment; then
                print_success "AI images built"
            else
                print_fail "Failed to build AI images"
                return 1
            fi
        fi
    fi
    # GHCR mode doesn't build anything

    return 0
}

run_migrations() {
    print_header "Running Database Migrations"

    cd "$PROJECT_ROOT"

    # Wait for postgres to be ready
    print_step "Waiting for PostgreSQL to be healthy..."
    local max_attempts=30
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if $CONTAINER_CMD exec "${PROJECT_NAME}_postgres_1" pg_isready -U "${POSTGRES_USER:-security}" > /dev/null 2>&1; then
            print_success "PostgreSQL is ready"
            break
        fi
        ((attempt++))
        sleep 2
    done

    if [ $attempt -eq $max_attempts ]; then
        print_fail "PostgreSQL did not become ready in time"
        return 1
    fi

    # Check if uv is available
    if ! command -v uv &> /dev/null; then
        print_warn "uv not found - skipping migrations"
        print_warn "Run manually: cd backend && uv run alembic upgrade head"
        return 0
    fi

    # Run alembic migrations
    print_step "Running alembic upgrade head..."
    export PYTHONPATH="$PROJECT_ROOT"
    export DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER:-security}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB:-security}"

    if (cd "$PROJECT_ROOT/backend" && uv run alembic upgrade head 2>&1 | grep -E "(INFO|ERROR|Running upgrade)"); then
        print_success "Database migrations completed"
    else
        print_warn "Migration output unclear - check database state"
    fi

    return 0
}

prepare_directories() {
    print_header "Preparing Directories"

    cd "$PROJECT_ROOT"

    # Create directories that containers need to write to
    # This prevents permission issues with rootless Podman
    local -a dirs=(
        "backend/data"
        "backend/data/logs"
    )

    for dir in "${dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            print_step "Creating $dir..."
            run_cmd mkdir -p "$dir"
        fi
    done

    # Fix ownership if directories were created by container with different UID
    if [ "$CONTAINER_CMD" = "podman" ]; then
        print_step "Fixing directory ownership for rootless Podman..."
        for dir in "${dirs[@]}"; do
            if [ -d "$dir" ]; then
                # Use podman unshare to set ownership to container user (UID 1000)
                run_cmd podman unshare chown -R 1000:1000 "$dir" 2>/dev/null || true
            fi
        done
    fi

    print_success "Directories prepared"
    return 0
}

start_containers() {
    print_header "Starting Containers"

    cd "$PROJECT_ROOT"

    if [ "$DEPLOY_MODE" = "local" ]; then
        # Start all 9 services from locally built images using prod compose
        print_step "Starting all containers from prod compose (local build)..."
        if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_PROD" up -d; then
            print_success "All containers started from local build"
        else
            print_fail "Failed to start containers"
            return 1
        fi
    elif [ "$DEPLOY_MODE" = "ghcr" ]; then
        # Start only 4 services from GHCR compose (works with both docker and podman)
        print_step "Starting GHCR containers..."
        if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_GHCR" up -d; then
            print_success "GHCR containers started"
        else
            print_fail "Failed to start GHCR containers"
            return 1
        fi
    elif [ "$DEPLOY_MODE" = "hybrid" ]; then
        # Hybrid: Start core services from GHCR, then AI services
        print_step "Starting core containers from GHCR..."
        if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_GHCR" up -d; then
            print_success "Core containers started (postgres, redis, backend, frontend)"
        else
            print_fail "Failed to start core containers"
            return 1
        fi

        if [ "$CONTAINER_CMD" = "podman" ]; then
            # Podman: Start AI containers with podman run (bypasses compose parser bug)
            if ! start_ai_containers_podman; then
                return 1
            fi
            # Restart backend with internal network URLs (podman-compose uses host.docker.internal
            # but AI containers are on the same network, so we need internal container names)
            if ! restart_backend_with_internal_urls; then
                return 1
            fi
        else
            # Docker: Use compose normally
            print_step "Starting AI containers from prod compose..."
            if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE_PROD" up -d ai-detector ai-llm ai-florence ai-clip ai-enrichment; then
                print_success "AI containers started"
            else
                print_fail "Failed to start AI containers"
                return 1
            fi
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
                # Local is now the default, this flag is kept for backwards compatibility
                DEPLOY_MODE="local"
                shift
                ;;
            --hybrid)
                DEPLOY_MODE="hybrid"
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

    # Prepare directories for container volume mounts
    prepare_directories

    # Start containers
    if ! start_containers; then
        print_fail "Failed to start containers"
        exit 1
    fi

    # Run database migrations if volumes were destroyed (fresh database)
    if [ "$KEEP_VOLUMES" != "true" ]; then
        run_migrations
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
