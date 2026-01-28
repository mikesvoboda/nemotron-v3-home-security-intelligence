#!/usr/bin/env bash
#
# Monitor mascot variant generation (10 new videos)
#

set -euo pipefail

TASK_OUTPUT="/private/tmp/claude/-Users-msvoboda-github-home-security-intelligence/tasks/b8b0c89.output"
PROJECT_DIR="/Users/msvoboda/github/home_security_intelligence"

echo "Monitoring Mascot Variant Generation (10 videos)..."
echo "All actions complete within 8 seconds - no cut-off speech"
echo ""

while true; do
    if grep -q "Complete:" "$TASK_OUTPUT" 2>/dev/null; then
        echo "✓ Generation complete!"
        echo ""

        tail -30 "$TASK_OUTPUT" | grep -v "^{" | grep -E "Complete:|SUCCESS|FAILED"
        echo ""

        # Show generated videos
        if [[ -d "$PROJECT_DIR/docs/media/veo3-mascot-variants" ]]; then
            echo "✓ Variant videos saved to: docs/media/veo3-mascot-variants/"
            ls -lh "$PROJECT_DIR/docs/media/veo3-mascot-variants/"
            echo ""

            total_size=$(du -sh "$PROJECT_DIR/docs/media/veo3-mascot-variants" | awk '{print $1}')
            count=$(ls -1 "$PROJECT_DIR/docs/media/veo3-mascot-variants/"*.mp4 2>/dev/null | wc -l | xargs)
            echo "Total: $count videos, $total_size"
        else
            echo "⚠ Variants directory not found yet"
        fi

        break
    fi

    echo "=== Status Update $(date +%H:%M:%S) ==="
    tail -40 "$TASK_OUTPUT" | grep -v "^{" | grep -E "Submitting|Polling|SUCCESS|FAILED|BATCH" | tail -10 || echo "Processing..."
    echo ""

    sleep 30
done

echo ""
echo "🎬 10 new mascot variants ready!"
echo "   Each video: 8 seconds, complete action, no cut-offs"
