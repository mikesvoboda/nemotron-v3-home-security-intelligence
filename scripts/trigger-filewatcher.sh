#!/bin/bash
# =============================================================================
# Trigger File Watcher Script
# =============================================================================
# Finds real image files under /export/foscam and touches them to trigger
# the file watcher pipeline for processing.
#
# Usage:
#   ./scripts/trigger-filewatcher.sh [OPTIONS]
#
# Options:
#   --count N       Number of images to touch (default: 100)
#   --camera NAME   Only touch images from specific camera (optional)
#   --dry-run       Show what would be touched without doing it
#   --help, -h      Show this help message
#
# Examples:
#   ./scripts/trigger-filewatcher.sh                    # Touch 100 random images
#   ./scripts/trigger-filewatcher.sh --count 50         # Touch 50 images
#   ./scripts/trigger-filewatcher.sh --camera kitchen   # Touch 100 kitchen images
#   ./scripts/trigger-filewatcher.sh --dry-run          # Preview without touching
# =============================================================================

set -e

# Configuration
FOSCAM_PATH="${CAMERA_PATH:-/export/foscam}"
COUNT=100
CAMERA=""
DRY_RUN=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

show_help() {
    head -25 "$0" | tail -20
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            ;;
        --count)
            COUNT="$2"
            shift 2
            ;;
        --camera)
            CAMERA="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${CYAN}=== File Watcher Trigger ===${NC}"
echo ""

# Build find path
if [ -n "$CAMERA" ]; then
    SEARCH_PATH="$FOSCAM_PATH/$CAMERA"
    echo -e "Camera:  ${GREEN}$CAMERA${NC}"
else
    SEARCH_PATH="$FOSCAM_PATH"
    echo -e "Camera:  ${GREEN}all${NC}"
fi

echo -e "Path:    ${GREEN}$SEARCH_PATH${NC}"
echo -e "Count:   ${GREEN}$COUNT${NC}"
echo -e "Dry run: ${GREEN}$DRY_RUN${NC}"
echo ""

# Check path exists
if [ ! -d "$SEARCH_PATH" ]; then
    echo -e "${RED}Error: Path does not exist: $SEARCH_PATH${NC}"
    exit 1
fi

# Find real image files (non-empty jpg files)
echo -e "${CYAN}Finding images...${NC}"
IMAGES=$(find "$SEARCH_PATH" -name "*.jpg" -type f -size +0 2>/dev/null | shuf | head -n "$COUNT")

FOUND=$(echo "$IMAGES" | grep -c . || echo 0)

if [ "$FOUND" -eq 0 ]; then
    echo -e "${RED}No images found in $SEARCH_PATH${NC}"
    exit 1
fi

echo -e "Found:   ${GREEN}$FOUND images${NC}"
echo ""

# Touch files
if [ "$DRY_RUN" = "true" ]; then
    echo -e "${YELLOW}[DRY-RUN] Would touch these files:${NC}"
    echo "$IMAGES" | head -10
    if [ "$FOUND" -gt 10 ]; then
        echo "... and $((FOUND - 10)) more"
    fi
else
    echo -e "${CYAN}Touching $FOUND images...${NC}"
    echo "$IMAGES" | xargs -I{} touch "{}"
    echo -e "${GREEN}✓ Touched $FOUND images${NC}"
    echo ""
    echo -e "${CYAN}Check file watcher logs:${NC}"
    echo "  podman logs --tail 50 nemotron-v3-home-security-intelligence_backend_1"
fi

echo ""
echo -e "${GREEN}Done!${NC}"
