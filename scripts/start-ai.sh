#!/bin/bash
#
# AI Services Startup Script
# Nemotron v3 Home Security Intelligence
#
# This script manages both RT-DETRv2 detection server and Nemotron LLM server.
# Services run as independent native processes (not in Docker) for optimal GPU performance.
#
# Usage:
#   ./scripts/start-ai.sh [start|stop|restart|status|health]
#
# Requirements:
#   - NVIDIA GPU with CUDA support (RTX A5500 or similar)
#   - llama-server (from llama.cpp) in PATH
#   - Python environment with RT-DETRv2 dependencies
#   - Model files downloaded (run ai/download_models.sh first)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AI_DIR="$PROJECT_ROOT/ai"
RTDETR_DIR="$AI_DIR/rtdetr"
NEMOTRON_DIR="$AI_DIR/nemotron"

# Service configuration
DETECTOR_PORT="${RTDETR_PORT:-8090}"
LLM_PORT="${NEMOTRON_PORT:-8091}"
DETECTOR_PID_FILE="/tmp/rtdetr-detector.pid"
LLM_PID_FILE="/tmp/nemotron-llm.pid"
DETECTOR_LOG_FILE="/tmp/rtdetr-detector.log"
LLM_LOG_FILE="/tmp/nemotron-llm.log"

# Model files
RTDETR_MODEL="$RTDETR_DIR/rtdetrv2_r50vd.onnx"
NEMOTRON_MODEL="$NEMOTRON_DIR/nemotron-mini-4b-instruct-q4_k_m.gguf"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored message
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if a service is running
is_running() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Check service health endpoint
check_health() {
    local url=$1
    local timeout=${2:-5}
    if curl -sf --max-time "$timeout" "$url/health" > /dev/null 2>&1; then
        return 0
    fi
    return 1
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."

    local errors=0

    # Check NVIDIA GPU
    if ! command -v nvidia-smi &> /dev/null; then
        print_error "nvidia-smi not found. NVIDIA GPU required."
        errors=$((errors + 1))
    else
        print_success "NVIDIA GPU detected: $(nvidia-smi --query-gpu=name --format=csv,noheader)"
    fi

    # Check CUDA
    if ! nvidia-smi | grep -q "CUDA"; then
        print_warning "CUDA may not be available"
    else
        print_success "CUDA available"
    fi

    # Check llama-server
    if ! command -v llama-server &> /dev/null; then
        print_error "llama-server not found in PATH. Install llama.cpp first."
        print_error "See: https://github.com/ggerganov/llama.cpp"
        errors=$((errors + 1))
    else
        print_success "llama-server found: $(which llama-server)"
    fi

    # Check Python
    if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
        print_error "Python not found"
        errors=$((errors + 1))
    else
        local python_cmd=$(command -v python3 || command -v python)
        print_success "Python found: $python_cmd"
    fi

    # Check model files
    if [ ! -f "$NEMOTRON_MODEL" ]; then
        print_error "Nemotron model not found: $NEMOTRON_MODEL"
        print_error "Run: ./ai/download_models.sh"
        errors=$((errors + 1))
    else
        print_success "Nemotron model found ($(du -h "$NEMOTRON_MODEL" | cut -f1))"
    fi

    if [ ! -f "$RTDETR_MODEL" ]; then
        print_warning "RT-DETRv2 model not found: $RTDETR_MODEL"
        print_warning "Model will be downloaded automatically on first use"
    else
        print_success "RT-DETRv2 model found ($(du -h "$RTDETR_MODEL" | cut -f1))"
    fi

    if [ $errors -gt 0 ]; then
        print_error "Prerequisites check failed with $errors errors"
        return 1
    fi

    print_success "All prerequisites satisfied"
    return 0
}

# Start RT-DETRv2 detection server
start_detector() {
    print_status "Starting RT-DETRv2 detection server..."

    if is_running "$DETECTOR_PID_FILE"; then
        print_warning "RT-DETRv2 already running (PID: $(cat "$DETECTOR_PID_FILE"))"
        return 0
    fi

    # Start detector in background
    cd "$RTDETR_DIR"
    nohup python model.py > "$DETECTOR_LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$DETECTOR_PID_FILE"

    print_status "Waiting for RT-DETRv2 to start (PID: $pid)..."

    # Wait for service to be ready (max 60 seconds)
    local max_attempts=12
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if check_health "http://localhost:$DETECTOR_PORT" 2; then
            print_success "RT-DETRv2 detection server started successfully"
            print_success "  Port: $DETECTOR_PORT"
            print_success "  PID: $pid"
            print_success "  Log: $DETECTOR_LOG_FILE"
            print_success "  Expected VRAM: ~4GB"
            return 0
        fi
        sleep 5
        attempt=$((attempt + 1))
    done

    print_error "RT-DETRv2 failed to start within 60 seconds"
    print_error "Check logs: tail -f $DETECTOR_LOG_FILE"
    return 1
}

# Start Nemotron LLM server
start_llm() {
    print_status "Starting Nemotron LLM server..."

    if is_running "$LLM_PID_FILE"; then
        print_warning "Nemotron LLM already running (PID: $(cat "$LLM_PID_FILE"))"
        return 0
    fi

    # Start LLM server in background
    nohup llama-server \
        --model "$NEMOTRON_MODEL" \
        --port $LLM_PORT \
        --ctx-size 4096 \
        --n-gpu-layers 99 \
        --host 0.0.0.0 \
        --parallel 2 \
        --cont-batching \
        > "$LLM_LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$LLM_PID_FILE"

    print_status "Waiting for Nemotron LLM to start (PID: $pid)..."

    # Wait for service to be ready (max 60 seconds)
    local max_attempts=12
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if check_health "http://localhost:$LLM_PORT" 2; then
            print_success "Nemotron LLM server started successfully"
            print_success "  Port: $LLM_PORT"
            print_success "  PID: $pid"
            print_success "  Log: $LLM_LOG_FILE"
            print_success "  Expected VRAM: ~3GB"
            return 0
        fi
        sleep 5
        attempt=$((attempt + 1))
    done

    print_error "Nemotron LLM failed to start within 60 seconds"
    print_error "Check logs: tail -f $LLM_LOG_FILE"
    return 1
}

# Stop a service
stop_service() {
    local service_name=$1
    local pid_file=$2

    if ! is_running "$pid_file"; then
        print_warning "$service_name not running"
        return 0
    fi

    local pid=$(cat "$pid_file")
    print_status "Stopping $service_name (PID: $pid)..."

    kill "$pid" 2>/dev/null || true

    # Wait for graceful shutdown (max 10 seconds)
    local attempt=0
    while [ $attempt -lt 10 ]; do
        if ! ps -p "$pid" > /dev/null 2>&1; then
            rm -f "$pid_file"
            print_success "$service_name stopped"
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done

    # Force kill if still running
    print_warning "Force killing $service_name..."
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$pid_file"
    print_success "$service_name stopped (forced)"
}

# Show service status
show_status() {
    echo ""
    echo "=========================================="
    echo "AI Services Status"
    echo "=========================================="
    echo ""

    # RT-DETRv2 Detection Server
    echo "RT-DETRv2 Detection Server:"
    echo "  Port: $DETECTOR_PORT"
    if is_running "$DETECTOR_PID_FILE"; then
        local pid=$(cat "$DETECTOR_PID_FILE")
        echo -e "  Status: ${GREEN}RUNNING${NC} (PID: $pid)"
        if check_health "http://localhost:$DETECTOR_PORT"; then
            echo -e "  Health: ${GREEN}HEALTHY${NC}"
        else
            echo -e "  Health: ${RED}UNHEALTHY${NC}"
        fi
    else
        echo -e "  Status: ${RED}STOPPED${NC}"
    fi
    echo ""

    # Nemotron LLM Server
    echo "Nemotron LLM Server:"
    echo "  Port: $LLM_PORT"
    if is_running "$LLM_PID_FILE"; then
        local pid=$(cat "$LLM_PID_FILE")
        echo -e "  Status: ${GREEN}RUNNING${NC} (PID: $pid)"
        if check_health "http://localhost:$LLM_PORT"; then
            echo -e "  Health: ${GREEN}HEALTHY${NC}"
        else
            echo -e "  Health: ${RED}UNHEALTHY${NC}"
        fi
    else
        echo -e "  Status: ${RED}STOPPED${NC}"
    fi
    echo ""

    # GPU Status
    if command -v nvidia-smi &> /dev/null; then
        echo "GPU Status:"
        nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader | \
            awk -F', ' '{printf "  GPU: %s\n  VRAM: %s / %s\n  Utilization: %s\n", $1, $2, $3, $4}'
        echo ""
    fi

    echo "Log Files:"
    echo "  Detector: $DETECTOR_LOG_FILE"
    echo "  LLM: $LLM_LOG_FILE"
    echo ""
}

# Test service health
test_health() {
    echo ""
    echo "=========================================="
    echo "AI Services Health Check"
    echo "=========================================="
    echo ""

    local all_healthy=true

    # Test RT-DETRv2
    print_status "Testing RT-DETRv2 detection server..."
    if check_health "http://localhost:$DETECTOR_PORT"; then
        print_success "RT-DETRv2 is healthy"
        # Show detailed health info
        curl -s "http://localhost:$DETECTOR_PORT/health" | python3 -m json.tool 2>/dev/null || true
    else
        print_error "RT-DETRv2 is not responding"
        all_healthy=false
    fi
    echo ""

    # Test Nemotron LLM
    print_status "Testing Nemotron LLM server..."
    if check_health "http://localhost:$LLM_PORT"; then
        print_success "Nemotron LLM is healthy"
        # Show server info
        curl -s "http://localhost:$LLM_PORT/health" 2>/dev/null || true
    else
        print_error "Nemotron LLM is not responding"
        all_healthy=false
    fi
    echo ""

    if $all_healthy; then
        print_success "All AI services are healthy"
        return 0
    else
        print_error "One or more AI services are unhealthy"
        return 1
    fi
}

# Main command dispatcher
main() {
    local command=${1:-start}

    case "$command" in
        start)
            echo ""
            echo "=========================================="
            echo "Starting AI Services"
            echo "=========================================="
            echo ""

            if ! check_prerequisites; then
                exit 1
            fi

            echo ""
            start_detector || exit 1
            echo ""
            start_llm || exit 1
            echo ""
            show_status
            ;;

        stop)
            echo ""
            echo "=========================================="
            echo "Stopping AI Services"
            echo "=========================================="
            echo ""

            stop_service "RT-DETRv2" "$DETECTOR_PID_FILE"
            stop_service "Nemotron LLM" "$LLM_PID_FILE"
            echo ""
            print_success "All AI services stopped"
            ;;

        restart)
            echo ""
            echo "=========================================="
            echo "Restarting AI Services"
            echo "=========================================="
            echo ""

            "$0" stop
            sleep 2
            "$0" start
            ;;

        status)
            show_status
            ;;

        health)
            test_health
            ;;

        *)
            echo "Usage: $0 {start|stop|restart|status|health}"
            echo ""
            echo "Commands:"
            echo "  start   - Start both AI services"
            echo "  stop    - Stop both AI services"
            echo "  restart - Restart both AI services"
            echo "  status  - Show service status"
            echo "  health  - Test service health endpoints"
            echo ""
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
