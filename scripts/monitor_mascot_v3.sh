#!/usr/bin/env bash
#
# Monitor mascot-v3 generation (CORRECTED prompts with full character description)
#

set -euo pipefail

TASK_OUTPUT="/private/tmp/claude/-Users-msvoboda-github-home-security-intelligence/tasks/a325a0b.output"
PROJECT_DIR="/Users/msvoboda/github/home_security_intelligence"

echo "Monitoring mascot-v3 video generation (CORRECTED with full Nano description)..."
echo ""
echo "Fix: Embedded complete mascot description in every prompt"
echo "Expected: Green NVIDIA robot (not blue crystalline character)"
echo ""

while true; do
    if grep -q "Complete: .* succeeded" "$TASK_OUTPUT" 2>/dev/null; then
        echo "✓ Generation complete!"
        echo ""

        tail -10 "$TASK_OUTPUT" | grep "Complete:"
        echo ""

        # The agent should have copied videos to docs/media/veo3-mascot-branded-v3/
        echo "Checking generated videos..."
        if [[ -d "$PROJECT_DIR/docs/media/veo3-mascot-branded-v3" ]]; then
            echo ""
            echo "✓ V3 Videos saved to: docs/media/veo3-mascot-branded-v3/"
            ls -lh "$PROJECT_DIR/docs/media/veo3-mascot-branded-v3/"

            echo ""
            echo "📊 Version Comparison:"
            echo ""
            echo "V1 (wrong character - blue):"
            ls -lh "$PROJECT_DIR/docs/media/veo3-mascot-branded/" 2>/dev/null | tail -4 || echo "  (not found)"
            echo ""
            echo "V2 (wrong character - blue):"
            ls -lh "$PROJECT_DIR/docs/media/veo3-mascot-branded-v2/" 2>/dev/null | tail -4 || echo "  (not found)"
            echo ""
            echo "V3 (CORRECTED - should be green):"
            ls -lh "$PROJECT_DIR/docs/media/veo3-mascot-branded-v3/" 2>/dev/null | tail -4 || echo "  (generating)"
        else
            echo "⚠ Warning: V3 videos directory not created yet"
        fi

        break
    fi

    echo "=== Status Update ==="
    tail -20 "$TASK_OUTPUT" | grep -E "Submitting|Polling|SUCCESS|FAILED|Complete:" || echo "Processing..."
    echo ""

    sleep 30
done

echo ""
echo "🎯 Next Steps:"
echo "  1. Extract frame from V3 videos to verify green NVIDIA robot"
echo "  2. Compare with working examples"
echo "  3. If correct, proceed to final video assembly"
echo ""
echo "Expected: Lime green body, NVIDIA chest text, friendly cartoon eyes"
