#!/usr/bin/env bash
#
# Monitor architecture-v2 generation and copy when complete
#

set -euo pipefail

TASK_OUTPUT="/private/tmp/claude/-Users-msvoboda-github-home-security-intelligence/tasks/b668e92.output"
TEMP_DIR="/var/folders/77/wvp85_2x3_365pb730sjpxkh0000gp/T/tmp.ob2njSBmSU"
PROJECT_DIR="/Users/msvoboda/github/home_security_intelligence"

echo "Monitoring AMAZING architecture-v2 video generation..."
echo "Improved prompts for cinema-quality results"
echo ""

while true; do
    if grep -q "Complete: .* succeeded" "$TASK_OUTPUT" 2>/dev/null; then
        echo "✓ Generation complete!"
        echo ""

        tail -10 "$TASK_OUTPUT" | grep "Complete:"
        echo ""

        # Copy videos
        echo "Copying AMAZING v2 videos to docs/media/..."
        mkdir -p "$PROJECT_DIR/docs/media/veo3-architecture-tech-v2"

        if [[ -d "$TEMP_DIR/clb-vibecode/nano-videos/media/veo3-architecture-tech-v2" ]]; then
            cp -v "$TEMP_DIR/clb-vibecode/nano-videos/media/veo3-architecture-tech-v2/"*.mp4 \
                  "$PROJECT_DIR/docs/media/veo3-architecture-tech-v2/"

            echo ""
            echo "✓ AMAZING videos saved to: docs/media/veo3-architecture-tech-v2/"
            ls -lh "$PROJECT_DIR/docs/media/veo3-architecture-tech-v2/"

            echo ""
            echo "📊 Comparison:"
            echo "V1 (original):"
            ls -lh "$PROJECT_DIR/docs/media/veo3-architecture-tech/" | tail -4
            echo ""
            echo "V2 (AMAZING):"
            ls -lh "$PROJECT_DIR/docs/media/veo3-architecture-tech-v2/" | tail -4
        fi

        break
    fi

    echo "=== Status Update ==="
    tail -20 "$TASK_OUTPUT" | grep -E "Submitting|Polling|SUCCESS|FAILED|Complete:" || echo "Processing..."
    echo ""

    sleep 30
done

echo ""
echo "🎬 Ready for final video assembly!"
echo ""
echo "You now have:"
echo "  ✓ 6 mascot-branded videos (v2 with real mascot)"
echo "  ✓ 3 architecture videos (v2 with AMAZING prompts)"
echo "  = 9 VEO3 videos ready for your presentation"
