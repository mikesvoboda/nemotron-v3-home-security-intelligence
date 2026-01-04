#!/usr/bin/env bash
# Development server management script
# Usage: ./scripts/dev.sh [start|stop|status|restart]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PID_DIR="$PROJECT_ROOT/.pids"
REDIS_CONTAINER="home-security-redis"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

mkdir -p "$PID_DIR"

start_redis() {
    # Check if port 6379 is already in use (system Redis or existing container)
    if ss -tlnp 2>/dev/null | grep -q ':6379\s'; then
        echo -e "${YELLOW}Redis already running on port 6379${NC}"
        return 0
    fi

    # Determine docker command (use sudo if needed)
    DOCKER_CMD="docker"
    if ! docker info &>/dev/null; then
        if sudo docker info &>/dev/null; then
            DOCKER_CMD="sudo docker"
        fi
    fi

    # Try Docker
    if $DOCKER_CMD info &>/dev/null; then
        # Check if container exists but is stopped
        if $DOCKER_CMD ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${REDIS_CONTAINER}$"; then
            echo -e "${GREEN}Starting existing Redis container...${NC}"
            $DOCKER_CMD start "$REDIS_CONTAINER" > /dev/null
        else
            echo -e "${GREEN}Creating and starting Redis container...${NC}"
            $DOCKER_CMD run -d --name "$REDIS_CONTAINER" -p 6379:6379 redis:alpine > /dev/null
        fi

        # Wait for Redis to be ready
        for i in {1..10}; do
            if $DOCKER_CMD exec "$REDIS_CONTAINER" redis-cli ping 2>/dev/null | grep -q "PONG"; then
                echo -e "${GREEN}Redis started (container: ${REDIS_CONTAINER}) - localhost:6379${NC}"
                return 0
            fi
            sleep 0.5
        done
        echo -e "${RED}Redis container failed to start${NC}"
        return 1
    fi

    echo -e "${RED}Could not start Redis. Docker not available.${NC}"
    echo -e "  ${YELLOW}Option 1:${NC} sudo systemctl start redis"
    echo -e "  ${YELLOW}Option 2:${NC} Add user to docker group: sudo usermod -aG docker \$USER"
    return 1
}

stop_redis() {
    # Determine docker command (use sudo if needed)
    DOCKER_CMD="docker"
    if ! docker info &>/dev/null; then
        if sudo docker info &>/dev/null; then
            DOCKER_CMD="sudo docker"
        fi
    fi

    if $DOCKER_CMD ps --format '{{.Names}}' 2>/dev/null | grep -q "^${REDIS_CONTAINER}$"; then
        echo -e "${RED}Stopping Redis container...${NC}"
        $DOCKER_CMD stop "$REDIS_CONTAINER" > /dev/null
        echo -e "${GREEN}Redis stopped${NC}"
    else
        echo -e "${YELLOW}Redis container not running${NC}"
    fi
}

start_backend() {
    if [ -f "$PID_DIR/backend.pid" ] && kill -0 "$(cat "$PID_DIR/backend.pid")" 2>/dev/null; then
        echo -e "${YELLOW}Backend already running (PID: $(cat "$PID_DIR/backend.pid"))${NC}"
        return 0
    fi

    echo -e "${GREEN}Starting backend server...${NC}"
    cd "$PROJECT_ROOT"
    source .venv/bin/activate
    nohup uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 > "$PROJECT_ROOT/logs/backend.log" 2>&1 &
    echo $! > "$PID_DIR/backend.pid"
    echo -e "${GREEN}Backend started (PID: $!) - http://localhost:8000${NC}"
}

start_frontend() {
    if [ -f "$PID_DIR/frontend.pid" ] && kill -0 "$(cat "$PID_DIR/frontend.pid")" 2>/dev/null; then
        echo -e "${YELLOW}Frontend already running (PID: $(cat "$PID_DIR/frontend.pid"))${NC}"
        return 0
    fi

    echo -e "${GREEN}Starting frontend server...${NC}"
    cd "$PROJECT_ROOT/frontend"
    nohup npm run dev > "$PROJECT_ROOT/logs/frontend.log" 2>&1 &
    echo $! > "$PID_DIR/frontend.pid"
    echo -e "${GREEN}Frontend started (PID: $!) - http://localhost:5173${NC}"
}

stop_backend() {
    if [ -f "$PID_DIR/backend.pid" ]; then
        PID=$(cat "$PID_DIR/backend.pid")
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "${RED}Stopping backend (PID: $PID)...${NC}"
            kill "$PID" 2>/dev/null || true
            # Also kill any child uvicorn processes
            pkill -f "uvicorn backend.main:app" 2>/dev/null || true
        fi
        rm -f "$PID_DIR/backend.pid"
        echo -e "${GREEN}Backend stopped${NC}"
    else
        echo -e "${YELLOW}Backend not running${NC}"
        # Clean up any orphaned processes
        pkill -f "uvicorn backend.main:app" 2>/dev/null || true
    fi
}

stop_frontend() {
    if [ -f "$PID_DIR/frontend.pid" ]; then
        PID=$(cat "$PID_DIR/frontend.pid")
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "${RED}Stopping frontend (PID: $PID)...${NC}"
            kill "$PID" 2>/dev/null || true
            # Also kill any child vite processes
            pkill -f "vite" 2>/dev/null || true
        fi
        rm -f "$PID_DIR/frontend.pid"
        echo -e "${GREEN}Frontend stopped${NC}"
    else
        echo -e "${YELLOW}Frontend not running${NC}"
        # Clean up any orphaned processes
        pkill -f "vite" 2>/dev/null || true
    fi
}

status() {
    echo -e "${GREEN}=== Development Server Status ===${NC}"
    echo ""

    # Determine docker command (use sudo if needed)
    DOCKER_CMD="docker"
    if ! docker info &>/dev/null 2>&1; then
        if sudo docker info &>/dev/null 2>&1; then
            DOCKER_CMD="sudo docker"
        fi
    fi

    # Redis status
    if $DOCKER_CMD ps --format '{{.Names}}' 2>/dev/null | grep -q "^${REDIS_CONTAINER}$"; then
        echo -e "Redis:    ${GREEN}RUNNING${NC} (container: ${REDIS_CONTAINER}) - localhost:6379"
    elif ss -tlnp 2>/dev/null | grep -q ':6379\s'; then
        echo -e "Redis:    ${GREEN}RUNNING${NC} (port 6379) - localhost:6379"
    else
        echo -e "Redis:    ${RED}STOPPED${NC}"
    fi

    # Backend status
    if [ -f "$PID_DIR/backend.pid" ] && kill -0 "$(cat "$PID_DIR/backend.pid")" 2>/dev/null; then
        echo -e "Backend:  ${GREEN}RUNNING${NC} (PID: $(cat "$PID_DIR/backend.pid")) - http://localhost:8000"
    else
        echo -e "Backend:  ${RED}STOPPED${NC}"
    fi

    # Frontend status
    if [ -f "$PID_DIR/frontend.pid" ] && kill -0 "$(cat "$PID_DIR/frontend.pid")" 2>/dev/null; then
        echo -e "Frontend: ${GREEN}RUNNING${NC} (PID: $(cat "$PID_DIR/frontend.pid")) - http://localhost:5173"
    else
        echo -e "Frontend: ${RED}STOPPED${NC}"
    fi
    echo ""
}

logs() {
    echo -e "${GREEN}=== Recent Logs ===${NC}"
    echo ""
    echo -e "${YELLOW}--- Backend (last 20 lines) ---${NC}"
    tail -20 "$PROJECT_ROOT/logs/backend.log" 2>/dev/null || echo "No backend logs"
    echo ""
    echo -e "${YELLOW}--- Frontend (last 20 lines) ---${NC}"
    tail -20 "$PROJECT_ROOT/logs/frontend.log" 2>/dev/null || echo "No frontend logs"
}

# Create logs directory
mkdir -p "$PROJECT_ROOT/logs"

case "${1:-}" in
    start)
        start_redis
        start_backend
        sleep 2
        start_frontend
        echo ""
        status
        ;;
    stop)
        stop_frontend
        stop_backend
        stop_redis
        ;;
    restart)
        stop_frontend
        stop_backend
        stop_redis
        sleep 1
        start_redis
        start_backend
        sleep 2
        start_frontend
        echo ""
        status
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    redis)
        case "${2:-start}" in
            start) start_redis ;;
            stop) stop_redis ;;
            *) echo "Usage: $0 redis [start|stop]" ;;
        esac
        ;;
    backend)
        case "${2:-start}" in
            start) start_backend ;;
            stop) stop_backend ;;
            *) echo "Usage: $0 backend [start|stop]" ;;
        esac
        ;;
    frontend)
        case "${2:-start}" in
            start) start_frontend ;;
            stop) stop_frontend ;;
            *) echo "Usage: $0 frontend [start|stop]" ;;
        esac
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|redis|backend|frontend}"
        echo ""
        echo "Commands:"
        echo "  start    - Start Redis, backend, and frontend"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo "  status   - Show service status"
        echo "  logs     - Show recent log output"
        echo "  redis    - Manage Redis only (start|stop)"
        echo "  backend  - Manage backend only (start|stop)"
        echo "  frontend - Manage frontend only (start|stop)"
        exit 1
        ;;
esac
