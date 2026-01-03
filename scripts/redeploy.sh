#!/bin/bash
# =============================================================================
# Redeploy Script for Home Security Intelligence
# =============================================================================
# Pulls latest backend/frontend containers from GitHub Container Registry
# and redeploys them with Podman.
#
# Usage:
#   ./scripts/redeploy.sh [OPTIONS]
#
# Options:
#   --help, -h       Show this help message
#   --dry-run        Show what would be done without executing
#   --skip-pull      Skip pulling images (use existing local images)
#   --tag TAG        Use specific image tag (default: latest)
#
# Prerequisites:
#   - Podman or Docker installed
#   - .env file configured (run ./setup.sh if missing)
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
SKIP_PULL="${SKIP_PULL:-false}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.ghcr.yml}"

# GHCR settings (from docker-compose.ghcr.yml defaults)
GHCR_OWNER="${GHCR_OWNER:-mikesvoboda}"
GHCR_REPO="${GHCR_REPO:-nemotron-v3-home-security-intelligence}"

# Load .env file if present (for POSTGRES_PASSWORD and other vars)
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Ensure POSTGRES_PASSWORD is set (required by docker-compose.ghcr.yml)
if [ -z "$POSTGRES_PASSWORD" ]; then
    # Extract from DATABASE_URL if available
    if [ -n "$DATABASE_URL" ]; then
        POSTGRES_PASSWORD=$(echo "$DATABASE_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
    fi
    # Still not set? Use default for development
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
NC='\033[0m' # No Color
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
    --skip-pull      Skip pulling images (use existing local images)
    --tag TAG        Use specific image tag (default: latest)

DESCRIPTION:
    This script automates redeployment of the backend and frontend
    containers from GitHub Container Registry (GHCR).

    Steps performed:
    1. Stop existing containers
    2. Pull latest images from GHCR (unless --skip-pull)
    3. Start containers with new images
    4. Verify deployment health

EXAMPLES:
    # Standard redeploy with latest images
    ./scripts/redeploy.sh

    # Dry run to see what would happen
    ./scripts/redeploy.sh --dry-run

    # Deploy specific version
    ./scripts/redeploy.sh --tag abc1234

    # Restart without pulling new images
    ./scripts/redeploy.sh --skip-pull

ENVIRONMENT VARIABLES:
    IMAGE_TAG        Image tag to deploy (default: latest)
    GHCR_OWNER       GitHub owner/org (default: mikesvoboda)
    GHCR_REPO        Repository name (default: home-security-intelligence)
    COMPOSE_FILE     Compose file to use (default: docker-compose.ghcr.yml)

EOF
}

# =============================================================================
# Main Functions
# =============================================================================

check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check compose file exists
    print_step "Checking compose file..."
    if [ ! -f "$PROJECT_ROOT/$COMPOSE_FILE" ]; then
        print_fail "Compose file not found: $COMPOSE_FILE"
        return 2
    fi
    print_success "Found $COMPOSE_FILE"

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

    return 0
}

stop_containers() {
    print_header "Stopping Existing Containers"

    cd "$PROJECT_ROOT"

    print_step "Stopping containers..."
    if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE" down; then
        print_success "Containers stopped"
    else
        print_warn "Some containers may not have been running"
    fi
}

pull_images() {
    print_header "Pulling Latest Images from GHCR"

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

start_containers() {
    print_header "Starting Containers"

    cd "$PROJECT_ROOT"

    print_step "Starting containers..."
    if run_cmd $COMPOSE_CMD -f "$COMPOSE_FILE" up -d; then
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

    print_step "Waiting for services to be ready..."
    sleep 5

    # Check backend health
    print_step "Checking backend health..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s --connect-timeout 2 "http://localhost:8000/api/system/health/ready" | grep -q "ready"; then
            print_success "Backend is healthy"
            break
        fi

        if [ $attempt -eq $max_attempts ]; then
            print_warn "Backend not ready after ${max_attempts} attempts"
            echo "  Check logs: $COMPOSE_CMD -f $COMPOSE_FILE logs backend"
        fi

        sleep 2
        ((attempt++))
    done

    # Check frontend
    print_step "Checking frontend..."
    if curl -s --connect-timeout 5 "http://localhost:8080" > /dev/null 2>&1; then
        print_success "Frontend is responding"
    else
        print_warn "Frontend not responding on port 8080"
    fi

    # Show running containers
    print_step "Running containers:"
    $COMPOSE_CMD -f "$COMPOSE_FILE" ps

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
            --skip-pull)
                SKIP_PULL="true"
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

    echo ""
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo -e "${BLUE}${BOLD}  Home Security Intelligence Redeploy      ${NC}"
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo ""
    echo -e "Runtime:    ${CYAN}$COMPOSE_CMD${NC}"
    echo -e "Image Tag:  ${CYAN}$IMAGE_TAG${NC}"
    echo -e "Compose:    ${CYAN}$COMPOSE_FILE${NC}"
    echo -e "Dry Run:    ${CYAN}$DRY_RUN${NC}"
    echo -e "Skip Pull:  ${CYAN}$SKIP_PULL${NC}"
    echo -e "Started:    ${CYAN}$(date '+%Y-%m-%d %H:%M:%S')${NC}"

    # Run prerequisite checks
    if ! check_prerequisites; then
        exit 2
    fi

    # Stop existing containers
    stop_containers

    # Pull latest images (unless skipped)
    if [ "$SKIP_PULL" = "false" ]; then
        if ! pull_images; then
            print_fail "Failed to pull images"
            exit 1
        fi
    else
        print_info "Skipping image pull (--skip-pull specified)"
    fi

    # Start containers
    if ! start_containers; then
        print_fail "Failed to start containers"
        exit 1
    fi

    # Verify deployment
    verify_deployment

    # Summary
    print_header "Redeploy Complete"
    echo ""
    echo -e "${GREEN}${BOLD}  REDEPLOY SUCCESSFUL  ${NC}"
    echo ""
    echo "Services:"
    echo "  - Backend:  http://localhost:8000"
    echo "  - Frontend: http://localhost:8080"
    echo ""
    echo "Useful commands:"
    echo "  View logs:    $COMPOSE_CMD -f $COMPOSE_FILE logs -f"
    echo "  Stop:         $COMPOSE_CMD -f $COMPOSE_FILE down"
    echo "  Restart:      $COMPOSE_CMD -f $COMPOSE_FILE restart"
    echo ""

    exit 0
}

# Run main
main "$@"
