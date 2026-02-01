#!/usr/bin/env bash
#
# Generate VEO3 videos for presentation
# Uses the local Python generator script
#
# Examples:
#   ./docs/media/generate_veo3_videos.sh list
#   ./docs/media/generate_veo3_videos.sh generate --category mascot-branded --parallel 3
#   ./docs/media/generate_veo3_videos.sh generate --all --parallel 3
#   ./docs/media/generate_veo3_videos.sh preview --id scene04-what-if-moment
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Check API key
if [[ -z "${NVIDIA_API_KEY:-}" && -z "${NVAPIKEY:-}" ]]; then
  echo "Error: NVIDIA_API_KEY or NVAPIKEY environment variable required"
  echo ""
  echo "Set with:"
  echo "  export NVIDIA_API_KEY='your-key-here'"
  exit 1
fi

# Use the local generator script
cd "$PROJECT_ROOT"
uv run "$SCRIPT_DIR/generate_veo3_videos.py" "$@"
