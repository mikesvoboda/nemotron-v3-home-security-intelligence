#!/usr/bin/env bash
# ABOUTME: Wrapper script to generate all promotional videos using Veo 3.1
# ABOUTME: Requires NVIDIA_API_KEY or NVAPIKEY environment variable

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}$1${NC}"
}

print_error() {
    echo -e "${RED}$1${NC}"
}

# Check for API key
check_api_key() {
    if [[ -z "${NVIDIA_API_KEY:-}" ]] && [[ -z "${NVAPIKEY:-}" ]]; then
        print_error "Error: NVIDIA_API_KEY or NVAPIKEY environment variable not set"
        echo ""
        echo "Please set your NVIDIA API key:"
        echo "  export NVIDIA_API_KEY='your-api-key-here'"  # pragma: allowlist secret
        echo ""
        echo "You can get an API key from: https://build.nvidia.com"
        exit 1
    fi
    print_success "API key found"
}

# Check for uv
check_uv() {
    if ! command -v uv &> /dev/null; then
        print_error "Error: 'uv' is not installed"
        echo ""
        echo "Please install uv:"
        echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    print_success "uv found: $(uv --version)"
}

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Generate promotional videos for Home Security Intelligence using Veo 3.1.

Options:
    -h, --help          Show this help message
    -l, --list          List available video prompts
    -t, --test          Test API connection
    -a, --all           Generate all 8 videos
    -v, --video ID      Generate a specific video (e.g., 1a, 2b)
    -d, --duration SEC  Target duration in seconds (default: 120)
    --no-intermediate   Don't save intermediate video files

Available Videos:
    1a  Day-to-Night Security Timelapse
    1b  Night Arrival Sequence
    4a  Dawn Property Flyover Tour
    4b  Neighborhood Context to Smart Home
    2a  AI Processing Data Visualization Journey
    2b  System Boot Sequence
    3a  Real-Time Detection Event with AI Overlay
    3b  Multi-Camera Security Montage with AI Analysis

Examples:
    # Test API connection first
    $(basename "$0") --test

    # List all available videos
    $(basename "$0") --list

    # Generate a specific video
    $(basename "$0") --video 1a

    # Generate all videos
    $(basename "$0") --all

    # Generate with custom duration (60 seconds)
    $(basename "$0") --video 2a --duration 60

Output:
    Videos are saved to: ~/Documents/Videos/HomeSecurityIntelligence/

Environment Variables:
    NVIDIA_API_KEY or NVAPIKEY - Required for API authentication
EOF
}

# Main execution
main() {
    print_header "Home Security Intelligence Video Generator"

    # Parse arguments
    if [[ $# -eq 0 ]]; then
        usage
        exit 0
    fi

    # Check dependencies
    echo "Checking dependencies..."
    check_api_key
    check_uv
    echo ""

    # Build command arguments
    local args=()
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -l|--list)
                args+=("--list")
                shift
                ;;
            -t|--test)
                args+=("--test")
                shift
                ;;
            -a|--all)
                args+=("--all")
                shift
                ;;
            -v|--video)
                args+=("--video" "$2")
                shift 2
                ;;
            -d|--duration)
                args+=("--duration" "$2")
                shift 2
                ;;
            --no-intermediate)
                args+=("--no-intermediate")
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done

    # Run the Python script
    print_header "Starting Video Generation"
    cd "$PROJECT_ROOT"
    uv run "$SCRIPT_DIR/generate_videos.py" "${args[@]}"
}

main "$@"
