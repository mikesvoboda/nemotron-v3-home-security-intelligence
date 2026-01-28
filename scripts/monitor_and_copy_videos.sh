#!/usr/bin/env bash
#
# Monitor VEO3 generation and copy videos to docs/media when complete
#

set -euo pipefail

TASK_OUTPUT="/private/tmp/claude/-Users-msvoboda-github-home-security-intelligence/tasks/bcd59ee.output"
TEMP_DIR="/var/folders/77/wvp85_2x3_365pb730sjpxkh0000gp/T/tmp.oFcnQFJdB0"
PROJECT_DIR="/Users/msvoboda/github/home_security_intelligence"

echo "Monitoring VEO3 video generation..."
echo "Task output: $TASK_OUTPUT"
echo ""

# Check if task is still running
check_complete() {
    if grep -q "Complete: .* succeeded" "$TASK_OUTPUT" 2>/dev/null; then
        return 0  # Complete
    else
        return 1  # Still running
    fi
}

# Show current status
show_status() {
    echo "=== Current Status ==="
    tail -15 "$TASK_OUTPUT" | grep -E "Submitting|Polling|SUCCESS|FAILED|Complete:" || echo "Waiting for updates..."
    echo ""
}

# Monitor loop
echo "Press Ctrl+C to stop monitoring (generation will continue in background)"
echo ""

while true; do
    if check_complete; then
        echo "✓ Generation complete!"
        echo ""

        # Show final summary
        tail -20 "$TASK_OUTPUT" | grep "Complete:"
        echo ""

        # Copy videos
        echo "Copying videos to project directory..."
        mkdir -p "$PROJECT_DIR/docs/media/veo3-mascot-branded"
        mkdir -p "$PROJECT_DIR/docs/media/veo3-architecture-tech"

        if [[ -d "$TEMP_DIR/clb-vibecode/nano-videos/media" ]]; then
            cp -v "$TEMP_DIR/clb-vibecode/nano-videos/media/veo3-mascot-branded/"*.mp4 \
                  "$PROJECT_DIR/docs/media/veo3-mascot-branded/" 2>/dev/null || true
            cp -v "$TEMP_DIR/clb-vibecode/nano-videos/media/veo3-architecture-tech/"*.mp4 \
                  "$PROJECT_DIR/docs/media/veo3-architecture-tech/" 2>/dev/null || true

            echo ""
            echo "Videos saved to:"
            echo "  docs/media/veo3-mascot-branded/"
            ls -lh "$PROJECT_DIR/docs/media/veo3-mascot-branded/" 2>/dev/null | tail -n +2 || echo "  (no files yet)"
            echo "  docs/media/veo3-architecture-tech/"
            ls -lh "$PROJECT_DIR/docs/media/veo3-architecture-tech/" 2>/dev/null | tail -n +2 || echo "  (no files yet)"
        else
            echo "⚠ Warning: Video directory not found at $TEMP_DIR"
        fi

        break
    fi

    show_status
    sleep 30
done

echo ""
echo "Done!"
