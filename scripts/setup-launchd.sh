#!/usr/bin/env bash
# Setup launchd user agents for Home Security Intelligence containers (macOS)
# This script creates plist files and enables auto-start on boot
#
# Usage: ./scripts/setup-launchd.sh
#
# Requirements:
# - macOS with launchd
# - Podman with containers already running

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Home Security Intelligence - launchd Setup (macOS)${NC}"
echo "==================================================="

# Check if running on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}Error: This script is only for macOS${NC}"
    echo "Linux users: Use ./scripts/setup-systemd.sh"
    echo "Windows users: Use ./scripts/setup-windows.ps1"
    exit 1
fi

# Check if podman is available
if ! command -v podman &> /dev/null; then
    echo -e "${RED}Error: podman not found. Please install podman first.${NC}"
    echo "Install with: brew install podman"
    exit 1
fi

# Get podman path
PODMAN_PATH=$(which podman)

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

# Create LaunchAgents directory
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCH_AGENTS_DIR"
echo -e "${GREEN}Created LaunchAgents directory: $LAUNCH_AGENTS_DIR${NC}"

# Function to create plist file for a container
create_plist() {
    local container=$1
    local label="com.security.${container}"
    local plist_file="$LAUNCH_AGENTS_DIR/${label}.plist"

    cat > "$plist_file" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PODMAN_PATH}</string>
        <string>start</string>
        <string>-a</string>
        <string>${container}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/${container}.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/${container}.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
EOF
    echo "$plist_file"
}

# Generate plist files for each container
echo ""
echo "Generating launchd plist files..."
GENERATED=0
declare -a PLIST_FILES
for container in $CONTAINERS; do
    echo -n "  - $container: "
    plist_file=$(create_plist "$container")
    if [[ -f "$plist_file" ]]; then
        echo -e "${GREEN}OK${NC}"
        PLIST_FILES+=("$plist_file")
        GENERATED=$((GENERATED + 1))
    else
        echo -e "${RED}FAILED${NC}"
    fi
done

if [[ $GENERATED -eq 0 ]]; then
    echo -e "${RED}Error: No plist files generated.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Generated $GENERATED launchd plist files${NC}"

# Create a wrapper script for frontend that depends on backend
echo ""
echo "Creating frontend dependency wrapper..."
WRAPPER_DIR="$HOME/.local/bin"
mkdir -p "$WRAPPER_DIR"
FRONTEND_WRAPPER="$WRAPPER_DIR/start-security-frontend.sh"

cat > "$FRONTEND_WRAPPER" << 'EOF'
#!/usr/bin/env bash
# Wait for backend to be healthy before starting frontend
BACKEND_CONTAINER="nemotron-v3-home-security-intelligence_backend_1"
FRONTEND_CONTAINER="nemotron-v3-home-security-intelligence_frontend_1"
MAX_WAIT=120
WAITED=0

echo "Waiting for backend to be ready..."
while [[ $WAITED -lt $MAX_WAIT ]]; do
    if podman inspect "$BACKEND_CONTAINER" --format '{{.State.Health.Status}}' 2>/dev/null | grep -q "healthy"; then
        echo "Backend is healthy, starting frontend..."
        exec podman start -a "$FRONTEND_CONTAINER"
    fi
    sleep 5
    WAITED=$((WAITED + 5))
    echo "Waiting... ($WAITED/$MAX_WAIT seconds)"
done

echo "Backend not healthy after $MAX_WAIT seconds, starting frontend anyway..."
exec podman start -a "$FRONTEND_CONTAINER"
EOF
chmod +x "$FRONTEND_WRAPPER"

# Update frontend plist to use wrapper
FRONTEND_LABEL="com.security.nemotron-v3-home-security-intelligence_frontend_1"
FRONTEND_PLIST="$LAUNCH_AGENTS_DIR/${FRONTEND_LABEL}.plist"
if [[ -f "$FRONTEND_PLIST" ]]; then
    cat > "$FRONTEND_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${FRONTEND_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${FRONTEND_WRAPPER}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/nemotron-v3-home-security-intelligence_frontend_1.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/nemotron-v3-home-security-intelligence_frontend_1.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
EOF
    echo -e "  - Frontend dependency wrapper: ${GREEN}OK${NC}"
fi

# Load all agents
echo ""
echo "Loading launchd agents..."
LOADED=0
for container in $CONTAINERS; do
    label="com.security.${container}"
    plist_file="$LAUNCH_AGENTS_DIR/${label}.plist"

    # Unload first if already loaded (ignore errors)
    launchctl unload "$plist_file" 2>/dev/null || true

    if launchctl load "$plist_file" 2>/dev/null; then
        echo -e "  - $label: ${GREEN}loaded${NC}"
        LOADED=$((LOADED + 1))
    else
        echo -e "  - $label: ${YELLOW}already loaded or failed${NC}"
    fi
done

# Summary
echo ""
echo "==================================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo ""
echo "Services will start automatically on login."
echo ""
echo "Useful commands:"
echo "  # Check service status"
echo "  launchctl list | grep com.security"
echo ""
echo "  # View logs"
echo "  tail -f /tmp/nemotron-v3-home-security-intelligence_backend_1.log"
echo ""
echo "  # Stop a service"
echo "  launchctl unload ~/Library/LaunchAgents/com.security.nemotron-v3-home-security-intelligence_backend_1.plist"
echo ""
echo "  # Start a service"
echo "  launchctl load ~/Library/LaunchAgents/com.security.nemotron-v3-home-security-intelligence_backend_1.plist"
echo ""
echo "  # Disable auto-start (remove plist files)"
echo "  rm ~/Library/LaunchAgents/com.security.nemotron-v3-home-security-intelligence_*.plist"
