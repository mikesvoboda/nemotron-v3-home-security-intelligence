#!/usr/bin/env bash
#
# Monitor V3 final generation using working script
#

set -euo pipefail

TASK_OUTPUT="/private/tmp/claude/-Users-msvoboda-github-home-security-intelligence/tasks/b5c81f2.output"
SLACK_REPO="/Users/msvoboda/gitlab/slack-channel-fetcher"
PROJECT_DIR="/Users/msvoboda/github/home_security_intelligence"

echo "Monitoring V3 Final Generation (using working generator)..."
echo "Expected: Green NVIDIA robot with 'NVIDIA' text on chest"
echo ""

while true; do
    if grep -q "Complete:" "$TASK_OUTPUT" 2>/dev/null; then
        echo "✓ Generation complete!"
        echo ""

        tail -30 "$TASK_OUTPUT" | grep -v "^{" | grep -E "Complete:|SUCCESS|FAILED"
        echo ""

        # Copy videos from slack repo to our project
        echo "Copying videos to project..."
        mkdir -p "$PROJECT_DIR/docs/media/veo3-mascot-branded-v3"

        if [[ -d "$SLACK_REPO/clb-vibecode/nano-videos/docs/media/veo3-mascot-branded-v3" ]]; then
            cp -v "$SLACK_REPO/clb-vibecode/nano-videos/docs/media/veo3-mascot-branded-v3/"*.mp4 \
                  "$PROJECT_DIR/docs/media/veo3-mascot-branded-v3/" 2>/dev/null || true

            echo ""
            echo "✓ V3 videos copied to:"
            ls -lh "$PROJECT_DIR/docs/media/veo3-mascot-branded-v3/"
        else
            echo "⚠ Videos directory not found in slack repo"
            # Try alternate location
            if [[ -d "$SLACK_REPO/clb-vibecode/nano-videos/media/veo3-mascot-branded-v3" ]]; then
                cp -v "$SLACK_REPO/clb-vibecode/nano-videos/media/veo3-mascot-branded-v3/"*.mp4 \
                      "$PROJECT_DIR/docs/media/veo3-mascot-branded-v3/" 2>/dev/null || true
                echo "✓ V3 videos copied from alternate location"
                ls -lh "$PROJECT_DIR/docs/media/veo3-mascot-branded-v3/"
            fi
        fi

        break
    fi

    echo "=== Status Update $(date +%H:%M:%S) ==="
    tail -40 "$TASK_OUTPUT" | grep -v "^{" | grep -E "Submitting|Polling|Status:|SUCCESS|FAILED" | tail -8 || echo "Processing..."
    echo ""

    sleep 30
done

echo ""
echo "🎯 Next: Extract frame and verify green NVIDIA robot"
