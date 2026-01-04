#!/usr/bin/env bash
#
# Full Stack Restart Script
# Nemotron v3 Home Security Intelligence
#
# Starts all containerized services: core, AI, and monitoring.
#
# Usage:
#   ./scripts/restart-all.sh [start|stop|restart|status]
#
# Services:
#   Core:       postgres, redis, backend, frontend
#   AI:         ai-detector, ai-llm, ai-florence, ai-clip, ai-enrichment
#   Monitoring: prometheus, grafana, redis-exporter, json-exporter
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.prod.yml"
ENV_FILE="$PROJECT_ROOT/.env"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[OK]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Service groups
CORE_SERVICES="postgres redis backend frontend"
AI_SERVICES="ai-detector ai-llm ai-florence ai-clip ai-enrichment"
MONITORING_SERVICES="prometheus grafana redis-exporter json-exporter"
ALL_SERVICES="$CORE_SERVICES $AI_SERVICES $MONITORING_SERVICES"

# Load environment variables
load_env() {
    if [ -f "$ENV_FILE" ]; then
        set -a
        source "$ENV_FILE"
        set +a
    fi

    # Set defaults for required variables
    export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-security_dev_password}"
    export POSTGRES_USER="${POSTGRES_USER:-security}"
    export POSTGRES_DB="${POSTGRES_DB:-security}"
    export AI_MODELS_PATH="${AI_MODELS_PATH:-/export/ai_models}"
    export HF_CACHE="${HF_CACHE:-$HOME/.cache/huggingface}"
    export CAMERA_PATH="${CAMERA_PATH:-/export/foscam}"
}

# Check if podman-compose is available
check_compose() {
    if command -v podman-compose &> /dev/null; then
        COMPOSE_CMD="podman-compose"
    elif command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
    elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        print_error "No compose command found. Install podman-compose or docker-compose."
        exit 1
    fi
    print_status "Using: $COMPOSE_CMD"
}

# Start services
start_services() {
    local services="$1"
    local group_name="$2"
    local profile="${3:-}"

    print_status "Starting $group_name services..."

    # Run compose up with explicit service names and optional profile
    if [ -n "$profile" ]; then
        $COMPOSE_CMD -f "$COMPOSE_FILE" --profile "$profile" up -d $services 2>&1 | grep -v "^Error:" || true
    else
        $COMPOSE_CMD -f "$COMPOSE_FILE" up -d $services 2>&1 | grep -v "^Error:" || true
    fi

    print_success "$group_name services started"
}

# Stop services
stop_services() {
    local services="$1"
    local group_name="$2"
    local profile="${3:-}"

    print_status "Stopping $group_name services..."
    if [ -n "$profile" ]; then
        $COMPOSE_CMD -f "$COMPOSE_FILE" --profile "$profile" stop $services 2>&1 || true
    else
        $COMPOSE_CMD -f "$COMPOSE_FILE" stop $services 2>&1 || true
    fi
    print_success "$group_name services stopped"
}

# Show status
show_status() {
    echo ""
    echo "=========================================="
    echo "Container Status"
    echo "=========================================="
    echo ""

    podman ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "nemotron|NAME" || \
    docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "nemotron|NAME"

    echo ""

    # Check GPU if available
    if command -v nvidia-smi &> /dev/null; then
        echo "GPU Status:"
        nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader | \
            awk -F', ' '{printf "  GPU: %s | VRAM: %s / %s | Util: %s\n", $1, $2, $3, $4}'
        echo ""
    fi
}

# Health check
health_check() {
    echo ""
    echo "=========================================="
    echo "Service Health Check"
    echo "=========================================="
    echo ""

    local services=(
        "Backend:http://localhost:8000/api/system/health/ready"
        "RT-DETRv2:http://localhost:8090/health"
        "Nemotron:http://localhost:8091/health"
        "Florence:http://localhost:8092/health"
        "CLIP:http://localhost:8093/health"
        "Enrichment:http://localhost:8094/health"
        "Prometheus:http://localhost:9090/-/healthy"
        "Grafana:http://localhost:3002/api/health"
    )

    for svc in "${services[@]}"; do
        local name="${svc%%:*}"
        local url="${svc#*:}"

        if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
            echo -e "  ${GREEN}✓${NC} $name"
        else
            echo -e "  ${RED}✗${NC} $name"
        fi
    done
    echo ""
}

# Main
main() {
    local command=${1:-start}

    cd "$PROJECT_ROOT"
    load_env
    check_compose

    case "$command" in
        start)
            echo ""
            echo "=========================================="
            echo "Starting All Services"
            echo "=========================================="
            echo ""

            start_services "$CORE_SERVICES" "Core"
            echo ""
            start_services "$AI_SERVICES" "AI"
            echo ""
            start_services "$MONITORING_SERVICES" "Monitoring" "monitoring"
            echo ""

            print_status "Waiting for services to initialize..."
            sleep 10
            show_status
            health_check
            ;;

        stop)
            echo ""
            echo "=========================================="
            echo "Stopping All Services"
            echo "=========================================="
            echo ""

            stop_services "$MONITORING_SERVICES" "Monitoring" "monitoring"
            stop_services "$AI_SERVICES" "AI"
            stop_services "$CORE_SERVICES" "Core"

            print_success "All services stopped"
            ;;

        restart)
            "$0" stop
            sleep 3
            "$0" start
            ;;

        status)
            show_status
            health_check
            ;;

        core)
            start_services "$CORE_SERVICES" "Core"
            ;;

        ai)
            start_services "$AI_SERVICES" "AI"
            ;;

        monitoring)
            start_services "$MONITORING_SERVICES" "Monitoring" "monitoring"
            ;;

        *)
            echo "Usage: $0 {start|stop|restart|status|core|ai|monitoring}"
            echo ""
            echo "Commands:"
            echo "  start      - Start all services (core, AI, monitoring)"
            echo "  stop       - Stop all services"
            echo "  restart    - Restart all services"
            echo "  status     - Show container status and health"
            echo "  core       - Start only core services (postgres, redis, backend, frontend)"
            echo "  ai         - Start only AI services"
            echo "  monitoring - Start only monitoring services"
            echo ""
            echo "Services:"
            echo "  Core:       $CORE_SERVICES"
            echo "  AI:         $AI_SERVICES"
            echo "  Monitoring: $MONITORING_SERVICES"
            echo ""
            exit 1
            ;;
    esac
}

main "$@"
