#!/usr/bin/env bash
#
# Monitor mascot-v2 generation and copy when complete
#

set -euo pipefail

TASK_OUTPUT="/private/tmp/claude/-Users-msvoboda-github-home-security-intelligence/tasks/bba4cb0.output"
TEMP_DIR="/var/folders/77/wvp85_2x3_365pb730sjpxkh0000gp/T/tmp.Zy7krPPj88"
PROJECT_DIR="/Users/msvoboda/github/home_security_intelligence"

echo "Monitoring mascot-v2 video generation (real Nemotron mascot)..."
echo ""

while true; do
    if grep -q "Complete: .* succeeded" "$TASK_OUTPUT" 2>/dev/null; then
        echo "✓ Generation complete!"
        echo ""

        tail -10 "$TASK_OUTPUT" | grep "Complete:"
        echo ""

        # Copy videos
        echo "Copying v2 videos to docs/media/..."
        mkdir -p "$PROJECT_DIR/docs/media/veo3-mascot-branded-v2"

        if [[ -d "$TEMP_DIR/clb-vibecode/nano-videos/media/veo3-mascot-branded-v2" ]]; then
            cp -v "$TEMP_DIR/clb-vibecode/nano-videos/media/veo3-mascot-branded-v2/"*.mp4 \
                  "$PROJECT_DIR/docs/media/veo3-mascot-branded-v2/"

            echo ""
            echo "✓ Videos saved to: docs/media/veo3-mascot-branded-v2/"
            ls -lh "$PROJECT_DIR/docs/media/veo3-mascot-branded-v2/"
        fi

        break
    fi

    echo "=== Status Update ==="
    tail -20 "$TASK_OUTPUT" | grep -E "Submitting|Polling|SUCCESS|FAILED|Complete:" || echo "Processing..."
    echo ""

    sleep 30
done

echo ""
echo "Done! You now have both versions:"
echo "  docs/media/veo3-mascot-branded/ (placeholder mascot)"
echo "  docs/media/veo3-mascot-branded-v2/ (real Nemotron mascot)"
