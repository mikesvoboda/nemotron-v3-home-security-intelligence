#!/usr/bin/env bash
#
# Monitor architecture video generation (14 videos)
#

set -euo pipefail

TASK_OUTPUT="/private/tmp/claude/-Users-msvoboda-github-home-security-intelligence/tasks/b660b16.output"
PROJECT_DIR="/Users/msvoboda/github/home_security_intelligence"

echo "Monitoring Architecture Video Generation (14 videos)..."
echo "Using actual project diagrams as reference images"
echo ""

while true; do
    if grep -q "Complete:" "$TASK_OUTPUT" 2>/dev/null; then
        echo "✓ Generation complete!"
        echo ""

        tail -30 "$TASK_OUTPUT" | grep -v "^{" | grep -E "Complete:|SUCCESS|FAILED" || true
        echo ""

        # Show generated videos
        if [[ -d "$PROJECT_DIR/docs/media/veo3-architecture-tech" ]]; then
            echo "✓ Architecture videos saved to: docs/media/veo3-architecture-tech/"
            ls -lh "$PROJECT_DIR/docs/media/veo3-architecture-tech/"
            echo ""

            total_size=$(du -sh "$PROJECT_DIR/docs/media/veo3-architecture-tech" | awk '{print $1}')
            count=$(ls -1 "$PROJECT_DIR/docs/media/veo3-architecture-tech/"*.mp4 2>/dev/null | wc -l | xargs)
            echo "Total: $count videos, $total_size"
        else
            echo "⚠ Architecture directory not found yet"
        fi

        break
    fi

    echo "=== Status Update $(date +%H:%M:%S) ==="
    tail -40 "$TASK_OUTPUT" | grep -v "^{" | grep -E "Submitting|Polling|SUCCESS|FAILED|BATCH|Loading" | tail -15 || echo "Processing..."
    echo ""

    sleep 30
done

echo ""
echo "🎬 14 architecture videos ready!"
echo "   Reference images used: arch-system-overview.png, ai-pipeline-hero.png, flow-batch-aggregator.png, arch-model-zoo.png, security-architecture.png, container-architecture.png"
