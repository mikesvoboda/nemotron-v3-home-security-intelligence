#!/usr/bin/env bash
# setup-container-api.sh - Configure container API for orchestrator self-healing
#
# This script sets up the Docker/Podman API service so the backend container
# orchestrator can monitor and restart unhealthy AI containers.
#
# Supported platforms:
#   - Linux (rootless Podman): Creates systemd user service
#   - Linux (Docker): Uses existing Docker socket
#   - macOS (Docker Desktop): Uses existing Docker socket
#   - macOS (Podman): Creates launchd user agent
#   - Windows: Use Docker Desktop (auto-configured) or WSL2 with this script
#
# Usage: ./scripts/setup-container-api.sh [--check|--disable]

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Detect container runtime
detect_runtime() {
    if command -v podman &>/dev/null; then
        # Check if it's rootless
        if podman info --format '{{.Host.Security.Rootless}}' 2>/dev/null | grep -q "true"; then
            echo "podman-rootless"
        else
            echo "podman-root"
        fi
    elif command -v docker &>/dev/null; then
        echo "docker"
    else
        echo "none"
    fi
}

# Check if API is accessible
check_api() {
    local endpoint="${1:-}"

    if [[ -z "$endpoint" ]]; then
        # Try common endpoints
        if curl -s --unix-socket /var/run/docker.sock http://localhost/version &>/dev/null; then
            echo "unix:///var/run/docker.sock"
            return 0
        elif curl -s http://localhost:2375/version &>/dev/null; then
            echo "tcp://localhost:2375"
            return 0
        elif [[ -S "/run/user/$(id -u)/podman/podman.sock" ]]; then
            if curl -s --unix-socket "/run/user/$(id -u)/podman/podman.sock" http://localhost/version &>/dev/null; then
                echo "unix:///run/user/$(id -u)/podman/podman.sock"
                return 0
            fi
        fi
        return 1
    else
        if [[ "$endpoint" == unix://* ]]; then
            local socket="${endpoint#unix://}"
            curl -s --unix-socket "$socket" http://localhost/version &>/dev/null
        else
            curl -s "${endpoint#tcp://}/version" &>/dev/null
        fi
    fi
}

# Setup for Linux with rootless Podman
setup_linux_podman_rootless() {
    local service_dir="$HOME/.config/systemd/user"
    local service_file="$service_dir/podman-api-tcp.service"

    log_info "Setting up Podman API service for rootless Podman..."

    mkdir -p "$service_dir"

    cat > "$service_file" << 'EOF'
[Unit]
Description=Podman API Service (TCP)
Documentation=man:podman-system-service(1)
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/podman system service --time=0 tcp://0.0.0.0:2375
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable podman-api-tcp.service
    systemctl --user start podman-api-tcp.service

    # Enable lingering for boot persistence
    if command -v loginctl &>/dev/null; then
        loginctl enable-linger "$(whoami)" 2>/dev/null || true
    fi

    log_info "Podman API service started on tcp://localhost:2375"
    log_info "Service will persist across reboots"

    echo "ORCHESTRATOR_DOCKER_HOST=tcp://host.containers.internal:2375"
}

# Setup for macOS with Podman
setup_macos_podman() {
    local plist_dir="$HOME/Library/LaunchAgents"
    local plist_file="$plist_dir/com.podman.api.plist"

    log_info "Setting up Podman API service for macOS..."

    mkdir -p "$plist_dir"

    cat > "$plist_file" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.podman.api</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which podman)</string>
        <string>system</string>
        <string>service</string>
        <string>--time=0</string>
        <string>tcp://0.0.0.0:2375</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/podman-api.err</string>
    <key>StandardOutPath</key>
    <string>/tmp/podman-api.out</string>
</dict>
</plist>
EOF

    launchctl unload "$plist_file" 2>/dev/null || true
    launchctl load "$plist_file"

    log_info "Podman API service started on tcp://localhost:2375"

    echo "ORCHESTRATOR_DOCKER_HOST=tcp://host.containers.internal:2375"
}

# Setup for Docker (socket already available)
setup_docker() {
    local socket="/var/run/docker.sock"

    if [[ -S "$socket" ]]; then
        log_info "Docker socket found at $socket"
        log_info "No additional setup required"
        echo "ORCHESTRATOR_DOCKER_HOST=unix://$socket"
    else
        log_error "Docker socket not found at $socket"
        log_info "If using Docker Desktop, ensure it's running"
        return 1
    fi
}

# Disable the service
disable_service() {
    local os_type="$(uname -s)"

    case "$os_type" in
        Linux)
            if systemctl --user is-active podman-api-tcp.service &>/dev/null; then
                systemctl --user stop podman-api-tcp.service
                systemctl --user disable podman-api-tcp.service
                log_info "Podman API service disabled"
            else
                log_info "Service not running"
            fi
            ;;
        Darwin)
            local plist_file="$HOME/Library/LaunchAgents/com.podman.api.plist"
            if [[ -f "$plist_file" ]]; then
                launchctl unload "$plist_file" 2>/dev/null || true
                rm -f "$plist_file"
                log_info "Podman API service disabled"
            else
                log_info "Service not configured"
            fi
            ;;
        *)
            log_error "Unsupported OS: $os_type"
            return 1
            ;;
    esac
}

# Main
main() {
    local action="${1:-setup}"

    case "$action" in
        --check)
            if endpoint=$(check_api); then
                log_info "Container API accessible at: $endpoint"
                exit 0
            else
                log_error "Container API not accessible"
                exit 1
            fi
            ;;
        --disable)
            disable_service
            exit 0
            ;;
        --help|-h)
            echo "Usage: $0 [--check|--disable|--help]"
            echo ""
            echo "Options:"
            echo "  --check    Check if container API is accessible"
            echo "  --disable  Disable the API service"
            echo "  --help     Show this help message"
            echo ""
            echo "Without options, sets up the container API service."
            exit 0
            ;;
    esac

    local os_type="$(uname -s)"
    local runtime=$(detect_runtime)

    log_info "Detected OS: $os_type"
    log_info "Detected runtime: $runtime"

    case "$os_type" in
        Linux)
            case "$runtime" in
                podman-rootless)
                    setup_linux_podman_rootless
                    ;;
                podman-root|docker)
                    setup_docker
                    ;;
                none)
                    log_error "No container runtime found. Install Docker or Podman first."
                    exit 1
                    ;;
            esac
            ;;
        Darwin)
            case "$runtime" in
                podman*)
                    setup_macos_podman
                    ;;
                docker)
                    setup_docker
                    ;;
                none)
                    log_error "No container runtime found. Install Docker Desktop or Podman first."
                    exit 1
                    ;;
            esac
            ;;
        MINGW*|MSYS*|CYGWIN*)
            log_info "Windows detected"
            log_info "For Docker Desktop: API is auto-configured, no setup needed"
            log_info "For WSL2: Run this script inside WSL2"
            log_info ""
            log_info "Set in .env: ORCHESTRATOR_DOCKER_HOST=tcp://host.docker.internal:2375"
            ;;
        *)
            log_error "Unsupported OS: $os_type"
            exit 1
            ;;
    esac

    # Verify setup
    sleep 2
    if check_api &>/dev/null; then
        log_info "Setup complete! Container API is accessible."
    else
        log_warn "API may take a moment to start. Run '$0 --check' to verify."
    fi
}

main "$@"
