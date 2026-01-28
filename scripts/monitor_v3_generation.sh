#!/usr/bin/env bash
#
# Monitor VEO3 V3 generation (corrected prompts)
#

set -euo pipefail

TASK_OUTPUT="/private/tmp/claude/-Users-msvoboda-github-home-security-intelligence/tasks/bbdcdfc.output"
PROJECT_DIR="/Users/msvoboda/github/home_security_intelligence"

echo "Monitoring VEO3 V3 video generation..."
echo "Fix: Full mascot description embedded in prompts"
echo "Expected: Green NVIDIA robot with 'NVIDIA' chest text"
echo ""

while true; do
    if grep -q "Generation complete\|✓ Generation complete" "$TASK_OUTPUT" 2>/dev/null; then
        echo "✓ Generation complete!"
        echo ""

        tail -30 "$TASK_OUTPUT" | grep -v "^{" | tail -20
        echo ""

        # Check for generated videos
        echo "Generated videos:"
        echo ""
        if [[ -d "$PROJECT_DIR/docs/media/veo3-mascot-branded-v3" ]]; then
            echo "V3 Mascot videos:"
            ls -lh "$PROJECT_DIR/docs/media/veo3-mascot-branded-v3/" 2>/dev/null || echo "  (none yet)"
        fi
        echo ""

        break
    fi

    # Show recent activity
    echo "=== Status Update $(date +%H:%M:%S) ==="
    tail -40 "$TASK_OUTPUT" | grep -v "^{" | grep -E "Submitting|Polling|Status:|Video|Saved:|succeeded|failed|Complete" | tail -10 || echo "Processing..."
    echo ""

    sleep 30
done

echo ""
echo "🎯 Next: Extract frame to verify green NVIDIA robot character"
