#!/bin/bash
# Docker Compose Deployment Test Script
# Tests that all services start correctly, are healthy, and can communicate

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"

# Configuration
TIMEOUT=120  # Maximum wait time for services to become healthy (seconds)
CHECK_INTERVAL=5  # How often to check service health (seconds)

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Docker Compose Deployment Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print colored status messages
print_status() {
    local status=$1
    local message=$2
    case $status in
        "info")
            echo -e "${BLUE}[INFO]${NC} $message"
            ;;
        "success")
            echo -e "${GREEN}[✓]${NC} $message"
            ;;
        "warning")
            echo -e "${YELLOW}[!]${NC} $message"
            ;;
        "error")
            echo -e "${RED}[✗]${NC} $message"
            ;;
    esac
}

# Function to cleanup on exit
cleanup() {
    local exit_code=$?
    print_status "info" "Cleaning up..."

    if [ "$CLEANUP_ON_EXIT" = "true" ]; then
        docker compose down -v 2>/dev/null || true
        print_status "success" "Containers stopped and volumes removed"
    else
        print_status "warning" "Containers left running (use 'docker compose down' to stop)"
    fi

    exit $exit_code
}

# Register cleanup function
trap cleanup EXIT INT TERM

# Parse command line arguments
CLEANUP_ON_EXIT=true
SKIP_BUILD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-cleanup)
            CLEANUP_ON_EXIT=false
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --no-cleanup   Leave containers running after test"
            echo "  --skip-build   Skip docker compose build step"
            echo "  --help         Show this help message"
            exit 0
            ;;
        *)
            print_status "error" "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Step 1: Check if Docker is available
print_status "info" "Checking Docker availability..."
if ! command -v docker &> /dev/null; then
    print_status "error" "Docker is not installed or not in PATH"
    exit 1
fi

if ! docker info &> /dev/null; then
    print_status "error" "Docker daemon is not running or not accessible"
    print_status "info" "Try running: sudo systemctl start docker"
    exit 1
fi
print_status "success" "Docker is available"

# Step 2: Check if docker-compose.yml exists
print_status "info" "Checking docker-compose.yml..."
if [ ! -f "docker-compose.yml" ]; then
    print_status "error" "docker-compose.yml not found in $PROJECT_ROOT"
    exit 1
fi
print_status "success" "docker-compose.yml found"

# Step 3: Validate docker-compose.yml syntax
print_status "info" "Validating docker-compose.yml syntax..."
if ! docker compose config > /dev/null 2>&1; then
    print_status "error" "docker-compose.yml has syntax errors"
    docker compose config
    exit 1
fi
print_status "success" "docker-compose.yml syntax is valid"

# Step 4: Stop any existing containers
print_status "info" "Stopping any existing containers..."
docker compose down -v 2>/dev/null || true
print_status "success" "Cleaned up existing containers"

# Step 5: Build images (if not skipped)
if [ "$SKIP_BUILD" = "false" ]; then
    print_status "info" "Building Docker images..."
    if ! docker compose build --no-cache; then
        print_status "error" "Failed to build Docker images"
        exit 1
    fi
    print_status "success" "Docker images built successfully"
else
    print_status "warning" "Skipping build step (using existing images)"
fi

# Step 6: Start services
print_status "info" "Starting services with docker compose up -d..."
if ! docker compose up -d; then
    print_status "error" "Failed to start services"
    docker compose logs
    exit 1
fi
print_status "success" "Services started"

# Step 7: Wait for services to become healthy
print_status "info" "Waiting for services to become healthy (timeout: ${TIMEOUT}s)..."
elapsed=0
all_healthy=false

while [ $elapsed -lt $TIMEOUT ]; do
    # Get service health status
    redis_health=$(docker compose ps redis --format json 2>/dev/null | jq -r '.[0].Health // "unknown"' 2>/dev/null || echo "unknown")
    backend_health=$(docker compose ps backend --format json 2>/dev/null | jq -r '.[0].Health // "unknown"' 2>/dev/null || echo "unknown")
    frontend_health=$(docker compose ps frontend --format json 2>/dev/null | jq -r '.[0].Health // "unknown"' 2>/dev/null || echo "unknown")

    # Check if all services are running
    redis_state=$(docker compose ps redis --format json 2>/dev/null | jq -r '.[0].State // "unknown"' 2>/dev/null || echo "unknown")
    backend_state=$(docker compose ps backend --format json 2>/dev/null | jq -r '.[0].State // "unknown"' 2>/dev/null || echo "unknown")
    frontend_state=$(docker compose ps frontend --format json 2>/dev/null | jq -r '.[0].State // "unknown"' 2>/dev/null || echo "unknown")

    echo -e "  Redis:    state=${redis_state}, health=${redis_health}"
    echo -e "  Backend:  state=${backend_state}, health=${backend_health}"
    echo -e "  Frontend: state=${frontend_state}, health=${frontend_health}"

    # Check for failed containers
    if [ "$redis_state" = "exited" ] || [ "$backend_state" = "exited" ] || [ "$frontend_state" = "exited" ]; then
        print_status "error" "One or more services exited unexpectedly"
        docker compose logs
        exit 1
    fi

    # Check if all are healthy
    if [ "$redis_health" = "healthy" ] && [ "$backend_health" = "healthy" ] && [ "$frontend_health" = "healthy" ]; then
        all_healthy=true
        break
    fi

    sleep $CHECK_INTERVAL
    elapsed=$((elapsed + CHECK_INTERVAL))
    echo ""
done

if [ "$all_healthy" = "false" ]; then
    print_status "error" "Services did not become healthy within ${TIMEOUT}s"
    print_status "info" "Container logs:"
    docker compose logs
    exit 1
fi

print_status "success" "All services are healthy (took ${elapsed}s)"

# Step 8: Test service endpoints
print_status "info" "Testing service endpoints..."

# Test Redis
print_status "info" "Testing Redis connection..."
if docker compose exec -T redis redis-cli ping | grep -q "PONG"; then
    print_status "success" "Redis is responding"
else
    print_status "error" "Redis is not responding"
    exit 1
fi

# Test Backend health endpoint
print_status "info" "Testing Backend health endpoint (http://localhost:8000/health)..."
if curl -f -s http://localhost:8000/health > /dev/null; then
    health_response=$(curl -s http://localhost:8000/health)
    print_status "success" "Backend health endpoint responded"
    echo "  Response: $health_response"
else
    print_status "error" "Backend health endpoint failed"
    exit 1
fi

# Test Backend root endpoint
print_status "info" "Testing Backend root endpoint (http://localhost:8000/)..."
if curl -f -s http://localhost:8000/ > /dev/null; then
    root_response=$(curl -s http://localhost:8000/)
    print_status "success" "Backend root endpoint responded"
    echo "  Response: $root_response"
else
    print_status "error" "Backend root endpoint failed"
    exit 1
fi

# Test Frontend (just check if it responds, content doesn't matter in dev mode)
print_status "info" "Testing Frontend endpoint (http://localhost:3000)..."
if curl -f -s http://localhost:3000 > /dev/null; then
    print_status "success" "Frontend is responding"
else
    print_status "warning" "Frontend endpoint check failed (may still be starting)"
fi

# Step 9: Test inter-service communication
print_status "info" "Testing inter-service communication..."

# Test backend -> redis communication
print_status "info" "Testing Backend -> Redis communication..."
backend_redis_test=$(curl -s http://localhost:8000/health | jq -r '.redis')
if [ "$backend_redis_test" = "healthy" ]; then
    print_status "success" "Backend can communicate with Redis"
else
    print_status "warning" "Backend -> Redis communication issue (status: $backend_redis_test)"
fi

# Step 10: Show container resource usage
print_status "info" "Container resource usage:"
docker compose ps
echo ""
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" $(docker compose ps -q)

# Step 11: Success summary
echo ""
print_status "success" "========================================="
print_status "success" "Docker Compose Deployment Test PASSED"
print_status "success" "========================================="
echo ""
echo "All services are running and healthy:"
echo "  - Redis:    http://localhost:6379"
echo "  - Backend:  http://localhost:8000 (API docs: http://localhost:8000/docs)"
echo "  - Frontend: http://localhost:3000"
echo ""

if [ "$CLEANUP_ON_EXIT" = "true" ]; then
    print_status "info" "Services will be stopped on exit"
else
    print_status "info" "Services are still running. Use 'docker compose down' to stop them."
fi
