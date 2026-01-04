#!/usr/bin/env bash
# Setup systemd user services for Home Security Intelligence containers
# This script generates systemd unit files and enables auto-start on boot
#
# Usage: ./scripts/setup-systemd.sh
#
# Requirements:
# - Linux with systemd
# - Podman with containers already running
# - User session (not root)

set -e

# Container name sanitization function (NEM-1124)
# Only allows alphanumeric characters, hyphens, and underscores
# to prevent command injection attacks
sanitize_container_name() {
    local name="$1"
    # Validate: only allow alphanumeric, hyphen, underscore
    # Must start with alphanumeric
    if [[ ! "$name" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]]; then
        echo -e "${RED}Error: Invalid container name detected: $name${NC}" >&2
        echo "Container names must only contain alphanumeric characters, hyphens, and underscores." >&2
        return 1
    fi
    # Limit length to prevent issues
    if [[ ${#name} -gt 128 ]]; then
        echo -e "${RED}Error: Container name too long: $name${NC}" >&2
        return 1
    fi
    echo "$name"
}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Home Security Intelligence - Systemd Setup${NC}"
echo "============================================="

# Check if running on Linux
if [[ "$(uname)" != "Linux" ]]; then
    echo -e "${RED}Error: This script is only for Linux systems${NC}"
    echo "macOS users: Use 'brew services' or launchd for auto-start"
    exit 1
fi

# Check if systemd is available
if ! command -v systemctl &> /dev/null; then
    echo -e "${RED}Error: systemctl not found. Is systemd installed?${NC}"
    exit 1
fi

# Check if podman is available
if ! command -v podman &> /dev/null; then
    echo -e "${RED}Error: podman not found. Please install podman first.${NC}"
    exit 1
fi

# Check if running as root (we want user services)
if [[ $EUID -eq 0 ]]; then
    echo -e "${YELLOW}Warning: Running as root. Systemd user services work better as non-root.${NC}"
    echo "Consider running this script as your regular user."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if containers are running
CONTAINERS=$(podman ps --format "{{.Names}}" | grep -E "nemotron-v3-home-security-intelligence" || true)
if [[ -z "$CONTAINERS" ]]; then
    echo -e "${YELLOW}No running containers found. Starting containers first...${NC}"
    cd "$PROJECT_ROOT"
    podman-compose -f docker-compose.prod.yml up -d
    echo "Waiting 30 seconds for containers to start..."
    sleep 30
    CONTAINERS=$(podman ps --format "{{.Names}}" | grep -E "nemotron-v3-home-security-intelligence" || true)
fi

if [[ -z "$CONTAINERS" ]]; then
    echo -e "${RED}Error: No containers running after startup attempt.${NC}"
    echo "Please run 'podman-compose -f docker-compose.prod.yml up -d' manually first."
    exit 1
fi

# Create systemd user directory
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"
echo -e "${GREEN}Created systemd user directory: $SYSTEMD_USER_DIR${NC}"

# Generate systemd units for each container
echo ""
echo "Generating systemd unit files..."
GENERATED=0
for container in $CONTAINERS; do
    # Sanitize container name to prevent command injection (NEM-1124)
    sanitized_container=$(sanitize_container_name "$container") || continue
    echo -n "  - $sanitized_container: "
    SERVICE_FILE="$SYSTEMD_USER_DIR/${sanitized_container}.service"
    if podman generate systemd --new --name "$sanitized_container" > "$SERVICE_FILE" 2>/dev/null; then
        echo -e "${GREEN}OK${NC}"
        GENERATED=$((GENERATED + 1))
    else
        echo -e "${RED}FAILED${NC}"
    fi
done

if [[ $GENERATED -eq 0 ]]; then
    echo -e "${RED}Error: No systemd units generated.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Generated $GENERATED systemd unit files${NC}"

# Add ExecStartPre cleanup to all services (fixes orphaned container restarts)
echo ""
echo "Adding container cleanup to all services..."
for container in $CONTAINERS; do
    # Sanitize container name to prevent command injection (NEM-1124)
    sanitized_container=$(sanitize_container_name "$container") || continue
    SERVICE_FILE="$SYSTEMD_USER_DIR/${sanitized_container}.service"
    if [[ -f "$SERVICE_FILE" ]]; then
        # Add ExecStartPre to remove orphaned containers before ExecStart
        if ! grep -q "ExecStartPre=.*podman rm" "$SERVICE_FILE"; then
            sed -i "/^ExecStart=/i # Cleanup any orphaned container before starting (fixes stuck container restarts)\nExecStartPre=-/usr/bin/podman rm -f --ignore $sanitized_container" "$SERVICE_FILE"
            echo -e "  - $sanitized_container: ${GREEN}cleanup added${NC}"
        fi
    fi
done

# Add frontend dependency on backend (fixes stale DNS on backend restart)
FRONTEND_SERVICE="$SYSTEMD_USER_DIR/nemotron-v3-home-security-intelligence_frontend_1.service"
BACKEND_SERVICE="nemotron-v3-home-security-intelligence_backend_1.service"
if [[ -f "$FRONTEND_SERVICE" ]]; then
    echo ""
    echo "Adding frontend dependency on backend (fixes DNS cache issues)..."
    # Add After= dependency if not present
    if ! grep -q "After=.*$BACKEND_SERVICE" "$FRONTEND_SERVICE"; then
        sed -i "s/^After=network-online.target/After=network-online.target $BACKEND_SERVICE/" "$FRONTEND_SERVICE"
    fi
    # Add Requires= if not present
    if ! grep -q "Requires=$BACKEND_SERVICE" "$FRONTEND_SERVICE"; then
        sed -i "/^After=/a Requires=$BACKEND_SERVICE" "$FRONTEND_SERVICE"
    fi
    # Add PartOf= if not present (causes frontend to restart when backend restarts)
    if ! grep -q "PartOf=$BACKEND_SERVICE" "$FRONTEND_SERVICE"; then
        sed -i "/^Requires=/a PartOf=$BACKEND_SERVICE" "$FRONTEND_SERVICE"
    fi
    echo -e "  - Frontend linked to backend: ${GREEN}OK${NC}"
fi

# Reload systemd
echo ""
echo "Reloading systemd daemon..."
systemctl --user daemon-reload

# Enable services
echo ""
echo "Enabling services for auto-start..."
ENABLED=0
for container in $CONTAINERS; do
    # Sanitize container name to prevent command injection (NEM-1124)
    sanitized_container=$(sanitize_container_name "$container") || continue
    SERVICE_NAME="${sanitized_container}.service"
    if systemctl --user enable "$SERVICE_NAME" 2>/dev/null; then
        echo -e "  - $SERVICE_NAME: ${GREEN}enabled${NC}"
        ENABLED=$((ENABLED + 1))
    else
        echo -e "  - $SERVICE_NAME: ${YELLOW}already enabled or failed${NC}"
    fi
done

# Enable lingering (allows user services to run without login)
echo ""
echo "Enabling user lingering..."
if loginctl enable-linger "$USER" 2>/dev/null; then
    echo -e "${GREEN}Lingering enabled for user: $USER${NC}"
else
    echo -e "${YELLOW}Could not enable lingering (may already be enabled)${NC}"
fi

# Summary
echo ""
echo "============================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo ""
echo "Services will start automatically on boot."
echo ""
echo "Useful commands:"
echo "  # Check all service status"
echo "  systemctl --user list-units 'nemotron-v3-home-security-intelligence_*'"
echo ""
echo "  # View logs for a service"
echo "  journalctl --user -u nemotron-v3-home-security-intelligence_backend_1 -f"
echo ""
echo "  # Stop all services"
echo "  systemctl --user stop 'nemotron-v3-home-security-intelligence_*'"
echo ""
echo "  # Start all services"
echo "  systemctl --user start 'nemotron-v3-home-security-intelligence_*'"
echo ""
echo "  # Disable auto-start"
echo "  for s in $SYSTEMD_USER_DIR/nemotron-v3*.service; do"
echo "    systemctl --user disable \"\$(basename \$s)\""
echo "  done"
